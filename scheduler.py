"""scheduler.py — Kunlik vazifalar"""

import logging
from datetime import datetime
from telegram.ext import Application

logger = logging.getLogger("Scheduler")


def setup_scheduler(app: Application):
    jq = app.job_queue
    if jq is None:
        logger.warning("JobQueue yo'q. pip install 'python-telegram-bot[job-queue]'")
        return
    jq.run_daily(
        kunlik_snapshot,
        time=datetime.strptime("00:00", "%H:%M").time(),
        name="daily_snap"
    )
    logger.info("Scheduler tayyor.")


async def kunlik_snapshot(context):
    db = context.bot_data.get("db")
    if db:
        db.snapshot_analytics()
        logger.info("Kunlik analitika saqlandi.")
