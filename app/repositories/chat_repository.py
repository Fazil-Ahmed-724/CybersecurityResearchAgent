from sqlalchemy.orm import Session

from app.models.chat import Chat
from app.models.message import Message


class ChatRepository:

    def __init__(
        self,
        db: Session
    ):
        self.db = db

    # ----------------------------------
    # Chats
    # ----------------------------------

    def create_chat(
        self,
        user_id: int,
        title: str
    ):

        chat = Chat(
            user_id=user_id,
            title=title
        )

        self.db.add(chat)

        self.db.commit()

        self.db.refresh(chat)

        return chat

    def get_user_chats(
        self,
        user_id: int
    ):

        return (
            self.db.query(Chat)
            .filter(
                Chat.user_id == user_id
            )
            .order_by(Chat.id.desc())
            .all()
        )

    def get_chat(
        self,
        chat_id: int
    ):

        return (
            self.db.query(Chat)
            .filter(
                Chat.id == chat_id
            )
            .first()
        )

    def delete_chat(
        self,
        chat_id: int
    ):

        chat = self.get_chat(
            chat_id
        )

        if chat:

            self.db.delete(chat)

            self.db.commit()

    # ----------------------------------
    # Messages
    # ----------------------------------

    def save_message(
        self,
        chat_id: int,
        role: str,
        content: str
    ):

        message = Message(
            chat_id=chat_id,
            role=role,
            content=content
        )

        self.db.add(message)

        self.db.commit()

        self.db.refresh(message)

        return message

    def get_chat_messages(
        self,
        chat_id: int
    ):

        return (
            self.db.query(Message)
            .filter(
                Message.chat_id == chat_id
            )
            .order_by(Message.id.asc())
            .all()
        )