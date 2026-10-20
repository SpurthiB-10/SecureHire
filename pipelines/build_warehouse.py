"""
build_warehouse.py — Warehouse ETL Stage 4: BUILD WAREHOUSE
-----------------------------------------------------------------
Takes the curated (enriched) data, writes the final warehouse-ready
parquet snapshot to data/warehouse/<run_id>/, and records this pipeline
run's metrics into the `pipeline_metrics` table (see docs/schema.sql)
for the Pipeline Health dashboard and as a reproducibility log.

Note: this does NOT write job postings or fraud predictions into new
warehouse-specific database tables — `job_postings` and
`fraud_predictions` already ARE the source-of-record tables (this
pipeline reads FROM them via ingest_jobs.py), and `v_warehouse_job_fact`
(a SQL view, see docs/schema.sql) is the flat denormalized join the
analytics dashboard queries. Writing a duplicate copy into a second set
of tables would just create a second, driftable source of truth for the
same facts — the warehouse VIEW avoids that while still giving the
dashboard the flat, pre-joined shape it needs.
"""
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parent.parent / "data"
WAREHOUSE_DIR = BASE / "warehouse"

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://securehire:securehire@localhost:5432/securehire"
)


def record_pipeline_metrics(
    run_id: str,
    rows_ingested: int,
    rows_cleaned: int,
    duplicates_removed: int,
    fraud_rows_detected: int,
    pipeline_duration_seconds: float,
    rows_enriched: int = 0,
    rows_loaded: int = 0,
    extraction_mode: str = "full",
    since_timestamp: datetime | None = None,
    data_quality_passed: bool | None = None,
    data_quality_issues: list | None = None,
    status: str = "success",
    error_message: str | None = None,
    database_url: str = DATABASE_URL,
) -> None:
    import json

    engine = create_engine(database_url, future=True)
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO pipeline_metrics (
                    run_id, extraction_mode, since_timestamp,
                    rows_ingested, rows_cleaned, rows_enriched, rows_loaded,
                    duplicates_removed, fraud_rows_detected,
                    data_quality_passed, data_quality_issues,
                    pipeline_duration_seconds, status, error_message
                ) VALUES (
                    :run_id, :extraction_mode, :since_timestamp,
                    :rows_ingested, :rows_cleaned, :rows_enriched, :rows_loaded,
                    :duplicates_removed, :fraud_rows_detected,
                    :data_quality_passed, :data_quality_issues,
                    :duration, :status, :error_message
                )
                ON CONFLICT (run_id) DO UPDATE SET
                    extraction_mode = EXCLUDED.extraction_mode,
                    since_timestamp = EXCLUDED.since_timestamp,
                    rows_ingested = EXCLUDED.rows_ingested,
                    rows_cleaned = EXCLUDED.rows_cleaned,
                    rows_enriched = EXCLUDED.rows_enriched,
                    rows_loaded = EXCLUDED.rows_loaded,
                    duplicates_removed = EXCLUDED.duplicates_removed,
                    fraud_rows_detected = EXCLUDED.fraud_rows_detected,
                    data_quality_passed = EXCLUDED.data_quality_passed,
                    data_quality_issues = EXCLUDED.data_quality_issues,
                    pipeline_duration_seconds = EXCLUDED.pipeline_duration_seconds,
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message
            """),
            {
                "run_id": run_id, "extraction_mode": extraction_mode, "since_timestamp": since_timestamp,
                "rows_ingested": rows_ingested, "rows_cleaned": rows_cleaned,
                "rows_enriched": rows_enriched, "rows_loaded": rows_loaded,
                "duplicates_removed": duplicates_removed, "fraud_rows_detected": fraud_rows_detected,
                "data_quality_passed": data_quality_passed,
                "data_quality_issues": json.dumps(data_quality_issues) if data_quality_issues is not None else None,
                "duration": pipeline_duration_seconds, "status": status, "error_message": error_message,
            },
        )
    print(f"[build_warehouse] recorded pipeline_metrics for run_id={run_id} (mode={extraction_mode})")


def run(
    curated_parquet: Path,
    run_id: str,
    rows_ingested: int,
    rows_cleaned: int,
    duplicates_removed: int,
    pipeline_duration_seconds: float,
    rows_enriched: int | None = None,
    extraction_mode: str = "full",
    since_timestamp: datetime | None = None,
    data_quality_passed: bool | None = None,
    data_quality_issues: list | None = None,
    load_metrics_to_db: bool = True,
) -> Path:
    df = pd.read_parquet(curated_parquet)
    rows_loaded = len(df)
    # enrich_jobs.py doesn't currently drop rows (only adds derived
    # columns), so rows_enriched defaults to the loaded count when not
    # explicitly passed — tracked as its own number rather than silently
    # reusing rows_cleaned, so a future change that DOES filter during
    # enrichment is reflected correctly without touching this function.
    if rows_enriched is None:
        rows_enriched = rows_loaded

    out_dir = WAREHOUSE_DIR / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "job_postings_warehouse.parquet"
    df.to_parquet(out_path, index=False)
    print(f"[build_warehouse] wrote warehouse snapshot ({rows_loaded} rows) -> {out_path}")

    fraud_rows_detected = int(df.get("is_high_risk", pd.Series(dtype=bool)).sum())

    if load_metrics_to_db:
        record_pipeline_metrics(
            run_id=run_id, rows_ingested=rows_ingested, rows_cleaned=rows_cleaned,
            rows_enriched=rows_enriched, rows_loaded=rows_loaded,
            duplicates_removed=duplicates_removed, fraud_rows_detected=fraud_rows_detected,
            pipeline_duration_seconds=pipeline_duration_seconds,
            extraction_mode=extraction_mode, since_timestamp=since_timestamp,
            data_quality_passed=data_quality_passed, data_quality_issues=data_quality_issues,
        )

    return out_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--curated-parquet", required=True)
    parser.add_argument("--rows-ingested", type=int, required=True)
    parser.add_argument("--rows-cleaned", type=int, required=True)
    parser.add_argument("--duplicates-removed", type=int, required=True)
    parser.add_argument("--duration-seconds", type=float, required=True)
    parser.add_argument("--no-db", action="store_true", help="Skip writing pipeline_metrics to Postgres")
    args = parser.parse_args()
    run(
        Path(args.curated_parquet), args.run_id, args.rows_ingested, args.rows_cleaned,
        args.duplicates_removed, args.duration_seconds, load_metrics_to_db=not args.no_db,
    )
