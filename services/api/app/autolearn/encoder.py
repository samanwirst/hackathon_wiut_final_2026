"""Frozen pretrained image embedding encoder (M3-AC3).

A genuine torchvision ResNet18 with ImageNet1K_V1 weights, parameters frozen and
the module held in ``eval()`` so outputs are deterministic. The final fully
connected layer is removed; the 512-dim global-average-pooled feature vector is
the embedding. CPU only, two threads, matching the limited host.

The pretrained weights download once into the torch hub cache. If they are not
present and cannot be fetched, encoding raises ``EncoderUnavailable`` rather than
silently substituting random features — a random encoder would produce a
meaningless "trained" Student.
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

import numpy as np
import torch

from app import config

ENCODER_NAME = "resnet18"
# Recorded weight identity/version. The torchvision filename embeds the sha256
# prefix of the checkpoint (resnet18-f37072fd.pth), so this doubles as a weight
# hash tag that changes if the weights ever change.
WEIGHTS_VERSION = "IMAGENET1K_V1"
PREPROCESS_VERSION = "resnet18-imagenet1k-v1-rgb-224-centercrop"
EMBED_DIM = 512


class EncoderUnavailable(RuntimeError):
    """Pretrained weights are unavailable; no embeddings can be produced."""


_lock = threading.Lock()
_encoder: "FrozenEncoder | None" = None


class FrozenEncoder:
    def __init__(self) -> None:
        torch.set_num_threads(max(1, config.THREAD_COUNT))
        try:
            from torchvision.models import ResNet18_Weights, resnet18
        except Exception as exc:  # pragma: no cover - torchvision missing
            raise EncoderUnavailable(f"torchvision unavailable: {exc}") from exc

        weights = ResNet18_Weights.IMAGENET1K_V1
        self.weights_tag = weights.url.rsplit("/", 1)[-1]  # e.g. resnet18-f37072fd.pth
        try:
            model = resnet18(weights=weights)
        except Exception as exc:  # network/cache failure -> explicit unavailable
            raise EncoderUnavailable(
                f"could not load pretrained {ENCODER_NAME} weights: {exc}"
            ) from exc

        # Drop the classifier head; keep up to the global average pool.
        model.fc = torch.nn.Identity()
        model.eval()
        for p in model.parameters():
            p.requires_grad_(False)
        self.model = model
        self._preprocess = weights.transforms()

    def _load_pil(self, data: bytes):
        from PIL import Image

        img = Image.open(io.BytesIO(data)).convert("RGB")
        return img

    @torch.inference_mode()
    def embed_bytes(self, images: list[bytes]) -> tuple[np.ndarray, list[float]]:
        """Return (N, 512) float32 embeddings and per-image latencies (ms)."""
        if not images:
            return np.zeros((0, EMBED_DIM), dtype=np.float32), []
        out = np.zeros((len(images), EMBED_DIM), dtype=np.float32)
        latencies: list[float] = []
        for i, data in enumerate(images):
            t0 = time.perf_counter()
            tensor = self._preprocess(self._load_pil(data)).unsqueeze(0)
            feat = self.model(tensor).squeeze(0).to(torch.float32).cpu().numpy()
            out[i] = feat
            latencies.append((time.perf_counter() - t0) * 1000.0)
        return out, latencies

    def embed_paths(self, paths: list[str | Path]) -> tuple[np.ndarray, list[float]]:
        blobs = [Path(p).read_bytes() for p in paths]
        return self.embed_bytes(blobs)

    def frozen(self) -> bool:
        return (
            not self.model.training
            and all(not p.requires_grad for p in self.model.parameters())
        )


def get_encoder() -> FrozenEncoder:
    global _encoder
    with _lock:
        if _encoder is None:
            _encoder = FrozenEncoder()
        return _encoder
