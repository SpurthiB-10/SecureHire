"""
clean_jobs.py — Warehouse ETL Stage 2: STAGE + CLEAN
--------------------------------------------------------
Two sub-stages, both handled here since they operate on the same
DataFrame in sequence:

  STAGING  (data/staging/<run_id>/): schema validation + dtype coercion.
           The data is still essentially raw, but we now know it matches
           the expected shape — this is the "quarantine" checkpoint
           before any values are actually changed.

  PROCESSED (data/processed/<run_id>/): deduplication + normalization
           (company name, location) + an ingestion timestamp, reusing the
           exact same normalize_company_name/normalize_location/text_hash
           logic already defined in pipelines/clean.py, rather than
           duplicating it.

Returns a metrics dict (rows in, rows after staging validation, rows
after dedup, duplicates removed) — build_warehouse.py persists this to
the pipeline_metrics table.
"""
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent / "data"
STAGING_DIR = BASE / "staging"
PROCESSED_DIR = BASE / "processed"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean import normalize_company_name, normalize_location, text_hash  # noqa: E402
from data_quality import validate_job_postings  # noqa: E402

REQUIRED_COLUMNS = {
    "job_id", "title", "raw_text", "location", "company_name",
    "fraud_probability", "risk_category", "created_at",
}


def validate_schema(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """STAGING step: check required columns exist, coerce dtypes. Never
    silently drops a required column — raises if the extract's shape has
    genuinely changed (a real schema-drift signal worth failing loudly on,
    not papering over)."""
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Raw extract is missing required columns: {missing}")

    issues = []
    df = df.copy()

    for numeric_col in ("salary_min", "salary_max", "fraud_probability", "fraud_confidence"):
        if numeric_col in df.columns:
            before_nulls = df[numeric_col].isna().sum()
            df[numeric_col] = pd.to_numeric(df[numeric_col], errors="coerce")
            after_nulls = df[numeric_col].isna().sum()
            if after_nulls > before_nulls:
                issues.append(f"{numeric_col}: {after_nulls - before_nulls} values failed numeric coercion")

    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce")

    return df, issues


def clean_and_normalize(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """PROCESSED step: dedup + normalize, reusing pipelines/clean.py logic."""
    df = df.copy()
    rows_before = len(df)

    df["company_name"] = df["company_name"].apply(normalize_company_name)
    df["normalized_location"] = df["location"].apply(normalize_location)
    df["raw_text"] = df["raw_text"].fillna("").astype(str)
    df["title"] = df["title"].fillna("Unknown Role").astype(str).str.strip()

    df["_dedup_hash"] = (df["title"] + " " + df["raw_text"]).apply(text_hash)
    df = df.drop_duplicates(subset="_dedup_hash", keep="first")
    duplicates_removed = rows_before - len(df)

    metrics = {
        "rows_before_clean": rows_before,
        "rows_after_clean": len(df),
        "duplicates_removed": duplicates_removed,
    }
    return df.reset_index(drop=True), metrics


def run(raw_csv: Path, run_id: str) -> tuple[Path, dict]:
    df = pd.read_csv(raw_csv)
    rows_ingested = len(df)

    staged_df, validation_issues = validate_schema(df)
    staging_out = STAGING_DIR / run_id
    staging_out.mkdir(parents=True, exist_ok=True)
    staged_df.to_parquet(staging_out / "job_postings_staged.parquet", index=False)
    if validation_issues:
        print(f"[clean_jobs] staging validation issues: {validation_issues}")

    # --- data quality checks (see data_quality.py) ---
    # Run against the staged data (post-dtype-coercion, pre-dedup/normalize)
    # so checks see the data closest to its original, unmodified form.
    dq_report = validate_job_postings(staged_df)
    print(f"[clean_jobs] data quality: {dq_report.summary_line()}")
    for issue in dq_report.issues:
        print(f"  [{issue.severity.upper()}] {issue.check_name}: {issue.row_count} rows — {issue.description}")
    if dq_report.has_errors:
        # Error-severity issues mean the extract itself is untrustworthy
        # (e.g. a null job_id, a fraud_probability outside [0, 100]) —
        # halt rather than silently build a warehouse on top of it. This
        # should never actually fire if the application is working
        # correctly; if it does, something upstream needs a human to look
        # at it, not a pipeline that quietly proceeds anyway.
        raise ValueError(
            f"Data quality check failed: {dq_report.summary_line()} "
            f"See the [ERROR] lines above for which checks failed."
        )

    processed_df, dedup_metrics = clean_and_normalize(staged_df)
    processed_out = PROCESSED_DIR / run_id
    processed_out.mkdir(parents=True, exist_ok=True)
    out_path = processed_out / "job_postings_clean.parquet"
    processed_df.to_parquet(out_path, index=False)

    metrics = {
        "rows_ingested": rows_ingested,
        "rows_cleaned": dedup_metrics["rows_after_clean"],
        "duplicates_removed": dedup_metrics["duplicates_removed"],
        "validation_issues": validation_issues,
        "data_quality": dq_report.to_dict(),
    }
    print(f"[clean_jobs] {rows_ingested} -> {dedup_metrics['rows_after_clean']} rows "
          f"({dedup_metrics['duplicates_removed']} duplicates removed) -> {out_path}")
    return out_path, metrics


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--raw-csv", required=True)
    args = parser.parse_args()
    run(Path(args.raw_csv), args.run_id)
