from app.database.db import SessionLocal
from app.models.article import Article
from app.services.article_scraper import ArticleScraper


class ContentEnrichmentService:

    def enrich_articles(self):

        db = SessionLocal()

        articles = (
            db.query(Article)
            .filter(Article.content.is_(None))
            .all()
        )

        print(f"Articles to process: {len(articles)}")

        scraper = ArticleScraper()

        for article in articles:

            print(f"Processing: {article.title}")

            content = scraper.scrape(
                article.url
            )

            if not content:
                continue

            article.content = content

            db.commit()

        db.close()