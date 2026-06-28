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

MAX_FOCUSED_CONTEXT_CHARS = 1800
MAX_FOCUSED_ARTICLES = 3

MIN_PARAGRAPH_LENGTH = 60
MAX_PARAGRAPHS_PER_ARTICLE = 4

MAX_SENTENCES_PER_ARTICLE = 10
MIN_SENTENCE_LENGTH = 40

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

MITRE_ATTACK_MAP = [
    {
        "technique_id": "T1528",
        "technique_name": "Steal Application Access Token",
        "tactic": "Credential Access",
        "keywords": [
            "oauth token",
            "oauth tokens",
            "access token",
            "token theft",
            "stolen token",
        ],
    },
    {
        "technique_id": "T1078",
        "technique_name": "Valid Accounts",
        "tactic": "Defense Evasion",
        "keywords": [
            "valid account",
            "credentials",
            "credential",
            "stolen credentials",
            "compromised account",
            "login",
        ],
    },
    {
        "technique_id": "T1566",
        "technique_name": "Phishing",
        "tactic": "Initial Access",
        "keywords": [
            "phishing",
            "phishing email",
            "social engineering",
        ],
    },
    {
        "technique_id": "T1195",
        "technique_name": "Supply Chain Compromise",
        "tactic": "Initial Access",
        "keywords": [
            "supply chain",
            "third-party",
            "vendor",
            "dependency",
            "integration",
        ],
    },
]

# ============================================================
# Grounded Answer Context
# ============================================================
@dataclass
class Evidence:
    """
    Represents one ranked evidence sentence extracted
    from a retrieved article.
    """
    evidence_id: int
    article_index: int
    title: str
    source: str
    url: str
    sentence: str
    score: int
    matched_terms: List[str]
    matched_entities: List[str]

@dataclass
class Citation:

    evidence_id: int

    source: str

    title: str

    url: str

    sentence: str

@dataclass
class MITRETechnique:
    """
    MITRE ATT&CK technique inferred from grounded evidence.
    """

    technique_id: str

    technique_name: str

    tactic: str

    confidence: float

    evidence_count: int = 0

    matched_keywords: List[str] = field(default_factory=list)

    supporting_evidence_ids: List[int] = field(default_factory=list)

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
 
    mitre_techniques: List[MITRETechnique] = field(
        default_factory=list
    )

# ============================================================
# Helpers
# ============================================================

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

def _match_mitre_for_evidence(
    evidence: Evidence,
) -> List[MITRETechnique]:
    """
    Infer MITRE ATT&CK techniques from one evidence sentence.
    """

    text = evidence.sentence.lower()

    techniques = []

    for mapping in MITRE_ATTACK_MAP:

        matched = [
            keyword
            for keyword in mapping["keywords"]
            if keyword in text
        ]

        if not matched:
            continue

        confidence = min(
            1.0,
            0.60 + (0.10 * len(matched))
        )

        techniques.append(
            MITRETechnique(
                technique_id=mapping["technique_id"],
                technique_name=mapping["technique_name"],
                tactic=mapping["tactic"],
                confidence=confidence,
                evidence_count=1,
                matched_keywords=matched,
                supporting_evidence_ids=[
                    evidence.evidence_id
                ],
            )
        )

    return techniques

def _map_mitre_techniques(
    evidence_list: List[Evidence],
) -> List[MITRETechnique]:
    """
    Build a deduplicated MITRE ATT&CK list from all evidence.
    """

    merged = {}

    for evidence in evidence_list:

        for technique in _match_mitre_for_evidence(
            evidence
        ):

            key = technique.technique_id

            if key not in merged:

                merged[key] = technique

            else:

                existing = merged[key]

                existing.confidence = max(
                    existing.confidence,
                    technique.confidence,
                )

                existing.supporting_evidence_ids.extend(
                    technique.supporting_evidence_ids
                )
                
                existing.evidence_count += 1

                existing.confidence = min(
                    1.0,
                    existing.confidence
                    + (0.05 * existing.evidence_count)
                )

                existing.supporting_evidence_ids = sorted(
                    set(existing.supporting_evidence_ids)
                )

                existing.matched_keywords = sorted(
                    set(
                        existing.matched_keywords
                        + technique.matched_keywords
                    )
                )

    return sorted(
        merged.values(),
        key=lambda t: (
            t.confidence,
            t.evidence_count,
        ),
        reverse=True,
    )

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

    context.mitre_techniques = _map_mitre_techniques(
        evidence_list,
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

    if context.all_evidence:
        print("Top Evidence IDs:",
            [e.evidence_id for e in context.all_evidence[:5]])

    print("MITRE         :", len(context.mitre_techniques))

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
    # Confirmed Facts
    #

    sections.append("\nCONFIRMED FACTS")

    if context.confirmed_facts:

        for idx, evidence in enumerate(
            context.confirmed_facts,
            start=1,
        ):

            sections.append(
                f"""
Fact #{idx}

Relevance Score:
{evidence.score}

Matched Terms:
{", ".join(evidence.matched_terms) or "None"}

Matched Entities:
{", ".join(evidence.matched_entities) or "None"}

Evidence ID:
{evidence.evidence_id}

Source:
{evidence.source}

Title:
{evidence.title}

URL:
{evidence.url}

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
    # Response Actions
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
    # MITRE ATT&CK
    #

    sections.append("\nMITRE ATT&CK")

    if context.mitre_techniques:

        for technique in context.mitre_techniques:

            sections.append(
                f"""
Technique ID:
{technique.technique_id}

Technique:
{technique.technique_name}

Tactic:
{technique.tactic}

Confidence:
{technique.confidence:.2f}

Supporting Evidence Count:
{technique.evidence_count}

Matched Keywords:
{", ".join(technique.matched_keywords) or "None"}

Supporting Evidence:
{", ".join(f"#{e}" for e in technique.supporting_evidence_ids)}
""".strip()
            )

    else:

        sections.append(
            "No MITRE ATT&CK techniques mapped."
        )

    #
    # Known Gaps
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

    citation_registry = _build_citation_registry(
        ranked_evidence,
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
        "citation_registry": citation_registry,
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
                evidence_id=0,  # Assigned later after ranking
                article_index=article_index,
                title=article.get("title", ""),
                source=article.get("source", ""),
                url=article.get("url", ""),
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

    for evidence_id, evidence in enumerate(ranked, start=1):
        evidence.evidence_id = evidence_id

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

    for item in ranked:

        block = f"""
    Evidence #{item.evidence_id}

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

            URL:
            {item.url}

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

def _build_citation_registry(
    evidence_list: List[Evidence],
) -> Dict[int, Citation]:
    """
    Build a lookup table:
        Evidence ID -> Citation
    """

    registry = {}

    for evidence in evidence_list:

        registry[evidence.evidence_id] = Citation(
            evidence_id=evidence.evidence_id,
            source=evidence.source,
            title=evidence.title,
            url=evidence.url,
            sentence=evidence.sentence,
        )

    return registry

def _replace_evidence_references(
    answer: str,
    citation_registry: Dict[int, Citation],
) -> str:
    """
    Replace internal Evidence references with user-friendly citations.

    Example:

        [Evidence #7]
            ↓
        [1]

    Then append a Sources section.
    """

    if not answer:
        return answer

    if not citation_registry:
        return answer

    #
    # Find all Evidence IDs in order of appearance
    #
    pattern = re.compile(
        r"\[Evidence\s*#(\d+)\]",
        flags=re.IGNORECASE,
    )

    evidence_to_citation: Dict[int, int] = {}
    ordered_evidence_ids: List[int] = []

    def replace_match(match: re.Match) -> str:

        evidence_id = int(match.group(1))

        #
        # Ignore invalid IDs
        #
        if evidence_id not in citation_registry:
            return "[Invalid Citation]"

        #
        # First occurrence gets next citation number
        #
        if evidence_id not in evidence_to_citation:

            evidence_to_citation[evidence_id] = (
                len(evidence_to_citation) + 1
            )

            ordered_evidence_ids.append(
                evidence_id
            )

        citation_number = evidence_to_citation[
            evidence_id
        ]

        return f"[{citation_number}]"

    #
    # Replace Evidence references
    #
    formatted_answer = pattern.sub(
        replace_match,
        answer,
    )

    #
    # Nothing referenced
    #
    if not ordered_evidence_ids:
        return formatted_answer

    #
    # Build Sources section
    #
    source_lines = []

    source_lines.append("")
    source_lines.append("-" * 60)
    source_lines.append("")
    source_lines.append("## Sources")
    source_lines.append("")

    for evidence_id in ordered_evidence_ids:

        citation_number = evidence_to_citation[
            evidence_id
        ]

        citation = citation_registry[
            evidence_id
        ]

        source_lines.append(
            f"[{citation_number}]"
        )

        source_lines.append(
            citation.source
        )

        source_lines.append(
            citation.title
        )

        if citation.url:

            source_lines.append(
                citation.url
            )

        source_lines.append("")

    return (
        formatted_answer.rstrip()
        + "\n"
        + "\n".join(source_lines)
    )

def generate_answer_node(state: GraphState) -> GraphState:
    print("\n[Node] Generating Answer")

    question = _safe_str(state.get("question"))
    resolved_question = _safe_str(state.get("resolved_question")) or question

    context = _safe_str(state.get("context"))
    focused_context = _safe_str(state.get("focused_context"))

    sources = state.get("sources", []) or []
    focused_sources = state.get("focused_sources", []) or []
    citation_registry = state.get("citation_registry", {})
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
            "answer": answer,
            "answer_sections": {},
            "answer_metadata": {
                "resolved_question": resolved_question,
                "topic_context": topic_context,
                "question_type": question_type,
                "used_context": True,
                "used_focused_context": bool(focused_context),

                "mitre": [
                    {
                        "technique_id": t.technique_id,
                        "technique_name": t.technique_name,
                        "tactic": t.tactic,
                        "confidence": round(t.confidence, 2),
                        "evidence_count": t.evidence_count,
                        "matched_keywords": t.matched_keywords,
                        "supporting_evidence_ids": t.supporting_evidence_ids,
                    }
                    for t in (
                        grounding_context.mitre_techniques
                        if grounding_context
                        else []
                    )
                ],
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

10. After every factual statement, append the supporting evidence ID.

Use this exact format:

[Evidence #<id>]

Example:

LastPass confirmed it was affected. [Evidence #3]

Only use evidence IDs that appear in the grounded answer context.

Do NOT invent evidence IDs.

Do NOT create a Sources section.

11. Avoid repeating information across sections.

12. Keep answers concise.

====================================================
OUTPUT FORMAT
====================================================

## Executive Summary

Write one concise paragraph answering ONLY the resolved question.

Append an evidence reference after every factual sentence.

Example:

LastPass confirmed it was affected. [Evidence #3]

If the answer is unavailable, explicitly state:

"Not explicitly stated in the retrieved sources."

----------------------------------------------------

## Key Findings

Provide 3-6 bullet points.

Every bullet MUST come directly from the grounded answer context.

Every factual bullet MUST end with one supporting evidence reference.

Example:

• LastPass confirmed it was affected. [Evidence #3]

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

Provide 3–5 evidence-based recommendations.

Every recommendation must end with an evidence reference.

Otherwise write:

General Cybersecurity Best Practices

(Not derived from the retrieved sources)

followed by 3–5 generic recommendations.

----------------------------------------------------

## MITRE ATT&CK

If one or more MITRE ATT&CK techniques appear in the grounded answer context,

include a section like:

• T1528 – Steal Application Access Token

  Tactic:
  Credential Access

  Confidence:
  High

• T1195 – Supply Chain Compromise
  Tactic: Initial Access

Only list techniques present in the grounded answer context.

If no techniques exist,

omit this section completely.

====================================================
MITRE ATT&CK USAGE
====================================================

The grounded answer context may contain inferred MITRE ATT&CK techniques.

Only reference a MITRE ATT&CK technique when:

• It appears in the grounded answer context.

• It is supported by the listed evidence.

Do NOT invent ATT&CK techniques.

Do NOT infer additional ATT&CK mappings.

If no ATT&CK techniques are supplied in the grounded answer context,

do not mention MITRE ATT&CK.

====================================================
FINAL VALIDATION
====================================================

Before producing the final answer, verify:

✓ Every factual statement exists in the grounded answer context.

✓ Every factual statement includes at least one valid evidence reference.

✓ Every evidence reference corresponds to an Evidence ID present in the grounded answer context.

✓ Every MITRE ATT&CK technique mentioned appears in the grounded answer context.

✓ Do not invent ATT&CK techniques.

✓ Do not infer ATT&CK mappings beyond the supplied evidence.

✓ No outside knowledge was used.

✓ No unsupported conclusions were made.

✓ The answer focuses only on the resolved question.

✓ Every MITRE ATT&CK technique must be supported by at least one evidence item.

✓ Never assign confidence beyond the grounded evidence.

✓ Prefer higher-confidence techniques when summarizing.

✓ If uncertain, respond:

"Not explicitly stated in the retrieved sources."
""".strip()

    answer = llm.generate(prompt)

    if not answer:
        answer = "I could not generate an answer for this question."
    else:

        answer = clean_generated_answer(
            answer,
        )

        #
        # Convert:
        # [Evidence #7]
        #      ↓
        # [1]
        #
        # Append Sources section.
        #
        if citation_registry:

            answer = _replace_evidence_references(
                answer=answer,
                citation_registry=citation_registry,
            )

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

            "mitre": [
                {
                    "technique_id": t.technique_id,
                    "technique_name": t.technique_name,
                    "tactic": t.tactic,
                    "confidence": round(t.confidence, 2),
                    "evidence_count": t.evidence_count,
                    "matched_keywords": t.matched_keywords,
                    "supporting_evidence_ids": t.supporting_evidence_ids,
                }
                for t in (
                    grounding_context.mitre_techniques
                    if grounding_context
                    else []
                )
            ],
        },
        "sources": chosen_sources,
    }