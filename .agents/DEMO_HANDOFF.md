# HANDOFF — DEMO-SAFE build (separate authorized task)

- **Task:** standalone DEMO-SAFE deliverable (NOT an M2 recovery, NOT M3/M4).
- **Branch:** `feature/demo-safe`
- **Base:** `088b17aded860bd5d926600573184c883919d20e`
- **Initial implementation SHA:** `fcf48d67b6f5598b49a5693c0ae6b96270c9cc5c`
- **DEMO correction SHA (first correction pass):**
  `dd7a2b930f1be51ad5914e76a24f5b05a49fe4b3`
- **DEMO source-boundary correction SHA (second/last pass — the exact code
  target for QA):** `7f3b5ebe459eab07dca68ee27b31f655cb3189cb`
- **This handoff commit:** recorded separately on top of the correction SHA.
- **Previous handoff base:** `8611cbdb79511e852f25aa113370f7ffa6c02c2d`.
- **Milestone status (unchanged):** M1 accepted; **M2 BLOCKED**. No M2 defect
  fixes, no AutoLearn/Teacher/GPU/RTSP/integration/deployment work.

## Scope delivered

A polished, demonstrable **geometric** visual-analytics control platform for
recorded video, with the experimental M2 paths locked off in the backend.

### Backend demo-safe guard (`VISIONFLOW_DEMO_SAFE`, default TRUE)

Enforced server-side, not just in the UI (minimal, flag-gated guards; no backend
redesign; compiler / Teacher transport / router / detector / tracker / event /
dispatch engine algorithms unchanged):

- `config.py`: added `DEMO_SAFE` (`_demo_safe_from_env`, default true) + two message
  constants.
- `main.py`:
  - `POST /api/workflows/compile` returns a visible unavailable `CompileResponse`
    **without calling `nl_compiler`** — no prompt reaches the grammar. The
    compiler module is imported at startup.
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

## DEMO correction (SHA `dd7a2b9`, on top of `8611cbd`)

A focused correction of concrete demo defects found during the controller's
Chromium journey. **Not** an M2 cycle, new milestone, or M3. The nine protected
hashes (milestone state/review/history and the compiler/Teacher/router/action
algorithms) are unchanged.

1. **Fail-closed config + verified safe mode.** `VISIONFLOW_DEMO_SAFE` now
   disables only on recognized false values (`0/false/no/off`); unknown values
   (e.g. `treu`) keep the guard **ON** and log why (was: `treu` → `False`).
   Parametric regressions added. `/api/health` returns `demo_safe`; the frontend
   verifies it and **refuses** uploads/arming/runs (with a visible warning) when
   the API is not safe or the capability is unverifiable. The header badge
   reflects verified / unverified / not-safe instead of a hardcoded claim.
2. **Legacy/visual rules no longer downgraded.** Visual-predicate workflows
   render as *unavailable* (disable-only + read-only JSON); no Edit, Review & arm,
   or new geometric draft. Edit/review/approve handlers refuse any non-null
   `visual_predicate`. (Backend `403` guards were already present and unchanged.)
3. **Exact editing/approval.** Any builder field/zone change invalidates ALL
   pending reviews (new + re-enable). Edit preserves the exact fractional dwell
   (removed `Math.round`; `step="any"`). Run/arm/edit are unavailable during the
   pending + actual analysis window; Disable stays available.
4. **Honest, guided operation.** Fabricated `progressPct` (15% / ÷6 assumption)
   replaced by an indeterminate indicator + real sampled-frame count. Run requires
   an approved enabled **geometric** rule (guides otherwise) and cannot start a
   second pass. `refresh()` checks `response.ok`/array shape, keeps request errors
   visible, and drops stale source-scoped responses.
5. **Mobile + provenance.** Removed the appbar negative-margin page overflow;
   tables scroll inside themselves; explicit body background, no fixed-attachment
   capture artifact. Canvas alignment preserved. UI no longer prints shell
   commands/data paths. New `scripts/make_demo_safe_video.py` (bus-only crop
   excluding foreground pedestrians, declared synthetic motion); LICENSES no
   longer asserts image consent (subject rights **unverified**); DEMO_GUIDE
   reordered to upload → zone → rule → JSON → approve → one run → evidence →
   edit, with exact 7-minute timing and a concrete three-month pilot proposal.

## DEMO source-boundary correction (SHA `7f3b5eb`, on top of `68ef63e`)

The last correction within the demo's two bounded fix passes. **Not** an M2
cycle, new milestone, or M3. Frontend-only (`apps/web/app/page.tsx`); the nine
protected hashes are unchanged (verified: `git status` shows only `page.tsx`
modified). This fixes one **reproduced** (not speculative) source-boundary
defect captured by the controller's probe (`selected_source_id=2`,
`run_disabled=false`, `old_rule_visible=true`, `old_event_visible=true`): after
uploading source 2 while its `GET /api/workflows?source_id=2` response was held,
source 1's approved rule stayed visible, its event appeared under the source 2
timeline, and Run stayed enabled — inheriting another recording's approval.

1. **Source-scoped render + eligibility.** New `scopeReady` flag is false until
   the currently selected source's zones/workflows/events finish loading, and
   derived `scopedZones` / `scopedWorkflows` / `scopedEvents` additionally
   require `record.source_id == selectedSource`. All rendering (overlay polygons,
   zone chips, zone picker, rule table, event timeline, and the notifications
   derived from those events) and `approvedGeometric` / Run now use the scoped
   views, so no previous recording's data can appear under — or arm — the new
   source while requests are in flight. Even the single transient render right
   after a switch is covered by the `source_id` filter.
2. **Clear on switch + drop stale callbacks.** Switching source resets
   `scopeReady` and clears the scoped arrays, the pending review, the edit note,
   and the evidence + read-only JSON modals; loading scopes show honest loading
   states instead of old lists. The in-flight refresh guard now also sets
   `scopeReady` only for the still-selected source, so stale/null-source
   callbacks are dropped rather than installing another source's data.
3. **Source-bound async form lifecycle. `ReviewTarget` carries `sourceId`.**
   Save-draft / approve / edit / re-arm all re-check the source binding **after**
   their awaited responses; a delayed save or enable can no longer install an
   old-source review or approval into a new source. The review panel only renders
   for `review.sourceId == selectedSource`.
4. **Builder locked during transitions.** A new `formPending` flag marks the
   save/approve/edit window and disables every builder field + the save/approve/
   arm/edit/Run controls during it (Disable stays available), so an instant edit
   can no longer be clobbered by the late server copy — the dwell selector no
   longer disappears mid-fill. The edit note is shown before the awaited reload.
5. **Frames clarity.** The single `Frames` column (`30 / ~180`) is split into
   `Samples analyzed` (real sampled YOLO count) and `Clip frames` (container
   metadata), each with an explanatory tooltip; it is sampled progress, not a
   completion percentage. Indeterminate progress and real counters are kept; no
   invented values. (The backend smoke log confirms the wording:
   `30 frames analyzed (180 decoded)`.)

No backend/algorithm/compiler/Teacher/router/action changes; no new libraries,
infrastructure, redesign, or source-string/mirror tests. No frontend unit-test
harness exists in the repo, so no JS tests were added; the controller's Chromium
regression `journey.mjs` (which holds source responses to exercise this exact
race) is their QA evidence, committed separately.

### Commands executed and ACTUAL results (correction SHA `7f3b5eb`)

- `make check` (structure + full pytest + frontend build) → **passed**:
  `Repository scaffold: OK`, **195 passed, 4 warnings** in 16.22s, Next.js build
  compiled + type-checked + linted clean (route `/` 8.74 kB, 111 kB first load).
- `make smoke` (real YOLO, own server, isolated temp data dir) → **SMOKE PASS**:
  `30 frames analyzed (180 decoded)`, avg inference **63.0 ms**,
  `bus #1 entered Service Bay A` at **t=4.2s conf=0.76**, evidence JPEG + local
  notification persisted. Synthetic motion of a real photo; not held-out
  accuracy.

## Commands executed and ACTUAL results (correction SHA `dd7a2b9`)

Using `services/api/.venv` and installed `apps/web/node_modules`.

- `services/api/.venv/bin/python -m pytest tests/ -q`
  → **195 passed, 4 warnings** in 16.06s (166 prior + 29 new parametric config
  cases). The 4 warnings are pre-existing (Starlette/FastAPI `on_event`
  deprecations + the intentional-crash recovery test in `test_m1_fixes.py`).
- Targeted: `pytest tests/unit/test_config_demo_safe.py tests/integration/test_demo_safe.py tests/integration/test_m2_visual.py -q`
  → **48 passed, 3 warnings** in 3.55s.
- `npm --prefix apps/web run build` → compiled + type-checked + linted clean
  (route `/` 8.35 kB, 111 kB first load).
- `make check` (structure + full tests + frontend build) → **passed**.
- `make smoke` (real YOLO, own server, isolated temp data dir) → **SMOKE PASS**:
  30 frames analyzed, avg inference **72.6 ms**, `bus #1 entered Service Bay A`
  at **t=4.2s conf=0.76**, evidence JPEG + local notification persisted.
  Synthetic motion of a real photo; not natural held-out accuracy. (The smoke
  path still uses the historical M1 generator `demo_bus.mp4`, left untouched; the
  demo-safe journey uses `demo_bus_private_crop.mp4` from the new script.)
- `scripts/make_demo_safe_video.py` ran cleanly, producing the bus-only crop MP4.

## Preserved byte-for-byte (verified unchanged via `git status`)

The nine protected hashes in `preservation-before.json` are unchanged:
`.agents/STATE.md`, `.agents/HANDOFF.md`, `.agents/reviews/M2.md`,
`docs/TRACEABILITY.md`, `.agents/runtime/state.json`, and the
`nl_compiler.py` / `teacher.py` / `vlm_router.py` / `actions.py` algorithms,
plus the detector / tracker / event / zone engine and the controller.

## Known limitations

- This is a demo-safe geometric deliverable, **not** an M2 acceptance. M2 remains
  BLOCKED with **three remaining P1s (M2-001 / M2-003 / M2-007) plus one P2
  (M2-009)** unresolved — not four material blockers; none were fixed here.
- In demo-safe mode the NL compiler module is **imported at startup but never
  invoked** (the compile endpoint returns an unavailable response before calling
  the grammar). Do not claim it is never imported.
- Teacher VLM inference, AutoLearn/Student, foveated input and any GPU/cost
  savings are **UNVERIFIED**; no savings percentage is claimed. Zero Teacher
  calls reflect the geometric path, not a paired cost benchmark.
- Demo data is a real photo with synthetic motion; live camera/RTSP unavailable.
- No credentials, GPU, force-push, main merge, public deployment, or purchase.

## For the controller

- Independent test target: the exact source-boundary correction SHA `7f3b5eb`
  (code) — run `make check`, `make smoke`, and
  `pytest tests/unit/test_config_demo_safe.py tests/integration/test_demo_safe.py`.
- Source-boundary browser QA focus (the controller's `journey.mjs` holds the
  `workflows?source_id=*` response to force the race): upload a second source
  while source 1 has an approved active geometric rule + a real event; confirm
  Run is **disabled**, source 1's rule/event/polygons are **not** shown under
  source 2 while loading, the loading state is visible, and a delayed
  save/approve/edit never installs an old-source review. Confirm the builder
  fields are locked during an Edit transition (dwell field persists).
- Generate the demo-safe fixture with
  `scripts/make_demo_safe_video.py data/demo/demo_bus_private_crop.mp4`.
- Browser QA focus (upload → zone → rule → **review JSON** → Approve → one Run →
  event/evidence/one notification; then Edit disables-and-replaces, Disable +
  Review & arm re-activates from stored JSON). Verify the correction probes:
  any builder change clears a pending re-enable review; Edit preserves a 1.5s
  dwell; a legacy visual rule shows unavailable (no Edit/arm, disable + View JSON
  only); run/arm/edit blocked during analysis; no page-wide overflow at 390px.
- Independent verification of the exact handoff `99e8670`, reproducible QA
  harnesses and the known loaded-source phone overflow are recorded in
  [demo evidence](demo-evidence/99e8670/VALIDATION.md). The supported show path
  uses desktop widths 1024/1280/1440px. The earlier 390px check concerned a
  loading/empty source and does not establish phone readiness.
