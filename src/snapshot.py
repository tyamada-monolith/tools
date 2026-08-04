#!/usr/bin/env python3
"""Trello リストのスナップショット蓄積と前回比の算出。

溜めるのは json だけ。md は日報の自動生成ブロックに直接埋めるので持たない。
差分の「正」は json であって md ではない（md で diff を取ると表記ゆれで汚れる）。
"""
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

# src/snapshot.py -> src -> root
REPO_ROOT = Path(__file__).resolve().parent.parent
JST = ZoneInfo("Asia/Tokyo")

# 取得対象。slug は data/trello/ 配下のディレクトリ名になるので、
# 変えると蓄積が別系列になり過去分との差分が切れる。
CONFIG = {
    "list_id": "681dc21d190923eb7ba06626",
    "name": "エンジニアチームタスク",
    "slug": "engineer-team",
    "board_url": "https://trello.com/b/fPHCPsiF",
    "stale_days": 14,
}


def now_jst() -> datetime:
    return datetime.now(JST)


def parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


# ---------------------------------------------------------------- 保存 / 読み出し


def snapshot_dir(slug: str) -> Path:
    return REPO_ROOT / "data" / "trello" / slug


def snapshot_path(slug: str, day: date) -> Path:
    return snapshot_dir(slug) / f"{day:%Y}" / f"{day:%Y-%m-%d}.json"


def normalize_card(card: dict) -> dict:
    """Trello の生カードから、溜めたい分だけ抜いて安定した形にする。"""
    return {
        "id": card.get("id", ""),
        "name": (card.get("name") or "").strip(),
        "desc": card.get("desc") or "",
        "due": card.get("due"),
        "due_complete": bool(card.get("dueComplete")),
        "url": card.get("shortUrl") or "",
        "last_activity_at": card.get("dateLastActivity"),
        "labels": [
            {"name": label.get("name") or "", "color": label.get("color") or ""}
            for label in (card.get("labels") or [])
        ],
        "members": [
            (m.get("fullName") or m.get("username") or "").strip()
            for m in (card.get("members") or [])
        ],
        "pos": card.get("pos"),
    }


def build_payload(cards: list, config: dict, fetched_at: datetime) -> dict:
    return {
        "fetched_at": fetched_at.isoformat(),
        "list": {
            "id": config["list_id"],
            "name": config["name"],
            "board_url": config["board_url"],
        },
        "cards": [normalize_card(c) for c in cards],
    }


def save_snapshot(payload: dict, slug: str, day: date) -> Path:
    """その日の json を書く（同日再実行は上書き）。"""
    path = snapshot_path(slug, day)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def find_previous(slug: str, day: date) -> tuple[date, dict] | None:
    """day より前で、いちばん新しいスナップショット。

    「昨日」固定ではなく「直近に存在する分」を返すので、叩かなかった日があっても
    差分がその期間をまたいで繋がる。
    """
    base = snapshot_dir(slug)
    if not base.exists():
        return None

    latest = None
    for path in base.glob("*/*.json"):
        try:
            found = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if found < day and (latest is None or found > latest[0]):
            latest = (found, path)

    if latest is None:
        return None
    try:
        return latest[0], json.loads(latest[1].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------- 差分


def compute_diff(previous: dict | None, current: dict, stale_days: int, now: datetime) -> dict:
    prev_cards = {c["id"]: c for c in (previous or {}).get("cards", [])}
    curr_cards = {c["id"]: c for c in current["cards"]}

    added = [c for cid, c in curr_cards.items() if cid not in prev_cards]
    removed = [c for cid, c in prev_cards.items() if cid not in curr_cards]

    due_changed, renamed = [], []
    for cid, card in curr_cards.items():
        before = prev_cards.get(cid)
        if before is None:
            continue
        if (before.get("due") or None) != (card.get("due") or None):
            due_changed.append((card, before.get("due")))
        if (before.get("name") or "") != card["name"]:
            renamed.append((card, before.get("name") or ""))

    stale = []
    for card in current["cards"]:
        last = parse_dt(card["last_activity_at"])
        if last is not None and (now - last).days >= stale_days:
            stale.append(card)

    return {
        "has_previous": previous is not None,
        "added": added,
        "removed": removed,
        "due_changed": due_changed,
        "renamed": renamed,
        "stale": stale,
    }


def business_days_between(start: date, end: date) -> int:
    """start の翌日から end までの平日数。空き日数の目安に使う（祝日は見ない）。"""
    count = 0
    day = start + timedelta(days=1)
    while day <= end:
        if day.weekday() < 5:
            count += 1
        day += timedelta(days=1)
    return count


# ---------------------------------------------------------------- 整形


def sort_by_position(cards: list) -> list:
    """Trello のリスト上の並び順に揃える。

    Trello に優先度フィールドは無いので、リストの並び（pos）を優先度として扱う。
    Trello 側でカードを上下に動かせば、そのまま日報の順番になる。
    """

    def position(card: dict) -> float:
        try:
            return float(card.get("pos") or 0)
        except (TypeError, ValueError):
            return 0.0

    return sorted(cards, key=position)


def status_mark(card: dict, now: datetime, soon_days: int = 2) -> str:
    """期限の状態を1文字で表す。優先度順に並べても期限が読み取れるように。"""
    due = parse_dt(card["due"])
    if due is None:
        return "⚪"
    if card["due_complete"]:
        return "✅"
    if due < now:
        return "🔴"
    if (due - now).days <= soon_days:
        return "🟠"
    return "🟡"


def card_line(card: dict, mark: str, now: datetime) -> str:
    """1カード1行。grep と diff が効くように区切りを固定する。"""
    due = parse_dt(card["due"])
    if due is None:
        due_text = "期限なし"
    else:
        due_text = due.astimezone(JST).strftime("%m/%d %H:%M")
        if card["due_complete"]:
            due_text += "(済)"

    members = ",".join(sorted(m for m in card["members"] if m)) or "-"

    last = parse_dt(card["last_activity_at"])
    stale_text = f"停滞{(now - last).days}d" if last is not None else "停滞?"

    checkbox = "x" if card["due_complete"] else " "
    return (
        f"- [{checkbox}] {mark} {due_text} | {card['name']} | {members} | "
        f"{stale_text} | {card['url']}"
    )


def _names(cards: list, limit: int = 5) -> str:
    names = [c["name"] for c in cards]
    if len(names) > limit:
        return "、".join(names[:limit]) + f" ほか{len(names) - limit}件"
    return "、".join(names)


def render_diff(diff: dict, previous_day: date | None, today: date, stale_days: int) -> list:
    if not diff["has_previous"] or previous_day is None:
        return ["### 前回比", "- 初回取得（比較対象なし）"]

    gap = business_days_between(previous_day, today)
    gap_text = f"（{gap}営業日ぶり）" if gap > 1 else ""
    lines = [f"### 前回比 {previous_day:%Y-%m-%d} → {today:%Y-%m-%d}{gap_text}"]

    if diff["added"]:
        lines.append(f"- 🆕 新規 {len(diff['added'])}: {_names(diff['added'])}")
    if diff["removed"]:
        lines.append(f"- ✅ 消えた（完了/移動） {len(diff['removed'])}: {_names(diff['removed'])}")
    for card, before in diff["due_changed"]:
        before_dt = parse_dt(before)
        after_dt = parse_dt(card["due"])
        fmt = lambda d: d.astimezone(JST).strftime("%m/%d %H:%M") if d else "なし"
        lines.append(f"- 📅 期限変更: {card['name']} {fmt(before_dt)} → {fmt(after_dt)}")
    for card, before in diff["renamed"]:
        lines.append(f"- ✏️ 名称変更: {before} → {card['name']}")
    if diff["stale"]:
        lines.append(
            f"- 💤 {stale_days}日以上動きなし {len(diff['stale'])}: {_names(diff['stale'])}"
        )

    if len(lines) == 1:
        lines.append("- 変化なし")
    return lines


def render_section(payload: dict, diff: dict, previous_day: date | None, config: dict) -> str:
    """日報に埋める Trello セクション。"""
    now = parse_dt(payload["fetched_at"]) or now_jst()
    today = now.astimezone(JST).date()

    cards = sort_by_position(payload["cards"])
    marks = [status_mark(card, now) for card in cards]
    counts = " ".join(
        f"{mark}{marks.count(mark)}"
        for mark in ("🔴", "🟠", "🟡", "⚪", "✅")
        if marks.count(mark)
    )

    lines = [
        f"## Trello: {payload['list']['name']}",
        "",
        f"{payload['list']['board_url']} / 取得 {now.astimezone(JST):%Y-%m-%d %H:%M} JST / "
        f"{len(cards)}件（{counts}）",
        "",
        "並びは Trello のリスト順 = 優先度。入れ替えるときは Trello 側でカードを動かす。",
        "",
    ]
    lines += render_diff(diff, previous_day, today, config["stale_days"])

    # 優先度順に並べると期限切れが下に埋もれるので、ここで拾い直す
    urgent = [card for card, mark in zip(cards, marks) if mark in ("🔴", "🟠")]
    if urgent:
        lines.append(f"- ⚠ 期限切れ・期限間近 {len(urgent)}: {_names(urgent)}")

    lines += ["", "### 一覧（優先度順）"]
    lines += [card_line(card, mark, now) for card, mark in zip(cards, marks)]

    return "\n".join(lines)
