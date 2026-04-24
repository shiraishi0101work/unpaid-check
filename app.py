"""
未入金チェックシステム — Webアプリ メイン

起動: python app.py
アクセス: http://localhost:5000
"""

import os
import json
import threading
from datetime import datetime, date
from functools import wraps
from flask import (
    Flask, render_template, redirect, request,
    jsonify, send_file, url_for, flash, session
)
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

import auth
from mf_invoice    import get_all_billings, UNPAID_STATUSES, PAID_STATUSES
from reporter      import generate_report
from scheduler     import init_scheduler
from matcher       import match_by_kojinmei

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "mf-unpaid-check-secret-2026")

@app.errorhandler(500)
def handle_500(e):
    import traceback as _tb
    return jsonify({"error": f"内部エラー: {e}", "trace": _tb.format_exc()}), 500

DATA_DIR  = os.path.join(os.path.dirname(__file__), "data")
AUTH_FILE = os.path.join(DATA_DIR, "auth.json")
os.makedirs(DATA_DIR, exist_ok=True)

# バックグラウンドスレッド用：セッションの代わりにスレッドローカルで会社IDを保持
_thread_local = threading.local()

# ---- 会社IDごとのパスヘルパー ----
def get_company_id() -> str:
    """管理者は viewing_company_id で任意の会社を参照できる。スレッド内はthread_localを優先。"""
    if getattr(_thread_local, "company_id", None):
        return _thread_local.company_id
    try:
        return session.get("viewing_company_id") or session.get("company_id", "c_main")
    except RuntimeError:
        return "c_main"

def _cdir(cid: str = None) -> str:
    """会社のデータディレクトリを返す（なければ作成）"""
    d = os.path.join(DATA_DIR, cid or get_company_id())
    os.makedirs(d, exist_ok=True)
    return d

def _hdir(cid: str = None) -> str:
    d = os.path.join(_cdir(cid), "history")
    os.makedirs(d, exist_ok=True)
    return d

# ========================================
# 認証管理（マルチテナント）
# ========================================

def _load_auth_data() -> dict:
    """auth.json を読み込む。旧形式なら自動マイグレーション。"""
    if not os.path.exists(AUTH_FILE):
        return {"companies": []}
    with open(AUTH_FILE, encoding="utf-8") as f:
        data = json.load(f)
    # 旧形式（email直接）→ 新形式へ移行
    if "email" in data and "companies" not in data:
        data = _migrate_auth(data)
        _save_auth_data(data)
    return data

def _save_auth_data(data: dict):
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def _migrate_auth(old: dict) -> dict:
    """旧シングルテナント形式を新形式に移行し、データファイルもコピーする"""
    import shutil, uuid
    cid = "c_main"
    new = {
        "companies": [{
            "id":            cid,
            "email":         old["email"],
            "password_hash": old["password_hash"],
            "is_admin":      True,
            "created_at":    datetime.now().isoformat(),
        }]
    }
    # データファイルをサブディレクトリへコピー
    company_dir = os.path.join(DATA_DIR, cid)
    os.makedirs(company_dir, exist_ok=True)
    for fname in ["last_result.json", "settings.json", "invoice_meta.json",
                  "company_tantou.json", "deleted_drafts.json", "deleted_seikyu.json"]:
        src = os.path.join(DATA_DIR, fname)
        dst = os.path.join(company_dir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
    src_hist = os.path.join(DATA_DIR, "history")
    dst_hist = os.path.join(company_dir, "history")
    if os.path.exists(src_hist) and not os.path.exists(dst_hist):
        shutil.copytree(src_hist, dst_hist)
    # トークンもコピー
    tokens_dir = os.path.join(os.path.dirname(__file__), "tokens")
    comp_tok_dir = os.path.join(tokens_dir, cid)
    os.makedirs(comp_tok_dir, exist_ok=True)
    for fname in ["token_invoice.json"]:
        src = os.path.join(tokens_dir, fname)
        dst = os.path.join(comp_tok_dir, fname)
        if os.path.exists(src) and not os.path.exists(dst):
            shutil.copy2(src, dst)
    return new

def _find_company_by_email(email: str) -> dict | None:
    data = _load_auth_data()
    for c in data.get("companies", []):
        if c.get("email", "").lower() == email.strip().lower():
            return c
    return None

def _find_company_by_id(cid: str) -> dict | None:
    data = _load_auth_data()
    for c in data.get("companies", []):
        if c.get("id") == cid:
            return c
    return None

def _create_company_account(email: str, password: str, is_admin: bool = False) -> dict:
    import uuid
    cid = "c_" + uuid.uuid4().hex[:8]
    company = {
        "id":            cid,
        "email":         email.strip().lower(),
        "password_hash": generate_password_hash(password),
        "is_admin":      is_admin,
        "created_at":    datetime.now().isoformat(),
    }
    data = _load_auth_data()
    data["companies"].append(company)
    _save_auth_data(data)
    os.makedirs(_cdir(cid), exist_ok=True)
    os.makedirs(_hdir(cid), exist_ok=True)
    return company

# 後方互換（settings_page が load_auth() を呼んでいるため）
def load_auth() -> dict | None:
    cid = get_company_id()
    return _find_company_by_id(cid)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated

@app.context_processor
def inject_globals():
    s = load_settings()
    # セッションに is_admin がない場合は auth データから補完
    is_admin = session.get("is_admin")
    if is_admin is None and session.get("company_id"):
        c = _find_company_by_id(session["company_id"])
        is_admin = c.get("is_admin", False) if c else False
        session["is_admin"] = is_admin
    # 管理者用：全社リスト・現在参照中の会社情報
    all_companies = []
    viewing_company = None
    if is_admin:
        auth_data = _load_auth_data()
        all_companies = auth_data.get("companies", [])
        vcid = get_company_id()
        viewing_company = next((c for c in all_companies if c["id"] == vcid), None)
    return {
        "company_name":    s.get("company_name", ""),
        "is_admin":        bool(is_admin),
        "all_companies":   all_companies,
        "viewing_company": viewing_company,
        "viewing_cid":     get_company_id(),
    }

@app.before_request
def check_auth():
    public = ("/login", "/setup", "/static/")
    if not any(request.path.startswith(p) for p in public):
        if not session.get("logged_in"):
            data = _load_auth_data()
            if not data.get("companies"):
                if request.path != "/setup":
                    return redirect(url_for("setup"))
            else:
                return redirect(url_for("login", next=request.path))
        # 管理者専用ページ
        if request.path.startswith("/admin") and not session.get("is_admin"):
            return redirect(url_for("dashboard"))
        # 非管理者は viewing_company_id を自分の会社に固定
        if session.get("logged_in") and not session.get("is_admin"):
            session["viewing_company_id"] = session.get("company_id", "c_main")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))
    data = _load_auth_data()
    if not data.get("companies"):
        return redirect(url_for("setup"))
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        company  = _find_company_by_email(email)
        if company and check_password_hash(company["password_hash"], password):
            session["logged_in"]  = True
            session["email"]      = email
            session["company_id"] = company["id"]
            session["is_admin"]   = company.get("is_admin", False)
            next_url = request.form.get("next") or url_for("dashboard")
            return redirect(next_url)
        error = "メールアドレスまたはパスワードが違います"
    return render_template("login.html", error=error, next=request.args.get("next", ""))

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/setup", methods=["GET", "POST"])
def setup():
    data = _load_auth_data()
    if data.get("companies") and not session.get("logged_in"):
        return redirect(url_for("login"))
    error = None
    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm", "")
        if not email or "@" not in email:
            error = "有効なメールアドレスを入力してください"
        elif len(password) < 6:
            error = "パスワードは6文字以上にしてください"
        elif password != confirm:
            error = "パスワードが一致しません"
        else:
            company = _create_company_account(email, password, is_admin=True)
            session["logged_in"]  = True
            session["email"]      = email.lower()
            session["company_id"] = company["id"]
            session["is_admin"]   = True
            flash("アカウントを設定しました", "success")
            return redirect(url_for("dashboard"))
    return render_template("login.html", setup_mode=True, error=error, next="")

# ========================================
# 管理者：会社アカウント管理
# ========================================

@app.route("/admin/companies", methods=["GET"])
def admin_companies():
    data = _load_auth_data()
    companies = data.get("companies", [])
    return render_template("companies.html", companies=companies)

@app.route("/api/admin/create-company", methods=["POST"])
def api_create_company():
    if not session.get("is_admin"):
        # セッションにない場合はDBから確認
        c = _find_company_by_id(session.get("company_id", ""))
        if not (c and c.get("is_admin")):
            return jsonify({"error": "権限がありません"}), 403
        session["is_admin"] = True
    req_data = request.get_json(force=True, silent=True) or {}
    email    = req_data.get("email", "").strip()
    password = req_data.get("password", "")
    confirm  = req_data.get("confirm", "")
    if not email or "@" not in email:
        return jsonify({"error": "有効なメールアドレスを入力してください"}), 400
    if len(password) < 6:
        return jsonify({"error": "パスワードは6文字以上にしてください"}), 400
    if password != confirm:
        return jsonify({"error": "パスワードが一致しません"}), 400
    if _find_company_by_email(email):
        return jsonify({"error": "このメールアドレスはすでに登録されています"}), 400
    company = _create_company_account(email, password, is_admin=False)
    return jsonify({"ok": True, "id": company["id"], "email": company["email"]})

@app.route("/api/admin/switch-company", methods=["POST"])
def api_switch_company():
    if not session.get("is_admin"):
        c = _find_company_by_id(session.get("company_id", ""))
        if not (c and c.get("is_admin")):
            return jsonify({"error": "権限がありません"}), 403
        session["is_admin"] = True
    data = request.get_json(force=True, silent=True) or {}
    cid  = data.get("company_id", "")
    if not _find_company_by_id(cid):
        return jsonify({"error": "会社が見つかりません"}), 404
    session["viewing_company_id"] = cid
    return jsonify({"ok": True})

@app.route("/api/admin/update-company-role", methods=["POST"])
def api_update_company_role():
    if not session.get("is_admin"):
        c = _find_company_by_id(session.get("company_id", ""))
        if not (c and c.get("is_admin")):
            return jsonify({"error": "権限がありません"}), 403
        session["is_admin"] = True
    req_data = request.get_json(force=True, silent=True) or {}
    cid      = req_data.get("id", "")
    is_admin = req_data.get("is_admin", False)
    # 自分自身の管理者権限は外せない
    if cid == session.get("company_id") and not is_admin:
        return jsonify({"error": "自分自身の管理者権限は外せません"}), 400
    # 管理者が0人にならないようチェック
    data = _load_auth_data()
    admins = [c for c in data["companies"] if c.get("is_admin") and c["id"] != cid]
    if not is_admin and not admins:
        return jsonify({"error": "管理者が0人になるため変更できません"}), 400
    for c in data["companies"]:
        if c["id"] == cid:
            c["is_admin"] = bool(is_admin)
            break
    else:
        return jsonify({"error": "アカウントが見つかりません"}), 404
    _save_auth_data(data)
    return jsonify({"ok": True})

@app.route("/api/admin/update-company-login", methods=["POST"])
def api_update_company_login():
    if not session.get("is_admin"):
        c = _find_company_by_id(session.get("company_id", ""))
        if not (c and c.get("is_admin")):
            return jsonify({"error": "権限がありません"}), 403
        session["is_admin"] = True
    req_data  = request.get_json(force=True, silent=True) or {}
    cid       = req_data.get("id", "")
    new_email = req_data.get("email", "").strip().lower()
    new_pw    = req_data.get("password", "")
    confirm   = req_data.get("confirm", "")
    if not new_email or "@" not in new_email:
        return jsonify({"error": "有効なメールアドレスを入力してください"}), 400
    if new_pw and len(new_pw) < 6:
        return jsonify({"error": "パスワードは6文字以上にしてください"}), 400
    if new_pw and new_pw != confirm:
        return jsonify({"error": "パスワードが一致しません"}), 400
    # 別アカウントと重複チェック
    existing = _find_company_by_email(new_email)
    if existing and existing["id"] != cid:
        return jsonify({"error": "このメールアドレスはすでに使用されています"}), 400
    data = _load_auth_data()
    for c in data["companies"]:
        if c["id"] == cid:
            c["email"] = new_email
            if new_pw:
                c["password_hash"] = generate_password_hash(new_pw)
            break
    else:
        return jsonify({"error": "アカウントが見つかりません"}), 404
    _save_auth_data(data)
    return jsonify({"ok": True, "email": new_email})

@app.route("/api/admin/delete-company", methods=["POST"])
def api_delete_company():
    if not session.get("is_admin"):
        c = _find_company_by_id(session.get("company_id", ""))
        if not (c and c.get("is_admin")):
            return jsonify({"error": "権限がありません"}), 403
        session["is_admin"] = True
    req_data = request.get_json(force=True, silent=True) or {}
    cid = req_data.get("id", "")
    if cid == session.get("company_id"):
        return jsonify({"error": "自分自身のアカウントは削除できません"}), 400
    data = _load_auth_data()
    data["companies"] = [c for c in data["companies"] if c["id"] != cid]
    _save_auth_data(data)
    return jsonify({"ok": True})

# ========================================
# 設定管理
# ========================================

DEFAULT_SETTINGS = {
    "fiscal_year_start_month": 4,   # 4月始まり
    "company_name": "",
}

def load_settings() -> dict:
    path = os.path.join(_cdir(), "settings.json")
    if not os.path.exists(path):
        return dict(DEFAULT_SETTINGS)
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    return {**DEFAULT_SETTINGS, **s}

def save_settings(settings: dict):
    with open(os.path.join(_cdir(), "settings.json"), "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)

# ========================================
# 月次履歴管理
# ========================================

def load_history_list() -> list:
    """保存済み月次履歴の一覧（新しい順）を返す"""
    hd = _hdir()
    files = sorted([f for f in os.listdir(hd) if f.endswith(".json")], reverse=True)
    result = []
    for f in files:
        try:
            with open(os.path.join(hd, f), encoding="utf-8") as fp:
                result.append(json.load(fp))
        except Exception:
            pass
    return result

def load_history(year_month: str) -> dict | None:
    path = os.path.join(_hdir(), f"{year_month}.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_history(year_month: str, data: dict):
    with open(os.path.join(_hdir(), f"{year_month}.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_prev_year_month() -> str:
    """前月の YYYY-MM 文字列を返す"""
    from datetime import timedelta
    first = date.today().replace(day=1)
    return (first - timedelta(days=1)).strftime("%Y-%m")

def get_current_year_month() -> str:
    return date.today().strftime("%Y-%m")

def _build_history_snapshot(year_month: str) -> dict | None:
    """現在の last_result + meta から月次スナップショットを構築する"""
    result = _load_result()
    if not result:
        return None
    meta = load_meta()

    def apply_meta(lst):
        for b in lst:
            bid = b.get("請求書ID", "")
            m = meta.get(bid, {})
            b["担当者"]          = m.get("担当者", b.get("担当者", ""))
            b["メモ_手動"]       = m.get("メモ", b.get("メモ_手動", ""))
            b["着金日_手動"]     = m.get("着金日_手動", b.get("着金日_手動", ""))
            b["着金金額_手動"]   = m.get("着金金額_手動", b.get("着金金額_手動", 0))
            b["入金予定日_手動"] = m.get("入金予定日_手動", b.get("入金予定日_手動", ""))

    seikyu_raw   = result.get("seikyu_kakunin", [])
    seikyu_paid  = [b for b in seikyu_raw if meta.get(b.get("請求書ID",""), {}).get("着金日_手動")]
    seikyu_unpaid = [b for b in seikyu_raw if not meta.get(b.get("請求書ID",""), {}).get("着金日_手動")]

    # result["unpaid"] は overdue+upcoming の全体集合なので重複になる → カテゴリ別リストのみ使用
    unpaid_all = (result.get("overdue", []) + seikyu_unpaid +
                  result.get("draft_overdue", []) + result.get("ichiji_hokan", []) +
                  result.get("upcoming", []))
    # 請求書IDで重複除去（念のため）
    seen_ids = set()
    deduped = []
    for b in unpaid_all:
        bid = b.get("請求書ID", "")
        if bid and bid in seen_ids:
            continue
        if bid:
            seen_ids.add(bid)
        deduped.append(b)
    unpaid_all = deduped

    paid_all   = result.get("paid", []) + seikyu_paid

    apply_meta(unpaid_all)
    apply_meta(paid_all)

    return {
        "year_month":   year_month,
        "confirmed_at": datetime.now().isoformat(),
        "summary": {
            "unpaid_count": len(unpaid_all),
            "unpaid_total": int(sum(b.get("請求金額", 0) for b in unpaid_all)),
            "paid_count":   len(paid_all),
            "paid_total":   int(sum(b.get("請求金額", 0) for b in paid_all)),
        },
        "unpaid": _clean_items(unpaid_all),
        "paid":   _clean_items(paid_all),
    }

def _generate_history_excel(history: dict) -> str:
    """月次履歴のExcelを生成してパスを返す"""
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side

    def thin_border():
        s = Side(style="thin")
        return Border(left=s, right=s, top=s, bottom=s)

    def hdr(ws, r, c, val, bg, fc="FFFFFF"):
        cell = ws.cell(row=r, column=c, value=val)
        cell.fill = PatternFill("solid", fgColor=bg)
        cell.font = Font(bold=True, color=fc)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border()
        return cell

    def dat(ws, r, c, val, bg=None, fmt=None, bold=False):
        cell = ws.cell(row=r, column=c, value=val)
        if bg:
            cell.fill = PatternFill("solid", fgColor=bg)
        if fmt:
            cell.number_format = fmt
        cell.font = Font(bold=bold)
        cell.border = thin_border()
        return cell

    ym   = history["year_month"]
    summ = history["summary"]
    wb   = openpyxl.Workbook()

    # ---- サマリーシート ----
    ws = wb.active
    ws.title = "サマリー"
    ws.column_dimensions["A"].width = 20
    ws.column_dimensions["B"].width = 20

    hdr(ws, 1, 1, f"{ym} 月次確定レポート", "1F3864")
    ws.merge_cells("A1:B1")
    rows = [
        ("未入金件数",   summ["unpaid_count"]),
        ("未入金総額",   summ["unpaid_total"]),
        ("入金確認済み件数", summ["paid_count"]),
        ("入金確認済み総額", summ["paid_total"]),
        ("確定日時",     history.get("confirmed_at", "")[:19].replace("T", " ")),
    ]
    for i, (label, val) in enumerate(rows, start=2):
        dat(ws, i, 1, label, bold=True)
        cell = dat(ws, i, 2, val)
        if isinstance(val, int):
            cell.number_format = '#,##0'

    # ---- 未入金シート ----
    ws2 = wb.create_sheet("未入金")
    cols = ["取引先名", "請求番号", "件名", "担当者", "請求日", "支払期限", "請求金額", "メモ"]
    for c, col in enumerate(cols, 1):
        hdr(ws2, 1, c, col, "C00000")
        ws2.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 18
    ws2.column_dimensions["C"].width = 30
    ws2.column_dimensions["H"].width = 25

    for r, b in enumerate(history.get("unpaid", []), start=2):
        bg = "FCE4D6"
        dat(ws2, r, 1, b.get("取引先名", ""),  bg)
        dat(ws2, r, 2, b.get("請求番号", ""),  bg)
        dat(ws2, r, 3, b.get("件名", ""),      bg)
        dat(ws2, r, 4, b.get("担当者", ""),    bg)
        dat(ws2, r, 5, b.get("請求日", ""),    bg)
        dat(ws2, r, 6, b.get("支払期限", ""),  bg)
        dat(ws2, r, 7, b.get("請求金額", 0),   bg, '#,##0')
        dat(ws2, r, 8, b.get("メモ_手動", ""), bg)

    # ---- 入金確認済みシート ----
    ws3 = wb.create_sheet("入金確認済み")
    cols3 = ["取引先名", "請求番号", "件名", "担当者", "請求日", "支払期限", "請求金額", "着金日", "着金金額", "メモ"]
    for c, col in enumerate(cols3, 1):
        hdr(ws3, 1, c, col, "375623")
        ws3.column_dimensions[openpyxl.utils.get_column_letter(c)].width = 16
    ws3.column_dimensions["C"].width = 30

    for r, b in enumerate(history.get("paid", []), start=2):
        bg = "E2EFDA"
        dat(ws3, r, 1, b.get("取引先名", ""),       bg)
        dat(ws3, r, 2, b.get("請求番号", ""),       bg)
        dat(ws3, r, 3, b.get("件名", ""),           bg)
        dat(ws3, r, 4, b.get("担当者", ""),         bg)
        dat(ws3, r, 5, b.get("請求日", ""),         bg)
        dat(ws3, r, 6, b.get("支払期限", ""),       bg)
        dat(ws3, r, 7, b.get("請求金額", 0),        bg, '#,##0')
        dat(ws3, r, 8, b.get("着金日_手動", ""),    bg)
        dat(ws3, r, 9, b.get("着金金額_手動", 0),   bg, '#,##0')
        dat(ws3, r,10, b.get("メモ_手動", ""),      bg)

    output_dir = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"月次履歴_{ym}.xlsx")
    wb.save(path)
    return path

# ========================================
# 請求書メタデータ管理（担当者・メモ・手動着金）
# ========================================

def load_meta() -> dict:
    path = os.path.join(_cdir(), "invoice_meta.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def save_meta(meta: dict):
    with open(os.path.join(_cdir(), "invoice_meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_company_tantou() -> dict:
    """
    取引先マスタを読み込む。
    現行形式: {"会社名": {"担当者": "...", "振込名義": ["name1", "name2"]}}
    旧形式（文字列）: {"会社名": "担当者名"} → 自動的に担当者として扱う
    旧形式（個人名）: {"会社名": {"担当者": "...", "個人名": "..."}} → 振込名義に移行
    """
    path = os.path.join(_cdir(), "company_tantou.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _ensure_dict(mapping: dict, company: str) -> dict:
    """取引先エントリを dict 形式に統一して返す（破壊的変更）"""
    val = mapping.get(company)
    if isinstance(val, dict):
        # 旧形式 "個人名" (str) → "振込名義" (list) に移行
        if "個人名" in val and "振込名義" not in val:
            old_name = val.pop("個人名", "")
            val["振込名義"] = [old_name] if old_name else []
        val.setdefault("振込名義", [])
        val.setdefault("担当者", "")
        return val
    elif isinstance(val, str):
        # 旧形式: 文字列 = 担当者
        entry = {"担当者": val, "振込名義": []}
        mapping[company] = entry
        return entry
    else:
        entry = {"担当者": "", "振込名義": []}
        mapping[company] = entry
        return entry


def _get_tantou(mapping: dict, company: str) -> str:
    """取引先マスタから担当者名を返す（旧形式・新形式両対応）"""
    val = mapping.get(company)
    if val is None:
        return ""
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        return val.get("担当者", "")
    return ""


def _get_furikomi_list(mapping: dict, company: str) -> list:
    """取引先マスタから振込名義リストを返す"""
    val = mapping.get(company)
    if not isinstance(val, dict):
        return []
    # 旧 "個人名" (str) も含める
    names = list(val.get("振込名義", []))
    old = val.get("個人名", "")
    if old and old not in names:
        names.insert(0, old)
    return names


def _get_kojinmei(mapping: dict, company: str) -> str:
    """後方互換: 振込名義の先頭を返す（matcher.py用）"""
    lst = _get_furikomi_list(mapping, company)
    return lst[0] if lst else ""


def _set_tantou(mapping: dict, company: str, tantou: str):
    """取引先マスタの担当者をセット"""
    entry = _ensure_dict(mapping, company)
    entry["担当者"] = tantou


def _set_kojinmei(mapping: dict, company: str, kojinmei: str):
    """後方互換: 振込名義の先頭をセット"""
    entry = _ensure_dict(mapping, company)
    lst = entry["振込名義"]
    if kojinmei and kojinmei not in lst:
        lst.insert(0, kojinmei)
    elif not kojinmei and lst:
        lst.pop(0)


def _add_furikomi(mapping: dict, company: str, name: str):
    """振込名義を追加（重複は無視）"""
    if not name:
        return
    entry = _ensure_dict(mapping, company)
    if name not in entry["振込名義"]:
        entry["振込名義"].append(name)


def _remove_furikomi(mapping: dict, company: str, name: str):
    """振込名義を削除"""
    val = mapping.get(company)
    if isinstance(val, dict) and name in val.get("振込名義", []):
        val["振込名義"].remove(name)


def save_company_tantou(mapping: dict):
    with open(os.path.join(_cdir(), "company_tantou.json"), "w", encoding="utf-8") as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


def apply_auto_tantou(billings: list, meta: dict) -> list:
    """
    担当者が未設定の請求書に、同じ取引先名で登録済みの担当者を自動セットする。
    meta（請求書IDベース）→ 取引先名ベースのマップも参照。
    """
    company_tantou = load_company_tantou()
    for b in billings:
        if b.get("担当者"):
            continue  # すでに設定済みはスキップ
        company = b.get("取引先名", "").strip()
        if not company:
            continue
        tantou = _get_tantou(company_tantou, company)
        if tantou:
            b["担当者"] = tantou
    return billings

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

# まとめて再確認 バックグラウンド状態管理
_recheck_all_status = {"running": False, "result": None, "error": None, "error_type": None}
_recheck_all_lock   = threading.Lock()

def load_deleted_drafts() -> set:
    path = os.path.join(_cdir(), "deleted_drafts.json")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return set(json.load(f))

def save_deleted_drafts(ids: set):
    with open(os.path.join(_cdir(), "deleted_drafts.json"), "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False)

def load_deleted_seikyu() -> set:
    path = os.path.join(_cdir(), "deleted_seikyu.json")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        return set(json.load(f))

def save_deleted_seikyu(ids: set):
    with open(os.path.join(_cdir(), "deleted_seikyu.json"), "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False)


def load_recheck_records() -> list:
    path = os.path.join(_cdir(), "recheck_records.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_recheck_records(records: list):
    with open(os.path.join(_cdir(), "recheck_records.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def load_furikomi_unconfirmed() -> list:
    """振込名義未確認リスト（振込名義未登録顧客の候補入金データ）"""
    path = os.path.join(_cdir(), "furikomi_unconfirmed.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_furikomi_unconfirmed(records: list):
    with open(os.path.join(_cdir(), "furikomi_unconfirmed.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def load_accounting_deals() -> list:
    """アップロードされたMF会計CSVの仕訳データを読み込む"""
    path = os.path.join(_cdir(), "accounting_deals.json")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_accounting_deals(deals: list):
    with open(os.path.join(_cdir(), "accounting_deals.json"), "w", encoding="utf-8") as f:
        json.dump(deals, f, ensure_ascii=False, indent=2)


def parse_mf_accounting_csv(file_content: bytes) -> list:
    """
    MFクラウド会計の仕訳帳CSVをパースして照合用フォーマットに変換する。
    対応フォーマット:
      日付, 借方科目, ..., 借方金額, ..., 摘要, ..., MF仕訳ID
    """
    import csv, io, re as _re

    # エンコーディング自動判定（Shift-JIS / UTF-8-BOM）
    for enc in ("utf-8-sig", "shift_jis", "cp932", "utf-8"):
        try:
            text = file_content.decode(enc)
            break
        except Exception:
            text = None
    if not text:
        raise ValueError("CSVのエンコーディングを判定できませんでした")

    reader = csv.DictReader(io.StringIO(text))
    deals = []
    for i, row in enumerate(reader):
        # 日付
        date_raw = row.get("日付", "").strip()
        date_str = ""
        if date_raw:
            date_str = date_raw.replace("/", "-")
            if len(date_str) == 8 and "-" not in date_str:
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"

        # 借方金額（入金額として扱う）
        amt_str = row.get("借方金額", "0").strip().replace(",", "")
        try:
            amount = abs(int(float(amt_str))) if amt_str else 0
        except Exception:
            amount = 0

        # 取引先・摘要
        partner = row.get("取引先", row.get("取引先名", "")).strip()
        remark  = row.get("摘要", row.get("備考", row.get("description", ""))).strip()

        # 借方科目
        account = row.get("借方科目", "").strip()

        # 仕訳ID（MF仕訳ID列が無ければ行番号で代替）
        jid = row.get("MF仕訳ID", row.get("仕訳ID", "")).strip() or f"csv_{i}"

        if not date_str or amount == 0:
            continue

        deals.append({
            "取引ID":   jid,
            "着金日":   date_str,
            "入金金額": amount,
            "取引先名": partner,
            "備考":     remark,
            "科目":     account,
            "_matched": False,
        })

    return deals

def _is_delivered(b: dict) -> bool:
    """顧客への送付が確認されている（DL・メール・郵送のいずれか）"""
    return (
        bool(b.get("DL済み", False)) or
        b.get("メール状態") != "未送信" or
        b.get("送付状態") != "未郵送"
    )

def _is_draft_invoice(b: dict) -> bool:
    """下書き（顧客未着）: DL・メール・郵送のいずれも行われていない"""
    return not _is_delivered(b)


def _run_check(invoice_from=None, invoice_to=None, due_from=None, due_to=None, company_id=None):
    """MF請求書ステータス＋手動確認のみで未入金を判定する（MF会計照合なし）"""
    # スレッドローカルに会社IDをセット（sessionはスレッド内で使えないため）
    if company_id:
        _thread_local.company_id = company_id
    try:
        _update_status(running=True, error=None, progress=5, message="請求書データを取得中...")
        try:
            auth.get_access_token("invoice", company_id or get_company_id())
        except Exception as e:
            raise RuntimeError(f"MFクラウド請求書の認証が必要です: {e}")

        cid = company_id or get_company_id()
        all_billings = get_all_billings(company_id=cid)
        if not all_billings:
            raise RuntimeError("請求書データが0件でした。APIの応答を確認してください。")

        print(f"[取得] 請求書 {len(all_billings)}件")
        _update_status(progress=50, message=f"請求書 {len(all_billings)}件 取得完了。分類中...")

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
            b["解消済み"]      = m.get("解消済み", False)

        all_billings = apply_auto_tantou(all_billings, meta)

        # 日付フィルタ（支払期限ベース、未設定は請求日にフォールバック）
        def in_range(b):
            d = b.get("支払期限", "") or b.get("請求日", "")
            f = due_from or invoice_from
            t = due_to   or invoice_to
            if f and d and d < f:
                return False
            if t and d and d > t:
                return False
            return True

        filtered = [b for b in all_billings if in_range(b)]

        # 請求金額0円を除外（テスト・内部用の無効請求書）
        filtered = [b for b in filtered if (b.get("請求金額") or 0) > 0]

        # 分類
        # ① MF請求書が入金済み → 入金確認済み（MF）
        # ② MF未入金 かつ 手動着金日あり → 入金確認済み（手動）
        # ③ MF未入金 かつ 手動着金日なし → 未入金
        paid_mf     = [b for b in filtered if b["入金状態"] in PAID_STATUSES]
        paid_manual = [b for b in filtered
                       if b["入金状態"] in UNPAID_STATUSES and b.get("着金日_手動")]
        unpaid      = [b for b in filtered
                       if b["入金状態"] in UNPAID_STATUSES and not b.get("着金日_手動")]

        all_paid = paid_mf + paid_manual

        # 未入金を期限超過/期日前に分類
        all_overdue = [b for b in unpaid if b.get("支払期限") and b["支払期限"] < today_str]
        upcoming    = sorted(
            [b for b in unpaid if not b.get("支払期限") or b["支払期限"] >= today_str],
            key=lambda x: x.get("支払期限", ""))

        # 期限超過を4分類
        # ① メモ入力あり → 一時保管（毎月要確認）--- 他のタブには出さない
        # ② MFで「未入金」明示 → 未収
        # ③ MFで「未設定」かつ送付済み → 請求済みか確認
        # ④ MFで「未設定」かつ未送付 → 下書き（期限超過）
        deleted_draft_ids  = load_deleted_drafts()
        deleted_seikyu_ids = load_deleted_seikyu()

        # 未収解消済み：解消済みフラグあり（メモは未収タブに残す）
        ichiji_hokan = sorted(
            [b for b in all_overdue if b.get("解消済み")],
            key=lambda x: x.get("支払期限", ""))
        ichiji_ids = {b["請求書ID"] for b in ichiji_hokan}

        overdue = sorted(
            [b for b in all_overdue
             if b.get("入金状態") == "未入金" and b["請求書ID"] not in ichiji_ids],
            key=lambda x: x.get("支払期限", ""))
        seikyu_kakunin = sorted(
            [b for b in all_overdue
             if b.get("入金状態") == "未設定" and _is_delivered(b)
             and b["請求書ID"] not in ichiji_ids
             and b.get("請求書ID") not in deleted_seikyu_ids],
            key=lambda x: x.get("支払期限", ""))
        draft_overdue = sorted(
            [b for b in all_overdue
             if b.get("入金状態") == "未設定" and _is_draft_invoice(b)
             and b["請求書ID"] not in ichiji_ids
             and b.get("請求書ID") not in deleted_draft_ids],
            key=lambda x: x.get("支払期限", ""))

        result = {
            "paid":            all_paid,
            "unpaid":          unpaid,
            "overdue":         overdue,
            "seikyu_kakunin":  seikyu_kakunin,
            "draft_overdue":   draft_overdue,
            "ichiji_hokan":    ichiji_hokan,
            "upcoming":        upcoming,
            "total":           len(all_paid) + len(unpaid),
            "invoice_from":    invoice_from or "",
            "invoice_to":      invoice_to   or "",
        }

        print(f"[分類] 未入金={len(unpaid)}件（"
              f"未収:{len(overdue)} 請求済確認:{len(seikyu_kakunin)} 下書き:{len(draft_overdue)} "
              f"一時保管:{len(ichiji_hokan)} 期日前:{len(upcoming)}）"
              f" 入金済み={len(all_paid)}件（MF:{len(paid_mf)} 手動:{len(paid_manual)}）")

        _update_status(progress=85, message="Excelレポートを生成中...")
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
    finally:
        _thread_local.company_id = None


def _clean_items(items: list) -> list:
    return [{k: v for k, v in item.items() if k != "_raw"} for item in items]


def _save_result(result: dict, output_path: str):
    data = {
        "saved_at":         datetime.now().isoformat(),
        "output_path":      output_path,
        "unpaid":           _clean_items(result["unpaid"]),
        "overdue":          _clean_items(result["overdue"]),
        "seikyu_kakunin":   _clean_items(result.get("seikyu_kakunin", [])),
        "draft_overdue":    _clean_items(result.get("draft_overdue", [])),
        "ichiji_hokan":     _clean_items(result.get("ichiji_hokan", [])),
        "upcoming":         _clean_items(result["upcoming"]),
        "paid":             _clean_items(result["paid"]),
        "total":            result["total"],
        "invoice_from":     result.get("invoice_from", ""),
        "invoice_to":       result.get("invoice_to", ""),
    }
    with open(os.path.join(_cdir(), "last_result.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_result() -> dict | None:
    path = os.path.join(_cdir(), "last_result.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ========================================
# ルーティング — ダッシュボード
# ========================================

def _load_admin_aggregate() -> dict:
    """全一般会社のlast_resultを集約して返す"""
    auth_data = _load_auth_data()
    agg = {
        "overdue": [], "seikyu_kakunin": [], "draft_overdue": [],
        "ichiji_hokan": [], "upcoming": [], "paid": [],
        "has_data": False,
        "company_count": 0,
    }

    for c in auth_data.get("companies", []):
        if c.get("is_admin"):
            continue
        cid = c["id"]

        # 会社名（settings.json から取得、なければメール）
        settings_path = os.path.join(DATA_DIR, cid, "settings.json")
        comp_name = c["email"]
        if os.path.exists(settings_path):
            try:
                with open(settings_path, encoding="utf-8") as f:
                    s = json.load(f)
                comp_name = s.get("company_name") or c["email"]
            except Exception:
                pass

        # 最終照合結果
        result_path = os.path.join(DATA_DIR, cid, "last_result.json")
        if not os.path.exists(result_path):
            continue
        try:
            with open(result_path, encoding="utf-8") as f:
                result = json.load(f)
        except Exception:
            continue

        # メタデータ
        meta = {}
        meta_path = os.path.join(DATA_DIR, cid, "invoice_meta.json")
        if os.path.exists(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        agg["has_data"] = True
        agg["company_count"] += 1

        for cat in ["overdue", "seikyu_kakunin", "draft_overdue", "ichiji_hokan", "upcoming"]:
            for b in result.get(cat, []):
                bid = b.get("請求書ID", "")
                m = meta.get(bid, {})
                item = dict(b)
                item["担当者"]          = m.get("担当者", b.get("担当者", ""))
                item["メモ_手動"]       = m.get("メモ", b.get("メモ_手動", ""))
                item["着金日_手動"]     = m.get("着金日_手動", b.get("着金日_手動", ""))
                item["着金金額_手動"]   = m.get("着金金額_手動", b.get("着金金額_手動", 0))
                item["入金予定日_手動"] = m.get("入金予定日_手動", b.get("入金予定日_手動", ""))
                item["_company_name"]   = comp_name
                agg[cat].append(item)

        # 入金確認済み（seikyu_kakuninの着金済みも含む）
        seikyu_raw = result.get("seikyu_kakunin", [])
        paid_all = result.get("paid", []) + [b for b in seikyu_raw if meta.get(b.get("請求書ID",""), {}).get("着金日_手動")]
        for b in paid_all:
            bid = b.get("請求書ID", "")
            m = meta.get(bid, {})
            item = dict(b)
            item["担当者"]          = m.get("担当者", b.get("担当者", ""))
            item["メモ_手動"]       = m.get("メモ", b.get("メモ_手動", ""))
            item["着金日_手動"]     = m.get("着金日_手動", b.get("着金日_手動", ""))
            item["着金金額_手動"]   = m.get("着金金額_手動", b.get("着金金額_手動", 0))
            item["入金予定日_手動"] = m.get("入金予定日_手動", b.get("入金予定日_手動", ""))
            item["_company_name"]   = comp_name
            agg["paid"].append(item)

    return agg


@app.route("/")
def dashboard():
    settings  = load_settings()
    today_str = datetime.now().strftime("%Y-%m-%d")

    start_month = settings["fiscal_year_start_month"]
    fiscal_year = request.args.get("year", type=int)
    if fiscal_year is None:
        fiscal_year = get_current_fiscal_year(start_month)
    prev_year = fiscal_year - 1
    next_year = fiscal_year + 1
    fy_from, fy_to = get_fiscal_year_range(fiscal_year, start_month)
    prev_ym = get_prev_year_month()

    # ── 管理者が自社（管理者アカウント）を閲覧中 → 全社集約ビュー ──
    own_cid = session.get("company_id", "")
    viewing_cid_now = get_company_id()
    show_admin_aggregate = bool(session.get("is_admin")) and (viewing_cid_now == own_cid)

    if show_admin_aggregate:
        agg = _load_admin_aggregate()
        return render_template(
            "admin_dashboard.html",
            agg=agg,
            overdue=agg["overdue"],
            seikyu_kakunin=agg["seikyu_kakunin"],
            draft_overdue=agg["draft_overdue"],
            ichiji_hokan=agg["ichiji_hokan"],
            upcoming=agg["upcoming"],
            paid_fy=agg["paid"],
            settings=settings,
            fiscal_year=fiscal_year,
            prev_year=prev_year,
            next_year=next_year,
            fy_from=fy_from,
            fy_to=fy_to,
            today=today_str,
        )

    # ── 通常ビュー（個別会社） ──
    auth_invoice     = auth.is_authenticated("invoice", get_company_id())
    auth_accounting  = auth.is_authenticated("accounting", get_company_id())
    result           = _load_result()
    meta             = load_meta()

    show_history_popup = (
        date.today().day <= 7 and
        load_history(prev_ym) is None and
        settings.get("history_popup_dismissed") != prev_ym
    )

    def in_fy(b):
        d = b.get("請求日") or b.get("支払期限") or ""
        return fy_from <= d <= fy_to

    if result:
        company_tantou = load_company_tantou()
        for lst in [result.get("unpaid",[]), result.get("overdue",[]),
                    result.get("upcoming",[]), result.get("paid",[]),
                    result.get("seikyu_kakunin",[]), result.get("ichiji_hokan",[]),
                    result.get("draft_overdue",[])]:
            for b in lst:
                bid = b.get("請求書ID","")
                m = meta.get(bid, {})
                b["担当者"]          = m.get("担当者", b.get("担当者",""))
                b["メモ_手動"]       = m.get("メモ", b.get("メモ_手動",""))
                # 着金日_手動 / 着金金額_手動 はメタを優先（JSONの焼き込み値は無視）
                b["着金日_手動"]     = m.get("着金日_手動", "")
                b["着金金額_手動"]   = m.get("着金金額_手動", 0)
                b["入金予定日_手動"] = m.get("入金予定日_手動", b.get("入金予定日_手動", ""))
                b["部分入金"]        = m.get("部分入金", False)
                b["残額"]            = m.get("残額", 0)
                b["入金済金額"]      = m.get("入金済金額", 0)
                b["解消済み"]        = m.get("解消済み", False)
                company = b.get("取引先名", "").strip()
                if not b.get("担当者") and company:
                    tantou = _get_tantou(company_tantou, company)
                    if tantou:
                        b["担当者"] = tantou
                # 振込名義リスト（meta の 個人名 + company_tantou の振込名義を合算）
                furikomi_meta = m.get("個人名", "") or ""
                furikomi_list = _get_furikomi_list(company_tantou, company)
                if furikomi_meta and furikomi_meta not in furikomi_list:
                    furikomi_list = [furikomi_meta] + furikomi_list
                b["個人名"]         = furikomi_list[0] if furikomi_list else ""
                b["振込名義リスト"]  = furikomi_list

        seikyu_raw     = result.get("seikyu_kakunin", [])
        seikyu_moved   = [b for b in seikyu_raw if b.get("着金日_手動")]
        seikyu_kakunin = [b for b in seikyu_raw if not b.get("着金日_手動")]

        # overdue + ichiji_hokan を統合して現在のメタで再分類
        all_overdue_pool = result.get("overdue", []) + result.get("ichiji_hokan", [])
        overdue_moved  = [b for b in all_overdue_pool if b.get("着金日_手動")]
        ichiji_hokan   = sorted([b for b in all_overdue_pool
                                  if b.get("解消済み") and not b.get("着金日_手動")],
                                 key=lambda x: x.get("支払期限", ""))
        ichiji_ids_d   = {b["請求書ID"] for b in ichiji_hokan}
        overdue        = sorted([b for b in all_overdue_pool
                                  if not b.get("着金日_手動") and b["請求書ID"] not in ichiji_ids_d],
                                 key=lambda x: x.get("支払期限", ""))
        paid_all       = result.get("paid", []) + seikyu_moved + overdue_moved
        draft_overdue = result.get("draft_overdue", [])
        upcoming      = [b for b in result.get("upcoming", []) if in_fy(b)]
        paid_fy       = [b for b in paid_all if in_fy(b)]

    else:
        overdue = seikyu_kakunin = draft_overdue = ichiji_hokan = upcoming = paid_fy = []

    recheck_records       = [r for r in load_recheck_records() if not r.get("deleted")]
    furikomi_unconfirmed  = [r for r in load_furikomi_unconfirmed() if not r.get("deleted")]

    return render_template(
        "dashboard.html",
        auth_invoice=auth_invoice,
        auth_accounting=auth_accounting,
        result=result,
        overdue=overdue,
        seikyu_kakunin=seikyu_kakunin,
        draft_overdue=draft_overdue,
        ichiji_hokan=ichiji_hokan,
        upcoming=upcoming,
        paid_fy=paid_fy,
        status=dict(_status),
        today=today_str,
        settings=settings,
        fiscal_year=fiscal_year,
        prev_year=prev_year,
        next_year=next_year,
        fy_from=fy_from,
        fy_to=fy_to,
        show_history_popup=show_history_popup,
        prev_ym=prev_ym,
        current_ym=get_current_year_month(),
        history_list=load_history_list(),
        recheck_records=recheck_records,
        furikomi_unconfirmed=furikomi_unconfirmed,
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

    # 請求書発行月（YYYY-MM 形式 → YYYY-MM-01 / YYYY-MM-末日 に変換）
    invoice_from_ym = request.form.get("invoice_from_ym") or ""
    invoice_to_ym   = request.form.get("invoice_to_ym")   or ""
    def ym_to_from(ym: str) -> str | None:
        if not ym:
            return None
        return f"{ym}-01"

    def ym_to_to(ym: str) -> str | None:
        import calendar
        if not ym:
            return None
        try:
            y, m = int(ym[:4]), int(ym[5:7])
            last = calendar.monthrange(y, m)[1]
            return f"{ym}-{last:02d}"
        except Exception:
            return None

    invoice_from = ym_to_from(invoice_from_ym)
    invoice_to   = ym_to_to(invoice_to_ym)

    # 未指定なら年度から自動設定
    if not invoice_from and not invoice_to:
        invoice_from, invoice_to = get_fiscal_year_range(fiscal_year, start_month)

    thread = threading.Thread(
        target=_run_check,
        args=(invoice_from, invoice_to, None, None, get_company_id()),
        daemon=True,
    )
    thread.start()
    return redirect(url_for("dashboard", year=fiscal_year))


@app.route("/api/status")
def api_status():
    with _status_lock:
        return jsonify(dict(_status))


@app.route("/api/version")
def api_version():
    import subprocess
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=os.path.dirname(__file__),
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        commit = "unknown"
    return jsonify({"commit": commit, "deployed_at": datetime.now().isoformat()})


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
                           auth_invoice=auth.is_authenticated("invoice", get_company_id()),
                           auth_accounting=auth.is_authenticated("accounting", get_company_id()),
                           current_email=session.get("email", ""))

@app.route("/api/update-credentials", methods=["POST"])
def update_credentials():
    """メールアドレス・パスワードの変更"""
    data        = request.get_json() or {}
    new_email   = data.get("email", "").strip()
    new_password = data.get("password", "")
    confirm     = data.get("confirm", "")
    current_pw  = data.get("current_password", "")

    company = _find_company_by_id(get_company_id())
    if not company:
        return jsonify({"error": "認証情報が設定されていません"}), 400
    if not check_password_hash(company["password_hash"], current_pw):
        return jsonify({"error": "現在のパスワードが違います"}), 400
    if not new_email or "@" not in new_email:
        return jsonify({"error": "有効なメールアドレスを入力してください"}), 400
    if new_password and len(new_password) < 6:
        return jsonify({"error": "パスワードは6文字以上にしてください"}), 400
    if new_password and new_password != confirm:
        return jsonify({"error": "新しいパスワードが一致しません"}), 400

    data = _load_auth_data()
    for c in data["companies"]:
        if c["id"] == get_company_id():
            c["email"] = new_email.strip().lower()
            if new_password:
                c["password_hash"] = generate_password_hash(new_password)
            break
    _save_auth_data(data)
    session["email"] = new_email.strip().lower()
    return jsonify({"ok": True})

# ========================================
# ルーティング — 請求書メタデータ編集
# ========================================

@app.route("/api/invoice/<invoice_id>/meta", methods=["GET", "POST"])
def invoice_meta(invoice_id):
    meta = load_meta()
    if request.method == "POST":
        data = request.get_json() or {}
        meta.setdefault(invoice_id, {})
        for key in ["担当者", "メモ", "着金日_手動", "着金金額_手動", "入金予定日_手動", "個人名", "解消済み"]:
            if key in data:
                meta[invoice_id][key] = data[key]
        save_meta(meta)

        # 担当者 or 個人名が設定された場合、取引先名マスタも更新
        tantou    = data.get("担当者", "").strip()
        kojinmei  = data.get("個人名", "").strip()
        if tantou or ("個人名" in data):
            # 請求書IDから取引先名を逆引き
            result = _load_result()
            company_name = ""
            if result:
                all_b = (result.get("unpaid", []) + result.get("paid", [])
                         + result.get("diff", []) + result.get("overdue", [])
                         + result.get("seikyu_kakunin", []) + result.get("upcoming", []))
                for b in all_b:
                    if b.get("請求書ID") == invoice_id:
                        company_name = b.get("取引先名", "").strip()
                        break
            if company_name:
                mapping = load_company_tantou()
                if tantou:
                    _set_tantou(mapping, company_name, tantou)
                if "個人名" in data:
                    _set_kojinmei(mapping, company_name, kojinmei)
                save_company_tantou(mapping)

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
        token = auth.get_access_token("invoice", get_company_id())
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

    return jsonify(results)



@app.route("/api/debug-check")
def debug_check():
    try:
        cid = get_company_id()
        token = auth.get_access_token("invoice", cid)
        billings = get_all_billings(company_id=cid)
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
    url, state = auth.get_auth_url(service_name, get_company_id())
    # Gunicorn複数ワーカー対応: stateをFlask sessionに保存
    session["oauth_state"]   = state
    session["oauth_service"] = service_name
    session["oauth_cid"]     = get_company_id()
    return redirect(url)


@app.route("/oauth/callback/<service_name>")
def oauth_callback(service_name):
    if service_name not in ("invoice", "accounting"):
        return "不正なサービス名", 400
    code  = request.args.get("code")
    state = request.args.get("state", "")
    error = request.args.get("error")
    if error:
        flash(f"認証がキャンセルされました: {error}")
        return redirect(url_for("settings_page"))
    if not code:
        flash("認可コードが取得できませんでした")
        return redirect(url_for("settings_page"))
    # Gunicorn複数ワーカー対応: Flask sessionからstate・service・company_idを取得
    expected_state   = session.pop("oauth_state",   "")
    stored_service   = session.pop("oauth_service", service_name)
    stored_cid       = session.pop("oauth_cid",     get_company_id())
    try:
        ok, _cid, actual_service = auth.handle_callback(
            stored_service, code, state,
            expected_state=expected_state,
            company_id=stored_cid,
        )
        if ok:
            name = "MFクラウド会計" if actual_service == "accounting" else "MFクラウド請求書"
            flash(f"{name}の認証が完了しました", "success")
        else:
            flash("認証に失敗しました（stateが一致しません）", "error")
    except Exception as e:
        flash(f"認証エラー: {e}", "error")
    return redirect(url_for("settings_page"))


@app.route("/oauth/revoke/<service_name>", methods=["POST"])
def oauth_revoke(service_name):
    if service_name not in ("invoice", "accounting"):
        return "不正なサービス名", 400
    auth.revoke_token(service_name, get_company_id())
    labels = {"invoice": "MFクラウド請求書", "accounting": "MFクラウド会計"}
    flash(f"{labels[service_name]}の認証を解除しました")
    return redirect(url_for("dashboard"))


# ========================================
# MFクラウド会計 — 個人名チェック
# ========================================

def _run_recheck_all(cid: str):
    """まとめて再確認をバックグラウンドで実行する"""
    # バックグラウンドスレッドでセッションが使えないため、thread_localに会社IDをセット
    _thread_local.company_id = cid

    import re as _re
    import uuid as _uuid
    import jaconv as _jc
    import requests
    from mf_accounting import get_deals, AccountingPeriodError

    def _norm(s: str) -> str:
        s = _jc.hira2kata(s.strip())
        s = _jc.h2z(s, kana=True, ascii=False, digit=False)
        s = _re.sub(r'[\s\u3000\-－　]', '', s).upper()
        return s

    def _norm_fuzzy(s: str) -> str:
        """類似マッチ用: 長音符(ー)も除去して比較"""
        s = _norm(s)
        s = s.replace('ー', '')
        return s

    try:
        result = _load_result()
        if not result:
            raise ValueError("先に請求書チェックを実行してください。")

        # 取得範囲: 過去2ヶ月（ボタン押下日から遡る）
        today = date.today()
        m2 = today.month - 2
        y2 = today.year
        if m2 <= 0:
            m2 += 12
            y2 -= 1
        fetch_from = f"{y2}-{m2:02d}-01"
        fetch_to   = today.strftime("%Y-%m-%d")

        # 過去2ヶ月を一括取得。会計期間またぎで400が返ったら警告ポップアップへ
        try:
            deals = get_deals(fetch_from, fetch_to, company_id=cid)
            print(f"[再確認] 仕訳: {len(deals)}件 ({fetch_from}〜{fetch_to})", flush=True)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 400:
                raise AccountingPeriodError(str(e)) from e
            raise

        overdue_list   = result.get("overdue", [])
        meta_all       = load_meta()
        company_tantou = load_company_tantou()

        recheck_records = load_recheck_records()
        existing_jids_rchk = {r.get("journal_id", r["id"]) for r in recheck_records}

        new_recheck = 0

        for billing in overdue_list:
            bid           = billing.get("請求書ID", "")
            partner_name  = billing.get("取引先名", "").strip()
            furikomi_meta = meta_all.get(bid, {}).get("個人名", "")
            furikomi_list = _get_furikomi_list(company_tantou, partner_name)
            if furikomi_meta and furikomi_meta not in furikomi_list:
                furikomi_list = [furikomi_meta] + furikomi_list
            if furikomi_list:
                for d in deals:
                    journal_id = str(d.get("取引ID", ""))
                    if journal_id in existing_jids_rchk:
                        continue
                    remark   = d.get("備考", "") or ""
                    remark_n = _norm(remark)
                    remark_f = _norm_fuzzy(remark)
                    matched  = False
                    similarity_flag     = False
                    similar_matched_name = ""
                    # 厳密マッチ
                    for name in furikomi_list:
                        if not name or len(name) < 2:
                            continue
                        name_n = _norm(name)
                        if (len(name_n) >= 2 and name_n in remark_n) or name in remark:
                            matched = True
                            break
                    # 厳密マッチ失敗時: 類似マッチ（長音符無視）
                    if not matched:
                        for name in furikomi_list:
                            if not name or len(name) < 2:
                                continue
                            name_f = _norm_fuzzy(name)
                            if len(name_f) >= 2 and name_f in remark_f:
                                matched = True
                                similarity_flag = True
                                similar_matched_name = name
                                break
                    if matched:
                        recheck_records.append({
                            "id":                     str(_uuid.uuid4()),
                            "journal_id":             journal_id,
                            "fetched_at":             datetime.now().isoformat(),
                            "fetched_for_invoice_id": bid,
                            "取引先名":               d.get("取引先名", ""),
                            "着金日":                 d.get("着金日", ""),
                            "入金金額":               d.get("入金金額", 0),
                            "備考":                   d.get("備考", ""),
                            "科目":                   d.get("科目", ""),
                            "memo":                   "",
                            "deleted":                False,
                            "linked_invoice_id":      None,
                            "linked_invoice_num":     None,
                            "linked_at":              None,
                            "similarity_flag":        similarity_flag,
                            "similar_matched_name":   similar_matched_name,
                        })
                        existing_jids_rchk.add(journal_id)
                        new_recheck += 1

        save_recheck_records(recheck_records)

        with _recheck_all_lock:
            _recheck_all_status["running"]    = False
            _recheck_all_status["error"]      = None
            _recheck_all_status["error_type"] = None
            _recheck_all_status["result"]     = {
                "ok":           True,
                "new_recheck":  new_recheck,
                "total_recheck": len([r for r in recheck_records if not r.get("deleted")]),
                "from_date":    fetch_from,
                "to_date":      fetch_to,
            }
    except AccountingPeriodError as e:
        print(f"[再確認] 会計期間エラー: {e}", flush=True)
        with _recheck_all_lock:
            _recheck_all_status["running"]    = False
            _recheck_all_status["error_type"] = "accounting_period"
            _recheck_all_status["error"]      = str(e)
            _recheck_all_status["result"]     = None
    except Exception as e:
        import traceback as _tb
        msg = f"{e}\n{_tb.format_exc()}"
        print(f"[再確認] エラー: {msg}", flush=True)
        with _recheck_all_lock:
            _recheck_all_status["running"]    = False
            _recheck_all_status["error"]      = msg
            _recheck_all_status["error_type"] = "general"
            _recheck_all_status["result"]     = None


@app.route("/api/overdue/recheck_all", methods=["POST"])
@login_required
def api_overdue_recheck_all():
    """
    未収リストの全件をまとめてMFクラウド会計と照合する（バックグラウンド実行）。
    """
    cid = get_company_id()
    if not auth.is_authenticated("accounting", cid):
        return jsonify({"error": "MFクラウド会計の連携が必要です。"}), 401

    with _recheck_all_lock:
        if _recheck_all_status["running"]:
            return jsonify({"error": "照合実行中です。しばらくお待ちください。"}), 409
        _recheck_all_status["running"] = True
        _recheck_all_status["result"]  = None
        _recheck_all_status["error"]   = None

    threading.Thread(target=_run_recheck_all, args=(cid,), daemon=True).start()
    return jsonify({"started": True})


@app.route("/api/overdue/recheck_all/status")
@login_required
def api_overdue_recheck_all_status():
    with _recheck_all_lock:
        return jsonify(dict(_recheck_all_status))


@app.route("/api/furikomi_unconfirmed/reset", methods=["POST"])
@login_required
def api_furikomi_unconfirmed_reset():
    """振込名義確認リストを全件クリアする（汚染データ除去用）"""
    save_furikomi_unconfirmed([])
    return jsonify({"ok": True})


@app.route("/api/furikomi_confirm/<record_id>/link", methods=["POST"])
@login_required
def api_furikomi_confirm_link(record_id):
    """
    振込名義確認タブの候補を確定する:
    1. 指定請求書に着金日/金額をセット（着金日_手動）
    2. 入力した振込名義を顧客リスト（company_tantou）に追加
    """
    data           = request.get_json(force=True, silent=True) or {}
    invoice_id     = data.get("invoice_id", "")
    invoice_num    = data.get("invoice_num", "")
    furikomi_name  = data.get("furikomi_name", "").strip()

    records = load_furikomi_unconfirmed()
    rec = next((r for r in records if r["id"] == record_id), None)
    if not rec:
        return jsonify({"error": "レコードが見つかりません"}), 404

    # 1. 請求書メタに着金情報を保存
    if invoice_id:
        meta = load_meta()
        if invoice_id not in meta:
            meta[invoice_id] = {}
        meta[invoice_id]["着金日_手動"]    = rec.get("着金日", "")
        meta[invoice_id]["着金金額_手動"]  = rec.get("入金金額", 0)
        save_meta(meta)

    # 2. 振込名義を顧客リストに追加
    if furikomi_name:
        partner = rec.get("suggested_partner", "")
        company_tantou = load_company_tantou()
        _set_kojinmei(company_tantou, partner, furikomi_name)
        save_company_tantou(company_tantou)

    # 3. レコードを確定済みにする
    rec["linked_invoice_id"]  = invoice_id
    rec["linked_invoice_num"] = invoice_num
    rec["linked_at"]          = datetime.now().isoformat()
    rec["furikomi_to_register"] = furikomi_name
    save_furikomi_unconfirmed(records)

    return jsonify({"ok": True})


@app.route("/api/furikomi_confirm/<record_id>/delete", methods=["POST"])
@login_required
def api_furikomi_confirm_delete(record_id):
    records = load_furikomi_unconfirmed()
    for r in records:
        if r["id"] == record_id:
            r["deleted"] = True
            break
    save_furikomi_unconfirmed(records)
    return jsonify({"ok": True})


@app.route("/api/debug/accounting-test", methods=["GET"])
@login_required
def api_debug_accounting_test():
    """MF会計API疎通テスト（診断用）"""
    import requests as _req
    cid = get_company_id()
    try:
        token = auth.get_access_token("accounting", cid)
    except Exception as e:
        return jsonify({"error": f"トークン取得失敗: {str(e)}"})
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    params = {"start_date": "2026-02-01", "end_date": "2026-04-22", "per_page": 1, "page": 1}
    try:
        resp = _req.get(
            "https://api-accounting.moneyforward.com/api/v3/journals",
            headers=headers, params=params, timeout=30
        )
        return jsonify({
            "status_code": resp.status_code,
            "request_url":  resp.url,
            "response_body": resp.text[:1000],
        })
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route("/api/accounting-kojinmei-check", methods=["POST"])
@login_required
def api_accounting_kojinmei_check():
    """
    未入金請求書の取引先の「個人名（振込人名）」を使って
    MFクラウド会計の仕訳データと照合する。

    Request JSON:
        from_date: str  照合開始日 YYYY-MM-DD
        to_date:   str  照合終了日 YYYY-MM-DD

    Response JSON:
        {
          "matched": [{請求書情報 + 会計仕訳情報}],
          "unmatched_count": int,
          "accounting_total": int,
        }
    """
    try:
        from mf_accounting import get_deals
    except ImportError as e:
        return jsonify({"error": f"mf_accounting モジュールが見つかりません: {e}"}), 500

    data      = request.get_json(force=True, silent=True) or {}
    from_date = data.get("from_date", "")
    to_date   = data.get("to_date", "")

    if not from_date or not to_date:
        return jsonify({"error": "from_date と to_date は必須です"}), 400

    cid = get_company_id()

    # 会計認証チェック
    if not auth.is_authenticated("accounting", cid):
        return jsonify({"error": "MFクラウド会計との連携が必要です。設定画面から連携してください。"}), 401

    # 現在の未入金一覧を取得
    result = _load_result()
    if not result:
        return jsonify({"error": "先に請求書チェックを実行してください。"}), 400

    meta           = load_meta()
    company_tantou = load_company_tantou()

    # 未入金の請求書を全カテゴリから集める
    unpaid_all = (
        result.get("overdue", []) +
        result.get("seikyu_kakunin", []) +
        result.get("upcoming", []) +
        result.get("ichiji_hokan", [])
    )

    # 振込名義を持つ請求書のみ絞り込む
    targets = []
    for b in unpaid_all:
        bid      = b.get("請求書ID", "")
        company  = b.get("取引先名", "").strip()
        # 振込名義リスト: invoice_meta + company_tantou
        furikomi_meta = meta.get(bid, {}).get("個人名", "")
        furikomi_list = _get_furikomi_list(company_tantou, company)
        if furikomi_meta and furikomi_meta not in furikomi_list:
            furikomi_list = [furikomi_meta] + furikomi_list
        if furikomi_list:
            targets.append({**b, "振込名義リスト": furikomi_list})

    if not targets:
        return jsonify({
            "matched":          [],
            "unmatched_count":  len(unpaid_all),
            "accounting_total": 0,
            "message":          "振込名義が登録されている未入金請求書がありません。顧客リストまたは編集ボタンから「振込名義」を登録してください。",
        })

    # MF会計から仕訳取得
    try:
        deals = get_deals(from_date, to_date, company_id=cid)
    except Exception as e:
        return jsonify({"error": f"MFクラウド会計からのデータ取得に失敗しました: {e}"}), 500

    # 振込名義リストの全名義でマッチング
    matched = []
    for b in targets:
        furikomi_list = b.get("振込名義リスト", [])
        matched_deal = None
        matched_name = ""
        for name in furikomi_list:
            deal = match_by_kojinmei(b, deals, name)
            if deal:
                matched_deal = deal
                matched_name = name
                deal["_matched"] = True
                break
        if matched_deal:
            matched.append({
                "請求書ID":      b.get("請求書ID", ""),
                "請求番号":      b.get("請求番号", ""),
                "取引先名":      b.get("取引先名", ""),
                "振込名義":      matched_name,
                "件名":          b.get("件名", ""),
                "担当者":        b.get("担当者", ""),
                "請求日":        b.get("請求日", ""),
                "支払期限":      b.get("支払期限", ""),
                "請求金額":      b.get("請求金額", 0),
                "着金日_会計":   matched_deal.get("着金日", ""),
                "着金金額_会計": matched_deal.get("入金金額", 0),
                "会計取引先名":  matched_deal.get("取引先名", ""),
                "会計備考":      matched_deal.get("備考", ""),
                "科目":          matched_deal.get("科目", ""),
            })

    return jsonify({
        "matched":          matched,
        "unmatched_count":  len(targets) - len(matched),
        "accounting_total": len(deals),
    })


# ========================================
# 顧客リスト（振込名義管理）
# ========================================

@app.route("/customers")
@login_required
def customers_page():
    """顧客リスト＋振込名義管理ページ"""
    return render_template(
        "customers.html",
        auth_invoice=auth.is_authenticated("invoice", get_company_id()),
        settings=load_settings(),
    )


@app.route("/api/customers", methods=["GET"])
@login_required
def api_customers_list():
    """
    顧客リストを返す。
    MF請求書の last_result と company_tantou をマージして全顧客を返す。
    """
    company_tantou = load_company_tantou()

    # MF請求書から顧客名一覧を収集
    invoice_companies: set[str] = set()
    result = _load_result()
    if result:
        for cat in ["unpaid", "overdue", "seikyu_kakunin", "upcoming", "paid",
                    "ichiji_hokan", "draft_overdue"]:
            for b in result.get(cat, []):
                c = b.get("取引先名", "").strip()
                if c:
                    invoice_companies.add(c)

    # company_tantou の顧客も追加
    all_companies = invoice_companies | set(company_tantou.keys())

    customers = []
    for name in sorted(all_companies):
        entry = _ensure_dict(company_tantou, name) if name in company_tantou else {"担当者": "", "振込名義": []}
        customers.append({
            "name":          name,
            "tantou":        entry.get("担当者", ""),
            "furikomi_list": entry.get("振込名義", []),
            "has_invoices":  name in invoice_companies,
        })

    return jsonify(customers)


@app.route("/api/customers/furikomi/add", methods=["POST"])
@login_required
def api_customers_furikomi_add():
    """振込名義を顧客に追加する（複数可）"""
    data    = request.get_json(force=True, silent=True) or {}
    company = data.get("company", "").strip()
    name    = data.get("furikomi_name", "").strip()
    if not company or not name:
        return jsonify({"error": "company と furikomi_name は必須です"}), 400
    mapping = load_company_tantou()
    _add_furikomi(mapping, company, name)
    save_company_tantou(mapping)
    return jsonify({"ok": True})


@app.route("/api/customers/furikomi/remove", methods=["POST"])
@login_required
def api_customers_furikomi_remove():
    """振込名義を顧客から削除する"""
    data    = request.get_json(force=True, silent=True) or {}
    company = data.get("company", "").strip()
    name    = data.get("furikomi_name", "").strip()
    if not company or not name:
        return jsonify({"error": "company と furikomi_name は必須です"}), 400
    mapping = load_company_tantou()
    _remove_furikomi(mapping, company, name)
    save_company_tantou(mapping)
    return jsonify({"ok": True})


@app.route("/api/customers/furikomi/bulk-add", methods=["POST"])
@login_required
def api_customers_furikomi_bulk_add():
    """振込名義を複数顧客に一括追加する（CSVインポート用）"""
    data  = request.get_json(force=True, silent=True) or {}
    items = data.get("items", [])  # [{company, furikomi_name}, ...]
    if not items:
        return jsonify({"error": "items は必須です"}), 400
    mapping = load_company_tantou()
    added = 0
    for item in items:
        company = item.get("company", "").strip()
        name    = item.get("furikomi_name", "").strip()
        if company and name:
            _add_furikomi(mapping, company, name)
            added += 1
    save_company_tantou(mapping)
    return jsonify({"ok": True, "added": added})


@app.route("/api/customers/tantou/update", methods=["POST"])
@login_required
def api_customers_tantou_update():
    """担当者を更新する"""
    data    = request.get_json(force=True, silent=True) or {}
    company = data.get("company", "").strip()
    tantou  = data.get("tantou", "").strip()
    if not company:
        return jsonify({"error": "company は必須です"}), 400
    mapping = load_company_tantou()
    _set_tantou(mapping, company, tantou)
    save_company_tantou(mapping)
    return jsonify({"ok": True})


@app.route("/api/customers/delete", methods=["POST"])
@login_required
def api_customers_delete():
    """顧客をマスタから削除する"""
    data    = request.get_json(force=True, silent=True) or {}
    company = data.get("company", "").strip()
    if not company:
        return jsonify({"error": "company は必須です"}), 400
    mapping = load_company_tantou()
    mapping.pop(company, None)
    save_company_tantou(mapping)
    return jsonify({"ok": True})



@app.route("/api/unclassified/check", methods=["POST"])
@login_required
def api_unclassified_check():
    """会計未仕分けタブ: 今日から2カ月前までの未仕分け仕訳を取得して保存する"""
    from datetime import timedelta
    cid = get_company_id()
    if not auth.is_authenticated("accounting", cid):
        return jsonify({"error": "MFクラウド会計の連携が必要です。"}), 401

    today = date.today()
    m = today.month - 2
    y = today.year
    if m <= 0:
        m += 12
        y -= 1
    from_dt   = date(y, m, 1)
    from_date = from_dt.strftime("%Y-%m-%d")
    to_date   = today.strftime("%Y-%m-%d")

    # 会計期間またぎチェック: またぐ場合は今期開始日にクリップ
    _s      = load_settings()
    _fstart = _s.get("fiscal_year_start_month", 4)
    _fy_year = today.year if today.month >= _fstart else today.year - 1
    curr_from_dt = date(_fy_year, _fstart, 1)
    curr_from    = curr_from_dt.strftime("%Y-%m-%d")
    spans_fiscal = (from_dt < curr_from_dt <= today)
    if spans_fiscal:
        return jsonify({"error": "過去2カ月間が会計期間をまたいでいるためデータ取得ができません。マネーフォワードクラウド会計でご確認ください。", "error_type": "accounting_period"}), 400

    try:
        from mf_accounting import get_unclassified_deals
    except ImportError as e:
        return jsonify({"error": f"mf_accounting モジュールが見つかりません: {e}"}), 500

    try:
        raw_deals = get_unclassified_deals(from_date, to_date, company_id=cid)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    filtered = raw_deals

    existing = load_furikomi_unconfirmed()
    existing_ids = {r.get("取引ID") for r in existing}

    import uuid as _uuid
    new_records = []
    for d in filtered:
        tid = d.get("取引ID", "")
        if tid in existing_ids:
            continue
        new_records.append({
            "id":                  str(_uuid.uuid4()),
            "取引ID":              tid,
            "着金日":              d.get("着金日", ""),
            "入金金額":            d.get("入金金額", 0),
            "取引先名":            d.get("取引先名", ""),
            "備考":                d.get("備考", ""),
            "科目":                d.get("科目", ""),
            "suggested_partner":   d.get("取引先名", ""),
            "candidate_invoice_id": None,
            "linked_invoice_id":   None,
            "deleted":             False,
        })

    all_records = existing + new_records
    save_furikomi_unconfirmed(all_records)

    total = len([r for r in all_records if not r.get("deleted") and not r.get("linked_invoice_id")])
    return jsonify({
        "ok":             True,
        "new_count":      len(new_records),
        "total":          total,
        "from_date":      from_date,
        "to_date":        to_date,
        "spans_fiscal":   spans_fiscal,
        "fiscal_boundary": curr_from if spans_fiscal else None,
    })


@app.route("/api/invoice/<invoice_id>/delete-draft", methods=["POST"])
def delete_draft_invoice(invoice_id):
    """下書き（期限超過）タブから請求書を削除（非表示）する"""
    ids = load_deleted_drafts()
    ids.add(invoice_id)
    save_deleted_drafts(ids)

    # last_result.json からも即時除去
    result = _load_result()
    if result:
        result["draft_overdue"] = [
            b for b in result.get("draft_overdue", [])
            if b.get("請求書ID") != invoice_id
        ]
        output_path = result.get("output_path", "")
        _save_result(result, output_path)

    return jsonify({"ok": True})


@app.route("/api/invoice/mark-unmade", methods=["POST"])
def mark_unmade():
    """請求済みか確認タブの請求書を「未請求」として除外する（複数対応）"""
    data        = request.get_json() or {}
    invoice_ids = data.get("invoice_ids", [])
    if not invoice_ids:
        return jsonify({"error": "invoice_ids が必要です"}), 400

    ids = load_deleted_seikyu()
    ids.update(invoice_ids)
    save_deleted_seikyu(ids)

    # last_result.json からも即時除去
    result = _load_result()
    if result:
        id_set = set(invoice_ids)
        result["seikyu_kakunin"] = [
            b for b in result.get("seikyu_kakunin", [])
            if b.get("請求書ID") not in id_set
        ]
        _save_result(result, result.get("output_path", ""))

    return jsonify({"ok": True, "count": len(invoice_ids)})


# ========================================
# 未収再確認 API
# ========================================

@app.route("/api/accounting/debug", methods=["GET"])
@login_required
def api_accounting_debug():
    """会計APIの接続状況をデバッグする（複数URLを試す）"""
    import requests as _req
    cid = get_company_id()
    try:
        token = auth.get_access_token("accounting", cid)
    except Exception as e:
        return jsonify({"step": "get_token", "error": str(e)})

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    results = {}

    # 試すURL一覧
    # 請求書APIトークンも取得して試す
    inv_headers = {}
    try:
        inv_token = auth.get_access_token("invoice", cid)
        inv_headers = {"Authorization": f"Bearer {inv_token}", "Accept": "application/json"}
    except Exception:
        pass

    test_urls = [
        ("journals_v3_new",  headers,     "https://api-accounting.moneyforward.com/api/v3/journals",   {"start_date": "2026-02-01", "end_date": "2026-04-22", "per_page": 1}),
        ("offices_v3_new",   headers,     "https://api-accounting.moneyforward.com/api/v3/offices",    {}),
        ("invoice_billings", inv_headers, "https://invoice.moneyforward.com/api/v3/billings",          {"per_page": 1}),
    ]

    for key, hdrs, url, params in test_urls:
        try:
            resp = _req.get(url, headers=hdrs, params=params, timeout=10)
            results[key] = {"status": resp.status_code, "body": resp.text[:300]}
        except Exception as e:
            results[key] = {"error": str(e)}

    return jsonify({"token_prefix": token[:10] + "...", "results": results})


@app.route("/api/accounting/upload_csv", methods=["POST"])
@login_required
def api_accounting_upload_csv():
    """MFクラウド会計の仕訳帳CSVをアップロードして保存する"""
    if "file" not in request.files:
        return jsonify({"error": "ファイルが選択されていません"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "ファイルが選択されていません"}), 400

    try:
        content = f.read()
        deals = parse_mf_accounting_csv(content)
        save_accounting_deals(deals)
        print(f"[会計CSV] {len(deals)}件の仕訳を取り込みました", flush=True)
        return jsonify({"ok": True, "count": len(deals)})
    except Exception as e:
        return jsonify({"error": f"CSVの読み込みエラー: {e}"}), 400


@app.route("/api/overdue/<invoice_id>/recheck", methods=["POST"])
@login_required
def api_overdue_recheck(invoice_id):
    """
    未収請求書の取引先の入金履歴を照合する。
    1. アップロード済みMF会計CSVデータを使用（優先）
    2. CSVがなければMFクラウド会計APIを試みる
    """
    result = _load_result()
    if not result:
        return jsonify({"error": "先に請求書チェックを実行してください。"}), 400

    # 請求書IDから取引先名を取得
    partner_name = ""
    invoice_amt  = 0
    for cat in ["overdue", "seikyu_kakunin", "upcoming", "unpaid", "ichiji_hokan"]:
        for b in result.get(cat, []):
            if b.get("請求書ID") == invoice_id:
                partner_name = b.get("取引先名", "")
                invoice_amt  = b.get("請求金額", 0)
                break
        if partner_name:
            break

    if not partner_name:
        return jsonify({"error": "請求書が見つかりません"}), 404

    # 抽出期間: 前期 + 当期（会計期間をまたがないよう分けて取得）
    _s = load_settings()
    _fstart = _s.get("fiscal_year_start_month", 4)
    _curr_fy = get_current_fiscal_year(_fstart)
    curr_from, _ = get_fiscal_year_range(_curr_fy, _fstart)
    curr_to = date.today().strftime("%Y-%m-%d")
    prev_from, prev_to = get_fiscal_year_range(_curr_fy - 1, _fstart)

    # データソース選択: CSVが優先、なければAPI
    cid = get_company_id()
    csv_deals = load_accounting_deals()
    if csv_deals:
        # CSVデータを日付フィルタして使用
        deals = [
            d for d in csv_deals
            if prev_from <= d.get("着金日", "") <= curr_to
        ]
        data_source = "CSV"
        print(f"[再確認] CSVデータ使用: {len(deals)}件（全{len(csv_deals)}件中）", flush=True)
    else:
        # APIから取得
        try:
            from mf_accounting import get_deals
            if not auth.is_authenticated("accounting", cid):
                return jsonify({
                    "error": "MFクラウド会計のデータがありません。サイドバーの「会計CSV取込」からMFクラウド会計の仕訳帳CSVをアップロードしてください。"
                }), 400
            try:
                deals_prev = get_deals(prev_from, prev_to, company_id=cid)
            except Exception:
                deals_prev = []
            deals_curr = get_deals(curr_from, curr_to, company_id=cid)
            deals = deals_prev + deals_curr
            data_source = "API"
        except Exception as e:
            return jsonify({
                "error": f"MFクラウド会計のデータがありません。サイドバーの「会計CSV取込」からMFクラウド会計の仕訳帳CSVをアップロードしてください。（詳細: {e}）"
            }), 400

    # 振込名義リストを取得（顧客リスト + 請求書メタ）
    company_tantou = load_company_tantou()
    meta_all       = load_meta()
    furikomi_meta  = meta_all.get(invoice_id, {}).get("個人名", "")
    furikomi_list  = _get_furikomi_list(company_tantou, partner_name)
    if furikomi_meta and furikomi_meta not in furikomi_list:
        furikomi_list = [furikomi_meta] + furikomi_list

    if not furikomi_list:
        return jsonify({
            "ok":          False,
            "error":       f"「{partner_name}」の振込名義が登録されていません。顧客リストまたは編集ボタンから振込名義を登録してください。",
            "new_count":   0,
            "total_count": 0,
        }), 400

    # 振込名義が会計の適用（備考）に含まれているかで照合
    import re as _re
    import jaconv as _jc

    def _norm(s: str) -> str:
        s = _jc.hira2kata(s.strip())
        s = _jc.h2z(s, kana=True, ascii=False, digit=False)
        s = _re.sub(r'[\s\u3000\-－　]', '', s).upper()
        return s

    matched_deals = []
    for d in deals:
        remark   = d.get("備考", "") or ""
        remark_n = _norm(remark)
        for name in furikomi_list:
            if not name or len(name) < 2:
                continue
            name_n = _norm(name)
            # 正規化後の名前が適用に含まれるか、または元テキストで含まれるか
            if (len(name_n) >= 2 and name_n in remark_n) or name in remark:
                matched_deals.append(d)
                break

    # recheck_records に追加（会計取引IDで重複除去、レコードIDはUUID）
    import uuid as _uuid
    records      = load_recheck_records()
    existing_jids = {r.get("journal_id", r["id"]) for r in records}
    new_count    = 0
    for d in matched_deals:
        journal_id = str(d.get("取引ID", ""))
        if not journal_id or journal_id in existing_jids:
            continue
        records.append({
            "id":                     str(_uuid.uuid4()),   # URLセーフなUUID
            "journal_id":             journal_id,           # 元の会計取引ID
            "fetched_at":             datetime.now().isoformat(),
            "fetched_for_invoice_id": invoice_id,
            "取引先名":               d.get("取引先名", ""),
            "着金日":                 d.get("着金日", ""),
            "入金金額":               d.get("入金金額", 0),
            "備考":                   d.get("備考", ""),
            "科目":                   d.get("科目", ""),
            "memo":                   "",
            "deleted":                False,
            "linked_invoice_id":      None,
            "linked_invoice_num":     None,
            "linked_at":              None,
        })
        existing_jids.add(journal_id)
        new_count += 1

    save_recheck_records(records)

    # デバッグ情報
    print(f"[再確認] 取引先名: {partner_name}", flush=True)
    print(f"[再確認] 振込名義リスト: {furikomi_list}", flush=True)
    print(f"[再確認] 会計仕訳件数: {len(deals)}件", flush=True)
    print(f"[再確認] 照合一致件数: {len(matched_deals)}件", flush=True)
    # 備考フィールドのサンプルを出力
    for d in deals[:5]:
        print(f"[再確認] 備考サンプル: '{d.get('備考', '')}' / 取引先名: '{d.get('取引先名', '')}'", flush=True)

    visible = [r for r in records if not r.get("deleted")]
    return jsonify({
        "ok":           True,
        "new_count":    new_count,
        "total_count":  len(visible),
        "partner_name": partner_name,
        "from_date":    prev_from,
        "to_date":      curr_to,
        "debug": {
            "deals_total":    len(deals),
            "deals_matched":  len(matched_deals),
            "furikomi_list":  furikomi_list,
            "sample_remarks": [d.get("備考", "") for d in deals[:5]],
        },
    })


@app.route("/api/recheck/<record_id>/link", methods=["POST"])
@login_required
def api_recheck_link(record_id):
    """
    入金履歴レコードを請求書に照合する。
    invoice_id に 着金日_手動・着金金額_手動 をセットし、未収から消す。
    """
    data       = request.get_json(force=True, silent=True) or {}
    invoice_id = data.get("invoice_id", "").strip()
    if not invoice_id:
        return jsonify({"error": "invoice_id が必要です"}), 400

    samediff = data.get("差額")
    if samediff is not None:
        try:
            samediff = int(samediff)
        except (TypeError, ValueError):
            samediff = None

    records = load_recheck_records()
    record  = next((r for r in records if r["id"] == record_id), None)
    if not record:
        return jsonify({"error": "レコードが見つかりません"}), 404

    # 請求書のメタに着金情報をセット
    meta = load_meta()
    meta.setdefault(invoice_id, {})
    if samediff and samediff > 0:
        # 部分入金: 未収に残したまま残額を記録
        meta[invoice_id]["部分入金"]   = True
        meta[invoice_id]["残額"]       = samediff
        meta[invoice_id]["入金済金額"] = record.get("入金金額", 0)
        meta[invoice_id]["差額"]       = samediff
        # 着金日_手動をクリア（以前に全額入金済みとしていた場合に備えて）
        meta[invoice_id].pop("着金日_手動", None)
        meta[invoice_id].pop("着金金額_手動", None)
    else:
        # 全額入金: 未収から消す
        meta[invoice_id]["着金日_手動"]   = record.get("着金日", "")
        meta[invoice_id]["着金金額_手動"] = record.get("入金金額", 0)
        # 部分入金フラグをクリア
        for k in ["部分入金", "残額", "入金済金額", "差額"]:
            meta[invoice_id].pop(k, None)
    save_meta(meta)

    # 請求書番号を取得（表示用）& 部分入金時は paid→overdue に移動
    result = _load_result()
    invoice_num = invoice_id
    if result:
        for cat in ["overdue", "seikyu_kakunin", "upcoming", "unpaid", "ichiji_hokan", "paid"]:
            for b in result.get(cat, []):
                if b.get("請求書ID") == invoice_id:
                    invoice_num = b.get("請求番号", invoice_id)
                    break

        # 部分入金の場合: paid に入っていれば overdue に戻す
        if samediff and samediff > 0:
            _META_KEYS = ["着金日_手動", "着金金額_手動", "部分入金", "残額", "入金済金額"]
            moved = False
            for lst_key in ["paid", "unpaid"]:
                lst = result.get(lst_key, [])
                for i, b in enumerate(lst):
                    if b.get("請求書ID") == invoice_id:
                        item = lst.pop(i)
                        for k in _META_KEYS:
                            item.pop(k, None)
                        item["着金日_手動"]   = ""
                        item["着金金額_手動"] = 0
                        result.setdefault("overdue", []).append(item)
                        result["overdue"].sort(key=lambda x: x.get("支払期限", ""))
                        moved = True
                        break
                if moved:
                    break
            result_path = os.path.join(_cdir(), "last_result.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

    # レコードを照合済みにマーク
    record["linked_invoice_id"]  = invoice_id
    record["linked_invoice_num"] = invoice_num
    record["linked_at"]          = datetime.now().isoformat()
    record["差額"]               = samediff
    save_recheck_records(records)

    return jsonify({"ok": True, "invoice_num": invoice_num, "差額": samediff})


@app.route("/api/recheck/<record_id>/unlink", methods=["POST"])
@login_required
def api_recheck_unlink(record_id):
    """照合済みレコードの紐づけを解除する"""
    records = load_recheck_records()
    record  = next((r for r in records if r["id"] == record_id), None)
    if not record:
        return jsonify({"error": "レコードが見つかりません"}), 404

    invoice_id = record.get("linked_invoice_id")
    if invoice_id:
        # ① invoice_meta をクリア
        meta = load_meta()
        if invoice_id in meta:
            for k in ["着金日_手動", "着金金額_手動", "差額", "部分入金", "残額", "入金済金額"]:
                meta[invoice_id].pop(k, None)
        save_meta(meta)

        # ② last_result.json 内の請求書を paid→overdue に移動し、焼き込みフィールドをクリア
        result = _load_result()
        if result:
            _META_KEYS = ["着金日_手動", "着金金額_手動", "部分入金", "残額", "入金済金額"]
            moved = False
            # paid リストから探して overdue へ移動
            for lst_key in ["paid", "unpaid"]:
                lst = result.get(lst_key, [])
                for i, b in enumerate(lst):
                    if b.get("請求書ID") == invoice_id:
                        item = lst.pop(i)
                        for k in _META_KEYS:
                            item.pop(k, None)
                        item["着金日_手動"]   = ""
                        item["着金金額_手動"] = 0
                        result.setdefault("overdue", []).append(item)
                        result["overdue"].sort(key=lambda x: x.get("支払期限", ""))
                        moved = True
                        break
                if moved:
                    break
            # overdue リストにある場合は焼き込みフィールドだけクリア
            if not moved:
                for b in result.get("overdue", []):
                    if b.get("請求書ID") == invoice_id:
                        for k in _META_KEYS:
                            b.pop(k, None)
                        b["着金日_手動"]   = ""
                        b["着金金額_手動"] = 0
                        break
            result_path = os.path.join(_cdir(), "last_result.json")
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

    record["linked_invoice_id"]  = None
    record["linked_invoice_num"] = None
    record["linked_at"]          = None
    record["差額"]               = None
    save_recheck_records(records)

    return jsonify({"ok": True, "unlinked_invoice_id": invoice_id})


@app.route("/api/recheck/<record_id>/edit", methods=["POST"])
@login_required
def api_recheck_edit(record_id):
    """入金履歴レコードのメモを更新する"""
    data    = request.get_json(force=True, silent=True) or {}
    memo    = data.get("memo", "")
    records = load_recheck_records()
    record  = next((r for r in records if r["id"] == record_id), None)
    if not record:
        return jsonify({"error": "レコードが見つかりません"}), 404
    record["memo"] = memo
    save_recheck_records(records)
    return jsonify({"ok": True})


@app.route("/api/recheck/<record_id>/delete", methods=["POST"])
@login_required
def api_recheck_delete(record_id):
    """入金履歴レコードを未収再確認リストから削除（ソフトデリート）"""
    records = load_recheck_records()
    record  = next((r for r in records if r["id"] == record_id), None)
    if not record:
        return jsonify({"error": "レコードが見つかりません"}), 404
    record["deleted"] = True
    save_recheck_records(records)
    return jsonify({"ok": True})


@app.route("/api/debug-billing-raw")
def debug_billing_raw():
    """請求書APIの実際のフィールド一覧を確認するデバッグエンドポイント"""
    import requests as _req
    try:
        token = auth.get_access_token("invoice", get_company_id())
        r = _req.get(
            "https://invoice.moneyforward.com/api/v3/billings",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            params={"per_page": 3, "page": 1},
            timeout=30,
        )
        if r.ok:
            items = r.json().get("data", [])
            if items:
                first = items[0]
                return jsonify({
                    "all_fields": sorted(first.keys()),
                    "delivery_fields": {
                        k: first.get(k)
                        for k in ["posting_status", "posting", "email_status",
                                  "is_downloaded", "is_locked", "billing_status",
                                  "status", "draft", "payment_status"]
                        if k in first
                    },
                    "sample_3": [
                        {k: v for k, v in item.items()
                         if k not in ("billing_items", "partner", "department",
                                      "memo", "title")}
                        for item in items
                    ],
                })
        return jsonify({"error": f"HTTP {r.status_code}", "body": r.text[:500]})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()})




# ========================================
# データクリア
# ========================================

@app.route("/api/clear-data", methods=["POST"])
def clear_data():
    cdir = _cdir()
    # 請求書照合結果
    p = os.path.join(cdir, "last_result.json")
    if os.path.exists(p):
        os.remove(p)
    # 手動メタデータ（着金日_手動 等が残ると再照合で入金済みに分類されるため）
    meta_p = os.path.join(cdir, "invoice_meta.json")
    if os.path.exists(meta_p):
        os.remove(meta_p)
    # 未収再確認・振込名義確認をリセット
    save_recheck_records([])
    save_furikomi_unconfirmed([])
    flash("表示データをクリアしました", "success")
    return redirect(url_for("dashboard"))

# ========================================
# 月次履歴 API・ページ
# ========================================

def _is_admin_aggregate() -> bool:
    """管理者が自社（集約ビュー）を見ているか判定"""
    own_cid = session.get("company_id", "")
    return bool(session.get("is_admin")) and (get_company_id() == own_cid)


def _load_all_histories() -> list:
    """全一般会社の月次履歴を集約して返す（管理者集約ビュー用）"""
    auth_data = _load_auth_data()
    all_hist = []
    for c in auth_data.get("companies", []):
        if c.get("is_admin"):
            continue
        cid = c["id"]
        # 会社名
        settings_path = os.path.join(DATA_DIR, cid, "settings.json")
        comp_name = c["email"]
        if os.path.exists(settings_path):
            try:
                with open(settings_path, encoding="utf-8") as f:
                    s = json.load(f)
                comp_name = s.get("company_name") or c["email"]
            except Exception:
                pass
        hd = os.path.join(DATA_DIR, cid, "history")
        if not os.path.exists(hd):
            continue
        for fname in sorted(os.listdir(hd), reverse=True):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(hd, fname), encoding="utf-8") as fp:
                    h = json.load(fp)
                h["_company_name"] = comp_name
                h["_company_id"]   = cid
                all_hist.append(h)
            except Exception:
                pass
    # 年月・会社名でソート
    all_hist.sort(key=lambda x: (x["year_month"], x["_company_name"]), reverse=True)
    return all_hist


@app.route("/api/history/<year_month>/delete-month", methods=["POST"])
def history_delete_month(year_month):
    """確定月の履歴ファイルを丸ごと削除する"""
    data = request.get_json() or {}
    cid  = data.get("cid", "")

    if _is_admin_aggregate() and cid:
        path = os.path.join(DATA_DIR, cid, "history", f"{year_month}.json")
    else:
        path = os.path.join(_hdir(), f"{year_month}.json")

    if not os.path.exists(path):
        return jsonify({"error": "履歴が見つかりません"}), 404

    os.remove(path)
    return jsonify({"ok": True})


@app.route("/api/history/confirm", methods=["POST"])
def history_confirm():
    data = request.get_json() or {}
    year_month = data.get("year_month", "").strip()
    if not year_month:
        return jsonify({"error": "year_month が必要です"}), 400

    snapshot = _build_history_snapshot(year_month)
    if not snapshot:
        return jsonify({"error": "チェック結果がありません。先にチェックを実行してください。"}), 400

    save_history(year_month, snapshot)
    return jsonify({"ok": True, "year_month": year_month})

@app.route("/api/history/<year_month>/delete-item", methods=["POST"])
def history_delete_item(year_month):
    """履歴の特定行を削除する（index指定で重複も個別削除可能）"""
    data = request.get_json() or {}
    item_type  = data.get("type", "")   # "unpaid" or "paid"
    row_index  = data.get("index", -1)  # 0始まりのインデックス
    cid        = data.get("cid", "")

    if _is_admin_aggregate() and cid:
        path = os.path.join(DATA_DIR, cid, "history", f"{year_month}.json")
    else:
        path = os.path.join(_hdir(), f"{year_month}.json")

    if not os.path.exists(path):
        return jsonify({"error": "履歴が見つかりません"}), 404

    with open(path, encoding="utf-8") as f:
        hist = json.load(f)

    if item_type in ("unpaid", "paid"):
        items = hist.get(item_type, [])
        if 0 <= row_index < len(items):
            items.pop(row_index)
            hist[item_type] = items
        else:
            return jsonify({"error": "行が見つかりません"}), 404
        # サマリー再計算
        hist["summary"]["unpaid_count"] = len(hist["unpaid"])
        hist["summary"]["unpaid_total"] = int(sum(b.get("請求金額", 0) for b in hist["unpaid"]))
        hist["summary"]["paid_count"]   = len(hist["paid"])
        hist["summary"]["paid_total"]   = int(sum(b.get("請求金額", 0) for b in hist["paid"]))
    else:
        return jsonify({"error": "type は unpaid か paid を指定してください"}), 400

    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

    return jsonify({"ok": True, "unpaid_count": hist["summary"]["unpaid_count"],
                    "paid_count": hist["summary"]["paid_count"]})


@app.route("/api/history/<year_month>/update-item", methods=["POST"])
def history_update_item(year_month):
    """履歴の特定行のメモ・担当者などを修正する"""
    data      = request.get_json() or {}
    item_type = data.get("type", "")   # "unpaid" or "paid"
    row_index = data.get("index", -1)
    updates   = data.get("updates", {})
    cid       = data.get("cid", "")

    if _is_admin_aggregate() and cid:
        path = os.path.join(DATA_DIR, cid, "history", f"{year_month}.json")
    else:
        path = os.path.join(_hdir(), f"{year_month}.json")

    if not os.path.exists(path):
        return jsonify({"error": "履歴が見つかりません"}), 404

    with open(path, encoding="utf-8") as f:
        hist = json.load(f)

    if item_type in ("unpaid", "paid"):
        items = hist.get(item_type, [])
        if 0 <= row_index < len(items):
            allowed = {"メモ_手動", "担当者", "着金日_手動", "着金金額_手動"}
            for k, v in updates.items():
                if k in allowed:
                    items[row_index][k] = v
        else:
            return jsonify({"error": "行が見つかりません"}), 404
    else:
        return jsonify({"error": "type は unpaid か paid を指定してください"}), 400

    with open(path, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, indent=2)

    return jsonify({"ok": True})


@app.route("/api/history/dismiss-popup", methods=["POST"])
def history_dismiss_popup():
    data = request.get_json() or {}
    year_month = data.get("year_month", "")
    s = load_settings()
    s["history_popup_dismissed"] = year_month
    save_settings(s)
    return jsonify({"ok": True})

@app.route("/history")
def history_list_page():
    settings = load_settings()
    if _is_admin_aggregate():
        histories = _load_all_histories()
        return render_template(
            "history.html",
            histories=histories,
            detail=None,
            selected_ym=None,
            admin_aggregate=True,
            auth_invoice=False,
            settings=settings,
        )
    histories = load_history_list()
    return render_template(
        "history.html",
        histories=histories,
        detail=None,
        selected_ym=None,
        admin_aggregate=False,
        auth_invoice=auth.is_authenticated("invoice", get_company_id()),
        settings=settings,
    )

@app.route("/history/<year_month>")
def history_detail(year_month):
    settings = load_settings()
    if _is_admin_aggregate():
        # 管理者集約：会社IDをクエリパラメータから取得
        cid = request.args.get("cid", "")
        if cid:
            path = os.path.join(DATA_DIR, cid, "history", f"{year_month}.json")
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    detail = json.load(f)
                # 会社名を付与
                c = _find_company_by_id(cid)
                sp = os.path.join(DATA_DIR, cid, "settings.json")
                comp_name = c["email"] if c else cid
                if os.path.exists(sp):
                    with open(sp, encoding="utf-8") as f:
                        comp_name = json.load(f).get("company_name") or comp_name
                detail["_company_name"] = comp_name
                detail["_company_id"]   = cid
            else:
                flash(f"{year_month} の履歴が見つかりません", "error")
                return redirect(url_for("history_list_page"))
        else:
            flash("会社を指定してください", "error")
            return redirect(url_for("history_list_page"))
        return render_template(
            "history.html",
            histories=_load_all_histories(),
            detail=detail,
            selected_ym=year_month,
            admin_aggregate=True,
            auth_invoice=False,
            settings=settings,
        )
    detail = load_history(year_month)
    if not detail:
        flash(f"{year_month} の履歴が見つかりません", "error")
        return redirect(url_for("history_list_page"))
    return render_template(
        "history.html",
        histories=load_history_list(),
        detail=detail,
        selected_ym=year_month,
        admin_aggregate=False,
        auth_invoice=auth.is_authenticated("invoice", get_company_id()),
        settings=settings,
    )

@app.route("/history/<year_month>/download")
def history_download(year_month):
    if _is_admin_aggregate():
        cid = request.args.get("cid", "")
        path_json = os.path.join(DATA_DIR, cid, "history", f"{year_month}.json") if cid else None
        if path_json and os.path.exists(path_json):
            with open(path_json, encoding="utf-8") as f:
                detail = json.load(f)
        else:
            flash(f"{year_month} の履歴が見つかりません", "error")
            return redirect(url_for("history_list_page"))
    else:
        detail = load_history(year_month)
        if not detail:
            flash(f"{year_month} の履歴が見つかりません", "error")
            return redirect(url_for("history_list_page"))
    path = _generate_history_excel(detail)
    return send_file(path, as_attachment=True)

# ========================================
# 入金チェックルール表
# ========================================

@app.route("/rules")
def rules_page():
    return render_template(
        "rules.html",
        auth_invoice=auth.is_authenticated("invoice", get_company_id()),
        settings=load_settings(),
    )

@app.route("/howto")
def howto_page():
    return render_template(
        "howto.html",
        auth_invoice=auth.is_authenticated("invoice", get_company_id()),
        settings=load_settings(),
    )

# ========================================
# メール通知設定（トークン失効アラート）
# ========================================

NOTIFY_SETTINGS_FILE = os.path.join(DATA_DIR, "notify_settings.json")

DEFAULT_EMAIL_SUBJECT = "【未入金チェックシステム】MFクラウド請求書の再認証が必要です"

DEFAULT_EMAIL_BODY = """\
{company_name} のMFクラウド請求書との連携トークンが失効しました。

このままでは未入金チェックが実行できません。
以下のURLにアクセスし、再認証を行ってください。

▼ 再認証URL
{domain}/oauth/start/invoice

【手順】
1. 上記URLにアクセスしてログイン（ログインID: {company_email}）
2. ログイン後、自動的にMFクラウドの認証画面へ移動します
3. MFクラウドで「許可する」を押して完了です

ご不明な点があればシステム管理者にお問い合わせください。

----
このメールは未入金チェックシステムから自動送信されています。
返信は不要です。
"""


def _load_notify_settings() -> dict:
    if not os.path.exists(NOTIFY_SETTINGS_FILE):
        return {
            "notify_enabled": False,
            "notify_emails":  [],
            "email_subject":  DEFAULT_EMAIL_SUBJECT,
            "email_body":     DEFAULT_EMAIL_BODY,
        }
    with open(NOTIFY_SETTINGS_FILE, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("notify_enabled", False)
    data.setdefault("notify_emails",  [])
    data.setdefault("email_subject",  DEFAULT_EMAIL_SUBJECT)
    data.setdefault("email_body",     DEFAULT_EMAIL_BODY)
    return data


def _save_notify_settings(data: dict):
    with open(NOTIFY_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _send_token_expired_email(company_name: str, company_email: str, notify: dict):
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASSWORD", "")
    app_url   = os.getenv("APP_URL", "https://check.coaris-ai.com")

    if not all([smtp_host, smtp_user, smtp_pass]):
        raise RuntimeError("SMTP設定が未入力です（SMTP_HOST / SMTP_USER / SMTP_PASSWORD を .env に設定してください）")

    recipients = [e.strip() for e in notify.get("notify_emails", []) if e.strip()]
    if not recipients:
        raise RuntimeError("通知先メールアドレスが設定されていません。設定画面でアドレスを追加して保存してください。")

    subject = notify.get("email_subject", DEFAULT_EMAIL_SUBJECT)
    body    = notify.get("email_body", DEFAULT_EMAIL_BODY)
    body    = body.replace("{company_name}",  company_name)
    body    = body.replace("{company_email}", company_email)
    body    = body.replace("{domain}",        app_url)

    msg = MIMEMultipart()
    msg["From"]    = smtp_user
    msg["To"]      = ", ".join(recipients)
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, recipients, msg.as_string())
    print(f"[メール通知] 送信完了 → {company_name}（{recipients}）")


def _check_all_tokens():
    """全会社のMFトークンをチェックし、失効していたらメール通知"""
    notify = _load_notify_settings()
    if not notify.get("notify_enabled"):
        return
    auth_data = _load_auth_data()
    for company in auth_data.get("companies", []):
        if company.get("is_admin"):
            continue
        cid = company["id"]
        if not auth.is_authenticated("invoice", cid):
            settings_path = os.path.join(DATA_DIR, cid, "settings.json")
            company_name = company["email"]
            if os.path.exists(settings_path):
                try:
                    with open(settings_path, encoding="utf-8") as f:
                        s = json.load(f)
                    company_name = s.get("company_name") or company["email"]
                except Exception:
                    pass
            print(f"[トークンチェック] 失効検出: {company_name}（{cid}）")
            try:
                _send_token_expired_email(company_name, company["email"], notify)
            except Exception as e:
                print(f"[メール通知] 送信失敗: {e}")


@app.route("/api/notify-settings", methods=["GET", "POST"])
@login_required
def api_notify_settings():
    if not session.get("is_admin"):
        return jsonify({"error": "権限がありません"}), 403
    if request.method == "GET":
        return jsonify(_load_notify_settings())
    data   = request.get_json(force=True, silent=True) or {}
    notify = _load_notify_settings()
    if "notify_enabled" in data:
        notify["notify_enabled"] = bool(data["notify_enabled"])
    if "notify_emails" in data:
        notify["notify_emails"] = [e.strip() for e in data["notify_emails"] if e.strip()]
    if "email_subject" in data:
        notify["email_subject"] = data["email_subject"].strip() or DEFAULT_EMAIL_SUBJECT
    if "email_body" in data:
        notify["email_body"] = data["email_body"] or DEFAULT_EMAIL_BODY
    _save_notify_settings(notify)
    return jsonify({"ok": True})


@app.route("/api/notify-settings/test", methods=["POST"])
@login_required
def api_notify_settings_test():
    if not session.get("is_admin"):
        return jsonify({"error": "権限がありません"}), 403
    notify = _load_notify_settings()
    try:
        _send_token_expired_email(
            company_name="テスト会社（送信テスト）",
            company_email="test@example.com",
            notify=notify,
        )
        return jsonify({"ok": True, "message": "テストメールを送信しました"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


# ========================================
# 起動
# ========================================

if __name__ == "__main__":
    port  = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    # 同じポートを使っている既存プロセスを終了
    import subprocess as _sp
    _sp.run(
        f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess | Where-Object {{$_ -ne {os.getpid()}}} | ForEach-Object {{Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue}}"',
        shell=True, capture_output=True
    )
    init_scheduler(run_func=_run_check, token_check_func=_check_all_tokens)
    import webbrowser, threading as _th
    _th.Timer(1.0, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    print(f"\n{'='*50}")
    print(f"  未入金チェックシステム 起動中")
    print(f"  http://localhost:{port}")
    print(f"{'='*50}\n")
    app.run(host="0.0.0.0", port=port, debug=debug, use_reloader=False)
