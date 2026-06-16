from app.services.retriever import Retriever

results = Retriever().search(
    "North Korean hackers malware campaign"
)

for row in results:

    print("=" * 50)

    print(row.title)

    print(row.source)

    print(row.distance)