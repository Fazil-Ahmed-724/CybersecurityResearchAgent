from app.models.chat import Chat
from app.models.message import Message


class ChatRepository:
    def __init__(self, db):
        self.db = db

    # ----------------------------------
    # Chats
    # ----------------------------------

    def create_chat(self, user_id: int, title: str):
        chat = Chat(user_id=user_id, title=title)
        self.db.add(chat)
        self.db.commit()
        self.db.refresh(chat)
        return chat

    def get_user_chats(self, user_id: int):
        return (
            self.db.query(Chat)
            .filter(Chat.user_id == user_id)
            .order_by(Chat.updated_at.desc())
            .all()
        )

    def get_chat(self, chat_id: int):
        return (
            self.db.query(Chat)
            .filter(Chat.id == chat_id)
            .first()
        )

    def delete_chat(self, chat_id: int):
        chat = self.get_chat(chat_id)
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
        content: str,
        metadata_json: dict | None = None
    ):
        message = Message(
            chat_id=chat_id,
            role=role,
            content=content,
            metadata_json=metadata_json
        )
        self.db.add(message)

        # also touch chat.updated_at by loading chat
        chat = self.get_chat(chat_id)
        if chat:
            chat.title = chat.title  # no-op but keeps object attached

        self.db.commit()
        self.db.refresh(message)
        return message

    def get_chat_messages(self, chat_id: int):
        return (
            self.db.query(Message)
            .filter(Message.chat_id == chat_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
            .all()
        )