# Архитектура / Architecture (M1)

## Pipeline

```
MP4 upload → VideoSource (SQLite) → background thread per source:
  OpenCV frame read → sampling (PROCESS_FPS, default 5/s)
  → YOLO11n detection + ByteTrack tracking (real inference, CPU by default)
  → per-workflow ZoneEventEngine (deterministic state machine)
  → TrackEvent row + annotated evidence JPEG
  → authorized local action (create_notification row)
```

All timestamps are video time (`frame_idx / fps`) — reproducible, testable.

## Components

| Path | Responsibility |
| --- | --- |
| `packages/vision/visionflow_vision/zones.py` | Normalized polygons, ray-cast inclusion, bottom-center bbox anchor |
| `packages/vision/visionflow_vision/events.py` | Enter/exit/dwell/count state machine: debounce, cooldown, lost-track grace, one-shot per visit, dedupe keys |
| `packages/vision/visionflow_vision/detector.py` | `YoloByteTrackDetector` (real YOLO via ultralytics); `BaseDetectorTracker` interface for test stubs |
| `services/api/app/schemas.py` | Pydantic workflow DSL + API models; unsupported types fail validation |
| `services/api/app/pipeline.py` | Background processing thread, evidence capture, progress/metrics |
| `services/api/app/actions.py` | Action executor: `create_notification` (local, side-effect-free). Outbound `send_webhook` removed (M1-011/M1-012); unsupported/legacy actions rejected with no network activity |
| `services/api/app/main.py` | FastAPI routes (PRD §11 subset for M1), CORS, evidence static serving |
| `apps/web/app/page.tsx` | Single-page UI: upload, canvas zone drawing, workflow form, event timeline, notifications |

## Key decisions

- **SQLite + WAL** — single-node MVP per PRD §7; sessions per thread.
- **Ultralytics `model.track(persist=True)`** — gives ByteTrack association
  without a separate tracker implementation (license note in LICENSES.md).
- **CPU inference** — yolo11n at ~60–140 ms/frame with 5 fps sampling keeps a
  6 s clip under ~30 s processing; `DETECTOR_DEVICE=cuda` is a config switch.
- **Workflows are created disabled** and must be explicitly enabled (PRD P0.7).
- **Frontend holds no business logic** — all validation/decisions server-side.
- **Server-authoritative security**: upload type/size validation, decode-
  completeness check for truncated videos (M1-013), secrets only via env.
- **Outbound webhooks removed** (M1-011/M1-012): rather than ship an SSRF
  allowlist that DNS rebinding could bypass on the delivery connection, M1 only
  performs the local `create_notification` action. A validated-egress
  integration is deferred.

## Deferred (per milestone plan)

M2: NL→DSL compilation, SSE updates, dashboard/timeline pages, service-event
action. M3: AutoLearn (teacher labels, embeddings, student training, shadow
mode). M4: deployment, metrics report, demo script.
