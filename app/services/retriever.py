from sqlalchemy import text

from app.database.db import SessionLocal
from app.services.embedding_service import EmbeddingService


class Retriever:

    def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.31
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

            query_lower = query.lower()
            keywords = query_lower.split()

            for row in rows:

                item = {
                    "id": row.id,
                    "title": row.title,
                    "source": row.source,
                    "url": row.url,
                    "summary": row.summary,
                    "distance": float(row.distance)
                }

                title_lower = item["title"].lower()

                rank_score = item["distance"]

                matches = 0

                for keyword in keywords:

                    if keyword in title_lower:
                        matches += 1

                # boost title relevance
                rank_score -= matches * 0.03

                item["rank_score"] = rank_score

                results.append(item)

            # sort by hybrid score
            results.sort(
                key=lambda x: x["rank_score"]
            )

            filtered_results = [
                item
                for item in results
                if item["rank_score"] <= threshold
            ]

            return filtered_results[:3]

        finally:
            db.close()