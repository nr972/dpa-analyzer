"""Compliance scoring logic for DPA analysis findings."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.analyzer import FindingData


@dataclass
class ComplianceScore:
    """Computed compliance scores from analysis findings."""

    overall_score: float  # 0–100
    framework_scores: dict[str, float]  # framework_id -> score
    category_scores: dict[str, dict[str, float]]  # framework_id -> {category -> score}


# Severity weights — higher weight means more impact on the score
_SEVERITY_WEIGHTS: dict[str, float] = {
    "critical": 4.0,
    "high": 3.0,
    "medium": 2.0,
    "low": 1.0,
    "info": 0.0,
}

# Finding type compliance percentages
_COMPLIANCE_MAP: dict[str, float] = {
    "compliant": 1.0,
    "partial_compliance": 0.5,
    "deviation": 0.25,
    "missing_provision": 0.0,
    "subprocessor_issue": 0.0,
    "transfer_mechanism_issue": 0.0,
}


def calculate_scores(findings: list[FindingData]) -> ComplianceScore:
    """Calculate compliance scores from analysis findings.

    Scoring algorithm:
    - Each finding is weighted by its severity.
    - Finding types map to compliance percentages (0.0 to 1.0).
    - Per-framework score = weighted average of compliance percentages.
    - Overall score = average of framework scores (equally weighted).
    """
    if not findings:
        return ComplianceScore(
            overall_score=0.0, framework_scores={}, category_scores={}
        )

    # Group findings by framework
    by_framework: dict[str, list[FindingData]] = {}
    for f in findings:
        by_framework.setdefault(f.framework, []).append(f)

    framework_scores: dict[str, float] = {}
    category_scores: dict[str, dict[str, float]] = {}

    for fw, fw_findings in by_framework.items():
        framework_scores[fw] = _weighted_score(fw_findings)

        # Per-category scores within the framework
        by_category: dict[str, list[FindingData]] = {}
        for f in fw_findings:
            # Derive category from requirement_id pattern or use framework as fallback
            cat = _derive_category(f)
            by_category.setdefault(cat, []).append(f)

        category_scores[fw] = {
            cat: _weighted_score(cat_findings)
            for cat, cat_findings in by_category.items()
        }

    # Overall = average of framework scores
    if framework_scores:
        overall = sum(framework_scores.values()) / len(framework_scores)
    else:
        overall = 0.0

    return ComplianceScore(
        overall_score=round(overall, 1),
        framework_scores={k: round(v, 1) for k, v in framework_scores.items()},
        category_scores={
            fw: {cat: round(s, 1) for cat, s in cats.items()}
            for fw, cats in category_scores.items()
        },
    )


def _weighted_score(findings: list[FindingData]) -> float:
    """Compute weighted compliance score for a list of findings."""
    total_weight = 0.0
    weighted_sum = 0.0

    for f in findings:
        weight = _SEVERITY_WEIGHTS.get(f.severity, 1.0)
        compliance = _COMPLIANCE_MAP.get(f.finding_type, 0.0)
        total_weight += weight
        weighted_sum += weight * compliance

    if total_weight == 0:
        return 0.0

    return (weighted_sum / total_weight) * 100.0


def _derive_category(finding: FindingData) -> str:
    """Derive a category label from the finding's requirement ID."""
    # Use the last meaningful segment of requirement_id
    # e.g., "gdpr_28_3a" -> "28_3a", "ccpa_sp_contract" -> "sp_contract"
    parts = finding.requirement_id.split("_", 1)
    return parts[1] if len(parts) > 1 else finding.requirement_id
