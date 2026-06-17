from app.services.question_answering_service import (
    QuestionAnsweringService
)

from app.services.retriever import Retriever
from app.services.context_builder import ContextBuilder


question = (
    "What malware campaigns have North Korean hackers "
    "been involved in recently?"
)

retriever = Retriever()

articles = retriever.search(
    question
)

print(len(articles))

context = ContextBuilder().build(
    articles
)

service = QuestionAnsweringService()

answer = service.answer_question(
    question=question,
    context=context
)

print("\n")
print("=" * 50)
print("ANSWER")
print("=" * 50)

print(answer)

print("\n")
print("=" * 50)
print("SOURCES")
print("=" * 50)

for article in articles:
    print(
        article["distance"],
        article["title"]
    )