from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from app.vulnerability.models import VulnerabilityContext


class GraphState(TypedDict, total=False):

    # ==========================================================
    # User Input
    # ==========================================================

    question: str
    resolved_question: str
    rewritten_query: str

    chat_id: int
    user_id: int

    # ==========================================================
    # Chat History
    # ==========================================================

    chat_history: List[Dict[str, Any]]
    chat_history_text: str

    # ==========================================================
    # Retrieval
    # ==========================================================

    topic_context: Dict[str, Any]
    retrieved_articles: List[Dict[str, Any]]

    # ==========================================================
    # Context
    # ==========================================================

    context: str
    focused_context: str

    # ==========================================================
    # Sources
    # ==========================================================

    sources: List[Dict[str, Any]]
    focused_sources: List[Dict[str, Any]]

    # ==========================================================
    # Grounding
    # ==========================================================

    grounding_context: Any
    citation_registry: Dict[int, Any]

    # ==========================================================
    # Vulnerability Intelligence
    # ==========================================================

    question_type: str
    cve_ids: List[str]
    vulnerability_context: Optional[VulnerabilityContext]
    vulnerability_report: Optional[Dict[str, Any]]

    # ==========================================================
    # Final Answer
    # ==========================================================

    answer: str
    answer_sections: Dict[str, str]
    answer_metadata: Dict[str, Any]