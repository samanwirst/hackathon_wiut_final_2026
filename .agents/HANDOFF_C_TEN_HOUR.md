# Handoff — Workstream C (ten-hour): AutoLearn M3 experimental vertical slice

- Branch: `experiment/autolearn-ten-hour` (worktree C).
- Implementation commit SHA: `530f36a752d132e0845cc9fbbbfc8f138c49709b`.
- **Blocker-fix pass code SHA: `699775eca6cf12ab7c18512215c31197aba509b0`**
  (prior review base `440eaa72d32874779eae447f94ea46dcca695a17`).
- Base: `ae2b5a5` (root `feature/demo-safe`, frozen — untouched).
- Status: **EXPERIMENTAL / UNVERIFIED.** No milestone verdict changed. M2 stays
  BLOCKED. M3 is **not** marked PASS. No push performed (root pushes).

---

## Blocker-fix pass (review AUTOLEARN-TEN-HOUR-INITIAL, commit 440eaa7)

Isolated one-pass fixes in worktree C only. Default demo guard and disabled
Teacher workflow actions stay enforced; AutoLearn still never dispatches an
action. Existing schema columns preserved; additions are a new table and nullable
audit columns applied with a data-preserving additive migration, so root can
retain the backed-up image hashes and human verifications.

| Finding | Resolution | Where |
| --- | --- | --- |
| C-001 | FIXED | `labeling.py`: one owned persistent loop for sync callers; per-running-loop admission semaphore (no global semaphore across `asyncio.run` loops); admission inside the absolute overall deadline; cancellation frees capacity on unwind; sync outer safety budget. |
| C-002 | FIXED | new `ModelVersionSample` manifest table; `service.evaluate/shadow_compare/gate_status` read the frozen per-version membership, fail closed on missing/inconsistent snapshots; gate requires finite f1, support == snapshot test count, both classes. |
| C-003 | FIXED | `service.build_split_plan` groups by physical `source_id`/`session_id`, rejects inconsistent group metadata; `dataset.build_split` refuses decode/re-encode near-dups across groups using a FIXED decoded-pixel MAD threshold (5.0; not tuned on held-out). |
| C-004 | FIXED | `page.tsx` selection-generation guard discards stale detail/sample fetches; added real image upload (session/group/source provenance) and offline-classify controls; minimal responsive rule. |
| C-005 | FIXED | durable per-task (`AUTOLEARN_LABEL_BUDGET_PER_TASK`) + per-job (`AUTOLEARN_LABEL_JOB_MAX`) budgets counted from the audit; duplicate suppression + cached-identical reuse (zero attempts); missing provider = zero attempts; offline classify fallback is budget-guarded. |
| C-006 | FIXED | `labeling._parse_strict` + content extraction reject non-string content (int/bool/object) as `invalid_response` instead of raising `AttributeError`. |
| C-007 | PRESERVED | success candidates carry the provider's ACTUAL `response_model` + `method` (`chat_json`) + bounded raw (usage, content preview, configured alias) with no credentials; audit stores `response_model`/`method`. `confidence_calibrated=False` flags self-reported confidence as uncalibrated. (Root's local Smol likelihood-scoring provider is a separate private experiment, not in this tree.) |

### Commands run and actual results (this pass)

- `pytest tests/unit/test_autolearn_c_transport.py -q` → **6 passed** (real 127.0.0.1 loopback TCP).
- `pytest tests/unit/test_autolearn_c_service.py -q` → **12 passed**.
- `pytest` on all AutoLearn files incl. integration → **41 passed** (real ResNet18 encoder + genuine fit/save/load/evaluate).
- `pytest tests/` (full suite) → **236 passed** (no regressions; one trace is the intentional simulated-crash recovery test).
- `apps/web`: `npm run build` → **compiled + type-checked OK**, `/autolearn` route built.
- Transpiled-component harness (deterministic hook/fetch, no browser): out-of-order
  A→B selection now shows **B_yes** review labels and activation targets **version 201**
  (Task B), not the stale Task A/101; 2 file inputs present with `/images`+FormData and `/classify` wiring.

### New / changed files (this pass)

- `services/api/app/autolearn/labeling.py`, `service.py`, `dataset.py`
- `services/api/app/db.py` (new `ModelVersionSample` table; nullable `response_model`/`method`
  on `LabelingAudit`; additive `_migrate_additive`), `config.py` (budgets, near-dup MAD)
- `apps/web/app/autolearn/page.tsx`
- `tests/unit/test_autolearn_c_transport.py`, `tests/unit/test_autolearn_c_service.py`

### Honest limits (this pass)

- No Student fit on root's real 24-image dataset here; root exercises new code
  against the copied backup. Image approval does NOT authorize activation.
- Synthetic data is QA_ONLY (shared-generator procedural renders) — no
  natural-video quality conclusion. No rental cost / GPU time / savings measured.
- The near-dup MAD threshold separates re-encodes (~0–1.5) from distinct synthetic
  scenes (~13.5) in this generator; on real footage root should sanity-check it.
- Live Teacher labeling against a real provider remains UNVERIFIED; tests use
  owned loopback mocks only (plainly QA_ONLY). **Not an M3 PASS.**

---

## Original slice (commit 530f36a) — context below

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
