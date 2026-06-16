import ollama


class EmbeddingService:

    def __init__(self):
        self.model = "nomic-embed-text"

    def generate_embedding(self, text: str):

        response = ollama.embed(
            model=self.model,
            input=text
        )

        return response["embeddings"][0]