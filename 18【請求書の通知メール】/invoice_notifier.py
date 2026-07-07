"""
請求書メール通知システム（ステータスウィンドウ版）
- IMAPでメールサーバーを定期監視
- 件名に「請求書」を含む新着メールを検知
- Windowsデスクトップ通知（トースト通知）で通知
- 小さいステータスウィンドウを常時表示
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


def load_seen_uids():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_uids(uids):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(uids), f)


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
        self.root.title("請求書監視")
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.root.configure(bg="#1a1a2e")

        # ウィンドウサイズと位置（右下に配置）
        w, h = 320, 120
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = screen_w - w - 20
        y = screen_h - h - 80
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        # 閉じるボタンで最小化（終了防止）
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # --- UI ---
        frame = tk.Frame(self.root, bg="#1a1a2e", padx=10, pady=8)
        frame.pack(fill="both", expand=True)

        # タイトル行
        title_frame = tk.Frame(frame, bg="#1a1a2e")
        title_frame.pack(fill="x")

        tk.Label(
            title_frame, text="請求書メール監視",
            font=("Meiryo UI", 11, "bold"), fg="#e0e0e0", bg="#1a1a2e"
        ).pack(side="left")

        self.status_dot = tk.Label(
            title_frame, text="●", font=("Meiryo UI", 10),
            fg="#00c853", bg="#1a1a2e"
        )
        self.status_dot.pack(side="right")

        # 区切り線
        tk.Frame(frame, height=1, bg="#333355").pack(fill="x", pady=4)

        # 情報表示
        info_frame = tk.Frame(frame, bg="#1a1a2e")
        info_frame.pack(fill="x")

        tk.Label(
            info_frame, text="最終チェック:",
            font=("Meiryo UI", 9), fg="#888888", bg="#1a1a2e"
        ).grid(row=0, column=0, sticky="w")

        self.last_check_label = tk.Label(
            info_frame, text="--:--:--",
            font=("Meiryo UI", 9, "bold"), fg="#e0e0e0", bg="#1a1a2e"
        )
        self.last_check_label.grid(row=0, column=1, sticky="w", padx=(8, 0))

        tk.Label(
            info_frame, text="本日の検知:",
            font=("Meiryo UI", 9), fg="#888888", bg="#1a1a2e"
        ).grid(row=1, column=0, sticky="w")

        self.detect_count_label = tk.Label(
            info_frame, text="0 件",
            font=("Meiryo UI", 9, "bold"), fg="#e0e0e0", bg="#1a1a2e"
        )
        self.detect_count_label.grid(row=1, column=1, sticky="w", padx=(8, 0))

        tk.Label(
            info_frame, text="状態:",
            font=("Meiryo UI", 9), fg="#888888", bg="#1a1a2e"
        ).grid(row=2, column=0, sticky="w")

        self.status_label = tk.Label(
            info_frame, text="起動中...",
            font=("Meiryo UI", 9, "bold"), fg="#ffd600", bg="#1a1a2e"
        )
        self.status_label.grid(row=2, column=1, sticky="w", padx=(8, 0))

        # 状態管理
        self.detect_count = 0
        self.today = datetime.now().strftime("%Y-%m-%d")
        self.running = True

        # ドラッグ移動
        self.root.bind("<Button-1>", self.start_drag)
        self.root.bind("<B1-Motion>", self.on_drag)

        # バックグラウンドスレッド開始
        self.thread = threading.Thread(target=self.monitor_loop, daemon=True)
        self.thread.start()

    def start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def on_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_x
        y = self.root.winfo_y() + event.y - self._drag_y
        self.root.geometry(f"+{x}+{y}")

    def on_close(self):
        if hasattr(self, '_confirm_shown') and self._confirm_shown:
            return
        self._confirm_shown = True
        result = tk.messagebox.askyesno(
            "確認", "請求書メール監視を終了しますか？"
        )
        self._confirm_shown = False
        if result:
            self.running = False
            self.root.destroy()

    def update_ui(self, last_check=None, status=None, status_color=None, new_detections=0):
        """UIをスレッドセーフに更新"""
        def _update():
            if last_check:
                self.last_check_label.config(text=last_check)
            if status:
                self.status_label.config(text=status, fg=status_color or "#e0e0e0")
            # 日付が変わったらカウントリセット
            today = datetime.now().strftime("%Y-%m-%d")
            if today != self.today:
                self.detect_count = 0
                self.today = today
            self.detect_count += new_detections
            self.detect_count_label.config(
                text=f"{self.detect_count} 件",
                fg="#ff1744" if self.detect_count > 0 else "#e0e0e0"
            )
        self.root.after(0, _update)

    def initial_scan(self):
        """初回起動: 既存メールを既読登録"""
        if STATE_FILE.exists():
            return
        self.update_ui(status="初回スキャン中...", status_color="#ffd600")
        try:
            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASSWORD)
            mail.select("INBOX")
            status, data = mail.uid("search", None, "ALL")
            seen = set()
            if status == "OK":
                for uid_bytes in data[0].split():
                    seen.add(uid_bytes.decode())
            save_seen_uids(seen)
            mail.logout()
        except Exception as e:
            self.update_ui(status=f"初回スキャンエラー", status_color="#ff1744")

    def check_emails(self):
        """メールチェック"""
        seen_uids = load_seen_uids()
        new_count = 0

        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("INBOX")

        status, data = mail.uid("search", None, "ALL")
        if status != "OK":
            mail.logout()
            return 0

        all_uids = data[0].split()

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
                send_desktop_notification(subject, sender)
                new_count += 1

            seen_uids.add(uid)

        save_seen_uids(seen_uids)
        mail.logout()
        return new_count

    def monitor_loop(self):
        """メインの監視ループ（バックグラウンドスレッド）"""
        self.initial_scan()

        while self.running:
            try:
                self.update_ui(status="チェック中...", status_color="#ffd600")
                new_count = self.check_emails()
                now = datetime.now().strftime("%H:%M:%S")

                if new_count > 0:
                    self.update_ui(
                        last_check=now,
                        status=f"請求書 {new_count}件 検知!",
                        status_color="#ff1744",
                        new_detections=new_count
                    )
                else:
                    self.update_ui(
                        last_check=now,
                        status="監視中",
                        status_color="#00c853"
                    )
            except Exception as e:
                self.update_ui(
                    status="接続エラー",
                    status_color="#ff1744"
                )

            # CHECK_INTERVAL秒待つ（1秒刻みで終了チェック）
            for _ in range(CHECK_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)

    def run(self):
        import tkinter.messagebox
        self.root.mainloop()


def main():
    if not IMAP_HOST or not IMAP_PASSWORD:
        print("エラー: .envファイルにIMAP_HOSTとIMAP_PASSWORDを設定してください。")
        sys.exit(1)

    app = InvoiceNotifierApp()
    app.run()


if __name__ == "__main__":
    main()
