from __future__ import annotations

import re


SECTION_ORDER = {
    "executive summary": 1,
    "key findings": 2,
    "impact": 3,
    "recommendations": 4,
}

SECTION_PATTERN = re.compile(
    r"^\s*(?:#+\s*)?(?:\*\*)?\s*(?:\d+\.\s*)?"
    r"(executive summary|key findings|impact|recommendations)"
    r"\s*:?\s*(?:\*\*)?\s*(.*)$",
    re.IGNORECASE,
)

SOURCES_PATTERN = re.compile(
    r"^\s*(?:#+\s*)?(?:[-*]\s*)?(?:\*\*)?sources(?:\*\*)?\s*:?.*$",
    re.IGNORECASE,
)


def _normalize_content_line(line: str) -> str:
    normalized = (line or "").strip().lower()
    normalized = re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", normalized)
    normalized = re.sub(r"[*_`>#]+", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def clean_generated_answer(answer: str) -> str:
    lines = (answer or "").strip().splitlines()
    cleaned_lines: list[str] = []
    seen_sections: set[str] = set()
    seen_content: set[str] = set()
    skip_duplicate_section = False

    for raw_line in lines:
        line = raw_line.rstrip()

        if SOURCES_PATTERN.match(line):
            break

        section_match = SECTION_PATTERN.match(line)

        if section_match:
            section_name = section_match.group(1).lower()
            section_body = section_match.group(2).strip()

            if section_name in seen_sections:
                skip_duplicate_section = True
                continue

            seen_sections.add(section_name)
            skip_duplicate_section = False

            section_number = SECTION_ORDER[section_name]
            section_title = section_name.title()

            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")

            cleaned_lines.append(f"**{section_number}. {section_title}:**")
            cleaned_lines.append("")

            if section_body:
                normalized_body = _normalize_content_line(section_body)
                if normalized_body and normalized_body not in seen_content:
                    seen_content.add(normalized_body)
                    cleaned_lines.append(section_body)

            continue

        if skip_duplicate_section:
            continue

        normalized_line = _normalize_content_line(line)
        if normalized_line:
            if normalized_line in seen_content:
                continue
            seen_content.add(normalized_line)

        cleaned_lines.append(line)

    compacted_lines: list[str] = []
    previous_blank = False

    for line in cleaned_lines:
        is_blank = not line.strip()
        if is_blank and previous_blank:
            continue
        compacted_lines.append(line)
        previous_blank = is_blank

    return "\n".join(compacted_lines).strip()
