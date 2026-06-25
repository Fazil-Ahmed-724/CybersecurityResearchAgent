from __future__ import annotations

import re
from typing import Any, Dict, List

from app.graph.state import GraphState
from app.services.retriever import Retriever
from app.services.llm_service import LLMService
from app.services.answer_cleanup import clean_generated_answer


MAX_SUMMARY_CHARS = 1200
MAX_CONTENT_CHARS = 2500
MAX_TOTAL_CONTEXT_CHARS = 7000

# Phase 26
MAX_FOCUSED_CONTEXT_CHARS = 4200
MAX_FOCUSED_ARTICLES = 3


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


# ============================================================
# Phase 26 helpers
# ============================================================

STOPWORDS = {
    "what", "about", "was", "were", "is", "are", "did", "does", "do", "the",
    "a", "an", "to", "too", "in", "on", "for", "of", "with", "from", "it",
    "this", "that", "these", "those", "and", "or", "at", "by", "be", "been",
    "being", "have", "has", "had", "their", "its", "his", "her", "they",
    "them", "he", "she", "we", "you", "i", "our", "my", "me", "your"
}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-zA-Z0-9][a-zA-Z0-9\-\._&]+", (text or "").lower())


def _extract_focus_terms(question: str, resolved_question: str) -> List[str]:
    """
    Pull likely entity / target terms from follow-up question.
    Example:
      'What about Huntress?' -> ['huntress']
      'Was LastPass affected too?' -> ['lastpass']
      'Did Salesforce disable the integration?' -> ['salesforce', 'integration']
    """
    raw_tokens = _tokenize(f"{question} {resolved_question}")
    focus_terms: List[str] = []

    for token in raw_tokens:
        if token in STOPWORDS:
            continue
        if len(token) <= 2:
            continue
        if token not in focus_terms:
            focus_terms.append(token)

    return focus_terms


def _article_text_blob(article: Dict[str, Any]) -> str:
    parts = [
        article.get("title", ""),
        article.get("summary", ""),
        article.get("content", ""),
        article.get("source", ""),
    ]
    return " ".join([_safe_str(x).lower() for x in parts if x])


def _score_article_for_question(
    article: Dict[str, Any],
    question: str,
    resolved_question: str,
    focus_terms: List[str],
) -> int:
    """
    Higher score if article explicitly mentions the entity/target from the question.
    """
    text = _article_text_blob(article)
    score = 0

    # direct focus term hits
    for term in focus_terms:
        if term in text:
            score += 8

    # question token overlap
    q_terms = [t for t in _tokenize(resolved_question) if t not in STOPWORDS and len(t) > 2]
    for term in q_terms:
        if term in text:
            score += 2

    # title hits get bonus
    title = _safe_str(article.get("title")).lower()
    for term in focus_terms:
        if term in title:
            score += 4

    return score


def _select_focus_articles(
    articles: List[Dict[str, Any]],
    question: str,
    resolved_question: str,
) -> List[Dict[str, Any]]:
    """
    Narrow context for entity-specific follow-up questions.
    """
    if not articles:
        return []

    focus_terms = _extract_focus_terms(question, resolved_question)

    # if no meaningful terms found, keep original top articles
    if not focus_terms:
        return articles[:MAX_FOCUSED_ARTICLES]

    scored: List[tuple[int, Dict[str, Any]]] = []
    for article in articles:
        score = _score_article_for_question(article, question, resolved_question, focus_terms)
        scored.append((score, article))

    scored.sort(key=lambda x: x[0], reverse=True)

    # keep only actually relevant articles if we found good matches
    top_relevant = [article for score, article in scored if score > 0][:MAX_FOCUSED_ARTICLES]

    if top_relevant:
        return top_relevant

    # fallback
    return articles[:MAX_FOCUSED_ARTICLES]


def _build_context_from_articles(
    articles: List[Dict[str, Any]],
    total_limit: int,
) -> str:
    if not articles:
        return ""

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

        if total_chars + len(block) > total_limit:
            remaining = total_limit - total_chars
            if remaining > 300:
                context_blocks.append(block[:remaining].rstrip() + "...")
            break

        context_blocks.append(block)
        total_chars += len(block)

    return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(context_blocks)


def _build_question_type_hint(question: str, resolved_question: str) -> str:
    q = f"{question} {resolved_question}".lower()

    if any(x in q for x in ["what happened", "summarize", "summary", "overview", "breach"]):
        return "incident_summary"

    if any(x in q for x in ["what data", "what was stolen", "stolen"]):
        return "stolen_data"

    if any(x in q for x in ["who", "attacker", "attackers", "linked to", "responsible"]):
        return "attacker_identity"

    if any(x in q for x in ["affected", "victim", "customer", "company", "companies"]):
        return "affected_entities"

    if any(x in q for x in ["disable", "disabled", "revoke", "integration"]):
        return "response_action"

    return "general_followup"


# ============================================================
# Graph nodes
# ============================================================

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
            "focused_context": "",
            "focused_sources": [],
            "sources": [],
        }

    # full context (for fallback / generic)
    context = _build_context_from_articles(
        articles=articles,
        total_limit=MAX_TOTAL_CONTEXT_CHARS,
    )

    # focused context for entity-specific follow-up questions
    question = _safe_str(state.get("question"))
    resolved_question = _safe_str(state.get("resolved_question")) or question

    focused_articles = _select_focus_articles(
        articles=articles,
        question=question,
        resolved_question=resolved_question,
    )

    focused_context = _build_context_from_articles(
        articles=focused_articles,
        total_limit=MAX_FOCUSED_CONTEXT_CHARS,
    )

    print(f"[Node] Context size (chars): {len(context)}")
    print(f"[Node] Focused context size (chars): {len(focused_context)}")
    print(f"[Node] Focused article count: {len(focused_articles)}")

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

    focused_sources = [
        {
            "id": article.get("id"),
            "title": article.get("title"),
            "source": article.get("source"),
            "url": article.get("url"),
            "published_at": article.get("published_at"),
        }
        for article in focused_articles
    ]

    return {
        **state,
        "context": context,
        "focused_context": focused_context,
        "focused_sources": focused_sources,
        "sources": sources,
    }


def generate_answer_node(state: GraphState) -> GraphState:
    print("\n[Node] Generating Answer")

    question = _safe_str(state.get("question"))
    resolved_question = _safe_str(state.get("resolved_question")) or question

    context = _safe_str(state.get("context"))
    focused_context = _safe_str(state.get("focused_context"))

    sources = state.get("sources", []) or []
    focused_sources = state.get("focused_sources", []) or []

    topic_context = state.get("topic_context") or {}
    question_type = _build_question_type_hint(question, resolved_question)

    llm = LLMService()

    # Prefer focused context if available
    chosen_context = focused_context or context
    chosen_sources = focused_sources or sources

    if not chosen_context:
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
                "question_type": question_type,
                "used_context": False,
            },
            "sources": chosen_sources,
        }

    prompt = f"""
You are a cybersecurity research assistant producing evidence-based incident answers.

You MUST answer ONLY from the supplied context.
Do NOT invent facts, organizations, attackers, victim counts, timelines, technical details, customer counts, or root-cause claims.

CRITICAL RULES:
1. Treat the RESOLVED QUESTION as the exact target of the answer.
2. If the question is about a specific company, victim, product, attacker, or action,
   answer ONLY about that target.
3. Do NOT drift into a generic incident summary unless the resolved question itself asks for one.
4. If a requested fact is missing or uncertain, say exactly:
   "Not explicitly stated in the retrieved sources."
5. Do NOT say a company was affected unless the context explicitly supports it.
6. Do NOT infer exact impact on a company from the broader incident unless the context specifically ties that company to the impact.
7. Do NOT add a Sources section.
8. Avoid repeating the same point across sections.

QUESTION TYPE:
{question_type}

User Question:
{question}

Resolved Question:
{resolved_question}

Topic Context:
{topic_context}

Context:
{chosen_context}

Return the answer in EXACTLY this structure:

1. Executive Summary
- 1 short paragraph focused ONLY on the resolved question.

2. Key Findings
- 3 to 6 bullet points
- Every bullet must be supported by the supplied context
- If the requested detail is missing, include a bullet:
  "Not explicitly stated in the retrieved sources."

3. Impact
- 1 short paragraph ONLY about impact relevant to the resolved question target
- If impact on that target is unclear, explicitly say so

4. Recommendations
- 3 to 5 bullet points
- Recommendations must logically follow from the retrieved context
- Do not invent remediation steps unique to a company unless the context supports them
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
            "question_type": question_type,
            "used_context": True,
            "used_focused_context": bool(focused_context),
        },
        "sources": chosen_sources,
    }