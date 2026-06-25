import re
from typing import Optional

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
        "behind",
        "stolen",
        "happen",
    }

    TOPIC_CANDIDATE_WORDS = {
        "klue",
        "oauth",
        "salesforce",
        "icarus",
        "lastpass",
        "huntress",
        "recorded",
        "future",
        "tanium",
        "jamf",
        "gong",
        "insurity",
        "sprout",
        "social",
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
        "lazarus",
        "bluenoroff",
    }

    FOLLOWUP_PRONOUNS = {
        "it", "they", "them", "that", "this", "those", "these",
        "he", "she", "his", "her", "its", "their", "there"
    }

    BAD_CONTEXT_TERMS = {
        "executive", "summary", "key", "findings", "impact", "recommendations",
        "stolen", "attackers", "companies", "data", "incident", "breach",
        "happened", "linked", "affected"
    }

    GENERIC_QUESTION_PATTERNS = [
        r"^what happened\??$",
        r"^what data was stolen\??$",
        r"^what was stolen\??$",
        r"^which companies were affected\??$",
        r"^who was affected\??$",
        r"^who was impacted\??$",
        r"^which attackers were linked to it\??$",
        r"^who was behind it\??$",
        r"^who were they\??$",
    ]

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

    def save_user_message(
        self,
        chat_id: int,
        content: str,
        metadata_json: dict | None = None
    ):
        return self.repository.save_message(
            chat_id=chat_id,
            role="user",
            content=content,
            metadata_json=metadata_json
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

    def build_chat_history_text(self, chat_id: int, limit: int = 12) -> str:
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

            lines.append(f"{speaker}: {content}")

        return "\n".join(lines)

    def get_recent_messages(self, chat_id: int, limit: int = 12):
        messages = self.get_chat_messages(chat_id) or []
        if not messages:
            return []
        return messages[-limit:]

    # ----------------------------------
    # Helpers
    # ----------------------------------

    def _tokenize(self, value: str) -> list[str]:
        return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9._-]*", (value or "").lower())

    def _normalize_question(self, value: str) -> str:
        value = (value or "").strip().lower()
        value = re.sub(r"\s+", " ", value)
        return value

    def _has_pronoun_followup_signal(self, question: str) -> bool:
        tokens = self._tokenize(question)
        return any(token in self.FOLLOWUP_PRONOUNS for token in tokens)

    def _is_generic_question(self, question: str) -> bool:
        q = self._normalize_question(question)
        return any(re.match(pattern, q) for pattern in self.GENERIC_QUESTION_PATTERNS)

    def _extract_topic_keywords(self, text_value: str) -> list[str]:
        tokens = self._tokenize(text_value)
        keywords = []

        for token in tokens:
            if len(token) < 3:
                continue
            if token in self.ENTITY_STOPWORDS:
                continue
            if token in self.BAD_CONTEXT_TERMS:
                continue
            keywords.append(token)

        seen = set()
        result = []
        for item in keywords:
            if item not in seen:
                seen.add(item)
                result.append(item)

        return result[:10]

    def _extract_context_topic_from_text(self, text_value: str) -> Optional[str]:
        if not text_value:
            return None

        tokens = self._tokenize(text_value)

        preferred = []
        fallback = []

        for token in tokens:
            if len(token) < 3:
                continue
            if token in self.ENTITY_STOPWORDS:
                continue
            if token in self.BAD_CONTEXT_TERMS:
                continue

            if token in self.TOPIC_CANDIDATE_WORDS:
                preferred.append(token)
            else:
                fallback.append(token)

        seen = set()
        ordered = []
        for token in preferred + fallback:
            if token not in seen:
                seen.add(token)
                ordered.append(token)

        if not ordered:
            return None

        return " ".join(ordered[:4])

    def _extract_last_assistant_resolved_question(self, messages) -> Optional[str]:
        for message in reversed(messages):
            role = (message.role or "").strip().lower()
            if role != "assistant":
                continue

            metadata = getattr(message, "metadata_json", None) or {}
            resolved = (metadata.get("resolved_question") or "").strip()
            if resolved:
                return resolved

        return None

    def _extract_last_user_resolved_question(self, messages) -> Optional[str]:
        for message in reversed(messages):
            role = (message.role or "").strip().lower()
            if role != "user":
                continue

            metadata = getattr(message, "metadata_json", None) or {}
            resolved = (metadata.get("resolved_question") or "").strip()
            if resolved:
                return resolved

        return None

    def _extract_best_context_topic(self, messages, chat_title: str | None = None) -> Optional[str]:
        assistant_resolved = self._extract_last_assistant_resolved_question(messages)
        if assistant_resolved:
            topic = self._extract_context_topic_from_text(assistant_resolved)
            if topic:
                return topic

        for message in reversed(messages):
            role = (message.role or "").strip().lower()
            if role != "assistant":
                continue

            topic = self._extract_context_topic_from_text(message.content or "")
            if topic:
                return topic

        user_resolved = self._extract_last_user_resolved_question(messages)
        if user_resolved:
            topic = self._extract_context_topic_from_text(user_resolved)
            if topic:
                return topic

        if chat_title:
            topic = self._extract_context_topic_from_text(chat_title)
            if topic:
                return topic

        return None

    def _contains_explicit_topic(self, question: str) -> bool:
        tokens = set(self._tokenize(question))
        return any(token in self.TOPIC_CANDIDATE_WORDS for token in tokens)

    def _compose_incident_question(self, question: str, topic: str, suffix: str) -> str:
        question = (question or "").strip()
        question = question.rstrip(" ?")

        if re.search(r"\b(in|about)\b", question.lower()):
            return f"{question}?"

        return f"{question} {suffix.format(topic=topic)}?"

    # ----------------------------------
    # Follow-up detection
    # ----------------------------------

    def is_followup_question(self, question: str, chat_id: int | None = None) -> bool:
        question = (question or "").strip()
        if not question:
            return False

        # if question already contains explicit incident/topic words,
        # treat it as standalone unless it also has a pronoun signal
        if self._contains_explicit_topic(question):
            return self._has_pronoun_followup_signal(question)

        # clear pronoun / reference signal => follow-up
        if self._has_pronoun_followup_signal(question):
            return True

        lower_question = question.lower()

        followup_patterns = [
            r"\bwhat about\b",
            r"\bhow about\b",
            r"\bwho were they\b",
            r"\bwho was behind it\b",
            r"\bwhich attackers were linked to it\b",
            r"\bwhat data was stolen\b",
            r"\bwho was impacted\b",
            r"\bwhat happened next\b",
            r"\bhow did it happen\b",
            r"\bwhich companies were affected\b",
            r"\bwhat was stolen\b",
        ]

        if any(re.search(pattern, lower_question) for pattern in followup_patterns):
            # only treat as follow-up if there is actually history/context
            if chat_id:
                messages = self.get_recent_messages(chat_id, limit=12)
                return len(messages) > 0
            return True

        return False

    # ----------------------------------
    # Resolved question builder
    # ----------------------------------

    def build_resolved_question(
        self,
        chat_id: int,
        current_question: str,
        chat_title: str | None = None
    ) -> str:
        current_question = (current_question or "").strip()
        if not current_question:
            return ""

        messages = self.get_recent_messages(chat_id, limit=12)

        # no history => standalone
        if not messages:
            return current_question

        if not self.is_followup_question(current_question, chat_id=chat_id):
            return current_question

        topic = self._extract_best_context_topic(messages, chat_title=chat_title)
        if not topic:
            return current_question

        question_lower = current_question.lower()

        if any(p in question_lower for p in ["what happened", "summarize", "summary", "overview"]):
            return self._compose_incident_question(
                current_question,
                topic,
                "in the {topic} incident"
            )

        if any(p in question_lower for p in ["who", "which attackers", "who was behind"]):
            return self._compose_incident_question(
                current_question,
                topic,
                "in the {topic} incident"
            )

        if any(p in question_lower for p in ["what data", "what was stolen"]):
            return self._compose_incident_question(
                current_question,
                topic,
                "in the {topic} breach"
            )

        if any(p in question_lower for p in ["which companies", "who was affected", "who was impacted"]):
            return self._compose_incident_question(
                current_question,
                topic,
                "in the {topic} incident"
            )

        return self._compose_incident_question(
            current_question,
            topic,
            "about {topic}"
        )