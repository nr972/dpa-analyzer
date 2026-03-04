"""Seed preset requirements matrices on startup."""

import json
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from dpa_app.config import settings
from dpa_app.models.analysis import RequirementsMatrix

logger = logging.getLogger(__name__)

# Map of JSON filenames to (name, framework, description)
PRESET_MATRICES = {
    "gdpr_art28.json": (
        "GDPR Article 28 — Processor Obligations",
        "gdpr_art28",
        "Requirements from GDPR Article 28 governing data processor obligations, "
        "including processing instructions, security, sub-processors, breach "
        "notification, audit rights, and data transfers.",
    ),
    "ccpa_cpra.json": (
        "CCPA/CPRA — Service Provider Obligations",
        "ccpa_cpra",
        "Requirements from the California Consumer Privacy Act (as amended by CPRA) "
        "governing service provider and contractor obligations for personal information.",
    ),
    "sccs.json": (
        "EU Standard Contractual Clauses",
        "sccs",
        "Requirements from the EU Commission's Standard Contractual Clauses (June 2021) "
        "for international data transfers, covering Modules 1–4.",
    ),
    "state_privacy.json": (
        "US State Privacy Laws",
        "state_privacy",
        "Common requirements across US state privacy laws (Virginia VCDPA, Colorado CPA, "
        "Connecticut CTDPA, and others) for processor/service provider obligations.",
    ),
}


def seed_matrices(db: Session) -> None:
    """Load preset matrices from JSON files if they don't already exist."""
    existing = set(
        db.scalars(
            select(RequirementsMatrix.name).where(RequirementsMatrix.is_preset.is_(True))
        ).all()
    )

    for filename, (name, framework, description) in PRESET_MATRICES.items():
        if name in existing:
            continue

        filepath = settings.matrices_dir / filename
        if not filepath.exists():
            logger.warning("Seed matrix file not found: %s", filepath)
            continue

        with open(filepath) as f:
            content = json.load(f)

        matrix = RequirementsMatrix(
            name=name,
            description=description,
            framework=framework,
            version=content.get("version", "1.0"),
            is_preset=True,
            content=content,
        )
        db.add(matrix)
        logger.info("Seeded preset matrix: %s", name)

    db.commit()
