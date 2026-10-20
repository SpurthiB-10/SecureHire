from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.deps import get_current_user
from app.db.session import get_db
from app.ml_core.feature_engineering import SKILL_DEMAND, extract_skills
from app.models.models import ExtractedSkill, JobPosting, User, UserSkill
from app.schemas.misc import SkillExtractRequest, SkillExtractResponse

router = APIRouter(prefix="/skills", tags=["Skill Intelligence"])

# Minimal mock learning-resource map for the Skill Intelligence Engine.
LEARNING_RESOURCES = {
    "python": "https://docs.python.org/3/tutorial/",
    "sql": "https://mode.com/sql-tutorial/",
    "airflow": "https://airflow.apache.org/docs/apache-airflow/stable/tutorial/",
    "aws": "https://aws.amazon.com/training/",
    "docker": "https://docs.docker.com/get-started/",
    "spark": "https://spark.apache.org/docs/latest/quick-start.html",
    "kubernetes": "https://kubernetes.io/docs/tutorials/",
    "machine learning": "https://www.coursera.org/learn/machine-learning",
    "nlp": "https://www.nltk.org/book/",
    "etl": "https://www.databricks.com/glossary/extract-transform-load",
}


@router.post("/extract", response_model=SkillExtractResponse)
def extract(payload: SkillExtractRequest):
    """Extracts technical skills mentioned in an arbitrary text (job posting,
    resume, etc.) using the shared skill vocabulary/NLP matcher."""
    return SkillExtractResponse(skills=extract_skills(payload.text))


@router.get("/job-fit/{job_id}")
def job_fit(job_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Compares a job posting's required skills against the logged-in
    user's tracked skill profile to compute a fit percentage + gaps."""
    from app.models.models import ExtractedSkill  # local import avoids circulars

    required = db.query(ExtractedSkill).filter(ExtractedSkill.job_id == job_id).all()
    user_skills = {s.skill_name.lower() for s in db.query(UserSkill).filter(UserSkill.user_id == user.id).all()}

    matched, missing = [], []
    for r in required:
        if r.normalized_skill in user_skills:
            matched.append(r.skill_name)
        else:
            missing.append({
                "skill_name": r.skill_name,
                "demand_level": r.demand_level,
                "learning_resource": LEARNING_RESOURCES.get(r.normalized_skill),
            })

    total = len(required) or 1
    fit_percentage = round(len(matched) / total * 100, 1)

    return {
        "job_id": job_id,
        "fit_percentage": fit_percentage,
        "matched_skills": matched,
        "missing_skills": missing,
    }


@router.get("/mine")
def my_skills(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return [
        {"skill_name": s.skill_name, "proficiency": s.proficiency, "created_at": s.created_at}
        for s in db.query(UserSkill).filter(UserSkill.user_id == user.id).order_by(UserSkill.skill_name.asc()).all()
    ]


@router.post("/track")
def track_skill(skill_name: str, proficiency: str = "Intermediate", db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Adds/updates a skill in the user's personal Skill Tracker."""
    existing = db.query(UserSkill).filter_by(user_id=user.id, skill_name=skill_name.lower()).first()
    if existing:
        existing.proficiency = proficiency
    else:
        db.add(UserSkill(user_id=user.id, skill_name=skill_name.lower(), proficiency=proficiency))
    db.commit()
    return {"status": "ok", "skill_name": skill_name, "proficiency": proficiency}


@router.get("/demand")
def skill_demand_levels(db: Session = Depends(get_db)):
    """Returns demand tiers plus observed job counts from analyzed postings."""
    rows = (
        db.query(ExtractedSkill.normalized_skill, func.count(func.distinct(ExtractedSkill.job_id)))
        .join(JobPosting, JobPosting.id == ExtractedSkill.job_id)
        .group_by(ExtractedSkill.normalized_skill)
        .all()
    )
    observed = {name: int(count) for name, count in rows}
    return [
        {
            "skill_name": name.title(),
            "normalized_skill": name,
            "demand_level": level,
            "jobs_count": observed.get(name, 0),
        }
        for name, level in SKILL_DEMAND.items()
    ]
