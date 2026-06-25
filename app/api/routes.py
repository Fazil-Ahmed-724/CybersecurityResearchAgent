from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.repositories.chat_repository import ChatRepository
from app.schemas.chat import ChatListItem
from app.services.chat_service import ChatService
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/chats", tags=["Chats"])


def get_chat_service(db: Session) -> ChatService:
    repository = ChatRepository(db)
    return ChatService(repository)


@router.get("/my-chats", response_model=list[ChatListItem])
def get_my_chats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_chat_service(db)
    chats = service.get_user_chats(current_user.id)

    return [
        ChatListItem(
            id=chat.id,
            title=chat.title,
            created_at=chat.created_at,
            updated_at=chat.updated_at,
        )
        for chat in chats
    ]


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = get_chat_service(db)

    chat = service.get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    if chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not own this chat")

    service.delete_chat(chat_id)
    return {"message": "Chat deleted successfully"}