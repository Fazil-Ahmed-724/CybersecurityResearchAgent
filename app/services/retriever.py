from sqlalchemy import text

from app.database.db import SessionLocal
from app.services.embedding_service import EmbeddingService


class Retriever:

    def search(self, query: str):

        db = SessionLocal()

        embedder = EmbeddingService()

        query_embedding = embedder.generate_embedding(
            query
        )

        sql = text("""
        SELECT
            title,
            source,
            summary,
            embedding <=> CAST(:embedding AS vector) AS distance
        FROM articles
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> CAST(:embedding AS vector)
        LIMIT 5
        """)

        results = db.execute(
            sql,
            {
                "embedding": str(query_embedding)
            }
        )

        return results.fetchall()