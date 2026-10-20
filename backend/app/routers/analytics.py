import re
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Company, CompanyIntelligence, ExtractedSkill, FraudPrediction, JobPosting, PipelineMetric
from app.schemas.misc import CompanyTrustResponse, FraudTrendsResponse, PipelineHealthResponse
from app.services.cache import cache_get, cache_set

router = APIRouter(prefix="/analytics", tags=["Analytics"])

SCAM_KEYWORDS = [
    "registration fee", "guaranteed", "urgent", "immediate joining",
    "no experience needed", "easy money", "work from home", "processing fee",
    "earn up to", "limited seats",
]


@router.get("/fraud-trends", response_model=FraudTrendsResponse)
def fraud_trends(db: Session = Depends(get_db)):
    """
    Powers the analytics dashboard: fake-vs-real split, fraud by location,
    fraud by category, top scam keywords, model confidence distribution,
    and skill demand trends. Cached for 5 minutes since it aggregates the
    full postings table and doesn't need to be real-time-fresh per request.
    """
    cache_key = "analytics:fraud-trends"
    cached = cache_get(cache_key)
    if cached:
        return cached

    # --- fake vs real ---
    risk_counts = dict(
        db.query(FraudPrediction.risk_category, func.count(FraudPrediction.id))
        .group_by(FraudPrediction.risk_category)
        .all()
    )
    fake_vs_real = {
        "Real (Low Risk)": risk_counts.get("Low", 0),
        "Suspicious (Medium Risk)": risk_counts.get("Medium", 0),
        "Fake (High Risk)": risk_counts.get("High", 0),
    }

    # --- fraud by location (High risk postings grouped by normalized location) ---
    loc_rows = (
        db.query(JobPosting.normalized_location, func.count(JobPosting.id))
        .join(FraudPrediction, FraudPrediction.job_id == JobPosting.id)
        .filter(FraudPrediction.risk_category == "High")
        .group_by(JobPosting.normalized_location)
        .all()
    )
    fraud_by_location = {loc or "Unknown": count for loc, count in loc_rows}

    # --- fraud by employment_type as a proxy for "category" ---
    cat_rows = (
        db.query(JobPosting.employment_type, func.count(JobPosting.id))
        .join(FraudPrediction, FraudPrediction.job_id == JobPosting.id)
        .filter(FraudPrediction.risk_category == "High")
        .group_by(JobPosting.employment_type)
        .all()
    )
    fraud_by_category = {cat or "Unspecified": count for cat, count in cat_rows}

    # --- top scam keywords across High-risk postings ---
    high_risk_texts = (
        db.query(JobPosting.raw_text)
        .join(FraudPrediction, FraudPrediction.job_id == JobPosting.id)
        .filter(FraudPrediction.risk_category == "High")
        .limit(1000)
        .all()
    )
    keyword_counter = Counter()
    for (text,) in high_risk_texts:
        text_l = text.lower()
        for kw in SCAM_KEYWORDS:
            if kw in text_l:
                keyword_counter[kw] += 1
    top_scam_keywords = [{"keyword": k, "count": v} for k, v in keyword_counter.most_common(10)]

    # --- model confidence distribution (bucketed) ---
    confidences = [c for (c,) in db.query(FraudPrediction.confidence).all() if c is not None]
    buckets = {"0-25": 0, "25-50": 0, "50-75": 0, "75-100": 0}
    for c in confidences:
        c = float(c)
        if c < 25:
            buckets["0-25"] += 1
        elif c < 50:
            buckets["25-50"] += 1
        elif c < 75:
            buckets["50-75"] += 1
        else:
            buckets["75-100"] += 1

    # --- skill demand trends: most frequently extracted required skills ---
    skill_rows = (
        db.query(ExtractedSkill.normalized_skill, func.count(ExtractedSkill.id))
        .group_by(ExtractedSkill.normalized_skill)
        .order_by(func.count(ExtractedSkill.id).desc())
        .limit(10)
        .all()
    )
    skill_demand_trends = [{"skill": s, "postings_count": c} for s, c in skill_rows]

    # --- jobs analyzed per day (most recent 30 days with activity) ---
    day_rows = (
        db.query(func.date(JobPosting.created_at), func.count(JobPosting.id))
        .group_by(func.date(JobPosting.created_at))
        .order_by(func.date(JobPosting.created_at).desc())
        .limit(30)
        .all()
    )
    jobs_per_day = [{"date": str(d), "count": c} for d, c in reversed(day_rows)]

    result = FraudTrendsResponse(
        fake_vs_real=fake_vs_real,
        fraud_by_location=fraud_by_location,
        fraud_by_category=fraud_by_category,
        top_scam_keywords=top_scam_keywords,
        model_confidence_distribution=buckets,
        skill_demand_trends=skill_demand_trends,
        jobs_per_day=jobs_per_day,
    ).model_dump()

    cache_set(cache_key, result, ttl=300)
    return result


@router.get("/model-performance")
def model_performance():
    """Surfaces the latest offline evaluation metrics (from ml/train.py's
    metrics.json) for the admin 'Monitor model performance' page."""
    import json
    import os
    from pathlib import Path

    _env_root = os.environ.get("MODELS_ROOT")
    models_root = (
        Path(_env_root) if _env_root
        else Path(__file__).resolve().parent.parent.parent.parent / "models"
    )
    latest_path = models_root / "latest.json"
    if not latest_path.exists():
        return {"status": "no_trained_model", "metrics": {}}

    version = json.loads(latest_path.read_text())["latest_version"]
    metrics_path = models_root / version / "metrics.json"
    if not metrics_path.exists():
        return {"status": "metrics_not_found", "metrics": {}}

    return {"status": "ok", "model_version": version, "metrics": json.loads(metrics_path.read_text())}


@router.get("/companies/top-trusted")
def top_trusted_companies(db: Session = Depends(get_db), limit: int = 10):
    companies = db.query(Company).order_by(Company.trust_score.desc()).limit(limit).all()
    return [
        {"name": c.name, "trust_score": float(c.trust_score), "posting_count": c.posting_count}
        for c in companies
    ]


@router.get("/company-trust", response_model=CompanyTrustResponse)
def company_trust(db: Session = Depends(get_db), limit: int = 10):
    """
    Powers the Company Trust dashboard section: most suspicious and most
    trusted companies by trust_score, recruiter email domain distribution
    (free vs corporate), and Gemini website-verification distribution
    (only reflects companies that have actually had a company_intelligence
    lookup run — postings analyzed without GEMINI_API_KEY configured, or
    seeded demo data, won't appear here since there's nothing to report).
    """
    cache_key = "analytics:company-trust"
    cached = cache_get(cache_key)
    if cached:
        return cached

    suspicious = (
        db.query(Company)
        .filter(Company.posting_count > 0)
        .order_by(Company.trust_score.asc(), Company.fraud_report_count.desc())
        .limit(limit)
        .all()
    )
    top_suspicious_companies = [
        {"name": c.name, "trust_score": float(c.trust_score), "fraud_report_count": c.fraud_report_count}
        for c in suspicious
    ]

    trusted = db.query(Company).order_by(Company.trust_score.desc()).limit(limit).all()
    top_trusted_companies = [
        {"name": c.name, "trust_score": float(c.trust_score), "posting_count": c.posting_count}
        for c in trusted
    ]

    # --- recruiter email domain distribution (free vs corporate-looking) ---
    domain_rows = (
        db.query(JobPosting.contact_email)
        .filter(JobPosting.contact_email.isnot(None))
        .limit(2000)
        .all()
    )
    free_domains = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
                     "rediffmail.com", "aol.com", "protonmail.com", "icloud.com"}
    domain_counter: Counter = Counter()
    for (email,) in domain_rows:
        if email and "@" in email:
            domain = email.split("@")[-1].lower()
            domain_counter["Free email"] += 1 if domain in free_domains else 0
            domain_counter["Corporate domain"] += 0 if domain in free_domains else 1
    recruiter_domain_distribution = [{"category": k, "count": v} for k, v in domain_counter.items()]

    # --- Gemini website-verification distribution ---
    verification_rows = (
        db.query(CompanyIntelligence.website_status, func.count(CompanyIntelligence.id))
        .filter(CompanyIntelligence.status == "ok")
        .group_by(CompanyIntelligence.website_status)
        .all()
    )
    website_verification_distribution = {status or "unknown": count for status, count in verification_rows}

    result = CompanyTrustResponse(
        top_suspicious_companies=top_suspicious_companies,
        top_trusted_companies=top_trusted_companies,
        recruiter_domain_distribution=recruiter_domain_distribution,
        website_verification_distribution=website_verification_distribution,
    ).model_dump()

    cache_set(cache_key, result, ttl=300)
    return result


@router.get("/pipeline-health", response_model=PipelineHealthResponse)
def pipeline_health(db: Session = Depends(get_db), limit: int = 20):
    """
    Powers the Pipeline Health dashboard section — reads from
    `pipeline_metrics`, populated by pipelines/run_pipeline_jobs.py (the
    warehouse ETL pipeline: ingest_jobs -> clean_jobs -> enrich_jobs ->
    build_warehouse). Empty/near-empty until that pipeline has been run
    at least once — see README.md for the command.
    """
    runs = (
        db.query(PipelineMetric)
        .order_by(PipelineMetric.created_at.desc())
        .limit(limit)
        .all()
    )

    def _serialize(r: PipelineMetric) -> dict:
        return {
            "run_id": r.run_id,
            "extraction_mode": r.extraction_mode,
            "since_timestamp": r.since_timestamp.isoformat() if r.since_timestamp else None,
            "rows_ingested": r.rows_ingested,
            "rows_cleaned": r.rows_cleaned,
            "rows_enriched": r.rows_enriched,
            "rows_loaded": r.rows_loaded,
            "duplicates_removed": r.duplicates_removed,
            "fraud_rows_detected": r.fraud_rows_detected,
            "data_quality_passed": r.data_quality_passed,
            "data_quality_issues": r.data_quality_issues,
            "pipeline_duration_seconds": float(r.pipeline_duration_seconds) if r.pipeline_duration_seconds else None,
            "status": r.status,
            "error_message": r.error_message,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }

    recent_runs = [_serialize(r) for r in runs]
    total_runs = db.query(PipelineMetric).count()
    success_count = db.query(PipelineMetric).filter(PipelineMetric.status == "success").count()
    success_rate = round((success_count / total_runs) * 100, 1) if total_runs else 0.0

    return PipelineHealthResponse(
        latest_run=recent_runs[0] if recent_runs else None,
        recent_runs=recent_runs,
        total_runs=total_runs,
        success_rate=success_rate,
    )
