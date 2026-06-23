from typing import TypedDict, List, Dict


class ResearchState(TypedDict, total=False):
    question: str
    chat_history: str
    rewritten_query: str
    articles: List[Dict]
    context: str
    answer: str