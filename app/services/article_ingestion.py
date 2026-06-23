from datetime import datetime, UTC

from app.database.db import SessionLocal
from app.models.article import Article
from app.services.rss_service import RSSService
from app.tasks.article_tasks import process_article_task


class ArticleIngestionService:
    def __init__(self):
        self.rss_service = RSSService()

    def ingest(self) -> dict:
        """
        Fetch RSS articles from all configured feeds,
        insert only new ones into DB,
        requeue incomplete existing articles,
        and queue Celery background task for processing.

        Returns:
            {
                "fetched_count": int,
                "inserted_count": int,
                "requeued_count": int,
                "skipped_existing_count": int,
                "failed_count": int,
            }
        """
        db = SessionLocal()

        inserted_count = 0
        requeued_count = 0
        skipped_existing_count = 0
        failed_count = 0

        try:
            all_articles = self.rss_service.fetch_articles()
            fetched_count = len(all_articles)

            print("\n========== INGESTION START ==========\n")
            print(f"[Ingestion] Total RSS articles fetched: {fetched_count}\n")

            for article_data in all_articles:
                try:
                    title = (article_data.get("title") or "").strip()
                    source = (article_data.get("source") or "").strip()
                    url = (article_data.get("link") or "").strip()
                    summary = (article_data.get("summary") or "").strip()
                    published_at = article_data.get("published_at")

                    if not url:
                        failed_count += 1
                        print("[Ingestion] Skipped article with missing URL")
                        continue

                    print("----------------------------------------")
                    print(f"[Ingestion] Source : {source}")
                    print(f"[Ingestion] Title  : {title}")
                    print(f"[Ingestion] URL    : {url}")

                    # Duplicate check by URL
                    existing = db.query(Article).filter(Article.url == url).first()
                    if existing:
                        needs_processing = (
                            not existing.content
                            or not existing.is_processed
                            or not existing.summary_generated
                            or not existing.embedding_generated
                        )

                        if needs_processing:
                            process_article_task.delay(existing.id)
                            requeued_count += 1
                            print(
                                "[Ingestion] Requeued existing incomplete "
                                f"article #{existing.id}"
                            )
                        else:
                            skipped_existing_count += 1
                            print("[Ingestion] Skipped: already processed")

                        continue

                    if not published_at:
                        published_at = datetime.now(UTC)

                    article = Article(
                        title=title,
                        source=source,
                        url=url,
                        published_at=published_at,
                        summary=summary if summary else None,
                        content=None,
                        scraped_at=None,
                        is_processed=False,
                        summary_generated=bool(summary),
                        embedding_generated=False,
                        processed_at=None,
                    )

                    db.add(article)
                    db.commit()
                    db.refresh(article)

                    inserted_count += 1
                    print(f"[Ingestion] Inserted article #{article.id}")

                    # Queue Celery background task
                    process_article_task.delay(article.id)
                    print(f"[Ingestion] Queued background task for article #{article.id}")

                except Exception as article_error:
                    failed_count += 1
                    db.rollback()
                    print(
                        f"[Ingestion] Failed article "
                        f"'{article_data.get('title', 'Unknown')}' : {article_error}"
                    )

            print("\n========== INGESTION COMPLETE ==========")
            print(f"[Ingestion] Total RSS fetched        : {fetched_count}")
            print(f"[Ingestion] New articles inserted   : {inserted_count}")
            print(f"[Ingestion] Existing requeued       : {requeued_count}")
            print(f"[Ingestion] Existing skipped        : {skipped_existing_count}")
            print(f"[Ingestion] Failed during ingestion : {failed_count}")
            print("========================================\n")

            return {
                "fetched_count": fetched_count,
                "inserted_count": inserted_count,
                "requeued_count": requeued_count,
                "skipped_existing_count": skipped_existing_count,
                "failed_count": failed_count,
            }

        finally:
            db.close()