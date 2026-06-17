from app.graph.research_graph import (
    research_graph
)

result = research_graph.invoke(
    {
        "question":
        "What malware campaigns have North Korean hackers been involved in recently?"
    }
)

print("\n")
print("=" * 50)
print("FINAL ANSWER")
print("=" * 50)

print(result["answer"])