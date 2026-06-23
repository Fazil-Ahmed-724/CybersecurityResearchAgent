import re

from sqlalchemy import text

from app.database.db import SessionLocal
from app.services.embedding_service import EmbeddingService


class Retriever:

    STOPWORDS = {
        "about",
        "after",
        "also",
        "and",
        "are",
        "campaign",
        "campaigns",
        "country",
        "create",
        "created",
        "creator",
        "creators",
        "did",
        "does",
        "explain",
        "for",
        "from",
        "has",
        "have",
        "how",
        "into",
        "its",
        "malware",
        "the",
        "this",
        "that",
        "they",
        "target",
        "targeted",
        "targets",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "with"
    }

    def _extract_keywords(
        self,
        query: str
    ):
        words = re.findall(
            r"[a-zA-Z0-9][a-zA-Z0-9._-]*",
            query.lower()
        )

        return [
            word
            for word in words
            if len(word) > 2
            and word not in self.STOPWORDS
        ][:8]

    def _build_lexical_query(
        self,
        keywords
    ):
        conditions = []
        params = {}

        for index, keyword in enumerate(keywords):
            param_name = f"keyword_{index}"
            params[param_name] = f"%{keyword}%"

            conditions.append(
                f"""
                (
                    title ILIKE :{param_name}
                    OR summary ILIKE :{param_name}
                    OR content ILIKE :{param_name}
                )
                """
            )

        if not conditions:
            return None, {}

        sql = text(f"""
        SELECT
            id,
            title,
            source,
            url,
            content,
            summary,
            published_at,
            0.0 AS distance,
            true AS lexical_match
        FROM articles
        WHERE {" OR ".join(conditions)}
        ORDER BY id DESC
        LIMIT :limit
        """)

        return sql, params

    def _rank_item(
        self,
        item,
        keywords
    ):
        title_lower = (item.get("title") or "").lower()
        summary_lower = (item.get("summary") or "").lower()
        content_lower = (item.get("content") or "").lower()

        rank_score = item["distance"]

        title_matches = 0
        summary_matches = 0
        content_matches = 0

        for keyword in keywords:
            if keyword in title_lower:
                title_matches += 1

            if keyword in summary_lower:
                summary_matches += 1

            if keyword in content_lower:
                content_matches += 1

        rank_score -= title_matches * 0.12
        rank_score -= summary_matches * 0.04
        rank_score -= content_matches * 0.02

        if item.get("lexical_match"):
            rank_score -= 0.35

        item["rank_score"] = rank_score
        return item

    def search(
        self,
        query: str,
        limit: int = 10,
        threshold: float = 0.70
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
                content,
                summary,
                published_at,
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
            ).fetchall()

            keywords = self._extract_keywords(
                query
            )

            lexical_sql, lexical_params = self._build_lexical_query(
                keywords
            )

            lexical_rows = []

            if lexical_sql is not None:
                lexical_params["limit"] = limit

                lexical_rows = db.execute(
                    lexical_sql,
                    lexical_params
                ).fetchall()

            results_by_id = {}

            for row in rows:
                item = {
                    "id": row.id,
                    "title": row.title,
                    "source": row.source,
                    "url": row.url,
                    "content": row.content,
                    "summary": row.summary,
                    "published_at": row.published_at,
                    "distance": float(row.distance),
                    "lexical_match": False
                }
                results_by_id[item["id"]] = item

            for row in lexical_rows:
                item = results_by_id.get(row.id)

                if item:
                    item["lexical_match"] = True
                    continue

                results_by_id[row.id] = {
                    "id": row.id,
                    "title": row.title,
                    "source": row.source,
                    "url": row.url,
                    "content": row.content,
                    "summary": row.summary,
                    "published_at": row.published_at,
                    "distance": float(row.distance),
                    "lexical_match": True
                }

            results = [
                self._rank_item(item, keywords)
                for item in results_by_id.values()
            ]

            results.sort(
                key=lambda x: x["rank_score"]
            )

            print("\n" + "=" * 60)
            print("RETRIEVER RESULTS")
            print("=" * 60)

            for item in results[:5]:
                print(
                    f"{item['rank_score']:.3f} | "
                    f"{item['title']}"
                )

            filtered_results = [
                item
                for item in results[:10]
                if item["rank_score"] <= threshold
            ]

            if filtered_results:
                print(
                    f"\nReturning {len(filtered_results[:3])} filtered results"
                )
                return filtered_results[:3]

            print(
                "\nNo results passed threshold. Returning top 3 closest matches."
            )
            return results[:3]

        finally:
            db.close()