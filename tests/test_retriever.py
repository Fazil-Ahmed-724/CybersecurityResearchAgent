from app.services.retriever import Retriever

retriever = Retriever()

results = retriever.search(
    query="North Korean hackers malware campaign",
    limit=10,
    threshold=0.33
)

for item in results:

    print("=" * 50)

    print(item["title"])

    print(
        f"distance={item['distance']:.4f}"
    )

    print(
        f"rank={item['rank_score']:.4f}"
    )