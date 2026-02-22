"""LLM-based DPA clause analysis using the Anthropic API."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

from anthropic import Anthropic, APIError, AuthenticationError, RateLimitError

from app.schemas.matrix import MatrixContent, RequirementItem
from app.services.parser import Clause

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a privacy law expert analyzing a Data Processing Agreement (DPA) \
against specific regulatory requirements. For each requirement provided, you must:

1. Search the DPA text for clauses that address the requirement.
2. Evaluate whether the DPA satisfies, partially satisfies, or fails to satisfy \
the requirement.
3. Classify the finding using EXACTLY one of these types:
   - "compliant": The DPA fully addresses the requirement.
   - "partial_compliance": The DPA partially addresses the requirement but has gaps.
   - "deviation": The DPA addresses the topic but deviates from the expected position.
   - "missing_provision": The DPA does not address the requirement at all.
   - "subprocessor_issue": The DPA has a specific issue with sub-processor provisions.
   - "transfer_mechanism_issue": The DPA has a specific issue with data transfer mechanisms.
4. Provide a specific, actionable remediation recommendation if the finding is \
not "compliant".
5. Quote the exact text from the DPA that you matched (or null if not found).

You MUST respond with ONLY a valid JSON array. No markdown fencing, no \
explanation outside the JSON. Each element must match this schema:

{
  "requirement_id": "<id from the requirement>",
  "finding_type": "<one of the six types above>",
  "severity": "<critical|high|medium|low|info>",
  "matched_clause_text": "<exact quote from DPA or null>",
  "explanation": "<detailed analysis>",
  "remediation": "<specific recommendation or null if compliant>",
  "confidence": <float 0.0 to 1.0>
}
"""


@dataclass
class FindingData:
    """A single analysis finding returned by the LLM."""

    requirement_id: str
    requirement_name: str
    framework: str
    finding_type: str
    severity: str
    matched_clause_text: str | None
    explanation: str
    remediation: str | None
    confidence: float


@dataclass
class AnalysisResult:
    """Aggregate result of analyzing a DPA against a requirements matrix."""

    findings: list[FindingData]
    model_used: str
    total_tokens: int


def analyze_dpa(
    clauses: list[Clause],
    full_text: str,
    matrix: MatrixContent,
    api_key: str,
    model: str = "claude-sonnet-4-20250514",
) -> AnalysisResult:
    """Analyze a DPA against a requirements matrix using Claude.

    Sends the document text along with batches of requirements,
    collects structured findings for each requirement.
    """
    client = Anthropic(api_key=api_key)

    all_findings: list[FindingData] = []
    total_tokens = 0

    # Batch requirements (5-10 per call to balance thoroughness vs cost)
    batches = _batch_requirements(matrix.requirements, batch_size=8)

    # Prepare document text (use full text for most DPAs)
    doc_text = _prepare_document_text(clauses, full_text)

    for batch in batches:
        user_prompt = _build_user_prompt(doc_text, batch)

        response_text, tokens = _call_claude(
            client=client,
            system=SYSTEM_PROMPT,
            user_message=user_prompt,
            model=model,
        )
        total_tokens += tokens

        findings = _parse_llm_response(
            response_text, batch, matrix.framework_id
        )
        all_findings.extend(findings)

    return AnalysisResult(
        findings=all_findings,
        model_used=model,
        total_tokens=total_tokens,
    )


def _batch_requirements(
    requirements: list[RequirementItem], batch_size: int = 8
) -> list[list[RequirementItem]]:
    """Split requirements into batches."""
    return [
        requirements[i : i + batch_size]
        for i in range(0, len(requirements), batch_size)
    ]


def _prepare_document_text(clauses: list[Clause], full_text: str) -> str:
    """Prepare document text for the LLM prompt.

    Uses clause-segmented text with section markers for structure,
    falling back to full text if clauses are too few.
    """
    if len(clauses) <= 1:
        return full_text

    parts: list[str] = []
    for clause in clauses:
        header = f"[Section {clause.index + 1}]"
        if clause.heading:
            header += f" {clause.heading}"
        parts.append(f"{header}\n{clause.text}")

    return "\n\n---\n\n".join(parts)


def _build_user_prompt(
    doc_text: str, requirements: list[RequirementItem]
) -> str:
    """Build the user prompt for a batch of requirements."""
    req_json = json.dumps(
        [
            {
                "id": r.id,
                "name": r.name,
                "article_reference": r.article_reference,
                "description": r.description,
                "expected_provisions": r.expected_provisions,
                "severity": r.severity,
            }
            for r in requirements
        ],
        indent=2,
    )

    return (
        f"## DPA Document\n\n{doc_text}\n\n"
        f"## Requirements to Evaluate\n\n{req_json}\n\n"
        "Analyze the DPA against each requirement and respond with a JSON array."
    )


def _call_claude(
    client: Anthropic,
    system: str,
    user_message: str,
    model: str,
    max_retries: int = 3,
) -> tuple[str, int]:
    """Call Claude API with retry logic. Returns (response_text, total_tokens)."""
    for attempt in range(max_retries):
        try:
            response = client.messages.create(
                model=model,
                max_tokens=8192,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            return text, tokens

        except AuthenticationError:
            raise  # Don't retry bad API keys

        except RateLimitError:
            if attempt < max_retries - 1:
                wait = 2 ** (attempt + 1)
                logger.warning("Rate limited. Retrying in %ds...", wait)
                time.sleep(wait)
            else:
                raise

        except APIError as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                logger.warning("API error: %s. Retrying in %ds...", e, wait)
                time.sleep(wait)
            else:
                raise

    raise RuntimeError("Unreachable")  # pragma: no cover


def _parse_llm_response(
    response_text: str,
    requirements: list[RequirementItem],
    framework_id: str,
) -> list[FindingData]:
    """Parse Claude's JSON response into FindingData objects."""
    # Strip markdown code fences if present
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        raw_findings = json.loads(text)
    except json.JSONDecodeError:
        logger.error("Failed to parse LLM response as JSON: %.200s...", text)
        # Return all requirements as failed-to-analyze
        return [
            FindingData(
                requirement_id=r.id,
                requirement_name=r.name,
                framework=framework_id,
                finding_type="missing_provision",
                severity=r.severity,
                matched_clause_text=None,
                explanation="Analysis failed: could not parse LLM response.",
                remediation="Re-run the analysis or review manually.",
                confidence=0.0,
            )
            for r in requirements
        ]

    # Build a lookup for requirement metadata
    req_lookup = {r.id: r for r in requirements}

    findings: list[FindingData] = []
    for item in raw_findings:
        req_id = item.get("requirement_id", "")
        req = req_lookup.get(req_id)
        if not req:
            logger.warning("LLM returned unknown requirement_id: %s", req_id)
            continue

        # Validate finding_type
        valid_types = {
            "compliant", "partial_compliance", "deviation",
            "missing_provision", "subprocessor_issue", "transfer_mechanism_issue",
        }
        finding_type = item.get("finding_type", "missing_provision")
        if finding_type not in valid_types:
            finding_type = "missing_provision"

        # Validate severity
        valid_severities = {"critical", "high", "medium", "low", "info"}
        severity = item.get("severity", req.severity)
        if severity not in valid_severities:
            severity = req.severity

        findings.append(
            FindingData(
                requirement_id=req_id,
                requirement_name=req.name,
                framework=framework_id,
                finding_type=finding_type,
                severity=severity,
                matched_clause_text=item.get("matched_clause_text"),
                explanation=item.get("explanation", "No explanation provided."),
                remediation=item.get("remediation"),
                confidence=min(max(float(item.get("confidence", 0.5)), 0.0), 1.0),
            )
        )

    # Check for requirements not returned by the LLM
    returned_ids = {f.requirement_id for f in findings}
    for req in requirements:
        if req.id not in returned_ids:
            logger.warning("LLM did not return finding for requirement: %s", req.id)
            findings.append(
                FindingData(
                    requirement_id=req.id,
                    requirement_name=req.name,
                    framework=framework_id,
                    finding_type="missing_provision",
                    severity=req.severity,
                    matched_clause_text=None,
                    explanation="Requirement was not evaluated by the LLM.",
                    remediation="Re-run the analysis or review manually.",
                    confidence=0.0,
                )
            )

    return findings
