from fastapi import FastAPI

app = FastAPI(
    title="Cyber Security Research Agent"
)

@app.get("/")
def home():
    return {
        "message": "Cyber Security Research Agent Running"
    }