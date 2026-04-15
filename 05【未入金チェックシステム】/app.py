"""
未入金チェックシステム — Webアプリ メイン

起動: python app.py
アクセス: http://localhost:5000
"""

import os
import json
import threading
from datetime import datetime, date
from flask import (
    Flask, render_template, redirect, request,
    jsonify, send_file, url_for, flash
)
from dotenv import load_dotenv

import auth
from mf_invoice    import get_all_billings, UNPAID_STATUSES, PAID_STATUSES
from mf_accounting import get_income_deals
from matcher       import match
from reporter      import generate_report
from scheduler     import init_scheduler

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mf-unpaid-check-secret-2026")

DATA_DIR     = os.path.join(os.path.dirname(__file__), "data")
RESULT_FILE  = os.path.join(DATA_DIR, "last_result.json")
SETTINGS_FILE= os.path.join(DATA_DIR, "settings.json")
META_FILE    = os.path.join(DATA_DIR, "invoice_meta.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ========================================
# 設定管理
# ========================================

DEFAULT_SETTINGS = {
    "fiscal_year_start_month": 4,   # 4月始まり
    "company_name": "",
}

def load_settings() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULT_SETTINGS)
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        s = json.load(f)
    return {**DEFAULT_SETTINGS, **s}

def save_settings(settings: dict):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# ========================================
# 請求書メタデータ管理（担当者・メモ・手動着金）
# ========================================

def load_meta() -> dict:
    if not os.path.exists(META_FILE):
        return {}
    with open(META_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_meta(meta: dict):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

# ========================================
# 年度ユーティリティ
# ========================================

def get_fiscal_year_range(year: int, start_month: int) -> tuple[str, str]:
    """年度の開始日・終了日を返す (YYYY-MM-DD)"""
    from_date = f"{year}-{start_month:02d}-01"
    end_year  = year + 1 if start_month > 1 else year
    end_month = start_month - 1 if start_month > 1 else 12
    import calendar
    last_day = calendar.monthrange(end_year, end_month)[1]
    to_date = f"{end_year}-{end_month:02d}-{last_day:02d}"
    return from_date, to_date

def get_current_fiscal_year(start_month: int) -> int:
    """今日の日付から現在の事業年度（開始年）を返す"""
    today = date.today()
    if today.month >= start_month:
        return today.year
    return today.year - 1

# ========================================
# 実行状態管理
# ========================================
_status = {
    "running":   False,
    "message":   "",
    "progress":  0,
    "error":     None,
    "last_run":  None,
    "last_file": None,
}
_status_lock = threading.Lock()

def _update_status(**kwargs):
    with _status_lock:
        _status.update(kwargs)

def _run_check(from_date=None, to_date=None):
    """バックグラウンドで照合処理を実行"""
    try:
        _update_status(running=True, error=None, progress=5, message="請求書データを取得中...")
        try:
            auth.get_access_token("invoice")
        except Exception as e:
            raise RuntimeError(f"MFクラウド請求書の認証が必要です: {e}")

        all_billings = get_all_billings(from_date=from_date, to_date=to_date)
        if len(all_billings) == 0:
            raise RuntimeError("請求書データが0件でした。APIの応答を確認してください。")

        print(f"[照合] 請求書 {len(all_billings)}件 取得完了")
        _update_status(progress=40, message=f"請求書 {len(all_billings)}件 取得完了。メタデータをマージ中...")

        today_str = datetime.now().strftime("%Y-%m-%d")
        meta = load_meta()

        # メタデータをマージ
        for b in all_billings:
            bid = b.get("請求書ID", "")
            m = meta.get(bid, {})
            b["担当者"]        = m.get("担当者", "")
            b["メモ_手動"]     = m.get("メモ", "")
            b["着金日_手動"]   = m.get("着金日_手動", "")
            b["着金金額_手動"] = m.get("着金金額_手動", 0)

        # MF Invoice のステータスで一次分類
        mf_unpaid = [b for b in all_billings if b["入金状態"] in UNPAID_STATUSES]
        mf_paid   = [b for b in all_billings if b["入金状態"] in PAID_STATUSES]

        paid_billings   = list(mf_paid)
        diff_billings   = []
        unpaid_billings = list(mf_unpaid)
        unmatched_deals = []

        # ── MF会計と照合（連携済みの場合）──────────────────────────
        if auth.is_authenticated("accounting"):
            _update_status(progress=60, message="会計データを取得して照合中...")
            try:
                income_deals = get_income_deals(from_date=from_date, to_date=to_date)
                print(f"[照合] 入金データ {len(income_deals)}件で照合開始")

                if income_deals:
                    matched = match(mf_unpaid, income_deals)
                    # 会計照合で入金確認できたものを追加
                    paid_billings   += matched["paid"]
                    diff_billings    = matched["diff"]
                    unpaid_billings  = matched["unpaid"]
                    unmatched_deals  = matched["unmatched_deals"]
                    print(
                        f"[照合] 完了: 入金確認={len(paid_billings)}件 "
                        f"差額={len(diff_billings)}件 "
                        f"未入金={len(unpaid_billings)}件"
                    )
                else:
                    print("[照合] 入金データ0件のため照合スキップ、MF請求書ステータスのみで分類")
            except Exception as e:
                import traceback
                print(f"[照合] 会計API照合エラー（MFステータスのみで分類）: {e}")
                traceback.print_exc()
        else:
            print("[照合] 会計未連携のため、MF請求書ステータスのみで分類")

        # ── 未入金を期限超過/期日前に分類 ───────────────────────────
        _update_status(progress=80, message="分類中...")
        overdue  = sorted(
            [b for b in unpaid_billings if b.get("支払期限", "") and b.get("支払期限", "") < today_str],
            key=lambda x: x.get("支払期限", "")
        )
        upcoming = sorted(
            [b for b in unpaid_billings if not b.get("支払期限") or b.get("支払期限", "") >= today_str],
            key=lambda x: x.get("支払期限", "")
        )

        result = {
            "unpaid":          unpaid_billings,
            "overdue":         overdue,
            "upcoming":        upcoming,
            "paid":            paid_billings,
            "diff":            diff_billings,
            "unmatched_deals": unmatched_deals,
            "total":           len(all_billings),
            "from_date":       from_date or "",
            "to_date":         to_date or "",
        }

        _update_status(progress=90, message="Excelレポートを生成中...")
        output_path = generate_report(result)
        _save_result(result, output_path)

        _update_status(
            running=False, progress=100, message="完了",
            last_run=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_file=output_path, error=None,
        )

    except Exception as e:
        import traceback
        traceback.print_exc()
        _update_status(running=False, error=str(e), message="エラーが発生しました", progress=0)


def _clean_items(items: list) -> list:
    return [{k: v for k, v in item.items() if k != "_raw"} for item in items]


def _merge_results(existing: dict, new_result: dict) -> dict:
    """
    既存の照合結果と新しい照合結果をマージする。

    ルール:
    - 今回のフェッチ対象外（日付範囲外）の請求書はそのまま保持
    - 今回の対象内の請求書:
        paid/diff → 常に採用（確認済みを上書きしない）
        unpaid    → 既存がpaid/diffなら既存を維持、そうでなければ新結果を採用
    - 新しく登場した請求書（既存にない）は追加
    """
    def by_id(lst):
        return {b["請求書ID"]: b for b in lst if b.get("請求書ID")}

    ex_paid   = by_id(existing.get("paid",   []))
    ex_diff   = by_id(existing.get("diff",   []))
    ex_unpaid = by_id(existing.get("unpaid", []))

    nw_paid   = by_id(new_result.get("paid",   []))
    nw_diff   = by_id(new_result.get("diff",   []))
    nw_unpaid = by_id(new_result.get("unpaid", []))

    all_new_ids = set(nw_paid) | set(nw_diff) | set(nw_unpaid)

    merged_paid   = {}
    merged_diff   = {}
    merged_unpaid = {}

    # ── 既存結果の保持（今回対象外のものはそのまま残す） ──
    for bid, b in ex_paid.items():
        if bid not in all_new_ids:
            merged_paid[bid] = b          # 今回未対象 → そのまま保持

    for bid, b in ex_diff.items():
        if bid not in all_new_ids:
            merged_diff[bid] = b

    for bid, b in ex_unpaid.items():
        if bid not in all_new_ids:
            merged_unpaid[bid] = b

    # ── 新しい照合結果を優先的にマージ ──
    for bid, b in nw_paid.items():
        merged_paid[bid] = b              # 今回 paid → 常に採用
        merged_diff.pop(bid, None)
        merged_unpaid.pop(bid, None)

    for bid, b in nw_diff.items():
        if bid not in merged_paid:        # paid済みは下げない
            merged_diff[bid] = b
            merged_unpaid.pop(bid, None)

    for bid, b in nw_unpaid.items():
        if bid not in merged_paid and bid not in merged_diff:
            # 既存で paid/diff だったものは下げない
            if bid in ex_paid or bid in ex_diff:
                pass
            else:
                merged_unpaid[bid] = b

    paid_list   = list(merged_paid.values())
    diff_list   = list(merged_diff.values())
    unpaid_list = list(merged_unpaid.values())

    today_str = datetime.now().strftime("%Y-%m-%d")
    overdue  = sorted([b for b in unpaid_list if b.get("支払期限", "") and b["支払期限"] < today_str],
                      key=lambda x: x.get("支払期限", ""))
    upcoming = sorted([b for b in unpaid_list if not b.get("支払期限") or b["支払期限"] >= today_str],
                      key=lambda x: x.get("支払期限", ""))

    return {
        "paid":            paid_list,
        "diff":            diff_list,
        "unpaid":          unpaid_list,
        "overdue":         overdue,
        "upcoming":        upcoming,
        "unmatched_deals": new_result.get("unmatched_deals", []),
        "total":           len(paid_list) + len(diff_list) + len(unpaid_list),
    }


def _save_result(result: dict, output_path: str):
    data = {
        "saved_at":        datetime.now().isoformat(),
        "output_path":     output_path,
        "unpaid":          _clean_items(result["unpaid"]),
        "overdue":         _clean_items(result["overdue"]),
        "upcoming":        _clean_items(result["upcoming"]),
        "paid":            _clean_items(result["paid"]),
        "diff":            _clean_items(result["diff"]),
        "unmatched_deals": _clean_items(result["unmatched_deals"]),
        "total":           result["total"],
        "from_date":       result.get("from_date", ""),
        "to_date":         result.get("to_date", ""),
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_result() -> dict | None:
    if not os.path.exists(RESULT_FILE):
        return None
    with open(RESULT_FILE, encoding="utf-8") as f:
        return json.load(f)

# ========================================
# ルーティング — ダッシュボード
# ========================================

@app.route("/")
def dashboard():
    settings        = load_settings()
    auth_invoice    = auth.is_authenticated("invoice")
    auth_accounting = auth.is_authenticated("accounting")
    result          = _load_result()
    meta            = load_meta()
    today_str       = datetime.now().strftime("%Y-%m-%d")

    start_month = settings["fiscal_year_start_month"]
    # URL パラメータで年度切替
    fiscal_year = request.args.get("year", type=int)
    if fiscal_year is None:
        fiscal_year = get_current_fiscal_year(start_month)

    prev_year = fiscal_year - 1
    next_year = fiscal_year + 1
    fy_from, fy_to = get_fiscal_year_range(fiscal_year, start_month)

    # 年度フィルタをかけた一覧
    def in_fy(b):
        d = b.get("請求日") or b.get("支払期限") or ""
        return fy_from <= d <= fy_to

    if result:
        # メタデータを最新にマージ
        for lst in [result.get("unpaid",[]), result.get("overdue",[]),
                    result.get("upcoming",[]), result.get("paid",[])]:
            for b in lst:
                bid = b.get("請求書ID","")
                m = meta.get(bid, {})
                b["担当者"]        = m.get("担当者", b.get("担当者",""))
                b["メモ_手動"]     = m.get("メモ", b.get("メモ_手動",""))
                b["着金日_手動"]   = m.get("着金日_手動", b.get("着金日_手動",""))
                b["着金金額_手動"] = m.get("着金金額_手動", b.get("着金金額_手動", 0))

        all_data  = result.get("unpaid",[]) + result.get("paid",[])
        overdue   = [b for b in result.get("overdue",[])  if in_fy(b)]
        upcoming  = [b for b in result.get("upcoming",[]) if in_fy(b)]
        paid_fy   = [b for b in result.get("paid",[])     if in_fy(b)]
        diff_fy   = [b for b in result.get("diff",[])     if in_fy(b)]

        # 着金月ごとにグループ化（着金日 → 支払期限 → 請求日 の優先順で月を決める）
        monthly = {}
        for b in paid_fy:
            ym = (b.get("着金日") or b.get("着金日_手動") or b.get("支払期限") or b.get("請求日") or "")[:7]
            if ym:
                monthly.setdefault(ym, []).append(b)
        monthly_sorted = sorted(monthly.items())
    else:
        overdue = upcoming = paid_fy = diff_fy = []
        monthly_sorted = []

    return render_template(
        "dashboard.html",
        auth_invoice=auth_invoice,
        auth_accounting=auth_accounting,
        result=result,
        overdue=overdue,
        upcoming=upcoming,
        paid_fy=paid_fy,
        diff_fy=diff_fy,
        monthly_sorted=monthly_sorted,
        status=dict(_status),
        today=today_str,
        settings=settings,
        fiscal_year=fiscal_year,
        prev_year=prev_year,
        next_year=next_year,
        fy_from=fy_from,
        fy_to=fy_to,
    )


@app.route("/run", methods=["POST"])
def run():
    with _status_lock:
        if _status["running"]:
            return jsonify({"error": "実行中です"}), 409

    settings    = load_settings()
    start_month = settings["fiscal_year_start_month"]
    fiscal_year = request.form.get("fiscal_year", type=int)
    if fiscal_year is None:
        fiscal_year = get_current_fiscal_year(start_month)

    from_date = request.form.get("from_date") or None
    to_date   = request.form.get("to_date")   or None

    # 日付未指定なら年度から自動設定
    if not from_date and not to_date:
        from_date, to_date = get_fiscal_year_range(fiscal_year, start_month)

    thread = threading.Thread(
        target=_run_check, args=(from_date, to_date), daemon=True
    )
    thread.start()
    return redirect(url_for("dashboard", year=fiscal_year))


@app.route("/api/status")
def api_status():
    with _status_lock:
        return jsonify(dict(_status))


@app.route("/download")
def download():
    with _status_lock:
        path = _status.get("last_file")
    if not path:
        result = _load_result()
        path = result.get("output_path") if result else None
    if not path or not os.path.exists(path):
        flash("ダウンロードできるファイルがありません。先に実行してください。")
        return redirect(url_for("dashboard"))
    return send_file(path, as_attachment=True)

# ========================================
# ルーティング — 設定
# ========================================

@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    settings = load_settings()
    if request.method == "POST":
        settings["fiscal_year_start_month"] = int(request.form.get("fiscal_year_start_month", 4))
        settings["company_name"] = request.form.get("company_name", "").strip()
        save_settings(settings)
        flash("設定を保存しました", "success")
        return redirect(url_for("settings_page"))
    return render_template("settings.html", settings=settings,
                           auth_invoice=auth.is_authenticated("invoice"),
                           auth_accounting=auth.is_authenticated("accounting"))

# ========================================
# ルーティング — 請求書メタデータ編集
# ========================================

@app.route("/api/invoice/<invoice_id>/meta", methods=["GET", "POST"])
def invoice_meta(invoice_id):
    meta = load_meta()
    if request.method == "POST":
        data = request.get_json() or {}
        meta.setdefault(invoice_id, {})
        for key in ["担当者", "メモ", "着金日_手動", "着金金額_手動"]:
            if key in data:
                meta[invoice_id][key] = data[key]
        save_meta(meta)
        return jsonify({"ok": True})
    return jsonify(meta.get(invoice_id, {}))

# ========================================
# ルーティング — API接続テスト
# ========================================

@app.route("/api/test-connection")
def test_connection():
    results = {}

    # 請求書API
    try:
        token = auth.get_access_token("invoice")
        import requests as req
        r = req.get(
            "https://invoice.moneyforward.com/api/v3/billings",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"per_page": 1, "page": 1},
            timeout=10,
        )
        if r.ok:
            total = r.json().get("pagination", {}).get("total_count", "?")
            results["invoice"] = {"ok": True, "message": f"✅ 接続OK（総件数: {total}件）"}
        else:
            results["invoice"] = {"ok": False, "message": f"❌ HTTPエラー {r.status_code}"}
    except Exception as e:
        results["invoice"] = {"ok": False, "message": f"❌ {e}"}

    # 会計API
    try:
        token = auth.get_access_token("accounting")
        import requests as req
        r = req.get(
            "https://api-accounting.moneyforward.com/api/v3/offices",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=10,
        )
        if r.ok:
            results["accounting"] = {"ok": True, "message": "✅ 接続OK"}
        else:
            results["accounting"] = {"ok": False, "message": f"❌ HTTPエラー {r.status_code}"}
    except Exception as e:
        results["accounting"] = {"ok": False, "message": f"❌ {e}"}

    return jsonify(results)


@app.route("/api/debug-accounting")
def debug_accounting():
    """会計APIの動作確認用デバッグエンドポイント"""
    import requests as _req
    import traceback
    result = {}

    # トークン取得
    try:
        token = auth.get_access_token("accounting")
        result["token_prefix"] = token[:15] + "..."
    except Exception as e:
        return jsonify({"step": "token", "error": str(e)}), 500

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    # offices API
    try:
        r = _req.get("https://api-accounting.moneyforward.com/api/v3/offices",
                     headers=headers, timeout=10)
        result["offices_status"] = r.status_code
        result["offices_body"]   = r.text[:500]
        if r.ok:
            offices = r.json().get("offices", [])
            result["office_ids"] = [o.get("id") for o in offices]
    except Exception as e:
        result["offices_error"] = str(e)

    # journals API - パターン別に試す
    from datetime import date as _d
    today = _d.today().strftime("%Y-%m-%d")
    test_cases = [
        {"per_page": 100, "page": 1, "end_date": today},
        {"per_page":  50, "page": 1, "end_date": today},
        {"per_page":  20, "page": 1, "end_date": today},
        {"per_page":  10, "page": 1, "end_date": today},
        {"per_page": 100, "page": 1, "start_date": "2025-12-01", "end_date": "2026-02-28"},
        {"per_page":  10, "page": 1, "start_date": "2025-12-01", "end_date": "2026-02-28"},
    ]
    for i, params in enumerate(test_cases):
        try:
            r = _req.get("https://api-accounting.moneyforward.com/api/v3/journals",
                         headers=headers, params=params, timeout=10)
            result[f"test{i}_params"] = params
            result[f"test{i}_status"] = r.status_code
            result[f"test{i}_body"]   = r.text[:300]
            if r.ok:
                break  # 成功したら終了
        except Exception as e:
            result[f"test{i}_error"] = str(e)

    return jsonify(result)


@app.route("/api/debug-check")
def debug_check():
    try:
        token = auth.get_access_token("invoice")
        billings = get_all_billings()
        from collections import Counter
        status_count = Counter(b["入金状態"] for b in billings)
        return jsonify({
            "total": len(billings),
            "token_prefix": token[:10] + "...",
            "status_counts": dict(status_count),
            "sample_due_date": billings[0].get("支払期限") if billings else None,
        })
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500

# ========================================
# OAuth認証
# ========================================

@app.route("/oauth/start/<service_name>")
def oauth_start(service_name):
    if service_name not in ("invoice", "accounting"):
        return "不正なサービス名", 400
    return redirect(auth.get_auth_url(service_name))


@app.route("/oauth/callback/<service_name>")
def oauth_callback(service_name):
    if service_name not in ("invoice", "accounting"):
        return "不正なサービス名", 400
    code  = request.args.get("code")
    state = request.args.get("state", "")
    error = request.args.get("error")
    if error:
        flash(f"認証がキャンセルされました: {error}")
        return redirect(url_for("dashboard"))
    if not code:
        flash("認可コードが取得できませんでした")
        return redirect(url_for("dashboard"))
    try:
        ok = auth.handle_callback(service_name, code, state)
        if ok:
            label = "クラウド請求書" if service_name == "invoice" else "クラウド会計"
            flash(f"MF{label}の認証が完了しました", "success")
        else:
            flash("認証に失敗しました（stateが一致しません）", "error")
    except Exception as e:
        flash(f"認証エラー: {e}", "error")
    return redirect(url_for("dashboard"))


@app.route("/oauth/revoke/<service_name>", methods=["POST"])
def oauth_revoke(service_name):
    if service_name not in ("invoice", "accounting"):
        return "不正なサービス名", 400
    auth.revoke_token(service_name)
    label = "クラウド請求書" if service_name == "invoice" else "クラウド会計"
    flash(f"MF{label}の認証を解除しました")
    return redirect(url_for("dashboard"))

# ========================================
# 入金履歴ページ
# ========================================

PAYMENT_LINKS_FILE   = os.path.join(DATA_DIR, "payment_links.json")
PAYMENT_HISTORY_FILE = os.path.join(DATA_DIR, "payment_history.json")


def load_payment_links() -> dict:
    if not os.path.exists(PAYMENT_LINKS_FILE):
        return {}
    with open(PAYMENT_LINKS_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_payment_links(links: dict):
    with open(PAYMENT_LINKS_FILE, "w", encoding="utf-8") as f:
        json.dump(links, f, ensure_ascii=False, indent=2)


def load_payment_history() -> list:
    if not os.path.exists(PAYMENT_HISTORY_FILE):
        return []
    with open(PAYMENT_HISTORY_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_payment_history(deals: list):
    with open(PAYMENT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)


@app.route("/payments")
def payments():
    import name_utils
    from collections import Counter

    auth_accounting = auth.is_authenticated("accounting")
    auth_invoice    = auth.is_authenticated("invoice")
    deals           = load_payment_history()
    links           = load_payment_links()
    settings        = load_settings()

    # 全請求書（紐づけ候補として利用）
    result = _load_result()
    all_billings = []
    if result:
        all_billings = result.get("unpaid", []) + result.get("paid", [])
    # _raw キーを除去してJSONシリアライズ可能にする
    all_billings = [{k: v for k, v in b.items() if k != "_raw"} for b in all_billings]

    # 合算確認フラグ: 未入金請求書を取引先の正規化名でカウント
    unpaid_billings = result.get("unpaid", []) if result else []
    company_count = Counter(
        name_utils.normalize(b["取引先名"])
        for b in unpaid_billings
        if b.get("取引先名")
    )

    # 各 deal に紐づけ情報と合算確認フラグを付与
    enriched = []
    billing_by_id = {b["請求書ID"]: b for b in all_billings}

    for d in deals:
        deal = {k: v for k, v in d.items() if k != "_matched"}
        deal_id = deal.get("取引ID", "")
        link = links.get(deal_id, {})
        linked_ids = link.get("invoice_ids", [])

        deal["紐づけ請求書IDs"] = linked_ids
        deal["紐づけメモ"]       = link.get("note", "")
        deal["紐づけ請求書"]     = [billing_by_id[bid] for bid in linked_ids if bid in billing_by_id]

        # 合算確認: 同一取引先（正規化後）で未入金請求書が2件以上
        norm = name_utils.normalize(deal.get("取引先名", ""))
        deal["合算確認"] = company_count.get(norm, 0) >= 2

        enriched.append(deal)

    # 着金日の降順でソート
    enriched.sort(key=lambda x: x.get("着金日", ""), reverse=True)

    return render_template(
        "payments.html",
        deals=enriched,
        all_billings=all_billings,
        auth_accounting=auth_accounting,
        auth_invoice=auth_invoice,
        settings=settings,
    )


def _auto_link_deals(deals: list, existing_links: dict) -> dict:
    """
    入金データと請求書を自動照合してリンクを生成する。
    既存の手動リンクは上書きしない。
    """
    import name_utils

    result   = _load_result()
    if not result:
        return existing_links

    all_billings = result.get("unpaid", []) + result.get("paid", [])
    links = dict(existing_links)

    AMOUNT_TOLERANCE = 500   # 振込手数料差引などを許容
    NAME_THRESHOLD   = 0.75  # 自動リンクの最低類似度

    for deal in deals:
        deal_id = deal.get("取引ID", "")
        # 手動リンク済みはスキップ
        if deal_id in links and links[deal_id].get("invoice_ids"):
            continue

        candidates = name_utils.find_matches(
            deal.get("取引先名", ""), all_billings, threshold=NAME_THRESHOLD
        )
        if not candidates:
            continue

        deal_amount = deal.get("入金金額", 0)

        # ① 金額完全一致（誤差許容）の候補を探す
        exact = [
            c for c in candidates
            if abs(c.get("請求金額", 0) - deal_amount) <= AMOUNT_TOLERANCE
        ]

        if len(exact) == 1:
            # 1件だけ金額一致 → 自動リンク
            links[deal_id] = {
                "invoice_ids": [exact[0]["請求書ID"]],
                "note": "自動紐づけ",
                "auto": True,
            }
        elif len(exact) > 1:
            # 複数件金額一致 → 合算の可能性、IDを全部候補として記録（未確定）
            links[deal_id] = {
                "invoice_ids": [c["請求書ID"] for c in exact],
                "note": "自動紐づけ（合算確認）",
                "auto": True,
            }
        elif len(candidates) == 1:
            # 金額不一致でも候補1件なら仮リンク
            links[deal_id] = {
                "invoice_ids": [candidates[0]["請求書ID"]],
                "note": f"自動紐づけ（金額差: ¥{deal_amount - candidates[0].get('請求金額',0):,}）",
                "auto": True,
            }

    return links


@app.route("/payments/fetch", methods=["POST"])
def payments_fetch():
    """MFクラウド会計から入金データを取得してキャッシュ、自動紐づけも実行"""
    from mf_accounting import get_income_deals

    # フォームから日付取得、未入力なら年度から自動設定
    from_date = request.form.get("from_date") or None
    to_date   = request.form.get("to_date")   or None

    if not from_date or not to_date:
        settings    = load_settings()
        start_month = settings["fiscal_year_start_month"]
        fiscal_year = get_current_fiscal_year(start_month)
        fy_from, fy_to = get_fiscal_year_range(fiscal_year, start_month)
        if not from_date:
            from_date = fy_from
        if not to_date:
            to_date = fy_to

    # MF会計APIは未来日付を受け付けないため、終了日を今日に制限
    today = date.today().strftime("%Y-%m-%d")
    if to_date > today:
        to_date = today

    try:
        deals   = get_income_deals(from_date=from_date, to_date=to_date)
        cleaned = [{k: v for k, v in d.items() if k != "_matched"} for d in deals]
        save_payment_history(cleaned)

        # 自動紐づけ実行
        existing_links = load_payment_links()
        new_links = _auto_link_deals(cleaned, existing_links)
        save_payment_links(new_links)
        auto_count = sum(1 for v in new_links.values() if v.get("auto"))

        flash(f"入金データ {len(cleaned)}件を取得しました（自動紐づけ: {auto_count}件）", "success")
    except Exception as e:
        flash(f"取得エラー: {e}", "error")
    return redirect(url_for("payments"))


@app.route("/api/payments/<deal_id>/link", methods=["POST"])
def payments_link(deal_id):
    """入金データに請求書を紐づけ保存"""
    data        = request.get_json() or {}
    invoice_ids = data.get("invoice_ids", [])
    note        = data.get("note", "")

    links = load_payment_links()
    links[deal_id] = {"invoice_ids": invoice_ids, "note": note}
    save_payment_links(links)
    return jsonify({"ok": True})


@app.route("/api/payments/<deal_id>/suggest")
def payments_suggest(deal_id):
    """会計の取引先名からファジーマッチで請求書候補を返す"""
    import name_utils

    deals = load_payment_history()
    deal  = next((d for d in deals if d.get("取引ID") == deal_id), None)
    if not deal:
        return jsonify([])

    result = _load_result()
    if not result:
        return jsonify([])

    all_billings = result.get("unpaid", []) + result.get("paid", [])
    suggestions  = name_utils.find_matches(deal.get("取引先名", ""), all_billings, threshold=0.4)

    return jsonify([
        {
            "請求書ID": b["請求書ID"],
            "請求番号": b["請求番号"],
            "取引先名": b["取引先名"],
            "件名":     b.get("件名", ""),
            "請求金額": b["請求金額"],
            "請求日":   b["請求日"],
            "支払期限": b["支払期限"],
            "入金状態": b["入金状態"],
            "_score":   b["_score"],
        }
        for b in suggestions[:30]
    ])


# ========================================
# 起動
# ========================================

if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    init_scheduler(run_func=_run_check)
    import webbrowser, threading as _th
    _th.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"\n{'='*50}")
    print(f"  未入金チェックシステム 起動中")
    print(f"  http://localhost:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
