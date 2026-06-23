from app.database.db import SessionLocal
from app.services.article_ingestion import ArticleIngestionService
from app.services.ingestion_run_logger_service import IngestionRunLoggerService


def main():
    db = SessionLocal()
    run_logger = IngestionRunLoggerService(db)
    run = run_logger.start_run(source="all")

    try:
        result = ArticleIngestionService().ingest()

        run_logger.finish_success(
            run_id=run.id,
            fetched_count=result.get("fetched_count", 0),
            inserted_count=result.get("inserted_count", 0),
            requeued_count=result.get("requeued_count", 0),
            skipped_existing_count=result.get("skipped_existing_count", 0),
            failed_count=result.get("failed_count", 0),
        )

    except Exception as e:
        run_logger.finish_failed(
            run_id=run.id,
            error_message=str(e),
        )
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()