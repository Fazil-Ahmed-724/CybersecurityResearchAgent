from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean
)

from pgvector.sqlalchemy import Vector

from app.database.base import Base


class Article(Base):
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True)

    title = Column(Text, nullable=False)

    source = Column(String(100), nullable=False)

    url = Column(Text, unique=True, nullable=False)

    content = Column(Text, nullable=True)

    summary = Column(Text, nullable=True)

    published_at = Column(DateTime, nullable=True)

    scraped_at = Column(DateTime, nullable=True)

    # Pipeline Status Flags
    is_processed = Column(
        Boolean,
        default=False,
        nullable=False
    )

    summary_generated = Column(
        Boolean,
        default=False,
        nullable=False
    )

    embedding_generated = Column(
        Boolean,
        default=False,
        nullable=False
    )
    
    processed_at = Column(
        DateTime, 
        nullable=True
    )

    # Vector Embedding
    embedding = Column(
        Vector(768),
        nullable=True
    )