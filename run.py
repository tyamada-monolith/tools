#!/usr/bin/env python3
"""起動セレモニー。日次データを作ってから VSCode と Chrome を開く。

データだけ欲しいとき（時刻トリガーなど）は daily.py を直接叩く。
"""
import os
import shutil
import subprocess
import time
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
    try:
        subprocess.Popen(
            [code_path, workspace],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    time.sleep(0.4)

    if today_file:
        try:
            subprocess.Popen(
                [code_path, "-r", "-g", str(today_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def main() -> None:
    # 人が叩いたときは曜日を問わず作る（土日に出社したケース）
    today_file = run_daily(force=True)

    open_vscode(today_file)
    open_url_grouped_with_chrome()


if __name__ == "__main__":
    main()
