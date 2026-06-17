from pydantic import BaseModel


class ChatRequest(BaseModel):
    question: str


class SourceItem(BaseModel):
    title: str
    url: str
    source: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceItem]