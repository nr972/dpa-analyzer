"""Integration tests for analysis API endpoints."""

import io
import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from dpa_app.models.analysis import (
    AnalysisFinding,
    AnalysisStatus,
    DPAAnalysis,
    FindingSeverity,
    FindingType,
    RequirementsMatrix,
)


@pytest.fixture()
def sample_matrix(db) -> RequirementsMatrix:
    """Create a test matrix in the DB."""
    matrix = RequirementsMatrix(
        name="Test GDPR Matrix",
        framework="gdpr_art28",
        content={
            "framework_id": "gdpr_art28",
            "framework_name": "Test GDPR",
            "requirements": [
                {
                    "id": "gdpr_28_3a",
                    "name": "Processing Instructions",
                    "article_reference": "Art. 28(3)(a)",
                    "description": "Test requirement.",
                    "expected_provisions": ["documented instructions"],
                    "severity": "critical",
                    "category": "processing_instructions",
                }
            ],
        },
    )
    db.add(matrix)
    db.commit()
    db.refresh(matrix)
    return matrix


@pytest.fixture()
def completed_analysis(db, sample_matrix) -> DPAAnalysis:
    """Create a completed analysis with findings."""
    analysis = DPAAnalysis(
        file_id="test-uuid-1234",
        original_filename="test.docx",
        file_type="docx",
        file_size_bytes=5000,
        status=AnalysisStatus.COMPLETED,
        overall_score=85.0,
        framework_scores={"gdpr_art28": 85.0},
        model_used="claude-sonnet-4-20250514",
        total_tokens_used=1500,
        completed_at=datetime.now(UTC),
    )
    analysis.matrices = [sample_matrix]
    db.add(analysis)
    db.commit()
    db.refresh(analysis)

    finding = AnalysisFinding(
        analysis_id=analysis.id,
        framework="gdpr_art28",
        requirement_id="gdpr_28_3a",
        requirement_name="Processing Instructions",
        finding_type=FindingType.COMPLIANT,
        severity=FindingSeverity.CRITICAL,
        explanation="Found documented instructions clause.",
        confidence=0.9,
    )
    db.add(finding)
    db.commit()
    return analysis


class TestListAnalyses:
    def test_list_empty(self, client):
        resp = client.get("/api/analyses/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    def test_list_with_data(self, client, completed_analysis):
        resp = client.get("/api/analyses/")
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "completed"

    def test_filter_by_status(self, client, completed_analysis):
        resp = client.get("/api/analyses/", params={"status": "completed"})
        assert resp.json()["total"] == 1
        resp = client.get("/api/analyses/", params={"status": "pending"})
        assert resp.json()["total"] == 0


class TestGetAnalysis:
    def test_get_detail(self, client, completed_analysis):
        resp = client.get(f"/api/analyses/{completed_analysis.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["overall_score"] == 85.0
        assert len(data["findings"]) == 1
        assert data["findings"][0]["finding_type"] == "compliant"
        assert len(data["matrices_used"]) == 1

    def test_not_found(self, client):
        resp = client.get("/api/analyses/999")
        assert resp.status_code == 404


class TestDeleteAnalysis:
    def test_delete(self, client, completed_analysis):
        resp = client.delete(f"/api/analyses/{completed_analysis.id}")
        assert resp.status_code == 204
        resp = client.get(f"/api/analyses/{completed_analysis.id}")
        assert resp.status_code == 404

    def test_delete_not_found(self, client):
        resp = client.delete("/api/analyses/999")
        assert resp.status_code == 404


class TestGetFindings:
    def test_get_all_findings(self, client, completed_analysis):
        resp = client.get(f"/api/analyses/{completed_analysis.id}/findings")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["summary"]["total_findings"] == 1

    def test_filter_by_framework(self, client, completed_analysis):
        resp = client.get(
            f"/api/analyses/{completed_analysis.id}/findings",
            params={"framework": "gdpr_art28"},
        )
        assert resp.json()["total"] == 1
        resp = client.get(
            f"/api/analyses/{completed_analysis.id}/findings",
            params={"framework": "ccpa_cpra"},
        )
        assert resp.json()["total"] == 0


class TestDownloadReport:
    def test_json_report(self, client, completed_analysis, tmp_path, monkeypatch):
        from dpa_app import config
        monkeypatch.setattr(config.settings, "reports_dir", tmp_path)

        resp = client.get(
            f"/api/analyses/{completed_analysis.id}/report",
            params={"format": "json"},
        )
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]

    def test_html_report(self, client, completed_analysis, tmp_path, monkeypatch):
        from dpa_app import config
        monkeypatch.setattr(config.settings, "reports_dir", tmp_path)

        resp = client.get(
            f"/api/analyses/{completed_analysis.id}/report",
            params={"format": "html"},
        )
        assert resp.status_code == 200

    def test_not_completed(self, client, db, sample_matrix):
        analysis = DPAAnalysis(
            file_id="pending-uuid",
            original_filename="test.docx",
            file_type="docx",
            file_size_bytes=1000,
            status=AnalysisStatus.PENDING,
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        resp = client.get(
            f"/api/analyses/{analysis.id}/report",
            params={"format": "json"},
        )
        assert resp.status_code == 400

    def test_invalid_format(self, client, completed_analysis):
        resp = client.get(
            f"/api/analyses/{completed_analysis.id}/report",
            params={"format": "csv"},
        )
        assert resp.status_code == 422


class TestCreateAnalysis:
    def test_missing_api_key(self, client, sample_matrix):
        file = io.BytesIO(b"test content")
        resp = client.post(
            "/api/analyses/",
            files={"file": ("test.docx", file, "application/octet-stream")},
            params={"matrix_ids": str(sample_matrix.id)},
        )
        assert resp.status_code == 400
        assert "API key" in resp.json()["detail"]

    def test_missing_matrix_ids(self, client):
        file = io.BytesIO(b"test content")
        resp = client.post(
            "/api/analyses/",
            files={"file": ("test.docx", file, "application/octet-stream")},
            headers={"x-api-key": "test-key"},
        )
        assert resp.status_code == 400
        assert "matrix_id" in resp.json()["detail"]
