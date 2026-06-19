from sqlalchemy import Column
from sqlalchemy import DateTime
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Text
from sqlalchemy.sql import func

from app.database.base import Base


class ChatSummary(Base):
    __tablename__ = "chat_summaries"

    id = Column(
        Integer,
        primary_key=True
    )

    chat_id = Column(
        Integer,
        ForeignKey("chats.id"),
        unique=True,
        nullable=False
    )

    summary = Column(
        Text,
        nullable=False
    )

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )
