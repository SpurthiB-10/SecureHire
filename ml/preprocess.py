"""
preprocess.py
--------------
Loads curated data (from data/curated/) and prepares it for model
training: text cleaning for NLP vectorization + red-flag feature matrix
+ label vector.

v1.1.0: now passes `company_name` through to `extract_red_flags()` so the
`company_name_missing` feature is trained on the same real signal it will
see at inference time (see feature_engineering.py's module docstring for
why the old `has_company_website`-based feature was removed).
"""
import re
from pathlib import Path

import pandas as pd

from feature_engineering import extract_red_flags, red_flags_to_frame

CURATED_PATH = Path(__file__).resolve().parent.parent / "data" / "curated" / "job_postings_curated.parquet"
RAW_LABELED_PATH = Path(__file__).resolve().parent.parent / "data" / "raw" / "job_postings.csv"


def clean_text(text: str) -> str:
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"[^a-zA-Z0-9\s.,!?%]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_training_data() -> pd.DataFrame:
    """
    Training needs the `fraudulent` label, which lives in the raw
    generated/source dataset (curated data in the DB pipeline path
    doesn't carry labels since real-world postings aren't pre-labeled).
    """
    if not RAW_LABELED_PATH.exists():
        raise FileNotFoundError(
            f"{RAW_LABELED_PATH} not found. Run pipelines/generate_dataset.py first."
        )
    df = pd.read_csv(RAW_LABELED_PATH)
    df["description"] = df["description"].fillna("").astype(str)
    df["clean_text"] = df["description"].apply(clean_text)
    return df


def build_feature_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    """Returns (red_flag_features_df, clean_text_series, labels_series)."""
    red_flags = []
    for _, row in df.iterrows():
        rf = extract_red_flags(
            title=str(row.get("title", "")),
            text=str(row.get("description", "")),
            contact_email=row.get("contact_email"),
            salary_min=row.get("salary_min"),
            salary_max=row.get("salary_max"),
            has_company_website=row.get("has_company_website"),
            location=row.get("location"),
            company_name=row.get("company_name"),
        )
        red_flags.append(rf)

    feature_df = red_flags_to_frame(red_flags)
    return feature_df, df["clean_text"], df["fraudulent"]


if __name__ == "__main__":
    df = load_training_data()
    features, texts, labels = build_feature_matrix(df)
    print(features.describe())
    print("Label balance:\n", labels.value_counts(normalize=True))
