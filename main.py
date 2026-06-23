from fastapi import FastAPI

from app.api.admin_routes import router as admin_router
from app.api.routes import router as main_router

app = FastAPI(title="Cyber Security Research Agent")


@app.get("/")
def home():
    return {
        "message": "Cyber Security Research Agent Running"
    }


app.include_router(main_router)
app.include_router(admin_router)