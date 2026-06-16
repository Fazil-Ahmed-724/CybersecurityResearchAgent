from app.database.base import Base
from app.database.db import engine

from app.models.article import Article


Base.metadata.create_all(bind=engine)

print("Tables Created")