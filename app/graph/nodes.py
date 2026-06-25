from __future__ import annotations

from typing import Any, Dict, List

from app.graph.state import GraphState
from app.services.retriever import Retriever
from app.services.llm_service import LLMService
from app.services.answer_cleanup import clean_generated_answer


MAX_SUMMARY_CHARS = 1200
MAX_CONTENT_CHARS = 2500
MAX_TOTAL_CONTEXT_CHARS = 7000


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clip_text(value: str, limit: int) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + "..."


def _normalize_article(article: Any) -> Dict[str, Any]:
    # Supports both SQLAlchemy Article objects and dict-like items
    if isinstance(article, dict):
        return {
            "id": article.get("id"),
            "title": article.get("title") or "Untitled",
            "source": article.get("source") or "Unknown",
            "url": article.get("url") or "",
            "published_at": article.get("published_at"),
            "summary": article.get("summary") or "",
            "content": article.get("content") or "",
        }

    return {
        "id": getattr(article, "id", None),
        "title": getattr(article, "title", None) or "Untitled",
        "source": getattr(article, "source_name", None) or getattr(article, "source", None) or "Unknown",
        "url": getattr(article, "url", None) or "",
        "published_at": getattr(article, "published_at", None),
        "summary": getattr(article, "summary", None) or "",
        "content": getattr(article, "content", None) or "",
    }


def retrieve_articles_node(state: GraphState) -> GraphState:
    print("\n[Node] Retrieving Articles")

    original_question = _safe_str(state.get("question"))
    resolved_question = _safe_str(state.get("resolved_question")) or original_question
    chat_history = state.get("chat_history") or []

    print("\n[Node] Original Question:")
    print(original_question)

    print("\n[Node] Resolved Question:")
    print(resolved_question)

    retriever = Retriever()

    retrieval_result = retriever.search(
        original_question=original_question,
        resolved_question=resolved_question,
        chat_history=chat_history,
    )

    rewritten_query = retrieval_result.get("rewritten_query") or resolved_question
    topic_context = retrieval_result.get("topic_context") or {}
    articles = retrieval_result.get("articles") or []

    normalized_articles = [_normalize_article(article) for article in articles]

    print("\n[Node] Search Query:")
    print(rewritten_query)

    print("\n[Node] Topic Context:")
    print(topic_context)

    print("\n[Node] Final Sources:")
    for idx, item in enumerate(normalized_articles, start=1):
        print(f"{idx}. {item.get('source')} | {item.get('title')}")

    return {
        **state,
        "rewritten_query": rewritten_query,
        "topic_context": topic_context,
        "retrieved_articles": normalized_articles,
    }


def build_context_node(state: GraphState) -> GraphState:
    print("\n[Node] Building Context")

    articles = state.get("retrieved_articles", []) or []

    if not articles:
        return {
            **state,
            "context": "",
            "sources": [],
        }

    context_blocks: List[str] = []
    total_chars = 0

    for idx, article in enumerate(articles, start=1):
        title = article.get("title", "")
        source = article.get("source", "")
        published_at = article.get("published_at")
        summary = _clip_text(article.get("summary", ""), MAX_SUMMARY_CHARS)
        content = _clip_text(article.get("content", ""), MAX_CONTENT_CHARS)

        published_str = ""
        if published_at:
            try:
                published_str = str(published_at)
            except Exception:
                published_str = ""

        block_parts = [
            f"[Article {idx}]",
            f"Title: {title}",
            f"Source: {source}",
        ]

        if published_str:
            block_parts.append(f"Published At: {published_str}")

        if summary:
            block_parts.append(f"Summary: {summary}")

        if content:
            block_parts.append(f"Content: {content}")

        block = "\n".join(block_parts)

        if total_chars + len(block) > MAX_TOTAL_CONTEXT_CHARS:
            remaining = MAX_TOTAL_CONTEXT_CHARS - total_chars
            if remaining > 300:
                context_blocks.append(block[:remaining].rstrip() + "...")
            break

        context_blocks.append(block)
        total_chars += len(block)

    context = "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(context_blocks)

    print(f"[Node] Context size (chars): {len(context)}")

    sources = [
        {
            "id": article.get("id"),
            "title": article.get("title"),
            "source": article.get("source"),
            "url": article.get("url"),
            "published_at": article.get("published_at"),
        }
        for article in articles
    ]

    return {
        **state,
        "context": context,
        "sources": sources,
    }


def generate_answer_node(state: GraphState) -> GraphState:
    print("\n[Node] Generating Answer")

    question = _safe_str(state.get("question"))
    resolved_question = _safe_str(state.get("resolved_question")) or question
    context = _safe_str(state.get("context"))
    sources = state.get("sources", []) or []
    topic_context = state.get("topic_context") or {}

    llm = LLMService()

    if not context:
        fallback = (
            "I could not find enough relevant cybersecurity context to answer this question."
        )
        return {
            **state,
            "answer": fallback,
            "answer_sections": {
                "executive_summary": fallback,
                "key_findings": "",
                "impact": "",
                "recommendations": "",
            },
            "answer_metadata": {
                "resolved_question": resolved_question,
                "topic_context": topic_context,
                "used_context": False,
            },
            "sources": sources,
        }

    prompt = f"""
You are a cybersecurity research assistant producing evidence-based incident answers.

You MUST answer ONLY from the supplied context.
Do NOT invent facts, organizations, attackers, victim counts, timelines, or technical details.
If a requested fact is not explicitly present in the context, say:
"Not explicitly stated in the retrieved sources."

Important behavior rules:
1. Treat the RESOLVED QUESTION as the main meaning of the user request.
2. Distinguish clearly between:
   - facts explicitly stated in the sources
   - cautious synthesis across multiple sources
3. Do not claim certainty where the context is partial or conflicting.
4. Do not add a Sources section.
5. Keep the answer specific to the resolved question, not a generic article summary.
6. Do not repeat the same point in multiple sections unless necessary.

User Question:
{question}

Resolved Question:
{resolved_question}

Topic Context:
{topic_context}

Context:
{context}

Return the answer in EXACTLY this structure:

1. Executive Summary
- 1 short paragraph focused on the resolved question.

2. Key Findings
- 3 to 6 bullet points
- Only include findings supported by the context
- If a requested detail is missing, include one bullet saying:
  "Not explicitly stated in the retrieved sources."

3. Impact
- 1 short paragraph describing operational / data / customer / business impact if supported
- If impact is unclear, say so

4. Recommendations
- 3 to 5 bullet points
- Only include recommendations that logically follow from the incident/context
""".strip()

    answer = llm.generate(prompt)

    if not answer:
        answer = "I could not generate an answer for this question."
    else:
        answer = clean_generated_answer(answer)

    return {
        **state,
        "answer": answer,
        "answer_sections": {},
        "answer_metadata": {
            "resolved_question": resolved_question,
            "topic_context": topic_context,
            "used_context": True,
        },
        "sources": sources,
    }