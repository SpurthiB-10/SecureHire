"""
clean.py — ETL Stage 2: CLEAN & NORMALIZE
-------------------------------------------
Reads the most recent landed parquet file, applies cleaning/normalization
rules, and writes a curated-quality DataFrame to data/processed/.

Responsibilities:
  * drop duplicate/near-duplicate postings (by normalized text hash)
  * standardize company names (casing, legal suffixes)
  * standardize locations ("Bengaluru" -> "Bangalore, India" etc.)
  * standardize/extract skill tokens
  * handle missing values with explicit, documented defaults
"""
import hashlib
import re
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent / "data"
PROCESSED_DIR = BASE / "processed"

LOCATION_ALIASES = {
    "bengaluru": "Bangalore, India",
    "bangalore": "Bangalore, India",
    "hyderabad": "Hyderabad, India",
    "gurgaon": "Delhi NCR, India",
    "gurugram": "Delhi NCR, India",
    "new delhi": "Delhi NCR, India",
    "delhi": "Delhi NCR, India",
    "bombay": "Mumbai, India",
    "mumbai": "Mumbai, India",
    "poona": "Pune, India",
    "pune": "Pune, India",
    "remote": "Remote",
    "work from home": "Remote",
}

COMPANY_SUFFIX_RE = re.compile(
    r"\b(pvt\.?\s*ltd\.?|private\s+limited|inc\.?|llc|ltd\.?|corp\.?|co\.?)\b",
    re.IGNORECASE,
)


def normalize_location(raw: str | float) -> str:
    if not isinstance(raw, str) or not raw.strip():
        return "Unknown"
    key = raw.strip().lower()
    key = re.split(r"[,/]", key)[0].strip()
    return LOCATION_ALIASES.get(key, raw.strip().title())


def normalize_company_name(raw: str | float) -> str:
    """
    Cleans whitespace and legal-suffix noise without destroying
    intentional brand capitalization.

    The previous version unconditionally applied .title() to every name,
    which mangles any name that already has meaningful internal
    capitalization: "AuditTestCorp" -> "Audittestcorp", "PayPal" ->
    "Paypal", "eBay" -> "Ebay", "OpenAI" -> "Openai". There's no way to
    *reconstruct* correct branding from a name that arrives ALL CAPS or
    all lowercase (that would need a real company-name database), but we
    CAN avoid destroying capitalization that's already there and clearly
    intentional. So: only apply .title() when the input is degenerate
    (entirely upper- or entirely lower-case, i.e. it carries no
    capitalization signal to preserve in the first place); otherwise
    trust the existing mixed-case spelling as-is.
    """
    if not isinstance(raw, str) or not raw.strip():
        return "Unknown"
    cleaned = COMPANY_SUFFIX_RE.sub("", raw).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        return "Unknown"
    if cleaned.isupper() or cleaned.islower():
        cleaned = cleaned.title()
    return cleaned


def text_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # --- normalize key text columns ---
    df["company_name"] = df["company_name"].apply(normalize_company_name)
    df["normalized_location"] = df["location"].apply(normalize_location)
    df["description"] = df["description"].fillna("").astype(str).str.strip()
    df["title"] = df["title"].fillna("Unknown Role").astype(str).str.strip()

    # --- fill sane defaults for missing numeric fields ---
    df["salary_min"] = pd.to_numeric(df["salary_min"], errors="coerce").fillna(0)
    df["salary_max"] = pd.to_numeric(df["salary_max"], errors="coerce").fillna(0)

    # --- dedup on normalized text hash (drop exact/near-duplicate postings) ---
    df["text_hash"] = (df["title"] + " " + df["description"]).apply(text_hash)
    before = len(df)
    df = df.drop_duplicates(subset="text_hash", keep="first")
    print(f"[clean] dropped {before - len(df)} duplicate postings")

    # --- drop rows with unusably short descriptions ---
    df = df[df["description"].str.len() >= 20]

    return df.reset_index(drop=True)


def run(landing_parquet: Path) -> Path:
    df = pd.read_parquet(landing_parquet)
    cleaned = clean(df)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = PROCESSED_DIR / "job_postings_clean.parquet"
    cleaned.to_parquet(out_path, index=False)
    print(f"[clean] wrote {len(cleaned)} rows -> {out_path}")
    return out_path


if __name__ == "__main__":
    landing_dirs = sorted((BASE / "raw" / "_landing").glob("*"))
    if not landing_dirs:
        raise SystemExit("No landed data found — run ingest.py first.")
    latest = landing_dirs[-1] / "job_postings_landed.parquet"
    run(latest)
