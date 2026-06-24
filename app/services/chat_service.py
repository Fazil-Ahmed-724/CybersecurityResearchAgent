import re
from typing import Any, Optional

from app.repositories.chat_repository import ChatRepository


class ChatService:
    FOLLOWUP_HINT_WORDS = {
        "it",
        "its",
        "they",
        "them",
        "their",
        "that",
        "those",
        "this",
        "these",
        "he",
        "she",
        "him",
        "her",
        "there",
        "then",
        "attackers",
        "victims",
        "impact",
        "impacted",
        "stolen",
        "linked",
        "related",
        "breach",
        "incident",
        "campaign",
        "malware",
        "group",
        "actor",
        "actors",
        "who",
        "what",
        "which",
        "how",
        "when",
        "where",
        "companies",
        "data",
        "affected",
        "happened",
    }

    ENTITY_STOPWORDS = {
        "what",
        "which",
        "who",
        "when",
        "where",
        "why",
        "how",
        "did",
        "does",
        "is",
        "are",
        "was",
        "were",
        "the",
        "this",
        "that",
        "these",
        "those",
        "about",
        "into",
        "from",
        "with",
        "for",
        "have",
        "has",
        "had",
        "tell",
        "explain",
        "linked",
        "attackers",
        "victims",
        "incident",
        "breach",
        "attack",
        "attacks",
        "campaign",
        "malware",
        "story",
        "news",
        "article",
        "data",
        "affected",
        "companies",
        "happened",
    }

    TOPIC_CANDIDATE_WORDS = {
        "klue",
        "oauth",
        "salesforce",
        "icarus",
        "lastpass",
        "narwhalrat",
        "lazarus",
        "bluenoroff",
        "fortinet",
        "fortisandbox",
        "fortibleed",
        "wordpress",
        "clickfix",
        "whatsapp",
        "microsoft",
        "npm",
        "malware",
        "ransomware",
        "breach",
        "incident",
        "campaign",
    }

    def __init__(self, repository: ChatRepository):
        self.repository = repository

    # ----------------------------------
    # Chats
    # ----------------------------------

    def create_chat(self, user_id: int, title: str):
        return self.repository.create_chat(user_id=user_id, title=title)

    def get_user_chats(self, user_id: int):
        return self.repository.get_user_chats(user_id)

    def get_chat(self, chat_id: int):
        return self.repository.get_chat(chat_id)

    def delete_chat(self, chat_id: int):
        self.repository.delete_chat(chat_id)

    # ----------------------------------
    # Messages
    # ----------------------------------

    def save_user_message(self, chat_id: int, content: str):
        return self.repository.save_message(
            chat_id=chat_id,
            role="user",
            content=content
        )

    def save_assistant_message(
        self,
        chat_id: int,
        content: str,
        metadata_json: dict | None = None
    ):
        return self.repository.save_message(
            chat_id=chat_id,
            role="assistant",
            content=content,
            metadata_json=metadata_json
        )

    def get_chat_messages(self, chat_id: int):
        return self.repository.get_chat_messages(chat_id)

    # ----------------------------------
    # History
    # ----------------------------------

    def build_chat_history_text(self, chat_id: int, limit: int = 8) -> str:
        messages = self.get_chat_messages(chat_id) or []
        if not messages:
            return ""

        recent_messages = messages[-limit:]
        lines = []

        for message in recent_messages:
            role = (message.role or "").strip().lower()
            speaker = "Assistant" if role == "assistant" else "User"

            content = (message.content or "").strip()
            if not content:
                continue

            content = self._truncate_text(content, 700)
            lines.append(f"{speaker}: {content}")

        return "\n".join(lines)

    def get_recent_messages(self, chat_id: int, limit: int = 12):
        messages = self.get_chat_messages(chat_id) or []
        if not messages:
            return []
        return messages[-limit:]

    # ----------------------------------
    # Follow-up detection / resolution
    # ----------------------------------

    def is_followup_question(self, question: str) -> bool:
        question = (question or "").strip().lower()
        if not question:
            return False

        tokens = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", question)

        if len(tokens) <= 7:
            return True

        if any(token in self.FOLLOWUP_HINT_WORDS for token in tokens):
            return True

        followup_patterns = [
            r"\bwhat about\b",
            r"\bhow about\b",
            r"\bwho were they\b",
            r"\bwho was behind it\b",
            r"\bwhich attackers\b",
            r"\bwhat data\b",
            r"\bwho was impacted\b",
            r"\bwhat happened next\b",
            r"\bhow did it happen\b",
            r"\bwhich companies\b",
        ]

        return any(re.search(pattern, question) for pattern in followup_patterns)

    def build_resolved_question(
        self,
        chat_id: int,
        current_question: str,
        chat_title: Optional[str] = None
    ) -> str:
        current_question = (current_question or "").strip()
        if not current_question:
            return ""

        # already standalone topic question
        lower_q = current_question.lower()
        strong_topic_words = [
            "klue", "oauth", "lastpass", "salesforce",
            "narwhalrat", "fortibleed", "icarus", "xolis"
        ]
        if any(word in lower_q for word in strong_topic_words):
            return current_question

        if not self.is_followup_question(current_question):
            return current_question

        messages = self.get_recent_messages(chat_id=chat_id, limit=12)

        # exclude current just-saved user message
        previous_messages = messages[:-1] if messages else []

        last_user_question = self._get_last_user_question(previous_messages)
        last_assistant_answer = self._get_last_assistant_answer(previous_messages)

        topic_phrase = self._extract_topic_from_text(last_user_question)

        if not topic_phrase and chat_title:
            topic_phrase = self._extract_topic_from_text(chat_title)

        if not topic_phrase and last_assistant_answer:
            answer_keywords = self._extract_keywords(last_assistant_answer, limit=4)
            if answer_keywords:
                topic_phrase = " ".join(answer_keywords)

        if not topic_phrase:
            return current_question

        return self._make_followup_standalone(
            current_question=current_question,
            topic_phrase=topic_phrase
        )

    # ----------------------------------
    # Helpers
    # ----------------------------------

    def _truncate_text(self, value: str, max_chars: int) -> str:
        value = (value or "").strip()
        if len(value) <= max_chars:
            return value
        return value[:max_chars].rstrip() + "..."

    def _extract_keywords(self, text_value: str, limit: int = 8) -> list[str]:
        tokens = re.findall(
            r"[a-zA-Z0-9][a-zA-Z0-9._-]*",
            (text_value or "").lower()
        )

        keywords = []
        seen = set()

        for token in tokens:
            if len(token) < 3:
                continue
            if token in self.ENTITY_STOPWORDS:
                continue
            if token in seen:
                continue

            seen.add(token)
            keywords.append(token)

            if len(keywords) >= limit:
                break

        return keywords

    def _get_last_user_question(self, messages: list[Any]) -> str:
        for message in reversed(messages):
            if (message.role or "").lower() == "user":
                content = (message.content or "").strip()
                if content:
                    return content
        return ""

    def _get_last_assistant_answer(self, messages: list[Any]) -> str:
        for message in reversed(messages):
            if (message.role or "").lower() == "assistant":
                content = (message.content or "").strip()
                if content:
                    return content
        return ""

    def _extract_topic_from_text(self, text_value: str) -> str:
        text_value = (text_value or "").strip()
        if not text_value:
            return ""

        original_tokens = re.findall(r"[A-Za-z0-9\-\']+", text_value)
        if not original_tokens:
            return ""

        keep = []
        for token in original_tokens:
            clean = token.lower()

            if len(clean) <= 2:
                continue
            if clean in self.ENTITY_STOPWORDS:
                continue

            if (
                token[0].isupper()
                or clean in self.TOPIC_CANDIDATE_WORDS
                or any(ch.isdigit() for ch in token)
                or "-" in token
            ):
                keep.append(token)

        if not keep:
            keywords = self._extract_keywords(text_value, limit=4)
            return " ".join(keywords).strip()

        dedup = []
        seen = set()
        for token in keep:
            low = token.lower()
            if low in seen:
                continue
            seen.add(low)
            dedup.append(token)

        topic = " ".join(dedup[:5]).strip()
        topic = re.sub(r"\s+", " ", topic).strip()
        return topic

    def _make_followup_standalone(
        self,
        current_question: str,
        topic_phrase: str
    ) -> str:
        current_question = (current_question or "").strip()
        topic_phrase = (topic_phrase or "").strip()

        if not current_question or not topic_phrase:
            return current_question

        q_lower = current_question.lower().strip(" ?")

        if "which attackers" in q_lower or "who was behind" in q_lower:
            return f"Which attackers were linked to {topic_phrase}?"

        if ("what data" in q_lower and "stolen" in q_lower) or q_lower.startswith("what data"):
            return f"What data was stolen in {topic_phrase}?"

        if "which companies" in q_lower or "who was affected" in q_lower:
            return f"Which companies were affected by {topic_phrase}?"

        if "what happened" in q_lower:
            return f"What happened in {topic_phrase}?"

        if "impact" in q_lower or "affected" in q_lower:
            return f"What was the impact of {topic_phrase}?"

        return f"{current_question.rstrip('?')} in {topic_phrase}?"