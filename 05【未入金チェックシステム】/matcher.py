"""
請求書と入金データの照合ロジック

照合ルール:
  1. 金額が一致（MATCH_AMOUNT_TOLERANCEの範囲内）
  2. 取引先名が一致（部分一致：請求書の取引先名が入金データの取引先名に含まれる、またはその逆）
  3. 着金日が請求日以降（MATCH_DATE_BEFORE_DAYSを考慮）

複数の入金が同一請求書に対応する可能性を考慮（分割払い等は未対応 → 金額一致優先）
"""

import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

AMOUNT_TOLERANCE  = int(os.getenv("MATCH_AMOUNT_TOLERANCE", 0))
DATE_BEFORE_DAYS  = int(os.getenv("MATCH_DATE_BEFORE_DAYS", 0))
DATE_AFTER_DAYS   = int(os.getenv("MATCH_DATE_AFTER_DAYS", 365))


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def _name_match(invoice_name: str, deal_name: str) -> bool:
    """取引先名の一致判定（部分一致）"""
    if not invoice_name or not deal_name:
        return False
    a = invoice_name.strip()
    b = deal_name.strip()
    return a in b or b in a or a == b


def _amount_match(invoice_amount: int, deal_amount: int) -> bool:
    """金額の一致判定（許容誤差範囲内）"""
    return abs(invoice_amount - deal_amount) <= AMOUNT_TOLERANCE


def _date_ok(billing_date_str: str, deal_date_str: str) -> bool:
    """着金日が請求日の妥当な範囲内かを確認"""
    billing_date = _parse_date(billing_date_str)
    deal_date    = _parse_date(deal_date_str)
    if billing_date is None or deal_date is None:
        return True  # 日付不明の場合は許容

    earliest = billing_date - timedelta(days=DATE_BEFORE_DAYS)
    latest   = billing_date + timedelta(days=DATE_AFTER_DAYS)
    return earliest <= deal_date <= latest


def match(billings: list[dict], deals: list[dict]) -> dict:
    """
    請求書リストと入金データリストを照合する

    Returns:
        {
            "paid":   [ {請求書データ + 着金日, 取引ID, ...} ],
            "unpaid": [ {請求書データ} ],
            "unmatched_deals": [ {照合できなかった入金データ} ],
        }
    """
    print("[照合] 請求書と入金データを照合中...")

    paid_billings    = []
    unpaid_billings  = []
    unmatched_deals  = []

    # 入金データの使用済みフラグをリセット
    for deal in deals:
        deal["_matched"] = False

    for billing in billings:
        invoice_amount = billing["請求金額"]
        invoice_name   = billing["取引先名"]
        billing_date   = billing["請求日"]

        matched_deal = None

        for deal in deals:
            if deal["_matched"]:
                continue  # 既に別の請求書に照合済み

            if not _amount_match(invoice_amount, deal["入金金額"]):
                continue
            if not _name_match(invoice_name, deal["取引先名"]):
                continue
            if not _date_ok(billing_date, deal["着金日"]):
                continue

            # 照合成功
            matched_deal = deal
            deal["_matched"] = True
            break

        if matched_deal:
            paid_billing = dict(billing)
            paid_billing["着金日"]  = matched_deal["着金日"]
            paid_billing["着金金額"] = matched_deal["入金金額"]
            paid_billing["会計取引ID"] = matched_deal["取引ID"]
            paid_billing["科目"]    = matched_deal["科目"]
            paid_billing["会計備考"] = matched_deal["備考"]
            paid_billing["照合結果"] = "入金確認済み"
            paid_billings.append(paid_billing)
        else:
            unpaid_billing = dict(billing)
            unpaid_billing["照合結果"] = "未入金"
            unpaid_billings.append(unpaid_billing)

    # 照合できなかった入金データ（請求書外の入金 or 取引先名・金額不一致）
    for deal in deals:
        if not deal["_matched"]:
            unmatched_deals.append(deal)

    print(f"[照合] 入金確認済み: {len(paid_billings)}件  未入金: {len(unpaid_billings)}件  照合不能な入金: {len(unmatched_deals)}件")

    return {
        "paid":            paid_billings,
        "unpaid":          unpaid_billings,
        "unmatched_deals": unmatched_deals,
    }
