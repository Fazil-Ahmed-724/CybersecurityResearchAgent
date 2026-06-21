from datetime import datetime, UTC
from pathlib import Path
import sys
import time

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.database.db import SessionLocal
from app.models.article import Article
from app.services.article_scraper import ArticleScraperService
from app.services.embedding_service import EmbeddingService


def backfill_article_content(limit: int | None = None):
    """
    Backfill article content + embeddings for rows where content IS NULL.

    What this script does:
    1) Finds articles where content is NULL
    2) Scrapes full article content from the article URL
    3) Saves content into the article row
    4) Regenerates embedding using title + summary + content
    5) Updates processing flags/timestamps

    Args:
        limit: Optional. If provided, only process the first N NULL-content articles.
               Useful for debugging, e.g. backfill_article_content(limit=1)
    """

    db: Session = SessionLocal()
    scraper = ArticleScraperService()
    embedding_service = EmbeddingService()

    try:
        query = (
            db.query(Article)
            .filter(Article.content.is_(None))
            .order_by(Article.id.asc())
        )

        if limit:
            query = query.limit(limit)

        articles = query.all()
        total = len(articles)

        print("\n========== BACKFILL START ==========")
        print(f"[Backfill] Articles with NULL content: {total}")
        if limit:
            print(f"[Backfill] Debug limit enabled: {limit}")
        print("====================================")

        updated = 0
        skipped = 0
        failed = 0
        embedding_failed = 0

        start_all = time.time()

        for index, article in enumerate(articles, start=1):
            article_start = time.time()

            print(
                f"\n[Backfill] ({index}/{total}) Processing article #{article.id}"
            )
            print(f"[Backfill] Title  : {article.title}")
            print(f"[Backfill] Source : {article.source}")
            print(f"[Backfill] URL    : {article.url}")

            try:
                # 1) Scrape full content
                content = scraper.scrape(
                    url=article.url,
                    source=article.source
                )

                if not content or not content.strip():
                    print(
                        f"[Backfill] No content extracted for article #{article.id}"
                    )
                    skipped += 1
                    continue

                # 2) Save content + processing metadata
                article.content = content
                article.scraped_at = datetime.now(UTC)
                article.is_processed = True
                article.processed_at = datetime.now(UTC)

                # If summary already exists from RSS, mark summary_generated accordingly
                article.summary_generated = bool(article.summary and article.summary.strip())

                # 3) Rebuild embedding using title + summary + content
                text_for_embedding = (
                    f"Title: {article.title}\n\n"
                    f"Summary:\n{article.summary or ''}\n\n"
                    f"Content:\n{content}"
                )

                try:
                    embedding = embedding_service.generate_embedding(
                        text_for_embedding
                    )
                    article.embedding = embedding
                    article.embedding_generated = True
                    print(f"[Backfill] Embedding generated for article #{article.id}")

                except Exception as embedding_error:
                    embedding_failed += 1
                    article.embedding_generated = False

                    print(
                        f"[Backfill] Embedding error for article #{article.id}: "
                        f"{embedding_error}"
                    )

                # 4) Commit article update
                db.add(article)
                db.commit()

                updated += 1

                duration = round(time.time() - article_start, 2)
                print(
                    f"[Backfill] Updated article #{article.id} "
                    f"in {duration}s"
                )

            except Exception as article_error:
                db.rollback()
                failed += 1

                duration = round(time.time() - article_start, 2)
                print(
                    f"[Backfill] Failed article #{article.id} "
                    f"after {duration}s: {article_error}"
                )

        total_duration = round(time.time() - start_all, 2)

        print("\n========== BACKFILL SUMMARY ==========")
        print(f"Total found        : {total}")
        print(f"Updated            : {updated}")
        print(f"Skipped (no content): {skipped}")
        print(f"Failed             : {failed}")
        print(f"Embedding failed   : {embedding_failed}")
        print(f"Total duration     : {total_duration}s")
        print("======================================")

    except Exception as e:
        db.rollback()
        print(f"[Backfill] Fatal error: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    # Normal full backfill:
    backfill_article_content()

    # Debug mode example:
    # backfill_article_content(limit=1)
