#!/usr/bin/env python3
import subprocess
import time
from pathlib import Path

URL_GROUP_DELAY = 3
CHROME_PATH = r"/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"

# src/urls.py -> src -> root
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent


def open_url_grouped_with_chrome() -> None:
    # config/urls.local.txt 優先、なければ config/urls.txt
    url_file = REPO_ROOT / "config" / "urls.local.txt"
    if not url_file.exists():
        url_file = REPO_ROOT / "config" / "urls.txt"

    if not url_file.exists():
        print(f"URLファイルが見つかりません: config/urls.txt")
        return

    print(f"\n=== URL起動開始: {url_file.name} ===\n")

    if not Path(CHROME_PATH).exists():
        print(f"Chrome が見つかりません: {CHROME_PATH}")
        return

    group_num = 1
    current_group_urls: list[str] = []

    text = url_file.read_text(encoding="utf-8")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        
        if not line or line.startswith("#"):
            continue
            
        # コメント除去 (http://... # comment)
        if " #" in line:
             line = line.split(" #", 1)[0].strip()

        if line == "---":
            if current_group_urls:
                _launch_chrome(current_group_urls, group_num)
                time.sleep(URL_GROUP_DELAY)
            group_num += 1
            current_group_urls = []
            continue

        current_group_urls.append(line)

    if current_group_urls:
        _launch_chrome(current_group_urls, group_num)

    print("\n=== 完了 ===")


def _launch_chrome(urls: list[str], group_num: int) -> None:
    print(
        f"\n━━━ グループ {group_num} を新規ウィンドウで起動 "
        f"({len(urls)}件) ━━━"
    )
    cmd = [CHROME_PATH, "--new-window"] + urls
    subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )