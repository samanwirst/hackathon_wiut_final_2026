# VisionFlow AI — Demo Guide (demo-safe build)

This guide covers the `feature/demo-safe` deliverable: a polished, demonstrable
**geometric** visual-analytics control platform for recorded video, with the
experimental M2 paths locked off in the backend.

> **Status honesty.** M1 is accepted; **M2 remains BLOCKED**. This demo is *not*
> an M2 acceptance, an M3 AutoLearn implementation, or a measured-cost result.
> Teacher VLM, Student, foveated input and any GPU savings are **UNVERIFIED** and
> no savings percentage is claimed. The zero Teacher calls shown reflect the
> geometric-only path, not a paired cost benchmark.

## 1. What runs vs. what is disabled

| Capability | Status in this demo |
| --- | --- |
| MP4 upload → frame sampling → **YOLO11n detection + ByteTrack** | **Supported (real)** |
| Polygon zones; temporal rules: enter / exit / **dwell ≥ s** / **count > n** | **Supported (real)** |
| Event persistence, evidence JPEG, **local `create_notification`** action | **Supported (real)** |
| Guided rule build → **server-canonical JSON review** → deliberate approval | **Supported (real)** |
| Edit / disable / re-arm with renewed JSON review | **Supported (real)** |
| Natural-language → DSL compiler | **Disabled** (M2-001 unresolved; never invoked) |
| Teacher-routed **visual-predicate** workflows (create/enable/process) | **Disabled** (zero Teacher admission) |
| Outbound webhook / external delivery | **Removed in M1** (M1-011/M1-012) |
| Live camera / RTSP | **Unavailable** |
| AutoLearn (Teacher → verified dataset → Student), foveated input, GPU savings | **Planned / UNVERIFIED** |

Rule-label semantics match the real engine exactly: **count** fires when the
in-zone count **strictly exceeds** the threshold (`count > n`); **dwell** fires
when the object has been in the zone for **≥** the configured seconds.

## 2. Demo-safe enforcement (backend, not just UI)

With `VISIONFLOW_DEMO_SAFE=true` (default):

- `POST /api/workflows/compile` returns a visible unavailable error **without
  importing or calling** the NL compiler — no prompt reaches the grammar.
- `POST /api/workflows` and `POST /api/workflows/{id}/enable` **reject**
  (`403`) any workflow carrying a `visual_predicate`.
- Processing **skips** any enabled `visual_predicate` workflow (even a legacy row
  or one enabled before the demo) — it is refused, never coerced to geometric —
  so no Teacher call can be admitted, even with `VLM_BASE_URL`/`VLM_MODEL` set.
- `GET /api/metrics` and `GET /api/vlm/stats` report an explicit
  `disabled_demo_safe` state **without instantiating** the router or a Teacher.

Set `VISIONFLOW_DEMO_SAFE=false` only to exercise the historical M2 experimental
paths; the original M2 tests opt out with an explicit fixture.

## 3. Local startup (loopback only, isolated data)

No credentials and no GPU are required. Run everything on loopback with an
isolated data directory so the demo never touches real data, and **without**
the autopilot/orchestrator.

### Backend

```sh
# from the repo root
export VISIONFLOW_DATA_DIR="$(mktemp -d /tmp/visionflow-demo.XXXX)"
export VISIONFLOW_DEMO_SAFE=true
services/api/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 \
  --app-dir services/api
```

The first processing run downloads YOLO11n weights (~5.6 MB) automatically.
API docs: http://127.0.0.1:8000/docs

### Frontend

```sh
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm --prefix apps/web run dev
# open http://localhost:3000
```

### Demo clip (real photo, synthetic motion)

```sh
services/api/.venv/bin/python scripts/make_demo_video.py data/demo/demo_bus.mp4
```

The clip translates a real Ultralytics sample photo (bus + pedestrians) across a
canvas so objects move through zones. **Detection is genuine YOLO inference on
real image content; only the motion is synthetic.** Provenance is recorded in
[LICENSES.md](LICENSES.md). Upload this file through the UI (or use any MP4 a
judge provides). There is no invented camera feed and no hardcoded prediction.

## 4. Seven-minute demo script

| Time | Beat | On screen |
| --- | --- | --- |
| 0:00–0:45 | **Problem** — manual service-bay monitoring is slow and undocumented. | Dashboard, demo-safe + capability chips. |
| 0:45–1:30 | **Product & customer** — recorded-video control platform for service ops. | Lede + architecture note. |
| 1:30–3:30 | **Live demo** — upload the demo clip → **Run** → draw “Service Bay A” polygon → build `bus · enters zone` → **review the exact server JSON** → **Approve & activate** → **Run** → event + evidence + local notification appear. | Sources, Zone workspace, Build & review, Event timeline, Notifications. |
| 3:30–4:30 | **Technical differentiation** — OpenVector-inspired hierarchy: cheap detection/tracking/temporal rules now; Teacher → verified dataset → Student planned. Honest JSON-review + server-side validation. | Architecture & honest status card. |
| 4:30–5:15 | **Honest evaluation** — real per-frame inference latency from `make smoke`; events are reproducible on video time. No savings % claimed. | Smoke output / metrics. |
| 5:15–6:00 | **Business & pilot** — three-month service-bay pilot (PRD §18). | Deck. |
| 6:00–7:00 | **Impact, limits, roadmap** — demo-safe boundary; M2 BLOCKED; AutoLearn/Teacher/foveated UNVERIFIED. | This matrix. |

Edit/version note to demonstrate if time allows: click **Edit** on an armed
rule — the old rule is disabled (its events/evidence preserved) and a new
reviewed version is created; **Approve** re-arms it.

## 5. Commands (verify before showing)

```sh
# full check: structure + unit/integration tests + frontend production build
make check

# real-YOLO end-to-end smoke (starts its own server on an isolated data dir)
make smoke

# demo-safe backend regressions only
services/api/.venv/bin/python -m pytest tests/integration/test_demo_safe.py -q
```

Record actual results; do not claim a pass that was not run. See
[.agents/DEMO_HANDOFF.md](../.agents/DEMO_HANDOFF.md) for the executed results of
this deliverable.

## 6. Pre-show checklist

- [ ] Backend on `127.0.0.1:8000` with `VISIONFLOW_DEMO_SAFE=true` and an
      isolated `VISIONFLOW_DATA_DIR`.
- [ ] Frontend on `127.0.0.1:3000` pointed at the loopback API.
- [ ] `data/demo/demo_bus.mp4` generated (or a judge's MP4 ready).
- [ ] `make check` and `make smoke` pass on the target machine.
- [ ] No autopilot/orchestrator running; no public deployment.
