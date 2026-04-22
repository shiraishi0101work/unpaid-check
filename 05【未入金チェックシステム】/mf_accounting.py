"""
MFクラウド会計APIクライアント
仕訳データ（入金取引）を取得する

API: https://accounting.moneyforward.com/api/v1
Scope: mfc/accounting/journal.read

MF会計の仕訳APIは fiscal_year (事業年度) + half_year (前期/後期) 単位で返す。
日付範囲での絞り込みは Python 側でフィルタする。
"""

import time
import requests
from auth import get_access_token

BASE_URL = "https://accounting.moneyforward.com/api/v1"

_REQUEST_INTERVAL = 1.5
_MAX_RETRIES = 5


def _headers(company_id: str = "") -> dict:
    token = get_access_token("accounting", company_id)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _request_with_retry(url: str, headers: dict, params: dict) -> requests.Response:
    for attempt in range(_MAX_RETRIES):
        resp = requests.get(url, headers=headers, params=params, timeout=30)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            print(f"[会計API] 429 Rate Limit → {wait}秒待機 ({attempt+1}/{_MAX_RETRIES})", flush=True)
            time.sleep(wait)
            continue
        return resp
    return resp


def _get_all_journal_pages(params: dict, company_id: str = "") -> list:
    """ページネーションを処理して全仕訳を取得"""
    results = []
    page = 1
    while True:
        params["page"] = page
        resp = _request_with_retry(
            f"{BASE_URL}/journals/search",
            headers=_headers(company_id),
            params=params,
        )
        print(f"[会計API] page={page} status={resp.status_code}", flush=True)
        if resp.status_code != 200:
            print(f"[会計API] エラー: {resp.text[:400]}", flush=True)
            resp.raise_for_status()

        data = resp.json()
        # レスポンス形式: {"journals": [...], "pagination": {...}}
        # または {"data": [...], "meta": {...}}
        items = data.get("journals") or data.get("data") or []
        if not items:
            break
        results.extend(items)

        pagination = data.get("pagination") or data.get("meta", {})
        total_pages = pagination.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1
        time.sleep(_REQUEST_INTERVAL)

    return results


def _to_deal_dict(j: dict) -> dict:
    """仕訳データを照合用フォーマットに変換"""
    # 日付フィールド（APIバージョンにより異なる）
    date_str = (
        j.get("journal_date")
        or j.get("recognized_at")
        or j.get("date")
        or ""
    )[:10]

    # 金額（借方金額を入金額として扱う）
    amount = abs(int(float(
        j.get("debit_amount")
        or j.get("amount")
        or j.get("total_price")
        or 0
    )))

    # 取引先名
    partner = j.get("partner_name") or j.get("partner", {}).get("name", "") or ""

    # 備考・摘要
    remark = j.get("description") or j.get("memo") or j.get("remark") or ""

    # 借方科目名
    account = (
        j.get("debit_account_name")
        or j.get("account_name")
        or j.get("debit_account", {}).get("name", "")
        or ""
    )

    return {
        "取引ID":   j.get("id", ""),
        "着金日":   date_str,
        "入金金額": amount,
        "取引先名": partner,
        "備考":     remark,
        "科目":     account,
        "_matched": False,
        "_raw":     j,
    }


def get_deals(from_date: str, to_date: str, company_id: str = "") -> list[dict]:
    """
    指定期間の仕訳一覧を取得して照合用フォーマットで返す。

    Args:
        from_date: 開始日 YYYY-MM-DD
        to_date:   終了日 YYYY-MM-DD
        company_id: 会社ID（マルチテナント用）

    Returns:
        照合用dictのリスト
    """
    print(f"[会計API] 仕訳取得: {from_date} 〜 {to_date}", flush=True)
    params = {
        "from_date": from_date,
        "to_date":   to_date,
        "per_page":  100,
    }
    items = _get_all_journal_pages(params, company_id=company_id)
    print(f"[会計API] 取得完了: {len(items)}件", flush=True)

    deals = [_to_deal_dict(j) for j in items]

    # 日付フィルタ（APIが対応していない場合のフォールバック）
    if from_date or to_date:
        filtered = []
        for d in deals:
            dt = d.get("着金日", "")
            if from_date and dt and dt < from_date:
                continue
            if to_date and dt and dt > to_date:
                continue
            filtered.append(d)
        deals = filtered

    return deals
