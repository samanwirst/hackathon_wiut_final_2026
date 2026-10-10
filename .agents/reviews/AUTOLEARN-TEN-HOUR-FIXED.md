# Review — AUTOLEARN-TEN-HOUR-FIXED

VERDICT: CHANGES_REQUIRED
TARGET_SHA: 5938b6d1f1396c1513d52ee9d9c3cdb377dc43a4

- Reviewed commit: `5938b6d1f1396c1513d52ee9d9c3cdb377dc43a4` (code `699775eca6cf12ab7c18512215c31197aba509b0`).
- Base commit: `440eaa72d32874779eae447f94ea46dcca695a17`.
- Review status: FAIL — 7 P1 findings and 2 P2 risks.
- Evidence/report: `/tmp/visionflow-c-qa-5938b6d/`.
- Worktree clean; HEAD unchanged.

## Commands executed

All Python checks used TMPDIR=/tmp, PYTHONDONTWRITEBYTECODE=1, VISIONFLOW_DEMO_SAFE=true, OMP_NUM_THREADS=2, MKL_NUM_THREADS=2, OPENBLAS_NUM_THREADS=2, reviewer-owned VISIONFLOW_DATA_DIR, and timeout 60s. No command exceeded 60s.
- `services/api/.venv/bin/python -m pytest tests/unit/test_autolearn_core.py tests/unit/test_autolearn_labeling_transport.py tests/unit/test_autolearn_c_service.py tests/unit/test_autolearn_c_transport.py tests/integration/test_autolearn_api.py -q -p no:cacheprovider`
- `services/api/.venv/bin/python /tmp/visionflow-c-qa-5938b6d/{api_probes,version_probes,multiworker_probe,extra_probes,physical_provenance_probe}.py` (individual executions)
- `node /tmp/visionflow-c-qa-5938b6d/ui_probe.cjs`
- Read-only `git status --short`, `git rev-parse HEAD`, `git log`, `git diff 440eaa7..5938b6d`; source brief, PRD/traceability, protocol, current handoff, initial report and supplied check receipts.

## Test results and verified behaviors

41 focused regressions passed (3 deprecation warnings, 13.06s). Genuine CPU encoder/Student training, save/reload, computed metrics and sequential old-version membership/artifact retention were independently exercised. Owned TCP checks verified single-process sync serialization, deadline/cancellation and post-cancellation reuse. Malformed content/confidence are rejected. Actual PNG/JPEG upload, provenance persistence, exact-duplicate suppression, unreadable-image rejection, fixed MAD reencoding refusal (1.333 <= 5.0), and honest insufficient-independence refusal were exercised. Actual-component harness confirmed FormData/provenance/offline wiring and an error banner; initial stale detail-fetch protection works. QA shadow/fallback/classification responses carry no actions; source inspection keeps AutoLearn disconnected from dispatch.

## Findings

### C-005

- ID: C-005
- Severity: P1
- File and line: `services/api/app/autolearn/service.py:153, 214, 244, 267, 764, 795`
- Reproduction: api_probes.py: two concurrent production-route /label jobs, then two /classify fallbacks, with task budget=1 and a delayed owned TCP provider. multiworker_probe.py repeats /label with two production Uvicorn processes. Repeat the same fresh fallback image three times. Queue a 100ms-deadline job behind a longer-deadline request; separately lower the local image cap after import.
- Expected behavior: Reserve durable task budget atomically before HTTP admission, across jobs/processes; identical completed/in-flight inputs reuse results; only actual outbound attempts consume spend.
- Actual behavior: Both two-request cases sent 2 POSTs under budget 1. Two worker processes sent 8 POSTs for the same pending sample under budget 1; all returned HTTP 200 and budget_remaining=0. Repeated identical fresh fallbacks sent 3 POSTs because freeform results are never cached. An admission-only timeout and a local oversize rejection each reported attempts_made=1 and consumed durable budget despite zero respective POSTs.
- Minimal suggested fix: Use an atomic durable reservation shared by labeling and fallback at the transport boundary, with committed admission/attempt state independent of job completion. Persist a bounded versioned fallback cache and deduplicate in-flight keys. Report explicit actual-attempt metadata rather than inferring attempts from status strings.

### C-003

- ID: C-003
- Severity: P1
- File and line: `services/api/app/autolearn/service.py:353, 361, 383`
- Reproduction: physical_provenance_probe.py creates ONE actual QA_ONLY AVI, decodes its 12 consecutive frames, attaches every row to the same VideoSource, and assigns six arbitrary session/group names before building the split.
- Expected behavior: All frames from one uploaded video remain in one partition regardless of caller session names; insufficient physical independence refuses training (M3-AC2).
- Actual behavior: The one video was accepted as 6 train / 2 validation / 4 test rows. Adjacent frames at timestamps 1.5s and 2.0s landed in train and test. The canonical source-plus-session key still treats arbitrary names as independent video sources; the fixed near-duplicate check did not close this provenance hole.
- Minimal suggested fix: Group uploaded-video rows by immutable video/source identity. For session-based sources, validate physical session ownership and group connected source/session identities together; do not let free-form group/session names subdivide one video.

### C-004

- ID: C-004
- Severity: P1
- File and line: `apps/web/app/autolearn/page.tsx:136, 248, 290, 308, 345`
- Reproduction: ui_probe.cjs executes the actual transpiled component. Start labeling/upload/shadow/classification on A, select B, resolve B detail, then finish A. The Activate request is captured only by a disclosed QA fetch fixture.
- Expected behavior: Every delayed operation commits results only to its original selection generation, and visible manual controls always target the selected task/version.
- Actual behavior: Delayed labeling and upload call reloadCurrent with captured A but B's current generation: B remains selected while A labels/details reappear. Activate then targets /versions/101/activate for A. Delayed shadow and classify results also display A results under B. Initial detail-fetch generation protection works, but action completions bypass it.
- Minimal suggested fix: Capture task ID and generation when each action starts and retain them through reload/result/error commits. Reject stale completions and require detail.task.id to match the selected ID before rendering/action dispatch. Guard shadow/classify results too.

### C-008

- ID: C-008
- Severity: P1
- File and line: `services/api/app/autolearn/service.py:451, 456, 457, 492; services/api/app/db.py:215`
- Reproduction: version_probes.py runs two actual /train requests using genuine frozen CPU embeddings and fitted Students. A QA barrier at save pauses the first request, imports additional independent QA sessions, then starts the second. The real saves are serialized only to avoid nondeterministic file corruption.
- Expected behavior: Each training job reserves a unique version and immutable artifact path; stored metadata/manifest always identify the artifact that was evaluated.
- Actual behavior: Both requests returned HTTP 200 with version=1 and different model_version IDs/dataset hashes. Both registry rows point to the same task_2/v1.pt; the surviving artifact metadata matches only the first snapshot, while the other row retains metrics/manifest for a different fitted model. A post-save injected failure also leaves orphan v1.pt with no failed job/version record.
- Minimal suggested fix: Reserve version identity transactionally before fitting; enforce unique (task_id, version), save to a unique temporary artifact and atomically finalize, and register success/failure without overwriting another version. Verify artifact metadata against its registry row on load.

### C-002

- ID: C-002
- Severity: P1
- File and line: `services/api/app/autolearn/service.py:520, 529, 638, 695, 757`
- Reproduction: version_probes.py removes one held-out manifest row from an owned QA version after evaluation, then calls gate/activate before reevaluation. extra_probes.py injects nonfinite negative-class probabilities at the classifier boundary of a real QA artifact and calls evaluate/gate/classify.
- Expected behavior: The gate is tied to a complete current frozen manifest and valid evaluated outputs; invalid/nonfinite outputs fail evaluation and yield unknown/fallback rather than a passing model.
- Actual behavior: A missing manifest row still produced gate.passed=true and activated=true using cached metrics. Only a later evaluation exposed support 11 versus test_count 12 and denied the gate. NaN negative probabilities were silently thresholded to negative predictions, producing finite F1=1/support=6 and a passing gate; offline classification of the NaN result returned HTTP 500. Sequential retraining does preserve the old manifest and artifact correctly.
- Minimal suggested fix: Validate manifest completeness, unique membership, hash/label consistency and metric provenance at gate/activation time, including versions created before manifests existed. Validate prediction shape and every probability as finite/in-range before metrics or decisions; clear invalid evaluation and return explicit non-actioning unknown/failure.

### C-009

- ID: C-009
- Severity: P1
- File and line: `services/api/app/autolearn/service.py:722, 735, 739, 754`
- Reproduction: version_probes.py trains and activates two reviewer-owned QA Students, archives the first, removes only its scratch artifact, and invokes the real rollback and classification routes.
- Expected behavior: Rollback restores a loadable known-good previous artifact/configuration, or fails visibly while preserving the current active version.
- Actual behavior: Rollback returned HTTP 200 rolled_back_to=1, persisted that broken version as active, and recorded gate_passed=true without loading or checking it. The next classification returned HTTP 500 because the artifact was missing.
- Minimal suggested fix: Validate the previous artifact, expected encoder/preprocessing/class mapping and frozen evaluation integrity before committing rollback. Reject an unusable target and retain the working current model; surface a bounded explicit failure.

### C-006

- ID: C-006
- Severity: P1
- File and line: `services/api/app/autolearn/labeling.py:247, 254; services/api/app/autolearn/service.py:262, 267`
- Reproduction: api_probes.py returns otherwise valid label/confidence JSON with an envelope model={"invalid":"object"} from the owned loopback provider; call the actual /label route.
- Expected behavior: Malformed envelope metadata yields invalid_response and a durable actual-attempt record; provider-controlled values never escape validation into incompatible DB fields.
- Actual behavior: The adapter returned status=labeled with a dict model. The API then raised sqlite3.ProgrammingError binding response_model, returned HTTP 500 and retained no audit row despite one actual POST. Numeric/object/bool content and malformed confidence are now correctly rejected.
- Minimal suggested fix: Validate model identity as an optional bounded string and allowlist usage/provenance fields before returning a candidate. Reject malformed metadata explicitly, and persist admitted/outbound attempt accounting independently of subsequent sample/audit commit failures.

### C-001

- ID: C-001
- Severity: P2
- File and line: `services/api/app/autolearn/labeling.py:53, 63, 277, 305`
- Reproduction: api_probes.py runs supported async classify calls on two event loops concurrently. multiworker_probe.py starts the unchanged production API under two Uvicorn processes, with a QA response-header wrapper to identify the workers.
- Expected behavior: A claimed global serial capacity limit must cover all supported interfaces/workers; any narrower scope must be explicit and included in deployment/cost assumptions.
- Actual behavior: Two async loops made two overlapping POSTs with concurrency=1; the two-process production route also reached provider_peak=2. Single-process sync API requests correctly share capacity=1 and the genuine trickle timed out in about 202ms with transport reuse succeeding.
- Minimal suggested fix: Route async and sync callers through shared deadline-aware admission, and coordinate worker-process capacity if a global limit is required. Otherwise explicitly expose/document the per-loop/per-process bound and enforce the durable task limit separately.

### C-007

- ID: C-007
- Severity: P2
- File and line: `services/api/app/autolearn/labeling.py:247, 257, 259; services/api/app/autolearn/api.py:384`
- Reproduction: api_probes.py returns a disclosed scoring envelope with two-candidate likelihood method, candidate scores, forward count and actual model revision metadata, plus valid label text. Inspect LabelCandidate/raw and the production audit response; no actual provider was queried.
- Expected behavior: Generation and image-conditioned likelihood scoring remain distinguishable, with bounded actual revision/method/scoring provenance and no invented model identity or credentials.
- Actual behavior: The adapter unconditionally stores method=chat_json and drops scoring/revision metadata, presenting scoring as generated JSON. A missing response model falls back to the configured alias. The audit endpoint omits even the newly stored response_model/method columns, so callers cannot inspect them. Confidence remains explicitly uncalibrated in the candidate.
- Minimal suggested fix: Preserve validated allowlisted provider method/revision and bounded candidate-score/forward-count metadata; distinguish configured alias from an unknown actual model. Expose actual model/method in audit responses and persist the uncalibrated-confidence flag, without credentials or headers.

## Unverified behaviors and scope

This is experimental QA, not M3 acceptance. All images/videos, labels, simulated review/activation/rollback decisions, failure injections and HTTP providers were disclosed QA_ONLY fixtures under /tmp. The root's approved 24 images/signoff were neither accessed nor modified. No GPU/real provider requests, workflow actions, agents, coding CLI, rentals, publication or ref/HEAD/source mutations. Root receipts name this SHA and record the 236-test/Next build and real YOLO smoke success; those broad checks were not repeated and are not this review's independent quality measurements. Natural-video accuracy, calibration, savings/cost, real-provider performance and root's partition amendment remain unverified. No live browser was run; 390px mobile usability remains a risk despite source CSS for the provenance grid and scrolling tables. Scratch report replaces the read-only .agents report path; no branch, fetch, commit or push was performed under the explicit mutation/publication prohibition.

## Acceptance criteria

- Passed in QA fixtures: actual fit/save/load, sequential frozen membership, strict label/confidence checks, fixed reencoding refusal, declined approval, ordinary offline rollback/classification, no shadow actions.
- Failed: atomic budget admission/reuse/accounting (M3-AC6), physical video independence (M3-AC2), selected-version UI controls, concurrent immutable artifact registration (M3-AC3), invalid snapshot/output gates (M3-AC4/5), failure-safe rollback (M3-AC6), total provider-envelope handling (M3-AC1).
- Not tested: real Teacher/verified root-data Student quality (M3-AC7), natural-video benchmarks, measured cost/savings/foveated comparison (M3-EXP1), live 390px browser behavior.

## Final recommendation

Fix the P1 defects before integrating this experimental slice. M2 remains BLOCKED; M3 is not accepted. Keep unsafe Teacher workflow actions off.

## Controller evidence packaging

The independent reviewer returned CHANGES_REQUIRED for this exact SHA. The
controller preserved the original report and copied only reviewer-owned scripts,
JSON results and the regression receipt into `.agents/review-evidence/C-5938b6d/`.
No raw images/videos/databases/weights, approved user assets, secrets or CLI logs
are included. The first focused C fix did not close seven material defects.
One final second normal fix/review pass is authorized within the code-freeze
window; this report is never replaced with a PASS.
