"""
MFクラウド請求書APIクライアント
発行済み・未入金の請求書一覧を取得する
API docs: https://invoice.moneyforward.com/docs/api/v3/index.html

payment_status の実際の値:
  "未設定"  → 入金登録なし（未入金扱い）
  "未入金"  → 明示的に未入金
  "入金済み" → 入金確認済み
"""

import requests
from auth import get_access_token

BASE_URL = "https://invoice.moneyforward.com/api/v3"

# 未入金とみなす payment_status 値
UNPAID_STATUSES = {"未設定", "未入金"}
PAID_STATUSES   = {"入金済み"}


def _headers() -> dict:
    token = get_access_token("invoice")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _get_all_pages(params: dict) -> list:
    """ページネーションを自動処理して全請求書を取得"""
    import sys
    results = []
    page = 1
    while True:
        params["page"] = page
        resp = requests.get(f"{BASE_URL}/billings", headers=_headers(), params=params)
        print(f"[請求書API] page={page} status={resp.status_code}", flush=True)
        if resp.status_code != 200:
            print(f"[請求書API] エラーレスポンス: {resp.text[:300]}", flush=True)
            resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        print(f"[請求書API] page={page} items={len(items)} keys={list(data.keys())}", flush=True)
        if not items:
            print(f"[請求書API] data空のためbreak。pagination={data.get('pagination')}", flush=True)
            break
        results.extend(items)

        pagination = data.get("pagination", {})
        total_pages = pagination.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return results


def _normalize_date(date_str: str) -> str:
    """YYYY/MM/DD → YYYY-MM-DD に統一（既にハイフンなら何もしない）"""
    if date_str:
        return date_str.replace("/", "-")
    return date_str or ""


def _to_billing_dict(b: dict) -> dict:
    """請求書データを整形"""
    partner = b.get("partner") or {}
    return {
        "請求書ID":  b.get("id", ""),
        "請求番号":  b.get("billing_number", ""),
        "件名":      b.get("title", ""),
        "取引先名":  b.get("partner_name") or partner.get("name", ""),
        "請求日":    _normalize_date(b.get("billing_date", "")),
        "支払期限":  _normalize_date(b.get("due_date", "")),
        "請求金額":  int(float(b.get("total_price", 0) or 0)),
        "入金状態":  b.get("payment_status", ""),
        "メモ":      b.get("memo", ""),
        "_raw":      b,
    }


def get_all_billings(from_date: str = None, to_date: str = None) -> list[dict]:
    """
    全請求書を取得してPython側でフィルタリング
    MF Invoice API v3 は billing_status / payment_status フィルタ不可のため全件取得
    """
    print("[請求書] 全請求書を取得中...")

    params = {"per_page": 100}
    billings_raw = _get_all_pages(params)
    print(f"[請求書] API取得: {len(billings_raw)}件")

    # 日付範囲フィルタ（Python側）
    if from_date or to_date:
        filtered = []
        for b in billings_raw:
            bill_date = b.get("billing_date", "") or b.get("due_date", "")
            if from_date and bill_date and bill_date < from_date:
                continue
            if to_date and bill_date and bill_date > to_date:
                continue
            filtered.append(b)
        billings_raw = filtered
        print(f"[請求書] 日付フィルタ後: {len(billings_raw)}件")

    return [_to_billing_dict(b) for b in billings_raw]


def get_unpaid_billings(from_date: str = None, to_date: str = None) -> list[dict]:
    """未入金の請求書のみ返す（payment_status が 未設定 or 未入金）"""
    all_billings = get_all_billings(from_date, to_date)
    unpaid = [b for b in all_billings if b["入金状態"] in UNPAID_STATUSES]
    print(f"[請求書] 未入金: {len(unpaid)}件")
    return unpaid


def get_paid_billings(from_date: str = None, to_date: str = None) -> list[dict]:
    """入金済みの請求書のみ返す"""
    all_billings = get_all_billings(from_date, to_date)
    paid = [b for b in all_billings if b["入金状態"] in PAID_STATUSES]
    print(f"[請求書] 入金済み: {len(paid)}件")
    return paid
