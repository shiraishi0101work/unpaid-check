"""
MFクラウド会計APIクライアント
入金データ（収入取引）を取得する
API docs: https://accounting.moneyforward.com/api/v1/docs
"""

import requests
from auth import get_access_token

BASE_URL = "https://accounting.moneyforward.com/api/v1"


def _headers() -> dict:
    token = get_access_token("accounting")
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

        items = data.get("data", [])
        if not items:
            break

        results.extend(items)

        meta = data.get("meta", {})
        total_pages = meta.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return results


def get_income_deals(from_date: str = None, to_date: str = None) -> list[dict]:
    """
    収入取引（入金）データを全件取得
    from_date, to_date: "YYYY-MM-DD"形式

    返却データ例:
    {
        "id": "XXXXXXXX",
        "deal_date": "2026-03-25",   # 着金日
        "amount": 110000,             # 金額
        "due_amount": 0,              # 未払い残額（0なら完済）
        "type": "income",             # 収入
        "partner": {
            "name": "株式会社〇〇"
        },
        "details": [
            {
                "account_item_name": "売掛金",
                "amount": 110000,
                "description": "〇〇の件"
            }
        ],
        ...
    }
    """
    print("[会計] 入金データを取得中...")

    params = {
        "type": "income",   # 収入のみ
        "per_page": 100,
    }
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date

    deals = _get_all_pages("/deals", params)

    # 必要なフィールドだけに整形
    result = []
    for d in deals:
        partner = d.get("partner") or {}
        details = d.get("details") or []

        # 科目名を結合して備考として使う
        account_items = "、".join(
            detail.get("account_item_name", "")
            for detail in details
            if detail.get("account_item_name")
        )
        descriptions = "、".join(
            detail.get("description", "")
            for detail in details
            if detail.get("description")
        )

        result.append({
            "取引ID":   d.get("id", ""),
            "着金日":   d.get("deal_date", ""),
            "取引先名": partner.get("name", ""),
            "入金金額": int(d.get("amount", 0)),
            "残額":     int(d.get("due_amount", 0)),
            "科目":     account_items,
            "備考":     descriptions,
            # 照合用
            "_raw": d,
            "_matched": False,       # 照合済みフラグ（matcher.pyが更新）
        })

    print(f"[会計] {len(result)}件取得完了")
    return result
