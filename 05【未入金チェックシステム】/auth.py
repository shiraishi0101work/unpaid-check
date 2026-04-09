"""
OAuth 2.0認証モジュール
MFクラウド請求書・会計の両方に対応
トークンはJSONファイルに保存し、期限切れ時は自動リフレッシュ
"""

import os
import json
import time
import webbrowser
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

load_dotenv()

# ========================================
# MFクラウドAPIのエンドポイント定義
# ========================================
SERVICES = {
    "invoice": {
        "auth_url":  "https://invoice.moneyforward.com/oauth/authorize",
        "token_url": "https://invoice.moneyforward.com/oauth/token",
        "scope":     "read",
        "client_id":     os.getenv("MF_INVOICE_CLIENT_ID"),
        "client_secret": os.getenv("MF_INVOICE_CLIENT_SECRET"),
        "redirect_uri":  os.getenv("MF_INVOICE_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob"),
        "token_file": "token_invoice.json",
    },
    "accounting": {
        "auth_url":  "https://accounting.moneyforward.com/oauth/authorize",
        "token_url": "https://accounting.moneyforward.com/oauth/token",
        "scope":     "read",
        "client_id":     os.getenv("MF_ACCOUNTING_CLIENT_ID"),
        "client_secret": os.getenv("MF_ACCOUNTING_CLIENT_SECRET"),
        "redirect_uri":  os.getenv("MF_ACCOUNTING_REDIRECT_URI", "urn:ietf:wg:oauth:2.0:oob"),
        "token_file": "token_accounting.json",
    },
}

TOKEN_DIR = os.path.join(os.path.dirname(__file__), "tokens")


def _token_path(service_name: str) -> str:
    os.makedirs(TOKEN_DIR, exist_ok=True)
    return os.path.join(TOKEN_DIR, SERVICES[service_name]["token_file"])


def _save_token(service_name: str, token_data: dict):
    """トークンをファイルに保存（取得時刻も記録）"""
    token_data["saved_at"] = time.time()
    with open(_token_path(service_name), "w", encoding="utf-8") as f:
        json.dump(token_data, f, ensure_ascii=False, indent=2)


def _load_token(service_name: str) -> dict | None:
    path = _token_path(service_name)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _is_expired(token_data: dict) -> bool:
    """アクセストークンが期限切れかどうか確認（60秒のマージン付き）"""
    saved_at = token_data.get("saved_at", 0)
    expires_in = token_data.get("expires_in", 0)
    return time.time() > saved_at + expires_in - 60


def _refresh_token(service_name: str, token_data: dict) -> dict:
    """リフレッシュトークンで新しいアクセストークンを取得"""
    svc = SERVICES[service_name]
    print(f"[{service_name}] アクセストークンをリフレッシュ中...")
    resp = requests.post(svc["token_url"], data={
        "grant_type":    "refresh_token",
        "refresh_token": token_data["refresh_token"],
        "client_id":     svc["client_id"],
        "client_secret": svc["client_secret"],
    })
    resp.raise_for_status()
    new_token = resp.json()
    _save_token(service_name, new_token)
    print(f"[{service_name}] トークンリフレッシュ完了")
    return new_token


def _authorize_new(service_name: str) -> dict:
    """
    新規OAuth認証フロー（ブラウザを開いて認可コードを取得）
    MFのoob（Out-of-Band）リダイレクトURIに対応
    """
    svc = SERVICES[service_name]

    if not svc["client_id"] or not svc["client_secret"]:
        raise ValueError(
            f"[{service_name}] .envにMF_{service_name.upper()}_CLIENT_IDと"
            f"MF_{service_name.upper()}_CLIENT_SECRETを設定してください"
        )

    params = {
        "response_type": "code",
        "client_id":     svc["client_id"],
        "redirect_uri":  svc["redirect_uri"],
        "scope":         svc["scope"],
    }
    auth_url = svc["auth_url"] + "?" + urlencode(params)

    print(f"\n{'='*60}")
    print(f"[{service_name}] 認証が必要です")
    print(f"{'='*60}")
    print(f"ブラウザで以下のURLを開いてください:\n{auth_url}\n")
    webbrowser.open(auth_url)

    code = input("表示された認可コードを貼り付けてください: ").strip()

    resp = requests.post(svc["token_url"], data={
        "grant_type":    "authorization_code",
        "code":          code,
        "client_id":     svc["client_id"],
        "client_secret": svc["client_secret"],
        "redirect_uri":  svc["redirect_uri"],
    })
    resp.raise_for_status()
    token_data = resp.json()
    _save_token(service_name, token_data)
    print(f"[{service_name}] 認証完了、トークンを保存しました\n")
    return token_data


def get_access_token(service_name: str) -> str:
    """
    有効なアクセストークンを返す。
    保存済みトークンがあればそれを使い、期限切れならリフレッシュ、
    トークンがなければ新規認証フローを起動する。
    """
    token_data = _load_token(service_name)

    if token_data is None:
        token_data = _authorize_new(service_name)
    elif _is_expired(token_data):
        try:
            token_data = _refresh_token(service_name, token_data)
        except Exception as e:
            print(f"[{service_name}] リフレッシュ失敗 ({e})、再認証します")
            token_data = _authorize_new(service_name)

    return token_data["access_token"]
