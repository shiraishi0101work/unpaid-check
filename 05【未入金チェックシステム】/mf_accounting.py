"""
MFクラウド会計APIクライアント (v3)
入金データ（売掛金回収仕訳）を取得する

API: https://api-accounting.moneyforward.com
仕訳一覧 GET /api/v3/journals
  - start_date / end_date で期間指定
  - per_page 最大 10000
  - レスポンス: { journals: [...], metadata: { total_count, total_pages } }

各 journal の branches[] に creditor（貸方）/ debitor（借方）が入っている。
入金 = 借方が「普通預金・現金」かつ 貸方が「売掛金」の仕訳を対象とする。
"""

import requests
from auth import get_access_token

BASE_URL = "https://api-accounting.moneyforward.com"

# 入金と判定する勘定科目キーワード
_CASH_ACCOUNTS   = ("普通預金", "当座預金", "現金")   # 借方（お金が入ってくる口座）
_RECEIVABLE_ACCS = ("売掛金",)                        # 貸方（売掛金が消える）


def _headers() -> dict:
    token = get_access_token("accounting")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }


def _get_office_id() -> str | None:
    """MFクラウド会計の事業所IDを取得する"""
    try:
        resp = requests.get(
            f"{BASE_URL}/api/v3/offices",
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        offices = data.get("offices", [])
        if offices:
            oid = offices[0].get("id", "")
            print(f"[会計API] office_id={oid}")
            return oid
    except Exception as e:
        print(f"[会計API] office_id取得失敗: {e}")
    return None


def _get_all_pages(params: dict) -> list:
    """仕訳一覧を全ページ取得して返す"""
    results = []
    page = 1
    prev_count = None
    while True:
        params["page"] = page
        resp = requests.get(
            f"{BASE_URL}/api/v3/journals",
            headers=_headers(),
            params=params,
        )
        if resp.status_code == 400:
            if page > 1:
                print(f"[会計API] page={page} 400→ページ終端と判定して終了")
                break
            else:
                print(f"[会計API] エラー {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
        if not resp.ok:
            print(f"[会計API] エラー {resp.status_code}: {resp.text[:500]}")
            resp.raise_for_status()

        data = resp.json()
        journals = data.get("journals", [])
        if not journals:
            break

        results.extend(journals)
        print(f"[会計API] page={page} {len(journals)}件取得 (累計{len(results)}件)")

        meta = data.get("metadata", {})
        total_pages = meta.get("total_pages", 1)
        if page >= total_pages:
            break
        if prev_count is not None and len(journals) < prev_count:
            break
        prev_count = len(journals)
        page += 1

    return results


def _is_cash(account_name: str) -> bool:
    return any(k in account_name for k in _CASH_ACCOUNTS)


def _is_receivable(account_name: str) -> bool:
    return any(k in account_name for k in _RECEIVABLE_ACCS)


def get_income_deals(from_date: str = None, to_date: str = None) -> list[dict]:
    """
    入金仕訳（売掛金回収）を全件取得して返す。
    日付フィルタはAPI非対応のため Python 側で実施。

    戻り値の各要素:
        着金日         : str  "YYYY-MM-DD"
        取引先名       : str
        入金金額       : int
        科目（借方）   : str  "普通預金" など
        科目（貸方）   : str  "売掛金" など
        備考           : str
        仕訳ID         : str
        _matched       : bool  照合済みフラグ（matcher.py が使用）
    """
    print("[会計] 入金データを取得中 (API v3)...")

    from datetime import date as _date
    today = _date.today().strftime("%Y-%m-%d")

    params: dict = {"per_page": 100}
    # APIは end_date のみ有効（start_date は非対応）。未来日付は拒否されるため today で上限
    params["end_date"] = min(to_date, today) if to_date else today

    journals = _get_all_pages(params)
    print(f"[会計] 仕訳 {len(journals)}件 取得完了")

    result = []
    for j in journals:
        txn_date = j.get("transaction_date", "")
        memo     = j.get("memo", "")
        jid      = j.get("id", "")

        for branch in j.get("branches", []):
            creditor = branch.get("creditor") or {}
            debitor  = branch.get("debitor")  or {}

            cr_account = creditor.get("account_name", "")
            db_account = debitor.get("account_name",  "")

            # 入金パターン: 借方=普通預金/現金 かつ 貸方=売掛金
            if not (_is_cash(db_account) and _is_receivable(cr_account)):
                continue

            # 取引先名は貸方（売掛金側）を優先、なければ借方
            partner = (
                creditor.get("trade_partner_name")
                or debitor.get("trade_partner_name")
                or ""
            )
            amount = int(creditor.get("value", 0))
            remark = branch.get("remark", "") or memo

            result.append({
                "取引ID":   jid,
                "着金日":   txn_date,
                "取引先名": partner,
                "入金金額": amount,
                "科目":     db_account,   # 借方科目（普通預金など）
                "備考":     remark,
                "_matched": False,
            })

    # Python 側で日付フィルタ
    if from_date or to_date:
        filtered = []
        for r in result:
            d = r.get("着金日", "")
            if from_date and d and d < from_date:
                continue
            if to_date and d and d > to_date:
                continue
            filtered.append(r)
        result = filtered

    print(f"[会計] 入金仕訳 {len(result)}件 抽出完了")
    return result
