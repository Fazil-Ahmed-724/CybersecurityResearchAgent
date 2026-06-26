from app.services.groq_service import GroqService


class ChatSummaryService:
    def __init__(self):
        self.groq = GroqService()

    def generate_summary(self, messages, existing_summary: str = ""):
        conversation = []

        for message in messages:
            role = (message.role or "").upper()
            content = (message.content or "").strip()
            if not content:
                continue

            metadata = getattr(message, "metadata_json", None) or {}
            resolved = metadata.get("resolved_question")

            if resolved:
                conversation.append(
                    f"{role}: {content}\nRESOLVED_QUESTION: {resolved}"
                )
            else:
                conversation.append(f"{role}: {content}")

        prompt = f"""
You are summarizing a cybersecurity research chat.

Your job is to preserve the conversation in a way that helps future follow-up questions.

Return a concise summary with these sections if information exists:

1. Primary incident / topic
2. Key entities involved
   - companies
   - threat actors
   - malware / campaign names
3. Important findings already established
4. Follow-up conclusions already answered
   - e.g. whether LastPass was affected
   - whether Huntress was affected
   - whether Salesforce disabled an integration
5. Open questions / uncertainties

Rules:
- Maximum 300 words
- Never invent facts
- Prefer facts explicitly stated in the conversation
- Preserve incident anchor terms like Klue, OAuth, Icarus, Salesforce, LastPass, Huntress when relevant
- If a resolved question is present, use it to understand what the message was actually about

Existing summary:
{existing_summary or "No existing summary."}

Conversation:
{chr(10).join(conversation)}
"""

        return self.groq.generate(prompt).strip()