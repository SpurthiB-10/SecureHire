"""
evaluate.py
------------
Shared evaluation utilities: computes accuracy/precision/recall/F1 and a
confusion matrix for a fitted model against a held-out test set. Used by
train.py after fitting each candidate model, and can be re-run standalone
against saved artifacts for a model-performance report.
"""
from pathlib import Path

import numpy as np
from sklearn.metrics import (
    accuracy_score, confusion_matrix, f1_score, precision_score,
    recall_score, roc_auc_score,
)

REPORTS_DIR = Path(__file__).resolve().parent.parent / "docs" / "model_reports"


def evaluate_model(model, X_test, y_test, name: str) -> dict:
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1] if hasattr(model, "predict_proba") else y_pred

    cm = confusion_matrix(y_test, y_pred)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "confusion_matrix": cm.tolist(),  # [[TN, FP], [FN, TP]]
    }
    print(f"\n--- {name} ---")
    print(f"Accuracy={metrics['accuracy']:.3f}  Precision={metrics['precision']:.3f}  "
          f"Recall={metrics['recall']:.3f}  F1={metrics['f1']:.3f}  ROC-AUC={metrics['roc_auc']:.3f}")
    print(f"Confusion matrix [[TN,FP],[FN,TP]]: {cm.tolist()}")
    return metrics


def plot_confusion_matrix(cm: list[list[int]], name: str, out_dir: Path = REPORTS_DIR) -> Path:
    import matplotlib.pyplot as plt

    out_dir.mkdir(parents=True, exist_ok=True)
    cm_arr = np.array(cm)
    fig, ax = plt.subplots(figsize=(4, 4))
    ax.imshow(cm_arr, cmap="Blues")
    ax.set_xticks([0, 1], labels=["Pred: Real", "Pred: Fake"])
    ax.set_yticks([0, 1], labels=["True: Real", "True: Fake"])
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm_arr[i, j]), ha="center", va="center", color="black")
    ax.set_title(f"Confusion Matrix — {name}")
    out_path = out_dir / f"confusion_matrix_{name}.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
