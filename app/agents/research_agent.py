from app.services.retriever import Retriever
from app.services.groq_service import GroqService


class ResearchAgent:

    def answer(self, question: str):

        results = Retriever().search(
            question
        )

        context = "\n\n".join(
            [
                row.summary
                for row in results
            ]
        )

        prompt = f"""
You are a cybersecurity analyst.

Answer using only the provided context.

Question:
{question}

Context:
{context}
"""

        groq = GroqService()

        response = groq.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response.choices[0].message.content