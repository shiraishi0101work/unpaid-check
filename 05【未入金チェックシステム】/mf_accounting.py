"""
MFクラウド会計APIクライアント
仕訳データ（入金取引）を取得する

API仕様: https://api-accounting.moneyforward.com (CA PUBLIC REST API v3)
Scope: mfc/accounting/journal.read

エンドポイント: GET /api/v3/journals
パラメータ: start_date, end_date (YYYY-MM-DD)
"""

import time
import requests
from auth import get_access_token

BASE_URL = "https://api-accounting.moneyforward.com"

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


def _get_all_journal_pages(from_date: str, to_date: str, company_id: str = "",
                           is_realized: bool | None = None) -> list:
    """ページネーションを処理して全仕訳を取得"""
    results = []
    page = 1
    while True:
        params = {
            "start_date": from_date,
            "end_date":   to_date,
            "per_page":   10000,
            "page":       page,
        }
        if is_realized is not None:
            params["is_realized"] = str(is_realized).lower()
        resp = _request_with_retry(
            f"{BASE_URL}/api/v3/journals",
            headers=_headers(company_id),
            params=params,
        )
        print(f"[会計API] page={page} status={resp.status_code}", flush=True)
        if resp.status_code == 401:
            print(f"[会計API] 401レスポンス: {resp.text[:400]}", flush=True)
            raise RuntimeError(
                "MFクラウド会計の認証が切れています。設定画面から再連携してください。"
            )
        if resp.status_code != 200:
            print(f"[会計API] エラー: {resp.text[:400]}", flush=True)
            resp.raise_for_status()

        data = resp.json()
        items = data.get("journals") or []
        if not items:
            break
        results.extend(items)

        metadata = data.get("metadata", {})
        total_pages = metadata.get("total_pages", 1)
        if page >= total_pages:
            break
        page += 1
        time.sleep(_REQUEST_INTERVAL)

    return results


def _to_deal_dict(j: dict) -> list[dict]:
    """
    仕訳データを照合用フォーマットに変換する。
    1仕訳に複数のbranches（行）がある場合、各branchを1件として展開する。
    """
    date_str = (j.get("transaction_date") or "")[:10]
    journal_id = j.get("id", "")
    memo = j.get("memo", "") or ""

    results = []
    branches = j.get("branches") or []

    for i, branch in enumerate(branches):
        remark  = branch.get("remark", "") or ""
        debitor  = branch.get("debitor") or {}
        creditor = branch.get("creditor") or {}

        # 入金金額: 借方金額（debitor.value）
        amount = abs(int(float(debitor.get("value") or creditor.get("value") or 0)))

        # 取引先名: 借方 → 貸方の順で優先
        partner = (
            debitor.get("trade_partner_name")
            or creditor.get("trade_partner_name")
            or ""
        )

        # 借方科目名
        account = debitor.get("account_name") or creditor.get("account_name") or ""

        # 備考: branch.remark + journal.memo を結合
        full_remark = " ".join(filter(None, [remark, memo]))

        # 同一仕訳の複数行はIDにインデックスを付加
        deal_id = f"{journal_id}_{i}" if len(branches) > 1 else journal_id

        results.append({
            "取引ID":   deal_id,
            "着金日":   date_str,
            "入金金額": amount,
            "取引先名": partner,
            "備考":     full_remark,
            "科目":     account,
            "_matched": False,
            "_raw":     j,
        })

    return results


def get_unclassified_deals(from_date: str, to_date: str, company_id: str = "") -> list[dict]:
    """
    未仕分け（is_realized=false）の仕訳のみを取得して照合用フォーマットで返す。
    振込名義確認タブ用。
    """
    print(f"[会計API] 未仕分け仕訳取得: {from_date} 〜 {to_date}", flush=True)

    try:
        raw_journals = _get_all_journal_pages(from_date, to_date, company_id=company_id,
                                              is_realized=False)
    except RuntimeError:
        raise
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise RuntimeError(
                "MFクラウド会計の認証が切れています。設定画面から再連携してください。"
            ) from e
        raise

    print(f"[会計API] 未仕分け取得完了: {len(raw_journals)}件", flush=True)

    deals = []
    for j in raw_journals:
        deals.extend(_to_deal_dict(j))

    seen = set()
    deduped = []
    for d in deals:
        tid = d.get("取引ID", "")
        if tid and tid in seen:
            continue
        if tid:
            seen.add(tid)
        deduped.append(d)

    return deduped


def get_deals(from_date: str, to_date: str, company_id: str = "",
              fiscal_start_month: int = 4,
              is_realized: bool | None = None) -> list[dict]:
    """
    指定期間の仕訳一覧を取得して照合用フォーマットで返す。

    Args:
        from_date: 開始日 YYYY-MM-DD
        to_date:   終了日 YYYY-MM-DD
        company_id: 会社ID（マルチテナント用）
        fiscal_start_month: 未使用（互換性のため残す）

    Returns:
        照合用dictのリスト
    """
    print(f"[会計API] 仕訳取得: {from_date} 〜 {to_date}", flush=True)

    try:
        raw_journals = _get_all_journal_pages(from_date, to_date, company_id=company_id)
    except RuntimeError:
        raise
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            raise RuntimeError(
                "MFクラウド会計の認証が切れています。設定画面から再連携してください。"
            ) from e
        raise

    print(f"[会計API] 取得完了（合計）: {len(raw_journals)}件", flush=True)

    deals = []
    for j in raw_journals:
        deals.extend(_to_deal_dict(j))

    # 取引IDで重複除去
    seen = set()
    deduped = []
    for d in deals:
        tid = d.get("取引ID", "")
        if tid and tid in seen:
            continue
        if tid:
            seen.add(tid)
        deduped.append(d)

    return deduped
