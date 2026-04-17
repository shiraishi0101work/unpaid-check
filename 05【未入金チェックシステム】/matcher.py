"""
請求書と入金データの照合ロジック

照合は3パスで実施:
  パス1（完全照合）: 金額一致 + 取引先名一致 + 日付範囲 → 「完全入金」
  パス2（差額照合）: 取引先名一致 + 日付範囲のみ（金額不問） → 「差額あり」
    - 入金金額 < 請求金額 → 部分入金（残額を表示）
    - 入金金額 > 請求金額 → 過払い（差額を表示）
  パス3（金額一致）: 会計仕訳に取引先名が未設定の場合、金額 + 日付のみで照合 → 「完全入金（金額一致）」

  ※取引先名一致は部分一致。取引先名が空の仕訳は備考（摘要）テキストからも検索する。
"""

import os
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
import jaconv

load_dotenv()

AMOUNT_TOLERANCE  = int(os.getenv("MATCH_AMOUNT_TOLERANCE", 0))
DATE_BEFORE_DAYS  = int(os.getenv("MATCH_DATE_BEFORE_DAYS", 0))
DATE_AFTER_DAYS   = int(os.getenv("MATCH_DATE_AFTER_DAYS", 365))

# 法人格プレフィックス/サフィックスを除去する正規表現
_LEGAL_STRIP = re.compile(
    r"^(株式会社|有限会社|合同会社|一般社団法人|医療法人|社会福祉法人|税理士法人|特定非営利活動法人|NPO法人)\s*"
    r"|^(カ\)|カ）|ユ\)|ユ）|ゼイ\)|ゼイ）|シャ\)|シャ）)\s*"  # 振込略称プレフィックス
    r"|\s*(株式会社|有限会社|合同会社|株|（株）|\(株\))$"
)


def _normalize(text: str) -> str:
    """照合用に文字列を正規化する
    - 法人格プレフィックス/サフィックスを除去
    - ひらがな→カタカナ変換
    - 大文字化
    - 空白・記号を除去
    """
    t = text.strip()
    t = _LEGAL_STRIP.sub("", t).strip()
    t = jaconv.hira2kata(t)   # ひらがな → カタカナ
    t = t.upper()
    # 全角英数→半角
    t = jaconv.z2h(t, kana=False, ascii=True, digit=True)
    # 空白・ハイフン・ドットなど記号除去
    t = re.sub(r"[\s\-・\.、。　,\.()（）「」【】\[\]]", "", t)
    return t


def _parse_date(date_str: str) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def _name_match(invoice_name: str, deal_name: str, deal_remark: str = "") -> bool:
    """取引先名の一致判定
    1. 取引先名同士: 部分一致（正規化あり）
    2. 取引先名で不一致 or 空の場合: 備考テキストを正規化して検索
       ※ 銀行振込では取引先名が略称で不一致でも備考に正式名が含まれることがある
    """
    if not invoice_name:
        return False

    a_raw  = invoice_name.strip()
    a_norm = _normalize(a_raw)
    # 法人格なしのコア名称（部分一致用）
    a_core = _LEGAL_STRIP.sub("", a_raw).strip()
    # ひらがな→カタカナ変換済みコア（「いぶき」→「イブキ」）
    a_kata = jaconv.hira2kata(a_core)

    # ── ① 取引先名同士で照合 ──
    if deal_name and deal_name.strip():
        b_raw  = deal_name.strip()
        b_norm = _normalize(b_raw)
        if a_norm and b_norm:
            if a_norm in b_norm or b_norm in a_norm or a_norm == b_norm:
                return True
        else:
            if a_raw in b_raw or b_raw in a_raw:
                return True
        # 取引先名で一致しなかった場合も備考チェックへ続ける

    # ── ② 備考テキストで検索（取引先名が空 or 不一致の場合） ──
    if deal_remark:
        remark_norm = _normalize(deal_remark)
        # 正規化後の名前が備考に含まれるか（最低3文字以上で照合）
        if len(a_norm) >= 3 and a_norm in remark_norm:
            return True
        # カタカナ変換後のコア名称が備考（元テキスト）に含まれるか
        # 例: 「いぶき」→「イブキ」が「振込 ゼイ)イブキ」に含まれる
        if len(a_kata) >= 2 and a_kata in deal_remark:
            return True
        # 元のコア名称が備考に直接含まれるか
        if len(a_core) >= 2 and a_core in deal_remark:
            return True

    return False


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


def _build_paid_entry(billing: dict, deal: dict, status: str) -> dict:
    """照合済み請求書のデータを組み立てる"""
    diff = deal["入金金額"] - billing["請求金額"]  # 正 = 過払い、負 = 不足
    entry = dict(billing)
    entry["着金日"]    = deal["着金日"]
    entry["着金金額"]  = deal["入金金額"]
    entry["差額"]      = diff          # 0=完全一致、負=不足、正=過払い
    entry["会計取引ID"] = deal["取引ID"]
    entry["科目"]      = deal["科目"]
    entry["会計備考"]  = deal["備考"]
    entry["照合結果"]  = status
    return entry


def match(billings: list[dict], deals: list[dict]) -> dict:
    """
    請求書リストと入金データリストを照合する（2パス方式）

    Returns:
        {
            "paid":            [ {完全入金の請求書データ} ],
            "diff":            [ {差額ありの請求書データ} ],
            "unpaid":          [ {未入金の請求書データ} ],
            "unmatched_deals": [ {照合できなかった入金データ} ],
        }
    """
    print("[照合] 請求書と入金データを照合中...")

    paid_billings   = []
    diff_billings   = []
    unpaid_billings = []

    for deal in deals:
        deal["_matched"] = False

    # =========================================================
    # パス1: 金額 + 取引先名 + 日付 の完全照合
    # =========================================================
    remaining_billings = []

    for billing in billings:
        matched_deal = None
        for deal in deals:
            if deal["_matched"]:
                continue
            if not _amount_match(billing["請求金額"], deal["入金金額"]):
                continue
            if not _name_match(billing["取引先名"], deal["取引先名"], deal.get("備考", "")):
                continue
            if not _date_ok(billing["請求日"], deal["着金日"]):
                continue
            matched_deal = deal
            deal["_matched"] = True
            break

        if matched_deal:
            paid_billings.append(_build_paid_entry(billing, matched_deal, "完全入金"))
        else:
            remaining_billings.append(billing)

    # =========================================================
    # パス2: 取引先名 + 日付のみ（金額不問）で差額照合
    # =========================================================
    remaining_billings2 = []
    for billing in remaining_billings:
        matched_deal = None
        for deal in deals:
            if deal["_matched"]:
                continue
            if not _name_match(billing["取引先名"], deal["取引先名"], deal.get("備考", "")):
                continue
            if not _date_ok(billing["請求日"], deal["着金日"]):
                continue
            matched_deal = deal
            deal["_matched"] = True
            break

        if matched_deal:
            diff = matched_deal["入金金額"] - billing["請求金額"]
            if diff < 0:
                status = f"差額あり（不足 ¥{abs(diff):,}）"
            else:
                status = f"差額あり（過払い ¥{diff:,}）"
            diff_billings.append(_build_paid_entry(billing, matched_deal, status))
        else:
            remaining_billings2.append(billing)

    # =========================================================
    # パス3: 金額 + 日付のみ（取引先名が空の入金データを対象）
    # 取引先名が空かつ備考でも照合できなかった入金データとのマッチング
    # =========================================================
    unpaid_billings = []
    for billing in remaining_billings2:
        matched_deal = None
        for deal in deals:
            if deal["_matched"]:
                continue
            if deal.get("取引先名", "").strip():
                continue  # 取引先名がある入金は名前照合で弾かれたものなのでスキップ
            if not _amount_match(billing["請求金額"], deal["入金金額"]):
                continue
            if not _date_ok(billing["請求日"], deal["着金日"]):
                continue
            matched_deal = deal
            deal["_matched"] = True
            break

        if matched_deal:
            # 取引先名不明での金額一致
            paid_billings.append(_build_paid_entry(billing, matched_deal, "完全入金（金額一致）"))
        else:
            entry = dict(billing)
            entry["照合結果"] = "未入金"
            unpaid_billings.append(entry)

    # 照合できなかった入金データ
    unmatched_deals = [d for d in deals if not d["_matched"]]

    print(
        f"[照合] 完全入金: {len(paid_billings)}件  "
        f"差額あり: {len(diff_billings)}件  "
        f"未入金: {len(unpaid_billings)}件  "
        f"照合不能な入金: {len(unmatched_deals)}件"
    )

    return {
        "paid":            paid_billings,
        "diff":            diff_billings,
        "unpaid":          unpaid_billings,
        "unmatched_deals": unmatched_deals,
    }
