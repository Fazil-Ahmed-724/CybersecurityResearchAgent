import re

from groq import Groq
from app.config.settings import settings


class GroqService:

    SECTION_ORDER = {
        "executive summary": 1,
        "key findings": 2,
        "impact": 3,
        "recommendations": 4
    }

    SECTION_PATTERN = re.compile(
        r"^\s*(?:\*\*)?\s*(?:\d+\.\s*)?"
        r"(executive summary|key findings|impact|recommendations)"
        r"\s*:?\s*(?:\*\*)?\s*(.*)$",
        re.IGNORECASE
    )

    SOURCES_PATTERN = re.compile(
        r"^\s*(?:#+\s*)?(?:\*\*)?sources(?:\*\*)?\s*:?\s*$",
        re.IGNORECASE
    )

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
        context: str,
        chat_history: str = ""
    ):

        prompt = f"""
You are a Senior Cybersecurity Research Analyst.

Use conversation history to resolve references
such as:

- it
- they
- this malware
- this actor
- that campaign

If the current question depends on previous messages,
combine the conversation history and the supplied context.

Never invent facts.
Only answer using information present in either:

1. Conversation History
2. Retrieved Context

If neither the conversation history nor the retrieved context
contains enough information, say so.

Conversation History:

{chat_history or "No previous conversation."}

Retrieved Context:

{context}

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
- Do not add an introductory sentence before the sections.
- Do not repeat any section.
- Do not include a Sources section.
"""

        answer = self.generate(prompt)

        return self._clean_answer(
            answer
        )

    def _clean_answer(
        self,
        answer: str
    ):

        lines = answer.strip().splitlines()
        cleaned_lines = []
        seen_sections = set()
        seen_content = set()
        skip_duplicate_section = False

        for line in lines:

            if self.SOURCES_PATTERN.match(line):
                break

            section_match = self.SECTION_PATTERN.match(
                line
            )

            if section_match:

                section_name = section_match.group(1).lower()
                section_body = section_match.group(2).strip()

                if section_name in seen_sections:
                    skip_duplicate_section = True
                    continue

                seen_sections.add(
                    section_name
                )

                skip_duplicate_section = False

                section_number = self.SECTION_ORDER[section_name]
                section_title = section_name.title()

                if cleaned_lines and cleaned_lines[-1] != "":
                    cleaned_lines.append("")

                cleaned_lines.append(
                    f"**{section_number}. {section_title}:**"
                )
                cleaned_lines.append("")

                if section_body:
                    cleaned_lines.append(
                        section_body
                    )

                continue

            if skip_duplicate_section:
                continue

            normalized_line = line.strip().lower()

            if normalized_line:

                if normalized_line in seen_content:
                    continue

                seen_content.add(
                    normalized_line
                )

            cleaned_lines.append(
                line
            )

        return "\n".join(cleaned_lines).strip()

    def rewrite_query(
        self,
        question: str,
        chat_history: str = ""
    ):

        if not chat_history.strip():
            return question

        prompt = f"""
You rewrite cybersecurity research questions for retrieval.

Use the conversation history to replace references such as:

- it
- they
- this malware
- this actor
- that campaign

Return one standalone search query.
If the question is already standalone, return it unchanged.
Do not answer the question.
Do not add facts that are not present in the conversation history.

Conversation History:

{chat_history}

Latest Question:

{question}
"""

        rewritten_query = self.generate(prompt).strip()

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

            if rewritten_query.lower().startswith(
                prefix.lower()
            ):

                rewritten_query = rewritten_query[len(prefix):].strip()

        return rewritten_query or question
