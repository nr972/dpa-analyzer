"""Tests for report generation."""

from datetime import UTC, datetime

import pytest

from app.models.analysis import (
    AnalysisFinding,
    AnalysisStatus,
    DPAAnalysis,
    FindingSeverity,
    FindingType,
    RequirementsMatrix,
)
from app.services.reporter import generate_report


@pytest.fixture()
def sample_analysis(db) -> DPAAnalysis:
    analysis = DPAAnalysis(
        file_id="test-uuid-1234",
        original_filename="sample_dpa.docx",
        file_type="docx",
        file_size_bytes=50000,
        status=AnalysisStatus.COMPLETED,
        overall_score=72.5,
        framework_scores={"gdpr_art28": 72.5},
        model_used="claude-sonnet-4-20250514",
        total_tokens_used=3000,
        completed_at=datetime.now(UTC),
    )
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@pytest.fixture()
def sample_findings(db, sample_analysis) -> list[AnalysisFinding]:
    findings = [
        AnalysisFinding(
            analysis_id=sample_analysis.id,
            framework="gdpr_art28",
            requirement_id="gdpr_28_3a",
            requirement_name="Processing Instructions",
            finding_type=FindingType.COMPLIANT,
            severity=FindingSeverity.CRITICAL,
            matched_clause_text="Processor acts on documented instructions.",
            explanation="DPA requires documented instructions from controller.",
            remediation=None,
            confidence=0.95,
        ),
        AnalysisFinding(
            analysis_id=sample_analysis.id,
            framework="gdpr_art28",
            requirement_id="gdpr_28_2",
            requirement_name="Sub-Processor Authorization",
            finding_type=FindingType.PARTIAL_COMPLIANCE,
            severity=FindingSeverity.CRITICAL,
            matched_clause_text="No sub-processor without consent.",
            explanation="Consent required but no notification mechanism.",
            remediation="Add sub-processor change notification clause with objection right.",
            confidence=0.8,
        ),
    ]
    db.add_all(findings)
    db.commit()
    for f in findings:
        db.refresh(f)
    return findings


@pytest.fixture()
def sample_matrix(db) -> RequirementsMatrix:
    matrix = RequirementsMatrix(
        name="Test GDPR Matrix",
        framework="gdpr_art28",
        content={"framework_id": "gdpr_art28", "requirements": []},
    )
    db.add(matrix)
    db.commit()
    db.refresh(matrix)
    return matrix


class TestReportGeneration:
    def test_json_report(self, db, tmp_path, monkeypatch, sample_analysis, sample_findings, sample_matrix):
        from app import config
        monkeypatch.setattr(config.settings, "reports_dir", tmp_path)

        path = generate_report(sample_analysis, sample_findings, [sample_matrix], "json")
        assert path.exists()
        assert path.suffix == ".json"

        import json
        data = json.loads(path.read_text())
        assert data["overall_score"] == 72.5
        assert len(data["findings"]) == 2
        assert len(data["remediation_checklist"]) == 1

    def test_html_report(self, db, tmp_path, monkeypatch, sample_analysis, sample_findings, sample_matrix):
        from app import config
        monkeypatch.setattr(config.settings, "reports_dir", tmp_path)

        path = generate_report(sample_analysis, sample_findings, [sample_matrix], "html")
        assert path.exists()
        assert path.suffix == ".html"

        content = path.read_text()
        assert "DPA Gap Analysis Report" in content
        assert "72" in content  # Overall score
        assert "Processing Instructions" in content

    def test_docx_report(self, db, tmp_path, monkeypatch, sample_analysis, sample_findings, sample_matrix):
        from app import config
        monkeypatch.setattr(config.settings, "reports_dir", tmp_path)

        path = generate_report(sample_analysis, sample_findings, [sample_matrix], "docx")
        assert path.exists()
        assert path.suffix == ".docx"
        assert path.stat().st_size > 0

    def test_pdf_report(self, db, tmp_path, monkeypatch, sample_analysis, sample_findings, sample_matrix):
        from app import config
        monkeypatch.setattr(config.settings, "reports_dir", tmp_path)

        path = generate_report(sample_analysis, sample_findings, [sample_matrix], "pdf")
        assert path.exists()
        assert path.suffix == ".pdf"
        assert path.stat().st_size > 0

    def test_unsupported_format(self, db, sample_analysis, sample_findings, sample_matrix):
        with pytest.raises(ValueError, match="Unsupported report format"):
            generate_report(sample_analysis, sample_findings, [sample_matrix], "csv")
