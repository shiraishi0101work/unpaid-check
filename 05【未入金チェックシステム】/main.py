"""
未入金チェックシステム — メイン実行スクリプト

使い方:
  python main.py                          # 全期間の未入金チェック
  python main.py --from 2026-01-01        # 特定期間の入金データを使用
  python main.py --from 2026-01-01 --to 2026-03-31
  python main.py --open                   # 実行後にExcelを自動で開く
"""

import argparse
import os
import subprocess
import sys

from mf_invoice import get_unpaid_billings
from reporter   import generate_report


def main():
    parser = argparse.ArgumentParser(
        description="MFクラウド請求書 未入金チェックシステム"
    )
    parser.add_argument(
        "--open", dest="auto_open", action="store_true",
        help="生成したExcelファイルを自動で開く"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("  未入金チェックシステム 起動")
    print("=" * 60)

    # ① MFクラウド請求書から未入金請求書を取得
    billings = get_unpaid_billings()

    if not billings:
        print("\n未入金の請求書はありません。")
        return

    result = {"unpaid": billings, "paid": [], "diff": [], "unmatched_deals": []}

    # ② Excelレポート生成
    output_path = generate_report(result)

    # ⑤ サマリーをコンソールにも表示
    from datetime import datetime as _dt
    today_str = _dt.now().strftime("%Y-%m-%d")
    unpaid   = result["unpaid"]
    overdue  = [b for b in unpaid if b.get("支払期限", "") < today_str]
    upcoming = [b for b in unpaid if b.get("支払期限", "") >= today_str or not b.get("支払期限")]

    print()
    print("=" * 60)
    print("  照合結果サマリー")
    print("=" * 60)
    diff = result.get("diff", [])
    print(f"  支払期限超過:     {len(overdue):>4} 件  "
          f"¥{sum(b['請求金額'] for b in overdue):>12,.0f}")
    print(f"  期日前（未入金）:  {len(upcoming):>4} 件  "
          f"¥{sum(b['請求金額'] for b in upcoming):>12,.0f}")
    print(f"  差額あり:         {len(diff):>4} 件  "
          f"¥{sum(b['請求金額'] for b in diff):>12,.0f}")
    print(f"  入金確認済み:     {len(result['paid']):>4} 件  "
          f"¥{sum(b['請求金額'] for b in result['paid']):>12,.0f}")
    print(f"  照合不能な入金:   {len(result['unmatched_deals']):>4} 件")
    print("=" * 60)
    print(f"  出力ファイル: {output_path}")
    print("=" * 60)

    if overdue:
        print("\n  【支払期限超過請求書】")
        print(f"  {'取引先名':<20} {'請求番号':<15} {'支払期限':<12} {'請求金額':>12}")
        print("  " + "-" * 65)
        for b in sorted(overdue, key=lambda x: x.get("支払期限", "")):
            print(f"  {b['取引先名']:<20} {b['請求番号']:<15} {b['支払期限']:<12} "
                  f"¥{b['請求金額']:>11,.0f}")

    if upcoming:
        print("\n  【期日前請求書】")
        print(f"  {'取引先名':<20} {'請求番号':<15} {'支払期限':<12} {'請求金額':>12}")
        print("  " + "-" * 65)
        for b in sorted(upcoming, key=lambda x: x.get("支払期限", "")):
            print(f"  {b['取引先名']:<20} {b['請求番号']:<15} {b['支払期限']:<12} "
                  f"¥{b['請求金額']:>11,.0f}")

    if diff:
        print("\n  【差額あり請求書】")
        print(f"  {'取引先名':<20} {'請求番号':<15} {'着金日':<12} {'請求金額':>12} {'着金金額':>12} {'差額':>12}")
        print("  " + "-" * 85)
        for b in sorted(diff, key=lambda x: x.get("支払期限", "")):
            d = b.get("差額", 0)
            sign = "▲" if d < 0 else "+"
            print(f"  {b['取引先名']:<20} {b['請求番号']:<15} {b.get('着金日',''):<12} "
                  f"¥{b['請求金額']:>11,.0f} ¥{b.get('着金金額',0):>11,.0f} "
                  f"{sign}¥{abs(d):>10,.0f}")

    # Excelを自動で開く
    if args.auto_open:
        if sys.platform == "win32":
            os.startfile(output_path)
        elif sys.platform == "darwin":
            subprocess.run(["open", output_path])
        else:
            subprocess.run(["xdg-open", output_path])


if __name__ == "__main__":
    main()
