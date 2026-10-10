"""QA_ONLY synthetic dataset generator.

DISCLOSURE: these are procedurally generated images, NOT natural footage. They
exist only to exercise the import -> label -> review -> train -> evaluate ->
activate/rollback tooling end to end. No accuracy, latency, or cost number
produced from this data represents real-world quality, and none may be presented
as a VisionFlow result. Real quality requires real Teacher labeling and human
verification on real sessions.

Each session is an independent procedural draw with its own RNG seed, so sessions
are genuinely disjoint groups for leakage-free splitting. The task mirrors the
"occupied vs empty bay" binary.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

import numpy as np

POSITIVE_LABEL = "occupied"
NEGATIVE_LABEL = "empty"


@dataclass
class SyntheticSample:
    session_id: str
    group_key: str
    label: str
    image_bytes: bytes
    image_hash: str


def _render(rng: np.random.Generator, occupied: bool, tint: np.ndarray) -> bytes:
    from PIL import Image, ImageDraw

    w = h = 160
    base = np.clip(tint + rng.normal(0, 6, size=(h, w, 3)), 0, 255).astype(np.uint8)
    img = Image.fromarray(base, "RGB")
    draw = ImageDraw.Draw(img)
    # Floor lane markings (present in both classes).
    for lx in (40, 120):
        draw.line([(lx, 10), (lx, 150)], fill=(210, 210, 210), width=2)
    if occupied:
        # A "vehicle" body: a filled rounded rectangle with two wheels, placed
        # with per-image jitter so images within a class are not identical.
        x0 = int(rng.integers(45, 60))
        y0 = int(rng.integers(50, 70))
        bw = int(rng.integers(45, 60))
        bh = int(rng.integers(30, 40))
        color = tuple(int(c) for c in rng.integers(20, 90, size=3))
        draw.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=8, fill=color)
        draw.ellipse([x0 + 4, y0 + bh - 6, x0 + 16, y0 + bh + 6], fill=(15, 15, 15))
        draw.ellipse([x0 + bw - 16, y0 + bh - 6, x0 + bw - 4, y0 + bh + 6], fill=(15, 15, 15))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def generate_sessions(
    n_sessions: int = 5,
    per_class_per_session: int = 3,
    seed: int = 20260101,
    task_slug: str = "bay",
) -> list[SyntheticSample]:
    """Generate independent sessions, each containing both classes."""
    out: list[SyntheticSample] = []
    for s in range(n_sessions):
        rng = np.random.default_rng(seed + s * 7919)
        tint = rng.integers(70, 150, size=3).astype(np.float64)
        tint = np.broadcast_to(tint, (160, 160, 3)).copy()
        session_id = f"qa-{task_slug}-session-{s:02d}"
        for occupied in (True, False):
            label = POSITIVE_LABEL if occupied else NEGATIVE_LABEL
            for _ in range(per_class_per_session):
                data = _render(rng, occupied, tint)
                out.append(
                    SyntheticSample(
                        session_id=session_id,
                        group_key=session_id,
                        label=label,
                        image_bytes=data,
                        image_hash=hashlib.sha256(data).hexdigest(),
                    )
                )
    return out
