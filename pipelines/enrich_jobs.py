"""
enrich_jobs.py — Warehouse ETL Stage 3: ENRICH
--------------------------------------------------
Adds derived/analytics-ready fields to the cleaned data and writes to
data/curated/<run_id>/. This is the last stage before loading into the
warehouse — everything here is a computed/derived column, never a
correction to the source data itself (raw data is never modified; see
docs/CHANGELOG_FRAUD_FIX.md's broader project principle of not silently
overwriting/guessing at unknown values).

Derived fields added:
  - salary_band: bucketed salary range for easier grouping in charts
  - is_high_risk: boolean convenience flag (risk_category == 'High')
  - recruiter_email_domain: extracted domain for the "recruiter domain
    distribution" dashboard chart
  - posting_age_days: days since the posting was created, at enrichment time
"""
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent / "data"
CURATED_DIR = BASE / "curated"


def _salary_band(row) -> str:
    if pd.isna(row.get("salary_min")) and pd.isna(row.get("salary_max")):
        return "Not specified"
    salary = row.get("salary_max") or row.get("salary_min") or 0
    if salary <= 0:
        return "Not specified"
    if salary < 20000:
        return "< 20k"
    if salary < 50000:
        return "20k - 50k"
    if salary < 100000:
        return "50k - 100k"
    return "100k+"


def _extract_email_domain(email) -> str | None:
    if not isinstance(email, str) or "@" not in email:
        return None
    return email.split("@")[-1].strip().lower()


def enrich(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["salary_band"] = df.apply(_salary_band, axis=1)
    df["is_high_risk"] = df["risk_category"].astype(str).str.lower() == "high"
    df["recruiter_email_domain"] = df["contact_email"].apply(_extract_email_domain) if "contact_email" in df.columns else None

    if "created_at" in df.columns:
        created = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
        now = pd.Timestamp.now(tz="UTC")
        df["posting_age_days"] = (now - created).dt.days

    return df


def run(processed_parquet: Path, run_id: str) -> Path:
    df = pd.read_parquet(processed_parquet)
    enriched = enrich(df)

    out_dir = CURATED_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "job_postings_curated.parquet"
    enriched.to_parquet(out_path, index=False)
    print(f"[enrich_jobs] enriched {len(enriched)} rows -> {out_path}")
    return out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--processed-parquet", required=True)
    args = parser.parse_args()
    run(Path(args.processed_parquet), args.run_id)
