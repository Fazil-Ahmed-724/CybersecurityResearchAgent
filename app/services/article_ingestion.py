from datetime import datetime

from app.database.db import SessionLocal
from app.models.article import Article
from app.services.rss_service import RSSService


class ArticleIngestionService:

    def ingest_hackernews(self):

        rss = RSSService()
        feed = rss.fetch_hackernews()

        print(f"Total entries found: {len(feed.entries)}")

        db = SessionLocal()

        inserted = 0

        for item in feed.entries:

            print(item.title)

            exists = db.query(Article).filter(
                Article.url == item.link
            ).first()

            if exists:
                print("Already exists")
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