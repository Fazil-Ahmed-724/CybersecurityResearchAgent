from fastapi import FastAPI
from app.api.routes import router
from app.api.admin_routes import router as admin_router
from app.api.chat_routes import (
    router as chat_router
)

from app.database.base import Base
from app.database.db import engine

from app.models.user import User
from app.models.chat import Chat
from app.models.message import Message
from app.models.chat_summary import ChatSummary
from app.models.article import Article
from app.models.failed_task import FailedTask
from app.api.auth_routes import router as auth_router

# Initialize scheduler
from app.jobs.scheduler import start_scheduler
from app.jobs.article_ingestion_job import run_ingestion

app = FastAPI(
    title="Cybersecurity Research Agent"
)

# Create tables on startup
Base.metadata.create_all(bind=engine)

@app.on_event("startup")
def startup():
    
    # Start scheduled article ingestion
    start_scheduler()
    print("[FastAPI] Scheduler Started")
    
    # Run immediate ingestion on startup
    try:
        run_ingestion()
    except Exception as e:
        print(f"[FastAPI] Immediate ingestion failed: {e}")

app.include_router(router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(admin_router)