"""
ingest.py — ETL Stage 1: INGEST
--------------------------------
Reads raw job posting files (CSV/JSON) from data/raw/, tags each record
with a source + ingestion timestamp, and writes them unmodified (append-only)
into the data lake's "landing" partition: data/raw/_landing/<date>/.

This mirrors how a real pipeline would land files from S3/GCS/local drops
before any cleaning happens — raw data is never mutated in place.
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent.parent / "data"
RAW_DIR = BASE / "raw"


def _read_any(path: Path) -> pd.DataFrame:
    if path.suffix == ".csv":
        return pd.read_csv(path)
    if path.suffix == ".json":
        with open(path) as f:
            data = json.load(f)
        return pd.DataFrame(data if isinstance(data, list) else data.get("records", []))
    raise ValueError(f"Unsupported file type: {path.suffix}")


def ingest(source_dir: Path = RAW_DIR) -> Path:
    date_partition = datetime.utcnow().strftime("%Y-%m-%d")
    landing_dir = RAW_DIR / "_landing" / date_partition
    landing_dir.mkdir(parents=True, exist_ok=True)

    files = [p for p in source_dir.glob("*") if p.suffix in (".csv", ".json")]
    if not files:
        raise FileNotFoundError(
            f"No .csv/.json files found in {source_dir}. "
            "Run generate_dataset.py first, or drop a dataset file here."
        )

    frames = []
    for f in files:
        df = _read_any(f)
        df["_source_file"] = f.name
        df["_ingested_at"] = datetime.utcnow().isoformat()
        frames.append(df)
        print(f"[ingest] read {len(df)} rows from {f.name}")

    combined = pd.concat(frames, ignore_index=True)
    out_path = landing_dir / "job_postings_landed.parquet"
    combined.to_parquet(out_path, index=False)
    print(f"[ingest] wrote {len(combined)} rows -> {out_path}")
    return out_path


if __name__ == "__main__":
    ingest()
