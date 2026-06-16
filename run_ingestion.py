from app.services.article_ingestion import (
    ArticleIngestionService
)

ArticleIngestionService().ingest_hackernews()

print("Done")