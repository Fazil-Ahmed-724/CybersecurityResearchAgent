from app.database.db import engine
from app.models.chat import Chat
from app.models.message import Message
from app.database.base import Base

Base.metadata.create_all(
    bind=engine
)

print(
    "Chat tables created"
)
