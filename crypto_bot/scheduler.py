"""Schedule prediction runs at 06:00 and 16:00 Africa/Johannesburg."""

from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from crypto_bot import config
from crypto_bot.pipeline import run_once

logger = logging.getLogger(__name__)


def start_scheduler() -> None:
    tz = ZoneInfo(config.TIMEZONE)
    scheduler = BlockingScheduler(timezone=tz)

    for hour in config.RUN_HOURS:
        trigger = CronTrigger(hour=hour, minute=0, timezone=tz)
        scheduler.add_job(
            run_once,
            trigger=trigger,
            id=f"predict_{hour:02d}00",
            name=f"Crypto predictions {hour:02d}:00 SAST",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=3600,
        )
        logger.info("Scheduled job at %02d:00 %s", hour, config.TIMEZONE)

    logger.info(
        "Scheduler started. Waiting for 06:00 and 16:00 %s…", config.TIMEZONE
    )
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
