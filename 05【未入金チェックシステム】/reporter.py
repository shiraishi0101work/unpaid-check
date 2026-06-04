"""
Excelレポート生成モジュール

シート構成:
  1. サマリー           — 合計金額・件数
  2. 支払期限超過請求書  — 支払期限を過ぎた未入金請求書
  3. 期日前請求書        — 支払期限内の未入金請求書
  4. 入金確認済み        — MF入金済み or 手動確認済みの請求書
"""

import os
from datetime import datetime
import openpyxl
from openpyxl.styles import (
    PatternFill, Font, Alignment, Border, Side
)
from openpyxl.utils import get_column_letter


# ========================================
# カラー定義
# ========================================
COLOR_HEADER_OVERDUE  = "C00000"  # 深紅（支払期限超過ヘッダー）
COLOR_HEADER_SEIKYU   = "0070C0"  # 青（請求済み・未確認ヘッダー）
COLOR_HEADER_UPCOMING = "833C00"  # 深オレンジ（期日前ヘッダー）
COLOR_HEADER_DIFF     = "7030A0"  # 紫（差額ありヘッダー）
COLOR_HEADER_ICHIJI   = "4B0082"  # 紫（一時保管ヘッダー）
COLOR_ROW_ICHIJI      = "F3EEFF"  # 薄紫（一時保管）
COLOR_HEADER_PAID     = "375623"  # 深緑（入金済みヘッダー）
COLOR_HEADER_UNMATCHED= "7F6000"  # 深黄（照合不能ヘッダー）
COLOR_HEADER_SUMMARY  = "1F3864"  # 紺（サマリーヘッダー）
COLOR_WHITE           = "FFFFFF"
COLOR_ROW_OVERDUE     = "FCE4D6"  # 薄いオレンジ（超過）
COLOR_ROW_SEIKYU      = "DEEAF1"  # 薄い青（請求済み・未確認）
COLOR_ROW_UPCOMING    = "FFF2CC"  # 薄い黄色（期日前）
COLOR_ROW_DIFF        = "E2CFED"  # 薄い紫（差額あり）
COLOR_ROW_PAID        = "E2EFDA"  # 薄い緑
COLOR_ROW_UNMATCHED   = "FFF2CC"  # 薄い黄色
COLOR_OVERDUE         = "FF0000"  # 支払期限超過テキスト
COLOR_SHORTAGE        = "C00000"  # 不足テキスト（赤）
COLOR_OVERPAY         = "7030A0"  # 過払いテキスト（紫）


def _thin_border():
    thin = Side(style="thin")
    return Border(left=thin, right=thin, top=thin, bottom=thin)


def _header_cell(ws, row, col, value, bg_color, font_color=COLOR_WHITE, bold=True):
    cell = ws.cell(row=row, column=col, value=value)
    cell.fill = PatternFill("solid", fgColor=bg_color)
    cell.font = Font(bold=bold, color=font_color)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border = _thin_border()
    return cell


def _data_cell(ws, row, col, value, bg_color=None, number_format=None,
               bold=False, font_color="000000", center=False):
    cell = ws.cell(row=row, column=col, value=value)
    if bg_color:
        cell.fill = PatternFill("solid", fgColor=bg_color)
    if number_format:
        cell.number_format = number_format
    cell.font = Font(bold=bold, color=font_color)
    cell.alignment = Alignment(
        horizontal="center" if center else "left",
        vertical="center",
        wrap_text=False
    )
    cell.border = _thin_border()
    return cell


def _auto_column_width(ws, padding=4):
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            try:
                val = str(cell.value) if cell.value is not None else ""
                # 日本語文字は2文字分の幅
                display_len = sum(2 if ord(c) > 127 else 1 for c in val)
                if display_len > max_len:
                    max_len = display_len
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + padding, 50)


def _write_unpaid_billings(ws, billings: list[dict], title: str,
                           tab_color: str, header_color: str, row_color: str,
                           show_overdue_days: bool = False):
    """未入金請求書シートの共通描画関数"""
    ws.title = title
    ws.sheet_properties.tabColor = tab_color
    today_str = datetime.now().strftime("%Y-%m-%d")

    cols = ["請求番号", "取引先名", "件名", "請求日", "支払期限", "請求金額", "メモ"]
    if show_overdue_days:
        cols.append("超過日数")
    for c, name in enumerate(cols, start=1):
        _header_cell(ws, 1, c, name, header_color)

    ws.row_dimensions[1].height = 25

    for r, billing in enumerate(billings, start=2):
        due_date = billing.get("支払期限", "")
        bg = row_color

        _data_cell(ws, r, 1, billing.get("請求番号", ""), bg, center=True)
        _data_cell(ws, r, 2, billing.get("取引先名", ""), bg)
        _data_cell(ws, r, 3, billing.get("件名", ""),     bg)
        _data_cell(ws, r, 4, billing.get("請求日", ""),   bg, center=True)
        _data_cell(ws, r, 5, due_date,                    bg, center=True)
        _data_cell(ws, r, 6, billing.get("請求金額", 0),  bg,
                   number_format='#,##0', center=True)
        _data_cell(ws, r, 7, billing.get("メモ", ""),     bg)

        if show_overdue_days and due_date:
            try:
                delta = (datetime.strptime(today_str, "%Y-%m-%d")
                         - datetime.strptime(due_date, "%Y-%m-%d")).days
                cell = _data_cell(ws, r, 8, delta, bg,
                                  number_format='#,##0', center=True)
                cell.font = Font(color=COLOR_OVERDUE, bold=True)
            except ValueError:
                _data_cell(ws, r, 8, "", bg)

    _auto_column_width(ws)


def _write_overdue_sheet(ws, overdue: list[dict]):
    """支払期限超過請求書シート（取引先名順→期限切れ順に並べる）"""
    sorted_billings = sorted(overdue, key=lambda x: (x.get("取引先名", ""), x.get("支払期限", "")))
    _write_unpaid_billings(
        ws, sorted_billings,
        title="未収",
        tab_color="C00000",
        header_color=COLOR_HEADER_OVERDUE,
        row_color=COLOR_ROW_OVERDUE,
        show_overdue_days=True,
    )


def _write_seikyu_kakunin_sheet(ws, billings: list[dict]):
    """請求済み・未確認シート（送付済みだがMF未入金ステータスが未設定のもの）"""
    ws.title = "請求済みか確認"
    ws.sheet_properties.tabColor = "0070C0"
    today_str = datetime.now().strftime("%Y-%m-%d")

    cols = ["請求番号", "取引先名", "件名", "請求日", "支払期限", "請求金額",
            "送付方法", "超過日数", "メモ"]
    for c, name in enumerate(cols, start=1):
        _header_cell(ws, 1, c, name, COLOR_HEADER_SEIKYU)

    ws.row_dimensions[1].height = 25

    sorted_billings = sorted(billings, key=lambda x: x.get("支払期限", ""))
    for r, billing in enumerate(sorted_billings, start=2):
        due_date = billing.get("支払期限", "")
        bg = COLOR_ROW_SEIKYU

        # 送付方法を整理
        methods = []
        if billing.get("DL済み"):
            methods.append("DL")
        if billing.get("メール状態") and billing.get("メール状態") != "未送信":
            methods.append("メール")
        if billing.get("送付状態") and billing.get("送付状態") != "未郵送":
            methods.append("郵送")
        method_str = " / ".join(methods) if methods else "—"

        _data_cell(ws, r, 1, billing.get("請求番号", ""), bg, center=True)
        _data_cell(ws, r, 2, billing.get("取引先名", ""), bg)
        _data_cell(ws, r, 3, billing.get("件名", ""),     bg)
        _data_cell(ws, r, 4, billing.get("請求日", ""),   bg, center=True)
        _data_cell(ws, r, 5, due_date,                    bg, center=True)
        _data_cell(ws, r, 6, billing.get("請求金額", 0),  bg,
                   number_format='#,##0', center=True)
        _data_cell(ws, r, 7, method_str,                  bg, center=True)

        if due_date:
            try:
                delta = (datetime.strptime(today_str, "%Y-%m-%d")
                         - datetime.strptime(due_date, "%Y-%m-%d")).days
                cell = _data_cell(ws, r, 8, delta, bg,
                                  number_format='#,##0', center=True)
                cell.font = Font(color=COLOR_OVERDUE, bold=True)
            except ValueError:
                _data_cell(ws, r, 8, "", bg)
        else:
            _data_cell(ws, r, 8, "", bg)

        _data_cell(ws, r, 9, billing.get("メモ", ""), bg)

    _auto_column_width(ws)


def _write_upcoming_sheet(ws, upcoming: list[dict]):
    """期日前請求書シート（支払期限が近い順に並べる）"""
    sorted_billings = sorted(upcoming, key=lambda x: x.get("支払期限", ""))
    _write_unpaid_billings(
        ws, sorted_billings,
        title="期日前請求書",
        tab_color="833C00",
        header_color=COLOR_HEADER_UPCOMING,
        row_color=COLOR_ROW_UPCOMING,
        show_overdue_days=False,
    )


def _write_diff_sheet(ws, diff_billings: list[dict]):
    """差額あり請求書シート（請求金額と入金金額が異なるもの）"""
    ws.title = "差額あり請求書"
    ws.sheet_properties.tabColor = "7030A0"

    cols = ["請求番号", "取引先名", "件名", "請求日", "支払期限",
            "請求金額", "着金日", "着金金額", "差額", "照合結果", "科目", "会計備考"]
    for c, name in enumerate(cols, start=1):
        _header_cell(ws, 1, c, name, COLOR_HEADER_DIFF)

    ws.row_dimensions[1].height = 25

    for r, billing in enumerate(diff_billings, start=2):
        bg   = COLOR_ROW_DIFF
        diff = billing.get("差額", 0)

        _data_cell(ws, r, 1,  billing.get("請求番号", ""), bg, center=True)
        _data_cell(ws, r, 2,  billing.get("取引先名", ""), bg)
        _data_cell(ws, r, 3,  billing.get("件名", ""),     bg)
        _data_cell(ws, r, 4,  billing.get("請求日", ""),   bg, center=True)
        _data_cell(ws, r, 5,  billing.get("支払期限", ""), bg, center=True)
        _data_cell(ws, r, 6,  billing.get("請求金額", 0),  bg, number_format='#,##0', center=True)
        _data_cell(ws, r, 7,  billing.get("着金日", ""),   bg, center=True)
        _data_cell(ws, r, 8,  billing.get("着金金額", 0),  bg, number_format='#,##0', center=True)

        # 差額セル: 不足は赤、過払いは紫で強調
        diff_color = COLOR_SHORTAGE if diff < 0 else COLOR_OVERPAY
        diff_cell = _data_cell(ws, r, 9, diff, bg, number_format='+#,##0;-#,##0;0', center=True)
        diff_cell.font = Font(bold=True, color=diff_color)

        _data_cell(ws, r, 10, billing.get("照合結果", ""), bg)
        _data_cell(ws, r, 11, billing.get("科目", ""),     bg)
        _data_cell(ws, r, 12, billing.get("会計備考", ""), bg)

    _auto_column_width(ws)


def _write_ichiji_hokan_sheet(ws, billings: list[dict]):
    """一時保管（毎月要確認）シート"""
    ws.title = "一時保管（毎月要確認）"
    ws.sheet_properties.tabColor = "6f42c1"
    today_str = datetime.now().strftime("%Y-%m-%d")

    cols = ["請求番号", "取引先名", "件名", "担当者", "請求日", "支払期限",
            "請求金額", "超過日数", "理由（社内メモ）"]
    for c, name in enumerate(cols, start=1):
        _header_cell(ws, 1, c, name, COLOR_HEADER_ICHIJI)

    ws.row_dimensions[1].height = 25

    sorted_billings = sorted(billings, key=lambda x: x.get("支払期限", ""))
    for r, b in enumerate(sorted_billings, start=2):
        due_date = b.get("支払期限", "")
        bg = COLOR_ROW_ICHIJI

        _data_cell(ws, r, 1, b.get("請求番号", ""), bg, center=True)
        _data_cell(ws, r, 2, b.get("取引先名", ""), bg)
        _data_cell(ws, r, 3, b.get("件名", ""),     bg)
        _data_cell(ws, r, 4, b.get("担当者", ""),   bg, center=True)
        _data_cell(ws, r, 5, b.get("請求日", ""),   bg, center=True)
        _data_cell(ws, r, 6, due_date,               bg, center=True)
        _data_cell(ws, r, 7, b.get("請求金額", 0),  bg, number_format='#,##0', center=True)

        if due_date:
            try:
                delta = (datetime.strptime(today_str, "%Y-%m-%d")
                         - datetime.strptime(due_date, "%Y-%m-%d")).days
                cell = _data_cell(ws, r, 8, delta, bg, number_format='#,##0', center=True)
                cell.font = Font(color=COLOR_OVERDUE, bold=True)
            except ValueError:
                _data_cell(ws, r, 8, "", bg)
        else:
            _data_cell(ws, r, 8, "", bg)

        _data_cell(ws, r, 9, b.get("メモ_手動", ""), bg)

    _auto_column_width(ws)


def _write_paid_sheet(ws, paid: list[dict]):
    ws.title = "入金確認済み"
    ws.sheet_properties.tabColor = "375623"

    cols = ["請求番号", "取引先名", "件名", "請求日", "支払期限", "請求金額", "入金状態"]
    for c, name in enumerate(cols, start=1):
        _header_cell(ws, 1, c, name, COLOR_HEADER_PAID)

    ws.row_dimensions[1].height = 25

    for r, billing in enumerate(paid, start=2):
        bg = COLOR_ROW_PAID
        _data_cell(ws, r, 1, billing.get("請求番号", ""),  bg, center=True)
        _data_cell(ws, r, 2, billing.get("取引先名", ""),  bg)
        _data_cell(ws, r, 3, billing.get("件名", ""),      bg)
        _data_cell(ws, r, 4, billing.get("請求日", ""),    bg, center=True)
        _data_cell(ws, r, 5, billing.get("支払期限", ""),  bg, center=True)
        _data_cell(ws, r, 6, billing.get("請求金額", 0),   bg, number_format='#,##0', center=True)
        _data_cell(ws, r, 7, billing.get("入金状態", ""),  bg, center=True)

    _auto_column_width(ws)


def _write_unmatched_sheet(ws, unmatched: list[dict]):
    ws.title = "照合不能入金"
    ws.sheet_properties.tabColor = "7F6000"

    cols = ["取引ID", "着金日", "取引先名", "入金金額", "科目", "備考"]
    for c, name in enumerate(cols, start=1):
        _header_cell(ws, 1, c, name, COLOR_HEADER_UNMATCHED, font_color="000000")

    ws.row_dimensions[1].height = 25

    for r, deal in enumerate(unmatched, start=2):
        bg = COLOR_ROW_UNMATCHED
        _data_cell(ws, r, 1, deal.get("取引ID", ""),   bg, center=True)
        _data_cell(ws, r, 2, deal.get("着金日", ""),   bg, center=True)
        _data_cell(ws, r, 3, deal.get("取引先名", ""), bg)
        _data_cell(ws, r, 4, deal.get("入金金額", 0),  bg, number_format='#,##0', center=True)
        _data_cell(ws, r, 5, deal.get("科目", ""),     bg)
        _data_cell(ws, r, 6, deal.get("備考", ""),     bg)

    _auto_column_width(ws)


def _write_summary_sheet(ws, result: dict, generated_at: str):
    ws.title = "サマリー"
    ws.sheet_properties.tabColor = "1F3864"

    overdue         = result.get("overdue", [])
    seikyu_kakunin  = result.get("seikyu_kakunin", [])
    ichiji_hokan    = result.get("ichiji_hokan", [])
    upcoming        = result.get("upcoming", [])
    paid            = result.get("paid", [])
    unpaid          = result.get("unpaid", [])

    overdue_total        = sum(b.get("請求金額", 0) for b in overdue)
    seikyu_kakunin_total = sum(b.get("請求金額", 0) for b in seikyu_kakunin)
    ichiji_total         = sum(b.get("請求金額", 0) for b in ichiji_hokan)
    upcoming_total       = sum(b.get("請求金額", 0) for b in upcoming)
    paid_total           = sum(b.get("請求金額", 0) for b in paid)

    rows = [
        ("集計日時",                generated_at),
        (None, None),
        ("■ 未収（未入金）",          None),
        ("件数",                    len(overdue)),
        ("合計金額（税込）",         overdue_total),
        (None, None),
        ("■ 請求済みか確認",          None),
        ("件数",                    len(seikyu_kakunin)),
        ("合計金額（税込）",         seikyu_kakunin_total),
        (None, None),
        ("■ 一時保管（毎月要確認）",  None),
        ("件数",                    len(ichiji_hokan)),
        ("合計金額（税込）",         ichiji_total),
        (None, None),
        ("■ 期日前請求書",           None),
        ("件数",                    len(upcoming)),
        ("合計金額（税込）",         upcoming_total),
        (None, None),
        ("■ 未入金合計",             None),
        ("件数",                    len(unpaid)),
        ("合計金額（税込）",         overdue_total + seikyu_kakunin_total + ichiji_total + upcoming_total),
        (None, None),
        ("■ 入金確認済み",           None),
        ("件数",                    len(paid)),
        ("合計金額（税込）",         paid_total),
    ]

    for r, (label, value) in enumerate(rows, start=1):
        if label is None:
            continue
        cell_l = ws.cell(row=r, column=1, value=label)
        cell_l.font = Font(bold=True)
        cell_l.alignment = Alignment(horizontal="left", vertical="center")
        if value is not None:
            cell_v = ws.cell(row=r, column=2, value=value)
            cell_v.alignment = Alignment(horizontal="right", vertical="center")
            if isinstance(value, int) and "金額" in label:
                cell_v.number_format = '#,##0'

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 20


def generate_report(result: dict, output_dir: str = None) -> str:
    """
    Excelレポートを生成してファイルパスを返す

    Args:
        result: matcher.match()の返り値
        output_dir: 出力先ディレクトリ（省略時はスクリプトと同じ場所に output/ フォルダ）

    Returns:
        生成されたExcelファイルのパス
    """
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)

    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp    = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename     = f"未入金チェック_{timestamp}.xlsx"
    filepath     = os.path.join(output_dir, filename)

    wb = openpyxl.Workbook()
    # デフォルトシートを使ってサマリーを先頭に
    ws_summary = wb.active
    _write_summary_sheet(ws_summary, result, generated_at)

    ws_overdue = wb.create_sheet()
    _write_overdue_sheet(ws_overdue, result.get("overdue", []))

    if result.get("seikyu_kakunin"):
        ws_seikyu = wb.create_sheet()
        _write_seikyu_kakunin_sheet(ws_seikyu, result["seikyu_kakunin"])

    if result.get("ichiji_hokan"):
        ws_ichiji = wb.create_sheet()
        _write_ichiji_hokan_sheet(ws_ichiji, result["ichiji_hokan"])

    ws_upcoming = wb.create_sheet()
    _write_upcoming_sheet(ws_upcoming, result.get("upcoming", []))

    ws_paid = wb.create_sheet()
    _write_paid_sheet(ws_paid, result.get("paid", []))

    wb.save(filepath)
    print(f"[レポート] 保存完了: {filepath}")
    return filepath
