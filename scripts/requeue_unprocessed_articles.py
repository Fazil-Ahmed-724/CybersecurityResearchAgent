import argparse
from pathlib import Path
import sys

from sqlalchemy import or_

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db import SessionLocal
from app.models.article import Article
from app.tasks.article_tasks import process_article_task


def requeue_unprocessed_articles(limit: int | None = None) -> int:
    db = SessionLocal()
    queued_count = 0

    try:
        query = (
            db.query(Article)
            .filter(
                or_(
                    Article.content.is_(None),
                    Article.content == "",
                    Article.is_processed.is_(False),
                    Article.summary_generated.is_(False),
                    Article.embedding_generated.is_(False),
                )
            )
            .order_by(Article.id.asc())
        )

        if limit:
            query = query.limit(limit)

        articles = query.all()

        print("\n========== REQUEUE START ==========")
        print(f"[Requeue] Incomplete articles found: {len(articles)}")

        for article in articles:
            process_article_task.delay(article.id)
            queued_count += 1

            print(
                f"[Requeue] Queued article #{article.id}: "
                f"{article.title}"
            )

        print("\n========== REQUEUE COMPLETE ==========")
        print(f"[Requeue] Articles queued: {queued_count}")
        print("======================================\n")

        return queued_count

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Queue Celery processing tasks for incomplete articles."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only queue the first N incomplete articles.",
    )

    args = parser.parse_args()
    requeue_unprocessed_articles(limit=args.limit)
