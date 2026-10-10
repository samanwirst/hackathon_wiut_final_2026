# Review — AutoLearn ten-hour experiment, initial snapshot

- Reviewed commit: `440eaa72d32874779eae447f94ea46dcca695a17`
- Base commit: `ae2b5a5ebdaef0e9e58dd2710aee9b113a35f112`
- Review status: FAIL (root Codex QA). The separate CLI review is INCONCLUSIVE: its controller exited 130 before the 1500-second deadline, without a final verdict. The handler responds to SIGINT/SIGTERM; sender and precise signal are unavailable. This report uses executed observations, not a synthesized CLI verdict.
- Commands executed: `OMP_NUM_THREADS=2 MKL_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 VISIONFLOW_DEMO_SAFE=true NEXT_PUBLIC_API_URL=http://127.0.0.1:8094 make check`; same environment `make smoke`; owned loopback concurrent-worker reproduction; deterministic split-membership reproduction. The separate reviewer executed the exact commands retained in `.agents/review-evidence/C-440eaa7/executed-probes.json`.
- Test results: root 218 passed and production Next build passed; real YOLO smoke passed, 30 sampled frames/180 decoded frames, real event/evidence/local notification. Reviewer 20 targeted tests passed, one file-fixture test excluded; actual frozen pretrained encoder and fitted classifier save/load exercised in memory. These fixture probes are not quality measurements.
- Verified behaviors: default geometric demo guard remains enforced; actual image import and 24 local GPU Teacher requests executed through API; human approved the exact 24 image labels and 12 Teacher proposals were corrected; UI rendered all 24 decoded images. No Student was fitted on that dataset or activated.
- Unverified behaviors: natural-video accuracy, actual rental cost, GPU kernel time, foveated gains, savings, public deployment. No M3 acceptance verdict is issued.

## Findings

### C-001
- Severity: P1
- File and line: `services/api/app/autolearn/labeling.py:34`, `:140`, `:208`
- Reproduction: configure an owned loopback server with a 150ms reply and 250ms overall timeout. Two threads call `classify_sync` while the first HTTP request is active. Root observed the second thread still alive after 1.15s and one HTTP POST; reviewer additionally observed a third worker raising “bound to a different event loop.” Three same-loop delayed requests took 757ms against a 250ms deadline.
- Expected behavior: one actual active request, admission included in a finite overall deadline, no worker hangs across sync API requests.
- Actual behavior: global asyncio semaphore is reused across separate `asyncio.run` loops; waiting occurs outside the deadline.
- Minimal suggested fix: use one owned transport loop with deadline-bounded, thread-safe admission; retain capacity until transport cancellation finishes. Add real loopback concurrent sync and async regression tests.

### C-002
- Severity: P1
- File and line: `services/api/app/autolearn/service.py:261`, `:352`, `:380`, `:427`
- Reproduction: retain a version's initial split, add groups, rebuild and assign the new task split. Root reproduced former training IDs 5–8 becoming test rows. Evaluate the old version: queries read current sample splits. Reviewer inspected an old version whose stored support was four while reevaluation used 504 rows; narrowing current test rows to one still yielded a passing gate because the gate read the stale count.
- Expected behavior: immutable per-version dataset membership; held-out gate uses the exact evaluated manifest, finite metrics, support and class coverage.
- Actual behavior: task-global split is mutable; stored hash/count do not identify reevaluation rows; gate ignores computed support.
- Minimal suggested fix: persist per-version row/hash/label/split manifest and use it for evaluation, shadow and rollback. Fail closed on missing or inconsistent snapshots and invalid metrics.

### C-003
- Severity: P1
- File and line: `services/api/app/autolearn/service.py:229`, `services/api/app/autolearn/dataset.py:66`
- Reproduction: import both labels into six arbitrary groups while every row has the same session and source. Reviewer reproduced train/validation/test memberships despite one physical session. Exact-byte duplicate hashes are the only duplicate guard; reencoded or adjacent frames are not checked.
- Expected behavior: videos/sessions and related images cannot straddle partitions merely by choosing different group strings.
- Actual behavior: grouping trusts caller strings and ignores stored session/source identity; near-duplicate protection is absent.
- Minimal suggested fix: enforce physical session/source grouping, reject inconsistent group metadata, and conservatively block near-duplicate cross-split inputs. Preserve honest shared-generator limits for synthetic pilots.

### C-004
- Severity: P1
- File and line: `apps/web/app/autolearn/page.tsx:73`
- Reproduction: select Task A, select B before A's detail request completes, complete B's responses then A's. Reviewer executed the real transpiled component in a deterministic fetch harness: B remained selected, A's review labels were visible, Activate sent `/versions/101/activate` for A.
- Expected behavior: pending responses cannot change the selected task's labels or activation target.
- Actual behavior: stale detail overwrites state and buttons act on the wrong task/version.
- Minimal suggested fix: selection generation/cancellation and canonical task/version checks; clear pending detail and shadow state immediately. Test out-of-order responses. Provide concrete image import and offline classification controls so this vertical slice can be demonstrated through the UI; currently only QA fixture import is exposed.

### C-005
- Severity: P1
- File and line: `services/api/app/autolearn/service.py:156`, `:519`
- Reproduction: source inspection confirms labeling accepts an omitted limit and visits every pending row, while every low-margin classification may call the Teacher with no durable per-task call budget. Root's own experiment was manually bounded to 24; that is not an application guard.
- Expected behavior: hard explicit request budgets, duplicate suppression and versioned result reuse bound expensive offline Teacher calls.
- Actual behavior: concurrent or repeated jobs/fallbacks have no enforced cumulative admission budget.
- Minimal suggested fix: bounded task/job admission with durable attempt accounting and bounded versioned caching; no repeated charge for cached identical image/prompt/model inputs. Keep workflow actions disconnected.

### C-006
- Severity: P1
- File and line: `services/api/app/autolearn/labeling.py:64`, `:172`
- Reproduction: owned loopback provider returns valid JSON envelope with numeric `message.content=42`; reviewer observed uncaught `AttributeError: 'int' object has no attribute 'strip'`.
- Expected behavior: malformed provider response produces an explicit nonconfirming failure.
- Actual behavior: unexpected content type escapes the adapter.
- Minimal suggested fix: strict envelope/content validation with regression coverage; no coercion of provider output into a fabricated successful label.

### C-007
- Severity: P2
- File and line: `services/api/app/autolearn/labeling.py:182`, `:185`
- Reproduction: reviewer provider returned a different actual model revision but the candidate stored only configured alias; `raw` retains only usage. Real local scoring responses likewise lose method, raw scores, forward counts and revision in the application audit.
- Expected behavior: actual model/method/usage and bounded raw response provenance distinguish generation from likelihood scoring.
- Actual behavior: configured alias and token usage cannot reproduce the labeling method.
- Minimal suggested fix: preserve validated actual response model plus bounded provenance, without headers/tokens/secrets; keep likelihood confidence explicitly uncalibrated.

## Acceptance criteria

- Passed: actual pretrained frozen encoder; real classifier fitting/save/load in QA fixture probe; default geometric guard; real YOLO evidence pipeline; image import, real local Teacher proposals and application of explicit human image-label signoff.
- Failed: worker-safe Teacher admission/deadlines, immutable held-out membership and support gate, session leakage prevention, correct UI selection, call budgets, total malformed-response handling.
- Not tested: real verified-dataset Student fit/evaluation/activation/rollback, natural-video robustness, public deployment, rental billing, foveated experiment, savings.

## Final recommendation

Fix blockers in the isolated experiment. Preserve the accepted demo fallback and historical M2 BLOCKED verdict. Run fresh exact-commit review after fixes; do not claim M3 PASS.
