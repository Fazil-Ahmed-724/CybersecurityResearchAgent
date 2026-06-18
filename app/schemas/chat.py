from pydantic import BaseModel
from typing import Optional


class ChatRequest(BaseModel):
    question: str
    chat_id: Optional[int] = None


class CreateChatRequest(BaseModel):
    user_id: int
    title: str


class UserChatResponse(BaseModel):
    id: int
    title: str


class MessageResponse(BaseModel):
    role: str
    content: str


class SourceItem(BaseModel):
    title: str
    url: str
    source: str


class ChatResponse(BaseModel):
    answer: str
    chat_id: int
    sources: list[SourceItem]