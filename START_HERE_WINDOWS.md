# SecureHire AI — Start Here (Windows)

This package keeps the existing SecureHire application, ML artifacts, datasets, ETL pipelines,
and React screens, with a safer environment configuration and optional Gemini-powered chat.

## Before you start
- Install Docker Desktop and wait until it says Docker is running.
- Keep this folder extracted; do not run Docker Compose from inside `frontend`.
- The bundled `.env` has no API key. Add your own `GEMINI_API_KEY` for Gemini company research and AI chat.
- Never upload `.env` to GitHub. If an API key from an earlier copy was shared, revoke it and issue a replacement.

## Start the full app
Open PowerShell in the extracted `SecureHire` folder (the folder containing `docker`, `frontend`, and `backend`) and run:

```powershell
docker compose -f .\docker\docker-compose.yml config --quiet
docker compose -f .\docker\docker-compose.yml up -d --build
docker compose -f .\docker\docker-compose.yml ps
```

Wait for backend, frontend, PostgreSQL, and Redis to become healthy.

Open:
- App: http://localhost:3000
- API documentation: http://localhost:8000/docs
- Backend health: http://localhost:8000/health

## First use
1. Click **Create account** and register a new user.
2. Open **Analyze Job**, paste a full job description, and run analysis.
3. Open the result and test the company intelligence action. Without a Gemini key, company search will show retrieved public source links as a clearly labelled preview; it will not pretend to produce an AI verdict.
4. Check Dashboard, Saved Analyses, Trusted Feed, Skills Demand, and Profile.

Protected endpoints returning `401 Unauthorized` before login is expected. Register or log in first. If a previously signed-in browser shows `Could not validate credentials` after you replace the project folder or change `SECRET_KEY`, log out and log in again. If needed, clear site data for `localhost:3000` and reload.

The job-risk model works without a Gemini key. AI-generated company summaries require a valid `GEMINI_API_KEY` in the root `.env`; company-name search attempts to retrieve public pages, but availability depends on internet access and the search provider.

## If a container was already created before source changes
Use `docker compose ... up -d --build` rather than `start`; `start` only starts old containers and does not rebuild images.

## What is integrated
- React + Vite + Tailwind frontend, styled around the supplied dark navy/blue/purple reference screenshots.
- FastAPI backend with JWT authentication and PostgreSQL/Redis services.
- Trained ML ensemble and explainable fraud-risk results from the included model artifacts.
- Company-name web search/public-page retrieval and optional Gemini-generated company research; when Gemini is not configured, the UI shows a clearly labelled source preview instead of a fake AI verdict.
- Optional Gemini career chat grounded in stored analysis context.
- Deterministic chat fallback when Gemini is not configured or temporarily unavailable.
- Data ingestion, cleaning, enrichment, warehouse, and pipeline health modules.

## Verification note
Python source compilation was checked during packaging. Full automated API tests and a frontend production build
must be run on a machine with the project dependencies installed and PostgreSQL/Redis available; this packaging
environment did not have the PostgreSQL Python driver, and package installation could not complete here.
