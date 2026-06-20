from datetime import datetime, UTC
import time
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.models.article import Article
from app.services.embedding_service import EmbeddingService


def backfill_missing_embeddings(limit: int | None = None):
    """
    Backfill embeddings for articles where embedding IS NULL.
    Uses safe truncated article text to avoid model context overflow.
    """

    db: Session = SessionLocal()
    embedding_service = EmbeddingService()

    try:
        query = (
            db.query(Article)
            .filter(Article.embedding.is_(None))
            .order_by(Article.id.asc())
        )

        if limit:
            query = query.limit(limit)

        articles = query.all()
        total = len(articles)

        print("\n========== EMBEDDING BACKFILL START ==========")
        print(f"[Embedding Backfill] Articles with NULL embedding: {total}")
        if limit:
            print(f"[Embedding Backfill] Debug limit enabled: {limit}")
        print("==============================================")

        updated = 0
        skipped = 0
        failed = 0

        start_all = time.time()

        for index, article in enumerate(articles, start=1):
            article_start = time.time()

            print(
                f"\n[Embedding Backfill] ({index}/{total}) Processing article #{article.id}"
            )
            print(f"[Embedding Backfill] Title  : {article.title}")
            print(f"[Embedding Backfill] Source : {article.source}")
            print(f"[Embedding Backfill] URL    : {article.url}")

            try:
                title = article.title or ""
                summary = article.summary or ""
                content = article.content or ""

                if not title.strip() and not summary.strip() and not content.strip():
                    print(
                        f"[Embedding Backfill] Skipped article #{article.id} "
                        f"because title/summary/content are all empty"
                    )
                    skipped += 1
                    continue

                embedding = embedding_service.generate_article_embedding(
                    title=title,
                    summary=summary,
                    content=content
                )

                article.embedding = embedding
                article.embedding_generated = True
                article.processed_at = datetime.now(UTC)

                if article.content and article.content.strip():
                    article.is_processed = True

                if article.summary and article.summary.strip():
                    article.summary_generated = True

                db.add(article)
                db.commit()

                updated += 1

                duration = round(time.time() - article_start, 2)
                print(
                    f"[Embedding Backfill] Updated article #{article.id} "
                    f"in {duration}s"
                )

            except Exception as article_error:
                db.rollback()
                failed += 1

                duration = round(time.time() - article_start, 2)
                print(
                    f"[Embedding Backfill] Failed article #{article.id} "
                    f"after {duration}s: {article_error}"
                )

        total_duration = round(time.time() - start_all, 2)

        print("\n========== EMBEDDING BACKFILL SUMMARY ==========")
        print(f"Total found   : {total}")
        print(f"Updated       : {updated}")
        print(f"Skipped       : {skipped}")
        print(f"Failed        : {failed}")
        print(f"Total duration: {total_duration}s")
        print("================================================")

    except Exception as e:
        db.rollback()
        print(f"[Embedding Backfill] Fatal error: {e}")

    finally:
        db.close()


if __name__ == "__main__":
    backfill_missing_embeddings()