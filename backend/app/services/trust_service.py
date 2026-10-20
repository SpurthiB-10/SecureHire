"""
trust_service.py
------------------
Computes a 0-100 "Trust Score" for a company based on a weighted blend of
signals — the "Trust Graph" feature. Domain-age lookup is mocked (a real
deployment would call a WHOIS API); everything else is derived from data
already in our own database (posting history, user reports, verification
status), which is what makes this genuinely ours rather than a wrapper
around a third-party fraud API.
"""
import random

from sqlalchemy.orm import Session

from app.models.models import Company, TrustedCompany


def mock_domain_age_days(domain: str | None) -> int | None:
    """
    Stand-in for a WHOIS API call. Deterministic per-domain via hashing so
    repeated lookups for the same domain are stable within a demo/session,
    without requiring network access or an API key.
    """
    if not domain:
        return None
    seed = sum(ord(c) for c in domain)
    rng = random.Random(seed)
    # known big companies "feel" older; unknown/free-looking domains skew younger
    if any(known in domain for known in ["google", "microsoft", "amazon", "infosys", "tcs", "wipro"]):
        return rng.randint(3000, 9000)
    return rng.randint(5, 900)


def compute_trust_score(
    db: Session,
    company: Company | None,
    domain: str | None,
) -> dict:
    if company is None:
        # unknown / first-seen company — start neutral-low, everything else unknown
        domain_age = mock_domain_age_days(domain)
        score = 35.0
        if domain_age and domain_age > 1000:
            score += 15
        return {
            "domain_age_days": domain_age,
            "has_verified_domain": False,
            "posting_count": 0,
            "fraud_report_count": 0,
            "trust_score": round(min(max(score, 0), 100), 2),
        }

    is_verified = (
        db.query(TrustedCompany).filter(TrustedCompany.company_id == company.id).first()
        is not None
    )

    score = 50.0
    score += 20 if is_verified else 0
    score += min(company.posting_count, 20) * 0.5      # consistent posting history builds trust
    score -= min(company.fraud_report_count, 20) * 3     # user reports strongly hurt trust
    score += 10 if company.has_verified_domain else 0
    if company.domain_age_days:
        score += 10 if company.domain_age_days > 1000 else -5

    score = round(min(max(score, 0), 100), 2)

    return {
        "domain_age_days": company.domain_age_days,
        "has_verified_domain": company.has_verified_domain,
        "posting_count": company.posting_count,
        "fraud_report_count": company.fraud_report_count,
        "trust_score": score,
    }
