"""
定期自動実行スケジューラー
.envの SCHEDULE_CRON で実行タイミングを設定する

例:
  SCHEDULE_CRON=0 9 * * 1-5   → 平日9:00に実行
  SCHEDULE_CRON=0 8 * * *     → 毎日8:00に実行
  SCHEDULE_ENABLED=false       → 未入金チェック自動実行を無効化
                                （トークン失効チェックは常に有効）
"""

import os
from dotenv import load_dotenv

load_dotenv()

SCHEDULE_ENABLED = os.getenv("SCHEDULE_ENABLED", "false").lower() == "true"
SCHEDULE_CRON    = os.getenv("SCHEDULE_CRON", "0 9 * * 1-5")  # デフォルト: 平日9:00


def init_scheduler(run_func, token_check_func=None):
    """
    APSchedulerを初期化して定期実行を登録する
    run_func:          _run_check と同じシグネチャ（未入金チェック自動実行）
    token_check_func:  _check_all_tokens（MFトークン失効チェック、毎日9:00）
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("[スケジューラー] apschedulerが未インストール。定期実行は無効。")
        return

    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")

    # ── 未入金チェック自動実行 ──
    if SCHEDULE_ENABLED:
        parts = SCHEDULE_CRON.split()
        if len(parts) == 5:
            minute, hour, day, month, day_of_week = parts
            scheduler.add_job(
                func=lambda: run_func(),
                trigger=CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                    timezone="Asia/Tokyo",
                ),
                id="unpaid_check",
                name="未入金チェック自動実行",
                replace_existing=True,
            )
            print(f"[スケジューラー] 有効 {SCHEDULE_CRON}（Asia/Tokyo）")
        else:
            print(f"[スケジューラー] SCHEDULE_CRONの形式が不正: {SCHEDULE_CRON}")
    else:
        print("[スケジューラー] 無効（SCHEDULE_ENABLED=false）")

    # ── MFトークン失効チェック（毎日09:00、常に有効）──
    if token_check_func:
        scheduler.add_job(
            func=token_check_func,
            trigger=CronTrigger(hour=9, minute=0, timezone="Asia/Tokyo"),
            id="token_check",
            name="MFトークン失効チェック",
            replace_existing=True,
        )
        print("[トークンチェッカー] 有効 — 毎日09:00（Asia/Tokyo）")

    scheduler.start()
