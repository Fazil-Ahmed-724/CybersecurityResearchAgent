from app.services.retriever import Retriever
from app.services.context_builder import ContextBuilder

question = "North Korean hackers malware campaign"

articles = Retriever().search(question)

context = ContextBuilder().build(
    articles
)

print(context)