"""
company_ai_service.py
------------------------
Gemini-powered company intelligence: given a job posting's company name,
website (if known), recruiter email, and description text, asks Gemini
to return a structured verification assessment.

DESIGN PRINCIPLES (matching the rest of this project's approach):
  1. Structured output only. We ask Gemini to return JSON matching an
     exact schema and parse it defensively — never treat free-form LLM
     text as something to display directly or execute.
  2. Fail open, loudly logged. If GEMINI_API_KEY isn't set, the API call
     fails, or the response doesn't parse as valid JSON, this returns a
     clearly-labeled "unavailable" result (status="unavailable" or
     "error") rather than crashing the whole /jobs/analyze request or
     silently fabricating a verification score. The ML fraud analysis
     (the app's core feature) must keep working even if Gemini is down,
     misconfigured, or the key is missing/rate-limited.
  3. This is a genuinely separate, additional signal from the ML fraud
     model — it estimates company legitimacy from what an LLM can find/
     reason about the company name, not from the posting's text
     patterns. It is surfaced alongside, not blended into, the ML
     fraud_probability.
"""
import json
import logging
import os
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

GEMINI_MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

_RESPONSE_SCHEMA_INSTRUCTIONS = """
You are a company-verification assistant for a job-fraud-detection tool.
Given a company name (and optionally a website/domain and recruiter email
domain), assess how verifiable and legitimate this company appears to be
based on what you know about it.

Respond with ONLY a single JSON object (no markdown fences, no prose
before or after) matching EXACTLY this schema:

{
  "company_summary": "<1-2 sentence factual summary of the company, or 'Unknown company — no reliable information available' if you don't recognize it>",
  "industry": "<industry/sector, or null if unknown>",
  "headquarters": "<HQ location, or null if unknown>",
  "website_status": "<one of: verified, not_found, unknown, suspicious>",
  "online_presence": "<one of: strong, moderate, weak, unknown>",
  "recruiter_email_status": "<one of: corporate_domain, free_email, unknown>",
  "company_verification_score": <integer 0-100, your confidence this is a real, legitimate, currently-operating company>,
  "key_findings": ["<short finding 1>", "<short finding 2>", "..."],
  "evidence": [{"claim": "<what you're claiming>", "reasoning": "<why/how you know this>"}],
  "recommendation": "<1-2 sentence actionable recommendation for the job seeker>"
}

Rules:
- If you do not recognize the company at all, or cannot verify it,
  DO NOT invent details. Use "unknown"/null values and a low-to-moderate
  verification_score, and say so plainly in company_summary.
- Never claim certainty about a company you don't actually have
  information about.
- company_verification_score must be an integer 0-100.
"""


@dataclass
class CompanyIntelligenceResult:
    status: str  # "ok" | "unavailable" | "error"
    company_summary: str | None = None
    industry: str | None = None
    headquarters: str | None = None
    website_status: str = "unknown"
    online_presence: str = "unknown"
    recruiter_email_status: str = "unknown"
    verification_score: float | None = None
    key_findings: list[str] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    recommendation: str | None = None
    llm_provider: str = "gemini"
    llm_model: str | None = None
    error_message: str | None = None


def _unavailable(internal_reason: str, user_message: str) -> CompanyIntelligenceResult:
    """internal_reason is logged server-side only and NEVER exposed via the
    API — user_message is a short, generic, safe-to-display string. This
    split is the actual fix: earlier, the raw internal reason (which could
    include exception text, SDK internals, etc.) was the only message
    available, and it was silently dropped before reaching the API anyway
    (a Pydantic extra-field quirk) — so errors were invisible to users AND
    developers had to grep server logs even for the simple "no key
    configured" case. Now both audiences get an appropriate message."""
    logger.info("Gemini company intelligence unavailable: %s", internal_reason)
    return CompanyIntelligenceResult(
        status="unavailable",
        company_summary="Company intelligence is unavailable right now.",
        recommendation="Verify this company independently (official website, LinkedIn, past employee reviews) before proceeding.",
        error_message=user_message,
    )


def _error(internal_reason: str, user_message: str = "Company intelligence is temporarily unavailable.") -> CompanyIntelligenceResult:
    """Same split as _unavailable() — internal_reason (which may contain
    raw exception text from the Gemini SDK) is logged only; user_message
    is always one of a small set of generic, safe strings. NEVER pass
    exception text, API keys, or any internal detail as user_message."""
    logger.warning("Gemini company intelligence error: %s", internal_reason)
    return CompanyIntelligenceResult(
        status="error",
        company_summary="Company intelligence could not be generated for this request.",
        recommendation="Verify this company independently before proceeding.",
        error_message=user_message,
    )


def _extract_json(raw_text: str) -> dict:
    """Gemini is asked for raw JSON, but models sometimes wrap it in
    markdown fences anyway — strip those defensively before parsing."""
    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _derive_recruiter_email_status(contact_email: str | None) -> str:
    if not contact_email or "@" not in contact_email:
        return "unknown"
    domain = contact_email.split("@")[-1].lower()
    free_domains = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
                     "rediffmail.com", "aol.com", "protonmail.com", "icloud.com"}
    return "free_email" if domain in free_domains else "corporate_domain"


def get_company_intelligence(
    company_name: str | None,
    company_website: str | None = None,
    contact_email: str | None = None,
    job_description_excerpt: str | None = None,
) -> CompanyIntelligenceResult:
    """
    Main entry point. Never raises — always returns a CompanyIntelligenceResult
    with a clear `status`, so callers (the /jobs/analyze endpoint) can persist
    and return it unconditionally without extra error handling.
    """
    if not company_name or not company_name.strip():
        return _unavailable(
            "No company name was supplied — nothing to verify.",
            user_message="No company name was provided to verify.",
        )

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return _unavailable(
            "GEMINI_API_KEY is not configured.",
            user_message="Company intelligence is not configured for this deployment.",
        )

    try:
        import google.generativeai as genai
    except ImportError:
        return _unavailable(
            "google-generativeai package is not installed.",
            user_message="Company intelligence is not available for this deployment.",
        )

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            GEMINI_MODEL_NAME,
            generation_config={"response_mime_type": "application/json"},
        )

        prompt_parts = [_RESPONSE_SCHEMA_INSTRUCTIONS, f"\nCompany name: {company_name.strip()}"]
        if company_website:
            prompt_parts.append(f"Claimed website: {company_website.strip()}")
        if contact_email:
            prompt_parts.append(f"Recruiter contact email domain: {contact_email.split('@')[-1] if '@' in contact_email else contact_email}")
        if job_description_excerpt:
            excerpt = job_description_excerpt.strip()[:500]
            prompt_parts.append(f"Job posting excerpt (for context only, do not verify the job itself): {excerpt}")

        response = model.generate_content("\n".join(prompt_parts))
        raw_text = response.text
    except Exception as exc:  # network error, auth error, rate limit, etc.
        # exc's text is logged (internal_reason) but NEVER put in
        # user_message — SDK exception text can include request details
        # that shouldn't be echoed back to an end user.
        return _error(f"Gemini API call failed: {exc}")

    try:
        parsed = _extract_json(raw_text)
    except (json.JSONDecodeError, AttributeError) as exc:
        return _error(
            f"Gemini response was not valid JSON: {exc}",
            user_message="Company intelligence returned an unexpected response and could not be used.",
        )

    score = parsed.get("company_verification_score")
    try:
        score = float(score) if score is not None else None
        if score is not None:
            score = max(0.0, min(100.0, score))
    except (TypeError, ValueError):
        score = None

    recruiter_status = parsed.get("recruiter_email_status") or _derive_recruiter_email_status(contact_email)

    return CompanyIntelligenceResult(
        status="ok",
        company_summary=parsed.get("company_summary"),
        industry=parsed.get("industry"),
        headquarters=parsed.get("headquarters"),
        website_status=parsed.get("website_status") or "unknown",
        online_presence=parsed.get("online_presence") or "unknown",
        recruiter_email_status=recruiter_status,
        verification_score=score,
        key_findings=parsed.get("key_findings") or [],
        evidence=parsed.get("evidence") or [],
        recommendation=parsed.get("recommendation"),
        llm_model=GEMINI_MODEL_NAME,
    )
