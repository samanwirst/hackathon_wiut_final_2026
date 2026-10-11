# Review — AUTOLEARN-TEN-HOUR-FINAL

VERDICT: CHANGES_REQUIRED
TARGET_SHA: ff48ca9756e179e1bda1f9556e44d20c24776a8b

- Reviewed commit: ff48ca9756e179e1bda1f9556e44d20c24776a8b
- Implementation: 8e9d95fe0c4d6939d793e086cf2820b80231a5a8
- Base: 5938b6d1f1396c1513d52ee9d9c3cdb377dc43a4
- Review status: FAIL — six P1 findings and one P2 finding.
- Full report, executable probes and receipts: /tmp/visionflow-c-final-ff48ca9.

## Commands executed

Every Python run used TMPDIR=/tmp, PYTHONDONTWRITEBYTECODE=1, VISIONFLOW_DEMO_SAFE=true, OMP_NUM_THREADS=2, MKL_NUM_THREADS=2, OPENBLAS_NUM_THREADS=2, PYTHONPATH=services/api:/tmp/visionflow-c-final-ff48ca9 and separate owned data directories.

- `timeout 120s services/api/.venv/bin/python -m pytest tests/unit/test_autolearn_core.py tests/unit/test_autolearn_labeling_transport.py tests/unit/test_autolearn_c_service.py tests/unit/test_autolearn_c_transport.py tests/unit/test_autolearn_c2_regressions.py tests/integration/test_autolearn_api.py -q -p no:cacheprovider --basetemp=/tmp/visionflow-c-final-ff48ca9/pytest-temp` — **54 passed**, 9.23s.
- `timeout 60s services/api/.venv/bin/python -m pytest tests/unit/test_config_demo_safe.py tests/integration/test_demo_safe.py tests/integration/test_m2_visual.py::test_geometric_workflow_makes_zero_vlm_calls -q -p no:cacheprovider --basetemp=/tmp/visionflow-c-final-ff48ca9/pytest-safety` — **36 passed**, 2.65s.
- Executed individually with `services/api/.venv/bin/python /tmp/visionflow-c-final-ff48ca9/SCRIPT`: api_probes.py (timeout 90s), version_probes.py (120s), multiworker_probe.py (70s), physical_provenance_probe.py (30s), extra_probes.py (45s), boundary_probes.py (90s), multiworker_race.py (75s), artifact_probes.py (120s), batch_label_probe.py (35s), cleanup_probe.py (60s), optional_overflow.py (30s). All completed; their JSON results reproduce defects rather than imply PASS.
- Executed individually with `timeout 30s node /tmp/visionflow-c-final-ff48ca9/SCRIPT`: ui_probe.cjs, ui_recovery.cjs, ui_all_actions.cjs, ui_create.cjs, ui_detail_mismatch.cjs.
- Read-only Git status/history/diff and relevant source reads; committed handoff, official brief text, PRD/TRACEABILITY, protocol, immutable prior evidence and supplied receipts. Inspected only the expressly supplied local-server code in B. Final `git status --short --untracked-files=all` was empty; `git diff --exit-code` succeeded; HEAD remains the target.

## Original findings verified

| Issue | Result at the original fault boundary |
| --- | --- |
| C-005 | Original parallel same-sample cases now send one POST; repeated fallback sends one; admission timeout/oversize consume zero; sent timeout and injected audit-commit failure retain spend. Additional actual SQL interleavings still break admission, and ordinary batches self-lock. |
| C-003 | FIXED: one actual owned AVI's 12 adjacent frames, one VideoSource and six arbitrary session names are refused as one independent group. Independent synthetic sessions still train. Reencoding MAD 1.333 <= fixed 5.0 and insufficient independence are refused. |
| C-004 | Original stale data/errors/shadow/classify results are suppressed. Mismatched detail ID renders no task controls. Busy-state cleanup now blocks normal Create and task-navigation completions. |
| C-008 | Original concurrent genuine CPU fits reserve distinct v1/v2 identities, datasets and paths. Post-save failure records failed v3, removes its artifact/temp and preserves earlier artifact hashes plus another job's temp. Complete artifact loading still fails. |
| C-002 | Original missing manifest row and NaN predictions now fail closed. Same-count changed membership is rejected. Missing metric digest remains ineligible until genuine reevaluation. Artifact/input-byte integrity and stricter output validation still fail. |
| C-009 | Missing/mismatched archived targets reject before pointer changes; successful rollback loads the verified target. Corrupt archives preserve the working current model but return generic 500. Incomplete metadata remains accepted through C-008. |
| C-006 | Original dict-model response returns invalid_response/200 with actual-attempt audit retained. Malformed content/confidence is rejected. Optional metadata retains the P2 defect below. |

Original scripts remain immutable. Owned copies changed scratch/output paths and caught the now-correct one-video rejection. Because the rejected manifest activation changes the original script's subsequent rollback state, artifact_probes.py establishes a fresh genuinely trained/activated QA_ONLY v1/v2 pair before removing the archived target. SQL hooks schedule actual database reads without replacing admission or HTTP. UI probes execute the actual transpiled component and inspect real disabled attributes; manually calling a disabled handler is not accepted as usable UI.

## Remaining findings

- **C-004, P1** — page.tsx:125,155,159,167. `ui_create.cjs` reproduces permanent busy='create' after normal creation; `ui_all_actions.cjs` reproduces nine disabled controls after A→B completion. Track operation ownership separately from selection validity.
- **C-005-BATCH, P1** — service.py:384,413,429,443,448. `batch_label_probe.py` performs an ordinary three-image label job: one POST, SQLite self-lock, HTTP 500, no persisted labels/audit. End the job write transaction before independent reservations and persist completed results incrementally.
- **C-005, P1** — service.py:229,240,243,256,1156; db.py:320; labeling.py:377. `multiworker_race.py` admits two POSTs under budget 1 across two distinct Uvicorn processes; `boundary_probes.py` repeats mixed label/fallback and identical-key races. Its invalid local URL sends zero POSTs but consumes a sent attempt; corrupted cached results are reused. Make admission atomic and validate preflight/cache state.
- **C-002, P1** — service.py:796,850,882,966,977,1032. `artifact_probes.py` activates changed weights using cached F1=1, then genuine saved-artifact evaluation computes F1=0. Input-byte changes pass cached hashes; invalid types/shapes can pass, conversion errors leave stale passing gates, and malformed metrics can return 500. Bind complete evaluated provenance and strictly validate outputs.
- **C-008, P1** — service.py:600,602,604,612,1077,1113; student.py:125. `artifact_probes.py` activates/rolls back missing provenance or reversed classes and classifies v2 while reporting v1. Use mandatory verified loading everywhere and normalize archive failures.
- **C-007, P1** — labeling.py:90,301,338,341; service.py:482,1189; api.py:387. `boundary_probes.py` actual_local_scoring reproduces local_teacher.py:223,238,258's experimental_metrics envelope: two image-conditioned candidate forwards are mislabeled chat_json, revision/work counts disappear, and revision is inferred from model ID. Support and persist the actual bounded contract. The prior alternate-envelope test is insufficient evidence for this server. Severity is P1 because actual provenance required by M3-AC1/M4-AC2 is misrepresented.
- **C-006, P2** — labeling.py:291,295,352,355; service.py:424,426. `optional_overflow.py` produces one POST, OverflowError/500, no audit and a reserved ledger row. Strictly bound optional metadata and preserve received-attempt accounting.

## Acceptance criteria

- Passed in owned QA_ONLY fixtures: genuine frozen CPU fitting/save/reload, concurrent version identity and cleanup, original physical-video leakage refusal, missing/changed DB membership rejection, ordinary rollback, strict original envelope faults, stale task-data suppression and non-actioning shadow/offline responses.
- Failed: production multi-image labeling/provenance (M3-AC1), complete artifact integrity (M3-AC3), valid evaluation/activation gates (M3-AC4/5), durable admission/cache/fallback integrity (M3-AC6), and usable task/action state transitions.
- Safety: 36 focused checks preserve default demo_safe=true, disabled unsafe NL/Teacher workflow actions and zero Teacher calls for geometric workflows.
- C-001 capacity is per loop/process: single-process sync peak=1; two async loops peak=2; two-worker race peak=2. The handoff documents a single-process production assumption, but no runtime prohibition of additional workers was found. Global capacity/production enforcement is not verified; durable budget fails independently.
- NOT TESTED: approved root experiment/artifact, real GPU/provider inference or identity, natural-video quality, calibration, real Teacher comparisons, cost/savings/foveated benchmarks, live browser/mobile usability or publication. Root's 249-test/build/YOLO receipts were not rerun and do not determine this verdict. No timeout or inconclusive result was counted as PASS.

## Final recommendation

Fix the P1 defects before integrating this experimental slice. M2 remains BLOCKED; this is code QA, not M3 acceptance or permission to activate/publicize. All images/video, models, labels, simulated approvals and providers were owned QA_ONLY fixtures. Approved root assets were neither read nor modified. No real provider/GPU calls, spend, workflow actions, agents/coding CLI spawns, publication, fetch/ref/HEAD/source changes, commit or push occurred. HEAD/worktree remain frozen and clean; read-only .agents is untouched.
