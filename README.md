# VisionFlow AI — WIUT Hackathon Final 2026

Visual AI automation for automotive operations: upload a video (or connect a
camera), draw a zone, describe a condition, and get real detections turned into
events, evidence, and authorized actions. Track: Computer Vision.

The official task is in [docs/source/README.md](docs/source/README.md);
product requirements in [docs/PRD.md](docs/PRD.md);
architecture in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Current state (M1)

Working end-to-end pipeline: **MP4 upload → YOLO11n detection + ByteTrack
tracking → polygon-zone temporal events (enter / exit / dwell / count) →
SQLite persistence + evidence JPEG → authorized action (notification,
allowlisted webhook) → web UI** (upload, canvas zone drawing, workflow
builder, event timeline).

## Run locally

Requirements: Python 3.11+ (3.14 tested), Node 20+, ~1 GB disk for ML wheels.

### Backend

```sh
cd services/api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --port 8000
```

First processing run downloads YOLO11n weights (~5.6 MB) automatically.
API docs: http://localhost:8000/docs

### Frontend

```sh
cd apps/web
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open http://localhost:3000: upload an MP4, Select it, draw a zone on the
first-frame snapshot, create + enable a workflow, press Process.

## Tests

```sh
# unit + integration (fast; integration uses a disclosed test-stub detector)
services/api/.venv/bin/python -m pytest tests/ -q

# end-to-end smoke with REAL YOLO inference (starts its own server)
services/api/.venv/bin/python scripts/smoke_e2e.py

# demo video from real photographic content (Ultralytics sample photo)
services/api/.venv/bin/python scripts/make_demo_video.py data/demo/demo_bus.mp4

# repository structure check
make check
```

Configuration variables: see [.env.example](.env.example).
Licenses and data provenance: [docs/LICENSES.md](docs/LICENSES.md).

## Structure

```text
apps/web/              Next.js UI (M1: single-page flow)
services/api/          FastAPI backend, SQLite, pipeline worker
packages/vision/       detection, tracking, zones, temporal event engine
packages/workflows/    (M2) NL → DSL compilation
packages/autolearn/    (M3) teacher/student specialization
packages/integrations/ (M2+) webhook/CRM/GVERA adapters
tests/                 unit + integration
scripts/               structure check, demo video builder, e2e smoke
docs/                  task source, PRD, architecture, traceability, licenses
.agents/               agent protocol, state, handoffs, reviews
```

## Agents

Instructions: [AGENTS.md](AGENTS.md) · Protocol: [.agents/PROTOCOL.md](.agents/PROTOCOL.md) ·
State: [.agents/STATE.md](.agents/STATE.md) · Handoff: [.agents/HANDOFF.md](.agents/HANDOFF.md)
