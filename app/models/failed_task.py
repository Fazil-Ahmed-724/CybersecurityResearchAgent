from datetime import datetime, UTC

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean

from app.database.base import Base


class FailedTask(Base):
    __tablename__ = "failed_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String(255), nullable=False)
    article_id = Column(Integer, nullable=True, index=True)
    stage = Column(String(100), nullable=False)  # scrape / summary / embedding / unknown
    error_message = Column(Text, nullable=False)
    traceback = Column(Text, nullable=True)

    retry_count = Column(Integer, default=0, nullable=False)
    is_resolved = Column(Boolean, default=False, nullable=False)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC), nullable=False)
    resolved_at = Column(DateTime, nullable=True)