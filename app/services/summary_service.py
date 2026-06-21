from app.database.db import SessionLocal
from app.models.article import Article
from app.services.groq_service import GroqService


class SummaryService:

    def generate_summary(self, content: str):
        return self._generate_summary(
            content,
            GroqService()
        )

    def _generate_summary(self, content: str, groq: GroqService):
        return groq.summarize_article(
            content
        )

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

                summary = self._generate_summary(
                    article.content,
                    groq
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
