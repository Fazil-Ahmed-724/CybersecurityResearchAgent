from app.repositories.chat_repository import ChatRepository
from app.repositories.chat_summary_repository import ChatSummaryRepository


class MemoryService:

    def __init__(
        self,
        repository: ChatRepository,
        summary_repository: ChatSummaryRepository
    ):
        self.repository = repository
        self.summary_repository = summary_repository

    def get_chat_context(
        self,
        chat_id: int,
        limit: int = 10
    ) -> str:

        chat_summary = self.summary_repository.get_summary(
            chat_id=chat_id
        )

        messages = self.repository.get_recent_chat_messages(
            chat_id=chat_id,
            limit=limit
        )

        history = []

        for message in messages:

            history.append(
                f"{message.role.upper()}: {message.content}"
            )

        summary = chat_summary.summary if chat_summary else ""

        recent_messages = "\n".join(history)

        if not summary and not recent_messages:
            return ""

        summary = summary or "No conversation summary yet."
        recent_messages = recent_messages or "No recent messages yet."

        return f"""
Conversation Summary:

{summary}

Recent Messages:

{recent_messages}
""".strip()
