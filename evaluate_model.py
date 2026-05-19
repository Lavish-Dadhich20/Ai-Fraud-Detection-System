

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
    precision_recall_curve,
    average_precision_score,
    f1_score,
    recall_score,
)
import os


def evaluate_model(model, X_test: np.ndarray, y_test: np.ndarray,
                   model_name: str = "Model", threshold: float = 0.5) -> dict:
    """
    Full evaluation suite for a binary fraud classifier.

    Args:
        model:      Trained sklearn-compatible classifier.
        X_test:     Preprocessed test features.
        y_test:     True labels.
        model_name: Display name for plots and logs.
        threshold:  Decision threshold (default 0.5; tune for recall vs precision).

    Returns:
        dict with key metrics.
    """
    # ── Predictions ──────────────────────────────────────────────────────────
    y_prob  = model.predict_proba(X_test)[:, 1]     # fraud probability
    y_pred  = (y_prob >= threshold).astype(int)      # binary prediction

    # ── Console report ────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  EVALUATION REPORT — {model_name}")
    print(f"  Decision threshold: {threshold}")
    print(f"{'='*60}")
    print(classification_report(y_test, y_pred, target_names=["Legit", "Fraud"]))

    roc_auc = roc_auc_score(y_test, y_prob)
    avg_prec = average_precision_score(y_test, y_prob)
    recall   = recall_score(y_test, y_pred)
    f1       = f1_score(y_test, y_pred)

    print(f"  ROC-AUC Score          : {roc_auc:.4f}")
    print(f"  Avg Precision (PR-AUC) : {avg_prec:.4f}")
    print(f"  Recall (fraud)         : {recall:.4f}  ← KEY METRIC")
    print(f"  F1-Score (fraud)       : {f1:.4f}")
    print(f"{'='*60}\n")

    # ── Plots ─────────────────────────────────────────────────────────────────
    os.makedirs("plots", exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle(f"{model_name} — Evaluation Dashboard", fontsize=14, fontweight="bold")

    # 1. Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues",
                xticklabels=["Legit", "Fraud"],
                yticklabels=["Legit", "Fraud"], ax=axes[0])
    axes[0].set_title("Confusion Matrix")
    axes[0].set_ylabel("Actual")
    axes[0].set_xlabel("Predicted")

    # 2. ROC Curve
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    axes[1].plot(fpr, tpr, color="royalblue", lw=2, label=f"AUC = {roc_auc:.3f}")
    axes[1].plot([0, 1], [0, 1], "k--", lw=1, label="Random")
    axes[1].fill_between(fpr, tpr, alpha=0.1, color="royalblue")
    axes[1].set_xlabel("False Positive Rate")
    axes[1].set_ylabel("True Positive Rate (Recall)")
    axes[1].set_title("ROC Curve")
    axes[1].legend()

    # 3. Precision-Recall Curve (more informative for imbalanced datasets)
    prec, rec, _ = precision_recall_curve(y_test, y_prob)
    axes[2].plot(rec, prec, color="darkorange", lw=2, label=f"PR-AUC = {avg_prec:.3f}")
    axes[2].axhline(y_test.mean(), color="gray", linestyle="--", label="Baseline (random)")
    axes[2].set_xlabel("Recall")
    axes[2].set_ylabel("Precision")
    axes[2].set_title("Precision-Recall Curve")
    axes[2].legend()

    plt.tight_layout()
    plot_path = f"plots/{model_name.replace(' ', '_')}_eval.png"
    plt.savefig(plot_path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"[Plot] Saved → {plot_path}")

    return {
        "roc_auc": roc_auc,
        "pr_auc":  avg_prec,
        "recall":  recall,
        "f1":      f1,
    }


def plot_feature_importance(model, feature_names: list, model_name: str = "XGBoost", top_n: int = 15):
    """
    Plot top-N features by importance.

    Works for XGBoost (feature_importances_) and Logistic Regression
    (absolute value of coefficients).
    """
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
        title = f"{model_name} — Feature Importance (Gain)"
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_[0])
        title = f"{model_name} — Feature Importance (|Coefficient|)"
    else:
        print("[FeatureImportance] Model does not expose importances.")
        return

    # Sort and select top N
    idx = np.argsort(importances)[::-1][:top_n]
    top_feats  = [feature_names[i] for i in idx]
    top_scores = importances[idx]

    plt.figure(figsize=(10, 6))
    colors = plt.cm.RdYlGn_r(np.linspace(0.1, 0.9, len(top_feats)))
    bars = plt.barh(top_feats[::-1], top_scores[::-1], color=colors[::-1])
    plt.xlabel("Importance Score")
    plt.title(title)
    plt.tight_layout()

    os.makedirs("plots", exist_ok=True)
    path = f"plots/{model_name.replace(' ', '_')}_feature_importance.png"
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close()
    print(f"[Plot] Feature importance saved → {path}")

    print(f"\n[Feature Importance] Top {top_n} features ({model_name}):")
    for feat, score in zip(top_feats, top_scores):
        print(f"  {feat:<40} {score:.5f}")