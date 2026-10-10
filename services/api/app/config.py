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

# Comma-separated URL prefixes that send_webhook actions may target.
WEBHOOK_ALLOWLIST = [
    p.strip()
    for p in os.environ.get("WEBHOOK_ALLOWLIST", "").split(",")
    if p.strip()
]

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
