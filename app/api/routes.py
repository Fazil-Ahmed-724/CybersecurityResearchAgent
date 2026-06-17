from fastapi import APIRouter

from app.schemas.chat import (
    ChatRequest,
    ChatResponse
)

from app.graph.research_graph import (
    research_graph
)

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest
):

    result = research_graph.invoke(
        {
            "question": request.question
        }
    )

    return ChatResponse(
        answer=result["answer"]
    )