"""
Unit tests for the feature engineering module. Run with:
    cd ml && pytest ../tests/test_feature_engineering.py -v

Includes regression tests for the v1.1.0 bug fixes: the always-triggered
"missing company info" feature, the word-boundary-free technical-role
regex, and general-purpose (non-technical-category) coverage.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ml"))

from feature_engineering import extract_red_flags, extract_skills, is_feature_genuinely_present  # noqa: E402

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

Responsibilities:
- Develop and execute integrated marketing campaigns across channels.
- Manage the marketing budget and report on campaign performance.
- Collaborate with sales and product teams on go-to-market strategy.

Requirements:
- 5+ years of marketing experience, ideally in B2B SaaS.
- Strong understanding of SEO, content strategy, and Google Analytics.
- Excellent written and verbal communication skills.

This is a full-time, hybrid role based in our downtown office, with two
days per week remote. Competitive salary and benefits package.
"""

OBVIOUS_SCAM = """
Earn Rs 2 lakh per month from home! No experience required! Immediate
joining, limited seats! Pay Rs 999 registration fee to confirm your seat
today. Message us on WhatsApp to apply now, don't miss this chance!!!
"""


# --- TEST 1: Legitimate Google-style Product Manager job -------------------

def test_google_pm_job_has_no_fee_flag():
    rf = extract_red_flags(title="Product Manager, AI Platform Operations and Tooling",
                            text=GOOGLE_PM_JD, company_name="Google")
    assert rf.has_registration_fee_mention == 0


def test_google_pm_job_has_no_urgent_language():
    rf = extract_red_flags(title="Product Manager, AI Platform Operations and Tooling",
                            text=GOOGLE_PM_JD, company_name="Google")
    assert rf.urgent_language_score == 0


def test_google_pm_job_salary_not_provided_is_not_suspicious():
    rf = extract_red_flags(title="Product Manager, AI Platform Operations and Tooling",
                            text=GOOGLE_PM_JD, company_name="Google")
    assert rf.salary_is_suspicious == 0


def test_google_pm_job_company_name_not_missing():
    rf = extract_red_flags(title="Product Manager, AI Platform Operations and Tooling",
                            text=GOOGLE_PM_JD, company_name="Google")
    assert rf.company_name_missing == 0


def test_google_pm_job_not_flagged_as_technical_skill_mismatch():
    """This is the exact regression case: 'AI Platform' in the title must
    NOT match the technical-role detector via a bare 'ai' substring."""
    rf = extract_red_flags(title="Product Manager, AI Platform Operations and Tooling",
                            text=GOOGLE_PM_JD, company_name="Google")
    assert rf.skill_role_mismatch_score == 0.0


# --- TEST 2: Obvious fake job ------------------------------------------

def test_obvious_scam_flags_fee():
    rf = extract_red_flags(title="Data Entry Executive", text=OBVIOUS_SCAM)
    assert rf.has_registration_fee_mention == 1


def test_obvious_scam_flags_urgent_language():
    rf = extract_red_flags(title="Data Entry Executive", text=OBVIOUS_SCAM)
    assert rf.urgent_language_score > 0


def test_obvious_scam_flags_promo_phrases():
    rf = extract_red_flags(title="Data Entry Executive", text=OBVIOUS_SCAM)
    assert rf.promo_phrase_count >= 1


def test_obvious_scam_flags_informal_contact():
    rf = extract_red_flags(title="Data Entry Executive", text=OBVIOUS_SCAM)
    assert rf.requests_informal_contact == 1


# --- TEST 3: Legitimate non-technical job -------------------------------

def test_marketing_job_not_flagged_for_missing_technical_skills():
    rf = extract_red_flags(title="Marketing Manager", text=MARKETING_JD, company_name="Acme Corp")
    assert rf.skill_role_mismatch_score == 0.0


def test_marketing_job_clean_overall():
    rf = extract_red_flags(title="Marketing Manager", text=MARKETING_JD, company_name="Acme Corp")
    assert rf.has_registration_fee_mention == 0
    assert rf.urgent_language_score == 0
    assert rf.promo_phrase_count == 0


# --- TEST 4: Legitimate technical job -----------------------------------

def test_technical_job_with_skills_not_mismatched():
    text = ("We need a Software Engineer with strong Python, SQL, AWS, and "
            "Docker experience to build our backend services.")
    rf = extract_red_flags(title="Software Engineer", text=text, company_name="Acme Corp")
    assert rf.skill_role_mismatch_score == 0.0


def test_technical_job_without_skills_is_mismatched():
    """Sanity check the signal still fires for a GENUINELY technical title
    that names no concrete tools at all."""
    text = "We need a great engineer to join our team. Apply today."
    rf = extract_red_flags(title="Software Engineer", text=text, company_name="Acme Corp")
    assert rf.skill_role_mismatch_score > 0


def test_skills_do_not_increase_risk_for_other_features():
    """Technical skills themselves must never be treated as suspicious."""
    text = "Required skills: Python, SQL, AWS, Docker, Kubernetes."
    rf = extract_red_flags(title="Software Engineer", text=text, company_name="Acme Corp")
    assert rf.promo_phrase_count == 0
    assert rf.urgent_language_score == 0


# --- TEST 5: Missing information stays unknown, not fraudulent ---------

def test_no_salary_no_website_no_email_is_not_penalized():
    rf = extract_red_flags(title="Operations Manager", text=MARKETING_JD, company_name="Acme Corp")
    assert rf.salary_is_suspicious == 0  # no salary supplied at all
    assert rf.has_free_email_domain == 0  # no email supplied at all


def test_has_company_website_param_never_used_for_scoring():
    """has_company_website is accepted for forward-compatibility but must
    never itself produce a red flag, regardless of its value."""
    rf_none = extract_red_flags(title="Marketing Manager", text=MARKETING_JD,
                                 company_name="Acme Corp", has_company_website=None)
    rf_false = extract_red_flags(title="Marketing Manager", text=MARKETING_JD,
                                  company_name="Acme Corp", has_company_website=False)
    # Neither produces a company_name_missing flag, since company_name IS
    # provided in both cases — has_company_website plays no role.
    assert rf_none.company_name_missing == 0
    assert rf_false.company_name_missing == 0


def test_missing_company_name_is_the_real_observable_signal():
    rf = extract_red_flags(title="Data Entry Executive", text=OBVIOUS_SCAM, company_name=None)
    assert rf.company_name_missing == 1

    rf_empty = extract_red_flags(title="Data Entry Executive", text=OBVIOUS_SCAM, company_name="")
    assert rf_empty.company_name_missing == 1


# --- TEST 6: Free email is a mild, non-determinative signal -------------

def test_free_email_domain_flagged():
    rf = extract_red_flags(title="Marketing Manager", text=MARKETING_JD,
                            contact_email="hr.jobs99@gmail.com")
    assert rf.has_free_email_domain == 1


def test_corporate_email_not_flagged():
    rf = extract_red_flags(title="Data Analyst", text=MARKETING_JD,
                            contact_email="careers@infosys.com")
    assert rf.has_free_email_domain == 0


# --- TEST 7: Registration fee explicit mention --------------------------

def test_registration_fee_mention_detected():
    rf = extract_red_flags(
        title="Work From Home Opportunity",
        text="Pay a small registration fee to confirm your seat and start earning today.",
    )
    assert rf.has_registration_fee_mention == 1


def test_processing_fee_variants_detected():
    for phrase in ["processing fee", "security fee", "training fee", "activation fee"]:
        rf = extract_red_flags(title="Work From Home", text=f"Please pay the {phrase} to begin.")
        assert rf.has_registration_fee_mention == 1, f"failed for: {phrase}"


def test_unrelated_use_of_word_fee_not_flagged():
    rf = extract_red_flags(title="Customer Support", text="This role has no application fee of any kind.")
    assert rf.has_registration_fee_mention == 0


# --- Other general checks ------------------------------------------------

def test_urgent_language_score_scales_with_matches():
    calm = extract_red_flags(title="Data Engineer", text="We welcome applications from qualified candidates.")
    urgent = extract_red_flags(
        title="Data Engineer",
        text="Immediate joining required!!! Apply now, limited seats!!! Don't miss this chance!",
    )
    assert urgent.urgent_language_score > calm.urgent_language_score


def test_salary_suspicious_for_entry_level_high_pay():
    rf = extract_red_flags(
        title="Fresher Intern", text="Great opportunity", salary_min=0, salary_max=200000,
    )
    assert rf.salary_is_suspicious == 1


def test_salary_not_suspicious_for_reasonable_range():
    rf = extract_red_flags(
        title="Data Engineer Intern", text="Great opportunity", salary_min=25000, salary_max=30000,
    )
    assert rf.salary_is_suspicious == 0


def test_extract_skills_finds_known_technologies():
    skills = extract_skills("We need someone skilled in Python, SQL, Docker, and Airflow.")
    assert "python" in skills
    assert "sql" in skills
    assert "docker" in skills
    assert "airflow" in skills


def test_extract_skills_finds_non_technical_skills():
    skills = extract_skills("Experience with SEO, content strategy, and Google Analytics required.")
    assert "seo" in skills
    assert "content strategy" in skills
    assert "google analytics" in skills


def test_extract_skills_empty_for_no_matches():
    skills = extract_skills("We are looking for a friendly, hard-working team player.")
    assert skills == []


def test_is_feature_genuinely_present_gates_correctly():
    assert is_feature_genuinely_present("has_registration_fee_mention", 0) is False
    assert is_feature_genuinely_present("has_registration_fee_mention", 1) is True
    assert is_feature_genuinely_present("urgent_language_score", 0) is False
    assert is_feature_genuinely_present("urgent_language_score", 0.5) is True
