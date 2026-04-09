"""
MFクラウド会計APIクライアント
入金データ（収入仕訳）を取得する
API docs: https://accounting.moneyforward.com/api/v1
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

        # レスポンス構造はエンドポイントによって異なる
        if isinstance(data, list):
            items = data
        else:
            # {"data": [...], "meta": {...}} 形式
            items = data.get("data", [])

        if not items:
            break

        results.extend(items)

        if isinstance(data, list):
            # リスト形式の場合はページネーションなし
            break

        meta = data.get("meta", {})
        total_pages = meta.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1

    return results


def get_income_deals(from_date: str = None, to_date: str = None) -> list[dict]:
    """
    収入仕訳（入金）データを全件取得
    from_date, to_date: "YYYY-MM-DD"形式

    MF Cloud Accounting API v1 の /journals エンドポイントを使用
    収入系の仕訳（売掛金回収・売上計上など）を取得する
    """
    print("[会計] 入金データを取得中...")

    params = {
        "per_page": 100,
    }
    if from_date:
        params["from_date"] = from_date
    if to_date:
        params["to_date"] = to_date

    # まず /journals エンドポイントを試す
    try:
        journals = _get_all_pages("/journals", params)
        print(f"[会計] 仕訳データ {len(journals)}件取得完了")

        result = []
        for j in journals:
            # 仕訳の構造を解析して収入系のエントリを抽出
            entry_side = j.get("debit_or_credit", "")  # "debit" or "credit"
            account_item_name = j.get("account_item_name", "")

            # 収入判定: 売掛金の借方（回収）、または売上の貸方
            is_income = (
                ("売掛金" in account_item_name and entry_side == "debit")
                or ("売上" in account_item_name and entry_side == "credit")
                or ("売上高" in account_item_name and entry_side == "credit")
                or ("普通預金" in account_item_name and entry_side == "debit")
                or ("現金" in account_item_name and entry_side == "debit")
            )

            result.append({
                "取引ID":   j.get("id", ""),
                "着金日":   j.get("date", j.get("deal_date", "")),
                "取引先名": j.get("partner_name", ""),
                "入金金額": int(j.get("amount", 0)),
                "残額":     0,
                "科目":     account_item_name,
                "備考":     j.get("description", ""),
                "_is_income": is_income,
                "_raw": j,
                "_matched": False,
            })

        # 収入系のみフィルタ（もし判定できる場合）
        income_result = [r for r in result if r["_is_income"]]
        if income_result:
            print(f"[会計] うち収入系: {len(income_result)}件")
            return income_result
        else:
            # 判定できなかった場合は全件返す
            print("[会計] 収入フィルタなし: 全仕訳を返します")
            return result

    except Exception as e:
        print(f"[会計] /journals エラー: {e}")
        raise
