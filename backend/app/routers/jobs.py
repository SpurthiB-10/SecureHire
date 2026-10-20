import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.models import CompanyIntelligence, ExtractedSkill, FraudPrediction, JobPosting, User, UserSavedJob
from app.schemas.jobs import (
    CompanyIntelligenceInfo, JobAnalyzeRequest, JobAnalyzeResponse,
    JobFullAnalysisResponse, JobOut, SkillInfo, TopFeature, TrustSignals,
)
from app.services.analysis_service import analyze_and_persist
from app.services.trust_service import compute_trust_score

router = APIRouter(prefix="/jobs", tags=["Jobs"])


@router.post("/analyze", response_model=JobAnalyzeResponse)
def analyze_job(
    payload: JobAnalyzeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Authenticated core feature: paste a job description and get a fraud score + explanation."""
    return analyze_and_persist(db, payload, user)


@router.post("/upload", response_model=JobAnalyzeResponse)
async def upload_job(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Accepts a .txt job posting file upload and runs the same analysis pipeline."""
    if file.content_type not in ("text/plain", "application/octet-stream") and not file.filename.endswith(".txt"):
        raise HTTPException(status_code=400, detail="Only .txt job posting files are supported in this endpoint")

    content = (await file.read()).decode("utf-8", errors="ignore")
    if len(content.strip()) < 30:
        raise HTTPException(status_code=400, detail="Uploaded file content is too short to analyze")

    title = content.strip().splitlines()[0][:255] or "Uploaded Job Posting"
    payload = JobAnalyzeRequest(title=title, raw_text=content)
    return analyze_and_persist(db, payload, user)


@router.get("/trusted", response_model=list[JobOut])
def trusted_jobs_feed(db: Session = Depends(get_db), user: User = Depends(get_current_user), limit: int = 10):
    """Feed of postings whose latest prediction is Low risk, newest first."""
    jobs = (
        db.query(JobPosting)
        .join(FraudPrediction, FraudPrediction.job_id == JobPosting.id)
        .filter(FraudPrediction.risk_category == "Low")
        .order_by(JobPosting.created_at.desc())
        .limit(min(limit, 10))
        .all()
    )
    results = []
    for job in jobs:
        latest_pred = max(job.predictions, key=lambda p: p.predicted_at, default=None)
        results.append(JobOut(
            id=job.id, title=job.title, location=job.location,
            employment_type=job.employment_type, created_at=job.created_at,
            fraud_probability=float(latest_pred.fraud_probability) if latest_pred else None,
            risk_category=latest_pred.risk_category if latest_pred else None,
            company_name=job.company.name if job.company else None,
            source_url=job.source_url,
        ))
    return results


@router.get("/mine", response_model=list[JobOut])
def my_analyzed_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user), limit: int = 100):
    """
    All postings the current user has ever analyzed (via submitted_by),
    newest first — this is the "My Analyses" history, distinct from
    /jobs/saved/me which only returns postings explicitly bookmarked via
    the Save button. Placed BEFORE /jobs/{job_id} below: both are
    2-segment paths ("/jobs/mine" vs "/jobs/{job_id}"), so declaration
    order matters — Starlette would otherwise try to parse "mine" as a
    job_id UUID and 422 before this handler is ever reached.
    """
    jobs = (
        db.query(JobPosting)
        .filter(JobPosting.submitted_by == user.id)
        .order_by(JobPosting.created_at.desc())
        .limit(limit)
        .all()
    )
    results = []
    for job in jobs:
        latest_pred = max(job.predictions, key=lambda p: p.predicted_at, default=None)
        results.append(JobOut(
            id=job.id, title=job.title, location=job.location,
            employment_type=job.employment_type, created_at=job.created_at,
            fraud_probability=float(latest_pred.fraud_probability) if latest_pred else None,
            risk_category=latest_pred.risk_category if latest_pred else None,
            company_name=job.company.name if job.company else None,
            source_url=job.source_url,
        ))
    return results


@router.get("/{job_id}/analysis", response_model=JobFullAnalysisResponse)
def get_full_analysis(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """
    Full analysis detail for the /analysis/:jobId page — reconstructed
    from already-persisted data, not a fresh model run (so revisiting a
    past analysis is instant and doesn't re-invoke the ML model or
    Gemini). 3-segment path, so no ordering conflict with /jobs/{job_id}
    or /jobs/mine above.
    """
    job = db.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    if job.submitted_by != user.id:
        raise HTTPException(status_code=403, detail="You can only view analyses from your own account")

    latest_pred = max(job.predictions, key=lambda p: p.predicted_at, default=None)
    if not latest_pred:
        raise HTTPException(status_code=404, detail="This job posting has not been analyzed yet")

    skills = db.query(ExtractedSkill).filter(ExtractedSkill.job_id == job.id).all()
    skills_out = [
        SkillInfo(skill_name=s.skill_name, is_required=s.is_required, demand_level=s.demand_level or "Medium")
        for s in skills
    ]

    domain = job.contact_email.split("@")[-1].lower() if job.contact_email and "@" in job.contact_email else None
    trust = compute_trust_score(db, job.company, domain)

    latest_intel = (
        db.query(CompanyIntelligence)
        .filter(CompanyIntelligence.job_id == job.id)
        .order_by(CompanyIntelligence.generated_at.desc())
        .first()
    )
    if latest_intel:
        company_intel = CompanyIntelligenceInfo(
            status=latest_intel.status,
            company_summary=latest_intel.company_summary,
            industry=latest_intel.industry,
            headquarters=latest_intel.headquarters,
            website_status=latest_intel.website_status or "unknown",
            online_presence=latest_intel.online_presence or "unknown",
            recruiter_email_status=latest_intel.recruiter_email_status or "unknown",
            verification_score=float(latest_intel.verification_score) if latest_intel.verification_score is not None else None,
            key_findings=latest_intel.key_findings or [],
            evidence=latest_intel.evidence or [],
            recommendation=latest_intel.recommendation,
            llm_provider=latest_intel.llm_provider,
            llm_model=latest_intel.llm_model,
        )
    else:
        # No successful Gemini lookup was ever persisted for this job
        # (company_intelligence rows are only written on status="ok" —
        # see analysis_service.py). Genuinely unknown, not an error.
        company_intel = CompanyIntelligenceInfo(
            status="unavailable",
            company_summary="Company intelligence was not available when this job was analyzed.",
            recommendation="Verify this company independently before proceeding.",
            error_message="No company intelligence result is on record for this posting.",
        )

    return JobFullAnalysisResponse(
        job_id=job.id,
        title=job.title,
        company_name=job.company.name if job.company else None,
        location=job.location,
        employment_type=job.employment_type,
        source_url=job.source_url,
        created_at=job.created_at,
        fraud_probability=float(latest_pred.fraud_probability),
        risk_category=latest_pred.risk_category,
        confidence=float(latest_pred.confidence) if latest_pred.confidence is not None else 0.0,
        model_version=latest_pred.model_version,
        top_features=[TopFeature(**f) for f in (latest_pred.top_features or [])],
        explanation_text=latest_pred.explanation_text or "",
        skills=skills_out,
        trust_signals=TrustSignals(**trust),
        company_intelligence=company_intel,
    )


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    latest_pred = max(job.predictions, key=lambda p: p.predicted_at, default=None)
    return JobOut(
        id=job.id, title=job.title, location=job.location,
        employment_type=job.employment_type, created_at=job.created_at,
        fraud_probability=float(latest_pred.fraud_probability) if latest_pred else None,
        risk_category=latest_pred.risk_category if latest_pred else None,
        company_name=job.company.name if job.company else None,
        source_url=job.source_url,
    )


@router.post("/{job_id}/save", status_code=204)
def save_job(job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(JobPosting, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")
    exists = db.query(UserSavedJob).filter_by(user_id=user.id, job_id=job_id).first()
    if not exists:
        db.add(UserSavedJob(user_id=user.id, job_id=job_id))
        db.commit()


@router.get("/saved/me", response_model=list[JobOut])
def my_saved_jobs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    saved = db.query(UserSavedJob).filter_by(user_id=user.id).all()
    results = []
    for s in saved:
        job = db.get(JobPosting, s.job_id)
        latest_pred = max(job.predictions, key=lambda p: p.predicted_at, default=None)
        results.append(JobOut(
            id=job.id, title=job.title, location=job.location,
            employment_type=job.employment_type, created_at=job.created_at,
            fraud_probability=float(latest_pred.fraud_probability) if latest_pred else None,
            risk_category=latest_pred.risk_category if latest_pred else None,
            company_name=job.company.name if job.company else None,
            source_url=job.source_url,
        ))
    return results
