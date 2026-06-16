from groq import Groq
from app.config.settings import settings


class GroqService:

    def __init__(self):
        self.client = Groq(
            api_key=settings.GROQ_API_KEY
        )

    def summarize_article(self, content: str):

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