# VisionFlow AI — WIUT Hackathon Final 2026

Visual AI automation for automotive operations: upload a video (or connect a
camera), draw a zone, describe a condition, and get real detections turned into
events, evidence, and authorized actions. Track: Computer Vision.

The product's innovation is **cost-efficient visual analytics inspired by
OpenVector**: cheap detection and tracking run continuously at a configured
sampling rate; temporal events select frames or object ROIs for expensive
visual reasoning. Deduplication and versioned caches limit repeated teacher
calls. AutoLearn transfers verified teacher labels to a lightweight student
over frozen visual embeddings, with held-out evaluation, shadow comparison,
manual activation, fallback, and rollback.

These are implementation requirements, not a claim that all stages are
already available. Cost savings require an actual paired baseline experiment.

The official task is in [docs/source/README.md](docs/source/README.md);
product requirements in [docs/PRD.md](docs/PRD.md);
architecture in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Current state (M1 recovery cycle)

Working end-to-end pipeline: **MP4 upload → YOLO11n detection + ByteTrack
tracking → polygon-zone temporal events (enter / exit / dwell / count) →
SQLite persistence + evidence JPEG → authorized local action
(create_notification) → web UI** (upload, canvas zone drawing, workflow
builder, event timeline).

The exceptional M1 recovery cycle resolved the four P1 defects from the
`cc59523` review: dispatch-after-disable is now serialized and suppressed
(M1-010); a truncated video is reported as a failed source (M1-013); and
arbitrary outbound webhooks were **removed** (M1-011/M1-012) — the SSRF/
DNS-rebinding guard could not safely protect the delivery connection without a
risky custom egress transport, so only the local `create_notification` action
ships. See [.agents/reviews/M1.md](.agents/reviews/M1.md) and
[docs/TRACEABILITY.md](docs/TRACEABILITY.md).

VLM routing/caching is assigned to M2, verified teacher-to-student learning
to M3, and measured baseline comparisons to M4. These stages are pending.
The [architecture audit](docs/VISUAL_ANALYTICS_AUDIT.md) and
[milestone acceptance criteria](docs/PRD.md#16-acceptance-criteria) define
the remaining work. No VLM savings or held-out quality result is established.

## Demo-safe build (current deliverable)

The branch `feature/demo-safe` ships a polished, demonstrable **geometric**
control platform for recorded video with the experimental M2 paths locked off
in the backend. See the [Demo Guide](docs/DEMO_GUIDE.md) for the exact startup,
data provenance, the seven-minute script, and the supported/disabled/unverified
matrix.

Demo-safe mode (`VISIONFLOW_DEMO_SAFE=true`, the default) is enforced
server-side, not just in the UI:

- the natural-language compiler is **never invoked** (M2-001 remains unresolved);
- Teacher-routed **visual-predicate** workflows cannot be created, enabled, or
  processed — zero Teacher admission even with a VLM endpoint configured or a
  legacy visual row enabled, and they are refused rather than silently coerced
  into geometric rules;
- VLM stats report an explicit disabled state **without** instantiating a Teacher.

**M1 is accepted; M2 remains BLOCKED.** This demo is not an M2 acceptance, an M3
AutoLearn implementation, or a measured-cost result. Teacher, Student, foveated
input and any GPU savings are UNVERIFIED and no savings percentage is claimed.
The guided UI builds a rule, shows the exact server-validated JSON, and requires
a deliberate approval before the real detector → tracker → temporal-rule
pipeline is armed.

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

The sequential Claude/Codex controller is documented in
[.agents/AUTOPILOT.md](.agents/AUTOPILOT.md). With both CLIs authenticated:

```sh
python3 scripts/orchestrate.py --dry-run
make autopilot
python3 scripts/orchestrate.py --resume
python3 scripts/orchestrate.py --stop
```

`make check` runs the structure check, tests and frontend build. `make smoke`
runs real YOLO inference. The controller reviews frozen commits, saves local
checkpoints, caps fix cycles, pushes validated feature work and never merges
into main or publishes without approval.
