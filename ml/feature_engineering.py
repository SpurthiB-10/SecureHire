"""
feature_engineering.py
------------------------
Rule-based + NLP feature extraction for the fake-job classifier.

v1.1.0 CHANGES (see docs/CHANGELOG_FRAUD_FIX.md for the full incident writeup):
  - `missing_company_info` was renamed to `company_name_missing` and is now
    derived ONLY from whether a company name was actually supplied — a
    fact we always genuinely know. The old feature was driven by
    `has_company_website`, a field the product has never had a way to
    populate, so it was silently `False` (== "missing") on every single
    request in production. That is a train/serve skew, not a red flag.
  - `has_company_website` is kept as an optional parameter for forward
    compatibility (e.g. a future "verify this domain" integration) but is
    NO LONGER used to compute any fraud signal. If we don't actually know
    it, we must not pretend we do.
  - `_skill_role_mismatch()`'s technical-role detector previously matched
    bare substrings with no word boundaries (`"ai"` inside "Product
    Manager, AI Platform..." falsely matched). It's now a whitelist regex
    over actual individual-contributor technical titles, so PM/Marketing/
    HR/Sales/Finance/Design/etc. roles are never held to a "must mention
    Python/SQL" standard.
  - Added `requests_informal_contact` — a general-purpose scam signal
    (WhatsApp/Telegram/personal-number-only application instructions)
    that applies across every job category, not just technical roles.
  - Broadened SKILLS_VOCAB with role-general terms (marketing, HR, sales,
    finance, design, healthcare, ops, support, teaching, admin) so skill
    extraction is useful outside tech roles too (Skill Intelligence
    Engine), while the fraud-relevant skill-mismatch signal stays
    strictly scoped to genuinely technical IC titles.

Design note: features are split into two groups —
  1. Hand-crafted "red flag" signals (interpretable, drive the SHAP
     explanations shown to the user) — these are the columns fed into
     the tabular classifiers (LogReg / RandomForest / XGBoost).
  2. Text-representation features (TF-IDF) — these capture patterns the
     hand-crafted rules miss and are concatenated to the hand-crafted
     feature vector.

This module has NO dependency on FastAPI/SQLAlchemy so it can be reused
identically by the offline training pipeline (train.py) and the online
inference service (backend/app/services/ml_service.py).

IMPORTANT: changing RedFlagFeatures' fields changes the model's input
schema. Any change here REQUIRES retraining (see ml/train.py) — old
model artifacts trained on a different feature set are not compatible
and must not be loaded against this version of the module.
"""
import re
from dataclasses import dataclass, asdict

import pandas as pd

FREE_EMAIL_DOMAINS = {
    "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
    "rediffmail.com", "aol.com", "protonmail.com", "icloud.com", "live.com",
}

URGENT_KEYWORDS = [
    "immediate joining", "urgent", "urgently", "limited seats", "act fast",
    "don't miss", "apply now", "hurry", "only few seats", "join today",
    "seats filling fast", "last few slots", "immediate hiring",
]

PROMO_KEYWORDS = [
    "earn up to", "no experience needed", "no experience required",
    "guaranteed placement", "guaranteed job", "guaranteed income",
    "100% job guarantee", "work from home and earn", "registration fee",
    "pay a small fee", "processing fee", "easy money", "quick money",
    "per week guaranteed", "lakhs per month", "instant hiring",
    "hiring without interview", "no interview required",
    "work 2 hours a day", "pay after you get hired", "earn daily",
    "earn weekly", "part time full income",
]

# Broadened, still-conservative fee/payment-request detector — this is one
# of the strongest genuine scam signals (a legitimate employer never asks
# a candidate to pay to be hired), so it's kept fairly literal/precise
# rather than fuzzy, to avoid false positives on legitimate mentions of
# "fee" in unrelated contexts (e.g. "no application fee").
FEE_REQUEST_PATTERN = re.compile(
    r"(registration|processing|security|training|kit|activation|joining)\s+fee"
    r"|pay\s+(a\s+)?(small\s+)?(fee|deposit|amount)"
    r"|refundable\s+deposit"
    r"|advance\s+payment"
    r"|investment\s+required",
    re.IGNORECASE,
)

# Scam postings frequently steer applicants off official channels and onto
# informal messaging apps or a bare personal phone number — a pattern that
# applies across every job category (not just tech), and is genuinely
# always observable from the text alone.
INFORMAL_CONTACT_PATTERN = re.compile(
    r"(whatsapp|telegram)[^.]{0,40}(apply|contact|message|send|share|dm|number)"
    r"|(apply|contact|message|send\s+(your\s+)?(resume|cv|details))[^.]{0,40}(whatsapp|telegram)"
    r"|\bping\s+(us|me)\s+on\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------
# Skill vocabulary — deliberately spans many job categories, not just
# software/data roles, so skill extraction (Skill Intelligence Engine)
# is useful for Marketing, HR, Sales, Finance, Design, Healthcare,
# Operations, Support, Teaching, and Admin postings too.
# ---------------------------------------------------------------------
SKILLS_VOCAB = [
    # software / data / technical
    "python", "sql", "java", "c++", "pandas", "numpy", "spark", "hadoop",
    "airflow", "aws", "azure", "gcp", "docker", "kubernetes", "react",
    "node.js", "django", "flask", "fastapi", "machine learning",
    "deep learning", "nlp", "etl", "kafka", "postgresql", "mongodb",
    "tableau", "powerbi", "excel", "git", "linux", "tensorflow", "pytorch",
    # product / marketing
    "product management", "roadmapping", "seo", "sem", "content strategy",
    "google analytics", "social media marketing", "brand management",
    "market research", "a/b testing", "crm",
    # hr / recruiting
    "recruitment", "talent acquisition", "hris", "employee relations",
    "onboarding", "performance management", "payroll",
    # sales
    "salesforce", "lead generation", "account management",
    "negotiation", "quota attainment", "b2b sales",
    # finance / accounting
    "financial modeling", "gaap", "bookkeeping", "accounts payable",
    "budgeting", "forecasting", "tally", "quickbooks",
    # design
    "figma", "adobe xd", "wireframing", "user research", "photoshop",
    "ui design", "ux design",
    # healthcare
    "patient care", "clinical procedures", "emr", "nursing",
    # operations / support
    "process optimization", "vendor management", "logistics",
    "supply chain", "ticketing systems", "customer support", "sla",
    # teaching / admin
    "curriculum design", "classroom management", "scheduling",
    "office management", "correspondence",
]

# rough market-demand tiers for the Skill Intelligence Engine (mocked;
# in production this would be computed from live job-market aggregation)
SKILL_DEMAND = {
    "python": "High", "sql": "High", "aws": "High", "machine learning": "High",
    "docker": "High", "kubernetes": "Medium", "airflow": "Medium",
    "spark": "Medium", "react": "High", "excel": "Medium", "tableau": "Medium",
    "powerbi": "Medium", "nlp": "Medium", "etl": "Medium", "kafka": "Medium",
    "django": "Low", "flask": "Low", "c++": "Medium",
    "product management": "High", "seo": "Medium", "google analytics": "Medium",
    "crm": "Medium", "salesforce": "High", "recruitment": "Medium",
    "financial modeling": "Medium", "figma": "High", "ux design": "High",
    "patient care": "Medium", "logistics": "Medium", "customer support": "Medium",
}

# Strictly individual-contributor, hands-on technical titles ONLY. This is
# a whitelist (not a blacklist substring match) specifically so titles like
# "Product Manager, AI Platform Operations and Tooling" or "Technical
# Recruiter" or "Sales Engineer" don't get swept in just because they
# contain a technical-sounding word. Word boundaries are mandatory.
TECHNICAL_IC_ROLE_PATTERN = re.compile(
    r"\b(software|data|ml|machine\s+learning|backend|front[\s-]?end|"
    r"full[\s-]?stack|devops|site\s+reliability|sre|qa|quality\s+assurance|"
    r"cloud|platform|infrastructure|security|embedded|firmware)\s+"
    r"(engineer|developer|scientist|architect)\b"
    r"|\bdata\s+analyst\b"
    r"|\b(ml|ai)\s+engineer\b",
    re.IGNORECASE,
)


@dataclass
class RedFlagFeatures:
    has_free_email_domain: int
    salary_is_suspicious: int
    urgent_language_score: float
    company_name_missing: int
    experience_mismatch_score: float
    promo_phrase_count: int
    skill_role_mismatch_score: float
    location_inconsistency: int
    description_length: int
    exclamation_count: int
    salary_spread_ratio: float
    has_registration_fee_mention: int
    requests_informal_contact: int


def _extract_email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return email.split("@")[-1].strip().lower()


def _count_matches(text: str, phrases: list[str]) -> int:
    text_l = text.lower()
    return sum(text_l.count(p) for p in phrases)


def _salary_suspicious(salary_min: float | None, salary_max: float | None, role_title: str) -> tuple[int, float]:
    """Flags unrealistically wide or high salary bands for entry-level/intern
    roles. Only ever computed when salary data was actually supplied —
    missing salary is UNKNOWN, never treated as suspicious.

    Note: the absolute-value threshold below assumes INR-scale monthly-ish
    figures (a holdover from the training dataset's locale) and is a known
    limitation for other currencies/scales — see docs/CHANGELOG_FRAUD_FIX.md.
    The spread-ratio check is currency-agnostic and is the primary signal.
    """
    if not salary_min and not salary_max:
        return 0, 0.0
    salary_min = salary_min or 0
    salary_max = salary_max or salary_min
    spread_ratio = (salary_max - salary_min) / max(salary_min, 1)

    is_entry_level = bool(re.search(r"\b(intern|entry[\s-]?level|fresher|junior)\b", role_title, re.IGNORECASE))
    suspicious = 0
    if is_entry_level and salary_max > 100000:
        suspicious = 1
    if spread_ratio > 2.5:
        suspicious = 1
    return suspicious, round(spread_ratio, 2)


def _skill_role_mismatch(text: str, role_title: str) -> float:
    """Only applies to strictly technical, hands-on individual-contributor
    titles (see TECHNICAL_IC_ROLE_PATTERN). A Product Manager, Marketing
    Manager, HR Manager, Sales rep, etc. is NEVER penalized for not
    mentioning Python/SQL/Docker — that would be a false generalization,
    not a fraud signal."""
    is_technical_ic_role = bool(TECHNICAL_IC_ROLE_PATTERN.search(role_title))
    if not is_technical_ic_role:
        return 0.0
    skill_hits = len(extract_skills(text))
    if skill_hits == 0:
        return 1.0
    if skill_hits <= 1:
        return 0.5
    return 0.0


def extract_red_flags(
    title: str,
    text: str,
    contact_email: str | None = None,
    salary_min: float | None = None,
    salary_max: float | None = None,
    has_company_website: bool | None = None,  # noqa: ARG001 — kept for forward compatibility, intentionally unused for scoring; see module docstring
    location: str | None = None,
    company_name: str | None = None,
) -> RedFlagFeatures:
    domain = _extract_email_domain(contact_email)
    has_free_email = int(domain in FREE_EMAIL_DOMAINS) if domain else 0

    salary_suspicious, spread_ratio = _salary_suspicious(salary_min, salary_max, title)

    urgent_score = min(_count_matches(text, URGENT_KEYWORDS) / 2.0, 1.0)
    promo_count = _count_matches(text, PROMO_KEYWORDS)

    # A company NAME being absent is directly, always observable from the
    # supplied data — unlike "website presence," which this product has no
    # way to verify, so it is never used as a signal (see module docstring).
    company_name_missing = int(not isinstance(company_name, str) or not company_name.strip())

    exclaim = text.count("!")

    # experience mismatch: "intern" role asking for 2+ years experience
    exp_match = re.search(r"(\d+)\+?\s*years?.{0,15}experience", text, re.IGNORECASE)
    is_intern = bool(re.search(r"\bintern\b", title, re.IGNORECASE))
    exp_mismatch = 0.0
    if exp_match and is_intern and int(exp_match.group(1)) >= 2:
        exp_mismatch = 1.0

    skill_mismatch = _skill_role_mismatch(text, title)

    # Kept conservative/off by default — see module docstring on why a
    # weak heuristic here is worse than no signal at all. Left as an
    # explicit, documented placeholder rather than silently vestigial.
    loc_inconsistent = 0

    fee_mention = int(bool(FEE_REQUEST_PATTERN.search(text)))
    informal_contact = int(bool(INFORMAL_CONTACT_PATTERN.search(text)))

    return RedFlagFeatures(
        has_free_email_domain=has_free_email,
        salary_is_suspicious=salary_suspicious,
        urgent_language_score=urgent_score,
        company_name_missing=company_name_missing,
        experience_mismatch_score=exp_mismatch,
        promo_phrase_count=promo_count,
        skill_role_mismatch_score=skill_mismatch,
        location_inconsistency=loc_inconsistent,
        description_length=len(text),
        exclamation_count=exclaim,
        salary_spread_ratio=spread_ratio,
        has_registration_fee_mention=fee_mention,
        requests_informal_contact=informal_contact,
    )


def extract_skills(text: str) -> list[str]:
    """Word-boundary matching, not naive substring search — otherwise short
    skill tokens false-positive inside unrelated words (e.g. "excel" would
    match inside "excellent", "r" inside almost anything). Multi-word
    phrases get the same treatment for consistency."""
    text_l = text.lower()
    found = []
    for s in SKILLS_VOCAB:
        pattern = r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])"
        if re.search(pattern, text_l):
            found.append(s)
    return found


def red_flags_to_frame(rows: list[RedFlagFeatures]) -> pd.DataFrame:
    return pd.DataFrame([asdict(r) for r in rows])


FEATURE_COLUMNS = list(RedFlagFeatures.__dataclass_fields__.keys())

# Presence rule per feature: given a RAW (unscaled) feature value, does it
# indicate the signal is genuinely, observably present? Used by explain.py
# to gate which reasons are allowed to be shown to the user — SHAP ranking
# alone is NOT sufficient grounds to claim a red flag exists (a feature
# sitting at its "off" value can still receive nonzero SHAP attribution in
# a tree ensemble; that is a statistical artifact, not evidence).
def is_feature_genuinely_present(feature_name: str, raw_value: float) -> bool:
    if feature_name in (
        "has_free_email_domain", "salary_is_suspicious", "company_name_missing",
        "location_inconsistency", "has_registration_fee_mention",
        "requests_informal_contact",
    ):
        return raw_value >= 1
    if feature_name == "experience_mismatch_score":
        return raw_value >= 1.0
    if feature_name == "skill_role_mismatch_score":
        return raw_value >= 0.5
    if feature_name == "urgent_language_score":
        return raw_value > 0
    if feature_name == "promo_phrase_count":
        return raw_value >= 1
    if feature_name == "exclamation_count":
        return raw_value >= 4  # a handful of "!" is normal; treat excess as the signal
    if feature_name == "salary_spread_ratio":
        return raw_value > 2.5
    if feature_name == "description_length":
        return raw_value < 200  # unusually thin description
    return raw_value != 0
