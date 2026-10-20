# 🛡️ SecureHire AI

**An intelligent, explainable platform that detects fraudulent job and internship postings using Data Engineering, NLP, and Machine Learning — and helps job seekers find trustworthy opportunities instead.**

> Built as a full-stack Data Engineering / Data Science portfolio project by a final-year B.Tech CSE student targeting Data Engineering & Data Science internships. Every module in this repo is real, runnable code — not pseudo-code.

---

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [Installation](#installation)
- [Deploying to One Public URL](#deploying-to-one-public-url)
- [Running with Docker (local, multi-container)](#running-with-docker-recommended)
- [Running Locally (no Docker)](#running-locally-no-docker)
- [API Usage Examples](#api-usage-examples)
- [ML Model Performance](#ml-model-performance)
- [Testing](#testing)
- [Screenshots](#screenshots)
- [Known Limitations & Future Improvements](#known-limitations--future-improvements)
- [Resume Bullet Points](#resume-bullet-points)

---

## Overview

Job and internship scams have surged with the rise of remote work — postings that demand a "registration fee," promise unrealistic pay for zero experience, or impersonate real companies to harvest personal data. Students and early-career job seekers are disproportionately targeted.

SecureHire AI attacks this problem the way a real trust-and-safety / fraud-detection team would:

1. **Data Engineering** — an ETL pipeline ingests, cleans, standardizes, and curates job posting data into a data lake and PostgreSQL.
2. **Data Science / ML** — 12 hand-crafted red-flag features + TF-IDF text vectorization feed a Logistic Regression / Random Forest / XGBoost soft-voting ensemble.
3. **Explainable AI** — SHAP attributes every prediction back to specific, human-readable reasons — never a black box.
4. **Full-Stack Product** — a FastAPI backend and a React + Tailwind + Framer Motion frontend, containerized with Docker Compose.

## Features

| Category | What it does |
|---|---|
| **Fraud Probability Score** | Paste/upload a posting → get a 0–100% fraud score in under a second. |
| **Explainable AI** | SHAP-based top-feature breakdown: exactly which signals drove the score, and in which direction. |
| **Company Trust Graph** | Live 0–100 trust score per company from domain age (mocked WHOIS), verification status, posting history, and user reports. |
| **Skill Intelligence Engine** | NLP-extracted required skills, compared against your tracked profile, with market-demand tiers and learning resources for gaps. |
| **Job Authenticity Timeline** *(data model ready)* | Posted/updated timestamps and duplicate-detection hooks are in the schema (`job_postings.duplicate_of`, `last_updated_at`) for a visual timeline UI. |
| **Community Reporting** | Users can report suspicious postings with evidence; reports directly lower a company's trust score. |
| **AI Career Assistant** | A grounded chat endpoint answers "why is this suspicious?", "what should I learn?", "find safer alternatives?" using real prediction data — no external LLM API dependency required to run. |
| **Analytics Dashboard** | Fake-vs-real ratio, fraud by location/category, top scam keywords, model confidence distribution, skill demand trends — all live charts. |
| **Admin Console** | Review reported jobs, verify companies, monitor live model performance metrics. |

## Architecture

Full system diagram (Mermaid) and a request-flow sequence diagram: **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**

```
React (Vite/Tailwind) → FastAPI (JWT auth, REST) → ML Service (features → NLP → ensemble → SHAP)
                                ↕                              ↕                    ↕
                           PostgreSQL                     Model Store          Gemini AI
                                ↕                          (joblib)         (company intelligence)
                             Redis (prediction cache)

ML training ETL:      data/raw → ingest.py → clean.py → load.py → data/curated → PostgreSQL
Warehouse/analytics ETL: PostgreSQL → ingest_jobs.py → clean_jobs.py → enrich_jobs.py
                         → build_warehouse.py → data/warehouse + pipeline_metrics table
```

## Data Engineering Architecture

SecureHire AI runs **two separate, independently-runnable ETL pipelines** —
they serve different purposes and don't share state:

1. **ML training pipeline** (`pipelines/generate_dataset.py` →
   `ingest.py` → `clean.py` → `load.py`) — produces the *synthetic
   labeled* dataset the fraud classifier is trained on (see
   [ML Model Performance](#ml-model-performance) below). Raw → landing →
   processed → curated.

2. **Warehouse/analytics pipeline** (`pipelines/ingest_jobs.py` →
   `clean_jobs.py` → `enrich_jobs.py` → `build_warehouse.py`, orchestrated
   by `run_pipeline_jobs.py`) — extracts **real, already-analyzed**
   postings from the live PostgreSQL database and builds an
   analytics-ready warehouse layer that powers the Pipeline Health,
   Company Trust, and Fraud Trends dashboard sections.

   ```
   data/raw/warehouse/<run_id>/       — immutable extract from PostgreSQL
   data/staging/<run_id>/             — schema-validated, dtype-coerced
   data/processed/<run_id>/           — deduplicated + normalized
   data/curated/<run_id>/             — enriched with derived fields
   data/warehouse/<run_id>/           — final analytics-ready snapshot
   ```

   Every run is recorded in the `pipeline_metrics` table (rows ingested/
   cleaned, duplicates removed, duration, success/failure) — visible on
   the dashboard's Pipeline Health section.

   **Architecture note:** this pipeline does *not* write into new
   duplicate `job_postings`/`fraud_analysis` warehouse tables — those
   already exist as the OLTP source-of-record tables this pipeline reads
   *from*. Instead, `v_warehouse_job_fact` (a SQL view — see
   `docs/schema.sql`) is the flat, denormalized join used for fast
   dashboard queries, and two genuinely new tables (`company_intelligence`,
   `pipeline_metrics`) hold the data that didn't exist before. This avoids
   two tables silently drifting out of sync as a second, competing source
   of truth for the same facts.

   Run it: `cd pipelines && python3 run_pipeline_jobs.py`

## AI Components

- **RandomForest fraud classifier** — used specifically for SHAP
  explainability (fast, exact `TreeExplainer` for tree ensembles).
- **Calibrated ensemble (LogReg + RandomForest + XGBoost)** — the actual
  `fraud_probability` score comes from this soft-voting ensemble,
  probability-calibrated via `CalibratedClassifierCV` on a held-out split
  (see `docs/CHANGELOG_FRAUD_FIX.md` for why this matters).
- **TF-IDF NLP processing** — text-pattern features, concatenated with 13
  hand-crafted red-flag features (registration fee mentions, urgent
  language, salary anomalies, etc.).
- **SHAP explainability** — every prediction's top contributing features
  are gated by `is_feature_genuinely_present()` so an explanation is only
  ever shown if the underlying raw signal was actually observed in the
  text — never inferred purely from a statistical SHAP artifact.
- **Gemini company intelligence** (`backend/app/services/company_ai_service.py`)
  — a second, independent signal: given a company name (+ website/email if
  known), Gemini returns a structured JSON assessment (industry, HQ,
  website/online-presence status, a 0–100 verification score, and a
  recommendation). This is surfaced *alongside*, never blended into, the
  ML fraud score — they're different questions ("does this text look like
  a scam" vs. "does this company appear to be real"). Optional: the app
  works fully without a `GEMINI_API_KEY` configured, returning
  `company_intelligence.status = "unavailable"` instead of failing the
  request.

## System Workflow

```
User → FastAPI /jobs/analyze
         ├─→ ML Engine (feature engineering → TF-IDF → calibrated ensemble → SHAP)
         ├─→ Gemini AI (company verification, additive, fails open)
         ├─→ PostgreSQL (job_postings, fraud_predictions, company_intelligence)
         └─→ Analytics Dashboard (fraud-trends, company-trust, pipeline-health)
```

## Tech Stack

- **Frontend:** React 18 + Vite, Tailwind CSS, Framer Motion, Recharts, React Router
- **Backend:** Python 3.11, FastAPI, JWT auth (python-jose + passlib), Pydantic v2, Swagger/OpenAPI (auto-generated at `/docs`)
- **Database:** PostgreSQL 16 (normalized OLTP schema + warehouse layer: `company_intelligence`, `pipeline_metrics`, `v_warehouse_job_fact`), Redis 7 (prediction + analytics caching)
- **Data Engineering:** Pandas, SQLAlchemy, two independent ETL pipelines (ML training data, and a live-data analytics warehouse) with a reference Airflow DAG
- **ML/NLP:** scikit-learn (Logistic Regression, Random Forest), XGBoost, TF-IDF (scikit-learn), SHAP, calibrated probabilities (`CalibratedClassifierCV`)
- **AI:** Google Gemini (`google-generativeai`) for structured company intelligence
- **Deployment:** Docker + Docker Compose (postgres, redis, backend, frontend/nginx, plus one-off `trainer` and `warehouse_pipeline` tool services)

## Folder Structure

```
securehire-ai/
├── frontend/                  # React + Vite + Tailwind SPA
│   └── src/{pages,components,api,context}
├── backend/                   # FastAPI service
│   └── app/
│       ├── routers/           # auth, jobs, reports, skills, analytics, chat, admin
│       ├── models/            # SQLAlchemy ORM (incl. CompanyIntelligence, PipelineMetric)
│       ├── schemas/           # Pydantic request/response models
│       ├── services/          # ml_service, analysis_service, company_ai_service (Gemini),
│       │                      #   trust_service, cache, seed_service
│       ├── ml_core/           # mirrored copy of ml/ (feature_engineering, explain, preprocess)
│       └── core/               # config, security, deps
├── ml/                        # Standalone, testable ML training package
│   ├── feature_engineering.py
│   ├── preprocess.py
│   ├── train.py               # calibration, versioned artifacts
│   ├── evaluate.py
│   ├── explain.py             # SHAP + presence-gated explanations
│   └── predict.py
├── pipelines/
│   ├── generate_dataset.py    # ML training pipeline: synthetic labeled dataset generator
│   ├── ingest.py / clean.py / load.py / run_pipeline.py
│   ├── ingest_jobs.py         # Warehouse pipeline: extract from live PostgreSQL
│   ├── clean_jobs.py          #   stage + clean + normalize
│   ├── enrich_jobs.py         #   derived/analytics fields
│   ├── build_warehouse.py     #   final snapshot + pipeline_metrics
│   ├── run_pipeline_jobs.py   #   orchestrates the 4 warehouse steps above
│   └── airflow_dag.py         # reference production orchestration
├── data/
│   ├── raw/                   # landing zone (both pipelines)
│   ├── staging/                # schema-validated (warehouse pipeline)
│   ├── processed/             # cleaned/deduplicated
│   ├── curated/                # ML/DB-ready + enriched
│   └── warehouse/              # final analytics-ready snapshots
├── models/<version>/          # versioned joblib artifacts + metrics.json + training_env.json
├── docker/                    # Dockerfiles + docker-compose.yml + nginx.conf
│   └── Dockerfile.deploy      # combined single-service image (frontend + backend + trained model baked in)
├── render.yaml                # one-click Render blueprint (single-URL deployment)
├── docs/                      # ARCHITECTURE.md, schema.sql, DEPLOY.md, CHANGELOG_FRAUD_FIX.md
└── tests/                     # pytest suite (API + ML + explainability regression tests)
```

`backend/app/main.py` can serve the built frontend directly from the same
process (`backend/app/static/`, populated by `Dockerfile.deploy` or manually
via `npm run build && cp -r frontend/dist/* backend/app/static/`) — this is
what makes the one-URL deployment possible; see [`docs/DEPLOY.md`](docs/DEPLOY.md).

## Installation

### Prerequisites
- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (or Docker)
- Redis 7 (or Docker)

## Deploying to One Public URL

Want a single shareable link (e.g. for a resume/LinkedIn) where opening it shows the complete app — landing page, Analyze Job, Dashboard, everything — at one origin? See **[`docs/DEPLOY.md`](docs/DEPLOY.md)** for the full walkthrough (free, no credit card, ~10 minutes).

Short version: `docker/Dockerfile.deploy` builds the React frontend, trains the ML model, and bakes both into a single FastAPI container that serves the whole product from one process (`backend/app/main.py` serves the built frontend directly). Deploy that one image to Render (or any Docker host) + a free Neon Postgres database, and you get one URL for everything.

## Running with Docker (local, multi-container — recommended for development)

```bash
git clone <your-fork-url> securehire-ai
cd securehire-ai

# 1. Generate data + train the model once, locally (models/ is volume-mounted into the backend)
cd pipelines && pip install -r requirements.txt && python3 generate_dataset.py --n 6000 && python3 run_pipeline.py && cd ..
cd ml && pip install -r requirements.txt && python3 train.py && cd ..

# 2. (Optional) add your Gemini API key for company intelligence — the app
#    works fully without this, company_intelligence.status will just be
#    "unavailable" instead of a real result.
cp backend/.env.example backend/.env
#    edit backend/.env and set GEMINI_API_KEY=... (get one at https://aistudio.google.com/apikey)

# 3. Bring up the full stack
cd docker
docker compose up --build
```

- Frontend → http://localhost:3000
- Backend Swagger docs → http://localhost:8000/docs
- PostgreSQL → localhost:5432 (`securehire` / `securehire`)

### Running the warehouse ETL pipeline

Once the app has analyzed at least a few postings (or after the
auto-seed on first boot), build the analytics warehouse:

```bash
# Via Docker (uses the same environment as the backend):
docker compose -f docker/docker-compose.yml run --rm warehouse_pipeline

# Or locally, with DATABASE_URL pointed at your running Postgres:
cd pipelines
export DATABASE_URL="postgresql+psycopg2://securehire:securehire@localhost:5432/securehire"
python3 run_pipeline_jobs.py
```

This populates the Company Trust and Pipeline Health sections of the
dashboard (`/dashboard`) and the `pipeline_metrics` table.

## Running Locally (no Docker)

```bash
chmod +x setup.sh && ./setup.sh
```
This generates the dataset, runs the ETL pipeline, trains the models, and installs both backend and frontend dependencies. Then, in two terminals:
```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload         # http://localhost:8000/docs

# Terminal 2
cd frontend && npm run dev                          # http://localhost:5173
```

## API Usage Examples

Full interactive docs are auto-generated at `/docs` (Swagger UI). A few examples:

```bash
# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword123","full_name":"name"}'

# Analyze a job posting
curl -X POST http://localhost:8000/api/v1/jobs/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Data Entry Intern",
    "raw_text": "Immediate joining required!!! Earn up to Rs 90,000 per week working from home! No experience needed, guaranteed placement! Send registration fee to confirm your seat.",
    "contact_email": "hr.hiring123@gmail.com",
    "company_name": "Quick Earn Solutions"
  }'
# -> {"fraud_probability": 78.51, "risk_category": "High", ...,
#     "company_intelligence": {"status": "unavailable", ...}}  <- "ok" if GEMINI_API_KEY is set

# Fraud analytics for the dashboard
curl http://localhost:8000/api/v1/analytics/fraud-trends

# Company trust: suspicious/trusted companies, recruiter domain split,
# Gemini website-verification distribution
curl http://localhost:8000/api/v1/analytics/company-trust

# Warehouse ETL pipeline run history (requires having run
# pipelines/run_pipeline_jobs.py at least once)
curl http://localhost:8000/api/v1/analytics/pipeline-health
```

### Example warehouse SQL queries

```sql
-- Flat, pre-joined view the dashboard queries under the hood
SELECT title, company_name, risk_category, fraud_probability,
       company_verification_score, website_status
FROM v_warehouse_job_fact
WHERE risk_category = 'High'
ORDER BY job_created_at DESC
LIMIT 20;

-- Pipeline run history
SELECT run_id, rows_ingested, rows_cleaned, duplicates_removed,
       fraud_rows_detected, pipeline_duration_seconds, status, created_at
FROM pipeline_metrics
ORDER BY created_at DESC;

-- Companies Gemini flagged with a low verification score
SELECT jp.title, c.name, ci.verification_score, ci.recommendation
FROM company_intelligence ci
JOIN job_postings jp ON jp.id = ci.job_id
JOIN companies c ON c.id = jp.company_id
WHERE ci.status = 'ok' AND ci.verification_score < 40
ORDER BY ci.verification_score ASC;
```

## ML Model Performance

Trained on a 5,000-row synthetic dataset (with injected label noise to avoid unrealistic separability) — see `pipelines/generate_dataset.py`. In production this pipeline ingests real labeled data such as the Kaggle "Real / Fake Job Posting Prediction" dataset; swap the CSV in `data/raw/` and re-run `ml/train.py`.

| Model | Accuracy | Precision | Recall | F1 | ROC-AUC | 5-fold CV F1 |
|---|---|---|---|---|---|---|
| Logistic Regression | 94.0% | 91.3% | 88.2% | 0.897 | 0.928 | 0.891 ± 0.016 |
| Random Forest | 94.0% | 91.6% | 87.9% | 0.897 | 0.924 | 0.889 ± 0.016 |
| XGBoost | 93.9% | 91.0% | 88.2% | 0.896 | 0.915 | 0.886 ± 0.017 |
| **Ensemble (soft voting)** | **94.0%** | **91.3%** | **88.2%** | **0.897** | **0.924** | — |

Confusion matrix (ensemble, test set): `[[678, 25], [35, 262]]` → 25 false positives, 35 false negatives out of 1,000 held-out postings.

Re-generate this table: `cd ml && python3 train.py` (writes `models/<version>/metrics.json`).

## Testing

```bash
# ML unit tests (feature engineering logic — no DB required)
cd ml && pytest ../tests/test_feature_engineering.py -v

# API integration tests (requires Postgres + Redis running)
cd backend && pytest ../tests/test_api.py -v
```

## Screenshots

> _Add screenshots here after running the app locally:_
> - `docs/screenshots/landing.png` — Landing page
> - `docs/screenshots/analyze.png` — Analyze Job result view
> - `docs/screenshots/dashboard.png` — Analytics dashboard
> - `docs/screenshots/admin.png` — Admin console

## Known Limitations & Future Improvements

This is a portfolio scaffold, built and verified end-to-end — but built honestly, so here's what's simplified and what a v2 would add:

- **Training data is synthetic.** Swap in the Kaggle "Real/Fake Job Posting" dataset (or a scraped/live feed) via `pipelines/ingest.py` for production-grade evaluation.
- **Domain age is mocked** (`trust_service.mock_domain_age_days`). Swap in a real WHOIS API (e.g. whoisxmlapi.com) behind the same function signature.
- **AI Career Assistant is retrieval + template based**, not an LLM call — intentional, so the project runs fully offline with no API keys. Swapping in a real LLM call (e.g. the Anthropic API) at `chat.py::_generate_reply` is a small, well-isolated change.
- **`ml_core/` is duplicated** between `ml/` (training) and `backend/app/ml_core/` (inference) rather than published as a shared internal package — called out in `ml_service.py`'s docstring as the natural next refactor.
- **DB schema managed via `create_all()`** for local/demo simplicity; Alembic is listed as a dependency for when real migrations are needed.
- **The free single-URL deployment path skips Redis** (see `docs/DEPLOY.md`) — the app is designed to fail open without it (`cache.py`), so this only costs a bit of caching performance, not functionality. The local Docker Compose stack still runs the full Postgres + Redis architecture as originally designed.
- **Job Authenticity Timeline UI** — the schema supports it (`duplicate_of`, `last_updated_at`) but the frontend visual timeline component isn't built yet.
- Sentence-embedding (SBERT) similarity search for "find safer alternatives" is a natural upgrade over the current trust-score-based ranking.
- **Gemini company intelligence was tested with mocked API responses**, not a live key — the sandbox this was built in has no network access to Google's API domain. The request/response parsing, JSON-fence stripping, and fail-open behavior (no key / bad key / malformed response) are all directly tested (see `company_ai_service.py`'s inline test), but you should do one live smoke test with a real `GEMINI_API_KEY` before relying on it.
- **The fraud model uses a calibrated ensemble (`ensemble.joblib`), not `random_forest.joblib` alone**, for the actual `fraud_probability` score — this is a deliberate choice carried over from the previous calibration fix (see `docs/CHANGELOG_FRAUD_FIX.md`); reverting to RandomForest-only would lose that calibration. `random_forest.joblib` is still used, separately, for SHAP explanations.
- **The warehouse pipeline's `enrich_jobs.py` derived fields are intentionally simple** (salary bands, high-risk flag, email domain, posting age) — a v2 could add trend/rolling-window features (e.g. 7-day fraud rate by category) computed at this stage rather than only at query time.

## Resume Bullet Points

- **Architected and built SecureHire AI**, a full-stack fraud-detection platform (React, FastAPI, PostgreSQL, Redis, Docker) that scores job/internship postings for fraud risk in real time, combining a normalized 11-table relational schema with a Redis-cached prediction API.
- **Designed and implemented a 3-stage ETL pipeline** (ingest → clean/normalize → curate/load) using Pandas and SQLAlchemy to standardize company names, locations, and skills from raw job posting data into a structured data lake and PostgreSQL, including a reference Apache Airflow DAG for production orchestration.
- **Engineered 12 interpretable fraud-detection features** (salary anomalies, urgent-language scoring, free-email-domain detection, skill-role mismatch, etc.) combined with TF-IDF text vectorization, then trained and cross-validated a Logistic Regression / Random Forest / XGBoost soft-voting ensemble achieving 94% accuracy and 0.90 F1 on held-out test data.
- **Built an Explainable AI layer using SHAP** to attribute every fraud prediction to specific, human-readable risk factors, and designed a company "Trust Graph" scoring system combining domain verification, posting history, and community-sourced fraud reports.
- **Shipped a production-style deployment**: containerized all 4 services (React/nginx, FastAPI, PostgreSQL, Redis) with Docker Compose, wrote a pytest suite covering both ML logic and live API integration, and documented the system with Mermaid architecture diagrams and auto-generated OpenAPI/Swagger docs.

---

Built by a 4th-year B.Tech CSE student as a Data Engineering / AI-ML portfolio project. Contributions and forks welcome.

## Product UX behavior
- Job analysis requires an authenticated SecureHire account; analysis history is stored per user.
- The Analyze Job form accepts the source website where the job description was found, separately from the employer's own website.
- Trusted Jobs is a small shortlist capped at 10 low-risk analyzed postings.
- Dashboard is user-facing account/history space rather than technical ETL/model analytics.
- Jobs & Skills in Demand shows the existing skill-demand vocabulary with observed counts from analyzed jobs.
- Light/dark theme selection is available from the navigation bar.
- Gemini company intelligence is available after a job analysis and can perform deeper, search-grounded company research when `GEMINI_API_KEY` is configured.
