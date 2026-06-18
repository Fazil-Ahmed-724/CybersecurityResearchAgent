from fastapi import FastAPI
from app.api.routes import router

from app.api.chat_routes import (
    router as chat_router
)

from app.database.base import Base
from app.database.db import engine

from app.models.user import User
from app.models.chat import Chat
from app.models.message import Message
from app.models.article import Article

app = FastAPI(
    title="Cybersecurity Research Agent"
)

# Create tables on startup
Base.metadata.create_all(bind=engine)

app.include_router(router)

app.include_router(
    chat_router
)