"""Tests for compliance scoring logic."""

from dpa_app.services.analyzer import FindingData
from dpa_app.services.scorer import calculate_scores


def _finding(
    req_id: str = "test_1",
    framework: str = "gdpr_art28",
    finding_type: str = "compliant",
    severity: str = "critical",
) -> FindingData:
    return FindingData(
        requirement_id=req_id,
        requirement_name="Test",
        framework=framework,
        finding_type=finding_type,
        severity=severity,
        matched_clause_text=None,
        explanation="Test",
        remediation=None,
        confidence=0.9,
    )


class TestCalculateScores:
    def test_empty_findings(self):
        result = calculate_scores([])
        assert result.overall_score == 0.0
        assert result.framework_scores == {}

    def test_all_compliant(self):
        findings = [
            _finding(req_id="r1", severity="critical"),
            _finding(req_id="r2", severity="high"),
        ]
        result = calculate_scores(findings)
        assert result.overall_score == 100.0
        assert result.framework_scores["gdpr_art28"] == 100.0

    def test_all_missing(self):
        findings = [
            _finding(req_id="r1", finding_type="missing_provision", severity="critical"),
            _finding(req_id="r2", finding_type="missing_provision", severity="high"),
        ]
        result = calculate_scores(findings)
        assert result.overall_score == 0.0

    def test_mixed_findings(self):
        findings = [
            _finding(req_id="r1", finding_type="compliant", severity="critical"),  # weight 4, compliance 1.0
            _finding(req_id="r2", finding_type="missing_provision", severity="low"),  # weight 1, compliance 0.0
        ]
        result = calculate_scores(findings)
        # Expected: (4*1.0 + 1*0.0) / (4+1) * 100 = 80.0
        assert result.overall_score == 80.0

    def test_partial_compliance(self):
        findings = [
            _finding(req_id="r1", finding_type="partial_compliance", severity="critical"),
        ]
        result = calculate_scores(findings)
        assert result.overall_score == 50.0

    def test_deviation(self):
        findings = [
            _finding(req_id="r1", finding_type="deviation", severity="critical"),
        ]
        result = calculate_scores(findings)
        assert result.overall_score == 25.0

    def test_multiple_frameworks(self):
        findings = [
            _finding(req_id="r1", framework="gdpr_art28", finding_type="compliant"),
            _finding(req_id="r2", framework="ccpa_cpra", finding_type="missing_provision"),
        ]
        result = calculate_scores(findings)
        assert result.framework_scores["gdpr_art28"] == 100.0
        assert result.framework_scores["ccpa_cpra"] == 0.0
        # Overall is average of the two
        assert result.overall_score == 50.0

    def test_info_severity_ignored(self):
        findings = [
            _finding(req_id="r1", finding_type="compliant", severity="critical"),
            _finding(req_id="r2", finding_type="missing_provision", severity="info"),  # weight 0
        ]
        result = calculate_scores(findings)
        # info has weight 0, so only the critical finding counts
        assert result.overall_score == 100.0

    def test_category_scores(self):
        findings = [
            _finding(req_id="gdpr_28_3a", finding_type="compliant"),
            _finding(req_id="gdpr_28_3b", finding_type="missing_provision"),
        ]
        result = calculate_scores(findings)
        assert "gdpr_art28" in result.category_scores
        cats = result.category_scores["gdpr_art28"]
        # Two different categories derived from requirement_id
        assert len(cats) >= 1
