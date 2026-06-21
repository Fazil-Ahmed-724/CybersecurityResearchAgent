from datetime import datetime, UTC
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.article_ingestion import ArticleIngestionService


def run_scheduled_ingestion():
    print(
        f"\n[Scheduled Ingestion] Started at {datetime.now(UTC).isoformat()}"
    )

    try:
        service = ArticleIngestionService()
        service.ingest()
        print("[Scheduled Ingestion] Completed successfully.")
    except Exception as e:
        print(f"[Scheduled Ingestion] Failed: {e}")
        raise


if __name__ == "__main__":
    run_scheduled_ingestion()
