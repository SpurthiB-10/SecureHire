import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.models import Company, TrustedCompany, User
from app.services.trust_service import mock_domain_age_days

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/companies")
def list_companies(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    companies = db.query(Company).order_by(Company.trust_score.desc()).all()
    return [
        {
            "id": str(c.id), "name": c.name, "trust_score": float(c.trust_score),
            "posting_count": c.posting_count, "fraud_report_count": c.fraud_report_count,
            "has_verified_domain": c.has_verified_domain,
        }
        for c in companies
    ]


@router.post("/companies/{company_id}/verify")
def verify_company(
    company_id: uuid.UUID,
    note: str | None = None,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")

    existing = db.query(TrustedCompany).filter_by(company_id=company_id).first()
    if not existing:
        db.add(TrustedCompany(company_id=company_id, verified_by=admin.id, verification_note=note))

    company.has_verified_domain = True
    company.domain_age_days = company.domain_age_days or mock_domain_age_days(company.domain or company.name)
    company.trust_score = min(float(company.trust_score) + 25, 100)
    db.commit()
    return {"status": "verified", "company": company.name, "new_trust_score": float(company.trust_score)}


@router.get("/dashboard-summary")
def dashboard_summary(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    from app.models.models import FraudPrediction, JobPosting, Report

    total_jobs = db.query(JobPosting).count()
    high_risk = db.query(FraudPrediction).filter(FraudPrediction.risk_category == "High").count()
    pending_reports = db.query(Report).filter(Report.status == "pending").count()
    total_companies = db.query(Company).count()

    return {
        "total_jobs_analyzed": total_jobs,
        "high_risk_postings": high_risk,
        "pending_reports": pending_reports,
        "total_companies_tracked": total_companies,
    }
