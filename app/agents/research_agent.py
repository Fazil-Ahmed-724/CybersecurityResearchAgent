from app.services.retriever import Retriever
from app.services.groq_service import GroqService


class ResearchAgent:

    def answer(self, question: str):

        results = Retriever().search(question)

        if not results:

            return {
                "answer": "No relevant articles found.",
                "sources": []
            }

        context = "\n\n".join(
            [
                f"""
Title: {row['title']}
Source: {row['source']}
Summary: {row['summary']}
                """
                for row in results
            ]
        )

        prompt = f"""
You are a cybersecurity analyst.

Use ONLY the supplied context.

Question:
{question}

Context:
{context}

Provide:

1. Executive Summary
2. Key Findings
3. Impact
4. Recommendations
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

        answer = response.choices[0].message.content

        sources = [
            {
                "title": row["title"],
                "source": row["source"],
                "url": row["url"]
            }
            for row in results
        ]

        return {
            "answer": answer,
            "sources": sources
        }