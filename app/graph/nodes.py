from app.services.retriever import Retriever
from app.services.context_builder import ContextBuilder
from app.services.question_answering_service import (
    QuestionAnsweringService
)

retriever = Retriever()
context_builder = ContextBuilder()
qa_service = QuestionAnsweringService()


def retrieve_articles(state):
    print("\n[Node] Retrieving Articles")

    query = state["question"]

    chat_history = state.get(
        "chat_history",
        ""
    )

    if chat_history.strip():
        try:
            query = qa_service.rewrite_query(
                question=state["question"],
                chat_history=chat_history
            )
        except Exception as error:
            print("\nQuery rewrite failed:")
            print(error)

    state["rewritten_query"] = query

    print("\nSearch Query:")
    print(query)

    articles = retriever.search(
        query=query
    )

    state["articles"] = articles
    return state


def build_context(state):
    print("\n[Node] Building Context")

    context = context_builder.build(
        state["articles"]
    )

    state["context"] = context
    return state


def generate_answer(state):
    print("\n[Node] Generating Answer")

    answer = qa_service.answer_question(
        question=state["question"],
        context=state["context"],
        chat_history=state.get(
            "chat_history",
            ""
        )
    )

    state["answer"] = answer
    return state