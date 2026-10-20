"""
main.py — SecureHire AI backend entrypoint.

Run locally (API only):
    uvicorn app.main:app --reload --port 8000

Run as a single combined deployment (API + built React frontend, one URL):
    1. cd frontend && npm run build
    2. cp -r frontend/dist/* backend/app/static/
    3. uvicorn app.main:app --host 0.0.0.0 --port 8000
    -> http://localhost:8000/  now serves the full React app, and
       http://localhost:8000/api/v1/...  serves the API, from the SAME origin.
    (docker/Dockerfile.deploy automates all of this for real deployment.)

Swagger docs available at /docs, ReDoc at /redoc.
"""
from pathlib import Path
import warnings

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import settings
from app.db.session import Base, SessionLocal, engine
from app.routers import admin, analytics, auth, chat, company, company_research, jobs, reports, skills

# Import models so SQLAlchemy's metadata registry knows about every table
# before create_all() (fine for demo/single-instance deployment; a larger
# production system would move schema changes to Alembic migrations).
from app.models import models  # noqa: F401

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "SecureHire AI — an intelligent platform for detecting fraudulent job "
        "and internship postings using explainable ML, NLP, and a company Trust Graph."
    ),
    version=settings.MODEL_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    # Security audit finding (see docs/AUDIT_DB_AUTH.md): SECRET_KEY signs
    # every JWT this app issues. If it's left at the placeholder value
    # from .env.example, anyone who reads the (public) source code could
    # forge a valid auth token for any user. This warning is the entire
    # fix — it doesn't change auth behavior, it just makes the misconfiguration
    # impossible to miss in the logs instead of silently working with a
    # known, guessable key.
    if settings.SECRET_KEY == "change-me-in-production-please":
        warnings.warn(
            "SECRET_KEY is still the default placeholder value. Every JWT this "
            "server issues can be forged by anyone who knows this default. Set "
            "a real random SECRET_KEY in backend/.env (or your deployment's env "
            "vars) before exposing this instance beyond local development.",
            stacklevel=2,
        )

    # Idempotent — safe to run on every boot. Real production migrations
    # should go through Alembic instead; create_all() is used here to keep
    # a single-instance / free-tier deployment simple (see README).
    Base.metadata.create_all(bind=engine)

    # Auto-seed a handful of analyzed postings on first boot only, so a
    # freshly deployed instance isn't a blank dashboard/empty feed the
    # first time someone opens the link. No-ops instantly if data exists.
    db = SessionLocal()
    try:
        from app.services.seed_service import seed_if_empty
        seed_if_empty(db)
    except Exception as exc:  # never block startup on a seeding failure
        print(f"[startup] demo seeding skipped: {exc}")
    finally:
        db.close()


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(jobs.router, prefix=settings.API_V1_PREFIX)
app.include_router(reports.router, prefix=settings.API_V1_PREFIX)
app.include_router(skills.router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics.router, prefix=settings.API_V1_PREFIX)
app.include_router(chat.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin.router, prefix=settings.API_V1_PREFIX)
app.include_router(company.router, prefix=settings.API_V1_PREFIX)
app.include_router(company_research.router, prefix=settings.API_V1_PREFIX)


# ---------------------------------------------------------------------------
# Single-URL deployment: serve the built React app from the same FastAPI
# process/origin as the API. If backend/app/static/ doesn't exist (e.g. in
# local `uvicorn --reload` API-only development), "/" falls back to a
# small JSON status message instead — nothing above this breaks either way.
# ---------------------------------------------------------------------------
RESERVED_PREFIXES = ("api/", "docs", "redoc", "openapi.json", "health")


@app.get("/", include_in_schema=False)
async def root():
    index_file = STATIC_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"service": settings.APP_NAME, "status": "ok", "docs": "/docs"}


@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    """Catch-all for client-side routes (React Router) — must stay the LAST
    route registered so every API router above gets first match."""
    if not STATIC_DIR.exists() or full_path.startswith(RESERVED_PREFIXES):
        raise HTTPException(status_code=404, detail="Not found")

    candidate = STATIC_DIR / full_path
    if candidate.is_file():
        return FileResponse(candidate)

    # Any unknown path (e.g. /analyze, /dashboard) falls back to
    # index.html so React Router can render the right page client-side.
    return FileResponse(STATIC_DIR / "index.html")
