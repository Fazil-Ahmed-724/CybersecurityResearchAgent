from sqlalchemy import text

from app.database.db import SessionLocal
from app.services.embedding_service import EmbeddingService


class Retriever:

    def search(
        self,
        query: str,
        limit: int = 5
    ):

        db = SessionLocal()

        try:

            embedder = EmbeddingService()

            query_embedding = embedder.generate_embedding(
                query
            )

            sql = text("""
            SELECT
                id,
                title,
                source,
                url,
                summary,
                embedding <=> CAST(:embedding AS vector) AS distance
            FROM articles
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :limit
            """)

            rows = db.execute(
                sql,
                {
                    "embedding": str(query_embedding),
                    "limit": limit
                }
            )

            results = []

            for row in rows:

                results.append(
                    {
                        "id": row.id,
                        "title": row.title,
                        "source": row.source,
                        "url": row.url,
                        "summary": row.summary,
                        "distance": float(row.distance)
                    }
                )

            return results

        finally:
            db.close()