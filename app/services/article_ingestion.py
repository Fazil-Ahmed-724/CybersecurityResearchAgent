from datetime import datetime, UTC
from sqlalchemy.exc import IntegrityError

from app.database.db import SessionLocal
from app.models.article import Article
from app.services.rss_service import RSSService
from app.services.embedding_service import EmbeddingService
from app.services.article_scraper import ArticleScraperService


class ArticleIngestionService:
    def __init__(self):
        self.rss_service = RSSService()
        self.embedding_service = EmbeddingService()
        self.scraper_service = ArticleScraperService()

    def ingest(self):
        """
        Ingest articles from all RSS feeds.

        Flow:
        1) Fetch RSS entries
        2) Skip duplicates by URL
        3) Scrape full article content
        4) Save article row
        5) Generate embedding from title + summary + content
        6) Update processing flags/timestamps
        """

        db = SessionLocal()
        total_inserted = 0
        total_skipped = 0
        total_failed = 0

        try:
            articles = self.rss_service.fetch_articles()

            print(f"\n[Ingestion] Total RSS articles found: {len(articles)}")

            by_source = {}

            for article_data in articles:
                source = article_data["source"]
                title = article_data["title"]
                url = article_data["link"]
                summary = article_data.get("summary", "") or ""
                published_at = article_data.get("published_at", datetime.now(UTC))

                if source not in by_source:
                    by_source[source] = {
                        "inserted": 0,
                        "skipped": 0,
                        "failed": 0
                    }

                print("\n----------------------------------------")
                print(f"[Ingestion] Source : {source}")
                print(f"[Ingestion] Title  : {title}")
                print(f"[Ingestion] URL    : {url}")

                try:
                    # 1) Duplicate check by URL
                    exists = (
                        db.query(Article)
                        .filter(Article.url == url)
                        .first()
                    )

                    if exists:
                        total_skipped += 1
                        by_source[source]["skipped"] += 1
                        print("[Ingestion] Skipped: already exists")
                        continue

                    # 2) Scrape full article content
                    content = ""
                    scraped_at = None

                    try:
                        content = self.scraper_service.scrape(
                            url=url,
                            source=source
                        )

                        if content and content.strip():
                            scraped_at = datetime.now(UTC)
                            print("[Ingestion] Content scraped successfully")
                        else:
                            content = None
                            print("[Ingestion] No content extracted")

                    except Exception as scrape_error:
                        content = None
                        print(
                            f"[Ingestion] Scrape error for '{title}': "
                            f"{scrape_error}"
                        )

                    # 3) Create article row
                    article = Article(
                        title=title,
                        source=source,
                        url=url,
                        summary=summary if summary else None,
                        content=content,
                        published_at=published_at,
                        scraped_at=scraped_at,
                        is_processed=bool(content),
                        summary_generated=bool(summary and summary.strip()),
                        embedding_generated=False,
                        processed_at=datetime.now(UTC) if content else None,
                    )

                    # 4) Generate embedding only if we have enough text
                    text_for_embedding = (
                        f"Title: {title}\n\n"
                        f"Summary:\n{summary}\n\n"
                        f"Content:\n{content}"
                    )

                    embedding = embedding_service.generate_embedding(
                        text_for_embedding
                    )

                    try:
                        embedding = self.embedding_service.generate_embedding(
                            text_for_embedding
                        )
                        article.embedding = embedding
                        article.embedding_generated = True
                        print("[Ingestion] Embedding generated successfully")

                    except Exception as embedding_error:
                        article.embedding_generated = False
                        print(
                            f"[Ingestion] Embedding error for '{title}': "
                            f"{embedding_error}"
                        )

                    # 5) Insert article
                    db.add(article)
                    db.commit()
                    db.refresh(article)

                    total_inserted += 1
                    by_source[source]["inserted"] += 1

                    print(f"[Ingestion] Inserted article #{article.id}")

                except IntegrityError:
                    db.rollback()
                    total_skipped += 1
                    by_source[source]["skipped"] += 1
                    print("[Ingestion] Skipped due to duplicate URL")

                except Exception as article_error:
                    db.rollback()
                    total_failed += 1
                    by_source[source]["failed"] += 1
                    print(
                        f"[Ingestion] Failed article '{title}': "
                        f"{article_error}"
                    )

            print("\n========== INGESTION SUMMARY ==========")
            print(f"Total inserted : {total_inserted}")
            print(f"Total skipped  : {total_skipped}")
            print(f"Total failed   : {total_failed}")
            print("---------------------------------------")

            for source, stats in by_source.items():
                print(
                    f"{source}: "
                    f"inserted={stats['inserted']}, "
                    f"skipped={stats['skipped']}, "
                    f"failed={stats['failed']}"
                )

            print("=======================================")

        except Exception as e:
            db.rollback()
            print(f"[Ingestion] Fatal error during ingestion: {e}")

        finally:
            db.close()

        return total_inserted

    def ingest_hackernews(self):
        """
        Legacy single-source method kept for backward compatibility.
        Prefer using ingest() for all-source ingestion.
        """
        db = SessionLocal()
        inserted = 0

        try:
            feed = self.rss_service.fetch_hackernews()

            print(f"[Ingestion] Hacker News entries found: {len(feed.entries)}")

            for item in feed.entries:
                exists = db.query(Article).filter(
                    Article.url == item.link
                ).first()

                if exists:
                    continue

                content = None
                scraped_at = None

                try:
                    content = self.scraper_service.scrape(
                        url=item.link,
                        source="The Hacker News"
                    )
                    if content and content.strip():
                        scraped_at = datetime.now(UTC)
                    else:
                        content = None
                except Exception as e:
                    print(f"[Ingestion] Scrape error for {item.title}: {e}")

                article = Article(
                    title=item.title,
                    source="The Hacker News",
                    url=item.link,
                    summary=getattr(item, "summary", None),
                    content=content,
                    published_at=datetime.now(UTC),
                    scraped_at=scraped_at,
                    is_processed=bool(content),
                    summary_generated=bool(getattr(item, "summary", None)),
                    embedding_generated=False,
                    processed_at=datetime.now(UTC) if content else None,
                )

                try:
                    text_for_embedding = (
                        f"Title: {item.title}\n\n"
                        f"Summary:\n{getattr(item, 'summary', '')}\n\n"
                        f"Content:\n{content or ''}"
                    )

                    embedding = self.embedding_service.generate_embedding(
                        text_for_embedding
                    )
                    article.embedding = embedding
                    article.embedding_generated = True

                except Exception as e:
                    print(f"[Ingestion] Embedding error for {item.title}: {e}")

                db.add(article)
                db.commit()
                inserted += 1

            print(f"[Ingestion] Hacker News inserted: {inserted}")

        except Exception as e:
            db.rollback()
            print(f"[Ingestion] Fatal Hacker News ingestion error: {e}")

        finally:
            db.close()

        return inserted