from typing import TypedDict, List, Dict, Any


class GraphState(TypedDict, total=False):
    question: str
    resolved_question: str
    rewritten_query: str
    chat_id: int
    user_id: int

    # Structured chat history for retriever / follow-up topic context
    chat_history: List[Dict[str, Any]]

    # Optional plain text history for prompt/debugging if needed
    chat_history_text: str

    retrieved_articles: List[Dict[str, Any]]
    context: str
    answer: str
    topic_context: Dict[str, Any]

    # FINAL OUTPUT FOR ROUTE/UI
    sources: List[Dict[str, Any]]