from datetime import datetime

from sqlalchemy.exc import IntegrityError

from app.database.db import SessionLocal
from app.models.article import Article
from app.services.rss_service import RSSService
from app.services.embedding_service import EmbeddingService


class ArticleIngestionService:

    def __init__(self):
        self.rss_service = RSSService()
        self.embedding_service = EmbeddingService()

    def ingest(self):
        """
        Ingest articles from all RSS feeds.
        Handles duplicate detection and embedding generation.
        """

        db = SessionLocal()
        total_inserted = 0

        try:

            articles = self.rss_service.fetch_articles()

            print(
                f"\n[Ingestion] Total articles found: {len(articles)}"
            )

            by_source = {}

            for article_data in articles:

                source = article_data["source"]

                if source not in by_source:
                    by_source[source] = 0

                article = Article(
                    title=article_data["title"],
                    source=source,
                    url=article_data["link"],
                    summary=article_data.get("summary", ""),
                    published_at=article_data.get(
                        "published_at",
                        datetime.now()
                    ),
                )

                # Generate embedding
                try:

                    text_for_embedding = (
                        f"{article_data['title']} "
                        f"{article_data.get('summary', '')}"
                    )

                    embedding = (
                        self.embedding_service.generate_embedding(
                            text_for_embedding
                        )
                    )

                    article.embedding = embedding
                    article.embedding_generated = True

                except Exception as e:

                    print(
                        f"[Ingestion] Embedding error for "
                        f"{article_data['title']}: {e}"
                    )

                # Insert article
                try:

                    with db.begin_nested():

                        db.add(article)
                        db.flush()

                    total_inserted += 1
                    by_source[source] += 1

                    print(
                        f"[Ingestion] {source}: + "
                        f"{article_data['title'][:50]}"
                    )

                except IntegrityError:

                    print(
                        f"[Ingestion] {source}: "
                        f"Already exists - "
                        f"{article_data['title'][:50]}"
                    )

                except Exception as e:

                    print(
                        f"[Ingestion] {source}: "
                        f"Error inserting article - {e}"
                    )

            try:

                db.commit()

            except Exception as e:

                db.rollback()

                print(
                    f"[Ingestion] Error during final commit: {e}"
                )

            print("\n[Ingestion] Summary:")

            for source, count in by_source.items():

                if count > 0:

                    print(
                        f"  {source}: +{count} articles"
                    )

            print(
                f"[Ingestion] Total ingested: {total_inserted}"
            )

        except Exception as e:

            db.rollback()

            print(
                f"[Ingestion] Error during ingestion: {e}"
            )

        finally:

            db.close()

        return total_inserted

    def ingest_hackernews(self):
        """
        Legacy method - kept for backward compatibility
        """

        rss = RSSService()
        feed = rss.fetch_hackernews()

        print(
            f"Total entries found: {len(feed.entries)}"
        )

        db = SessionLocal()

        inserted = 0

        for item in feed.entries:

            exists = db.query(Article).filter(
                Article.url == item.link
            ).first()

            if exists:
                continue

            article = Article(
                title=item.title,
                source="The Hacker News",
                url=item.link,
                published_at=datetime.now(),
            )

            db.add(article)
            inserted += 1

        db.commit()

        print(f"Inserted: {inserted}")

        db.close()