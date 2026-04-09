"""
未入金チェックシステム — Webアプリ メイン

起動: python app.py  または  start.bat
アクセス: http://localhost:5000
"""

import os
import json
import threading
from datetime import datetime
from flask import (
    Flask, render_template, redirect, request,
    jsonify, send_file, url_for, flash
)
from dotenv import load_dotenv

import auth
from mf_invoice    import get_unpaid_billings
from mf_accounting import get_income_deals
from matcher       import match
from reporter      import generate_report
from scheduler     import init_scheduler

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mf-unpaid-check-secret-2026")

DATA_DIR   = os.path.join(os.path.dirname(__file__), "data")
RESULT_FILE = os.path.join(DATA_DIR, "last_result.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ========================================
# 実行状態管理
# ========================================
_status = {
    "running":   False,
    "message":   "",
    "progress":  0,        # 0-100
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
        _update_status(running=True, error=None, progress=10, message="請求書データを取得中...")
        billings = get_unpaid_billings()

        _update_status(progress=40, message="入金データを取得中...")
        deals = get_income_deals(from_date=from_date, to_date=to_date)

        _update_status(progress=70, message="照合処理中...")
        result = match(billings, deals)

        _update_status(progress=85, message="Excelレポートを生成中...")
        output_path = generate_report(result)

        # 結果をJSONで保存（ダッシュボード表示用）
        _save_result(result, output_path)

        _update_status(
            running=False,
            progress=100,
            message="完了",
            last_run=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            last_file=output_path,
            error=None,
        )

    except Exception as e:
        _update_status(running=False, error=str(e), message="エラーが発生しました", progress=0)


def _save_result(result: dict, output_path: str):
    """照合結果をJSON保存（_rawフィールドは除外）"""
    def _clean(items):
        return [{k: v for k, v in item.items() if k != "_raw"} for item in items]

    data = {
        "saved_at":        datetime.now().isoformat(),
        "output_path":     output_path,
        "paid":            _clean(result["paid"]),
        "diff":            _clean(result.get("diff", [])),
        "unpaid":          _clean(result["unpaid"]),
        "unmatched_deals": _clean(result["unmatched_deals"]),
    }
    with open(RESULT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_result() -> dict | None:
    if not os.path.exists(RESULT_FILE):
        return None
    with open(RESULT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


# ========================================
# ルーティング
# ========================================

@app.route("/")
def dashboard():
    auth_invoice    = auth.is_authenticated("invoice")
    auth_accounting = auth.is_authenticated("accounting")
    result          = _load_result()
    today_str       = datetime.now().strftime("%Y-%m-%d")

    overdue  = []
    upcoming = []

    if result:
        unpaid = result.get("unpaid", [])
        overdue  = sorted(
            [b for b in unpaid if b.get("支払期限", "") < today_str],
            key=lambda x: x.get("支払期限", "")
        )
        upcoming = sorted(
            [b for b in unpaid if b.get("支払期限", "") >= today_str or not b.get("支払期限")],
            key=lambda x: x.get("支払期限", "")
        )

    return render_template(
        "dashboard.html",
        auth_invoice=auth_invoice,
        auth_accounting=auth_accounting,
        result=result,
        overdue=overdue,
        upcoming=upcoming,
        status=dict(_status),
        today=today_str,
    )


@app.route("/run", methods=["POST"])
def run():
    with _status_lock:
        if _status["running"]:
            return jsonify({"error": "実行中です"}), 409

    from_date = request.form.get("from_date") or None
    to_date   = request.form.get("to_date")   or None

    thread = threading.Thread(
        target=_run_check, args=(from_date, to_date), daemon=True
    )
    thread.start()
    return redirect(url_for("dashboard"))


@app.route("/api/status")
def api_status():
    """フロントエンドのポーリング用"""
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
# 起動
# ========================================

if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    init_scheduler(run_func=_run_check)

    import webbrowser, threading
    threading.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()

    print(f"\n{'='*50}")
    print(f"  未入金チェックシステム 起動中")
    print(f"  http://localhost:{port}")
    print(f"{'='*50}\n")

    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
