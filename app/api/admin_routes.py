from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.database.db import get_db
from app.models.article import Article
from app.models.failed_task import FailedTask
from app.models.ingestion_run import IngestionRun

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/health")
def admin_health(db: Session = Depends(get_db)):
    total_articles = db.query(func.count(Article.id)).scalar() or 0

    incomplete_articles = (
        db.query(func.count(Article.id))
        .filter(
            or_(
                Article.content == None,
                Article.content == "",
                Article.summary_generated == False,
                Article.embedding_generated == False,
                Article.is_processed == False,
            )
        )
        .scalar()
        or 0
    )

    unresolved_failed_tasks = (
        db.query(func.count(FailedTask.id))
        .filter(FailedTask.is_resolved == False)
        .scalar()
        or 0
    )

    last_run = db.query(IngestionRun).order_by(IngestionRun.id.desc()).first()

    source_counts = (
        db.query(
            Article.source,
            func.count(Article.id).label("count")
        )
        .group_by(Article.source)
        .all()
    )

    return {
        "total_articles": total_articles,
        "incomplete_articles": incomplete_articles,
        "unresolved_failed_tasks": unresolved_failed_tasks,
        "last_ingestion_run": {
            "id": last_run.id if last_run else None,
            "status": last_run.status if last_run else None,
            "started_at": last_run.started_at if last_run else None,
            "finished_at": last_run.finished_at if last_run else None,
            "fetched_count": last_run.fetched_count if last_run else 0,
            "inserted_count": last_run.inserted_count if last_run else 0,
            "requeued_count": last_run.requeued_count if last_run else 0,
            "skipped_existing_count": last_run.skipped_existing_count if last_run else 0,
            "failed_count": last_run.failed_count if last_run else 0,
        },
        "source_counts": [
            {"source": row.source, "count": row.count}
            for row in source_counts
        ],
    }