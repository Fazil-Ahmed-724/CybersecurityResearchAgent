from app.services.article_ingestion import (
    ArticleIngestionService
)


def run_ingestion():
    """
    Scheduled job to ingest articles from RSS feeds.
    Runs automatically every X minutes.
    """

    print(
        "\n[Scheduler] Starting scheduled ingestion..."
    )

    try:

        service = ArticleIngestionService()

        count = service.ingest()

        print(
            f"[Scheduler] Ingested {count} articles"
        )

    except Exception as e:

        print(
            f"[Scheduler] Error during ingestion: {e}"
        )
