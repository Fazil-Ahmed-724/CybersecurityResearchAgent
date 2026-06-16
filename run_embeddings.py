from app.services.vector_service import (
    VectorService
)

VectorService().generate_embeddings()

print(
    "Embedding Generation Complete"
)