"""
explain.py
-----------
SHAP-based explainability for a single prediction. Uses TreeExplainer for
the RandomForest model (fast, exact for tree ensembles) to attribute the
fraud-probability score to individual features, then maps the top
contributing features back to human-readable descriptions for the UI.

v1.1.0 CRITICAL FIX: SHAP contribution and "the underlying signal is
actually present" are two different questions and were previously
conflated. A tree ensemble can assign a feature nonzero SHAP weight even
when that feature sits at its "off"/zero value (e.g. via interaction
effects with other features, or simply because the "off" value isn't
exactly at the tree splits' pivot points once standardized). Ranking
purely by |SHAP weight| — which the old code did — can therefore surface
a reason like "posting mentions a registration fee" when no fee was ever
mentioned. That is a fabricated explanation, not a statistical nuance.

The fix: `explain_prediction()` now requires the RAW (unscaled,
pre-StandardScaler) feature values alongside the SHAP-derived weights.
SHAP still determines ranking/ordering/direction among *candidate*
reasons, but a reason is only ever included if
`feature_engineering.is_feature_genuinely_present()` confirms the raw
value indicates the signal is actually there. This is the "feature
extraction answers 'was this present', SHAP answers 'how much did it
contribute'" split — both must agree before a reason is shown to a user.

Falls back to the model's own `feature_importances_` if SHAP fails for
any reason (e.g. unsupported estimator), so the API never breaks due to
an explainability library issue — the same presence-gating is applied to
the fallback path too.
"""
import numpy as np
import shap

from app.ml_core.feature_engineering import FEATURE_COLUMNS, is_feature_genuinely_present

FEATURE_DESCRIPTIONS = {
    "has_free_email_domain": "Recruiter contact uses a free/personal email domain instead of a company domain",
    "salary_is_suspicious": "Salary range is unrealistically high or wide for the stated role/level",
    "urgent_language_score": "Posting uses high-pressure urgent-hiring language",
    "company_name_missing": "No company name was provided with this posting",
    "experience_mismatch_score": "Experience requirement is inconsistent with an internship/entry-level title",
    "promo_phrase_count": "Contains promotional/scam-style phrases (e.g. 'earn lakhs', 'guaranteed job')",
    "skill_role_mismatch_score": "This technical role's posting lacks any concrete required technical skills",
    "location_inconsistency": "Location details are inconsistent within the posting",
    "description_length": "Description is unusually short/thin for a genuine posting",
    "exclamation_count": "Excessive use of exclamation marks / hype language",
    "salary_spread_ratio": "Salary min-max spread is abnormally wide",
    "has_registration_fee_mention": "Posting asks the applicant to pay a registration/processing fee — a major scam red flag",
    "requests_informal_contact": "Posting directs applicants to informal channels (WhatsApp/Telegram/personal number) instead of an official process",
}

# Positive/reassuring framing for features that legitimately signal
# trustworthiness when they're at a "good" raw value — used only when a
# feature is a candidate but NOT genuinely present in the risk direction;
# we don't invent reassuring copy for every absent red flag (that would be
# just as noisy as the bug we're fixing), only for the ones worth surfacing.
_REASSURING_DESCRIPTIONS = {
    "has_registration_fee_mention": "No request for a registration or processing fee was found",
    "requests_informal_contact": "Applicants are not directed to informal contact channels",
    "urgent_language_score": "No high-pressure urgent-hiring language was found",
}


def explain_prediction(
    model,
    scaled_feature_row: np.ndarray,
    raw_feature_values: dict[str, float],
    n_red_flag_features: int,
    top_k: int = 5,
) -> list[dict]:
    """
    scaled_feature_row: 1 x N array — the SAME (scaled) feature vector passed
                 to model.predict_proba (scaled red-flag features
                 concatenated with TF-IDF features). Used to compute SHAP
                 attributions.
    raw_feature_values: dict mapping red-flag feature name -> its RAW,
                 unscaled value for this specific prediction. Used to gate
                 which SHAP-ranked candidates are allowed to be shown.
    n_red_flag_features: how many of the leading columns are the interpretable
                 red-flag features (the rest are TF-IDF and are summarized, not
                 shown individually, to keep explanations human-readable).
    """
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(scaled_feature_row, check_additivity=False)
        # SHAP's return shape varies by version:
        #   - list [class0_array, class1_array]                 (older API)
        #   - ndarray (n_samples, n_features)                    (regression/binary-collapsed)
        #   - ndarray (n_samples, n_features, n_classes)          (newer API)
        if isinstance(shap_values, list):
            values = shap_values[1][0]
        else:
            arr = np.asarray(shap_values)
            if arr.ndim == 3:
                values = arr[0, :, 1]  # sample 0, all features, class "1" (fraudulent)
            else:
                values = arr[0]
    except Exception:
        # Fallback: use built-in feature_importances_ as a coarse substitute
        importances = getattr(model, "feature_importances_", None)
        if importances is None:
            return []
        values = importances * scaled_feature_row[0]

    red_flag_values = values[:n_red_flag_features]
    ranked_idx = np.argsort(-np.abs(red_flag_values))

    explanations = []
    for idx in ranked_idx:
        if len(explanations) >= top_k:
            break
        if idx >= len(FEATURE_COLUMNS):
            continue
        feat_name = FEATURE_COLUMNS[idx]
        weight = float(red_flag_values[idx])
        if abs(weight) < 1e-4:
            continue

        raw_value = raw_feature_values.get(feat_name)
        if raw_value is None:
            continue  # unknown/unavailable — never guess

        direction = "increases_risk" if weight > 0 else "decreases_risk"
        genuinely_present = is_feature_genuinely_present(feat_name, raw_value)

        # THE CORE FIX: a "this increases risk" reason is only shown if the
        # raw value actually indicates the signal is present. SHAP's sign
        # and magnitude alone are never sufficient — a nonzero contribution
        # from a feature sitting at its "off" value is a modeling artifact,
        # not a fact about the posting.
        if direction == "increases_risk" and not genuinely_present:
            continue

        # "decreases_risk" reasons are only worth surfacing for the small
        # set of features where a clean/negative reading is itself
        # reassuring and interpretable (see _REASSURING_DESCRIPTIONS);
        # otherwise skip rather than manufacture a description.
        if direction == "decreases_risk":
            if feat_name not in _REASSURING_DESCRIPTIONS or genuinely_present:
                continue
            description = _REASSURING_DESCRIPTIONS[feat_name]
        else:
            description = FEATURE_DESCRIPTIONS.get(feat_name, feat_name)

        explanations.append({
            "feature": feat_name,
            "weight": round(weight, 4),
            "direction": direction,
            "description": description,
        })

    return explanations


def risk_category_from_probability(prob: float) -> str:
    """
    Thresholds are empirically derived from the calibrated probability
    distribution on held-out data (see docs/CHANGELOG_FRAUD_FIX.md for the
    exact methodology): genuinely fraudulent and genuinely legitimate
    postings separate into two tight clusters (~5-10% vs ~94%), with very
    few real postings ever scoring above ~10% and under 2% scoring above
    45%. That bimodal gap is what these cutoffs are placed inside — they
    are not arbitrary round numbers.
    """
    if prob >= 65:
        return "High"
    if prob >= 45:
        return "Medium"
    return "Low"


def build_explanation_text(top_features: list[dict], risk_category: str, fraud_probability: float) -> str:
    risk_reasons = [f["description"] for f in top_features if f["direction"] == "increases_risk"][:3]

    if not risk_reasons:
        if risk_category == "Low":
            return "This posting looks consistent with genuine listings — no specific scam indicators were found in the text provided."
        # Medium/High with no *specific* surfaced reason means the model's
        # overall pattern-matching (text style, structure) is driving the
        # score rather than any single named red flag — say that honestly
        # instead of inventing a reason.
        return (
            f"This posting is classified as {risk_category} risk based on its overall similarity to "
            f"other flagged postings' writing style and structure, rather than any single specific red flag. "
            f"Treat this as a weaker, less certain signal than a posting with named red flags."
        )

    joined = "; ".join(risk_reasons)
    qualifier = "" if fraud_probability >= 60 or fraud_probability < 30 else " (a moderate, not conclusive, signal)"
    return f"Flagged as {risk_category} risk{qualifier} primarily because: {joined}."
