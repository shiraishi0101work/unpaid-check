"""
請求書メール通知システム
- IMAPでメールサーバーを定期監視
- 件名に「請求書」を含む新着メールを検知
- 画面右側にポップアップ表示
- メールが開封（既読）されたらポップアップ自動消去
"""

import imaplib
import email
from email.header import decode_header
import threading
import time
import os
import sys
import json
import tkinter as tk
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

try:
    from winotify import Notification, audio
    HAS_WINOTIFY = True
except ImportError:
    HAS_WINOTIFY = False

# --- 設定 ---
BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

IMAP_HOST = os.getenv("IMAP_HOST", "")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "shiraishi@dellaforce.com")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))
KEYWORD = "請求書"

STATE_FILE = BASE_DIR / "seen_uids.json"
ALERT_FILE = BASE_DIR / "active_alerts.json"


def load_seen_uids():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_uids(uids):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(uids), f)


def load_active_alerts():
    """未開封の請求書メール（ポップアップ表示中）のUID→情報"""
    if ALERT_FILE.exists():
        with open(ALERT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_active_alerts(alerts):
    with open(ALERT_FILE, "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False)


def decode_mime_header(raw):
    decoded_parts = decode_header(raw)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def send_desktop_notification(subject, sender):
    if not HAS_WINOTIFY:
        return
    toast = Notification(
        app_id="請求書メール通知",
        title="請求書メールが届きました",
        msg=f"{subject}\n差出人: {sender}",
        duration="long",
    )
    toast.set_audio(audio.Default, loop=False)
    toast.show()


class InvoiceNotifierApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()  # メインウィンドウは非表示

        self.running = True
        self.popup = None  # ポップアップウィンドウ
        self.alert_labels = {}  # UID → ラベルウィジェット

        # バックグラウンドスレッド開始
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()

    def _round_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        """角丸四角形を描画"""
        points = [
            x1 + r, y1, x2 - r, y1,
            x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def show_popup(self, alerts):
        """ポップアップを表示/更新する"""
        def _show():
            if self.popup and self.popup.winfo_exists():
                self.popup.destroy()
            self.alert_labels.clear()

            if not alerts:
                self.popup = None
                return

            # --- 色定義（天使界隈 / 水色 x 白） ---
            BG_TRANSPARENT = "#f0f0f0"
            COLOR_WHITE = "#ffffff"
            COLOR_CARD = "#f0f8ff"
            COLOR_ACCENT = "#89c4e1"
            COLOR_ACCENT_LIGHT = "#c5e5f5"
            COLOR_ACCENT_DARK = "#5ba3c9"
            COLOR_TEXT = "#4a6d7c"
            COLOR_TEXT_LIGHT = "#8aaab8"
            COLOR_TEXT_SOFT = "#a0c4d4"
            COLOR_BORDER = "#d4eef8"
            COLOR_GLOW = "#e8f4fa"

            self.popup = tk.Toplevel(self.root)
            self.popup.title("請求書通知")
            self.popup.attributes("-topmost", True)
            self.popup.overrideredirect(True)
            self.popup.attributes("-transparentcolor", BG_TRANSPARENT)
            self.popup.configure(bg=BG_TRANSPARENT)

            # コンパクトなポップアップ
            W = 280
            H = 140
            count = len(alerts)

            canvas = tk.Canvas(
                self.popup, width=W, height=H,
                bg=BG_TRANSPARENT, highlightthickness=0
            )
            canvas.pack()

            # 影
            self._round_rect(canvas, 4, 4, W - 2, H - 2, 22, fill=COLOR_ACCENT_LIGHT, outline="")

            # メイン背景（角丸・白）
            self._round_rect(canvas, 0, 0, W - 6, H - 6, 20, fill=COLOR_WHITE, outline=COLOR_BORDER, width=1.5)

            # 上部アクセントライン
            self._round_rect(canvas, 0, 0, W - 6, 8, 20, fill=COLOR_ACCENT, outline="")
            canvas.create_rectangle(0, 6, W - 6, 8, fill=COLOR_ACCENT, outline="")

            # メインテキスト
            canvas.create_text(
                W // 2 - 3, 45,
                text="請求書メールが届いています",
                font=("Meiryo UI", 11, "bold"), fill=COLOR_TEXT
            )

            # 件数（大きく表示）
            canvas.create_text(
                W // 2 - 3, 82,
                text=f"{count} 件",
                font=("Meiryo UI", 22, "bold"), fill=COLOR_ACCENT_DARK
            )

            # 装飾ドット
            for dx in [-30, -15, 0, 15, 30]:
                canvas.create_oval(
                    W // 2 + dx - 2, 108, W // 2 + dx + 2, 112,
                    fill=COLOR_ACCENT_LIGHT, outline=""
                )

            # フッター
            canvas.create_text(
                W // 2 - 3, H - 18,
                text="- 開封すると自動で消えます -",
                font=("Meiryo UI", 8), fill=COLOR_TEXT_SOFT
            )

            for uid in alerts:
                self.alert_labels[uid] = True

            # サイズと位置（画面右側中央）
            self.popup.update_idletasks()
            screen_w = self.popup.winfo_screenwidth()
            screen_h = self.popup.winfo_screenheight()
            x = screen_w - W - 30
            y = (screen_h - H) // 2
            self.popup.geometry(f"{W}x{H}+{x}+{y}")

            # ドラッグ移動
            canvas.bind("<Button-1>", self._start_drag)
            canvas.bind("<B1-Motion>", self._on_drag)

        self.root.after(0, _show)

    def hide_popup(self):
        """ポップアップを消す"""
        def _hide():
            if self.popup and self.popup.winfo_exists():
                self.popup.destroy()
            self.popup = None
            self.alert_labels.clear()
        self.root.after(0, _hide)

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        if self.popup and self.popup.winfo_exists():
            x = self.popup.winfo_x() + event.x - self._drag_x
            y = self.popup.winfo_y() + event.y - self._drag_y
            self.popup.geometry(f"+{x}+{y}")

    def initial_scan(self):
        """初回起動: 既存メールを既読登録"""
        if STATE_FILE.exists():
            return
        try:
            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASSWORD)
            mail.select("INBOX")
            status, data = mail.uid("search", None, "ALL")
            seen = set()
            if status == "OK" and data[0]:
                for uid_bytes in data[0].split():
                    seen.add(uid_bytes.decode())
            save_seen_uids(seen)
            mail.logout()
        except Exception:
            pass

    def check_new_emails(self):
        """新着メールをチェックし、請求書メールを検知"""
        seen_uids = load_seen_uids()
        active_alerts = load_active_alerts()
        new_found = False

        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("INBOX")

        status, data = mail.uid("search", None, "ALL")
        if status != "OK":
            mail.logout()
            return False

        all_uids = data[0].split() if data[0] else []

        for uid_bytes in all_uids:
            uid = uid_bytes.decode()
            if uid in seen_uids:
                continue

            status, msg_data = mail.uid("fetch", uid_bytes, "(BODY.PEEK[HEADER])")
            if status != "OK":
                seen_uids.add(uid)
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            raw_subject = msg.get("Subject", "")
            subject = decode_mime_header(raw_subject)

            if KEYWORD in subject:
                sender = decode_mime_header(msg.get("From", ""))
                now_str = datetime.now().strftime("%m/%d %H:%M")
                active_alerts[uid] = {
                    "subject": subject,
                    "sender": sender,
                    "detected": now_str,
                    "notify_time": time.time(),
                }
                send_desktop_notification(subject, sender)
                new_found = True

            seen_uids.add(uid)

        save_seen_uids(seen_uids)
        save_active_alerts(active_alerts)
        mail.logout()
        return new_found

    def check_read_status(self):
        """未開封だった請求書メールが開封されたかチェック。
        検知から120秒以内はチェックしない（ポップアップを確実に表示するため）"""
        active_alerts = load_active_alerts()
        if not active_alerts:
            return False

        now = time.time()
        # 全アラートが検知から120秒以内ならスキップ
        all_recent = all(
            now - info.get("notify_time", 0) < 30
            for info in active_alerts.values()
        )
        if all_recent:
            return False

        removed = False

        try:
            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASSWORD)
            mail.select("INBOX")

            uids_to_remove = []
            for uid in list(active_alerts.keys()):
                # 検知から120秒以内のものはスキップ
                if now - active_alerts[uid].get("notify_time", 0) < 120:
                    continue
                # FLAGSを取得して\Seenがあるか確認
                status, flag_data = mail.uid("fetch", uid.encode(), "(FLAGS)")
                if status == "OK" and flag_data[0]:
                    flags_str = flag_data[0].decode() if isinstance(flag_data[0], bytes) else str(flag_data[0])
                    if "\\Seen" in flags_str:
                        uids_to_remove.append(uid)

            for uid in uids_to_remove:
                del active_alerts[uid]
                removed = True

            mail.logout()
        except Exception:
            pass

        if removed:
            save_active_alerts(active_alerts)

        return removed

    def monitor_loop(self):
        """メインの監視ループ"""
        self.initial_scan()

        # 起動時: 既存のアクティブアラートがあればポップアップ復元
        active = load_active_alerts()
        if active:
            self.show_popup(active)

        while self.running:
            try:
                # 新着チェック
                new_found = self.check_new_emails()

                # 開封チェック（アクティブなアラートがあるときだけ）
                read_detected = self.check_read_status()

                # ポップアップ更新
                active = load_active_alerts()
                if active:
                    if new_found or read_detected:
                        self.show_popup(active)
                else:
                    self.hide_popup()

                if new_found:
                    # 新着検知直後は短い間隔でチェック（開封検知を早くする）
                    for _ in range(10):
                        if not self.running:
                            break
                        time.sleep(1)
                    continue

            except Exception:
                pass

            for _ in range(CHECK_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)

    def run(self):
        self.root.mainloop()


def main():
    if not IMAP_HOST or not IMAP_PASSWORD:
        print("エラー: .envファイルにIMAP_HOSTとIMAP_PASSWORDを設定してください。")
        sys.exit(1)

    app = InvoiceNotifierApp()
    app.run()


if __name__ == "__main__":
    main()
