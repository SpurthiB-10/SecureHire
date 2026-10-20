"""
SQLAlchemy ORM models mirroring docs/schema.sql.
Kept in a single module for readability at this project's scale.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, ForeignKey, Integer, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def gen_uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    saved_jobs = relationship("UserSavedJob", back_populates="user")


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    website: Mapped[str | None] = mapped_column(String(512))
    domain: Mapped[str | None] = mapped_column(String(255))
    domain_age_days: Mapped[int | None] = mapped_column(Integer)
    industry: Mapped[str | None] = mapped_column(String(120))
    hq_location: Mapped[str | None] = mapped_column(String(255))
    has_verified_domain: Mapped[bool] = mapped_column(Boolean, default=False)
    trust_score: Mapped[float] = mapped_column(Numeric(5, 2), default=50.00)
    posting_count: Mapped[int] = mapped_column(Integer, default=0)
    fraud_report_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    postings = relationship("JobPosting", back_populates="company")


class JobPosting(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    normalized_location: Mapped[str | None] = mapped_column(String(255))
    employment_type: Mapped[str | None] = mapped_column(String(50))
    salary_min: Mapped[float | None] = mapped_column(Numeric(12, 2))
    salary_max: Mapped[float | None] = mapped_column(Numeric(12, 2))
    salary_currency: Mapped[str] = mapped_column(String(10), default="INR")
    contact_email: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(String(120))
    source_url: Mapped[str | None] = mapped_column(String(512))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duplicate_of: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("job_postings.id"))
    text_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    company = relationship("Company", back_populates="postings")
    features = relationship("JobFeature", back_populates="job", uselist=False)
    predictions = relationship("FraudPrediction", back_populates="job")
    skills = relationship("ExtractedSkill", back_populates="job")
    reports = relationship("Report", back_populates="job")


class JobFeature(Base):
    """
    The full raw (unscaled) red-flag feature snapshot for a single
    prediction — written by analysis_service.py on every /jobs/analyze
    call. Columns are kept 1:1 with feature_engineering.py's
    RedFlagFeatures dataclass; if that dataclass's fields ever change,
    update both together (and re-verify with tests/test_feature_engineering.py).
    Useful for auditing a specific past prediction and as a ready-made
    labeled feature set for future model retraining, without needing to
    re-run feature extraction against raw_text again.
    """
    __tablename__ = "job_features"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_postings.id"), unique=True)
    has_free_email_domain: Mapped[bool | None] = mapped_column(Boolean)
    salary_is_suspicious: Mapped[bool | None] = mapped_column(Boolean)
    urgent_language_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    company_name_missing: Mapped[bool | None] = mapped_column(Boolean)
    experience_mismatch_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    promo_phrase_count: Mapped[int | None] = mapped_column(Integer)
    skill_role_mismatch_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    location_inconsistency: Mapped[bool | None] = mapped_column(Boolean)
    description_length: Mapped[int | None] = mapped_column(Integer)
    exclamation_count: Mapped[int | None] = mapped_column(Integer)
    salary_spread_ratio: Mapped[float | None] = mapped_column(Numeric(10, 2))
    has_registration_fee_mention: Mapped[bool | None] = mapped_column(Boolean)
    requests_informal_contact: Mapped[bool | None] = mapped_column(Boolean)
    tfidf_vector_ref: Mapped[str | None] = mapped_column(String(255))
    embedding_ref: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    job = relationship("JobPosting", back_populates="features")


class FraudPrediction(Base):
    __tablename__ = "fraud_predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_postings.id"))
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    fraud_probability: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    risk_category: Mapped[str] = mapped_column(String(10), nullable=False)
    top_features: Mapped[dict | None] = mapped_column(JSONB)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 2))
    explanation_text: Mapped[str | None] = mapped_column(Text)
    predicted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    job = relationship("JobPosting", back_populates="predictions")


class ExtractedSkill(Base):
    __tablename__ = "extracted_skills"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_postings.id"))
    skill_name: Mapped[str] = mapped_column(String(120), nullable=False)
    normalized_skill: Mapped[str] = mapped_column(String(120), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    demand_level: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    job = relationship("JobPosting", back_populates="skills")


class UserSkill(Base):
    __tablename__ = "user_skills"
    __table_args__ = (UniqueConstraint("user_id", "skill_name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    skill_name: Mapped[str] = mapped_column(String(120), nullable=False)
    proficiency: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_postings.id"))
    reported_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    job = relationship("JobPosting", back_populates="reports")


class TrustedCompany(Base):
    __tablename__ = "trusted_companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id"), unique=True)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    verification_note: Mapped[str | None] = mapped_column(String(512))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class UserSavedJob(Base):
    __tablename__ = "user_saved_jobs"
    __table_args__ = (UniqueConstraint("user_id", "job_id"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_postings.id"))
    saved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    user = relationship("User", back_populates="saved_jobs")


# ---------------------------------------------------------------------
# Warehouse / Data Engineering layer additions. See docs/schema.sql for
# the architectural note on why there's no separate "job_postings" or
# "fraud_analysis" warehouse table here — job_postings and
# fraud_predictions above already are the source-of-record tables;
# v_warehouse_job_fact (a SQL view, not an ORM model) is the flat,
# denormalized join used by the analytics dashboard.
# ---------------------------------------------------------------------

class CompanyIntelligence(Base):
    """Gemini-generated company verification results for a posting. See
    backend/app/services/company_ai_service.py for how this is populated."""
    __tablename__ = "company_intelligence"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("job_postings.id"))
    company_summary: Mapped[str | None] = mapped_column(Text)
    industry: Mapped[str | None] = mapped_column(String(120))
    headquarters: Mapped[str | None] = mapped_column(String(255))
    website_status: Mapped[str | None] = mapped_column(String(30))
    online_presence: Mapped[str | None] = mapped_column(String(30))
    recruiter_email_status: Mapped[str | None] = mapped_column(String(30))
    verification_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    key_findings: Mapped[list | None] = mapped_column(JSONB)
    evidence: Mapped[list | None] = mapped_column(JSONB)
    recommendation: Mapped[str | None] = mapped_column(Text)
    llm_provider: Mapped[str] = mapped_column(String(50), default="gemini")
    llm_model: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="ok")  # 'ok' | 'unavailable' | 'error'
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PipelineMetric(Base):
    """One row per ETL pipeline run (ingest_jobs -> clean_jobs ->
    enrich_jobs -> build_warehouse), written by pipelines/run_pipeline_jobs.py.
    Powers the Pipeline Health dashboard and doubles as a reproducibility
    record of every warehouse-build run. Supports both full-refresh and
    incremental (--since) runs — see extraction_mode/since_timestamp."""
    __tablename__ = "pipeline_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=gen_uuid)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    extraction_mode: Mapped[str] = mapped_column(String(20), default="full")  # 'full' | 'incremental'
    since_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rows_ingested: Mapped[int] = mapped_column(Integer, default=0)
    rows_cleaned: Mapped[int] = mapped_column(Integer, default=0)
    rows_enriched: Mapped[int] = mapped_column(Integer, default=0)
    rows_loaded: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_removed: Mapped[int] = mapped_column(Integer, default=0)
    fraud_rows_detected: Mapped[int] = mapped_column(Integer, default=0)
    data_quality_passed: Mapped[bool | None] = mapped_column(Boolean)
    data_quality_issues: Mapped[list | None] = mapped_column(JSONB)
    pipeline_duration_seconds: Mapped[float | None] = mapped_column(Numeric(10, 3))
    status: Mapped[str] = mapped_column(String(20), default="success")  # 'success' | 'failed'
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
