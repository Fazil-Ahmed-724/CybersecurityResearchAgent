from app.database.base import Base
from app.database.db import engine

from app.models.article import Article
from app.models.chat import Chat
from app.models.message import Message


Base.metadata.create_all(bind=engine)

print("Tables Created")