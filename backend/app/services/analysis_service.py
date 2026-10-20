"""
analysis_service.py
----------------------
The core "analyze a posting end-to-end" logic: feature engineering + ML
prediction (via ml_service) + Trust Graph scoring + Gemini company
intelligence + persistence to PostgreSQL. Pulled out of the
/jobs/analyze router so it can also be called directly (no HTTP
round-trip) by app.services.seed_service, which auto-populates a freshly
deployed instance with demo data on first boot.

Flow (matches the requested Step A-E structure):
  A. Persist raw job posting
  B. ML fraud analysis (existing calibrated ensemble + SHAP)
  C. Gemini company intelligence (new, additive, fails open)
  D. Persist analytics (FraudPrediction + CompanyIntelligence)
  E. Return a unified response containing both
"""
import hashlib

from sqlalchemy.orm import Session

from app.models.models import (
    Company, CompanyIntelligence, ExtractedSkill, FraudPrediction, JobFeature, JobPosting, User,
)
from app.schemas.jobs import (
    CompanyIntelligenceInfo, JobAnalyzeRequest, JobAnalyzeResponse, SkillInfo, TopFeature, TrustSignals,
)
from app.services.cache import cache_get, cache_set, make_cache_key
from app.services.company_ai_service import get_company_intelligence
from app.services.ml_service import get_predictor
from app.services.trust_service import compute_trust_score

# Company intelligence changes far less often than a fraud score — cache
# it by company name (not job text) with a much longer TTL, both to cut
# Gemini API cost/latency and because "is this company real" doesn't
# meaningfully change between two people analyzing two different postings
# from the same company an hour apart.
COMPANY_INTEL_CACHE_TTL_SECONDS = 24 * 60 * 60


def get_or_create_company(db: Session, name: str | None, website: str | None = None) -> Company | None:
    if not name or not name.strip():
        return None
    normalized = name.strip().lower()
    company = db.query(Company).filter(Company.normalized_name == normalized).first()
    if company is None:
        company = Company(name=name.strip(), normalized_name=normalized, website=website or None)
        db.add(company)
        db.flush()
    else:
        company.posting_count += 1
        # Only ever ADD information we're newly given — never overwrite a
        # known website with None just because this particular request
        # didn't happen to include one.
        if website and not company.website:
            company.website = website
    return company


def _run_company_intelligence(payload: JobAnalyzeRequest) -> tuple[CompanyIntelligenceInfo, bool]:
    """Returns (result, was_cached). Cached by company name so repeated
    postings from the same employer don't re-hit the Gemini API."""
    if not payload.company_name or not payload.company_name.strip():
        result = get_company_intelligence(None)  # -> status="unavailable", no API call
        return CompanyIntelligenceInfo(**result.__dict__), False

    cache_key = make_cache_key("company_intel", payload.company_name.strip().lower())
    cached = cache_get(cache_key)
    if cached:
        return CompanyIntelligenceInfo(**cached), True

    result = get_company_intelligence(
        company_name=payload.company_name,
        company_website=payload.company_website,
        contact_email=payload.contact_email,
        job_description_excerpt=payload.raw_text,
    )
    result_dict = result.__dict__
    # Only cache genuinely successful lookups — never cache "unavailable"/
    # "error" results, so a transient API/key issue doesn't get pinned in
    # the cache for 24h once it's fixed.
    if result.status == "ok":
        cache_set(cache_key, result_dict, ttl=COMPANY_INTEL_CACHE_TTL_SECONDS)
    return CompanyIntelligenceInfo(**result_dict), False


def analyze_and_persist(
    db: Session,
    payload: JobAnalyzeRequest,
    user: User | None = None,
    use_cache: bool = True,
    run_company_intelligence: bool = True,
) -> JobAnalyzeResponse:
    """
    run_company_intelligence: set False to skip the Gemini call entirely
    (used by seed_service.py, which seeds ~40 postings on first boot —
    running 40 real LLM calls at container startup would be slow, costly,
    and doesn't need to succeed for the demo data to be useful).
    """
    cache_key = make_cache_key("job_analysis", payload.title + payload.raw_text)
    cached = cache_get(cache_key) if use_cache else None

    text_hash = hashlib.sha256(
        (payload.title + payload.raw_text).strip().lower().encode("utf-8")
    ).hexdigest()

    # --- Step A: persist raw job (company resolved/created first so we
    # can attach company_id) ---
    company = get_or_create_company(db, payload.company_name, payload.company_website)
    domain = (
        payload.contact_email.split("@")[-1].lower()
        if payload.contact_email and "@" in payload.contact_email else None
    )

    # --- Step B: ML fraud analysis ---
    if cached:
        prediction = cached
        cached_flag = True
    else:
        predictor = get_predictor()
        prediction = predictor.predict(
            title=payload.title,
            text=payload.raw_text,
            contact_email=payload.contact_email,
            salary_min=payload.salary_min,
            salary_max=payload.salary_max,
            # We have no way to verify a company website today — the
            # product has never had a field to collect one. Passing
            # `False` here (as the old code did) silently claimed "we know
            # this posting has no company info" on every single request,
            # which is a fabricated fact, not an observation. `None` is
            # the honest value: genuinely unknown, and the feature
            # extraction/explanation layers now treat unknown as
            # "don't penalize, don't mention" rather than "assume worst".
            # If payload.company_website is ever supplied (e.g. a future
            # integration that has it), we use it — otherwise it stays
            # unknown rather than guessed.
            has_company_website=(
                bool(payload.company_website) if payload.company_website else None
            ),
            location=payload.location,
            company_name=payload.company_name,
        )
        if use_cache:
            cache_set(cache_key, prediction)
        cached_flag = False

    trust = compute_trust_score(db, company, domain)

    # --- Step C: Gemini company intelligence (additive, fails open) ---
    if run_company_intelligence:
        company_intel, intel_cached = _run_company_intelligence(payload)
    else:
        company_intel = CompanyIntelligenceInfo(
            status="unavailable",
            company_summary="Company intelligence skipped for this request.",
        )
        intel_cached = False

    job = JobPosting(
        submitted_by=user.id if user else None,
        company_id=company.id if company else None,
        title=payload.title,
        raw_text=payload.raw_text,
        location=payload.location,
        normalized_location=(payload.location or "Unknown").title(),
        employment_type=getattr(payload, "employment_type", None),
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        contact_email=payload.contact_email,
        source=getattr(payload, "source", None) or "user_upload",
        source_url=payload.source_url,
        text_hash=text_hash,
    )
    db.add(job)
    db.flush()

    # --- Step D: persist analytics ---
    db.add(FraudPrediction(
        job_id=job.id,
        model_version=prediction["model_version"],
        fraud_probability=prediction["fraud_probability"],
        risk_category=prediction["risk_category"],
        top_features=prediction["top_features"],
        confidence=prediction["confidence"],
        explanation_text=prediction["explanation_text"],
    ))

    for s in prediction["skills"]:
        db.add(ExtractedSkill(
            job_id=job.id,
            skill_name=s["skill_name"],
            normalized_skill=s["skill_name"].lower(),
            is_required=s["is_required"],
            demand_level=s["demand_level"],
        ))

    # Persist the full raw (unscaled) feature snapshot — was computed on
    # every request already, just never written anywhere before. Useful
    # for debugging a specific prediction later and as a labeled dataset
    # for future model retraining, without needing to re-run feature
    # extraction against the raw_text again.
    raw_features = prediction.get("raw_features")
    if raw_features:
        db.add(JobFeature(
            job_id=job.id,
            has_free_email_domain=bool(raw_features.get("has_free_email_domain")),
            salary_is_suspicious=bool(raw_features.get("salary_is_suspicious")),
            urgent_language_score=raw_features.get("urgent_language_score"),
            company_name_missing=bool(raw_features.get("company_name_missing")),
            experience_mismatch_score=raw_features.get("experience_mismatch_score"),
            promo_phrase_count=raw_features.get("promo_phrase_count"),
            skill_role_mismatch_score=raw_features.get("skill_role_mismatch_score"),
            location_inconsistency=bool(raw_features.get("location_inconsistency")),
            description_length=raw_features.get("description_length"),
            exclamation_count=raw_features.get("exclamation_count"),
            salary_spread_ratio=raw_features.get("salary_spread_ratio"),
            has_registration_fee_mention=bool(raw_features.get("has_registration_fee_mention")),
            requests_informal_contact=bool(raw_features.get("requests_informal_contact")),
        ))

    # Only persist a fresh CompanyIntelligence row if this wasn't served
    # from the 24h cache — no need to write a near-identical row to the DB
    # every time the same company is looked up again within a day.
    if company_intel.status == "ok" and not intel_cached:
        db.add(CompanyIntelligence(
            job_id=job.id,
            company_summary=company_intel.company_summary,
            industry=company_intel.industry,
            headquarters=company_intel.headquarters,
            website_status=company_intel.website_status,
            online_presence=company_intel.online_presence,
            recruiter_email_status=company_intel.recruiter_email_status,
            verification_score=company_intel.verification_score,
            key_findings=company_intel.key_findings,
            evidence=company_intel.evidence,
            recommendation=company_intel.recommendation,
            llm_provider=company_intel.llm_provider,
            llm_model=company_intel.llm_model,
            status=company_intel.status,
        ))

    db.commit()

    # --- trusted alternatives: companies with strong trust scores ---
    alternatives = (
        db.query(Company)
        .filter(Company.trust_score >= 70)
        .order_by(Company.trust_score.desc())
        .limit(3)
        .all()
    )

    # --- Step E: unified response ---
    return JobAnalyzeResponse(
        job_id=job.id,
        fraud_probability=prediction["fraud_probability"],
        risk_category=prediction["risk_category"],
        confidence=prediction["confidence"],
        model_version=prediction["model_version"],
        top_features=[TopFeature(**f) for f in prediction["top_features"]],
        explanation_text=prediction["explanation_text"],
        skills=[SkillInfo(**s) for s in prediction["skills"]],
        trust_signals=TrustSignals(**trust),
        similar_trusted_alternatives=[c.name for c in alternatives],
        cached=cached_flag,
        company_intelligence=company_intel,
        source_url=payload.source_url,
    )
