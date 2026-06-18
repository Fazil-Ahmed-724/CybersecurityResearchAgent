from fastapi import APIRouter
from pydantic import BaseModel

from app.database.db import SessionLocal

from app.repositories.chat_repository import (
    ChatRepository
)

from app.services.chat_service import (
    ChatService
)

from app.schemas.chat import (
    CreateChatRequest
)

router = APIRouter(
    prefix="/chats",
    tags=["Chats"]
)


class MessageRequest(BaseModel):

    chat_id: int
    role: str
    content: str


# ----------------------------------
# Create Chat
# ----------------------------------

@router.post("/")
def create_chat(
    request: CreateChatRequest
):

    db = SessionLocal()

    try:

        repository = ChatRepository(db)

        service = ChatService(repository)

        chat = service.create_chat(
            user_id=request.user_id,
            title=request.title
        )

        return {
            "id": chat.id,
            "user_id": chat.user_id,
            "title": chat.title
        }

    finally:

        db.close()


# ----------------------------------
# User Chats
# ----------------------------------

@router.get("/user/{user_id}")
def get_user_chats(
    user_id: int
):

    db = SessionLocal()

    try:

        repository = ChatRepository(db)

        service = ChatService(repository)

        chats = service.get_user_chats(
            user_id
        )

        return [
            {
                "id": chat.id,
                "title": chat.title
            }
            for chat in chats
        ]

    finally:

        db.close()


# ----------------------------------
# Save Message
# ----------------------------------

@router.post("/message")
def save_message(
    request: MessageRequest
):

    db = SessionLocal()

    try:

        repository = ChatRepository(db)

        message = repository.save_message(
            chat_id=request.chat_id,
            role=request.role,
            content=request.content
        )

        return {
            "id": message.id,
            "chat_id": message.chat_id,
            "role": message.role
        }

    finally:

        db.close()


# ----------------------------------
# Chat Messages
# ----------------------------------

@router.get("/{chat_id}/messages")
def get_chat_messages(
    chat_id: int
):

    db = SessionLocal()

    try:

        repository = ChatRepository(db)

        service = ChatService(repository)

        messages = service.get_chat_messages(
            chat_id
        )

        return [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in messages
        ]

    finally:

        db.close()