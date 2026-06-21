from datetime import datetime, UTC

from celery import Task

from celery_app import celery_app
from app.database.db import SessionLocal
from app.models.article import Article
from app.services.article_scraper import ArticleScraperService
from app.services.embedding_service import EmbeddingService
from app.services.failure_logger_service import FailureLoggerService
from app.services.summary_service import SummaryService


class BaseArticleTask(Task):
    autoretry_for = ()
    retry_backoff = True
    retry_jitter = True
    retry_kwargs = {"max_retries": 3}


@celery_app.task(
    bind=True,
    base=BaseArticleTask,
    name="app.tasks.article_tasks.process_article_task",
)
def process_article_task(self, article_id: int):
    db = SessionLocal()
    task_name = "app.tasks.article_tasks.process_article_task"
    failure_logger = FailureLoggerService(db)

    try:
        article = db.query(Article).filter(Article.id == article_id).first()

        if not article:
            print(f"[Task] Article not found: {article_id}")
            return

        print("\n========================================")
        print(f"[Task] Processing article #{article.id}")
        print(f"[Task] Title  : {article.title}")
        print(f"[Task] Source : {article.source}")
        print(f"[Task] URL    : {article.url}")
        print("========================================\n")

        # Fully done? skip
        if (
            article.is_processed
            and article.content
            and article.summary_generated
            and article.embedding_generated
        ):
            print(f"[Task] Article #{article.id} already fully processed. Skipping.")
            return

        scraper = ArticleScraperService()
        summary_service = SummaryService()
        embedding_service = EmbeddingService()

        # --------------------------------------------------
        # 1) CONTENT / SCRAPING
        # --------------------------------------------------
        content = (article.content or "").strip()

        if not content:
            try:
                content = scraper.scrape(article.url, article.source)

                if not content or not content.strip():
                    raise ValueError("Scraper returned empty content")

                article.content = content
                article.scraped_at = datetime.now(UTC)
                db.commit()

                failure_logger.mark_resolved(
                    task_name=task_name,
                    article_id=article.id,
                    stage="scrape",
                )

                print(f"[Task] Content scraped for article #{article.id}")

            except Exception as scrape_error:
                db.rollback()

                failure_logger.log_failure(
                    task_name=task_name,
                    article_id=article.id,
                    stage="scrape",
                    error=scrape_error,
                    retry_count=self.request.retries,
                )

                print(
                    f"[Task] Content scraping failed for article #{article.id}: "
                    f"{scrape_error}"
                )
                raise

        if not article.scraped_at:
            article.scraped_at = datetime.now(UTC)

        # --------------------------------------------------
        # 2) SUMMARY
        # --------------------------------------------------
        # If summary already exists, keep it
        if article.summary and article.summary.strip():
            article.summary_generated = True
            failure_logger.mark_resolved(
                task_name=task_name,
                article_id=article.id,
                stage="summary",
            )
            print(f"[Task] Summary already exists for article #{article.id}")
        else:
            try:
                summary = summary_service.generate_summary(content)

                if summary and summary.strip():
                    article.summary = summary
                    article.summary_generated = True
                    db.commit()

                    failure_logger.mark_resolved(
                        task_name=task_name,
                        article_id=article.id,
                        stage="summary",
                    )

                    print(f"[Task] Summary generated for article #{article.id}")
                else:
                    raise ValueError("Summary service returned empty summary")

            except Exception as summary_error:
                db.rollback()

                failure_logger.log_failure(
                    task_name=task_name,
                    article_id=article.id,
                    stage="summary",
                    error=summary_error,
                    retry_count=self.request.retries,
                )

                print(
                    f"[Task] Summary generation failed for article #{article.id}: "
                    f"{summary_error}"
                )

                # Retry summary-like transient issues only a few times
                message = str(summary_error).lower()
                should_retry = (
                    "429" in message
                    or "rate limit" in message
                    or "timeout" in message
                    or "connection" in message
                )

                if should_retry and self.request.retries < 3:
                    countdown = 60 * (self.request.retries + 1)
                    print(
                        f"[Task] Retrying article #{article.id} summary in "
                        f"{countdown}s (retry {self.request.retries + 1}/3)"
                    )
                    raise self.retry(exc=summary_error, countdown=countdown)

                # Do NOT fail the whole article if summary failed permanently
                article.summary_generated = bool(
                    article.summary and article.summary.strip()
                )
                db.commit()

        # --------------------------------------------------
        # 3) EMBEDDING
        # --------------------------------------------------
        if article.embedding_generated and article.embedding is not None:
            failure_logger.mark_resolved(
                task_name=task_name,
                article_id=article.id,
                stage="embedding",
            )
            print(f"[Task] Embedding already exists for article #{article.id}")
        else:
            try:
                embedding = embedding_service.generate_article_embedding(
                    title=article.title or "",
                    summary=article.summary or "",
                    content=content,
                )

                if not embedding:
                    raise ValueError("Embedding service returned empty embedding")

                article.embedding = embedding
                article.embedding_generated = True
                db.commit()

                failure_logger.mark_resolved(
                    task_name=task_name,
                    article_id=article.id,
                    stage="embedding",
                )

                print(f"[Task] Embedding generated for article #{article.id}")

            except Exception as embedding_error:
                db.rollback()

                failure_logger.log_failure(
                    task_name=task_name,
                    article_id=article.id,
                    stage="embedding",
                    error=embedding_error,
                    retry_count=self.request.retries,
                )

                print(
                    f"[Task] Embedding generation failed for article #{article.id}: "
                    f"{embedding_error}"
                )

                # Embedding is critical for retrieval, so fail the task
                raise

        # --------------------------------------------------
        # 4) FINAL STATUS
        # --------------------------------------------------
        article.is_processed = bool(article.content and article.content.strip())
        article.processed_at = datetime.now(UTC)

        # If summary exists from RSS or generation, ensure flag reflects that
        article.summary_generated = bool(article.summary and article.summary.strip())

        db.commit()

        print(
            f"[Task] Article #{article.id} processed successfully. "
            f"is_processed={article.is_processed}, "
            f"summary_generated={article.summary_generated}, "
            f"embedding_generated={article.embedding_generated}"
        )

    except Exception as task_error:
        db.rollback()
        print(f"[Task] Error processing article #{article_id}: {task_error}")
        raise

    finally:
        db.close()
