from apscheduler.schedulers.background import (
    BackgroundScheduler
)

from app.jobs.article_ingestion_job import (
    run_ingestion
)

scheduler = BackgroundScheduler()

scheduler.add_job(
    run_ingestion,
    "interval",
    minutes=5,
    id="rss_ingestion"
)
