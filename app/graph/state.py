from typing import TypedDict


class ResearchState(TypedDict, total=False):

    question: str

    chat_history: str

    rewritten_query: str

    articles: list

    context: str

    answer: str
