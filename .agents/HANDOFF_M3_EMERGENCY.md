# HANDOFF — AutoLearn M3 exceptional (emergency) fix pass

- Milestone: M3 (AutoLearn experimental slice) — ONE authorized exceptional pass.
- Branch: `experiment/autolearn-emergency`
- Base (review target): `ff48ca9756e179e1bda1f9556e44d20c24776a8b`
- Implementation SHA: `956ba9b0e2ecf83637fe5344be68cdee794c0b67`
- Review consumed: `AUTOLEARN-TEN-HOUR-FINAL.md` (VERDICT CHANGES_REQUIRED — six P1 + one P2).
- Status: all six P1 + the P2 reproduced on NEW scratch QA_ONLY data, fixed, re-verified.
- This is code QA only — NOT M3 acceptance, activation, or publication. M2 remains BLOCKED.

## Changed component files

- `services/api/app/autolearn/service.py` — admission resolution, batch commit, verified
  loader, `_validate_proba`, frozen-manifest image-byte binding, gate artifact-hash binding,
  classify verified-load + cache validation.
- `services/api/app/autolearn/labeling.py` — URL preflight, actual `experimental_metrics`
  contract parsing, bounded optional metadata.
- `apps/web/app/autolearn/page.tsx` — operation-ownership token for busy cleanup.
- `tests/unit/test_autolearn_emergency_regressions.py` (new), `tests/unit/test_autolearn_c2_regressions.py`
  (C-007 contract test corrected to the real envelope).

No DB schema/migration change: `artifact_sha256` rides the existing `ModelVersion.metrics`
JSON; scoring provenance rides `TrainingSample.teacher_raw` + the existing
`LabelingAudit.response_model`/`method` columns.

## Repro → fix → result (NEW scratch, `/tmp/visionflow-c-emergency`, owned copies of the immutable probes)

Env: `VISIONFLOW_DATA_DIR=<scratch>/data VISIONFLOW_DEMO_SAFE=true OMP/MKL/OPENBLAS=2
PYTHONPATH=services/api:<scratch>`. Only scratch paths were adapted in the probe copies; the
original fault boundaries (actual SQL interleavings, two real Uvicorn processes, genuine CPU
Student fit, transpiled React) are unchanged.

- **C-004 (UI)** — `ui_create.cjs`/`ui_all_actions.cjs`.
  Before: `busy='create'` permanent after Create (4 disabled controls); 9 disabled controls
  after A→B late completion. Fix: `run()` releases `busy` by an op-ownership token
  (`opGen`), independent of selection generation; stale data/errors still gated by `live()`.
  After: create → `busy=null`, 0 disabled; every action after A→B → `busy=null`, 0 disabled,
  no stale A data/errors, B controls usable. No auto-approval anywhere.

- **C-005-BATCH** — `batch_label_probe.py` (3 distinct JPEGs, budget 5, job 3).
  Before: 1 POST then `sqlite3 database is locked` → HTTP 500, 0 audits, 0 labels.
  Fix: commit each sample's result+audit incrementally; the job never holds a write txn across
  the independent reservation commit / network call. After: HTTP 200, 3 POSTs, 3 labeled, 3
  audits, slots 0/1/2 `sent`.

- **C-005 (race)** — `multiworker_race.py` (2 real Uvicorn processes) + `boundary_probes.py`.
  Before: 2 POSTs under budget 1 (distinct slots bypass `UNIQUE`); same-key races 2 POSTs;
  invalid URL consumed a `sent`; corrupted cache reused.
  Fix: authoritative POST-COMMIT resolution against the committed active set — dedupe keeps the
  lowest-slot owner; budget keeps only the `budget` lowest-slot rows, losers self-release
  (ledger-visible, zero spend). Local URL preflight → `attempted=False`. Cache labels strictly
  re-validated before reuse.
  After: multiworker 1 POST, peak 1 (slot0 `sent`, slot1 `released`, one `deduped`); both
  boundary interleavings 1 POST; invalid URL 0 POSTs (slot `released`); corrupted cache →
  `unknown`, never the corrupt label. `sent` timeout and injected audit-commit fault still
  retain spend.

- **C-002 (gate/eval)** — `artifact_probes.py`.
  Before: zeroed weights activated on cached F1=1; changed image bytes passed; bool/column/row/
  numeric-string predictions passed; `bad_string`/NaN/inf metrics → 500; F1=2.0 passed.
  Fix: `_validate_proba` validates raw dtype/ndim before coercion; `_frozen_manifest` binds
  actual on-disk image bytes; gate binds `metrics.artifact_sha256` vs the current artifact file
  and requires finite F1∈[0,1] with a NaN-safe response.
  After: stale-weights gate FAIL + not activated (genuine reeval → F1=0); changed bytes FAIL;
  all nine prediction types gate FAIL / classify `unknown` / no 500; F1=2.0/NaN/inf FAIL with
  no 500. (See "Honest caveat" re the probe's `f1=True` line.)

- **C-008 (loader)** — `artifact_probes.py`.
  Before: classify used the raw loader (classified v2 while reporting v1); empty/partial
  provenance and reversed class mapping loaded; corrupt archive → 500.
  Fix: `_load_verified_artifact` is mandatory on classify too; `require_complete` demands all
  provenance fields for gate/eval/activate/rollback; class ordering verified against the
  mapping; load exceptions normalized to bounded `AutoLearnError`.
  After: wrong-artifact classify → `unavailable`; empty/missing-dataset/reversed-class gate
  FAIL + not activated; corrupt/missing rollback → HTTP 422 (current active unchanged);
  verified-target rollback → 200.

- **C-007 (contract)** — `boundary_probes.py::actual_local_scoring` (mirrors B's
  `local_teacher.py` `experimental_metrics` envelope).
  Before: method mislabeled `chat_json`, revision inferred from model id, scores/forward counts
  dropped.
  Fix: parse the ACTUAL `experimental_metrics` (`scoring.method=candidate_sequence_softmax`,
  `output_is_generated_json=false`, revision from the envelope, `model_forward_calls`,
  `actual_model_processed_tokens`, candidate labels/probabilities); configured alias stays
  distinct from the actual model/revision; nothing invented.
  After: candidate method/revision/model/forwards(2)/processed_tokens(27)/scores persisted on
  the sample `teacher_raw` and exposed; audit `method`+`response_model` correct.

- **C-006 P2 (overflow)** — `optional_overflow.py` + `boundary_probes.py::optional_envelope_types`.
  Before: `candidate_scores{10**400}` → `OverflowError`/500, no audit, stuck `reserved` row.
  Fix: `_finite_number`/`_bounded_int`/`_bounded_scores`/`_bounded_usage` bound every optional
  field (≤8 scores, drop overflow/NaN/bool/unbounded extras). After: HTTP 200, 1 POST, 1 audit,
  slot `sent`; oversize usage/scores normalized (bounded), no 500.

## Test / build / smoke results (actual)

- `pytest tests/` (full) — **259 passed** (24.5s). Includes the existing 54 AutoLearn + 9 new
  emergency regressions + 37 demo-safe/geometric-workflow safety checks.
- Frontend `npm run build` (apps/web) — **success** (`/autolearn` route built).
- `make smoke` (real YOLO) — **SMOKE PASS** (event + evidence + notification, avg inference
  59.3 ms).

## Required retrain / invalidation / migration

- **Invalidation:** the gate now requires `metrics.artifact_sha256` AND `manifest_digest` to
  match the current artifact/membership. Any ModelVersion whose stored metrics predate this
  field (incl. the approved root pilot v1) is **fail-closed** until a genuine re-evaluation
  (`POST /versions/{id}/evaluate`) re-measures and re-binds. This is intentional and honest —
  no provenance is auto-inferred or rewritten.
- **Retrain:** none forced by schema. ROOT should re-run the approved pilot's evaluation (and,
  if the split/artifact is regenerated, a genuine retrain) before any re-activation; I did not
  read or mutate that backed-up data.
- **Migration:** none. No column added/altered.

## Honest caveats (for the fresh review)

- `artifact_probes.py::malformed_metric_gate['True']` still shows `passed=true, f1=1.0`. This is
  a probe artifact, NOT a bypass: `True == 1.0` in Python, so SQLAlchemy's equality-based dirty
  check treats `metrics['f1']=True` as a no-op and the DB retains the genuine float `1.0`; the
  gate reflects the real metric. A genuinely bool-valued F1 IS rejected — proven by
  `test_gate_rejects_non_finite_f1`, `test_validate_proba_rejects_bad_types_and_shapes`, and a
  direct no-session check (`held-out F1 is not a finite number in [0, 1] (True)`).
- `LabelingCache` persists model/label/confidence but not `method`/`revision` (no column); the
  authoritative scoring provenance lives on `TrainingSample.teacher_raw` and `LabelingAudit`.
  The fallback cache is re-validated on read and is not a provenance source of record.

## Safety invariants preserved

Default `demo_safe=true`; unsafe NL/Teacher workflow actions off; zero Teacher calls for
geometric workflows; shadow mode records only (`action:"none"`); activation/rollback require an
explicit human approval AND a passed gate; no real Student activation performed; C-003 physical
source grouping and C-009 archived-rollback loader untouched. No pushes, no provider/GPU calls,
no spend, no publication, no reads of approved experiment data/.env/secrets, no changes to the
protected fallback / other worktrees / prior reports.

## Questions for Codex / ROOT

1. Confirm the artifact-hash gate binding is the intended invalidation boundary for the pilot v1
   (fail-closed until genuine reeval), vs. a one-time provenance backfill.
2. Is the post-commit slot-rank resolution acceptable as the "authoritative CAS", or is a
   `BEGIN IMMEDIATE` single-statement admission preferred (note: it would serialize the
   reviewer's pause-based interleave probes so they could not reproduce their precondition)?
