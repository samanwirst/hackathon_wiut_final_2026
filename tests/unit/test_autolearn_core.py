"""Unit tests for the AutoLearn ML core: dataset splitting, Student fit/save/load,
metrics, threshold selection, and offline labeling validation.

Embedding vectors here are synthetic numpy arrays used ONLY to exercise the
classifier/metrics contracts deterministically — they are a disclosed stand-in
for the real frozen encoder, which is exercised separately in the integration
test and the encoder test.
"""

import numpy as np
import pytest

from app.autolearn import dataset, labeling, metrics
from app.autolearn.student import StudentClassifier


# ------------------------------------------------------------------ dataset split


def _rows(spec):
    """spec: list of (group_key, image_hash, label)."""
    return [dataset.SampleRow(id=i, group_key=g, image_hash=h, label=l) for i, (g, h, l) in enumerate(spec)]


def test_split_is_session_disjoint_and_leakage_free():
    spec = []
    for s in range(6):  # six independent sessions, both classes each
        for k in range(2):
            spec.append((f"s{s}", f"h{s}_{k}_pos", "occupied"))
            spec.append((f"s{s}", f"h{s}_{k}_neg", "empty"))
    plan = dataset.build_split(_rows(spec), min_train_groups=2, min_val_groups=1, min_test_groups=1)
    # No group appears in more than one split.
    group_to_split = plan.group_split
    assert len(group_to_split) == 6
    # Every sample assigned; splits cover all.
    assert sum(plan.counts.values()) == len(spec)
    # Train and test both contain both classes.
    for split in ("train", "test"):
        assert plan.class_counts[split]["occupied"] > 0
        assert plan.class_counts[split]["empty"] > 0


def test_split_refuses_insufficient_groups():
    spec = [("s0", "a", "occupied"), ("s0", "b", "empty")]
    with pytest.raises(dataset.DatasetError):
        dataset.build_split(_rows(spec), min_train_groups=2, min_val_groups=1, min_test_groups=1)


def test_split_refuses_missing_class():
    spec = [(f"s{i}", f"h{i}", "occupied") for i in range(5)]
    with pytest.raises(dataset.DatasetError):
        dataset.build_split(_rows(spec), min_train_groups=2, min_val_groups=1, min_test_groups=1)


def test_split_detects_identical_content_leakage():
    # Same image_hash shared across two different groups -> leakage.
    spec = [
        ("s0", "dup", "occupied"), ("s0", "h1", "empty"),
        ("s1", "dup", "occupied"), ("s1", "h2", "empty"),
        ("s2", "h3", "occupied"), ("s2", "h4", "empty"),
        ("s3", "h5", "occupied"), ("s3", "h6", "empty"),
    ]
    with pytest.raises(dataset.DatasetError, match="identical image"):
        dataset.build_split(_rows(spec), min_train_groups=2, min_val_groups=1, min_test_groups=1)


# ------------------------------------------------------------------ student


def _separable(n=40, dim=16, seed=0):
    rng = np.random.default_rng(seed)
    neg = rng.normal(-1.0, 0.5, size=(n, dim))
    pos = rng.normal(1.0, 0.5, size=(n, dim))
    X = np.vstack([neg, pos]).astype(np.float32)
    y = np.array([0] * n + [1] * n, dtype=np.int64)
    return X, y


def test_student_fits_and_reload_matches(tmp_path):
    X, y = _separable()
    clf = StudentClassifier(in_dim=16, classes=["empty", "occupied"])
    res = clf.fit(X, y, epochs=300)
    assert res.duration_ms > 0
    probs = clf.predict_proba(X)
    # Genuinely learns the separable split.
    acc = float(np.mean((probs >= 0.5).astype(int) == y))
    assert acc > 0.9

    path = tmp_path / "student.pt"
    clf.save(str(path), extra={"threshold": 0.5})
    reloaded = StudentClassifier.load(str(path))
    np.testing.assert_allclose(reloaded.predict_proba(X), probs, rtol=0, atol=1e-6)


def test_student_requires_both_classes():
    X = np.zeros((5, 16), dtype=np.float32)
    y = np.zeros(5, dtype=np.int64)
    with pytest.raises(ValueError):
        StudentClassifier(in_dim=16, classes=["a", "b"]).fit(X, y)


# ------------------------------------------------------------------ metrics


def test_binary_metrics_values():
    y_true = np.array([1, 1, 0, 0, 1])
    y_pred = np.array([1, 0, 0, 1, 1])
    m = metrics.binary_metrics(y_true, y_pred)
    assert m["confusion_matrix"] == {"tp": 2, "fp": 1, "fn": 1, "tn": 1}
    assert m["support"] == 5
    assert 0.0 <= m["f1"] <= 1.0


def test_threshold_selection_on_val_only():
    probs = np.array([0.1, 0.2, 0.8, 0.9])
    y = np.array([0, 0, 1, 1])
    t, f1 = metrics.select_threshold(probs, y)
    assert f1 == 1.0
    assert 0.2 < t < 0.8


def test_latency_percentiles():
    p = metrics.latency_percentiles([10.0, 20.0, 30.0, 40.0])
    assert p["count"] == 4
    assert p["p50_ms"] is not None


# ------------------------------------------------------------------ labeling validation


def test_parse_strict_accepts_valid():
    label, conf, err = labeling._parse_strict('{"label": "occupied", "confidence": 0.9}', ["occupied", "empty"])
    assert err == ""
    assert label == "occupied"
    assert conf == 0.9


def test_parse_strict_rejects_non_json():
    _, _, err = labeling._parse_strict("the bay is occupied", ["occupied", "empty"])
    assert err


def test_parse_strict_rejects_unknown_label():
    _, _, err = labeling._parse_strict('{"label": "banana", "confidence": 0.9}', ["occupied", "empty"])
    assert "permitted" in err


def test_parse_strict_rejects_bad_confidence():
    for bad in ('{"label": "empty", "confidence": "high"}',
                '{"label": "empty", "confidence": 2.0}',
                '{"label": "empty"}'):
        _, _, err = labeling._parse_strict(bad, ["occupied", "empty"])
        assert err


def test_parse_strict_tolerates_code_fence():
    label, conf, err = labeling._parse_strict('```json\n{"label": "empty", "confidence": 0.7}\n```', ["occupied", "empty"])
    assert err == ""
    assert label == "empty"


def test_classify_unavailable_without_provider(monkeypatch):
    monkeypatch.setattr(labeling.config, "VLM_BASE_URL", "")
    monkeypatch.setattr(labeling.config, "VLM_MODEL", "")
    assert labeling.provider_configured() is False
    cand = labeling.classify_sync(b"not-a-real-image", prompt="is it occupied?", labels=["occupied", "empty"])
    assert cand.status == "unavailable"
    assert cand.label is None
