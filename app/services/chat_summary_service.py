from app.services.groq_service import GroqService


class ChatSummaryService:

    def __init__(self):

        self.groq = GroqService()

    def generate_summary(
        self,
        messages,
        existing_summary: str = ""
    ):

        conversation = []

        for message in messages:

            conversation.append(
                f"{message.role.upper()}: {message.content}"
            )

        prompt = f"""
Summarize this cybersecurity research conversation.

Keep:

- entities
- malware names
- threat actors
- findings
- important follow-up resolutions

Maximum 300 words.
Never invent facts.

Existing Conversation Summary:

{existing_summary or "No existing summary."}

Recent Messages:

{chr(10).join(conversation)}
"""

        return self.groq.generate(
            prompt
        ).strip()
