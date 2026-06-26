from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.graph.research_graph import research_graph
from app.schemas.chat import ChatRequest, ChatResponse, SourceItem
from app.services.chat_service import ChatService
from app.repositories.chat_repository import ChatRepository
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


def get_chat_service(db: Session) -> ChatService:
    repository = ChatRepository(db)
    return ChatService(repository)


def serialize_sources_for_metadata(sources: list[dict]) -> list[dict]:
    safe_sources = []

    for item in sources or []:
        published_at = item.get("published_at")

        if published_at is not None:
            try:
                published_at = published_at.isoformat()
            except AttributeError:
                published_at = str(published_at)

        safe_sources.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "source": item.get("source"),
                "url": item.get("url"),
                "published_at": published_at,
            }
        )

    return safe_sources


def build_structured_chat_history(messages: list) -> list[dict]:
    history = []

    for message in messages:
        history.append(
            {
                "role": (message.role or "").strip().lower(),
                "content": (message.content or "").strip(),
                "metadata": getattr(message, "metadata_json", None) or {},
            }
        )

    return history


@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    chat_service = get_chat_service(db)

    chat_id = payload.chat_id
    chat_obj = None

    if chat_id:
        chat_obj = chat_service.get_chat(chat_id)
        if not chat_obj:
            raise HTTPException(status_code=404, detail="Chat not found")

        if chat_obj.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="You do not own this chat")
    else:
        title = payload.question.strip()
        if len(title) > 80:
            title = title[:80].rstrip() + "..."
        if not title:
            title = "New Chat"

        chat_obj = chat_service.create_chat(
            user_id=current_user.id,
            title=title
        )
        chat_id = chat_obj.id

    resolved_question = chat_service.build_resolved_question(
        chat_id=chat_id,
        current_question=payload.question,
        chat_title=chat_obj.title if chat_obj else None
    )

    # Build history BEFORE saving current message
    chat_history_text = chat_service.build_chat_history_text(chat_id=chat_id)
    recent_messages = chat_service.get_recent_messages(chat_id=chat_id, limit=12)
    chat_history_structured = build_structured_chat_history(recent_messages)

    # Now save current user message
    chat_service.save_user_message(
        chat_id=chat_id,
        content=payload.question,
        metadata_json={
            "resolved_question": resolved_question
        }
    )

    print("\n" + "=" * 80)
    print("CHAT REQUEST")
    print("=" * 80)
    print(f"Original question : {payload.question}")
    print(f"Resolved question : {resolved_question}")
    print(f"Chat ID           : {chat_id}")
    print("=" * 80)

    result = research_graph.invoke(
        {
            "question": payload.question,
            "resolved_question": resolved_question,
            "chat_id": chat_id,
            "user_id": current_user.id,
            "chat_history": chat_history_structured,
            "chat_history_text": chat_history_text,
        }
    )

    answer = (result.get("answer") or "").strip()
    sources = result.get("sources", []) or []

    if not answer:
        answer = "I could not generate an answer for this question."

    metadata_sources = serialize_sources_for_metadata(sources)

    chat_service.save_assistant_message(
        chat_id=chat_id,
        content=answer,
        metadata_json={
            "resolved_question": resolved_question,
            "rewritten_query": result.get("rewritten_query"),
            "sources": metadata_sources,
        }
    )

    source_items = [
        SourceItem(
            id=item.get("id"),
            title=item.get("title"),
            source=item.get("source"),
            url=item.get("url"),
            published_at=item.get("published_at")
        )
        for item in sources
    ]

    return ChatResponse(
        answer=answer,
        chat_id=chat_id,
        sources=source_items
    )