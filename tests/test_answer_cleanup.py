from app.services.answer_cleanup import clean_generated_answer


def test_clean_generated_answer_removes_duplicate_sections_and_sources():
    answer = """
**1. Executive Summary:**

Klue suffered an OAuth-related breach.

**2. Key Findings:**

- Attackers abused OAuth tokens.
- Attackers abused OAuth tokens.

**2. Key Findings:**

- This duplicate section should be removed.

**Sources:**

- Example Source
"""

    cleaned = clean_generated_answer(answer)

    assert cleaned.count("**2. Key Findings:**") == 1
    assert cleaned.count("Attackers abused OAuth tokens.") == 1
    assert "Sources" not in cleaned
    assert "duplicate section" not in cleaned
