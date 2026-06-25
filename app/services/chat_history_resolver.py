# app/services/chat_history_resolver.py

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional


class ChatHistoryResolver:
    """
    Resolves follow-up questions into standalone questions using recent user-turn context.

    Important design choice:
    - We DO NOT build topic from assistant's long formatted answer text
    - We only use:
        1) previous user questions
        2) previous resolved questions if available
        3) current question
    """

    FOLLOWUP_PHRASES = {
        "what about",
        "which ones",
        "which company",
        "which companies",
        "who were they",
        "who were the attackers",
        "what happened",
        "what data",
        "what was stolen",
        "how did they",
        "how did attackers",
        "when did it happen",
        "where did it happen",
        "was it",
        "was lastpass affected",
        "who was affected",
        "who were affected",
        "and what",
        "and who",
        "and how",
        "and when",
        "tell me more",
        "what else",
        "what about them",
    }

    QUESTION_WORDS = {
        "what", "which", "who", "when", "where", "why", "how",
        "was", "were", "did", "does", "do", "is", "are", "can"
    }

    NOISE_WORDS = {
        "executive", "summary", "key", "findings", "recommendations",
        "recommendation", "impact", "report", "reports", "source",
        "sources", "article", "articles", "incident", "breach",
        "attack", "attacks", "details"
    }

    @staticmethod
    def _normalize(text: str) -> str:
        text = text or ""
        text = text.strip()
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9\-\+']+", (text or "").lower())

    @classmethod
    def _extract_candidate_topic_terms(cls, text: str) -> List[str]:
        """
        Extract topic-like terms from a USER question / resolved question.
        Keep only meaningful tokens.
        """
        tokens = cls._tokenize(text)

        stop = {
            "what", "which", "who", "when", "where", "why", "how",
            "is", "are", "was", "were", "do", "does", "did",
            "the", "a", "an", "of", "in", "on", "for", "to", "by",
            "and", "or", "with", "from", "that", "this", "it", "they",
            "them", "their", "there", "about", "into", "after",
            "affected", "stolen", "happened", "linked", "tell", "more",
            "please"
        } | cls.NOISE_WORDS

        cleaned = []
        for token in tokens:
            if len(token) <= 2:
                continue
            if token in stop:
                continue
            cleaned.append(token)

        # preserve order + dedupe
        seen = set()
        result = []
        for t in cleaned:
            if t not in seen:
                seen.add(t)
                result.append(t)
        return result

    @classmethod
    def _is_followup_question(cls, question: str) -> bool:
        q = cls._normalize(question).lower()
        if not q:
            return False

        # explicit follow-up phrases
        for phrase in cls.FOLLOWUP_PHRASES:
            if q.startswith(phrase):
                return True

        tokens = cls._tokenize(q)
        if not tokens:
            return False

        # very short question with pronoun/topic omitted = likely follow-up
        # e.g. "Which companies were affected?"
        if len(tokens) <= 6 and tokens[0] in cls.QUESTION_WORDS:
            # if it lacks a strong named entity/topic term, likely follow-up
            topicish = [
                t for t in tokens
                if len(t) > 3
                and t not in cls.NOISE_WORDS
                and t not in {"what", "which", "who", "when", "where", "why", "how",
                              "were", "was", "did", "does", "company", "companies",
                              "data", "attackers", "affected", "stolen"}
            ]
            if len(topicish) <= 1:
                return True

        return False

    @classmethod
    def _collect_recent_user_topic_terms(cls, chat_history: List[Dict[str, Any]]) -> List[str]:
        """
        Only collect topic terms from recent USER questions and resolved_question metadata.
        Never from assistant answer body.
        """
        collected: List[str] = []

        recent = chat_history[-12:] if len(chat_history) > 12 else chat_history

        for item in reversed(recent):
            role = (item.get("role") or "").lower()
            if role != "user":
                continue

            # prefer resolved_question if stored in metadata
            metadata = item.get("metadata") or {}
            resolved_question = metadata.get("resolved_question")
            content = item.get("content") or ""

            candidates = []
            if resolved_question:
                candidates.append(resolved_question)
            if content:
                candidates.append(content)

            for text in candidates:
                terms = cls._extract_candidate_topic_terms(text)
                for t in terms:
                    if t not in collected:
                        collected.append(t)

            if len(collected) >= 8:
                break

        return collected[:8]

    @classmethod
    def resolve_question(
        cls,
        question: str,
        chat_history: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Returns:
        {
            "original_question": ...,
            "resolved_question": ...,
            "is_followup": bool,
            "topic_terms": [...]
        }
        """
        question = cls._normalize(question)
        chat_history = chat_history or []

        is_followup = cls._is_followup_question(question)

        if not is_followup or not chat_history:
            return {
                "original_question": question,
                "resolved_question": question,
                "is_followup": False,
                "topic_terms": [],
            }

        topic_terms = cls._collect_recent_user_topic_terms(chat_history)

        if not topic_terms:
            return {
                "original_question": question,
                "resolved_question": question,
                "is_followup": True,
                "topic_terms": [],
            }

        # build standalone resolved question
        # Example:
        # "Which companies were affected?"
        # -> "Which companies were affected in the Klue OAuth incident?"
        topic_suffix = " ".join(topic_terms[:4])

        lowered = question.lower()

        if "affected" in lowered:
            resolved = f"{question.rstrip('?')} in the {topic_suffix} incident?"
        elif "stolen" in lowered or "data" in lowered:
            resolved = f"{question.rstrip('?')} in the {topic_suffix} incident?"
        elif "attacker" in lowered or lowered.startswith("who"):
            resolved = f"{question.rstrip('?')} in the {topic_suffix} incident?"
        elif lowered.startswith("how"):
            resolved = f"{question.rstrip('?')} in the {topic_suffix} incident?"
        elif lowered.startswith("when"):
            resolved = f"{question.rstrip('?')} in the {topic_suffix} incident?"
        else:
            resolved = f"{question.rstrip('?')} regarding {topic_suffix}?"

        return {
            "original_question": question,
            "resolved_question": resolved,
            "is_followup": True,
            "topic_terms": topic_terms,
        }