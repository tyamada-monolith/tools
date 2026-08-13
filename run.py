#!/usr/bin/env python3
"""起動セレモニー。日次データを作ってから VSCode と Chrome を開く。

データだけ欲しいとき（時刻トリガーなど）は daily.py を直接叩く。
"""
import os
import shutil
import subprocess
from pathlib import Path

from daily import run_daily
from src.urls import open_url_grouped_with_chrome

# 実行スクリプトのあるディレクトリ（プロジェクトルート）
REPO_ROOT = Path(__file__).resolve().parent


def open_vscode(today_file: Path | None) -> None:
    code_path = shutil.which("code")
    if not code_path:
        print("VSCode (codeコマンド) が見つかりません")
        return

    print("=== VSCode起動中 ===")

    # デフォルトでプロジェクトルートを開く
    workspace = os.environ.get("WORKSPACE", str(REPO_ROOT))

    # ワークスペースと日報は1回の呼び出しで渡す。2回に分けて sleep で繋ぐと、
    # VSCode のコールドスタート時に2本目の code が別ウィンドウを作り、
    # 日報がワークスペースと違うウィンドウで開く。
    cmd = [code_path, workspace]
    if today_file:
        cmd += ["-g", str(today_file)]
    try:
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def generate_daily_plan() -> None:
    """/daily-plan を Claude Code のヘッドレスモードで叩く。

    Trello の盤面読み → タイムテーブル生成 → 日報の plan ブロックへの書き込み
    まで数分かかるので、起動だけして待たない（VSCode は外部変更を自動で読み直す）。
    Trello は読み取りツールしか許可しないので、ここからカードが動くことはない。
    """
    claude_path = shutil.which("claude")
    if not claude_path:
        print("claude コマンドが見つかりません（/daily-plan はスキップ）")
        return

    log_path = REPO_ROOT / "data" / "daily-plan.log"
    print(f"=== /daily-plan をバックグラウンドで実行中（ログ: {log_path.relative_to(REPO_ROOT)}）===")
    with open(log_path, "w", encoding="utf-8") as log:
        subprocess.Popen(
            [
                claude_path,
                "-p",
                "/daily-plan",
                "--allowedTools",
                ",".join(
                    [
                        "Read",
                        "Edit(data/notes/**)",
                        "Write(data/notes/**)",
                        "mcp__claude_ai_Trello__trelloReadBoard",
                        "mcp__claude_ai_Trello__trelloReadCard",
                        "mcp__claude_ai_Trello__trelloReadList",
                        "mcp__claude_ai_Trello__trelloReadMember",
                    ]
                ),
            ],
            cwd=REPO_ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # 端末を閉じても道連れにしない
        )


def main() -> None:
    # 人が叩いたときは曜日を問わず作る（土日に出社したケース）
    today_file = run_daily(force=True)

    generate_daily_plan()
    open_vscode(today_file)
    open_url_grouped_with_chrome()


if __name__ == "__main__":
    main()
