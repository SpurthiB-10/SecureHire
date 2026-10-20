# Fraud Detection Fix — v1.0.0 → v1.1.0

## The reported bug

A real Google Careers posting ("Product Manager, AI Platform Operations
and Tooling") was scored **41.21% fraud probability, Medium Risk**, with
explanations claiming a registration fee, urgent-hiring language, a wide
suspicious salary spread, and a technical-skill mismatch — **none of which
were present in the actual posting text.**

## Root causes (each confirmed by direct reproduction before fixing)

### 1. `has_company_website` was always `False` in production
`backend/app/services/analysis_service.py` computed:
```python
has_company_website=company.website is not None if company else False
```
`company.website` is never populated anywhere in the codebase — there is
no frontend field, no scraper, nothing that ever sets it. So this
expression evaluates to `False` on **every single request**, forever.

During training (`ml/preprocess.py`), this same field was a genuinely
accurate boolean from the synthetic dataset generator (~90% correlated
with the true label). The model learned it as a strong predictive
feature. At inference, that same feature is permanently pinned to "missing
info" for every request — a severe train/serve skew that inflates every
prediction, including Google's.

**Fix:** `has_company_website` is no longer used to compute any fraud
signal. The feature it drove (`missing_company_info`) was replaced with
`company_name_missing`, derived from whether a company name was actually
supplied — something the product genuinely, always knows.

### 2. Word-boundary-free regex misclassified the PM role as "technical"
```python
pattern = r"data|engineer|developer|analyst|scientist|ml|ai"
re.search(pattern, "Product Manager, AI Platform Operations and Tooling")
# -> matches "AI" as a bare substring
```
Confirmed directly:
```python
>>> import re
>>> re.search(r"data|engineer|developer|analyst|scientist|ml|ai",
...            "Product Manager, AI Platform Operations and Tooling", re.IGNORECASE)
<re.Match object; span=(19,21), match='AI'>
```
This misclassified the posting as a hands-on technical role requiring
Python/SQL/etc., triggering a false "lacks concrete technical skills" flag.

**Fix:** `TECHNICAL_IC_ROLE_PATTERN` in `feature_engineering.py` is now a
whitelist regex over actual individual-contributor technical titles
(`Software Engineer`, `Data Scientist`, `ML Engineer`, etc.), with
mandatory word boundaries. Product/Program Managers, Marketing, HR,
Sales, Finance, Design, Healthcare, Operations, Support, Admin, and
Teaching roles are never held to a "must mention Python/SQL" standard.

### 3. SHAP contribution was treated as proof a red flag exists
`explain.py`'s old `explain_prediction()` ranked candidate reasons purely
by `|SHAP weight|` and displayed the canned description whenever
`direction == "increases_risk"` — with no check on whether the underlying
raw feature value indicated the signal was actually present. A tree
ensemble can assign nonzero SHAP attribution to a feature sitting at its
"off" value (via interaction effects with other features); that is a
statistical artifact of the model's internals, not a fact about the
posting.

**Fix:** `explain_prediction()` now requires the raw, unscaled feature
values alongside SHAP weights. `is_feature_genuinely_present()` gates
every candidate reason — SHAP determines ranking/ordering among
candidates, but presence-in-the-text is a hard requirement before a
reason is ever shown to a user. Regression-tested directly against the
trained model in `tests/test_explain.py`.

### 4. Training data had zero non-technical roles
`pipelines/generate_dataset.py` previously generated exactly 8 role
titles, all technical/data (`Data Engineer Intern`, `Data Analyst`,
`Machine Learning Intern`, etc.) — for BOTH the real and fake examples.
The model never saw a single legitimate Marketing/HR/Sales/PM/Finance/
Teaching/Healthcare/Operations/Support/Admin/Design posting during
training. Anything that didn't "look technical" was, by construction,
out-of-distribution relative to every legitimate example the model had
ever seen.

**Fix:** the dataset generator now spans 12 categories (see
`CATEGORIES` dict), each with category-appropriate legitimate
qualifications and category-appropriate scam templates (scams target
every job category, not just tech — "Data Entry from home", "Customer
Support work from home", and "HR Assistant, no experience" are extremely
common real-world scam categories). ~6,000 rows, verified balanced
across categories at generation time.

### 5. No probability calibration
A soft-voting ensemble's averaged `predict_proba` output is not
automatically a calibrated probability — there's no guarantee that "41%"
means "41 times out of 100, this would actually be fraud."

**Fix:** `ml/train.py` now fits the ensemble on a training split, then
calibrates its probability output against a **held-out calibration
split** (never used for fitting) via
`CalibratedClassifierCV(method="sigmoid", cv="prefit")`. Final evaluation
uses a third, fully held-out test split.

### 6. Risk category thresholds were arbitrary
The original Low/Medium/High cutoffs (35/70) were not derived from any
data. After retraining, we computed the actual calibrated score
distribution on held-out data:

```
FAKE (label=1) score percentiles [5,10,25,50,75,90]:  [5.4, 6.7, 93.2, 94.3, 94.6, 94.7]
REAL (label=0) score percentiles [50,75,90,95,99]:      [9.6, ... , 94.2 (rare outlier)]

Fraction of REAL postings scoring >= 45%: 2.08%
Fraction of REAL postings scoring >= 60%: 2.08%
Fraction of FAKE postings scoring >= 60%: 87.2%
```
The distribution is strongly bimodal — most postings land firmly in one
of two clusters (~5-10% or ~94%), with a sparse "genuinely ambiguous"
middle band. Thresholds were placed inside that gap:

```python
if prob >= 65: return "High"
if prob >= 45: return "Medium"
return "Low"
```

**Known, disclosed limitation:** a short, single-paragraph scam message
that doesn't closely match the training data's typical scam-text density
(multiple stacked red flags, longer text) can land in "Medium" rather
than "High," even when every red flag it does contain is correctly and
honestly identified. Lowering the High threshold further to catch every
such example would push it below the point where ~2% of genuine postings
also start scoring that high — a worse trade-off. This is documented in
`tests/test_explain.py`'s `test_obvious_scam_scores_elevated_risk_with_real_reasons`.

### 7. Skill extraction substring bug (found during this fix, unrelated to the original report)
`extract_skills()` used naive substring matching: `"excel" in text` also
matches inside `"excellent"`. Fixed with word-boundary regex matching.

## Dependency version consistency (the `InconsistentVersionWarning`)

`backend/requirements.txt`, `ml/requirements.txt`, and
`pipelines/requirements.txt` in this repo already pin identical versions
(`scikit-learn==1.5.1`, `xgboost==2.1.1`, etc.) — that was not the source
of the warning. The far more likely cause: training on a host machine's
raw Python environment (e.g. via `pip install -r ml/requirements.txt` in
PowerShell) can silently resolve a *different* wheel than what's pinned,
if the host Python version doesn't have a matching wheel available, or if
an existing global install shadows the pin.

**Fix:** `docker/docker-compose.yml` now has a `trainer` service that
reuses the exact same image/pinned dependencies as the `backend` service
(built from `Dockerfile.backend`). Training inside this container makes
version drift impossible by construction. `ml/train.py` and
`backend/app/services/ml_service.py` also now record/check exact library
versions (`training_env.json`) and **warn loudly** (never silently
suppress) on any mismatch.

## Model version

Model artifacts moved from `v1.0.0` to `v1.1.0` — this is a **breaking
change to the feature schema** (columns renamed/added). Old `v1.0.0`
artifacts are incompatible with this code and were removed; you must
retrain (see README.md / DEPLOY.md for the exact command).
