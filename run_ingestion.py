from app.services.article_ingestion import ArticleIngestionService

if __name__ == "__main__":
    ArticleIngestionService().ingest()
    print("Done")