"""
定期自動実行スケジューラー
.envの SCHEDULE_CRON で実行タイミングを設定する

例:
  SCHEDULE_CRON=0 9 * * 1-5   → 平日9:00に実行
  SCHEDULE_CRON=0 8 * * *     → 毎日8:00に実行
  SCHEDULE_ENABLED=false       → 無効化
"""

import os
from dotenv import load_dotenv

load_dotenv()

SCHEDULE_ENABLED = os.getenv("SCHEDULE_ENABLED", "false").lower() == "true"
SCHEDULE_CRON    = os.getenv("SCHEDULE_CRON", "0 9 * * 1-5")  # デフォルト: 平日9:00


def init_scheduler(run_func):
    """
    APSchedulerを初期化して定期実行を登録する
    run_func: _run_check(from_date, to_date) と同じシグネチャ
    """
    if not SCHEDULE_ENABLED:
        print("[スケジューラー] 無効（SCHEDULE_ENABLED=false）")
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("[スケジューラー] apschedulerが未インストール。定期実行は無効。")
        return

    parts = SCHEDULE_CRON.split()
    if len(parts) != 5:
        print(f"[スケジューラー] SCHEDULE_CRONの形式が不正: {SCHEDULE_CRON}")
        return

    minute, hour, day, month, day_of_week = parts

    scheduler = BackgroundScheduler(timezone="Asia/Tokyo")
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
    scheduler.start()
    print(f"[スケジューラー] 有効 — {SCHEDULE_CRON}（Asia/Tokyo）")
