# Handoff — Workstream C (ten-hour): AutoLearn M3 experimental vertical slice

- Branch: `experiment/autolearn-ten-hour` (worktree C).
- Implementation commit SHA: `530f36a752d132e0845cc9fbbbfc8f138c49709b`.
- Base: `ae2b5a5` (root `feature/demo-safe`, frozen — untouched).
- Status: **EXPERIMENTAL / UNVERIFIED.** No milestone verdict changed. M2 stays
  BLOCKED. M3 is **not** marked PASS. No push performed (root pushes).

## What this is

One genuine, small vertical slice: Teacher → human-reviewed dataset → frozen
pretrained embeddings → fitted/saved/reloaded lightweight Student → held-out
evaluation → shadow/manual activation/rollback, with a product UI. It is
isolated from the accepted M1/M2 pipeline and **never dispatches a workflow
action**. Teacher-backed workflow actions remain completely off.

## Changed / new files

- `services/api/app/autolearn/` (new package):
  - `encoder.py` — frozen torchvision ResNet18 (IMAGENET1K_V1), `eval()`, params
    frozen, CPU + 2 threads; records weight tag + `PREPROCESS_VERSION`; raises
    `EncoderUnavailable` instead of substituting random features.
  - `student.py` — real torch logistic-regression Student; deterministic fit
    (fixed seed), standardization, save/reload producing identical predictions.
  - `dataset.py` — session/group-disjoint split; refuses missing classes,
    insufficient independent groups, and exact-content cross-group leakage; held
    out set never used for fit/threshold; dataset/split hashes.
  - `metrics.py` — confusion/precision/recall/F1/accuracy/support, latency
    p50/p95, disagreement rate, validation-only threshold selection.
  - `labeling.py` — **own** async httpx offline client (not the legacy M2
    transport): overall+connect/read timeouts, cancellation, serial concurrency,
    request image-byte cap, streamed response-byte cap, strict JSON validation
    (permitted label + finite confidence in [0,1]), redacted errors. Missing
    `VLM_BASE_URL`/`VLM_MODEL` ⇒ `unavailable` (never a synthetic label).
  - `service.py` — orchestration (create/import/label/review/split/train/
    evaluate/shadow/gate/activate/rollback/offline-classify).
  - `fixtures.py` — **QA_ONLY** disclosed procedural synthetic sessions; no
    real-world quality claim.
  - `schemas.py`, `api.py` — Pydantic models + `/api/autolearn` router.
- `services/api/app/config.py` — AutoLearn dirs, gate/split/labeling bounds.
- `services/api/app/db.py` — tables: AutoLearnTask, TrainingSample, ModelVersion,
  ActivationEvent, LabelingAudit (verified labels immutable; full provenance:
  source/session/timestamp/imagehash/Teacher trace/human identity+time).
- `services/api/app/main.py` — include autolearn router (2 lines).
- `apps/web/app/autolearn/page.tsx` — new page in existing styles; experimental
  status always visible. `apps/web/app/page.tsx` — the home "AutoLearn" chip now
  links to `/autolearn` labeled "experimental" (home demo-safe flow preserved).
- Tests: `tests/unit/test_autolearn_core.py`,
  `tests/unit/test_autolearn_labeling_transport.py` (disclosed mock transport),
  `tests/integration/test_autolearn_api.py` (full flow, real encoder).

## Commands run and actual results

- `services/api/.venv/bin/python -m pytest tests/unit/test_autolearn_core.py tests/unit/test_autolearn_labeling_transport.py -q` → **21 passed**.
- `services/api/.venv/bin/python -m pytest tests/integration/test_autolearn_api.py -q` → **2 passed** (real ResNet18 encoder + genuine training).
- `services/api/.venv/bin/python -m pytest tests/ -q` → **218 passed** (no regressions; one trace is an intentional simulated-crash recovery test).
- `services/api/.venv/bin/python scripts/check_structure.py` → **Repository scaffold: OK**.
- ResNet18 IMAGENET1K_V1 weights downloaded once into the torch hub cache
  (`~/.cache/torch/hub`, outside the repo; git-ignored data otherwise).

## Test coverage mapping (meaningful integration)

pending provider · malformed labels · unverified-label exclusion · persisted
review (+ immutability) · session/hash leakage refusal · real classifier
fit/save/load · metrics from predictions · shadow zero-actions · activation
approval/rejection + gate fail/pass · rollback · encoder frozen+deterministic.

## Honest limitations (what is NOT verified)

- **No real Teacher labels.** No GPU/provider connected; all current labels in a
  live run would be `pending/unavailable`. Transport contract is tested via a
  **disclosed mock**; real self-hosted Teacher labeling is UNVERIFIED (M3-AC7).
- **All numbers are from QA_ONLY synthetic data** and are not real-world quality.
  No accuracy/latency/cost claim is made. No savings percentages.
- Near-duplicate prevention is exact-content-hash + session/group grouping;
  perceptual near-dup across distinct groups is not implemented (disclosed).
- Local compute only; no Vast.ai rental cost measured (would be separate).
- Frontend `npm run build` NOT run here (root schedules it to avoid RAM
  contention). TypeScript not type-checked in this session.
- No milestone marked PASS; M2 stays BLOCKED; root obtains human sign-off after
  concrete real images/labels exist.

## What root needs to do next

1. Run frontend build / full `make check` sequentially (RAM).
2. Provide a real OpenAI-compatible self-hosted Teacher (`VLM_BASE_URL`,
   `VLM_MODEL`, optional `VLM_API_KEY`) to run actual labeling.
3. Human verification of real labeled images via `/autolearn` (or the
   contact-sheet endpoint), then retrain + evaluate on untouched held-out data.
4. Obtain human-operator sign-off before any activation is treated as real.

## Questions for review

- Is the DB-table addition in the shared `db.py` acceptable, or should the
  AutoLearn tables move to a separate metadata/engine to keep isolation stronger?
- Gate defaults (F1 ≥ 0.75, test ≥ 4) — confirm desired thresholds for real data.
