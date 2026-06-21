from datetime import datetime, UTC
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db import SessionLocal
from app.models.article import Article
from app.services.summary_service import SummaryService


def backfill_missing_summaries():
    db = SessionLocal()
    summary_service = SummaryService()

    updated = 0
    skipped = 0
    failed = 0

    try:
        articles = (
            db.query(Article)
            .filter(Article.content.isnot(None))
            .filter(Article.content != "")
            .filter(Article.summary_generated.is_(False))
            .order_by(Article.id.asc())
            .all()
        )

        print("\n========== SUMMARY BACKFILL START ==========")
        print(f"[Summary Backfill] Articles needing summary: {len(articles)}")
        print("============================================\n")

        for index, article in enumerate(articles, start=1):
            print(
                f"[Summary Backfill] ({index}/{len(articles)}) "
                f"Processing article #{article.id}"
            )
            print(f"[Summary Backfill] Title  : {article.title}")
            print(f"[Summary Backfill] Source : {article.source}")
            print(f"[Summary Backfill] URL    : {article.url}")

            # If summary already exists in DB text, just mark flag true
            if article.summary and article.summary.strip():
                article.summary_generated = True
                article.processed_at = datetime.now(UTC)
                db.commit()
                updated += 1
                print(
                    f"[Summary Backfill] Existing summary found. "
                    f"Marked article #{article.id} as summary_generated=True\n"
                )
                continue

            try:
                summary = summary_service.generate_summary(article.content)

                if summary and summary.strip():
                    article.summary = summary
                    article.summary_generated = True
                    article.processed_at = datetime.now(UTC)

                    db.commit()
                    updated += 1

                    print(
                        f"[Summary Backfill] Summary generated for article "
                        f"#{article.id}\n"
                    )
                else:
                    skipped += 1
                    print(
                        f"[Summary Backfill] No summary returned for article "
                        f"#{article.id}\n"
                    )

            except Exception as e:
                db.rollback()
                failed += 1
                print(
                    f"[Summary Backfill] Failed article #{article.id}: {e}\n"
                )

        print("\n========== SUMMARY BACKFILL SUMMARY ==========")
        print(f"Updated : {updated}")
        print(f"Skipped : {skipped}")
        print(f"Failed  : {failed}")
        print("==============================================\n")

    finally:
        db.close()


if __name__ == "__main__":
    backfill_missing_summaries()
