import traceback as tb
from datetime import datetime, UTC

from sqlalchemy.orm import Session

from app.models.failed_task import FailedTask


class FailureLoggerService:
    def __init__(self, db: Session):
        self.db = db

    def log_failure(
        self,
        task_name: str,
        stage: str,
        error: Exception | str,
        article_id: int | None = None,
        retry_count: int = 0,
        traceback_text: str | None = None,
    ) -> FailedTask:
        if traceback_text is None and isinstance(error, Exception):
            traceback_text = tb.format_exc()

        failed_task = FailedTask(
            task_name=task_name,
            article_id=article_id,
            stage=stage,
            error_message=str(error),
            traceback=traceback_text,
            retry_count=retry_count,
            is_resolved=False,
            created_at=datetime.now(UTC),
        )

        self.db.add(failed_task)
        self.db.commit()
        self.db.refresh(failed_task)

        return failed_task

    def mark_resolved(
        self,
        task_name: str,
        article_id: int | None,
        stage: str | None = None,
    ) -> int:
        query = self.db.query(FailedTask).filter(
            FailedTask.task_name == task_name,
            FailedTask.article_id == article_id,
            FailedTask.is_resolved.is_(False),
        )

        if stage:
            query = query.filter(FailedTask.stage == stage)

        rows = query.all()
        count = 0

        for row in rows:
            row.is_resolved = True
            row.resolved_at = datetime.now(UTC)
            count += 1

        if count:
            self.db.commit()

        return count