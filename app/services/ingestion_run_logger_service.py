from app.models.ingestion_run import IngestionRun


class IngestionRunLoggerService:
    def __init__(self, db):
        self.db = db

    def start_run(self, source: str = "all") -> IngestionRun:
        from datetime import datetime, UTC

        run = IngestionRun(
            started_at=datetime.now(UTC),
            status="running",
            source=source,
            fetched_count=0,
            inserted_count=0,
            requeued_count=0,
            skipped_existing_count=0,
            failed_count=0,
        )
        self.db.add(run)
        self.db.commit()
        self.db.refresh(run)
        return run

    def finish_success(
        self,
        run_id: int,
        fetched_count: int,
        inserted_count: int,
        requeued_count: int,
        skipped_existing_count: int,
        failed_count: int = 0,
    ):
        from datetime import datetime, UTC

        run = self.db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
        if not run:
            return

        run.finished_at = datetime.now(UTC)
        run.status = "success"
        run.fetched_count = fetched_count
        run.inserted_count = inserted_count
        run.requeued_count = requeued_count
        run.skipped_existing_count = skipped_existing_count
        run.failed_count = failed_count

        self.db.commit()

    def finish_failed(
        self,
        run_id: int,
        error_message: str,
        fetched_count: int = 0,
        inserted_count: int = 0,
        requeued_count: int = 0,
        skipped_existing_count: int = 0,
        failed_count: int = 1,
    ):
        from datetime import datetime, UTC

        run = self.db.query(IngestionRun).filter(IngestionRun.id == run_id).first()
        if not run:
            return

        run.finished_at = datetime.now(UTC)
        run.status = "failed"
        run.error_message = error_message[:5000] if error_message else None
        run.fetched_count = fetched_count
        run.inserted_count = inserted_count
        run.requeued_count = requeued_count
        run.skipped_existing_count = skipped_existing_count
        run.failed_count = failed_count

        self.db.commit()