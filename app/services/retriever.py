import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.db import SessionLocal
from app.services.embedding_service import EmbeddingService


STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "for", "with", "from", "into", "onto",
    "what", "which", "who", "when", "where", "why", "how", "did", "does", "do",
    "is", "are", "was", "were", "be", "been", "being", "it", "its", "they", "them",
    "their", "this", "that", "these", "those", "to", "of", "in", "on", "at", "by",
    "about", "after", "before", "during", "over", "under", "linked", "related",
    "happened", "incident", "breach", "attack", "attacks", "hack", "hacked",
    "user", "assistant", "chat", "question", "answer"
}

FOLLOWUP_TRIGGER_WORDS = {
    "it",
    "they",
    "them",
    "their",
    "those",
    "that",
    "this",
    "attackers",
    "victims",
    "affected",
    "stolen",
    "linked",
    "companies",
    "data",
}


class Retriever:
    def __init__(self):
        self.embedding_service = EmbeddingService()

    def search(
        self,
        query: str,
        limit: int = 3,
        chat_history: str | None = None,
        original_question: str | None = None,
        resolved_question: str | None = None,
        topic_context: dict | None = None,
    ) -> dict:
        db: Session = SessionLocal()
        try:
            raw_query = (query or "").strip()
            original_question = (original_question or raw_query).strip()
            resolved_question = (resolved_question or raw_query).strip()

            if not resolved_question:
                return {
                    "rewritten_query": "",
                    "topic_context": {"entities": [], "keywords": []},
                    "results": [],
                }

            built_topic_context = self._build_topic_context(
                query=resolved_question,
                original_question=original_question,
                chat_history=chat_history or "",
                topic_context=topic_context or {},
            )

            rewritten_query = self._build_rewritten_query(
                query=resolved_question,
                topic_context=built_topic_context,
            )

            query_embedding = self.embedding_service.embed_query(rewritten_query)

            keywords = self._extract_keywords(rewritten_query)
            entities = self._extract_entities(rewritten_query)

            topic_entities = [
                x.lower() for x in built_topic_context.get("entities", []) if x
            ]
            topic_keywords = [
                x.lower() for x in built_topic_context.get("keywords", []) if x
            ]

            followup_mode = self._is_followup_query(original_question)

            all_query_terms = self._dedupe_preserve_order(
                keywords + entities + topic_keywords + topic_entities
            )

            sql = text(
                """
                SELECT
                    id,
                    title,
                    source,
                    url,
                    summary,
                    content,
                    published_at,
                    (
                        1 - (embedding <=> CAST(:query_embedding AS vector))
                    ) AS similarity
                FROM articles
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:query_embedding AS vector)
                LIMIT 25
                """
            )

            rows = db.execute(
                sql,
                {
                    "query_embedding": self._vector_to_pg(query_embedding),
                },
            ).mappings().all()

            scored_results = []

            for row in rows:
                title = row["title"] or ""
                summary = row["summary"] or ""
                content = row["content"] or ""
                source = row["source"] or ""

                combined_text = f"{title}\n{summary}\n{content}".lower()

                keyword_match = self._keyword_match_score(combined_text, keywords)
                entity_match = self._keyword_match_score(combined_text, entities)

                topic_keyword_match = self._keyword_match_score(combined_text, topic_keywords)
                topic_entity_match = self._keyword_match_score(combined_text, topic_entities)

                title_match_bonus = self._title_match_bonus(title.lower(), all_query_terms)

                topic_overlap_count = self._overlap_count(
                    combined_text,
                    topic_entities + topic_keywords
                )
                direct_query_overlap = self._overlap_count(
                    combined_text,
                    keywords + entities
                )

                penalty = 0.0

                if followup_mode and topic_entities:
                    if topic_overlap_count == 0:
                        penalty += 1.40
                    elif topic_overlap_count == 1:
                        penalty += 0.45

                if direct_query_overlap == 0 and topic_overlap_count == 0:
                    penalty += 0.80
                elif direct_query_overlap == 0 and topic_overlap_count <= 1:
                    penalty += 0.35

                if self._looks_generic_roundup(title.lower()):
                    penalty += 0.40

                vector_similarity = float(row["similarity"] or 0.0)

                score = (
                    (vector_similarity * 1.9)
                    + (keyword_match * 1.2)
                    + (entity_match * 1.3)
                    + (topic_keyword_match * 1.5)
                    + (topic_entity_match * 1.8)
                    + title_match_bonus
                    - penalty
                )

                scored_results.append(
                    {
                        "id": row["id"],
                        "title": row["title"],
                        "source": source,
                        "url": row["url"],
                        "summary": summary,
                        "content": content,
                        "published_at": row["published_at"],
                        "score": score,
                        "vector_similarity": vector_similarity,
                        "keyword_match": keyword_match,
                        "entity_match": entity_match,
                        "topic_keyword_match": topic_keyword_match,
                        "topic_entity_match": topic_entity_match,
                        "title_match_bonus": title_match_bonus,
                        "penalty": penalty,
                        "topic_overlap_count": topic_overlap_count,
                        "direct_query_overlap": direct_query_overlap,
                    }
                )

            scored_results.sort(key=lambda x: x["score"], reverse=True)

            print("\n" + "=" * 90)
            print("RETRIEVER RESULTS")
            print("=" * 90)
            print(f"Original Question : {original_question}")
            print(f"Resolved Question : {resolved_question}")
            print(f"Rewritten Query   : {rewritten_query}")
            print(f"Keywords          : {keywords}")
            print(f"Entities          : {entities}")
            print(f"Topic keywords    : {topic_keywords}")
            print(f"Topic entities    : {topic_entities}")
            print(f"Follow-up mode    : {followup_mode}")

            for item in scored_results[:10]:
                print(
                    f"{item['score']:.3f} | {item['source']} | {item['title']} | "
                    f"vs={item['vector_similarity']:.2f} "
                    f"km={item['keyword_match']:.2f} "
                    f"em={item['entity_match']:.2f} "
                    f"tk={item['topic_keyword_match']:.2f} "
                    f"te={item['topic_entity_match']:.2f} "
                    f"title={item['title_match_bonus']:.2f} "
                    f"pen={item['penalty']:.2f}"
                )

            final_results = self._select_final_results(
                scored_results=scored_results,
                limit=limit,
                topic_terms=self._dedupe_preserve_order(topic_entities + topic_keywords),
                followup_mode=followup_mode,
            )

            print(f"\nReturning {len(final_results)} final results")

            return {
                "rewritten_query": rewritten_query,
                "topic_context": built_topic_context,
                "results": final_results,
            }

        finally:
            db.close()

    def _build_topic_context(
        self,
        query: str,
        original_question: str,
        chat_history: str,
        topic_context: dict,
    ) -> dict:
        entities = []
        keywords = []

        entities.extend(topic_context.get("entities", []) or [])
        keywords.extend(topic_context.get("keywords", []) or [])

        entities.extend(self._extract_entities(query))
        keywords.extend(self._extract_keywords(query))

        entities.extend(self._extract_entities(original_question))
        keywords.extend(self._extract_keywords(original_question))

        history_entities, history_keywords = self._extract_topic_from_history(chat_history)
        entities.extend(history_entities)
        keywords.extend(history_keywords)

        return {
            "entities": self._dedupe_preserve_order(entities),
            "keywords": self._dedupe_preserve_order(keywords),
        }

    def _build_rewritten_query(self, query: str, topic_context: dict) -> str:
        query = (query or "").strip()
        if not query:
            return ""

        entities = topic_context.get("entities", [])[:5]
        keywords = topic_context.get("keywords", [])[:5]

        base_terms = self._dedupe_preserve_order(entities + keywords)

        query_terms = self._extract_keywords(query) + self._extract_entities(query)
        query_terms = self._dedupe_preserve_order(query_terms)

        missing = [t for t in base_terms if t not in query_terms]

        if not missing:
            return query

        extra = " ".join(missing[:4])
        return f"{query} {extra}".strip()

    def _extract_topic_from_history(self, chat_history: str) -> tuple[list[str], list[str]]:
        if not chat_history:
            return [], []

        lines = [line.strip() for line in chat_history.splitlines() if line.strip()]
        tail = "\n".join(lines[-12:])

        entities = self._extract_entities(tail)
        keywords = self._extract_keywords(tail)

        return entities[:12], keywords[:20]

    def _select_final_results(
        self,
        scored_results: list[dict],
        limit: int,
        topic_terms: list[str],
        followup_mode: bool,
    ) -> list[dict]:
        if not scored_results:
            return []

        strong_results = [item for item in scored_results if item["score"] >= 1.10]

        if not strong_results:
            strong_results = scored_results[:limit]

        if followup_mode and topic_terms:
            topic_filtered = [
                x for x in strong_results
                if x["topic_overlap_count"] > 0
            ]
            if len(topic_filtered) >= 1:
                strong_results = topic_filtered

        final = []
        seen_ids = set()

        for item in strong_results:
            if item["id"] in seen_ids:
                continue

            if followup_mode and topic_terms:
                if item["topic_overlap_count"] == 0:
                    continue

            final.append(self._strip_debug_fields(item))
            seen_ids.add(item["id"])

            if len(final) >= limit:
                break

        if not final:
            for item in scored_results[:limit]:
                if item["id"] in seen_ids:
                    continue
                final.append(self._strip_debug_fields(item))
                seen_ids.add(item["id"])

        return final

    def _strip_debug_fields(self, item: dict) -> dict:
        summary = item["summary"] or ""
        content = item["content"] or ""

        if len(summary) > 1500:
            summary = summary[:1500].rstrip() + "..."

        if len(content) > 3000:
            content = content[:3000].rstrip() + "..."

        return {
            "id": item["id"],
            "title": item["title"],
            "source": item["source"],
            "url": item["url"],
            "summary": summary,
            "content": content,
            "published_at": item["published_at"],
        }

    def _is_followup_query(self, raw_query: str) -> bool:
        raw = (raw_query or "").lower().strip()
        if not raw:
            return False

        tokens = set(self._tokenize(raw))
        return any(word in tokens for word in FOLLOWUP_TRIGGER_WORDS)

    def _extract_keywords(self, text_value: str) -> list[str]:
        words = self._tokenize(text_value)
        keywords = [
            word for word in words
            if len(word) > 2 and word not in STOPWORDS
        ]
        return self._dedupe_preserve_order(keywords)

    def _extract_entities(self, text_value: str) -> list[str]:
        if not text_value:
            return []

        original_tokens = re.findall(r"[A-Za-z0-9\-\']+", text_value)
        entities = []

        for token in original_tokens:
            token_clean = token.strip().lower()
            if len(token_clean) <= 2:
                continue
            if token_clean in STOPWORDS:
                continue

            if token[0].isupper() or any(ch.isdigit() for ch in token) or "-" in token:
                entities.append(token_clean)

        return self._dedupe_preserve_order(entities)

    def _keyword_match_score(self, text_value: str, terms: list[str]) -> float:
        if not text_value or not terms:
            return 0.0

        score = 0.0
        for term in terms:
            if not term:
                continue

            occurrences = len(re.findall(rf"\b{re.escape(term)}\b", text_value))
            if occurrences > 0:
                score += min(occurrences, 4) * 0.35

        return score

    def _title_match_bonus(self, title: str, terms: list[str]) -> float:
        if not title or not terms:
            return 0.0

        bonus = 0.0
        for term in terms:
            if re.search(rf"\b{re.escape(term)}\b", title):
                bonus += 0.30
        return min(bonus, 1.5)

    def _overlap_count(self, text_value: str, terms: list[str]) -> int:
        if not text_value or not terms:
            return 0

        count = 0
        seen = set()

        for term in terms:
            if term in seen:
                continue
            seen.add(term)
            if re.search(rf"\b{re.escape(term)}\b", text_value):
                count += 1

        return count

    def _looks_generic_roundup(self, title: str) -> bool:
        roundup_markers = [
            "weekly recap",
            "bulletin",
            "top 10",
            "survey:",
            "and more",
        ]
        return any(marker in title for marker in roundup_markers)

    def _tokenize(self, text_value: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", (text_value or "").lower())

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        seen = set()
        output = []

        for item in items:
            item = (item or "").strip().lower()
            if not item or item in seen:
                continue
            seen.add(item)
            output.append(item)

        return output

    def _vector_to_pg(self, vector: list[float]) -> str:
        return "[" + ",".join(str(float(x)) for x in vector) + "]"