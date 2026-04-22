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
from datetime import date
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
            f"{BASE_URL}/journals",
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


def _date_to_fiscal_half(d: date, fiscal_start_month: int = 4) -> tuple[int, int]:
    """
    日付から (fiscal_year, half_year) を返す。
    fiscal_start_month=4 の場合:
      前期 (half_year=1): 4月〜9月
      後期 (half_year=2): 10月〜3月
    """
    m = d.month
    y = d.year
    # 年度開始月を基準にずらして計算
    offset_month = (m - fiscal_start_month) % 12
    if m >= fiscal_start_month:
        fy = y
    else:
        fy = y - 1
    half = 1 if offset_month < 6 else 2
    return fy, half


def _fiscal_halves_in_range(from_date: str, to_date: str, fiscal_start_month: int = 4) -> list[tuple[int, int]]:
    """
    日付範囲に含まれる (fiscal_year, half_year) のペアリストを返す（重複なし）。
    """
    d_from = date.fromisoformat(from_date)
    d_to   = date.fromisoformat(to_date)
    halves = set()
    # 月単位で走査（最大24ヶ月）
    y, m = d_from.year, d_from.month
    for _ in range(25):
        cur = date(y, m, 1)
        if cur > d_to:
            break
        halves.add(_date_to_fiscal_half(cur, fiscal_start_month))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return sorted(halves)


def get_deals(from_date: str, to_date: str, company_id: str = "",
              fiscal_start_month: int = 4) -> list[dict]:
    """
    指定期間の仕訳一覧を取得して照合用フォーマットで返す。
    MF会計APIは fiscal_year + half_year 単位なので、
    日付範囲に含まれる半期分を順に取得して結合する。

    Args:
        from_date: 開始日 YYYY-MM-DD
        to_date:   終了日 YYYY-MM-DD
        company_id: 会社ID（マルチテナント用）
        fiscal_start_month: 事業年度開始月（デフォルト4月）

    Returns:
        照合用dictのリスト（日付フィルタ済み）
    """
    print(f"[会計API] 仕訳取得: {from_date} 〜 {to_date}", flush=True)

    halves = _fiscal_halves_in_range(from_date, to_date, fiscal_start_month)
    print(f"[会計API] 対象半期: {halves}", flush=True)

    all_items = []
    for fy, hy in halves:
        params = {
            "fiscal_year": fy,
            "half_year":   hy,
            "per_page":    100,
        }
        print(f"[会計API] fiscal_year={fy} half_year={hy}", flush=True)
        try:
            items = _get_all_journal_pages(params, company_id=company_id)
            all_items.extend(items)
            print(f"[会計API] {fy}年度第{hy}期: {len(items)}件", flush=True)
        except Exception as e:
            print(f"[会計API] {fy}年度第{hy}期 取得失敗: {e}", flush=True)
        time.sleep(_REQUEST_INTERVAL)

    print(f"[会計API] 取得完了（合計）: {len(all_items)}件", flush=True)

    deals = [_to_deal_dict(j) for j in all_items]

    # 日付フィルタ
    filtered = []
    for d in deals:
        dt = d.get("着金日", "")
        if from_date and dt and dt < from_date:
            continue
        if to_date and dt and dt > to_date:
            continue
        filtered.append(d)

    # 取引IDで重複除去
    seen = set()
    deduped = []
    for d in filtered:
        tid = d.get("取引ID", "")
        if tid and tid in seen:
            continue
        if tid:
            seen.add(tid)
        deduped.append(d)

    return deduped
