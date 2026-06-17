from typing import TypedDict


class ResearchState(TypedDict):

    question: str

    articles: list

    context: str

    answer: str