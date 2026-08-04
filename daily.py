#!/usr/bin/env python3
"""日次データだけを作る。UI を触らないので時刻トリガーからも叩ける。

  python daily.py            # 平日のみ実行（土日はスキップ）
  python daily.py --force    # 土日でも実行

やること:
  1. 叩き忘れた平日の日報ファイルを補完する
  2. 今日の日報ファイルを用意する
  3. Trello のリストを取得して json に溜め、前回比を出す
  4. 手書き TODO + Trello 一覧を日報の自動生成ブロックに書く（追記ではなく置換）

run.py はこれを呼んだあとに VSCode と Chrome を開く。
"""
import os
import sys
from datetime import date
from pathlib import Path

from src import snapshot
from src.note import (
    daily_file_path,
    ensure_daily_file,
    has_auto_block,
    missing_weekdays,
    write_auto_block,
)
from src.trello import TrelloError, fetch_list_cards, load_credentials

REPO_ROOT = Path(__file__).resolve().parent

# data/todo.txt をデフォルトとして使用
TODO_FILE_PATH = Path(os.environ.get("TODO_FILE", REPO_ROOT / "data" / "todo.txt"))

# 長期休暇明けに大量生成されるのを防ぐ上限
BACKFILL_LIMIT_DAYS = 14


def read_todo() -> str:
    if not TODO_FILE_PATH.exists():
        return ""
    return TODO_FILE_PATH.read_text(encoding="utf-8").strip()


def backfill_missing_days(today: date) -> None:
    """叩き忘れた平日の日報ファイルを作る。

    Trello は過去の盤面を返せないので、ここで作るのは日報の枠だけ。差分は
    「直近に存在するスナップショット」と比較するので、空いた期間をまたいで繋がる。
    """
    for day in missing_weekdays(today, BACKFILL_LIMIT_DAYS):
        path, created = ensure_daily_file(day)
        if created:
            print(f"  ✓ 欠損日を補完: {path.name}")


def build_trello_section(today: date) -> str:
    config = snapshot.CONFIG
    key, token = load_credentials()
    cards = fetch_list_cards(config["list_id"], key, token)

    fetched_at = snapshot.now_jst()
    payload = snapshot.build_payload(cards, config, fetched_at)

    previous = snapshot.find_previous(config["slug"], today)
    diff = snapshot.compute_diff(
        previous[1] if previous else None, payload, config["stale_days"], fetched_at
    )

    saved = snapshot.save_snapshot(payload, config["slug"], today)
    print(f"  ✓ {len(cards)}件 → {saved.relative_to(REPO_ROOT)}")

    return snapshot.render_section(payload, diff, previous[0] if previous else None, config)


def run_daily(force: bool = False) -> Path | None:
    today = date.today()

    if not force and today.weekday() >= 5:
        print(f"=== {today} は土日なのでスキップ（--force で実行）===")
        path = daily_file_path(today)
        return path if path.exists() else None

    print("=== 日報ファイル作成中 ===")
    backfill_missing_days(today)
    today_file, created = ensure_daily_file(today)
    print(f"  {'✓ 新規' if created else '- 既存'} {today_file}")

    print("=== Trello 取得中 ===")
    trello_section = None
    try:
        trello_section = build_trello_section(today)
    except TrelloError as e:
        print(f"  ! 取得に失敗: {e}")

    # 取得できなかったとき、今日すでに書けている一覧を消してしまわない
    if trello_section is None and has_auto_block(today_file):
        print("  - 既存の自動生成ブロックを保持した")
        return today_file

    sections = []
    todo = read_todo()
    if todo:
        sections.append(f"## TODO（手書き: {TODO_FILE_PATH.name}）\n\n{todo}")
    sections.append(
        trello_section
        if trello_section
        else "## Trello\n\n- ⚠ 取得に失敗した。`python daily.py` を再実行する"
    )

    write_auto_block(today_file, "\n\n".join(sections))
    print("  ✓ 日報の自動生成ブロックを更新した")

    return today_file


def main() -> None:
    run_daily(force="--force" in sys.argv[1:])


if __name__ == "__main__":
    main()
