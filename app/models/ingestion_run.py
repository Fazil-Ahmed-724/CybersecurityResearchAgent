from sqlalchemy import Column, Integer, String, DateTime, Text
from app.database.base import Base


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)

    status = Column(String(50), nullable=False, default="running")
    source = Column(String(100), nullable=True)  # optional: "all", "The Hacker News", etc.

    fetched_count = Column(Integer, nullable=False, default=0)
    inserted_count = Column(Integer, nullable=False, default=0)
    requeued_count = Column(Integer, nullable=False, default=0)
    skipped_existing_count = Column(Integer, nullable=False, default=0)
    failed_count = Column(Integer, nullable=False, default=0)

    error_message = Column(Text, nullable=True)