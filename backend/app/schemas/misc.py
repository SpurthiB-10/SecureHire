import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReportCreate(BaseModel):
    job_id: uuid.UUID
    reason: str = Field(max_length=120)
    evidence_url: str | None = None


class ReportOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    reason: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SkillExtractRequest(BaseModel):
    text: str = Field(min_length=10)


class SkillExtractResponse(BaseModel):
    skills: list[str]


class FraudTrendsResponse(BaseModel):
    fake_vs_real: dict[str, int]
    fraud_by_location: dict[str, int]
    fraud_by_category: dict[str, int]
    top_scam_keywords: list[dict[str, int | str]]
    model_confidence_distribution: dict[str, int]
    skill_demand_trends: list[dict[str, int | str]]
    # Additive: jobs analyzed per day, most recent 30 days with activity.
    jobs_per_day: list[dict[str, str | int]] = []


class CompanyTrustResponse(BaseModel):
    top_suspicious_companies: list[dict]
    top_trusted_companies: list[dict]
    recruiter_domain_distribution: list[dict]
    website_verification_distribution: dict[str, int]


class PipelineHealthResponse(BaseModel):
    latest_run: dict | None
    recent_runs: list[dict]
    total_runs: int
    success_rate: float


class ChatRequest(BaseModel):
    message: str
    job_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    reply: str
