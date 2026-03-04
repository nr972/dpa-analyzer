# Privacy & DPA Analyzer

Analyze Data Processing Agreements against regulatory requirements (GDPR, CCPA/CPRA, SCCs, state privacy laws). Upload a DPA, select frameworks, and get a gap analysis report with compliance scores and specific remediation recommendations.

Built for in-house legal teams, privacy professionals, and legal ops.

---

## Quick Start

### Option 1: Run locally (one command)

```bash
./start.sh        # macOS/Linux
start.bat          # Windows
```

Opens in your browser at [http://localhost:8501](http://localhost:8501).

### Option 2: Docker

```bash
docker compose up
```

API at [http://localhost:8000](http://localhost:8000/docs) | Frontend at [http://localhost:8501](http://localhost:8501)

### Option 3: Hosted version

*Coming soon — deploy to Railway with one click.*

---

## What It Does

1. **Upload** a DPA document (Word or PDF)
2. **Select** regulatory frameworks to analyze against
3. **Get** a clause-by-clause gap analysis powered by Claude AI
4. **Download** reports in JSON, HTML, Word, or PDF

### Supported Frameworks

- **GDPR Article 28** — Processor obligations (11 requirements)
- **CCPA/CPRA** — Service provider & contractor obligations (8 requirements)
- **EU Standard Contractual Clauses** — June 2021 SCC alignment (10 requirements)
- **US State Privacy Laws** — Virginia, Colorado, Connecticut, and others (8 requirements)

### Scoring

Each requirement is weighted by severity (critical, high, medium, low) and scored as compliant, partially compliant, deviation, or missing. Framework scores are weighted averages; the overall score averages across frameworks.

---

## Setup

### Requirements

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/) for Claude

### Install

```bash
pip install -e ".[dev]"
```

### Configure API Key

**Option A:** Set environment variable:
```bash
export DPA_ANTHROPIC_API_KEY=sk-ant-...
```

**Option B:** Enter in the web UI under **Settings** (stored in browser session only, never saved to disk).

### Run

```bash
# Terminal 1: API
uvicorn dpa_app.main:app --reload

# Terminal 2: Frontend
streamlit run dpa_frontend/app.py
```

Or just use `./start.sh` which handles both.

---

## API

The API is independently usable via Swagger docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/analyses/` | Upload DPA + run analysis |
| `GET` | `/api/analyses/{id}` | Get analysis with findings |
| `GET` | `/api/analyses/{id}/report?format=html` | Download report |
| `GET` | `/api/matrices/` | List requirement matrices |
| `POST` | `/api/matrices/` | Create custom matrix |

### Example

```bash
curl -X POST http://localhost:8000/api/analyses/ \
  -H "x-api-key: YOUR_KEY" \
  -F "file=@data/sample/sample_dpa_strong.docx" \
  -G -d "matrix_ids=1,2"
```

---

## Sample Data

The `data/sample/` directory includes:

- **sample_dpa_strong.docx** — Comprehensive DPA (scores ~90/100)
- **sample_dpa_weak.pdf** — Incomplete DPA with gaps (scores ~50/100)
- **sample_analysis_request.json** — Example API request

Upload these through the web UI or API to test immediately.

---

## Project Structure

```
dpa-analyzer/
├── dpa_app/                  # FastAPI backend
│   ├── api/routes/           # REST endpoints
│   ├── models/               # SQLAlchemy models
│   ├── schemas/              # Pydantic validation
│   ├── services/             # Business logic
│   └── templates/            # Report templates
├── dpa_frontend/             # Streamlit UI
├── data/
│   ├── matrices/             # Preset requirement matrices (JSON)
│   └── sample/               # Sample DPAs for testing
├── tests/                    # pytest test suite
├── start.sh                  # One-command startup
├── Dockerfile                # Container deployment
└── docker-compose.yml        # Multi-container setup
```

---

## Testing

```bash
pytest -v
```

---

## Tech Stack

- **Backend:** Python, FastAPI
- **LLM:** Anthropic Claude API (configurable model)
- **Document parsing:** python-docx, pdfplumber
- **Database:** SQLite (PostgreSQL-ready via SQLAlchemy)
- **Frontend:** Streamlit
- **Reports:** JSON, HTML, Word (python-docx), PDF (fpdf2)
- **Deployment:** Docker, Railway

---

## License

MIT
