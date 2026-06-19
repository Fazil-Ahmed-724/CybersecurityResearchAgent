from app.repositories.chat_repository import ChatRepository


class MemoryService:

    def __init__(self, repository: ChatRepository):
        self.repository = repository

    def get_chat_context(
        self,
        chat_id: int,
        limit: int = 10
    ) -> str:

        messages = self.repository.get_chat_messages(
            chat_id
        )

        messages = messages[-limit:]

        history = []

        for message in messages:

            history.append(
                f"{message.role.upper()}: {message.content}"
            )

        return "\n".join(history)