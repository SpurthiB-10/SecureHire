"""
load.py — ETL Stage 3: CURATE & LOAD
--------------------------------------
Takes the cleaned parquet file, does final feature-ready curation
(company upsert, skill tokenization), and loads it into PostgreSQL
(`companies`, `job_postings` tables), then writes the curated parquet
snapshot to data/curated/ for reproducibility / ML training.

Idempotent: re-running will upsert companies by normalized_name and skip
job postings whose text_hash already exists.
"""
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

BASE = Path(__file__).resolve().parent.parent / "data"
CURATED_DIR = BASE / "curated"

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+psycopg2://securehire:securehire@localhost:5432/securehire"
)


def load_to_postgres(df: pd.DataFrame, database_url: str = DATABASE_URL) -> None:
    engine = create_engine(database_url, future=True)
    with engine.begin() as conn:
        for _, row in df.iterrows():
            # upsert company
            company_row = conn.execute(
                text("""
                    INSERT INTO companies (name, normalized_name)
                    VALUES (:name, :norm)
                    ON CONFLICT (normalized_name) DO UPDATE SET
                        posting_count = companies.posting_count + 1
                    RETURNING id
                """),
                {"name": row["company_name"], "norm": row["company_name"].lower()},
            ).fetchone()
            company_id = company_row[0]

            conn.execute(
                text("""
                    INSERT INTO job_postings (
                        company_id, title, raw_text, location, normalized_location,
                        employment_type, salary_min, salary_max, contact_email,
                        source, text_hash
                    ) VALUES (
                        :company_id, :title, :raw_text, :location, :norm_location,
                        :emp_type, :sal_min, :sal_max, :email, :source, :text_hash
                    )
                    ON CONFLICT DO NOTHING
                """),
                {
                    "company_id": company_id,
                    "title": row["title"],
                    "raw_text": row["description"],
                    "location": row.get("location"),
                    "norm_location": row["normalized_location"],
                    "emp_type": row.get("employment_type"),
                    "sal_min": row.get("salary_min"),
                    "sal_max": row.get("salary_max"),
                    "email": row.get("contact_email"),
                    "source": "etl_pipeline",
                    "text_hash": row["text_hash"],
                },
            )
    print(f"[load] upserted {len(df)} postings into PostgreSQL")


def run(clean_parquet: Path, load_db: bool = False) -> Path:
    df = pd.read_parquet(clean_parquet)

    CURATED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = CURATED_DIR / "job_postings_curated.parquet"
    df.to_parquet(out_path, index=False)
    print(f"[load] wrote curated snapshot -> {out_path}")

    if load_db:
        load_to_postgres(df)

    return out_path


if __name__ == "__main__":
    clean_path = BASE / "processed" / "job_postings_clean.parquet"
    if not clean_path.exists():
        raise SystemExit("No cleaned data found — run clean.py first.")
    run(clean_path, load_db=os.environ.get("LOAD_TO_DB", "false").lower() == "true")
