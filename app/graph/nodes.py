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

    llm = LLMService()

    if not context:
        fallback = (
            "I could not find enough relevant cybersecurity context to answer this question."
        )
        return {
            **state,
            "answer": fallback,
            "sources": sources,
        }

    prompt = f"""
You are a cybersecurity research assistant.

Answer the user's question using ONLY the provided context.
If the question is a follow-up, use the resolved question as the primary meaning.
Do not invent facts not present in the context.
If multiple sources mention affected organizations, merge them carefully.
If the context is partial, say so clearly.

User Question:
{question}

Resolved Question:
{resolved_question}

Context:
{context}

Return a clear structured answer with:
1. Executive Summary
2. Key Findings
3. Impact
4. Recommendations

Formatting rules:
- Include each section exactly once.
- Do not include a Sources section.
- Do not repeat the same facts across sections unless needed for clarity.
- Keep the answer concise and specific to the resolved question.
""".strip()

    answer = llm.generate(prompt)

    if not answer:
        answer = "I could not generate an answer for this question."
    else:
        answer = clean_generated_answer(answer)

    return {
        **state,
        "answer": answer,
        "sources": sources,
    }
