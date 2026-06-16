from app.services.embedding_service import (
    EmbeddingService
)

embedder = EmbeddingService()

vector = embedder.generate_embedding(
    "North Korean malware attacks"
)

print(type(vector))
print(len(vector))