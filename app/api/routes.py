from fastapi import APIRouter

from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    SourceItem
)

from app.graph.research_graph import (
    research_graph
)

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse
)
def chat(request: ChatRequest):

    result = research_graph.invoke(
        {
            "question": request.question
        }
    )

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
        sources=sources
    )