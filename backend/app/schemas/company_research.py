"""
company_research.py — schemas for the search-grounded deep company
research feature (backend/app/services/company_research_service.py).

Deliberately a separate schema module from schemas/jobs.py's
CompanyIntelligenceInfo (the existing, non-search-grounded, automatically-
bundled-into-/jobs/analyze company signal) — this is a different
capability with a different shape (source citations, founded year,
verified/interpreted/unverifiable split), triggered on-demand, never
merged into the ML analysis response.
"""
from datetime import datetime

from pydantic import BaseModel


class ResearchSourceCitation(BaseModel):
    title: str | None = None
    url: str
    domain: str | None = None


class CompanyResearchRequest(BaseModel):
    company_name: str
    company_website: str | None = None
    job_title: str | None = None  # optional context to help ground the search


class CompanyResearchReport(BaseModel):
    status: str  # "ok" | "unavailable" | "error"
    company_name: str = ""
    company_overview: str | None = None
    official_website: str | None = None
    industry: str | None = None
    founded_year: str | None = None
    headquarters: str | None = None
    products_services: str | None = None
    company_size: str | None = None
    online_presence: str | None = None
    careers_presence: str | None = None
    recent_public_info: str | None = None
    red_flags: str | None = None
    # Only meaningfully populated when job_title was supplied in the
    # request (see company_research_service.py's prompt) — whether the
    # company's public presence appears consistent with the specific job
    # posting it's attached to. null/None if no job context was given.
    job_consistency_notes: str | None = None
    overall_assessment: str | None = None
    verified_facts: list[str] = []
    ai_interpretation: list[str] = []
    unverifiable: list[str] = []
    sources: list[ResearchSourceCitation] = []
    llm_model: str | None = None
    generated_at: datetime | None = None
    # Safe, generic, user-facing explanation when status != "ok" — same
    # pattern as CompanyIntelligenceInfo.error_message. Never contains
    # raw exception text or secrets.
    error_message: str | None = None
