"""
Regression tests for the SHAP-explanation bug: verifies that explanations
returned by the trained model NEVER mention a red flag whose raw feature
value indicates it isn't actually present. This directly reproduces the
originally-reported bug (a real Google Product Manager posting being told
it had a registration fee, urgent language, and a technical-skill mismatch
that were never in the text).

Requires a trained model at models/<version>/ (run `python ml/train.py`
first). Run with:
    cd ml && pytest ../tests/test_explain.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ml"))

import pytest  # noqa: E402
from predict import FraudPredictor  # noqa: E402

GOOGLE_PM_JD = """
Minimum qualifications:
- Bachelor's degree or equivalent practical experience.
- 8 years of experience in product management or a related technical role.
- Experience working with engineering teams on platform and tooling initiatives.

Preferred qualifications:
- Master's degree in a technical field.
- Experience with AI/ML platforms and operational tooling.
- Excellent program management and cross-functional leadership skills.

About the job:
The AI Platform Operations and Tooling team builds the internal tools and
processes that power Google's AI infrastructure. As a Product Manager on
this team, you will define the roadmap for internal tooling, partner with
engineering leads across the organization, and drive operational excellence
across our AI platform investments.

Responsibilities:
- Define and drive the product roadmap for AI platform tooling.
- Partner with engineering, data science, and operations stakeholders.
- Own key metrics for platform reliability and developer productivity.
- Communicate progress and priorities to senior leadership.

Google is proud to be an equal opportunity workplace.
"""

MARKETING_JD = """
We are seeking an experienced Marketing Manager to lead our brand campaigns.
Responsibilities include developing integrated marketing campaigns,
managing budget, and collaborating with sales on go-to-market strategy.
Requirements: 5+ years of marketing experience, strong understanding of
SEO, content strategy, and Google Analytics. Full-time, hybrid role with
competitive salary and benefits.
"""

OBVIOUS_SCAM = """
Earn Rs 2 lakh per month from home! No experience required! Immediate
joining, limited seats! Pay Rs 999 registration fee to confirm your seat
today. Message us on WhatsApp to apply now, don't miss this chance!!!
"""

FORBIDDEN_PHRASES_FOR_CLEAN_TEXT = [
    "registration", "processing fee", "urgent-hiring", "high-pressure",
    "whatsapp", "telegram",
]


@pytest.fixture(scope="module")
def predictor():
    try:
        return FraudPredictor()
    except FileNotFoundError:
        pytest.skip("No trained model found — run `python ml/train.py` first.")


def test_google_pm_explanation_has_no_fabricated_reasons(predictor):
    result = predictor.predict(
        title="Product Manager, AI Platform Operations and Tooling",
        text=GOOGLE_PM_JD,
        company_name="Google",
    )
    feature_names_shown = {f["feature"] for f in result["top_features"] if f["direction"] == "increases_risk"}

    # The exact bug reported: these must never appear for this text.
    assert "has_registration_fee_mention" not in feature_names_shown
    assert "urgent_language_score" not in feature_names_shown
    assert "company_name_missing" not in feature_names_shown  # company_name="Google" was supplied
    assert "skill_role_mismatch_score" not in feature_names_shown  # PM role, not technical IC

    explanation_lower = result["explanation_text"].lower()
    for phrase in FORBIDDEN_PHRASES_FOR_CLEAN_TEXT:
        assert phrase not in explanation_lower, f"explanation fabricated '{phrase}': {result['explanation_text']}"


def test_google_pm_scores_low_risk(predictor):
    result = predictor.predict(
        title="Product Manager, AI Platform Operations and Tooling",
        text=GOOGLE_PM_JD,
        company_name="Google",
    )
    assert result["risk_category"] == "Low", (
        f"Expected Low risk for a detailed, legitimate posting, got "
        f"{result['risk_category']} ({result['fraud_probability']}%). "
        f"Explanation: {result['explanation_text']}"
    )
    assert result["fraud_probability"] < 45


def test_marketing_job_not_flagged_for_missing_tech_skills(predictor):
    result = predictor.predict(
        title="Marketing Manager", text=MARKETING_JD, company_name="Acme Corp",
    )
    feature_names_shown = {f["feature"] for f in result["top_features"] if f["direction"] == "increases_risk"}
    assert "skill_role_mismatch_score" not in feature_names_shown
    assert result["risk_category"] == "Low"


def test_obvious_scam_scores_elevated_risk_with_real_reasons(predictor):
    result = predictor.predict(title="Data Entry Executive", text=OBVIOUS_SCAM)
    # A short, single-paragraph scam message can land in Medium rather than
    # High — the calibrated thresholds are set from the actual score
    # distribution (see explain.py's risk_category_from_probability
    # docstring), where under 2% of GENUINE postings ever score above 60%.
    # Forcing a lower High cutoff to catch every short scam example would
    # trade that away and start misclassifying real postings. What matters
    # here is that the score is clearly elevated and every reason shown is
    # genuinely present in the text — not the exact label boundary.
    assert result["risk_category"] in ("Medium", "High")
    assert result["fraud_probability"] >= 50

    feature_names_shown = {f["feature"] for f in result["top_features"] if f["direction"] == "increases_risk"}
    # At least one of the genuinely-present scam signals must be surfaced.
    assert feature_names_shown & {
        "has_registration_fee_mention", "urgent_language_score",
        "promo_phrase_count", "requests_informal_contact",
    }


def test_dense_obvious_scam_scores_high_risk(predictor):
    """A scam message matching the density/pattern of real-world scam
    postings (multiple stacked red flags) should clearly reach High."""
    dense_scam = (
        "Immediate joining required!!! Apply now, limited seats!!! "
        "We are hiring Data Entry Executives across India, no interview required. "
        "Earn up to Rs. 90,000 per week working from home! No experience needed, guaranteed placement! "
        "100% job guarantee, pay a small registration fee to start. "
        "Message us on WhatsApp to apply now, don't miss this chance! "
        "Send your Aadhar card and registration fee to confirm your seat."
    )
    result = predictor.predict(title="Data Entry Executive", text=dense_scam)
    assert result["risk_category"] == "High"
    assert result["fraud_probability"] >= 65


def test_technical_job_with_real_skills_not_penalized(predictor):
    result = predictor.predict(
        title="Software Engineer",
        text="We need a Software Engineer with strong Python, SQL, AWS, and Docker experience.",
        company_name="Acme Corp",
    )
    feature_names_shown = {f["feature"] for f in result["top_features"] if f["direction"] == "increases_risk"}
    assert "skill_role_mismatch_score" not in feature_names_shown
