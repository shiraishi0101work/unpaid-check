"""
MFクラウド請求書APIクライアント
発行済み・未入金の請求書一覧を取得する
API docs: https://invoice.moneyforward.com/api/v3/docs
"""

import requests
from auth import get_access_token

BASE_URL = "https://invoice.moneyforward.com/api/v3"


def _headers() -> dict:
    token = get_access_token("invoice")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _get_all_pages(endpoint: str, params: dict) -> list:
    """ページネーションを自動処理して全件取得"""
    results = []
    page = 1
    while True:
        params["page"] = page
        resp = requests.get(f"{BASE_URL}{endpoint}", headers=_headers(), params=params)
        resp.raise_for_status()
        data = resp.json()

        # MF APIのレスポンス構造に合わせてデータを取り出す
        items = data.get("data", [])
        if not items:
            break

        results.extend(items)

        # 次ページの有無を確認
        meta = data.get("meta", {})
        total_pages = meta.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return results


def get_unpaid_billings() -> list[dict]:
    """
    発行済み・未入金の請求書を全件取得
    返却データ例:
    {
        "id": "XXXXXXXX",
        "billing_number": "請求番号",
        "title": "件名",
        "billing_date": "2026-03-01",
        "due_date": "2026-03-31",
        "payment_status": "unregistered",  # 未入金
        "billing_status": "issued",         # 発行済み
        "total_amount_with_tax": 110000,
        "partner": {
            "id": "...",
            "name": "株式会社〇〇"
        },
        "operator": {...},
        "memo": "",
        "tags": [],
        ...
    }
    """
    print("[請求書] 発行済み・未入金の請求書を取得中...")

    params = {
        "billing_status": "issued",          # 発行済み
        "payment_status": "unregistered",    # 未入金
        "per_page": 100,
    }

    billings = _get_all_pages("/billings", params)

    # 必要なフィールドだけに整形
    result = []
    for b in billings:
        partner = b.get("partner") or {}
        result.append({
            "請求書ID":     b.get("id", ""),
            "請求番号":     b.get("billing_number", ""),
            "件名":         b.get("title", ""),
            "取引先名":     partner.get("name", ""),
            "請求日":       b.get("billing_date", ""),
            "支払期限":     b.get("due_date", ""),
            "請求金額":     int(b.get("total_amount_with_tax", 0)),
            "入金状態":     b.get("payment_status", ""),
            "請求ステータス": b.get("billing_status", ""),
            "メモ":         b.get("memo", ""),
            # 照合用フィールド（後でmatcher.pyが使う）
            "_raw": b,
        })

    print(f"[請求書] {len(result)}件取得完了")
    return result
