from sqlalchemy import Column, Integer, String, Text, DateTime

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