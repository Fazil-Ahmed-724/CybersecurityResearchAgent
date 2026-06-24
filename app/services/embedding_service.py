import ollama


class EmbeddingService:
    def __init__(self):
        self.model = "nomic-embed-text"

        # safe limits for embedding input
        self.max_content_chars = 4000
        self.max_summary_chars = 1500
        self.max_title_chars = 500
        self.max_query_chars = 1000

    def build_embedding_text(
        self,
        title: str = "",
        summary: str = "",
        content: str = ""
    ) -> str:
        """
        Build article text for embedding.
        """
        title = (title or "").strip()[:self.max_title_chars]
        summary = (summary or "").strip()[:self.max_summary_chars]
        content = (content or "").strip()[:self.max_content_chars]

        return (
            f"Title: {title}\n\n"
            f"Summary:\n{summary}\n\n"
            f"Content:\n{content}"
        )

    def build_query_text(self, query: str) -> str:
        """
        Build search query text for embedding.
        """
        query = (query or "").strip()[:self.max_query_chars]
        return f"Query: {query}"

    def generate_embedding(self, text: str):
        response = ollama.embed(
            model=self.model,
            input=text
        )
        return response["embeddings"][0]

    def generate_article_embedding(
        self,
        title: str = "",
        summary: str = "",
        content: str = ""
    ):
        text = self.build_embedding_text(
            title=title,
            summary=summary,
            content=content
        )
        return self.generate_embedding(text)

    def embed_query(self, query: str):
        """
        Generate embedding for user search query.
        Retriever isi method ko call karta hai.
        """
        text = self.build_query_text(query)
        return self.generate_embedding(text)