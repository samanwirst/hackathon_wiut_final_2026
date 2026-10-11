# VisionFlow AI — WIUT Hackathon Final 2026

Visual AI automation for automotive operations: upload a recorded video, draw a
zone, configure a supported geometric condition, review its JSON and approve
real events, evidence and local notifications. Track: Computer Vision.

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

## Accepted geometric engine (M1)

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

M2's experimental VLM routing/compiler implementation remains BLOCKED.
The isolated ten-hour experiment has executed actual private GPU Teacher
labeling and applied the user's verification of 24 exact synthetic images.
Twelve biased Teacher proposals needed correction. A real Student was fitted,
saved, reloaded and compared in shadow on six held-out synthetic images:
Student 6/6 correct, Teacher 3/6. The independent review of that experimental
snapshot returned CHANGES_REQUIRED. The final correction at `ff48ca9` passed249
tests/build/realYOLO but independently failed QA with6P1; the experiment is
BLOCKED, closed and not integrated. See the [final review](.agents/reviews/AUTOLEARN-TEN-HOUR-FINAL.md)
and [executed pilot evidence](.agents/autolearn-evidence/synthetic-5938b6d/VALIDATION.md)
for exact inputs, timings and limits. No model was activated; this is not M3
acceptance. The verified fallback
is protected on `feature/demo-safe`.
The [architecture audit](docs/VISUAL_ANALYTICS_AUDIT.md) and
[milestone acceptance criteria](docs/PRD.md#16-acceptance-criteria) define
the remaining work. No cost savings or natural-video quality result is established.

Current experimental verdicts and limits are in [the execution status](docs/TEN_HOUR_STATUS.md).

The delivery candidate uses [a private reproducible container deployment](deploy/README.md)
and an optional authenticated same-origin gateway. [Executed evidence](.agents/delivery-evidence/private-749d27b/VALIDATION.md)
records a real YOLO event, evidence and notification in the fresh unprivileged
container. No public tunnel is active. Use the [seven-minute defence script](docs/DEFENSE_SCRIPT.md)
and [actual recorded fallback](docs/presentation/VisionFlow-fallback-demo.mp4).

## Demo-safe build (current deliverable)

The branch `feature/demo-safe` ships a polished, demonstrable **geometric**
control platform for recorded video with the experimental M2 paths locked off
in the backend. See the [Demo Guide](docs/DEMO_GUIDE.md) for the exact startup,
data provenance, the seven-minute script, and the supported/disabled/unverified
matrix.

The [independent demo evidence](.agents/demo-evidence/99e8670/VALIDATION.md)
records 195 passing tests, the production build, real YOLO smoke and the actual
desktop approval/event/evidence journey. Use a desktop viewport of at least
1024px; a known phone layout issue is documented there.

Demo-safe mode (`VISIONFLOW_DEMO_SAFE=true`, the default) is enforced
server-side, not just in the UI:

- the natural-language compiler is **never invoked** (M2-001 remains unresolved);
- Teacher-routed **visual-predicate** workflows cannot be created, enabled, or
  processed — zero Teacher admission even with a VLM endpoint configured or a
  legacy visual row enabled, and they are refused rather than silently coerced
  into geometric rules;
- VLM stats report an explicit disabled state **without** instantiating a Teacher.

**M1 is accepted; M2 remains BLOCKED.** This demo is not an M2 acceptance, an M3
AutoLearn implementation, or a measured-cost result. The fallback does not expose
Teacher or Student features. Foveated input and GPU cost savings remain UNVERIFIED;
no savings percentage is claimed.
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

Open http://localhost:3000: upload an MP4, select it, draw a zone on the
first-frame snapshot, save a draft, review the validated JSON, click
**Approve & activate**, then **Run**. For an isolated, preflighted demo, follow
[the Demo Guide](docs/DEMO_GUIDE.md#3-local-startup-loopback-only-isolated-data).

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
