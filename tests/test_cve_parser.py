from app.vulnerability.parser import CVEParser, QuestionType


def test_single_cve():
    result = CVEParser.parse("Explain CVE-2026-46817")
    assert result.question_type == QuestionType.CVE_LOOKUP
    assert result.cve_ids == ["CVE-2026-46817"]


def test_multiple_cves():
    result = CVEParser.parse(
        "Compare CVE-2026-46817 and CVE-2025-12345"
    )
    assert len(result.cve_ids) == 2


def test_case_insensitive():
    result = CVEParser.parse("tell me about cve-2024-3400")
    assert result.cve_ids == ["CVE-2024-3400"]


def test_no_cve():
    result = CVEParser.parse("What happened to LastPass?")
    assert result.question_type == QuestionType.GENERAL
    assert result.cve_ids == []