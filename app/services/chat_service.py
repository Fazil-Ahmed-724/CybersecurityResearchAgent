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
        "too",
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

    # These are entity names that may appear in follow-up questions,
    # but should NOT become the main incident topic on their own.
    INCIDENT_ENTITY_WORDS = {
        "salesforce",
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
    }

    # Only these terms should anchor the incident thread.
    INCIDENT_ANCHOR_WORDS = {"klue", "oauth", "icarus"}

    FOLLOWUP_PRONOUNS = {
        "it", "they", "them", "that", "this", "those", "these",
        "he", "she", "his", "her", "its", "their", "there"
    }

    BAD_CONTEXT_TERMS = {
        "executive", "summary", "key", "findings", "impact", "recommendations",
        "stolen", "attackers", "companies", "data", "incident", "breach",
        "happened", "linked", "affected", "too"
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
        """
        Build the main incident topic from previous resolved questions / assistant messages.

        Rules:
        - Prefer incident anchor words like klue/oauth/icarus.
        - Do NOT let entity follow-up words like lastpass/huntress/salesforce
          become the main topic by themselves.
        - If anchor words exist, return only anchor topic.
        """
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

            if token in self.INCIDENT_ANCHOR_WORDS:
                preferred.append(token)
            else:
                fallback.append(token)

        preferred = list(dict.fromkeys(preferred))
        fallback = list(dict.fromkeys(fallback))

        # If we have incident anchors, only use those as topic
        if preferred:
            return " ".join(preferred[:3])

        # Otherwise use non-entity fallback words only
        strong_topic = [
            t for t in fallback
            if t not in self.INCIDENT_ENTITY_WORDS
        ]

        if strong_topic:
            return " ".join(strong_topic[:4])

        return None

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
        """
        Priority:
        1. last assistant resolved question
        2. last user resolved question
        3. assistant message content
        4. chat title
        """
        assistant_resolved = self._extract_last_assistant_resolved_question(messages)
        if assistant_resolved:
            topic = self._extract_context_topic_from_text(assistant_resolved)
            if topic:
                return topic

        user_resolved = self._extract_last_user_resolved_question(messages)
        if user_resolved:
            topic = self._extract_context_topic_from_text(user_resolved)
            if topic:
                return topic

        for message in reversed(messages):
            role = (message.role or "").strip().lower()
            if role != "assistant":
                continue

            topic = self._extract_context_topic_from_text(message.content or "")
            if topic:
                return topic

        if chat_title:
            topic = self._extract_context_topic_from_text(chat_title)
            if topic:
                return topic

        return None

    def _contains_explicit_topic(self, question: str) -> bool:
        tokens = set(self._tokenize(question))
        return any(token in self.INCIDENT_ANCHOR_WORDS for token in tokens)

    def _compose_incident_question(self, question: str, topic: str, suffix: str) -> str:
        question = (question or "").strip()
        question = question.rstrip(" ?")

        # If question already contains the exact topic, keep it as-is
        if topic and topic.lower() in question.lower():
            return f"{question}?"

        return f"{question} {suffix.format(topic=topic)}?"

    def _looks_like_entity_followup(self, question: str) -> bool:
        q = self._normalize_question(question)

        patterns = [
            r"^was\s+[a-z0-9._-]+\s+affected(\s+too)?\??$",
            r"^what about\s+[a-z0-9._ -]+\??$",
            r"^did\s+[a-z0-9._ -]+\??$",
            r"^is\s+[a-z0-9._ -]+\s+(involved|affected|impacted)\??$",
        ]
        return any(re.match(p, q) for p in patterns)

    # ----------------------------------
    # Follow-up detection
    # ----------------------------------

    def is_followup_question(self, question: str, chat_id: int | None = None) -> bool:
        question = (question or "").strip()
        if not question:
            return False

        lower_question = question.lower()

        # 1) explicit incident topic => standalone
        if self._contains_explicit_topic(question):
            return False

        # 2) pronoun signal => follow-up
        if self._has_pronoun_followup_signal(question):
            return True

        # 3) entity follow-up => follow-up if chat has history
        if self._looks_like_entity_followup(question):
            if chat_id:
                messages = self.get_recent_messages(chat_id, limit=12)
                return len(messages) > 0
            return True

        # 4) generic follow-up patterns
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

        # Entity follow-ups must ALWAYS stay tied to incident anchor
        if self._looks_like_entity_followup(current_question):
            return self._compose_incident_question(
                current_question,
                topic,
                "in the {topic} incident"
            )

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