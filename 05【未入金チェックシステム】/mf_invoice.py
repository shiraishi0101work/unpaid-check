"""
MFクラウド請求書APIクライアント
発行済み・未入金の請求書一覧を取得する
API docs: https://invoice.moneyforward.com/docs/api/v3/index.html

payment_status の実際の値:
  "未設定"  → 入金登録なし（未入金扱い）
  "未入金"  → 明示的に未入金
  "入金済み" → 入金確認済み
"""

import time
import requests
from auth import get_access_token

BASE_URL = "https://invoice.moneyforward.com/api/v3"

# 未入金とみなす payment_status 値
UNPAID_STATUSES = {"未設定", "未入金"}
PAID_STATUSES   = {"入金済み"}


def _headers(company_id: str = "") -> dict:
    token = get_access_token("invoice", company_id)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


_REQUEST_INTERVAL = 1.5   # ページ間の待機秒数
_MAX_RETRIES      = 5     # 429 時の最大リトライ回数


def _request_with_retry(url: str, headers: dict, params: dict) -> requests.Response:
    """429 Too Many Requests を受けたら Retry-After を尊重してリトライする"""
    for attempt in range(_MAX_RETRIES):
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            print(f"[請求書API] 429 Rate Limit → {wait}秒待機してリトライ ({attempt+1}/{_MAX_RETRIES})", flush=True)
            time.sleep(wait)
            continue
        return resp
    return resp


def _get_all_pages(params: dict, company_id: str = "") -> list:
    """ページネーションを自動処理して全請求書を取得"""
    results = []
    page = 1
    while True:
        params["page"] = page
        resp = _request_with_retry(f"{BASE_URL}/billings", headers=_headers(company_id), params=params)
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

        # 連続リクエストによるレート制限を避けるためウェイト
        time.sleep(_REQUEST_INTERVAL)

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
        "請求書ID":    b.get("id", ""),
        "請求番号":    b.get("billing_number", ""),
        "件名":        b.get("title", ""),
        "取引先名":    b.get("partner_name") or partner.get("name", ""),
        "請求日":      _normalize_date(b.get("billing_date", "")),
        "支払期限":    _normalize_date(b.get("due_date", "")),
        "請求金額":    int(float(b.get("total_price", 0) or 0)),
        "入金状態":    b.get("payment_status", ""),
        "送付状態":    b.get("posting_status", ""),   # 未郵送/郵送中/郵送済み
        "メール状態":  b.get("email_status", ""),      # 未送信/送信済み 等
        "DL済み":      bool(b.get("is_downloaded", False)),
        "メモ":        b.get("memo", ""),
        "_raw":        b,
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
    # APIはYYYY/MM/DD形式で返すためnormalize後に比較する
    if from_date or to_date:
        filtered = []
        for b in billings_raw:
            bill_date = _normalize_date(b.get("billing_date", "") or b.get("due_date", ""))
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
