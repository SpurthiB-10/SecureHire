"""
API-level tests for the FastAPI backend. Requires a running PostgreSQL +
Redis instance reachable via the DATABASE_URL / REDIS_URL env vars (or the
defaults, which assume `docker compose up` or a local Postgres/Redis).

Run with:
    cd backend && pytest ../tests/test_api.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import pytest
from fastapi.testclient import TestClient

from app.main import app

GOOGLE_PM_JD = (
    "Minimum qualifications: Bachelor's degree or equivalent practical experience. "
    "8 years of experience in product management or a related technical role. "
    "Experience working with engineering teams on platform and tooling initiatives. "
    "Preferred qualifications: Master's degree in a technical field. Experience with "
    "AI/ML platforms and operational tooling. Excellent program management and "
    "cross-functional leadership skills. About the job: The AI Platform Operations "
    "and Tooling team builds the internal tools and processes that power Google's AI "
    "infrastructure. As a Product Manager on this team, you will define the roadmap "
    "for internal tooling, partner with engineering leads across the organization, "
    "and drive operational excellence across our AI platform investments. "
    "Responsibilities: Define and drive the product roadmap for AI platform tooling. "
    "Partner with engineering, data science, and operations stakeholders. Own key "
    "metrics for platform reliability and developer productivity. Communicate "
    "progress and priorities to senior leadership. Google is proud to be an equal "
    "opportunity workplace."
)

MARKETING_JD = (
    "We are seeking an experienced Marketing Manager to lead our brand campaigns. "
    "Responsibilities include developing integrated marketing campaigns, managing "
    "budget, and collaborating with sales on go-to-market strategy. Requirements: "
    "5+ years of marketing experience, strong understanding of SEO, content "
    "strategy, and Google Analytics. Full-time, hybrid role with competitive "
    "salary and benefits."
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


def test_register_and_login_flow(client):
    email = "pytest_user@example.com"
    r = client.post("/api/v1/auth/register", json={
        "email": email, "password": "testpass123", "full_name": "Pytest User",
    })
    # allow re-runs against a non-fresh DB
    assert r.status_code in (201, 400)

    r = client.post("/api/v1/auth/login", json={"email": email, "password": "testpass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_analyze_obvious_fake_job_is_high_risk(client):
    payload = {
        "title": "Data Entry Intern",
        "raw_text": (
            "Immediate joining required!!! Earn up to Rs 90,000 per week working from home! "
            "No experience needed, guaranteed placement! Send registration fee to confirm your seat."
        ),
        "contact_email": "hr.hiring123@gmail.com",
        "company_name": "Quick Earn Solutions",
    }
    r = client.post("/api/v1/jobs/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert 0 <= body["fraud_probability"] <= 100
    assert body["risk_category"] in ("Low", "Medium", "High")
    assert body["risk_category"] == "High"


def test_analyze_google_pm_job_is_low_risk_with_no_fabricated_reasons(client):
    """Direct regression test for the reported bug: a real, detailed Google
    Product Manager posting was scored ~41% Medium risk with explanations
    mentioning a registration fee, urgent language, and a technical-skill
    mismatch — none of which were in the text."""
    payload = {
        "title": "Product Manager, AI Platform Operations and Tooling",
        "raw_text": GOOGLE_PM_JD,
        "company_name": "Google",
    }
    r = client.post("/api/v1/jobs/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()

    assert body["risk_category"] == "Low", (
        f"Expected Low risk, got {body['risk_category']} ({body['fraud_probability']}%). "
        f"Explanation: {body['explanation_text']}"
    )

    shown_risk_features = {f["feature"] for f in body["top_features"] if f["direction"] == "increases_risk"}
    assert "has_registration_fee_mention" not in shown_risk_features
    assert "urgent_language_score" not in shown_risk_features
    assert "company_name_missing" not in shown_risk_features
    assert "skill_role_mismatch_score" not in shown_risk_features

    explanation_lower = body["explanation_text"].lower()
    for forbidden in ["registration", "processing fee", "urgent-hiring", "whatsapp"]:
        assert forbidden not in explanation_lower


def test_analyze_marketing_job_not_penalized_for_missing_tech_skills(client):
    payload = {
        "title": "Marketing Manager",
        "raw_text": MARKETING_JD,
        "company_name": "Acme Corp",
    }
    r = client.post("/api/v1/jobs/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    shown_risk_features = {f["feature"] for f in body["top_features"] if f["direction"] == "increases_risk"}
    assert "skill_role_mismatch_score" not in shown_risk_features
    assert body["risk_category"] == "Low"


def test_analyze_job_missing_optional_fields_stays_unknown_not_penalized(client):
    """No salary, no website, no email supplied — none of these should be
    treated as fraud signals."""
    payload = {
        "title": "Operations Manager",
        "raw_text": MARKETING_JD,
        "company_name": "Acme Corp",
    }
    r = client.post("/api/v1/jobs/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    shown_risk_features = {f["feature"] for f in body["top_features"] if f["direction"] == "increases_risk"}
    assert "salary_is_suspicious" not in shown_risk_features
    assert "has_free_email_domain" not in shown_risk_features


def test_analyze_job_rejects_too_short_text(client):
    r = client.post("/api/v1/jobs/analyze", json={"title": "X", "raw_text": "too short"})
    assert r.status_code == 422


def test_analyze_job_accepts_optional_company_website_field(client):
    """Additive schema field — must not break existing callers that omit it."""
    payload = {
        "title": "Software Engineer",
        "raw_text": "We need a Software Engineer with Python, SQL, AWS, and Docker experience.",
        "company_name": "Acme Corp",
        "company_website": "https://acme.example.com",
    }
    r = client.post("/api/v1/jobs/analyze", json=payload)
    assert r.status_code == 200


def test_analyze_job_response_includes_company_intelligence_field(client):
    """New additive field — always present, even without a configured
    GEMINI_API_KEY (fails open to status='unavailable' rather than
    breaking the response or omitting the field)."""
    payload = {
        "title": "Software Engineer",
        "raw_text": "We need a Software Engineer with Python, SQL, AWS, and Docker experience.",
        "company_name": "Acme Corp",
    }
    r = client.post("/api/v1/jobs/analyze", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "company_intelligence" in body
    assert body["company_intelligence"]["status"] in ("ok", "unavailable", "error")


def test_skills_extract_endpoint(client):
    r = client.post("/api/v1/skills/extract", json={"text": "Looking for Python, SQL, and Docker skills."})
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert "python" in skills


def test_skills_extract_endpoint_non_technical(client):
    r = client.post("/api/v1/skills/extract", json={"text": "Looking for SEO and content strategy skills."})
    assert r.status_code == 200
    skills = r.json()["skills"]
    assert "seo" in skills
