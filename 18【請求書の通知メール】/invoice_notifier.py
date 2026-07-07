"""
請求書メール通知システム
- IMAPでメールサーバーを定期監視
- 件名に「請求書」を含む新着メールを検知
- Windowsデスクトップ通知（トースト通知）で通知
"""

import imaplib
import email
from email.header import decode_header
import time
import os
import sys
import json
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Windows トースト通知
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

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "60"))  # 秒
KEYWORD = "請求書"

STATE_FILE = BASE_DIR / "seen_uids.json"


def load_seen_uids():
    """既読UIDリストを読み込む"""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_uids(uids):
    """既読UIDリストを保存する"""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(uids), f)


def decode_mime_header(raw):
    """MIMEヘッダーをデコードする"""
    decoded_parts = decode_header(raw)
    result = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return "".join(result)


def send_desktop_notification(subject, sender, received_date):
    """Windowsデスクトップ通知を送る"""
    if not HAS_WINOTIFY:
        print(f"[通知] winotify未インストール。コンソール表示のみ。")
        print(f"  件名: {subject}")
        print(f"  差出人: {sender}")
        print(f"  受信日時: {received_date}")
        return

    toast = Notification(
        app_id="請求書メール通知",
        title="請求書メールが届きました",
        msg=f"{subject}\n差出人: {sender}",
        duration="long",
    )
    toast.set_audio(audio.Default, loop=False)
    toast.show()


def check_invoice_emails():
    """IMAPに接続して請求書メールをチェックする"""
    seen_uids = load_seen_uids()
    new_count = 0

    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("INBOX")

        # 全メールのUIDを取得
        status, data = mail.uid("search", None, "ALL")
        if status != "OK":
            print(f"[{now()}] メール検索に失敗しました")
            return 0

        all_uids = data[0].split()

        for uid_bytes in all_uids:
            uid = uid_bytes.decode()
            if uid in seen_uids:
                continue

            # ヘッダーだけ取得（軽量）
            status, msg_data = mail.uid("fetch", uid_bytes, "(BODY.PEEK[HEADER])")
            if status != "OK":
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # 件名をデコード
            raw_subject = msg.get("Subject", "")
            subject = decode_mime_header(raw_subject)

            # 件名に「請求書」が含まれているかチェック
            if KEYWORD in subject:
                sender = decode_mime_header(msg.get("From", ""))
                date_str = msg.get("Date", "")
                print(f"[{now()}] 請求書メール検知: {subject} / {sender}")
                send_desktop_notification(subject, sender, date_str)
                new_count += 1

            seen_uids.add(uid)

        save_seen_uids(seen_uids)
        mail.logout()

    except imaplib.IMAP4.error as e:
        print(f"[{now()}] IMAP接続エラー: {e}")
    except Exception as e:
        print(f"[{now()}] エラー: {e}")

    return new_count


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
    if not IMAP_HOST or not IMAP_PASSWORD:
        print("エラー: .envファイルにIMAP_HOSTとIMAP_PASSWORDを設定してください。")
        print()
        print("設定例（.env）:")
        print('  IMAP_HOST=sv***.xserver.jp')
        print('  IMAP_PASSWORD=your_password')
        print('  IMAP_USER=shiraishi@dellaforce.com')
        sys.exit(1)

    if not HAS_WINOTIFY:
        print("警告: winotifyがインストールされていません。")
        print("  pip install winotify")
        print("  インストール後に再起動してください。")
        print()

    print(f"[{now()}] 請求書メール通知システム起動")
    print(f"  監視対象: {IMAP_USER}")
    print(f"  IMAPサーバー: {IMAP_HOST}:{IMAP_PORT}")
    print(f"  チェック間隔: {CHECK_INTERVAL}秒")
    print(f"  検知キーワード: 件名に「{KEYWORD}」")
    print()

    # 初回: 既存メールをスキャンして既読登録（通知は出さない）
    if not STATE_FILE.exists():
        print(f"[{now()}] 初回起動: 既存メールをスキャン中...")
        seen_uids = set()
        try:
            mail = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
            mail.login(IMAP_USER, IMAP_PASSWORD)
            mail.select("INBOX")
            status, data = mail.uid("search", None, "ALL")
            if status == "OK":
                for uid_bytes in data[0].split():
                    seen_uids.add(uid_bytes.decode())
            save_seen_uids(seen_uids)
            mail.logout()
            print(f"[{now()}] 既存メール {len(seen_uids)} 件を既読登録しました")
        except Exception as e:
            print(f"[{now()}] 初回スキャンエラー: {e}")
            sys.exit(1)

    # メインループ
    while True:
        try:
            new_count = check_invoice_emails()
            if new_count > 0:
                print(f"[{now()}] 新着請求書メール {new_count} 件を通知しました")
            else:
                print(f"[{now()}] 新着なし")
        except KeyboardInterrupt:
            print(f"\n[{now()}] 終了します")
            break
        except Exception as e:
            print(f"[{now()}] エラー: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
