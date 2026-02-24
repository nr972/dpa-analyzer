# CLAUDE.md — Privacy & DPA Analyzer

## Project Summary

Tool for reviewing Data Processing Agreements, privacy addenda, and data-related contract clauses against regulatory requirements (GDPR, CCPA/CPRA, state privacy laws). Upload a DPA (Word or PDF), select a regulatory framework, and the tool performs clause-by-clause analysis against a structured requirements matrix using Claude API. Outputs a gap analysis report with compliance scores and specific remediation recommendations.

## Tech Stack

- **Backend:** Python (FastAPI)
- **LLM integration:** Anthropic API (Claude) for clause-level analysis
- **Document parsing:** python-docx for Word, pdfplumber for PDF
- **Database:** SQLite (prototype) — use SQLAlchemy ORM for future PostgreSQL migration
- **Validation:** Pydantic v2
- **Frontend:** Streamlit (rapid prototype)
- **Deployment:** Docker + Railway
- **Package management:** pyproject.toml (PEP 621)

## Project Structure

```
dpa-analyzer/
├── app/                      # FastAPI backend
│   ├── api/
│   │   └── routes/
│   │       ├── analyses.py   # Upload, analysis, results, report download
│   │       └── matrices.py   # Matrix CRUD endpoints
│   ├── models/
│   │   └── analysis.py       # SQLAlchemy models (4 models, 3 enums)
│   ├── schemas/
│   │   ├── analysis.py       # Analysis/finding Pydantic schemas
│   │   └── matrix.py         # Matrix Pydantic schemas
│   ├── services/
│   │   ├── analysis_service.py  # Orchestration pipeline
│   │   ├── analyzer.py       # Claude API integration + prompts
│   │   ├── matrix_service.py # Matrix CRUD operations
│   │   ├── parser.py         # Word + PDF → text + clauses
│   │   ├── reporter.py       # Report generation (JSON/HTML/Word/PDF)
│   │   ├── scorer.py         # Compliance scoring logic
│   │   └── seed.py           # Seed preset matrices on startup
│   ├── templates/
│   │   └── report.html       # Jinja2 HTML report template
│   ├── config.py             # pydantic-settings, DPA_ env prefix
│   ├── database.py           # SQLAlchemy engine, session, Base, get_db
│   └── main.py               # FastAPI app, lifespan, CORS, health check
├── frontend/
│   └── app.py                # Streamlit UI (4 pages)
├── data/
│   ├── matrices/             # Preset requirement matrices (JSON)
│   │   ├── gdpr_art28.json   # GDPR Article 28 (11 requirements)
│   │   ├── ccpa_cpra.json    # CCPA/CPRA (8 requirements)
│   │   ├── sccs.json         # EU SCCs (10 requirements)
│   │   └── state_privacy.json # US state laws (8 requirements)
│   ├── sample/               # Sample DPAs for testing
│   ├── uploads/              # Uploaded DPA documents (gitignored)
│   └── reports/              # Generated reports (gitignored)
├── tests/                    # pytest test suite (75 tests)
├── start.sh / start.bat      # One-command startup
├── Dockerfile / Dockerfile.railway
├── docker-compose.yml
├── railway.json / railway_start.sh
├── pyproject.toml
├── CLAUDE.md
├── README.md
└── LICENSE
```

## Coding Conventions

- Python 3.11+
- Type hints on all function signatures
- Pydantic v2 for data validation (`from_attributes=True` for ORM models)
- SQLAlchemy 2.0 style (`mapped_column`, `DeclarativeBase`, `Mapped[]`)
- FastAPI dependency injection for DB sessions (`Annotated[Session, Depends(get_db)]`)
- pytest for testing (fixtures in conftest.py, monkeypatch for config)
- Keep modules small and focused
- Service layer holds business logic; routes are thin wrappers

## Key Rules

- **No real data.** All sample data must be synthetic. Never commit real DPAs, company names, client data, or internal policies.
- **Generic framework.** Keep the public codebase company-agnostic. Company-specific requirements matrices stay out of the repo.
- **MIT License.** The copyright line in the LICENSE file must read: `Copyright (c) 2026 Noam Raz and Pleasant Secret Labs`.
- **SQLite for now.** Use SQLAlchemy so the DB layer is swappable to PostgreSQL later.
- **API-first architecture.** FastAPI handles all logic. Streamlit is a thin HTTP client.
- **Environment variables for secrets.** Anthropic API key via `.env` file, never hardcoded. Prefix env vars with `DPA_`.

## Security Requirements

- Validate uploaded file types (restrict to .docx and .pdf only) and enforce size limits
- Sanitize file names on upload to prevent path traversal
- Store uploaded files outside the web root with generated UUIDs, not original file names
- Never log or expose API keys in responses or error messages
- Use parameterized queries via SQLAlchemy ORM (no raw SQL)
- CORS configuration appropriate to deployment environment
- Validate and sanitize all user inputs via Pydantic schemas before processing

## Running the Project

```bash
# Install dependencies
pip install -e ".[dev]"

# Run FastAPI backend
uvicorn app.main:app --reload

# Run Streamlit frontend
streamlit run frontend/app.py

# Run tests
pytest
```

## Git Workflow

- Main branch: `main`
- Commit messages: imperative mood, concise
- PROJECT.md is gitignored (private project context)
- CLAUDE.md is committed (project instructions for AI tooling)
