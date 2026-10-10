"""Dataset assembly and leakage-free splitting (M3-AC2).

Only human-verified labels enter training. Splitting is done at the
group/session level so adjacent frames and common generated source assets never
straddle the train/val/test boundary. Exact-duplicate images (same content hash)
that would appear in more than one split are treated as leakage and refused. The
held-out test set is never used for fitting or threshold selection.

The module refuses to build a split (raising ``DatasetError``) rather than invent
an evaluation when a class is missing or there are too few independent groups.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass

import numpy as np


class DatasetError(ValueError):
    """Dataset is insufficient or leaky; refuse to build a split."""


@dataclass
class SampleRow:
    id: int
    group_key: str
    image_hash: str
    label: str  # the immutable human-verified label
    # Optional normalized decoded-pixel fingerprint (flattened 32x32 RGB float
    # array) for conservative near-duplicate detection across groups (a
    # decode/re-encode of the same frame). ``None`` when pixel data was
    # unavailable to compute it.
    fingerprint: "np.ndarray | None" = None


@dataclass
class SplitPlan:
    assignments: dict[int, str]  # sample_id -> train|val|test
    group_split: dict[str, str]  # group_key -> split
    counts: dict[str, int]
    class_counts: dict[str, dict[str, int]]
    dataset_hash: str
    split_hash: str
    class_mapping: dict[str, int]  # label -> 0/1


def _stable_order(keys: list[str]) -> list[str]:
    """Deterministic, label-independent ordering of group keys."""
    return sorted(keys, key=lambda k: hashlib.sha1(k.encode()).hexdigest())


def build_split(
    rows: list[SampleRow],
    *,
    min_train_groups: int,
    min_val_groups: int,
    min_test_groups: int,
    near_dup_max_mad: float = 0.0,
) -> SplitPlan:
    verified = [r for r in rows if r.label]
    if not verified:
        raise DatasetError("no verified samples available for training")

    labels = sorted({r.label for r in verified})
    if len(labels) != 2:
        raise DatasetError(
            f"binary task requires exactly two verified classes, found {labels or 'none'}"
        )
    class_mapping = {labels[0]: 0, labels[1]: 1}

    groups: dict[str, list[SampleRow]] = defaultdict(list)
    for r in verified:
        groups[r.group_key].append(r)

    # Exact-duplicate leakage check: a content hash must not appear in two groups
    # (which could then land in different splits).
    hash_to_groups: dict[str, set[str]] = defaultdict(set)
    for r in verified:
        hash_to_groups[r.image_hash].add(r.group_key)
    leaked = {h: g for h, g in hash_to_groups.items() if len(g) > 1}
    if leaked:
        raise DatasetError(
            f"identical image content appears across {len(leaked)} group(s); "
            "refusing to split to prevent leakage"
        )

    # Conservative near-duplicate leakage check (C-003): a decode/re-encode of the
    # same frame has a different content hash but near-identical decoded pixels.
    # If two rows in DIFFERENT groups have a mean-absolute decoded-pixel
    # difference below a small, FIXED threshold, they could straddle the split, so
    # refuse. Decoded-pixel MAD (unlike a perceptual hash) preserves global tint,
    # so independent scenes are not falsely flagged. Never tuned on held-out data.
    if near_dup_max_mad > 0:
        fp = [r for r in verified if r.fingerprint is not None]
        for i in range(len(fp)):
            for j in range(i + 1, len(fp)):
                a, b = fp[i], fp[j]
                if a.group_key == b.group_key:
                    continue
                mad = float(np.abs(a.fingerprint - b.fingerprint).mean())
                if mad <= near_dup_max_mad:
                    raise DatasetError(
                        "near-duplicate image content appears across groups "
                        f"{a.group_key!r} and {b.group_key!r} (decoded-pixel MAD "
                        f"{mad:.3f} <= {near_dup_max_mad}); refusing to split to prevent leakage"
                    )

    ordered = _stable_order(list(groups))
    need = min_train_groups + min_val_groups + min_test_groups
    if len(ordered) < need:
        raise DatasetError(
            f"insufficient independent groups: have {len(ordered)}, need at least {need} "
            f"(train>={min_train_groups}, val>={min_val_groups}, test>={min_test_groups})"
        )

    n = len(ordered)
    n_test = max(min_test_groups, round(n * 0.25))
    n_val = max(min_val_groups, round(n * 0.15))
    n_train = n - n_test - n_val
    if n_train < min_train_groups:
        # shrink held-out shares to protect the minimum training requirement
        overflow = min_train_groups - n_train
        take = min(overflow, n_test - min_test_groups)
        n_test -= take
        overflow -= take
        n_val -= min(overflow, n_val - min_val_groups)
        n_train = n - n_test - n_val
    if n_train < min_train_groups:
        raise DatasetError("cannot satisfy minimum group requirements with current data")

    group_split: dict[str, str] = {}
    for i, key in enumerate(ordered):
        if i < n_test:
            group_split[key] = "test"
        elif i < n_test + n_val:
            group_split[key] = "val"
        else:
            group_split[key] = "train"

    assignments: dict[int, str] = {}
    counts: dict[str, int] = {"train": 0, "val": 0, "test": 0}
    class_counts: dict[str, dict[str, int]] = {
        s: {labels[0]: 0, labels[1]: 0} for s in ("train", "val", "test")
    }
    for key, members in groups.items():
        split = group_split[key]
        for r in members:
            assignments[r.id] = split
            counts[split] += 1
            class_counts[split][r.label] += 1

    # A meaningful fit/evaluation needs both classes in train and in test.
    for split in ("train", "test"):
        present = [lbl for lbl, c in class_counts[split].items() if c > 0]
        if len(present) < 2:
            raise DatasetError(
                f"{split} split does not contain both classes ({class_counts[split]}); "
                "add more diverse independent sessions"
            )

    dataset_hash = _hash_rows(verified)
    split_hash = hashlib.sha256(
        "|".join(f"{k}:{group_split[k]}" for k in ordered).encode()
    ).hexdigest()

    return SplitPlan(
        assignments=assignments,
        group_split=group_split,
        counts=counts,
        class_counts=class_counts,
        dataset_hash=dataset_hash,
        split_hash=split_hash,
        class_mapping=class_mapping,
    )


def _hash_rows(rows: list[SampleRow]) -> str:
    items = sorted(f"{r.image_hash}:{r.label}" for r in rows)
    return hashlib.sha256("|".join(items).encode()).hexdigest()
