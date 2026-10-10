"""Held-out evaluation metrics computed from real predictions (M3-AC4).

All values are derived from predicted vs verified ground-truth rows. Nothing is
hardcoded. Teacher/Student disagreement is reported separately from accuracy.
"""

from __future__ import annotations

import numpy as np


def binary_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Positive class = 1. Returns confusion counts and P/R/F1/accuracy."""
    y_true = np.asarray(y_true).astype(np.int64)
    y_pred = np.asarray(y_pred).astype(np.int64)
    if y_true.shape != y_pred.shape:
        raise ValueError("y_true and y_pred must align")
    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))
    n = tp + tn + fp + fn
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    accuracy = (tp + tn) / n if n else 0.0
    return {
        "confusion_matrix": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "support": n,
        "positives": int(np.sum(y_true == 1)),
        "negatives": int(np.sum(y_true == 0)),
    }


def latency_percentiles(latencies_ms: list[float]) -> dict:
    if not latencies_ms:
        return {"count": 0, "p50_ms": None, "p95_ms": None}
    arr = np.asarray(latencies_ms, dtype=np.float64)
    return {
        "count": int(arr.size),
        "p50_ms": round(float(np.percentile(arr, 50)), 3),
        "p95_ms": round(float(np.percentile(arr, 95)), 3),
    }


def disagreement_rate(student_pred: list, teacher_pred: list) -> dict:
    """Fraction of items where Student and Teacher labels differ (both present)."""
    pairs = [
        (s, t)
        for s, t in zip(student_pred, teacher_pred)
        if s is not None and t is not None
    ]
    if not pairs:
        return {"compared": 0, "disagreements": 0, "rate": None}
    dis = sum(1 for s, t in pairs if s != t)
    return {
        "compared": len(pairs),
        "disagreements": dis,
        "rate": round(dis / len(pairs), 4),
    }


def select_threshold(probs: np.ndarray, y_true: np.ndarray) -> tuple[float, float]:
    """Pick the threshold maximizing F1 on the *validation* set only.

    Returns (threshold, f1_at_threshold). Candidate thresholds are the midpoints
    between sorted unique probabilities, so selection never touches the test set.
    """
    probs = np.asarray(probs, dtype=np.float64)
    y_true = np.asarray(y_true).astype(np.int64)
    uniq = np.unique(probs)
    if uniq.size == 0:
        return 0.5, 0.0
    candidates = [0.5]
    if uniq.size == 1:
        candidates.append(float(uniq[0]))
    else:
        mids = (uniq[:-1] + uniq[1:]) / 2.0
        candidates.extend(float(m) for m in mids)
        candidates.append(float(uniq[0] - 1e-6))
        candidates.append(float(uniq[-1] + 1e-6))
    best_t, best_f1 = 0.5, -1.0
    for t in candidates:
        pred = (probs >= t).astype(np.int64)
        m = binary_metrics(y_true, pred)
        if m["f1"] > best_f1:
            best_f1, best_t = m["f1"], t
    return round(best_t, 6), round(best_f1, 4)
