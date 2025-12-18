#!/usr/bin/env python3
import os
import subprocess
import time
import shutil
from pathlib import Path

# src配下のモジュールとしてインポート
from src.daily import create_daily_file
from src.urls import open_url_grouped_with_chrome

# 実行スクリプトのあるディレクトリ（プロジェクトルート）
REPO_ROOT = Path(__file__).resolve().parent

# data/todo.txt をデフォルトとして使用
TODO_FILE_PATH = Path(os.environ.get("TODO_FILE", REPO_ROOT / "data" / "todo.txt"))


def append_todo_to_daily(today_file: Path | None) -> None:
    """
    todo.txt の内容を日報ファイルの末尾に追記する
    """
    if not today_file or not today_file.exists():
        return

    if not TODO_FILE_PATH.exists():
        return

    try:
        content = TODO_FILE_PATH.read_text(encoding="utf-8").strip()
        
        if not content:
            return

        print(f"=== TODO追記中 ({TODO_FILE_PATH.name}) ===")
        
        with open(today_file, "a", encoding="utf-8") as f:
            f.write("\n\n## Unsorted TODO\n")
            f.write(content)
            f.write("\n")
        
        print("  ✓ 日報に追記しました")

        # 【オプション】追記後にtodo.txtの中身を空にする場合
        # TODO_FILE_PATH.write_text("", encoding="utf-8")

    except Exception as e:
        print(f"  ! TODO追記に失敗しました: {e}")


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
    print("=== デイリーファイル作成中 ===")
    today_file = create_daily_file()
    if today_file:
        print(f"  ✓ {today_file}")
    
    append_todo_to_daily(today_file)

    open_vscode(today_file)
    open_url_grouped_with_chrome()


if __name__ == "__main__":
    main()