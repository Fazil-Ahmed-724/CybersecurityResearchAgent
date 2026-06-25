from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str
    chat_id: Optional[int] = None


class CreateChatRequest(BaseModel):
    title: str


class UserChatResponse(BaseModel):
    id: int
    title: str


class MessageResponse(BaseModel):
    role: str
    content: str


class ChatListItem(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }


class SourceItem(BaseModel):
    id: int
    title: str
    url: str
    source: str
    published_at: Optional[datetime] = None


class ChatResponse(BaseModel):
    answer: str
    chat_id: int
    sources: list[SourceItem]