"""
data_quality.py
------------------
Lightweight data-quality validation for the warehouse ETL pipeline.

Design choice: hand-rolled rather than Pandera. Pandera is a fine library,
but for this project's actual needs (a handful of null/range/duplicate
checks on one DataFrame shape) it would add a new dependency to
pipelines/requirements.txt (and therefore to the `warehouse_pipeline`
Docker image) for something pure pandas already does cleanly and
transparently — matching the instruction to avoid it "if it can't be
added cleanly." This module intentionally mirrors clean_jobs.py's
existing validate_schema() style rather than introducing a second
validation paradigm into the same pipeline.

Each check produces a DataQualityIssue with a severity:
  - "error"   — the extract itself is untrustworthy; clean_jobs.py halts
                the pipeline rather than silently building a warehouse
                on top of corrupt data (e.g. a null job_id or a fraud
                probability outside [0, 100] should never happen if the
                app is working correctly — if it does, something upstream
                is broken and needs a human to look at it before this
                data is used for anything).
  - "warning" — worth recording and surfacing on the Pipeline Health
                dashboard, but not a reason to stop: e.g. a missing
                company name is EXPECTED, real data (it's one of the ML
                model's own fraud signals), not a pipeline defect.
"""
from dataclasses import asdict, dataclass, field

import pandas as pd


@dataclass
class DataQualityIssue:
    check_name: str
    severity: str  # "error" | "warning"
    row_count: int
    description: str


@dataclass
class DataQualityReport:
    total_rows: int
    issues: list[DataQualityIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def passed(self) -> bool:
        return not self.has_errors

    def to_dict(self) -> dict:
        return {
            "total_rows": self.total_rows,
            "passed": self.passed,
            "issues": [asdict(i) for i in self.issues],
        }

    def summary_line(self) -> str:
        if not self.issues:
            return f"{self.total_rows} rows — no data quality issues found."
        errors = [i for i in self.issues if i.severity == "error"]
        warnings = [i for i in self.issues if i.severity == "warning"]
        return (
            f"{self.total_rows} rows — {len(errors)} error check(s), "
            f"{len(warnings)} warning check(s) flagged."
        )


def validate_job_postings(df: pd.DataFrame) -> DataQualityReport:
    """Runs every check against a job-postings DataFrame (the shape
    produced by clean_jobs.py's staging step) and returns a report.
    Never mutates the input DataFrame."""
    report = DataQualityReport(total_rows=len(df))

    def _add(check_name: str, severity: str, mask: pd.Series, description: str) -> None:
        count = int(mask.sum())
        if count > 0:
            report.issues.append(DataQualityIssue(check_name, severity, count, description))

    # --- job_id must never be null ---
    if "job_id" in df.columns:
        _add(
            "job_id_not_null", "error",
            df["job_id"].isna(),
            "Rows with a null job_id — cannot be traced back to a source posting.",
        )

    # --- title must never be null/empty ---
    if "title" in df.columns:
        title_missing = df["title"].isna() | (df["title"].astype(str).str.strip() == "")
        _add(
            "title_not_null", "error",
            title_missing,
            "Rows with a null or empty title.",
        )

    # --- company_name missing (informational — this is real, expected
    # data, not a pipeline defect: it's one of the ML model's own fraud
    # signals, see company_name_missing in feature_engineering.py) ---
    if "company_name" in df.columns:
        company_missing = df["company_name"].isna() | (df["company_name"].astype(str).str.strip() == "")
        _add(
            "company_name_missing", "warning",
            company_missing,
            "Rows with no company name — expected for some postings (a known fraud signal), not necessarily a defect.",
        )

    # --- fraud_probability must be within [0, 100] where present ---
    if "fraud_probability" in df.columns:
        numeric = pd.to_numeric(df["fraud_probability"], errors="coerce")
        out_of_range = numeric.notna() & ((numeric < 0) | (numeric > 100))
        _add(
            "fraud_probability_range", "error",
            out_of_range,
            "fraud_probability values outside the valid [0, 100] range.",
        )

    # --- duplicate job_id within the same extract batch ---
    if "job_id" in df.columns:
        dup_mask = df["job_id"].duplicated(keep=False) & df["job_id"].notna()
        _add(
            "duplicate_job_id", "warning",
            dup_mask,
            "job_id appears more than once in this extract batch (downstream dedup in clean_and_normalize() already handles this, but it's worth knowing if the extract query itself is producing duplicates).",
        )

    # --- invalid/unparseable timestamps ---
    if "created_at" in df.columns:
        parsed = pd.to_datetime(df["created_at"], errors="coerce")
        invalid_ts = parsed.isna() & df["created_at"].notna()
        _add(
            "invalid_timestamp", "warning",
            invalid_ts,
            "created_at values that could not be parsed as a valid timestamp.",
        )

    # --- invalid salary ranges: negative, or min > max ---
    if "salary_min" in df.columns and "salary_max" in df.columns:
        smin = pd.to_numeric(df["salary_min"], errors="coerce")
        smax = pd.to_numeric(df["salary_max"], errors="coerce")
        negative = (smin < 0) | (smax < 0)
        inverted = smin.notna() & smax.notna() & (smin > smax) & (smax > 0)
        _add(
            "negative_salary", "warning",
            negative.fillna(False),
            "Rows with a negative salary_min or salary_max.",
        )
        _add(
            "inverted_salary_range", "warning",
            inverted.fillna(False),
            "Rows where salary_min > salary_max.",
        )

    return report
