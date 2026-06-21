from dotenv import load_dotenv
import os

load_dotenv()


class Settings:
    DATABASE_URL = os.getenv("DATABASE_URL")

    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")

    GROQ_API_KEY = os.getenv("GROQ_API_KEY")

    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")

    HACKERNEWS_RSS = os.getenv("HACKERNEWS_RSS")
    BLEEPINGCOMPUTER_RSS = os.getenv("BLEEPINGCOMPUTER_RSS")

    REDIS_URL = os.getenv("REDIS_URL")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND")

    SQL_ECHO = os.getenv(
        "SQL_ECHO",
        "false"
    ).lower() == "true"


settings = Settings()
