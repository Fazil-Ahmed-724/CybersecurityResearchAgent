from app.repositories.chat_repository import (
    ChatRepository
)


class ChatService:

    def __init__(
        self,
        repository: ChatRepository
    ):
        self.repository = repository

    # ----------------------------------
    # Chats
    # ----------------------------------

    def create_chat(
        self,
        user_id: int,
        title: str
    ):

        return self.repository.create_chat(
            user_id=user_id,
            title=title
        )

    def get_user_chats(
        self,
        user_id: int
    ):

        return self.repository.get_user_chats(
            user_id
        )

    def get_chat(
        self,
        chat_id: int
    ):

        return self.repository.get_chat(
            chat_id
        )

    def delete_chat(
        self,
        chat_id: int
    ):

        self.repository.delete_chat(
            chat_id
        )

    # ----------------------------------
    # Messages
    # ----------------------------------

    def save_user_message(
        self,
        chat_id: int,
        content: str
    ):

        return self.repository.save_message(
            chat_id=chat_id,
            role="user",
            content=content
        )

    def save_assistant_message(
        self,
        chat_id: int,
        content: str
    ):

        return self.repository.save_message(
            chat_id=chat_id,
            role="assistant",
            content=content
        )

    def get_chat_messages(
        self,
        chat_id: int
    ):

        return self.repository.get_chat_messages(
            chat_id
        )