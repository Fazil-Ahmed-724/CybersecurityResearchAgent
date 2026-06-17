from groq import Groq
from app.config.settings import settings


class GroqService:

    def __init__(self):
        self.client = Groq(
            api_key=settings.GROQ_API_KEY
        )

    def generate(self, prompt: str):

        response = self.client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.2
        )

        return response.choices[0].message.content

    def summarize_article(
        self,
        content: str
    ):

        prompt = f"""
You are a cybersecurity analyst.

Summarize the following cybersecurity article.

Requirements:
- 5 to 10 bullet points
- Mention threats
- Mention vulnerabilities
- Mention affected systems
- Mention mitigations

Article:

{content[:12000]}
"""

        return self.generate(prompt)

    def answer_question(
        self,
        question: str,
        context: str
    ):

        prompt = f"""
You are a Senior Cybersecurity Research Analyst.

Answer ONLY using the supplied context.

If the context does not contain enough information,
say so.

Context:

{context}

Question:

{question}

Provide:

1. Executive Summary
2. Key Findings
3. Impact
4. Recommendations
"""

        return self.generate(prompt)