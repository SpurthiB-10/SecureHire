"""
run_pipeline.py — orchestrates the full ETL DAG: ingest -> clean -> load.

This script is the *runnable* version of the pipeline (no Airflow install
required). `airflow_dag.py` in this same folder shows how the identical
tasks would be wired up as a real Airflow DAG in production, with the
same task functions imported and used as PythonOperator callables —
i.e. the pipeline logic is decoupled from the orchestrator.

Usage:
    python run_pipeline.py --load-db
"""
import argparse
from pathlib import Path

from clean import run as run_clean
from ingest import ingest
from load import run as run_load

BASE = Path(__file__).resolve().parent.parent / "data"


def main(load_db: bool = False) -> None:
    print("=== SecureHire AI ETL Pipeline ===")

    print("\n[1/3] INGEST")
    landed_path = ingest()

    print("\n[2/3] CLEAN & NORMALIZE")
    clean_path = run_clean(landed_path)

    print("\n[3/3] CURATE & LOAD")
    curated_path = run_load(clean_path, load_db=load_db)

    print(f"\n✅ Pipeline complete. Curated data at: {curated_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--load-db", action="store_true", help="Also load into PostgreSQL")
    args = parser.parse_args()
    main(load_db=args.load_db)
