# Career Relocation Planner API

A personalised career relocation planner that takes a user's career profile, target role, destination country, salary expectation, timeline, and work authorisation constraints, and returns a ranked action plan with an honest feasibility assessment.

## Quick Start

### Prerequisites
- Python 3.11+
- pip

### Setup

```bash
# Clone and enter project
cd GHX_Assessment

# Create virtual environment
python -m venv venv

# Activate (Windows)
.\venv\Scripts\activate

# Activate (Linux/Mac)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment config
cp .env.example .env

# (Optional) Add your Groq API key to .env for LLM narratives
# Get a free key at https://console.groq.com/

# Start the server
uvicorn app.main:app --reload --port 8000
```

### Access
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## API Endpoints

### Public
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/info` | App info + available destinations |

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Create account |
| POST | `/api/v1/auth/login` | Login → JWT token |
| GET | `/api/v1/auth/me` | Current user (protected) |

### Plans (all protected)
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/plans/generate` | Generate relocation plan |
| POST | `/api/v1/plans/save` | Save a generated plan |
| GET | `/api/v1/plans` | List saved plans |
| GET | `/api/v1/plans/{id}` | Get saved plan detail |

## Architecture

```
app/
├── main.py              # FastAPI entry point
├── config.py            # Pydantic settings
├── database.py          # SQLAlchemy engine
├── data_loader.py       # JSON data layer
├── data/                # Destination/role data (JSON)
│   ├── germany/
│   └── united_kingdom/
├── models/              # ORM models (User, Plan)
├── schemas/             # Pydantic request/response
├── routers/             # API endpoints
│   ├── auth.py
│   └── plans.py
├── services/            # Business logic
│   ├── eligibility.py   # Deterministic visa checks
│   ├── salary.py        # Deterministic salary analysis
│   ├── timeline.py      # Deterministic timeline analysis
│   ├── plan_engine.py   # Orchestrator
│   └── llm_service.py   # Groq LLM narrative
└── auth/                # JWT + hashing
```

## Key Design Decisions

- **Deterministic vs LLM**: Eligibility, salary thresholds, and timeline conflicts are computed deterministically. The LLM only generates narrative summaries.
- **Data layer**: JSON files per destination/role. Adding a new destination requires only a new JSON file — no code changes.
- **Graceful degradation**: If the LLM fails, the plan returns without a narrative. The `llm_metadata` field reports what happened.

See [DECISIONS.md](DECISIONS.md) for full documentation.

## Testing the Two Scenarios

### Scenario A: India → Germany (Senior Backend Engineer)
```json
{
  "origin": "India",
  "destination": "Germany",
  "target_role": "Senior Backend Engineer",
  "salary_expectation": 45000,
  "timeline_months": 12,
  "work_authorisation_status": "needs_sponsorship"
}
```

### Scenario B: India → UK (Product Manager)
```json
{
  "origin": "India",
  "destination": "United Kingdom",
  "target_role": "Product Manager",
  "salary_expectation": 60000,
  "timeline_months": 6,
  "work_authorisation_status": "no_constraint"
}
```

## Edge Cases Handled

1. **Timeline conflict**: 1-month timeline with 2-4 month visa processing → critical warning, `not_feasible`
2. **Salary shortfall**: €43,600 vs €43,800 Blue Card threshold → explicit €200 shortfall warning
3. **Missing data**: Unknown destination/role → structured 404 with available combinations

## Docker

```bash
docker build -t relocation-planner .
docker run -p 8000:8000 --env-file .env relocation-planner
```
