from fastapi import FastAPI

from app.api.routes import router


app = FastAPI(
    title="Cybersecurity Research Agent"
)

app.include_router(router)