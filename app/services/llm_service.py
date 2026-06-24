from groq import Groq

from app.core.config import settings


class LLMService:
    def __init__(self):
        self.client = Groq(api_key=settings.GROQ_API_KEY)
        self.model = settings.GROQ_MODEL

    def generate(self, prompt: str) -> str:
        prompt = (prompt or "").strip()

        # hard cap to avoid Groq 413 / prompt explosion
        if len(prompt) > 12000:
            prompt = prompt[:12000].rstrip() + "\n\n[Context truncated due to token limit.]"

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a cybersecurity research assistant. "
                        "Answer only from the provided context. "
                        "If context is insufficient, clearly say so."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0.2,
        )

        if not response or not response.choices:
            return ""

        message = response.choices[0].message
        if not message:
            return ""

        return (message.content or "").strip()