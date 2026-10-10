"""Runtime configuration from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = services/api/app/config.py -> three levels up
REPO_ROOT = Path(__file__).resolve().parents[3]

DATA_DIR = Path(os.environ.get("VISIONFLOW_DATA_DIR", REPO_ROOT / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
EVIDENCE_DIR = DATA_DIR / "evidence"
DB_PATH = DATA_DIR / "visionflow.db"

MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "200"))
PROCESS_FPS = float(os.environ.get("PROCESS_FPS", "5"))
DETECTOR_MODEL = os.environ.get("DETECTOR_MODEL", "yolo11n.pt")
DETECTOR_CONFIDENCE = float(os.environ.get("DETECTOR_CONFIDENCE", "0.35"))
DETECTOR_DEVICE = os.environ.get("DETECTOR_DEVICE", "cpu")

# Minimum fraction of the container-reported frame count that must actually be
# decoded for a run to count as complete. A larger shortfall indicates a
# truncated/corrupt upload and is surfaced as a failed source rather than
# silently reported "processed" (M1-013). Tolerance absorbs the small
# frame-count inaccuracies some codecs report.
DECODE_MIN_COMPLETENESS = float(os.environ.get("DECODE_MIN_COMPLETENESS", "0.9"))

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if o.strip()
]


def ensure_dirs() -> None:
    for d in (UPLOAD_DIR, SNAPSHOT_DIR, EVIDENCE_DIR):
        d.mkdir(parents=True, exist_ok=True)
