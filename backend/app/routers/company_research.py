"""
company_research.py — endpoint for the search-grounded deep company
research feature. Deliberately separate from routers/company.py's
POST /company/check (which uses the older, non-search-grounded
company_ai_service.py) — see company_research_service.py's module
docstring for the full rationale.

Stateless: no database writes. This is an on-demand "Research Company
with Gemini" action, not part of the persisted job-analysis record.
"""
from datetime import datetime, timezone

from fastapi import APIRouter

from app.schemas.company_research import (
    CompanyResearchReport, CompanyResearchRequest, ResearchSourceCitation,
)
from app.services.company_research_service import research_company

router = APIRouter(prefix="/company", tags=["Company Research (Gemini, search-grounded)"])


@router.post("/deep-research", response_model=CompanyResearchReport)
def deep_research_company(payload: CompanyResearchRequest):
    result = research_company(
        company_name=payload.company_name,
        company_website=payload.company_website,
        job_title=payload.job_title,
    )
    result_dict = result.__dict__.copy()
    # result.sources is a list of the service layer's own SourceCitation
    # dataclass instances — Pydantic won't auto-coerce an arbitrary
    # dataclass into a BaseModel, so convert explicitly rather than rely
    # on implicit validation (verified this fails silently-to-error
    # without this conversion).
    result_dict["sources"] = [
        ResearchSourceCitation(title=s.title, url=s.url, domain=s.domain)
        for s in result.sources
    ]
    # Only stamp a "last checked" time for a genuine, successful research
    # result — an "unavailable"/"error" status has nothing to timestamp.
    result_dict["generated_at"] = datetime.now(timezone.utc) if result.status == "ok" else None
    return CompanyResearchReport(**result_dict)
