from app.database.db import SessionLocal
from app.models.article import Article
from app.services.groq_service import GroqService


class SummaryService:

    def generate_summaries(self):

        db = SessionLocal()

        articles = (
            db.query(Article)
            .filter(Article.content.isnot(None))
            .filter(Article.summary_generated == False)
            .all()
        )

        print(f"Articles found: {len(articles)}")

        groq = GroqService()

        for article in articles:

            print(f"Summarizing: {article.title}")

            try:

                summary = groq.summarize_article(
                    article.content
                )

                article.summary = summary

                article.summary_generated = True

                db.commit()

            except Exception as e:

                print(
                    f"Error: {article.title}"
                )

                print(e)

        db.close()