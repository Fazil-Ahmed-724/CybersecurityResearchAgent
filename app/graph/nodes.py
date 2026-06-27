from __future__ import annotations

import re
from typing import Any, Dict, List

from app.graph.state import GraphState
from app.services.retriever import Retriever
from app.services.llm_service import LLMService
from app.services.answer_cleanup import clean_generated_answer
from dataclasses import dataclass, field


MAX_SUMMARY_CHARS = 1200
MAX_CONTENT_CHARS = 2500
MAX_TOTAL_CONTEXT_CHARS = 3000

# Phase 26
MAX_FOCUSED_CONTEXT_CHARS = 1800
MAX_FOCUSED_ARTICLES = 3

MIN_PARAGRAPH_LENGTH = 60
MAX_PARAGRAPHS_PER_ARTICLE = 4

MAX_SENTENCES_PER_ARTICLE = 10
MIN_SENTENCE_LENGTH = 40

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

IMPACT_KEYWORDS = {
    "affected",
    "breach",
    "compromise",
    "stolen",
    "exposed",
    "victim",
    "customer",
    "access",
    "leak",
}

RESPONSE_KEYWORDS = {
    "patched",
    "disabled",
    "revoked",
    "rotated",
    "blocked",
    "mitigated",
    "fixed",
    "updated",
    "removed",
    "investigating",
    "responded",
}

# ============================================================
# Grounded Answer Context
# ============================================================
@dataclass
class Evidence:
    article_index: int
    title: str
    source: str
    sentence: str
    score: int
    matched_terms: List[str]
    matched_entities: List[str]

@dataclass
class GroundedAnswerContext:

    question: str = ""

    resolved_question: str = ""

    primary_entity: str = ""

    incident: str = ""
    
    confirmed_facts: List[Evidence] = field(default_factory=list)

    impact: List[Evidence] = field(default_factory=list)

    response_actions: List[Evidence] = field(default_factory=list)

    unknowns: List[str] = field(default_factory=list)

    all_evidence: List[Evidence] = field(default_factory=list)

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

    QUESTION_WORDS = {
        "happened",
        "happen",
        "affected",
        "affect",
        "confirm",
        "confirmed",
        "linked",
        "link",
        "tell",
        "show",
        "describe",
        "details",
        "information",
    }

    for token in raw_tokens:

        if token in STOPWORDS:
            continue

        if token in QUESTION_WORDS:
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

        focus_terms = _extract_focus_terms(question, resolved_question)

        #
        # Entity follow-up questions:
        # Return only the best article.
        #
        if len(focus_terms) >= 3:
            return top_relevant[:1]

        #
        # Broad questions:
        # Return multiple articles.
        #
        return top_relevant[:MAX_FOCUSED_ARTICLES]

    # fallback
    return articles[:MAX_FOCUSED_ARTICLES]


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

def _classify_evidence(
    evidence: Evidence,
) -> str:
    """
    Classify evidence into one primary category.

    Priority:

    1. Response Actions
    2. Confirmed Facts
    3. Impact
    """

    text = evidence.sentence.lower()

    #
    # Response actions
    #
    if any(word in text for word in RESPONSE_KEYWORDS):
        return "response"

    #
    # Confirmed facts
    #
    fact_indicators = {
        "confirmed",
        "reported",
        "announced",
        "stated",
        "said",
        "disclosed",
        "revealed",
        "identified",
        "according to",
        "observed",
        "detected",
        "found",
        "noted",
        "published",
    }

    if any(word in text for word in fact_indicators):
        return "fact"

    #
    # Impact
    #
    if any(word in text for word in IMPACT_KEYWORDS):
        return "impact"

    #
    # Default
    #
    return "fact"

def _build_grounding_context(
    evidence_list: List[Evidence],
    question: str,
    resolved_question: str,
) -> GroundedAnswerContext:

    context = GroundedAnswerContext()

    context.question = question

    context.resolved_question = resolved_question

    context.all_evidence = evidence_list

    focus_terms = _extract_focus_terms(
        question,
        resolved_question,
    )

    if focus_terms:
        entity_priority = [
            "lastpass",
            "huntress",
            "salesforce",
            "klue",
        ]

        for entity in entity_priority:

            if entity in focus_terms:
                context.primary_entity = entity
                break

        if not context.primary_entity:
            context.primary_entity = focus_terms[0]

    incident_tokens = []

    IMPORTANT_INCIDENT_WORDS = {
        "breach",
        "incident",
        "attack",
        "campaign",
        "oauth",
    }

    INCIDENT_ENTITY_WORDS = {
        "klue",
    }

    for token in _tokenize(resolved_question):

        if (
            token in IMPORTANT_INCIDENT_WORDS
            or token in INCIDENT_ENTITY_WORDS
        ):
            incident_tokens.append(token)

    context.incident = " ".join(dict.fromkeys(incident_tokens))

    for evidence in evidence_list:

        category = _classify_evidence(
            evidence,
        )

        if category == "response":

            context.response_actions.append(
                evidence,
            )

        elif category == "impact":

            context.impact.append(
                evidence,
            )

        else:

            context.confirmed_facts.append(
                evidence,
            )

    #
    # Unknowns
    #

    if not context.impact:

        context.unknowns.append(
            "Impact is not explicitly stated in the retrieved sources."
        )

    if not context.response_actions:

        context.unknowns.append(
            "Response actions are not explicitly stated in the retrieved sources."
        )

    return context

def _log_grounding_context(
    context: GroundedAnswerContext,
):

    print()

    print("=" * 80)

    print("GROUNDED CONTEXT")

    print("=" * 80)

    print("Primary Entity :", context.primary_entity)

    print("Incident       :", context.incident)

    print("Facts          :", len(context.confirmed_facts))

    print("Impact         :", len(context.impact))

    print("Responses      :", len(context.response_actions))

    print("Unknowns       :", len(context.unknowns))

    print("=" * 80)

    print()

def _grounding_context_to_text(
    context: GroundedAnswerContext,
) -> str:

    sections = []

    sections.append("=" * 80)
    sections.append("GROUNDED ANSWER CONTEXT")
    sections.append("=" * 80)

    if context.primary_entity:
        sections.append(f"\nPrimary Entity: {context.primary_entity}")

    if context.incident:
        sections.append(f"Incident: {context.incident}")

    #
    # Confirmed facts
    #

    sections.append("\nCONFIRMED FACTS")

    if context.confirmed_facts:

        for idx, evidence in enumerate(context.confirmed_facts, start=1):

            sections.append(
                f"""
Fact #{idx}

Relevance Score:
{evidence.score}

Matched Terms:
{", ".join(evidence.matched_terms) or "None"}

Matched Entities:
{", ".join(evidence.matched_entities) or "None"}

Source:
{evidence.source}

Title:
{evidence.title}

Evidence:
{evidence.sentence}
""".strip()
            )

    else:

        sections.append(
            "Not explicitly stated in the retrieved sources."
        )

    #
    # Impact
    #

    sections.append("\nIMPACT")

    if context.impact:

        for evidence in context.impact:

            sections.append(
                f"- {evidence.sentence}"
            )

    else:

        sections.append(
            "Not explicitly stated in the retrieved sources."
        )

    #
    # Response actions
    #

    sections.append("\nRESPONSE ACTIONS")

    if context.response_actions:

        for evidence in context.response_actions:

            sections.append(
                f"- {evidence.sentence}"
            )

    else:

        sections.append(
            "Not explicitly stated in the retrieved sources."
        )

    #
    # Unknowns
    #

    if context.unknowns:

        sections.append("\nKNOWN GAPS")

        for item in context.unknowns:

            sections.append(
                f"- {item}"
            )

    return "\n".join(sections)



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


    # focused context for entity-specific follow-up questions
    question = _safe_str(state.get("question"))
    resolved_question = _safe_str(state.get("resolved_question")) or question
    
    # full context (for fallback / generic)
    context = _build_context_from_articles(
        articles=articles,
        total_limit=MAX_TOTAL_CONTEXT_CHARS,
        question=question,
        resolved_question=resolved_question,
    )

    focused_articles = _select_focus_articles(
        articles=articles,
        question=question,
        resolved_question=resolved_question,
    )

    focused_context = _build_context_from_articles(
        articles=focused_articles,
        total_limit=MAX_FOCUSED_CONTEXT_CHARS,
        question=question,
        resolved_question=resolved_question,
    )
    #
    # Build grounded context
    #

    ranked_evidence = _rank_evidence(
        articles=focused_articles,
        question=question,
        resolved_question=resolved_question,
    )

    ranked_evidence = _deduplicate_evidence(
        ranked_evidence,
    )

    grounding_context = _build_grounding_context(
        evidence_list=ranked_evidence,
        question=question,
        resolved_question=resolved_question,
    )

    _log_grounding_context(
        grounding_context,
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
        "grounding_context": grounding_context,
    }

def _split_into_sentences(article: Dict[str, Any]) -> List[str]:
    """
    Split article into clean sentences.

    Works even when RSS content is stored as one giant paragraph.
    """

    text = " ".join([
        _safe_str(article.get("summary")),
        _safe_str(article.get("content")),
    ])

    if not text:
        return []

    text = re.sub(r"\s+", " ", text)

    sentences = re.split(
        r'(?<=[.!?])\s+',
        text,
    )

    cleaned = []

    for sentence in sentences:

        sentence = sentence.strip()

        if len(sentence) < MIN_SENTENCE_LENGTH:
            continue

        cleaned.append(sentence)

    return cleaned

def _score_evidence(
    sentence: str,
    question: str,
    resolved_question: str,
    focus_terms: List[str],
) -> tuple[int, List[str], List[str]]:

    text = sentence.lower()

    score = 0

    matched_terms = []
    matched_entities = []

    #
    # Focus entities
    #
    for term in focus_terms:

        if term in text:

            score += 25

            matched_terms.append(term)

            matched_entities.append(term)

    #
    # Question keywords
    #
    keywords = [
        token
        for token in _tokenize(resolved_question)
        if token not in STOPWORDS
    ]

    for token in keywords:

        if token in text:

            score += 5

            if token not in matched_terms:
                matched_terms.append(token)

    important = [
        "confirmed",
        "affected",
        "breach",
        "stolen",
        "access",
        "oauth",
        "token",
        "customer",
        "attack",
        "attacker",
        "victim",
        "integration",
        "salesforce",
        "lastpass",
        "huntress",
    ]

    for word in important:

        if word in text:

            score += 2

            if word not in matched_terms:
                matched_terms.append(word)

    if sentence.endswith(":"):
        score -= 5

    return (
        score,
        matched_terms,
        matched_entities,
    )

def _extract_candidate_evidence(
    article: Dict[str, Any],
    article_index: int,
    question: str,
    resolved_question: str,
) -> List[Evidence]:

    sentences = _split_into_sentences(article)

    if not sentences:
        return []

    focus_terms = _extract_focus_terms(
        question,
        resolved_question,
    )

    evidence = []

    for sentence in sentences:

        score, matched_terms, matched_entities = _score_evidence(
            sentence=sentence,
            question=question,
            resolved_question=resolved_question,
            focus_terms=focus_terms,
        )

        if score <= 0:
            continue

        evidence.append(
            Evidence(
                article_index=article_index,
                title=article.get("title", ""),
                source=article.get("source", ""),
                sentence=sentence,
                score=score,
                matched_terms=matched_terms,
                matched_entities=matched_entities,
            )
        )

    return evidence

def _rank_evidence(
    articles: List[Dict[str, Any]],
    question: str,
    resolved_question: str,
) -> List[Evidence]:

    ranked = []

    for idx, article in enumerate(articles, start=1):

        ranked.extend(
            _extract_candidate_evidence(
                article=article,
                article_index=idx,
                question=question,
                resolved_question=resolved_question,
            )
        )

    ranked.sort(
        key=lambda item: item.score,
        reverse=True,
    )

    return ranked

def _deduplicate_evidence(
    evidence: List[Evidence],
) -> List[Evidence]:

    seen = set()
    unique = []

    for item in evidence:

        key = re.sub(
            r"\s+",
            " ",
            item.sentence.lower(),
        ).strip()

        if key in seen:
            continue

        seen.add(key)
        unique.append(item)

    return unique

def _build_evidence_pack(
    articles: List[Dict[str, Any]],
    question: str,
    resolved_question: str,
    total_limit: int,
) -> str:

    ranked = _rank_evidence(
        articles=articles,
        question=question,
        resolved_question=resolved_question,
    )

    ranked = _deduplicate_evidence(ranked)

    if not ranked:
        return ""

    blocks = []
    total_chars = 0

    for idx, item in enumerate(ranked, start=1):

        block = f"""
            Evidence #{idx}

            Relevance Score:
            {item.score}

            Matched Terms:
            {", ".join(item.matched_terms) or "None"}

            Matched Entities:
            {", ".join(item.matched_entities) or "None"}

            Source:
            {item.source}

            Title:
            {item.title}

            Evidence:
            {item.sentence}
        """.strip()

        if total_chars + len(block) > total_limit:
            break

        blocks.append(block)
        total_chars += len(block)

    return "\n\n------------------------------\n\n".join(blocks)

def _build_context_from_articles(
    articles: List[Dict[str, Any]],
    total_limit: int,
    question: str = "",
    resolved_question: str = "",
) -> str:

    return _build_evidence_pack(
        articles=articles,
        question=question,
        resolved_question=resolved_question,
        total_limit=total_limit,
    )

def generate_answer_node(state: GraphState) -> GraphState:
    print("\n[Node] Generating Answer")

    question = _safe_str(state.get("question"))
    resolved_question = _safe_str(state.get("resolved_question")) or question

    context = _safe_str(state.get("context"))
    focused_context = _safe_str(state.get("focused_context"))

    sources = state.get("sources", []) or []
    focused_sources = state.get("focused_sources", []) or []

    grounding_context = state.get("grounding_context")

    topic_context = state.get("topic_context") or {}
    question_type = _build_question_type_hint(question, resolved_question)

    llm = LLMService()

    # Prefer focused context if available
    chosen_context = focused_context or context

    if grounding_context:
        chosen_context = _grounding_context_to_text(
            grounding_context
        )
    else:
        chosen_context = focused_context or context

    if focused_sources:
        chosen_sources = focused_sources
    else:
        chosen_sources = sources

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
You are an Enterprise Cybersecurity Research Assistant.

Your ONLY source of truth is the supplied GROUNDED ANSWER CONTEXT.

====================================================
PRIMARY OBJECTIVE
====================================================

Answer the user's question ONLY using the supplied grounded answer context.

Do NOT use your own cybersecurity knowledge.

Do NOT use prior knowledge.

Do NOT infer.

Do NOT speculate.

If something is not explicitly stated in the grounded answer context, respond exactly with:

"Not explicitly stated in the retrieved sources."

====================================================
QUESTION
====================================================

Original Question:
{question}

Resolved Question:
{resolved_question}

Question Type:
{question_type}

Topic Context:
{topic_context}


====================================================
GROUNDED ANSWER CONTEXT
====================================================

The following information has already been filtered,
ranked, and grounded from the retrieved cybersecurity
sources.

Use ONLY this grounded context when generating
your answer.

Do not introduce information that does not appear
below.

{chosen_context}

====================================================
STRICT RULES
====================================================

1. Every factual statement MUST be supported by the grounded answer context.

2. Never invent:

- attackers
- malware
- CVEs
- companies
- timelines
- victim counts
- customer impact
- remediation
- root cause
- technical details

3. If the grounded answer context does not contain the requested information,
DO NOT guess.

Instead write:

"Not explicitly stated in the retrieved sources."

4. If the resolved question asks about ONE company
(for example LastPass, Huntress or Salesforce),

answer ONLY about that company.

Do NOT summarize the whole incident.

Do NOT discuss unrelated companies unless the evidence directly compares them.

5. Do not combine information from multiple articles into a new conclusion unless that conclusion is explicitly supported.

6. Never assume a company was affected simply because it appears in an article.

7. Never use words such as:

- likely
- probably
- may have
- appears to
- seems
- assumed
- inferred

unless those words are actually written in the grounded answer context.

8. If impact is unknown,
say so.

9. Recommendations must be based only on the grounded answer context.

If the grounded answer context contains no recommendations,

provide only GENERAL CYBERSECURITY BEST PRACTICES and clearly label them as such.

10. Do NOT create a Sources section.

11. Avoid repeating information across sections.

12. Keep answers concise.

====================================================
OUTPUT FORMAT
====================================================

## Executive Summary

Write one concise paragraph answering ONLY the resolved question.

If the answer is unavailable, explicitly state:

"Not explicitly stated in the retrieved sources."

----------------------------------------------------

## Key Findings

Provide 3-6 bullet points.

Every bullet MUST come directly from the grounded answer context.

If the requested information is absent, include:

• Not explicitly stated in the retrieved sources.

----------------------------------------------------

## Impact

Discuss ONLY the impact related to the resolved question.

If the grounded answer context does not describe the impact, write:

Not explicitly stated in the retrieved sources.

----------------------------------------------------

## Recommendations

If the grounded answer context contains recommendations:

Provide 3-5 evidence-based recommendations.

Otherwise write:

General Cybersecurity Best Practices
(Not derived from the retrieved sources)

followed by 3-5 generic security recommendations.

Do NOT invent incident-specific remediation.

====================================================
FINAL VALIDATION
====================================================

Before producing the final answer, verify:

✓ Every factual statement exists in the grounded answer context.

✓ No outside knowledge was used.

✓ No unsupported conclusions were made.

✓ The answer focuses only on the resolved question.

✓ If uncertain, respond:

"Not explicitly stated in the retrieved sources."
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