"""Lightweight Student classifier (M3-AC3).

A genuine binary logistic-regression model implemented in torch: embeddings are
standardized with the training mean/std, then a single linear layer is fitted by
full-batch gradient descent with a fixed seed (deterministic). The artifact
stores weights, standardization, class mapping, encoder/preprocess identity,
dataset/split hashes, training duration and environment so a reloaded model
reproduces the same predictions bit-for-bit.

No sklearn dependency is introduced; this is a real fitted classifier, not a
decorative progress bar.
"""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass

import numpy as np
import torch


@dataclass
class TrainResult:
    duration_ms: float
    final_loss: float
    epochs: int


class StudentClassifier:
    """Binary logistic regression over frozen embeddings.

    ``classes[0]`` is the negative class (label 0) and ``classes[1]`` the
    positive class (label 1). ``predict_proba`` returns P(positive)."""

    def __init__(self, in_dim: int, classes: list[str]):
        if len(classes) != 2:
            raise ValueError("StudentClassifier supports exactly two classes")
        self.in_dim = in_dim
        self.classes = list(classes)
        self._mean = np.zeros(in_dim, dtype=np.float32)
        self._std = np.ones(in_dim, dtype=np.float32)
        self._w = np.zeros(in_dim, dtype=np.float32)
        self._b = 0.0
        self.fitted = False

    # -- training ----------------------------------------------------------
    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        *,
        epochs: int = 400,
        lr: float = 0.05,
        weight_decay: float = 1e-3,
        seed: int = 1234,
    ) -> TrainResult:
        if X.ndim != 2 or X.shape[1] != self.in_dim:
            raise ValueError(f"X must be (N,{self.in_dim})")
        if len(np.unique(y)) < 2:
            raise ValueError("training labels must contain both classes")
        torch.manual_seed(seed)
        t0 = time.perf_counter()

        self._mean = X.mean(axis=0).astype(np.float32)
        std = X.std(axis=0).astype(np.float32)
        std[std < 1e-6] = 1.0
        self._std = std
        Xs = (X - self._mean) / self._std

        xt = torch.from_numpy(Xs.astype(np.float32))
        yt = torch.from_numpy(y.astype(np.float32)).unsqueeze(1)
        linear = torch.nn.Linear(self.in_dim, 1)
        torch.nn.init.zeros_(linear.weight)
        torch.nn.init.zeros_(linear.bias)
        opt = torch.optim.Adam(linear.parameters(), lr=lr, weight_decay=weight_decay)
        loss_fn = torch.nn.BCEWithLogitsLoss()
        final_loss = 0.0
        for _ in range(epochs):
            opt.zero_grad()
            logits = linear(xt)
            loss = loss_fn(logits, yt)
            loss.backward()
            opt.step()
            final_loss = float(loss.item())

        with torch.inference_mode():
            self._w = linear.weight.detach().squeeze(0).numpy().astype(np.float32)
            self._b = float(linear.bias.detach().item())
        self.fitted = True
        return TrainResult(
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            final_loss=final_loss,
            epochs=epochs,
        )

    # -- inference ---------------------------------------------------------
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.fitted:
            raise RuntimeError("classifier is not fitted")
        Xs = (X - self._mean) / self._std
        logits = Xs @ self._w + self._b
        return 1.0 / (1.0 + np.exp(-logits))

    def predict(self, X: np.ndarray, threshold: float = 0.5) -> np.ndarray:
        return (self.predict_proba(X) >= threshold).astype(np.int64)

    # -- persistence -------------------------------------------------------
    def state(self) -> dict:
        return {
            "in_dim": self.in_dim,
            "classes": self.classes,
            "mean": self._mean,
            "std": self._std,
            "w": self._w,
            "b": self._b,
            "fitted": self.fitted,
        }

    def save(self, path: str, *, extra: dict | None = None) -> None:
        payload = {"model": self.state(), "extra": extra or {}}
        torch.save(payload, path)

    @classmethod
    def load(cls, path: str) -> "StudentClassifier":
        payload = torch.load(path, weights_only=False)
        s = payload["model"]
        clf = cls(s["in_dim"], s["classes"])
        clf._mean = np.asarray(s["mean"], dtype=np.float32)
        clf._std = np.asarray(s["std"], dtype=np.float32)
        clf._w = np.asarray(s["w"], dtype=np.float32)
        clf._b = float(s["b"])
        clf.fitted = bool(s["fitted"])
        # Saved training provenance (threshold, class_mapping, encoder/preprocess
        # identity, dataset/split hashes) so a loader can verify the artifact
        # matches its registry row before trusting it (C-008/C-009).
        clf.extra = dict(payload.get("extra") or {})
        return clf


def environment_info() -> dict:
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "numpy": np.__version__,
        "threads": torch.get_num_threads(),
    }
