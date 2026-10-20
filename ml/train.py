"""
train.py
---------
Trains and compares Logistic Regression, Random Forest, XGBoost, and a
soft-voting Ensemble on the fake-job-posting classification task.

Feature vector = [hand-crafted red-flag features] + [TF-IDF text features]

v1.1.0 CHANGES:
  - Feature schema changed (see feature_engineering.py) — this is a
    BREAKING change to the model's input shape, hence the model version
    bump. Old v1.0.0 artifacts are NOT compatible with this code and must
    not be loaded by it.
  - Training data now spans many job categories, not just technical roles
    (see pipelines/generate_dataset.py) — this directly targets the
    generalization gap that caused legitimate non-technical postings to
    be scored as suspicious.
  - Added probability calibration: the ensemble's raw soft-voted
    predict_proba is not automatically a calibrated probability. We fit
    the ensemble on a training split, then calibrate its probability
    output against a held-out calibration split (never used for fitting)
    via CalibratedClassifierCV(cv="prefit"). The held-out TEST split
    (never used for fitting OR calibration) is used only for final
    evaluation, so reported metrics are not optimistic.
  - Records exact installed library versions to training_env.json so the
    inference service can detect (and loudly warn about, not silently
    hide) a version mismatch — see backend/app/services/ml_service.py.

Artifacts (versioned under models/<MODEL_VERSION>/):
    tfidf_vectorizer.joblib
    scaler.joblib
    logistic_regression.joblib
    random_forest.joblib          (uncalibrated — used directly for SHAP)
    xgboost.joblib
    ensemble.joblib                (CALIBRATED — used for predict_proba)
    feature_columns.json
    metrics.json
    training_env.json

Run:
    python train.py
"""
import json
import platform
import sys
from pathlib import Path

import joblib
import numpy as np
import sklearn
import xgboost as xgb
from scipy.sparse import hstack, csr_matrix
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler

from evaluate import evaluate_model
from feature_engineering import FEATURE_COLUMNS
from preprocess import build_feature_matrix, load_training_data

MODEL_VERSION = "v1.1.0"
MODELS_DIR = Path(__file__).resolve().parent.parent / "models" / MODEL_VERSION


def main():
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading + preprocessing data...")
    df = load_training_data()
    red_flags_df, texts, labels = build_feature_matrix(df)

    # --- TF-IDF text features ---
    tfidf = TfidfVectorizer(max_features=500, stop_words="english", ngram_range=(1, 2))
    tfidf_matrix = tfidf.fit_transform(texts)

    # --- scale hand-crafted features, then concatenate with sparse TF-IDF ---
    scaler = StandardScaler()
    red_flags_scaled = scaler.fit_transform(red_flags_df[FEATURE_COLUMNS])
    X = hstack([csr_matrix(red_flags_scaled), tfidf_matrix]).tocsr()
    y = labels.values

    # 3-way split: fit / calibration / test. Test is never seen by fitting
    # or calibration, so evaluation metrics reflect genuine generalization.
    X_trainval, X_test, y_trainval, y_test = train_test_split(
        X, y, test_size=0.15, random_state=42, stratify=y
    )
    X_train, X_calib, y_train, y_calib = train_test_split(
        X_trainval, y_trainval, test_size=0.15, random_state=42, stratify=y_trainval
    )
    print(f"Fit size: {X_train.shape}, Calibration size: {X_calib.shape}, Test size: {X_test.shape}")

    models = {
        "logistic_regression": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=300, max_depth=12, class_weight="balanced", random_state=42, n_jobs=-1
        ),
        "xgboost": xgb.XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.08,
            eval_metric="logloss", random_state=42,
        ),
    }

    results = {}
    for name, model in models.items():
        print(f"\nTraining {name}...")
        cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring="f1")
        model.fit(X_train, y_train)
        metrics = evaluate_model(model, X_test, y_test, name)
        metrics["cv_f1_mean"] = float(np.mean(cv_scores))
        metrics["cv_f1_std"] = float(np.std(cv_scores))
        results[name] = metrics
        joblib.dump(model, MODELS_DIR / f"{name}.joblib")

    # --- Soft-voting ensemble of all three, fit on the FIT split only ---
    print("\nTraining ensemble (soft voting)...")
    ensemble = VotingClassifier(
        estimators=[(k, v) for k, v in models.items()], voting="soft", n_jobs=-1
    )
    ensemble.fit(X_train, y_train)

    # Uncalibrated metrics, for comparison against the calibrated version.
    uncalibrated_metrics = evaluate_model(ensemble, X_test, y_test, "ensemble (uncalibrated)")

    # --- Calibrate probability output on the held-out calibration split ---
    # This is what makes "41% fraud probability" mean something closer to
    # "if we saw 100 postings the model scored around 41%, roughly 41 of
    # them would actually be fraudulent" — a soft-voting ensemble's raw
    # averaged probabilities are not guaranteed to have that property.
    print("\nCalibrating ensemble probabilities...")
    calibrated_ensemble = CalibratedClassifierCV(ensemble, method="sigmoid", cv="prefit")
    calibrated_ensemble.fit(X_calib, y_calib)
    calibrated_metrics = evaluate_model(calibrated_ensemble, X_test, y_test, "ensemble (calibrated)")
    calibrated_metrics["uncalibrated_comparison"] = uncalibrated_metrics
    results["ensemble"] = calibrated_metrics
    joblib.dump(calibrated_ensemble, MODELS_DIR / "ensemble.joblib")

    # --- persist preprocessing artifacts + metadata ---
    joblib.dump(tfidf, MODELS_DIR / "tfidf_vectorizer.joblib")
    joblib.dump(scaler, MODELS_DIR / "scaler.joblib")
    with open(MODELS_DIR / "feature_columns.json", "w") as f:
        json.dump(FEATURE_COLUMNS, f, indent=2)
    with open(MODELS_DIR / "metrics.json", "w") as f:
        json.dump(results, f, indent=2)

    # Exact environment snapshot — lets the inference service detect (and
    # clearly warn about) a version mismatch instead of silently loading a
    # pickle built by a different scikit-learn/xgboost version. See
    # backend/app/services/ml_service.py's startup version check.
    training_env = {
        "python_version": sys.version,
        "platform": platform.platform(),
        "scikit_learn_version": sklearn.__version__,
        "xgboost_version": xgb.__version__,
        "numpy_version": np.__version__,
        "model_version": MODEL_VERSION,
    }
    with open(MODELS_DIR / "training_env.json", "w") as f:
        json.dump(training_env, f, indent=2)

    # also drop a copy at models/latest -> for backend to load without version pinning
    latest_link_info = {"latest_version": MODEL_VERSION}
    with open(MODELS_DIR.parent / "latest.json", "w") as f:
        json.dump(latest_link_info, f, indent=2)

    print("\n=== Model comparison (held-out test set) ===")
    print(f"{'Model':<28}{'Accuracy':<10}{'Precision':<11}{'Recall':<9}{'F1':<8}{'CV-F1':<8}")
    for name, m in results.items():
        cv = m.get("cv_f1_mean", float("nan"))
        print(f"{name:<28}{m['accuracy']:<10.3f}{m['precision']:<11.3f}{m['recall']:<9.3f}{m['f1']:<8.3f}{cv:<8.3f}")

    print(f"\nTraining environment: scikit-learn={sklearn.__version__}, xgboost={xgb.__version__}, numpy={np.__version__}")
    print(f"✅ Artifacts saved to {MODELS_DIR}")


if __name__ == "__main__":
    main()
