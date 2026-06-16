from app.database.db import SessionLocal
from app.models.article import Article

from app.services.embedding_service import (
    EmbeddingService
)


class VectorService:

    def generate_embeddings(self):

        db = SessionLocal()

        articles = (
            db.query(Article)
            .filter(Article.summary.isnot(None))
            .filter(
                Article.embedding_generated == False
            )
            .all()
        )

        print(
            f"Articles Found: {len(articles)}"
        )

        embedder = EmbeddingService()

        for article in articles:

            print(
                f"Embedding: {article.title}"
            )

            try:

                embedding = (
                    embedder.generate_embedding(
                        article.summary
                    )
                )

                print(
                    f"Vector Length: {len(embedding)}"
                )

                article.embedding = embedding

                article.embedding_generated = True

                db.commit()

            except Exception as e:

                print(
                    f"Failed: {article.title}"
                )

                print(e)

        db.close()