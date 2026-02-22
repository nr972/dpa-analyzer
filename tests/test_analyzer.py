"""Tests for the LLM analysis engine with mocked Claude responses."""

import json
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.matrix import MatrixContent, RequirementItem
from app.services.analyzer import (
    FindingData,
    _batch_requirements,
    _build_user_prompt,
    _parse_llm_response,
    _prepare_document_text,
    analyze_dpa,
)
from app.services.parser import Clause


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def sample_clauses() -> list[Clause]:
    return [
        Clause(index=0, heading="1. Definitions", text="1. Definitions\nPersonal Data means any info."),
        Clause(index=1, heading="2. Processing", text="2. Processing\nProcessor acts on instructions."),
        Clause(index=2, heading="3. Sub-Processors", text="3. Sub-Processors\nNo sub-processor without consent."),
    ]


@pytest.fixture()
def sample_matrix() -> MatrixContent:
    return MatrixContent(
        framework_id="gdpr_art28",
        framework_name="GDPR Article 28",
        requirements=[
            RequirementItem(
                id="gdpr_28_3a",
                name="Processing Instructions",
                article_reference="Art. 28(3)(a)",
                description="Processor processes data on documented instructions.",
                expected_provisions=["documented instructions"],
                severity="critical",
                category="processing_instructions",
            ),
            RequirementItem(
                id="gdpr_28_2",
                name="Sub-Processor Authorization",
                article_reference="Art. 28(2)",
                description="Prior consent for sub-processors.",
                expected_provisions=["prior written consent"],
                severity="critical",
                category="sub_processors",
            ),
        ],
    )


def _mock_claude_response(findings_json: list[dict]) -> MagicMock:
    """Create a mock Anthropic messages.create response."""
    response = MagicMock()
    content_block = MagicMock()
    content_block.text = json.dumps(findings_json)
    response.content = [content_block]
    response.usage = MagicMock()
    response.usage.input_tokens = 1000
    response.usage.output_tokens = 500
    return response


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBatchRequirements:
    def test_batch_small(self, sample_matrix):
        batches = _batch_requirements(sample_matrix.requirements, batch_size=10)
        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_batch_splits(self, sample_matrix):
        batches = _batch_requirements(sample_matrix.requirements, batch_size=1)
        assert len(batches) == 2


class TestPrepareDocumentText:
    def test_multiple_clauses(self, sample_clauses):
        text = _prepare_document_text(sample_clauses, "full text fallback")
        assert "[Section 1] 1. Definitions" in text
        assert "[Section 2] 2. Processing" in text
        assert "---" in text

    def test_single_clause_uses_full_text(self):
        clauses = [Clause(index=0, heading=None, text="all text")]
        text = _prepare_document_text(clauses, "the full text")
        assert text == "the full text"


class TestBuildUserPrompt:
    def test_contains_document_and_requirements(self, sample_matrix):
        prompt = _build_user_prompt("DPA text here", sample_matrix.requirements)
        assert "DPA text here" in prompt
        assert "gdpr_28_3a" in prompt
        assert "Processing Instructions" in prompt


class TestParseLLMResponse:
    def test_valid_response(self, sample_matrix):
        response = json.dumps([
            {
                "requirement_id": "gdpr_28_3a",
                "finding_type": "compliant",
                "severity": "critical",
                "matched_clause_text": "Processor acts on instructions.",
                "explanation": "The DPA requires documented instructions.",
                "remediation": None,
                "confidence": 0.95,
            },
            {
                "requirement_id": "gdpr_28_2",
                "finding_type": "partial_compliance",
                "severity": "critical",
                "matched_clause_text": "No sub-processor without consent.",
                "explanation": "Consent required but no notification mechanism.",
                "remediation": "Add sub-processor notification clause.",
                "confidence": 0.8,
            },
        ])

        findings = _parse_llm_response(response, sample_matrix.requirements, "gdpr_art28")
        assert len(findings) == 2
        assert findings[0].finding_type == "compliant"
        assert findings[1].finding_type == "partial_compliance"
        assert findings[1].remediation == "Add sub-processor notification clause."

    def test_markdown_fenced_response(self, sample_matrix):
        response = "```json\n" + json.dumps([
            {
                "requirement_id": "gdpr_28_3a",
                "finding_type": "compliant",
                "severity": "critical",
                "matched_clause_text": None,
                "explanation": "Found it.",
                "remediation": None,
                "confidence": 0.9,
            },
            {
                "requirement_id": "gdpr_28_2",
                "finding_type": "compliant",
                "severity": "critical",
                "matched_clause_text": None,
                "explanation": "Found it.",
                "remediation": None,
                "confidence": 0.9,
            },
        ]) + "\n```"

        findings = _parse_llm_response(response, sample_matrix.requirements, "gdpr_art28")
        assert len(findings) == 2

    def test_invalid_json_returns_fallback(self, sample_matrix):
        findings = _parse_llm_response("not json at all", sample_matrix.requirements, "gdpr_art28")
        assert len(findings) == 2
        assert all(f.finding_type == "missing_provision" for f in findings)
        assert all(f.confidence == 0.0 for f in findings)

    def test_missing_requirement_gets_default(self, sample_matrix):
        # Only return one of two requirements
        response = json.dumps([
            {
                "requirement_id": "gdpr_28_3a",
                "finding_type": "compliant",
                "severity": "critical",
                "explanation": "OK",
                "confidence": 0.9,
            },
        ])
        findings = _parse_llm_response(response, sample_matrix.requirements, "gdpr_art28")
        assert len(findings) == 2
        missing = [f for f in findings if f.requirement_id == "gdpr_28_2"]
        assert len(missing) == 1
        assert missing[0].finding_type == "missing_provision"
        assert missing[0].confidence == 0.0

    def test_invalid_finding_type_corrected(self, sample_matrix):
        response = json.dumps([
            {
                "requirement_id": "gdpr_28_3a",
                "finding_type": "invalid_type",
                "severity": "critical",
                "explanation": "Test",
                "confidence": 0.5,
            },
            {
                "requirement_id": "gdpr_28_2",
                "finding_type": "compliant",
                "severity": "critical",
                "explanation": "OK",
                "confidence": 0.9,
            },
        ])
        findings = _parse_llm_response(response, sample_matrix.requirements, "gdpr_art28")
        corrected = [f for f in findings if f.requirement_id == "gdpr_28_3a"]
        assert corrected[0].finding_type == "missing_provision"


class TestAnalyzeDPA:
    @patch("app.services.analyzer.Anthropic")
    def test_full_analysis_flow(
        self, mock_anthropic_cls, sample_clauses, sample_matrix
    ):
        mock_response = _mock_claude_response([
            {
                "requirement_id": "gdpr_28_3a",
                "finding_type": "compliant",
                "severity": "critical",
                "matched_clause_text": "on instructions",
                "explanation": "Documented instructions found.",
                "remediation": None,
                "confidence": 0.95,
            },
            {
                "requirement_id": "gdpr_28_2",
                "finding_type": "deviation",
                "severity": "critical",
                "matched_clause_text": "without consent",
                "explanation": "Consent mentioned but no notification.",
                "remediation": "Add notification mechanism.",
                "confidence": 0.7,
            },
        ])

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        result = analyze_dpa(
            clauses=sample_clauses,
            full_text="full text",
            matrix=sample_matrix,
            api_key="test-key",
            model="claude-sonnet-4-20250514",
        )

        assert len(result.findings) == 2
        assert result.model_used == "claude-sonnet-4-20250514"
        assert result.total_tokens == 1500

        mock_anthropic_cls.assert_called_once_with(api_key="test-key")
        mock_client.messages.create.assert_called_once()
