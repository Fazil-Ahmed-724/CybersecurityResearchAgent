from apscheduler.schedulers.background import BackgroundScheduler

from app.jobs.scheduled_ingestion_job import run_scheduled_ingestion

scheduler = BackgroundScheduler(timezone="UTC")


def start_scheduler():
    # every 30 minutes
    scheduler.add_job(
        run_scheduled_ingestion,
        trigger="interval",
        minutes=30,
        id="scheduled_article_ingestion",
        replace_existing=True,
    )

    if not scheduler.running:
        scheduler.start()

    print("[Scheduler] Scheduled article ingestion every 30 minutes.")
