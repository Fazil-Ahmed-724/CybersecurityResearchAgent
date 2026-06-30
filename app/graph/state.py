from typing import TypedDict, List, Dict, Any


class GraphState(TypedDict, total=False):
    # User input
    question: str
    resolved_question: str
    rewritten_query: str

    chat_id: int
    user_id: int

    # Chat history
    chat_history: List[Dict[str, Any]]
    chat_history_text: str

    # Retrieval
    topic_context: Dict[str, Any]
    retrieved_articles: List[Dict[str, Any]]

    # Context
    context: str
    focused_context: str

    # Sources
    sources: List[Dict[str, Any]]
    focused_sources: List[Dict[str, Any]]

    # Grounding
    grounding_context: Any
    citation_registry: Dict[int, Any]
    
    # Final answer
    answer: str
    answer_sections: Dict[str, str]
    answer_metadata: Dict[str, Any]
