#!/usr/bin/env python3
"""日報ファイル（data/notes/daily/YYYY/YYYY-MM-DD.md）の生成と書き込み。

日報は「人が書く場所」なので、機械が書くのは自動生成ブロックの中だけに限る。
ブロック外は絶対に触らない。
"""
from pathlib import Path
from datetime import date, timedelta

# src/note.py -> src -> root
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

# 自動生成ブロックの目印。begin 行の文言は変わりうるのでプレフィックスで探す。
AUTO_BEGIN_PREFIX = "<!-- auto:begin"
AUTO_BEGIN = f"{AUTO_BEGIN_PREFIX} ここから下は daily.py が毎回書き換えます。手書きは上に -->"
AUTO_END = "<!-- auto:end -->"


def daily_file_path(day: date) -> Path:
    """data/notes/daily/YYYY/YYYY-MM-DD.md"""
    return REPO_ROOT / "data" / "notes" / "daily" / f"{day:%Y}" / f"{day:%Y-%m-%d}.md"


def ensure_daily_file(day: date) -> tuple[Path, bool]:
    """日報ファイルを用意する。戻り値は (パス, 新規作成したか)。"""
    out_file = daily_file_path(day)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    if out_file.exists():
        return out_file, False

    header = f"# {day:%Y-%m-%d} 日報\n"

    # config/templates/daily-template.md
    template = REPO_ROOT / "config" / "templates" / "daily-template.md"

    if template.exists():
        lines = template.read_text(encoding="utf-8").splitlines(True)
        if lines:
            lines[0] = header
        out_file.write_text("".join(lines), encoding="utf-8")
    else:
        # テンプレートがない場合のフォールバック
        out_file.write_text(
            f"{header}\n## 今日やること\n- \n\n## メモ\n- \n", encoding="utf-8"
        )

    return out_file, True


def latest_existing_day(before: date) -> date | None:
    """before より前で、いちばん新しい日報ファイルの日付。"""
    base = REPO_ROOT / "data" / "notes" / "daily"
    if not base.exists():
        return None

    latest = None
    for path in base.glob("*/*.md"):
        try:
            day = date.fromisoformat(path.stem)
        except ValueError:
            continue  # タスク一覧_2025-05_2026-07.md のような日付以外のファイル
        if day < before and (latest is None or day > latest):
            latest = day
    return latest


def missing_weekdays(today: date, limit_days: int = 14) -> list[date]:
    """叩き忘れた平日を拾う。

    最後に存在する日報の翌日から昨日までを見る。limit_days は長期休暇明けに
    大量生成されるのを防ぐ上限。祝日は判定していない（祝日カレンダーを持たない）。
    """
    last = latest_existing_day(today)
    if last is None:
        return []  # 初回は遡らない

    day = max(last + timedelta(days=1), today - timedelta(days=limit_days))
    missing = []
    while day < today:
        if day.weekday() < 5 and not daily_file_path(day).exists():
            missing.append(day)
        day += timedelta(days=1)
    return missing


def has_auto_block(path: Path) -> bool:
    """自動生成ブロックが既に書かれているか（Trello 取得失敗時に消さない判定用）。"""
    if not path.exists():
        return False
    return AUTO_BEGIN_PREFIX in path.read_text(encoding="utf-8")


def write_auto_block(path: Path, body: str) -> None:
    """日報の自動生成ブロックを差し替える。無ければ末尾に足す。

    追記ではなく置換なので、何度呼んでも二重にならない。
    """
    text = path.read_text(encoding="utf-8")
    block = f"{AUTO_BEGIN}\n\n{body.strip()}\n\n{AUTO_END}\n"

    begin = text.find(AUTO_BEGIN_PREFIX)
    if begin == -1:
        path.write_text(f"{text.rstrip()}\n\n---\n\n{block}", encoding="utf-8")
        return

    end = text.find(AUTO_END, begin)
    tail = text[end + len(AUTO_END) :].lstrip("\n") if end != -1 else ""
    path.write_text(f"{text[:begin]}{block}{tail}", encoding="utf-8")
