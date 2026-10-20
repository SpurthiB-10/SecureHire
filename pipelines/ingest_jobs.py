"""
ingest_jobs.py — Warehouse ETL Stage 1: INGEST
-------------------------------------------------
Extracts analyzed job postings (job_postings + latest fraud_predictions +
companies) from the live PostgreSQL OLTP database into a dated, immutable
raw extract under data/raw/warehouse/<run_id>/job_postings_raw.csv.

This is a DIFFERENT pipeline from pipelines/generate_dataset.py +
ingest.py/clean.py/load.py, which produce synthetic LABELED training data
for the ML model. This pipeline instead processes REAL postings the
application has already analyzed, to build an analytics warehouse for the
dashboard (Pipeline Health, Company Trust, Fraud Trends). The two
pipelines don't share state and can be run independently.

Supports two extraction modes:
  - FULL (default): every posting in job_postings, as before.
  - INCREMENTAL (--since <ISO timestamp>): only postings created at or
    after that timestamp. The WHERE clause is parameterized (:since),
    never string-interpolated, so this is not a SQL-injection surface.

Usage:
    python ingest_jobs.py --run-id <run_id>
    python ingest_jobs.py --run-id <run_id> --since 2026-01-01T00:00:00Z
"""
import argparse
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parent.parent / "data"
RAW_WAREHOUSE_DIR = BASE / "raw" / "warehouse"

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://securehire:securehire@localhost:5432/securehire"
)

_BASE_QUERY = """
    SELECT
        jp.id                 AS job_id,
        jp.title,
        jp.raw_text,
        jp.location,
        jp.normalized_location,
        jp.employment_type,
        jp.salary_min,
        jp.salary_max,
        jp.contact_email,
        jp.source,
        jp.created_at,
        c.id                  AS company_id,
        c.name                AS company_name,
        c.website             AS company_website,
        c.trust_score         AS company_trust_score,
        fp.fraud_probability,
        fp.risk_category,
        fp.confidence         AS fraud_confidence,
        fp.model_version
    FROM job_postings jp
    LEFT JOIN companies c ON c.id = jp.company_id
    LEFT JOIN LATERAL (
        SELECT * FROM fraud_predictions fp2
        WHERE fp2.job_id = jp.id ORDER BY fp2.predicted_at DESC LIMIT 1
    ) fp ON true
    {where_clause}
    ORDER BY jp.created_at
"""

FULL_EXTRACT_QUERY = text(_BASE_QUERY.format(where_clause=""))
INCREMENTAL_EXTRACT_QUERY = text(_BASE_QUERY.format(where_clause="WHERE jp.created_at >= :since"))


def ingest(run_id: str, database_url: str = DATABASE_URL, since: datetime | None = None) -> tuple[Path, str]:
    """Returns (output_path, extraction_mode) where extraction_mode is
    'full' or 'incremental' — recorded in pipeline_metrics for
    reproducibility."""
    engine = create_engine(database_url, future=True)
    with engine.connect() as conn:
        if since is not None:
            df = pd.read_sql(INCREMENTAL_EXTRACT_QUERY, conn, params={"since": since})
            mode = "incremental"
        else:
            df = pd.read_sql(FULL_EXTRACT_QUERY, conn)
            mode = "full"

    df["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    df["_run_id"] = run_id

    out_dir = RAW_WAREHOUSE_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "job_postings_raw.csv"
    df.to_csv(out_path, index=False)

    mode_desc = f"incremental (since {since.isoformat()})" if since else "full"
    print(f"[ingest_jobs] extracted {len(df)} rows ({mode_desc}) from the live database -> {out_path}")
    return out_path, mode


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None, help="Pipeline run identifier; auto-generated if omitted")
    parser.add_argument("--since", default=None, help="ISO timestamp — only extract postings created at/after this time (incremental mode). Omit for a full extract.")
    args = parser.parse_args()
    run_id = args.run_id or f"run_{uuid.uuid4().hex[:12]}"
    since_dt = datetime.fromisoformat(args.since.replace("Z", "+00:00")) if args.since else None
    ingest(run_id, since=since_dt)
