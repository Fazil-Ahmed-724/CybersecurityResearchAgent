from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SourceItem
)

from app.graph.research_graph import (
    research_graph
)

from app.database.db import (
    SessionLocal
)

from app.repositories.chat_repository import (
    ChatRepository
)

from app.services.chat_service import (
    ChatService
)

from app.api.dependencies import (
    get_current_user_id
)

from app.services.memory_service import (
    MemoryService
)

router = APIRouter()

@router.post(
    "/chat",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest,
    user_id: int = Depends(
        get_current_user_id
    )
):

    db = SessionLocal()

    try:

        repository = ChatRepository(db)

        chat_service = ChatService(
            repository
        )

        # -----------------------------
        # Create Chat
        # -----------------------------

        if request.chat_id:

            chat = chat_service.get_chat(
                request.chat_id
            )

            if not chat or chat.user_id != user_id:

                raise HTTPException(
                    status_code=403,
                    detail="You do not own this chat"
                )

            chat_id = chat.id

        else:

            chat = chat_service.create_chat(
                user_id=user_id,
                title=request.question[:50]
            )

            chat_id = chat.id

        memory_service = MemoryService(
            repository
        )

        conversation_context = memory_service.get_chat_context(
            chat_id=chat_id
        )

        # -----------------------------
        # Save User Message
        # -----------------------------

        chat_service.save_user_message(
            chat_id=chat_id,
            content=request.question
        )

        # -----------------------------
        # LangGraph
        # -----------------------------

        result = research_graph.invoke(
            {
                "question": request.question,
                "chat_history": conversation_context
            }
        )

        # -----------------------------
        # Save Assistant Message
        # -----------------------------

        chat_service.save_assistant_message(
            chat_id=chat_id,
            content=result["answer"]
        )

        # -----------------------------
        # Sources
        # -----------------------------

        sources = []
        seen_sources = set()

        for article in result["articles"]:

            source_key = article.get(
                "url"
            ) or article.get(
                "title"
            )

            if source_key in seen_sources:
                continue

            seen_sources.add(
                source_key
            )

            sources.append(
                SourceItem(
                    title=article["title"],
                    url=article["url"],
                    source=article["source"]
                )
            )

        return ChatResponse(
            answer=result["answer"],
            chat_id=chat_id,
            sources=sources
        )

    finally:

        db.close()
