"""
predict.py
-----------
Loads the trained ensemble + preprocessing artifacts and scores a single
new job posting end-to-end: feature engineering -> vectorize -> predict
-> explain. This is the function the FastAPI backend calls (see
backend/app/services/ml_service.py, which mirrors this logic for the
live service so the ML package stays a standalone, testable unit).

CLI usage:
    python predict.py --title "Data Entry Intern" --text "Earn 90000/week..."
"""
import argparse
import json
import warnings
from dataclasses import asdict
from pathlib import Path

import joblib
import sklearn
import xgboost as xgb
from scipy.sparse import hstack, csr_matrix

from evaluate import REPORTS_DIR  # noqa: F401 (kept for symmetry / potential reporting use)
from explain import build_explanation_text, explain_prediction, risk_category_from_probability
from feature_engineering import FEATURE_COLUMNS, extract_red_flags, extract_skills, red_flags_to_frame, SKILL_DEMAND
from preprocess import clean_text

MODELS_ROOT = Path(__file__).resolve().parent.parent / "models"


def load_latest_version() -> str:
    latest_path = MODELS_ROOT / "latest.json"
    if latest_path.exists():
        return json.loads(latest_path.read_text())["latest_version"]
    # fall back to the newest versioned directory present
    versions = sorted([p.name for p in MODELS_ROOT.glob("v*") if p.is_dir()])
    if not versions:
        raise FileNotFoundError("No trained model artifacts found. Run train.py first.")
    return versions[-1]


def _check_environment_drift(model_dir: Path) -> None:
    """Loudly warn (never silently suppress) if the installed ML library
    versions differ from what training used — an InconsistentVersionWarning
    from joblib/sklearn means the pickled estimator's internals may not
    match the running library's expectations."""
    env_path = model_dir / "training_env.json"
    if not env_path.exists():
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
            "environment, or align dependency versions. See docs/CHANGELOG_FRAUD_FIX.md.",
            stacklevel=2,
        )


class FraudPredictor:
    def __init__(self, version: str | None = None):
        self.version = version or load_latest_version()
        model_dir = MODELS_ROOT / self.version
        _check_environment_drift(model_dir)
        self.tfidf = joblib.load(model_dir / "tfidf_vectorizer.joblib")
        self.scaler = joblib.load(model_dir / "scaler.joblib")
        self.ensemble = joblib.load(model_dir / "ensemble.joblib")
        # RandomForest sub-estimator is used for SHAP TreeExplainer (fast + exact)
        self.rf_for_shap = joblib.load(model_dir / "random_forest.joblib")

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

        clean = clean_text(text)
        tfidf_vec = self.tfidf.transform([clean])

        X = hstack([csr_matrix(red_flags_scaled), tfidf_vec]).tocsr()

        proba = self.ensemble.predict_proba(X)[0][1]
        fraud_probability = round(float(proba) * 100, 2)
        risk_category = risk_category_from_probability(fraud_probability)

        top_features = explain_prediction(
            self.rf_for_shap, X.toarray(), raw_feature_values,
            n_red_flag_features=len(FEATURE_COLUMNS),
        )
        explanation_text = build_explanation_text(top_features, risk_category, fraud_probability)

        skills = extract_skills(text)
        skills_info = [
            {"skill_name": s, "demand_level": SKILL_DEMAND.get(s, "Medium"), "is_required": True}
            for s in skills
        ]

        # crude confidence heuristic: distance from decision boundary (0.5).
        # NOTE: this reflects decision margin, not calibrated certainty — a
        # 50%-adjacent score is inherently low-confidence regardless of how
        # this number is framed. See explain.py's build_explanation_text for
        # how this distinction is communicated to the user.
        confidence = round(abs(proba - 0.5) * 200, 2)

        return {
            "fraud_probability": fraud_probability,
            "risk_category": risk_category,
            "confidence": confidence,
            "model_version": self.version,
            "top_features": top_features,
            "explanation_text": explanation_text,
            "skills": skills_info,
            "raw_features": raw_feature_values,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--email", default=None)
    parser.add_argument("--company", default=None)
    parser.add_argument("--salary_min", type=float, default=None)
    parser.add_argument("--salary_max", type=float, default=None)
    args = parser.parse_args()

    predictor = FraudPredictor()
    result = predictor.predict(
        title=args.title, text=args.text, contact_email=args.email,
        salary_min=args.salary_min, salary_max=args.salary_max,
        company_name=args.company,
    )
    print(json.dumps(result, indent=2))
