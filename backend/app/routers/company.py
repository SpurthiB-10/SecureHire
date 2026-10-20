"""
company.py — standalone company verification endpoint.

Deliberately separate from /jobs/analyze: checking a company shouldn't
require fabricating a fake job description just to satisfy
JobAnalyzeRequest's min-length validation. This wires together three
services that already exist and are already used elsewhere in the app —
get_or_create_company (analysis_service.py), compute_trust_score
(trust_service.py), and get_company_intelligence (company_ai_service.py)
— no new ML/DE logic, no schema changes.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.jobs import CompanyCheckRequest, CompanyCheckResponse, CompanyIntelligenceInfo, TrustSignals
from app.services.analysis_service import get_or_create_company
from app.services.company_ai_service import get_company_intelligence
from app.services.trust_service import compute_trust_score

router = APIRouter(prefix="/company", tags=["Company Check"])


@router.post("/check", response_model=CompanyCheckResponse)
def check_company(payload: CompanyCheckRequest, db: Session = Depends(get_db)):
    company = get_or_create_company(db, payload.company_name, payload.company_website)
    db.commit()

    domain = None
    if payload.company_website:
        domain = payload.company_website.replace("https://", "").replace("http://", "").split("/")[0].lower()
    trust = compute_trust_score(db, company, domain)

    intel_result = get_company_intelligence(
        company_name=payload.company_name,
        company_website=payload.company_website,
    )

    return CompanyCheckResponse(
        company_name=payload.company_name,
        trust_signals=TrustSignals(**trust),
        company_intelligence=CompanyIntelligenceInfo(**intel_result.__dict__),
    )
