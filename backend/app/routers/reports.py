import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.models import Company, JobPosting, Report, User
from app.schemas.misc import ReportCreate, ReportOut

router = APIRouter(prefix="/reports", tags=["Community Reports"])


@router.post("/create", response_model=ReportOut, status_code=201)
def create_report(payload: ReportCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    job = db.get(JobPosting, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job posting not found")

    report = Report(
        job_id=payload.job_id,
        reported_by=user.id,
        reason=payload.reason,
        evidence_url=payload.evidence_url,
    )
    db.add(report)

    # a user report immediately dents the company's trust score signal
    if job.company_id:
        company = db.get(Company, job.company_id)
        if company:
            company.fraud_report_count += 1

    db.commit()
    db.refresh(report)
    return report


@router.get("/job/{job_id}", response_model=list[ReportOut])
def list_reports_for_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(Report).filter(Report.job_id == job_id).order_by(Report.created_at.desc()).all()


@router.get("/pending", response_model=list[ReportOut])
def list_pending_reports(db: Session = Depends(get_db), _admin: User = Depends(require_admin)):
    """Admin-only: review queue for reported jobs."""
    return db.query(Report).filter(Report.status == "pending").order_by(Report.created_at.desc()).all()


@router.patch("/{report_id}/status", response_model=ReportOut)
def update_report_status(
    report_id: uuid.UUID,
    status: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if status not in ("pending", "reviewed", "dismissed", "confirmed"):
        raise HTTPException(status_code=400, detail="Invalid status value")
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    report.status = status
    db.commit()
    db.refresh(report)
    return report
