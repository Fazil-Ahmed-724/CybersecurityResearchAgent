from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.database.db import SessionLocal
from app.models.article import Article


class Retriever:
    """
    Retrieval service with follow-up hardening:
    - removes generic question words from scoring
    - prefers real incident/entity terms
    - requires incident overlap when follow-up context exists
    - tightens generic first-turn questions
    """

    DEBUG_RESULT_LIMIT = 10
    MIN_FINAL_SCORE = 2.0
    MIN_PRIMARY_MATCH = 1.5
    MIN_TOPIC_ONLY_MATCH = 2.5

    FOLLOWUP_MIN_SCORE = 12.0
    FOLLOWUP_MIN_PRIMARY = 6.0
    FOLLOWUP_MIN_TOPIC = 6.0
    FIRST_TURN_INCIDENT_MIN_SCORE = 10.0

    STOPWORDS = {
        "the", "a", "an", "and", "or", "but", "if", "then", "else", "when",
        "what", "which", "who", "where", "why", "how", "is", "are", "was", "were",
        "be", "been", "being", "do", "does", "did", "done", "have", "has", "had",
        "of", "to", "in", "on", "for", "by", "with", "about", "into", "from",
        "that", "this", "these", "those", "it", "its", "they", "them", "their",
        "there", "here", "you", "your", "we", "our", "as", "at", "than", "after",
        "before", "during", "over", "under", "again", "more", "most"
    }

    JUNK_TOPIC_WORDS = {
        "executive", "summary", "key", "findings", "recommendation", "recommendations",
        "impact", "report", "reports", "source", "sources", "article", "articles",
        "response", "answer", "details", "background", "context"
    }

    # These are generic question intent words and should not be treated
    # as meaningful retrieval keywords/entities.
    QUESTION_FILLER = {
        "what", "which", "who", "where", "why", "how",
        "affected", "stolen", "happened", "linked", "known", "tell",
        "about", "more", "data", "company", "companies", "attacker", "attackers",
        "behind", "victims", "incident", "breach", "impact", "impacted",
        "targeted", "related", "involved"
    }

    # Extra generic words that should never contribute to keyword/entity scoring.
    GENERIC_MATCH_TERMS = {
        "affected", "stolen", "happened", "linked", "data",
        "company", "companies", "attacker", "attackers",
        "behind", "victims", "incident", "breach",
        "impact", "impacted", "targeted", "related", "involved"
    }

    INCIDENT_TERMS = {
        "klue", "oauth", "icarus", "salesforce", "lastpass", "huntress",
        "recorded", "future", "tanium", "jamf", "gong", "insurity", "sprout", "social",
        "fortinet", "fortisandbox", "fortibleed", "wordpress", "clickfix",
        "whatsapp", "microsoft", "lazarus", "bluenoroff"
    }

    GENERIC_QUESTION_PATTERNS = [
        r"^what happened(?: in .+)?\??$",
        r"^what data was stolen(?: in .+)?\??$",
        r"^what was stolen(?: in .+)?\??$",
        r"^which companies were affected(?: in .+)?\??$",
        r"^who was affected(?: in .+)?\??$",
        r"^who was impacted(?: in .+)?\??$",
        r"^which attackers were linked to it(?: in .+)?\??$",
        r"^who was behind it(?: in .+)?\??$",
        r"^who were they(?: in .+)?\??$",
    ]

    def __init__(self):
        self.db = SessionLocal()

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _normalize(text_value: str) -> str:
        text_value = text_value or ""
        text_value = text_value.strip()
        text_value = re.sub(r"\s+", " ", text_value)
        return text_value

    @staticmethod
    def _tokenize(text_value: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9\-\+']+", (text_value or "").lower())

    def _clean_terms(self, terms: List[str]) -> List[str]:
        cleaned = []
        seen = set()

        for t in terms:
            t = (t or "").strip().lower()
            if not t:
                continue
            if len(t) <= 2:
                continue
            if t in self.STOPWORDS:
                continue
            if t in self.JUNK_TOPIC_WORDS:
                continue
            if t in self.QUESTION_FILLER:
                continue
            if t not in seen:
                seen.add(t)
                cleaned.append(t)

        return cleaned

    def _extract_keywords(self, text_value: str) -> List[str]:
        tokens = self._tokenize(text_value)
        tokens = [
            t for t in tokens
            if len(t) > 2
            and t not in self.STOPWORDS
            and t not in self.JUNK_TOPIC_WORDS
            and t not in self.QUESTION_FILLER
        ]

        seen = set()
        result = []
        for t in tokens:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result[:12]

    def _extract_entities(self, text_value: str) -> List[str]:
        keywords = self._extract_keywords(text_value)
        entities = []

        priority_terms = [
            "klue", "oauth", "icarus", "salesforce", "lastpass", "huntress",
            "recorded", "future", "tanium", "jamf", "gong", "insurity", "sprout", "social"
        ]

        for p in priority_terms:
            if p in keywords and p not in entities:
                entities.append(p)

        for kw in keywords:
            if kw not in entities:
                entities.append(kw)

        return entities[:12]

    def _is_generic_question(self, question: str) -> bool:
        q = self._normalize(question).lower()
        return any(re.match(pattern, q) for pattern in self.GENERIC_QUESTION_PATTERNS)

    # ------------------------------------------------------------------
    # Topic context
    # ------------------------------------------------------------------
    def _build_topic_context(
        self,
        original_question: str,
        resolved_question: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, List[str]]:
        chat_history = chat_history or []

        terms: List[str] = []
        entities: List[str] = []

        def add_from_text(text_value: str):
            kws = self._extract_keywords(text_value)
            ents = self._extract_entities(text_value)

            for kw in kws:
                if kw not in terms:
                    terms.append(kw)
            for ent in ents:
                if ent not in entities:
                    entities.append(ent)

        add_from_text(original_question)
        add_from_text(resolved_question)

        recent = chat_history[-12:] if len(chat_history) > 12 else chat_history

        for item in reversed(recent):
            if (item.get("role") or "").lower() != "user":
                continue

            metadata = item.get("metadata") or {}
            resolved = metadata.get("resolved_question")
            content = item.get("content") or ""

            if resolved:
                add_from_text(resolved)
            elif content:
                add_from_text(content)

            if len(terms) >= 15 and len(entities) >= 10:
                break

        terms = [t for t in terms if t not in self.QUESTION_FILLER]
        entities = [e for e in entities if e not in self.QUESTION_FILLER]

        preferred = ["klue", "oauth", "icarus", "salesforce", "lastpass", "huntress"]
        ordered_entities = []
        for p in preferred:
            if p in entities and p not in ordered_entities:
                ordered_entities.append(p)
        for e in entities:
            if e not in ordered_entities:
                ordered_entities.append(e)

        return {
            "keywords": terms[:15],
            "entities": ordered_entities[:10],
        }

    # ------------------------------------------------------------------
    # Query rewrite
    # ------------------------------------------------------------------
    def _build_rewritten_query(
        self,
        original_question: str,
        resolved_question: str,
        topic_context: Dict[str, List[str]],
    ) -> str:
        base = self._normalize(resolved_question or original_question)
        lower_base = base.lower()
        entities = topic_context.get("entities", [])[:4]

        if any(e in lower_base for e in entities):
            return base

        if entities:
            return f"{base} {' '.join(entities)}"

        return base

    # ------------------------------------------------------------------
    # Scoring helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _safe_count(text_value: str, needle: str) -> int:
        if not text_value or not needle:
            return 0
        return text_value.lower().count(needle.lower())

    def _article_source_name(self, article: Article) -> str:
        return (
            getattr(article, "source_name", None)
            or getattr(article, "source", None)
            or "Unknown"
        )

    def _count_incident_term_overlap(
        self,
        title: str,
        summary: str,
        content: str,
        incident_terms: List[str],
    ) -> int:
        combined = f"{title}\n{summary}\n{content}".lower()
        count = 0
        for term in incident_terms:
            if term and term.lower() in combined:
                count += 1
        return count

    def _is_relevant_match(
        self,
        score: float,
        breakdown: Dict[str, float],
        query_entities: List[str],
        topic_entities: List[str],
        original_question: str,
        resolved_question: str,
    ) -> bool:
        if score < self.MIN_FINAL_SCORE:
            return False

        primary_match = (
            breakdown.get("km", 0.0)
            + breakdown.get("em", 0.0)
            + breakdown.get("title", 0.0)
        )
        topic_match = breakdown.get("tk", 0.0) + breakdown.get("te", 0.0)

        generic_question = self._is_generic_question(original_question)
        has_topic = original_question.strip().lower() != resolved_question.strip().lower()

        incident_entities = [
            e for e in (query_entities + topic_entities)
            if e in self.INCIDENT_TERMS
        ]
        incident_entities = list(dict.fromkeys(incident_entities))
        incident_overlap_count = breakdown.get("incident_overlap_count", 0)

        # ------------------------------------------------------------------
        # Follow-up / memory mode:
        # very strict because we already know the incident context
        # ------------------------------------------------------------------
        if has_topic and incident_entities:
            if incident_overlap_count < 2:
                return False

            if score < self.FOLLOWUP_MIN_SCORE:
                return False

            if primary_match < self.FOLLOWUP_MIN_PRIMARY and topic_match < self.FOLLOWUP_MIN_TOPIC:
                return False

            return True

        # ------------------------------------------------------------------
        # First-turn generic incident question:
        # e.g. "What happened in the Klue OAuth breach?"
        # keep only strong incident-linked matches
        # ------------------------------------------------------------------
        if generic_question and incident_entities:
            if incident_overlap_count < 2:
                return False

            if score < self.FIRST_TURN_INCIDENT_MIN_SCORE:
                return False

            return primary_match >= 4.0 or topic_match >= 4.0

        # ------------------------------------------------------------------
        # Generic first-turn question with no usable incident context
        # ------------------------------------------------------------------
        if generic_question and not has_topic and not incident_entities:
            return primary_match >= 4.0 and score >= 6.0

        # ------------------------------------------------------------------
        # Normal fallback behavior for non-incident queries
        # ------------------------------------------------------------------
        return (
            primary_match >= self.MIN_PRIMARY_MATCH
            or topic_match >= self.MIN_TOPIC_ONLY_MATCH
        )

    def _score_article(
        self,
        article: Article,
        query_keywords: List[str],
        query_entities: List[str],
        topic_keywords: List[str],
        topic_entities: List[str],
        original_question: str,
        resolved_question: str,
    ) -> Tuple[float, Dict[str, float]]:
        title = article.title or ""
        summary = article.summary or ""
        content = article.content or ""
        title_lower = title.lower()
        combined = f"{title}\n{summary}\n{content}".lower()

        keyword_match = 0.0
        entity_match = 0.0
        topic_keyword_match = 0.0
        topic_entity_match = 0.0
        title_bonus = 0.0
        incident_bonus = 0.0

        # --------------------------------------------------------------
        # Query keywords: skip generic question-intent terms
        # --------------------------------------------------------------
        for kw in query_keywords:
            if kw in self.GENERIC_MATCH_TERMS:
                continue

            cnt = self._safe_count(combined, kw)
            if cnt > 0:
                keyword_match += min(3.2, 0.8 * cnt)

            if kw in title_lower:
                title_bonus += 0.45

        # --------------------------------------------------------------
        # Query entities: skip generic question-intent terms
        # --------------------------------------------------------------
        for ent in query_entities:
            if ent in self.GENERIC_MATCH_TERMS:
                continue

            cnt = self._safe_count(combined, ent)
            if cnt > 0:
                entity_match += min(3.5, 0.9 * cnt)

            if ent in title_lower:
                title_bonus += 0.55

        # --------------------------------------------------------------
        # Topic keywords: these are more trusted than raw question words
        # --------------------------------------------------------------
        for kw in topic_keywords[:8]:
            if kw in self.GENERIC_MATCH_TERMS:
                continue

            cnt = self._safe_count(combined, kw)
            if cnt > 0:
                topic_keyword_match += min(2.4, 0.45 * cnt)

        for ent in topic_entities[:8]:
            if ent in self.GENERIC_MATCH_TERMS:
                continue

            cnt = self._safe_count(combined, ent)
            if cnt > 0:
                topic_entity_match += min(2.6, 0.50 * cnt)

            if ent in title_lower:
                title_bonus += 0.35

        incident_terms = [
            e for e in (query_entities + topic_entities)
            if e in self.INCIDENT_TERMS
        ]
        incident_terms = list(dict.fromkeys(incident_terms))

        incident_overlap = self._count_incident_term_overlap(
            title=title,
            summary=summary,
            content=content,
            incident_terms=incident_terms,
        )

        if incident_overlap > 0:
            incident_bonus += min(3.0, incident_overlap * 0.9)

        vector_score = (
            keyword_match * 0.25
            + entity_match * 0.30
            + topic_keyword_match * 0.20
            + topic_entity_match * 0.25
        )

        penalty = 0.0

        if (keyword_match + entity_match + topic_keyword_match + topic_entity_match) == 0:
            penalty += 1.5

        generic_question = self._is_generic_question(original_question)
        has_topic = original_question.strip().lower() != resolved_question.strip().lower()

        # For generic unresolved questions, penalize articles that don't carry incident overlap.
        if generic_question and not has_topic and incident_overlap == 0:
            penalty += 3.0

        # For follow-up/topic-enriched questions, anything with zero incident overlap
        # should be strongly penalized so it doesn't survive the filter.
        if has_topic and incident_terms and incident_overlap == 0:
            penalty += 4.0

        final_score = (
            vector_score
            + keyword_match
            + entity_match
            + topic_keyword_match
            + topic_entity_match
            + title_bonus
            + incident_bonus
            - penalty
        )

        return final_score, {
            "vs": round(vector_score, 2),
            "km": round(keyword_match, 2),
            "em": round(entity_match, 2),
            "tk": round(topic_keyword_match, 2),
            "te": round(topic_entity_match, 2),
            "title": round(title_bonus, 2),
            "incident": round(incident_bonus, 2),
            "incident_overlap_count": incident_overlap,
            "pen": round(penalty, 2),
        }

    # ------------------------------------------------------------------
    # Public search
    # ------------------------------------------------------------------
    def search(
        self,
        original_question: str,
        resolved_question: Optional[str] = None,
        chat_history: Optional[List[Dict[str, Any]]] = None,
        limit: int = 3,
    ) -> Dict[str, Any]:
        resolved_question = resolved_question or original_question
        chat_history = chat_history or []

        topic_context = self._build_topic_context(
            original_question=original_question,
            resolved_question=resolved_question,
            chat_history=chat_history,
        )

        rewritten_query = self._build_rewritten_query(
            original_question=original_question,
            resolved_question=resolved_question,
            topic_context=topic_context,
        )

        query_keywords = self._extract_keywords(rewritten_query)
        query_entities = self._extract_entities(rewritten_query)
        topic_keywords = topic_context.get("keywords", [])
        topic_entities = topic_context.get("entities", [])

        articles = (
            self.db.query(Article)
            .filter(Article.content.isnot(None))
            .filter(Article.content != "")
            .order_by(Article.published_at.desc())
            .limit(150)
            .all()
        )

        scored: List[Tuple[Article, float, Dict[str, float]]] = []
        for article in articles:
            score, breakdown = self._score_article(
                article=article,
                query_keywords=query_keywords,
                query_entities=query_entities,
                topic_keywords=topic_keywords,
                topic_entities=topic_entities,
                original_question=original_question,
                resolved_question=resolved_question,
            )
            scored.append((article, score, breakdown))

        scored.sort(key=lambda x: x[1], reverse=True)

        filtered_scored = [
            item for item in scored
            if self._is_relevant_match(
                score=item[1],
                breakdown=item[2],
                query_entities=query_entities,
                topic_entities=topic_entities,
                original_question=original_question,
                resolved_question=resolved_question,
            )
        ]

        print("\n" + "=" * 90)
        print("RETRIEVER RESULTS")
        print("=" * 90)
        print(f"Original Question : {original_question}")
        print(f"Resolved Question : {resolved_question}")
        print(f"Rewritten Query   : {rewritten_query}")
        print(f"Keywords          : {query_keywords}")
        print(f"Entities          : {query_entities}")
        print(f"Topic keywords    : {topic_keywords}")
        print(f"Topic entities    : {topic_entities}")
        print(f"Follow-up mode    : {original_question.strip().lower() != resolved_question.strip().lower()}")
        print(f"Candidates scored : {len(scored)}")
        print(f"Relevant matches  : {len(filtered_scored)}")

        for article, score, bd in filtered_scored[: self.DEBUG_RESULT_LIMIT]:
            source_name = self._article_source_name(article)
            article_title = getattr(article, "title", "") or "Untitled"

            print(
                f"{score:0.3f} | {source_name} | {article_title} | "
                f"vs={bd['vs']:.2f} km={bd['km']:.2f} em={bd['em']:.2f} "
                f"tk={bd['tk']:.2f} te={bd['te']:.2f} title={bd['title']:.2f} "
                f"incident={bd['incident']:.2f} overlap={bd['incident_overlap_count']} "
                f"pen={bd['pen']:.2f}"
            )

        if not filtered_scored:
            print("No candidates passed the relevance filter.")

        final_articles = [item[0] for item in filtered_scored[:limit]]

        print(f"\nReturning {len(final_articles)} final results\n")

        return {
            "rewritten_query": rewritten_query,
            "topic_context": topic_context,
            "articles": final_articles,
        }