#!/usr/bin/env python3
"""Trello REST の薄いラッパー。取得だけを担当し、整形は snapshot.py に任せる。"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# src/trello.py -> src -> root
REPO_ROOT = Path(__file__).resolve().parent.parent

API_BASE = "https://api.trello.com/1"
TIMEOUT_SEC = 20

# 取得するカードのフィールド。増やすとスナップショットの json も太るので必要な分だけ。
CARD_FIELDS = "id,name,desc,due,dueComplete,shortUrl,dateLastActivity,labels,pos"


class TrelloError(RuntimeError):
    """Trello 取得の失敗。メッセージに認証情報を含めない。"""


def scrub(text: str, *secrets: str) -> str:
    """API キー・トークンを伏せる。

    Trello はクエリ文字列で認証するため、URL がそのまま出るとトークンが平文で残る。
    """
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    return text


def _parse_env_file(path: Path) -> dict:
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip("\"'")
    return values


# daily-startup/.env が無ければここを見る。所内で同じトークンを使い回しているので、
# 2か所に複製しないほうが漏れにくい。パスだけなので秘密ではない。
# 片方を移動したら黙って壊れるのではなく「認証情報がありません」で止まる。
FALLBACK_ENV_PATH = (
    Path.home() / "workspace_tyamada/monolith-gas/trello-tools/trello-card-automator/.env"
)


def _env_file_candidates() -> list:
    override = os.environ.get("TRELLO_ENV_FILE")
    if override:
        return [Path(override)]
    return [REPO_ROOT / ".env", FALLBACK_ENV_PATH]


def load_credentials() -> tuple[str, str]:
    """環境変数 → .env → trello-card-automator の .env の順に探す。

    シェルの設定に依存させない（スケジューラ経由では ~/.zshrc が読まれないため）。
    """
    key = os.environ.get("TRELLO_API_KEY", "")
    token = os.environ.get("TRELLO_TOKEN", "")

    if not (key and token):
        candidates = _env_file_candidates()
        found = next((p for p in candidates if p.exists()), None)
        if found is None:
            tried = " / ".join(str(p) for p in candidates)
            raise TrelloError(f"認証情報がありません（環境変数も未設定、探した先: {tried}）")
        values = _parse_env_file(found)
        key = key or values.get("TRELLO_API_KEY", "")
        token = token or values.get("TRELLO_TOKEN", "")

    if not (key and token):
        raise TrelloError("TRELLO_API_KEY / TRELLO_TOKEN が空です")

    return key, token


def fetch_list_cards(list_id: str, key: str, token: str) -> list:
    """リスト内のオープンなカードを取得する。"""
    query = urllib.parse.urlencode(
        {
            "key": key,
            "token": token,
            "fields": CARD_FIELDS,
            "members": "true",
            "member_fields": "fullName,username",
            "filter": "open",
        }
    )
    url = f"{API_BASE}/lists/{urllib.parse.quote(list_id)}/cards?{query}"

    # 例外は URL を含みうるので、必ず scrub してから投げ直す（from None で連鎖も切る）
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SEC) as res:
            body = res.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise TrelloError(scrub(f"HTTP {e.code} {e.reason}", key, token)) from None
    except urllib.error.URLError as e:
        raise TrelloError(scrub(f"接続失敗: {e.reason}", key, token)) from None
    except TimeoutError:
        raise TrelloError(f"タイムアウト（{TIMEOUT_SEC}秒）") from None

    try:
        cards = json.loads(body)
    except json.JSONDecodeError:
        raise TrelloError("Trello の応答が JSON として読めません") from None

    if not isinstance(cards, list):
        raise TrelloError("Trello の応答が想定と違います（配列ではない）")

    return cards
