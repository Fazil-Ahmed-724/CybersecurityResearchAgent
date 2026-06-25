from groq import Groq
from groq import APIStatusError

from app.config.settings import settings
from app.services.answer_cleanup import clean_generated_answer


class GroqService:
    MAX_HISTORY_CHARS = 2500
    MAX_CONTEXT_CHARS = 12000
    MAX_PROMPT_CHARS = 17000

    def __init__(self):
        self.client = Groq(
            api_key=settings.GROQ_API_KEY
        )

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def _truncate_text(self, value: str, max_chars: int) -> str:
        value = (value or "").strip()
        if len(value) <= max_chars:
            return value
        return value[:max_chars].rstrip() + "..."

    def _fit_prompt_budget(self, prompt: str, max_chars: int | None = None) -> str:
        max_chars = max_chars or self.MAX_PROMPT_CHARS
        prompt = (prompt or "").strip()

        if len(prompt) <= max_chars:
            return prompt

        return prompt[:max_chars].rstrip() + "\n\n[Prompt truncated due to size]"

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    def generate(self, prompt: str):
        prompt = self._fit_prompt_budget(prompt)

        try:
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

        except APIStatusError as exc:
            # Groq 413 / rate limit / prompt too large fallback
            error_text = str(exc).lower()
            if "413" in error_text or "request too large" in error_text or "requested" in error_text:
                raise ValueError("GROQ_PROMPT_TOO_LARGE") from exc
            raise

    # ------------------------------------------------------------------
    # Summarization
    # ------------------------------------------------------------------

    def summarize_article(
        self,
        content: str
    ):
        content = self._truncate_text(content, 12000)

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

{content}
"""

        return self.generate(prompt)

    # ------------------------------------------------------------------
    # Answer generation
    # ------------------------------------------------------------------

    def answer_question(
        self,
        question: str,
        context: str,
        chat_history: str = ""
    ):
        chat_history = self._truncate_text(chat_history, self.MAX_HISTORY_CHARS)
        context = self._truncate_text(context, self.MAX_CONTEXT_CHARS)

        prompt = f"""
You are a Senior Cybersecurity Research Analyst.

Answer ONLY from the retrieved context and recent chat memory.
Do not introduce unrelated incidents, malware campaigns, or threat actors.
If the question is about one breach/incident, stay strictly on that breach/incident.

Rules:
- Never invent facts.
- If the answer is not present in the retrieved context, say that clearly.
- Do not mix multiple unrelated incidents together.
- Prefer concise, incident-specific answers.

Recent Chat Memory:
{chat_history or "No previous conversation."}

Retrieved Context:
{context or "No retrieved context available."}

Question:
{question}

Format the answer exactly like this:

**1. Executive Summary:**

One concise paragraph.

**2. Key Findings:**

- Bullet point
- Bullet point

**3. Impact:**

- Bullet point
- Bullet point

**4. Recommendations:**

- Bullet point
- Bullet point

Formatting rules:
- Keep each section heading on its own line.
- Include the colon inside each bold section heading.
- Do not put body text on the same line as a section heading.
- Do not repeat any section.
- Do not include a Sources section.
- Keep the answer concise and grounded in the retrieved context.
"""

        try:
            answer = self.generate(prompt)
        except ValueError as exc:
            if str(exc) == "GROQ_PROMPT_TOO_LARGE":
                # smaller retry prompt
                mini_history = self._truncate_text(chat_history, 1200)
                mini_context = self._truncate_text(context, 6000)

                retry_prompt = f"""
You are a Senior Cybersecurity Research Analyst.

Answer the question only from the context below.
Do not mix unrelated incidents.

Recent Chat Memory:
{mini_history or "No previous conversation."}

Retrieved Context:
{mini_context or "No retrieved context available."}

Question:
{question}

Return exactly these sections:

**1. Executive Summary:**
**2. Key Findings:**
**3. Impact:**
**4. Recommendations:**
"""
                answer = self.generate(retry_prompt)
            else:
                raise

        return self._clean_answer(answer)

    # ------------------------------------------------------------------
    # Query rewriting
    # ------------------------------------------------------------------

    def rewrite_query(
        self,
        question: str,
        chat_history: str = ""
    ):
        """
        Keep rewrite very small.
        Only resolve pronouns / vague references.
        Never expand into unrelated malware campaigns.
        """
        if not chat_history.strip():
            return question

        compact_history = self._truncate_text(chat_history, 1600)

        prompt = f"""
You rewrite cybersecurity follow-up questions into standalone retrieval queries.

Rules:
- Only resolve references like "it", "they", "the breach", "the attackers".
- Stay strictly within the same incident/topic already present in chat history.
- Do NOT add unrelated threat actors, malware families, or extra incidents.
- If the question is already standalone, return it unchanged.
- Return exactly one line and nothing else.

Chat History:
{compact_history}

Question:
{question}
"""

        try:
            rewritten_query = self.generate(prompt).strip()
        except ValueError:
            # if prompt too large or any size issue, fallback safely
            return question

        if not rewritten_query:
            return question

        rewritten_query = rewritten_query.splitlines()[0].strip()
        rewritten_query = rewritten_query.strip("\"'")

        prefixes = (
            "Standalone search query:",
            "Search query:",
            "Query:"
        )

        for prefix in prefixes:
            if rewritten_query.lower().startswith(prefix.lower()):
                rewritten_query = rewritten_query[len(prefix):].strip()

        return rewritten_query or question

    # ------------------------------------------------------------------
    # Output cleanup
    # ------------------------------------------------------------------

    def _clean_answer(
        self,
        answer: str
    ):
        return clean_generated_answer(answer)
