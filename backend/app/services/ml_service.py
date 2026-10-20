"""
ml_service.py
--------------
Loads the trained model artifacts produced by `ml/train.py` (shared model
store under /models/<version>/) and exposes a single `predict()` entry
point used by the /jobs/analyze router (via analysis_service.py).

NOTE on architecture: feature engineering logic is mirrored under
app/ml_core/ (copied from the top-level ml/ package) so this service has
no runtime dependency on the offline training package. In a larger
production system this would instead be published as a shared internal
Python package (`securehire-ml-core`) installed by both the training job
and the inference service — noted here and in README as the natural next
refactor.

v1.1.0: predict() now accepts `company_name` (used by the new,
honestly-observable `company_name_missing` feature) and passes RAW
feature values through to explain_prediction() so explanations are gated
by genuine presence, not just SHAP's ranking — see app/ml_core/explain.py
for the full rationale. Also added a loud (never silent) version-drift
warning if the loaded artifacts were trained with different library
versions than are currently installed.
"""
import json
import os
import warnings
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import joblib
import sklearn
import xgboost as xgb
from scipy.sparse import csr_matrix, hstack

from app.core.config import settings  # noqa: F401 — kept for parity/future use
from app.ml_core.explain import (
    build_explanation_text, explain_prediction, risk_category_from_probability,
)
from app.ml_core.feature_engineering import (
    FEATURE_COLUMNS, SKILL_DEMAND, extract_red_flags, extract_skills, red_flags_to_frame,
)
from app.ml_core.preprocess import clean_text

# Resolves the model artifact directory two ways:
#   1. MODELS_ROOT env var (set explicitly, e.g. "/models" inside Docker
#      where docker-compose mounts the repo's top-level models/ folder)
#   2. Falls back to a path relative to this file, for local `uvicorn`
#      dev runs where backend/ and models/ are siblings in the repo.
_env_root = os.environ.get("MODELS_ROOT")
MODELS_ROOT = (
    Path(_env_root) if _env_root
    else Path(__file__).resolve().parent.parent.parent.parent / "models"
)


def _check_environment_drift(model_dir: Path) -> None:
    """Loudly warn (never silently suppress) if the installed ML library
    versions differ from what training used. This is what an
    InconsistentVersionWarning from joblib/sklearn is telling you — ignoring
    it can silently change predictions. See docs/CHANGELOG_FRAUD_FIX.md."""
    env_path = model_dir / "training_env.json"
    if not env_path.exists():
        warnings.warn(
            f"{model_dir} has no training_env.json — this model was trained before "
            "version tracking was added, or with an older train.py. Cannot verify "
            "library-version compatibility; retraining is recommended.",
            stacklevel=2,
        )
        return
    trained_env = json.loads(env_path.read_text())
    mismatches = []
    if trained_env.get("scikit_learn_version") != sklearn.__version__:
        mismatches.append(f"scikit-learn: trained={trained_env.get('scikit_learn_version')} running={sklearn.__version__}")
    if trained_env.get("xgboost_version") != xgb.__version__:
        mismatches.append(f"xgboost: trained={trained_env.get('xgboost_version')} running={xgb.__version__}")
    if mismatches:
        warnings.warn(
            "Model artifacts were trained with different library versions than are "
            "currently installed:\n  " + "\n  ".join(mismatches) +
            "\nThis can silently change predictions. Retrain the model in this exact "
            "environment (see docs/CHANGELOG_FRAUD_FIX.md), or align dependency versions.",
            stacklevel=2,
        )


class FraudPredictor:
    def __init__(self, version: str | None = None):
        self.version = version or self._load_latest_version()
        model_dir = MODELS_ROOT / self.version
        _check_environment_drift(model_dir)
        self.tfidf = joblib.load(model_dir / "tfidf_vectorizer.joblib")
        self.scaler = joblib.load(model_dir / "scaler.joblib")
        self.ensemble = joblib.load(model_dir / "ensemble.joblib")
        self.rf_for_shap = joblib.load(model_dir / "random_forest.joblib")

    @staticmethod
    def _load_latest_version() -> str:
        latest_path = MODELS_ROOT / "latest.json"
        if latest_path.exists():
            return json.loads(latest_path.read_text())["latest_version"]
        versions = sorted(p.name for p in MODELS_ROOT.glob("v*") if p.is_dir())
        if not versions:
            raise FileNotFoundError(
                "No trained model artifacts found. Run `python ml/train.py` first."
            )
        return versions[-1]

    def predict(
        self,
        title: str,
        text: str,
        contact_email: str | None = None,
        salary_min: float | None = None,
        salary_max: float | None = None,
        has_company_website: bool | None = None,
        location: str | None = None,
        company_name: str | None = None,
    ) -> dict:
        red_flags = extract_red_flags(
            title=title, text=text, contact_email=contact_email,
            salary_min=salary_min, salary_max=salary_max,
            has_company_website=has_company_website, location=location,
            company_name=company_name,
        )
        raw_feature_values = asdict(red_flags)

        red_flags_df = red_flags_to_frame([red_flags])
        red_flags_scaled = self.scaler.transform(red_flags_df[FEATURE_COLUMNS])

        tfidf_vec = self.tfidf.transform([clean_text(text)])
        X = hstack([csr_matrix(red_flags_scaled), tfidf_vec]).tocsr()

        proba = float(self.ensemble.predict_proba(X)[0][1])
        fraud_probability = round(proba * 100, 2)
        risk_category = risk_category_from_probability(fraud_probability)

        top_features = explain_prediction(
            self.rf_for_shap, X.toarray(), raw_feature_values,
            n_red_flag_features=len(FEATURE_COLUMNS),
        )
        explanation_text = build_explanation_text(top_features, risk_category, fraud_probability)
        confidence = round(abs(proba - 0.5) * 200, 2)

        skills = extract_skills(text)
        skills_info = [
            {"skill_name": s, "demand_level": SKILL_DEMAND.get(s, "Medium"), "is_required": True}
            for s in skills
        ]

        return {
            "fraud_probability": fraud_probability,
            "risk_category": risk_category,
            "confidence": confidence,
            "model_version": self.version,
            "top_features": top_features,
            "explanation_text": explanation_text,
            "skills": skills_info,
            # Additive — the full raw (unscaled) red-flag feature snapshot
            # for this prediction, persisted to job_features for audit/
            # debugging/future-retraining use. Existing callers that only
            # read the keys above are unaffected.
            "raw_features": raw_feature_values,
        }


@lru_cache(maxsize=1)
def get_predictor() -> FraudPredictor:
    """Singleton loader — model artifacts are loaded once per process,
    not once per request (they're several MB and loading is not free)."""
    return FraudPredictor(version=None)
