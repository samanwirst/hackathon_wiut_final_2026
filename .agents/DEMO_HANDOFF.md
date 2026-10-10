# HANDOFF — DEMO-SAFE build (separate authorized task)

- **Task:** standalone DEMO-SAFE deliverable (NOT an M2 recovery, NOT M3/M4).
- **Branch:** `feature/demo-safe`
- **Base:** `088b17aded860bd5d926600573184c883919d20e`
- **Implementation SHA (code/tests/docs):**
  `fcf48d67b6f5598b49a5693c0ae6b96270c9cc5c`
- **This handoff commit:** recorded separately on top of the implementation SHA.
- **Milestone status (unchanged):** M1 accepted; **M2 BLOCKED**. No M2 defect
  fixes, no AutoLearn/Teacher/GPU/RTSP/integration/deployment work.

## Scope delivered

A polished, demonstrable **geometric** visual-analytics control platform for
recorded video, with the experimental M2 paths locked off in the backend.

### Backend demo-safe guard (`VISIONFLOW_DEMO_SAFE`, default TRUE)

Enforced server-side, not just in the UI (minimal, flag-gated guards; no backend
redesign; compiler / Teacher transport / router / detector / tracker / event /
dispatch engine algorithms unchanged):

- `config.py`: added `DEMO_SAFE` (`_env_bool`, default true) + two message
  constants.
- `main.py`:
  - `POST /api/workflows/compile` returns a visible unavailable `CompileResponse`
    **without importing/calling `nl_compiler`** — no prompt reaches the grammar.
  - `POST /api/workflows` and `POST /api/workflows/{id}/enable` reject (`403`)
    any workflow carrying a `visual_predicate`.
  - `GET /api/metrics` and `GET /api/vlm/stats` report `disabled_demo_safe`
    **without instantiating** the router or a Teacher adapter.
- `pipeline.py` (`_build_engines`): a single guard clause skips any enabled
  `visual_predicate` workflow in demo mode (legacy/pre-demo rows included). It is
  **refused, not silently coerced** to geometric, so zero Teacher admission can
  occur even with `VLM_BASE_URL`/`VLM_MODEL` configured.

### Frontend (full presentation replacement — authorized)

`apps/web/app/page.tsx` + `globals.css` rewritten (layout.tsx unchanged). Calm,
strong-hierarchy control platform with native CSS + inline SVG icons (no
external image assets or web fonts):

- Source select/upload with honest status, progress and failure surfacing; live
  camera shown unavailable; demo-clip provenance disclosed (real photo, synthetic
  motion, sampled real YOLO).
- Responsive zone workspace; the overlay canvas realigns with the snapshot via a
  `ResizeObserver` + window `resize` listener.
- Structured rule builder (class · zone · trigger). Saving stores a **disabled**
  draft and shows the **server-canonical JSON**; a deliberate "Approve &
  activate" arms the rule. Labels match engine semantics (count `>`, dwell `≥`).
- Edit disables the prior rule (events/evidence preserved) and creates a new
  reviewed version; re-arming a disabled rule shows its JSON again. Editing/arming
  are paused while a source processes; disabling always available.
- Draft/approval cleared when switching sources or editing builder fields (no
  stale approval). Source-scoped events, full evidence-frame modal, local
  notifications. NL agent / Teacher VLM / AutoLearn / foveated shown as
  planned / unavailable / unverified. No fabricated events, metrics or savings.

### Tests

- `tests/integration/test_m2_visual.py`: added an explicit autouse fixture that
  sets `config.DEMO_SAFE=False` so the historical experimental tests keep
  exercising NL compile + Teacher-routed predicates. **No original assertion was
  weakened.**
- `tests/integration/test_demo_safe.py` (new, flag TRUE): compiler never invoked
  even on a known-bad M2-001 prompt; visual create/enable rejected; an enabled
  legacy visual workflow is skipped with zero Teacher calls / events / VlmCall
  rows even with a VLM endpoint configured and a counting stub Teacher installed;
  manual geometric draft stays disabled until explicit enable (and the geometric
  path still works); VLM stats report disabled without instantiating the router.

### Docs

`README.md` (demo-safe section), `apps/web/README.md`, `docs/DEMO_GUIDE.md`
(loopback-only startup, isolated data dir, `DEMO_SAFE=true`, no autopilot, data
provenance, 7-minute script, supported/disabled/unverified matrix, commands),
`.env.example` (`VISIONFLOW_DEMO_SAFE`).

## Commands executed and ACTUAL results

Using `services/api/.venv` and installed `apps/web/node_modules`.

- `services/api/.venv/bin/python -m pytest tests/ -q`
  → **166 passed, 4 warnings** in 16.38s (was 160; +6 new demo-safe tests). The
  4 warnings are pre-existing (Starlette/FastAPI `on_event` deprecations + the
  intentional-crash recovery test in `test_m1_fixes.py`).
- Targeted: `pytest tests/integration/test_demo_safe.py tests/integration/test_m2_visual.py tests/integration/test_api_flow.py -q`
  → **25 passed, 3 warnings** in 3.85s.
- `npm --prefix apps/web run build` → compiled + type-checked + linted clean
  (route `/` 7.44 kB, 110 kB first load).
- `make check` (structure + full tests + frontend build) → **passed**.
- `make smoke` (real YOLO, own server, isolated temp data dir) → **SMOKE PASS**:
  30 frames analyzed (180 decoded), avg inference **64.4 ms**, `bus #1 entered
  Service Bay A` at **t=4.2s conf=0.76**, evidence JPEG + local notification
  persisted. Synthetic motion of a real photo; not natural held-out accuracy.

## Preserved byte-for-byte (verified unchanged via `git status`)

`.agents/STATE.md`, `.agents/HANDOFF.md`, `.agents/reviews/M2.md`,
`.agents/review-evidence/`, `docs/TRACEABILITY.md`, `.agents/runtime/state.json`,
and the `nl_compiler.py` / `teacher.py` / `vlm_router.py` algorithms, plus the
detector / tracker / event / zone engine and the controller.

## Known limitations

- This is a demo-safe geometric deliverable, **not** an M2 acceptance. M2 remains
  BLOCKED with its four material defects (M2-001/003/007/009) unresolved; none
  were fixed here.
- Teacher VLM inference, AutoLearn/Student, foveated input and any GPU/cost
  savings are **UNVERIFIED**; no savings percentage is claimed. Zero Teacher
  calls reflect the geometric path, not a paired cost benchmark.
- Demo data is a real photo with synthetic motion; live camera/RTSP unavailable.
- No credentials, GPU, force-push, main merge, public deployment, or purchase.

## For the controller

- Independent test target: the exact snapshot `fcf48d6...` (code) — run
  `make check` and `make smoke`, and `pytest tests/integration/test_demo_safe.py`.
- Browser QA focus: source upload → run → draw zone → build rule → review the
  canonical JSON → Approve & activate → run → event/evidence/notification;
  verify editing disables-and-replaces, re-arm shows JSON review, and that
  editing/arming are blocked while a source is processing.
- QA and push are the controller's responsibility.
