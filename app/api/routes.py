from fastapi import APIRouter

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SourceItem
)

from app.graph.research_graph import (
    research_graph
)

from app.database.db import SessionLocal

from app.repositories.chat_repository import (
    ChatRepository
)

from app.services.chat_service import (
    ChatService
)

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest
):

    db = SessionLocal()

    try:

        repository = ChatRepository(db)

        chat_service = ChatService(
            repository
        )

        # -----------------------------
        # Create chat if needed
        # -----------------------------

        if request.chat_id:

            chat_id = request.chat_id

        else:

            chat = chat_service.create_chat(
                1,
                request.question[:50]
            )

            chat_id = chat.id

        # -----------------------------
        # Save user message
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
                "question": request.question
            }
        )

        # -----------------------------
        # Save assistant answer
        # -----------------------------

        chat_service.save_assistant_message(
            chat_id=chat_id,
            content=result["answer"]
        )

        # -----------------------------
        # Sources
        # -----------------------------

        sources = []

        for article in result["articles"]:

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