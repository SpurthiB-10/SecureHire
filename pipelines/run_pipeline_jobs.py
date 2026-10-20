"""
run_pipeline_jobs.py — orchestrates the full warehouse ETL DAG:
ingest_jobs -> clean_jobs -> enrich_jobs -> build_warehouse.

Named distinctly from pipelines/run_pipeline.py (which orchestrates the
ML-training-data pipeline: generate_dataset -> ingest -> clean -> load)
so the two independent pipelines are never confused for one another.

Supports incremental extraction via --since, without changing the
default (full-refresh) behavior when it's omitted:

Usage:
    python run_pipeline_jobs.py                          # full refresh (default, unchanged)
    python run_pipeline_jobs.py --since 2026-01-01        # only postings created on/after this date
    python run_pipeline_jobs.py --since 2026-01-01T00:00:00Z
    python run_pipeline_jobs.py --no-db                   # skip writing pipeline_metrics (e.g. no DB available)

NOTE ON ORCHESTRATION: this script IS the real, runnable orchestrator —
running it is how the pipeline actually executes today, in Docker or
locally. pipelines/airflow_dag.py is a REFERENCE implementation showing
how these same task functions would be wired into a scheduled Airflow
DAG in a production deployment; no Airflow scheduler is actually running
anywhere in this project. Don't describe the DAG as "in production" —
it isn't; it's a design artifact.
"""
import argparse
import time
import uuid
from datetime import datetime

from build_warehouse import run as run_build_warehouse
from clean_jobs import run as run_clean_jobs
from enrich_jobs import run as run_enrich_jobs
from ingest_jobs import ingest as run_ingest_jobs


def main(load_db: bool = True, since: datetime | None = None) -> None:
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    start = time.monotonic()
    mode_desc = f"incremental, since {since.isoformat()}" if since else "full refresh"
    print(f"=== SecureHire AI Warehouse ETL Pipeline — run_id={run_id} ({mode_desc}) ===")

    try:
        print("\n[1/4] INGEST (from live PostgreSQL)")
        raw_path, extraction_mode = run_ingest_jobs(run_id, since=since)

        print("\n[2/4] CLEAN (staging + processed + data quality)")
        clean_path, clean_metrics = run_clean_jobs(raw_path, run_id)

        print("\n[3/4] ENRICH (curated)")
        curated_path = run_enrich_jobs(clean_path, run_id)

        print("\n[4/4] BUILD WAREHOUSE")
        duration = time.monotonic() - start
        dq = clean_metrics.get("data_quality", {})
        warehouse_path = run_build_warehouse(
            curated_parquet=curated_path,
            run_id=run_id,
            rows_ingested=clean_metrics["rows_ingested"],
            rows_cleaned=clean_metrics["rows_cleaned"],
            duplicates_removed=clean_metrics["duplicates_removed"],
            pipeline_duration_seconds=duration,
            extraction_mode=extraction_mode,
            since_timestamp=since,
            data_quality_passed=dq.get("passed"),
            data_quality_issues=dq.get("issues"),
            load_metrics_to_db=load_db,
        )

        print(f"\n✅ Pipeline complete in {duration:.2f}s ({mode_desc}). Warehouse snapshot: {warehouse_path}")

    except Exception as exc:
        duration = time.monotonic() - start
        print(f"\n❌ Pipeline FAILED after {duration:.2f}s: {exc}")
        if load_db:
            try:
                from build_warehouse import record_pipeline_metrics
                record_pipeline_metrics(
                    run_id=run_id, rows_ingested=0, rows_cleaned=0, duplicates_removed=0,
                    fraud_rows_detected=0, pipeline_duration_seconds=duration,
                    extraction_mode="incremental" if since else "full", since_timestamp=since,
                    status="failed", error_message=str(exc),
                )
            except Exception as log_exc:
                print(f"(also failed to record the failure to pipeline_metrics: {log_exc})")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-db", action="store_true")
    parser.add_argument(
        "--since", default=None,
        help="ISO timestamp (e.g. 2026-01-01 or 2026-01-01T00:00:00Z). "
             "If supplied, only extracts postings created at/after this time "
             "(incremental mode). If omitted, behaves exactly as before: a "
             "full extract of every posting (unchanged default behavior).",
    )
    args = parser.parse_args()
    since_dt = datetime.fromisoformat(args.since.replace("Z", "+00:00")) if args.since else None
    main(load_db=not args.no_db, since=since_dt)
