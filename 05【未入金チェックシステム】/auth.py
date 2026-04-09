"""
OAuth 2.0認証モジュール
MFクラウド請求書・会計の両方に対応

2つのモードをサポート:
  - webモード: Flaskのコールバックエンドポイントで自動処理（app.py経由）
  - CLIモード: ブラウザを開き、ユーザーがコードを手動入力（後方互換）

トークンはtokens/に保存し、期限切れ時は自動リフレッシュ
"""

import os
import json
import time
import secrets
import base64
import webbrowser
import requests
from urllib.parse import urlencode
from dotenv import load_dotenv

# .envをこのファイルと同じディレクトリから確実に読み込む
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, ".env"), override=True)

PORT = int(os.getenv("PORT", 5000))

_SERVICE_DEFS = {
    "invoice": {
        "auth_url":   "https://invoice.moneyforward.com/oauth/authorize",
        "token_url":  "https://invoice.moneyforward.com/oauth/token",
        "scope":      "read",
        "env_id":     "MF_INVOICE_CLIENT_ID",
        "env_secret": "MF_INVOICE_CLIENT_SECRET",
        "env_uri":    "MF_INVOICE_REDIRECT_URI",
        "default_uri": f"http://localhost:{PORT}/oauth/callback/invoice",
        "token_file": "token_invoice.json",
    },
    "accounting": {
        "auth_url":   "https://accounting.moneyforward.com/oauth/authorize",
        "token_url":  "https://accounting.moneyforward.com/oauth/token",
        "scope":      "read",
        "env_id":     "MF_ACCOUNTING_CLIENT_ID",
        "env_secret": "MF_ACCOUNTING_CLIENT_SECRET",
        "env_uri":    "MF_ACCOUNTING_REDIRECT_URI",
        "default_uri": f"http://localhost:{PORT}/oauth/callback/accounting",
        "token_file": "token_accounting.json",
    },
}


def _svc(service_name: str) -> dict:
    """env変数を毎回動的に読んでサービス設定を返す"""
    d = _SERVICE_DEFS[service_name]
    return {
        "auth_url":      d["auth_url"],
        "token_url":     d["token_url"],
        "scope":         d["scope"],
        "client_id":     os.getenv(d["env_id"], ""),
        "client_secret": os.getenv(d["env_secret"], ""),
        "redirect_uri":  os.getenv(d["env_uri"], d["default_uri"]),
        "token_file":    d["token_file"],
    }

TOKEN_DIR = os.path.join(os.path.dirname(__file__), "tokens")

# OAuth stateパラメータを一時保存（CSRF対策）
_pending_states: dict[str, str] = {}  # state -> service_name


def _token_path(service_name: str) -> str:
    os.makedirs(TOKEN_DIR, exist_ok=True)
    return os.path.join(TOKEN_DIR, _SERVICE_DEFS[service_name]["token_file"])


def save_token(service_name: str, token_data: dict):
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
    saved_at   = token_data.get("saved_at", 0)
    expires_in = token_data.get("expires_in", 0)
    return time.time() > saved_at + expires_in - 60


def _basic_auth_header(client_id: str, client_secret: str) -> dict:
    """CLIENT_SECRET_BASIC用のAuthorizationヘッダーを生成"""
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


def _refresh(service_name: str, token_data: dict) -> dict:
    svc     = _svc(service_name)
    headers = _basic_auth_header(svc["client_id"], svc["client_secret"])
    resp    = requests.post(svc["token_url"], headers=headers, data={
        "grant_type":    "refresh_token",
        "refresh_token": token_data["refresh_token"],
    })
    resp.raise_for_status()
    new_token = resp.json()
    save_token(service_name, new_token)
    return new_token


# ========================================
# Webモード用: app.pyから呼び出す
# ========================================

def get_auth_url(service_name: str) -> str:
    """OAuthの認可URLを生成して返す（stateはセッション管理用に保持）"""
    svc   = _svc(service_name)
    state = secrets.token_urlsafe(16)
    _pending_states[state] = service_name

    params = {
        "response_type": "code",
        "client_id":     svc["client_id"],
        "redirect_uri":  svc["redirect_uri"],
        "scope":         svc["scope"],
        "state":         state,
    }
    return svc["auth_url"] + "?" + urlencode(params)


def handle_callback(service_name: str, code: str, state: str) -> bool:
    """
    OAuthコールバックを処理してトークンを保存する
    Returns: 成功したらTrue
    """
    if _pending_states.pop(state, None) != service_name:
        return False  # stateが一致しない（不正リクエスト）

    svc     = _svc(service_name)
    headers = _basic_auth_header(svc["client_id"], svc["client_secret"])
    resp    = requests.post(svc["token_url"], headers=headers, data={
        "grant_type":   "authorization_code",
        "code":          code,
        "redirect_uri":  svc["redirect_uri"],
    })
    resp.raise_for_status()
    save_token(service_name, resp.json())
    return True


def is_authenticated(service_name: str) -> bool:
    """トークンが存在し有効（またはリフレッシュ可能）かを確認"""
    token_data = _load_token(service_name)
    if token_data is None:
        return False
    if _is_expired(token_data):
        try:
            _refresh(service_name, token_data)
        except Exception:
            return False
    return True


def revoke_token(service_name: str):
    """トークンファイルを削除（ログアウト）"""
    path = _token_path(service_name)
    if os.path.exists(path):
        os.remove(path)


# ========================================
# 共通: APIクライアントから呼び出す
# ========================================

def get_access_token(service_name: str) -> str:
    """
    有効なアクセストークンを返す。
    Webアプリ内では事前にis_authenticated()で確認してから呼ぶこと。
    """
    token_data = _load_token(service_name)
    if token_data is None:
        raise RuntimeError(f"{service_name} が未認証です。先にOAuth認証を行ってください。")
    if _is_expired(token_data):
        token_data = _refresh(service_name, token_data)
    return token_data["access_token"]
