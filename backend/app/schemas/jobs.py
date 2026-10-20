import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class JobAnalyzeRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    raw_text: str = Field(min_length=30, description="Full job/internship description text")
    company_name: str | None = None
    # Optional and NOT collected by the current frontend form. If a caller
    # (or a future frontend field / integration) supplies it, it's used;
    # otherwise it stays genuinely unknown rather than being assumed False.
    # See backend/app/services/analysis_service.py for how this is handled.
    company_website: str | None = None
    location: str | None = None
    contact_email: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    source_url: str | None = None


class TopFeature(BaseModel):
    feature: str
    weight: float
    direction: str  # "increases_risk" | "decreases_risk"
    description: str


class SkillInfo(BaseModel):
    skill_name: str
    is_required: bool
    demand_level: str
    user_has_skill: bool | None = None
    learning_resource: str | None = None


class TrustSignals(BaseModel):
    domain_age_days: int | None
    has_verified_domain: bool
    posting_count: int
    fraud_report_count: int
    trust_score: float


class CompanyIntelligenceInfo(BaseModel):
    """Gemini-generated company verification — a separate signal from the
    ML fraud_probability, surfaced alongside it, not blended into it. See
    backend/app/services/company_ai_service.py."""
    status: str  # "ok" | "unavailable" | "error"
    company_summary: str | None = None
    industry: str | None = None
    headquarters: str | None = None
    website_status: str = "unknown"
    online_presence: str = "unknown"
    recruiter_email_status: str = "unknown"
    verification_score: float | None = None
    key_findings: list[str] = []
    evidence: list[dict] = []
    recommendation: str | None = None
    llm_provider: str = "gemini"
    llm_model: str | None = None
    # Safe, generic, user-facing explanation when status != "ok" (e.g.
    # "Company intelligence is temporarily unavailable."). Never contains
    # raw exception text, API keys, or other internal detail — see
    # company_ai_service.py's _unavailable()/_error() for the split
    # between this and the internal-only log message.
    error_message: str | None = None


class JobAnalyzeResponse(BaseModel):
    job_id: uuid.UUID
    fraud_probability: float
    risk_category: str
    confidence: float
    model_version: str
    top_features: list[TopFeature]
    explanation_text: str
    skills: list[SkillInfo]
    trust_signals: TrustSignals
    similar_trusted_alternatives: list[str] = []
    cached: bool = False
    # Additive field — existing frontend/callers that don't read this
    # still work unchanged. Always present (never null) so the frontend
    # doesn't need special-casing; check `.status` to see if it's real.
    company_intelligence: CompanyIntelligenceInfo
    source_url: str | None = None


class JobFullAnalysisResponse(BaseModel):
    """Full analysis detail for the /analysis/:jobId page — reconstructed
    from already-persisted data (fraud_predictions, extracted_skills,
    company_intelligence), not a fresh model run. Superset of JobOut's
    descriptive fields (title/company/location, needed since this page
    can be opened directly, e.g. from history, without the original
    JobAnalyzeResponse still in memory) plus JobAnalyzeResponse's
    analysis fields, minus `cached` (not meaningful for a re-fetch)."""
    job_id: uuid.UUID
    title: str
    company_name: str | None = None
    location: str | None = None
    employment_type: str | None = None
    source_url: str | None = None
    created_at: datetime
    fraud_probability: float
    risk_category: str
    confidence: float
    model_version: str
    top_features: list[TopFeature]
    explanation_text: str
    skills: list[SkillInfo]
    trust_signals: TrustSignals
    company_intelligence: CompanyIntelligenceInfo


class CompanyCheckRequest(BaseModel):
    """Standalone company verification — deliberately separate from
    JobAnalyzeRequest, which requires a real job description (min 30
    chars). Checking a company shouldn't require fabricating a fake job
    posting just to satisfy that field."""
    company_name: str = Field(min_length=1, max_length=255)
    company_website: str | None = None


class CompanyCheckResponse(BaseModel):
    company_name: str
    trust_signals: TrustSignals
    company_intelligence: CompanyIntelligenceInfo


class JobOut(BaseModel):
    id: uuid.UUID
    title: str
    location: str | None
    employment_type: str | None
    created_at: datetime
    fraud_probability: float | None = None
    risk_category: str | None = None
    company_name: str | None = None
    source_url: str | None = None

    model_config = {"from_attributes": True}
