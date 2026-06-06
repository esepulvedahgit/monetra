import logging
from concurrent.futures import ThreadPoolExecutor

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()


def init_scheduler(app):
    """Initialize and start the background scheduler. Safe to call multiple times."""
    if scheduler.running:
        return

    scheduler.add_job(
        func=_weekly_report_job,
        args=[app],
        trigger='cron',
        day_of_week='mon',
        hour=10,
        minute=0,
        id='weekly_report',
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started — weekly report job scheduled every Monday at 10:00 UTC.")


def _weekly_report_job(app):
    """Batch job: generates and emails Excel reports for all opted-in users (max 5 concurrent)."""
    with app.app_context():
        from datetime import date
        from app.models import User
        from app.export.excel_builder import build_excel
        from app.email_service import send_weekly_report

        today = date.today()
        users = User.query.filter_by(weekly_report_enabled=True).all()

        if not users:
            logger.info("Weekly report job: no users opted in, skipping.")
            return

        logger.info(f"Weekly report job: processing {len(users)} user(s).")

        def process(user):
            try:
                buf = build_excel(user, today.year, today.month, today.month)
                filename = f"monetra_{user.username}_{today.year}_{today.month:02d}.xlsx"
                ok, msg = send_weekly_report(user, buf.read(), filename)
                if ok:
                    logger.info(f"Weekly report sent to {user.email}.")
                else:
                    logger.warning(f"Weekly report failed for {user.username}: {msg}")
            except Exception as e:
                logger.error(f"Weekly report error for {user.username}: {e}", exc_info=True)

        with ThreadPoolExecutor(max_workers=5) as executor:
            executor.map(process, users)

        logger.info("Weekly report job finished.")
