# Review — LIVE / Judges, fresh independent review

VERDICT: CHANGES_REQUIRED
TARGET_SHA: f5aeae3a9f0c04145671ffcdb51ab91f3a0fcc49

- Reviewed commit: `f5aeae3a9f0c04145671ffcdb51ab91f3a0fcc49`; implementation: `1c3e3b8bf94386c947efed5d8421ca88a6f1791f`.
- Base commit: `d35eb21be8acc9565817949abf9d8d051e51fed8`; review status: FAIL, eleven independently supported P1 findings. Additional findings exceed five because they are P1.
- Scope: one owner-authorized frozen LIVE review; no implementation/recovery cycle. Accepted fallback is untouched. Historical M2/M3 BLOCKED verdicts and reports remain unchanged; this result grants no integration, activation or publication permission.
- Sources: handoff, AGENTS/CLAUDE, official extracted `docs/source/README.md`, relevant PRD acceptance/TRACEABILITY/protocol, deployment/security instructions, the entire 23-file additive diff and necessary engine/local-Teacher dependencies. Original `FINAL_TASK_WIUT_HACKATHON.pdf` is absent; its authenticity/layout could not be independently checked.
- Artifacts/report: [visionflow-live-review-1-f5aeae3](/tmp/visionflow-live-review-1-f5aeae3), [JSON report](/tmp/visionflow-live-review-1-f5aeae3/report.json). Source and `.agents` remain read-only.

## Commands actually executed

- Read-only `git status --short`, `git rev-parse HEAD`, `git log --oneline -5`, base/target `git diff --stat`, `--name-status`, `--numstat`, `--check`, and `git merge-base --is-ancestor`; focused `rg`, `cat`, `sed`, `nl` reads.
- Inspected exact-SHA root receipts at `.../LIVE/checks-f5aeae3`: `make check` exit 0 (229 tests and legacy Next build), `make smoke` exit 0 (legacy M1 real YOLO event/evidence/notification). These are inspected root results, not independently repeated builds/YOLO checks. Neither receipt verifies physical phone or real LIVE planner/Teacher.
- `services/api/.venv/bin/python /tmp/visionflow-live-review-1-f5aeae3/run_pytest.py -p no:cacheprovider --basetemp=/tmp/visionflow-live-review-1-f5aeae3/existing-tmp tests/live -q`.
- Same owned harness with `test_acceptance.py -q --tb=short`, `test_teacher_tcp.py -q --tb=short`, and targeted additional malformed-framing/WS-CSRF cases; distinct owned basetemp directories.
- `node /tmp/visionflow-live-review-1-f5aeae3/frontend-contract.cjs` and `services/api/.venv/bin/python /tmp/visionflow-live-review-1-f5aeae3/live_tcp_probe.py`.
- Test subprocesses use `env -i`, two CPU thread limits, `VISIONFLOW_THREADS=2`, `PYTHONDONTWRITEBYTECODE=1`, `TMPDIR=/tmp`, explicit owned data/PYTHONPATH. Harness places Python temporary artifacts under the owned directory. Runtime PINs are random QA fixtures. Actual local TCP tests explicitly use insecure QA cookies, scripted CV and generated JPEGs. No credentials, real provider/GPU, coding CLI/agent, Student activation, root experiment data, physical capture or publication was used.

## Test results and evidence

- Existing LIVE suite: **34 passed** ([log](/tmp/visionflow-live-review-1-f5aeae3/existing-live.txt)).
- Fresh HTTP/WS/worker/planner acceptance: **10 passed, 32 failed** ([log](/tmp/visionflow-live-review-1-f5aeae3/acceptance.txt)). Initial harness WS hostname mismatch was corrected; only the corrected run supports findings.
- Actual loopback Teacher HTTP: **5 passed, 17 failed** ([log](/tmp/visionflow-live-review-1-f5aeae3/teacher-tcp.txt)); added malformed-framing/WS-CSRF checks: **5 passed, 1 failed** ([log](/tmp/visionflow-live-review-1-f5aeae3/additional.txt)). Counts include two repeated framing controls.
- Exact frontend scripts under Node VM with simulated DOM/HTTP/media: **6 passed, 4 failed** ([results](/tmp/visionflow-live-review-1-f5aeae3/frontend-results.json)). This verifies executable script contracts, not browser rendering or a physical phone.
- Actual uvicorn + HTTP/WebSocket TCP probe completed with valid control assertions and recorded fault outcomes ([results](/tmp/visionflow-live-review-1-f5aeae3/live-tcp-results.json)). Real JPEG decoding and shared temporal engine produced one local notification and retrievable 5,070-byte evidence; CV detections were explicitly scripted QA_ONLY fixtures.

## Original fault-boundary adaptations

- M2-001 keyword grammar is not wired into LIVE. Exercised the actual planner model branch with intercepted subprocess output and novel truck/dwell wording, plus faithful semantic-condition rejection/action boundaries. Real model translation remains NOT TESTED.
- M2-003 admission/deadline faults were adapted to LIVE's semaphore + httpx transport: actual TCP body trickle succeeds after 282.5 ms against 60 ms; expired admission still sends. Planner admission was exercised with intercepted spawning. No fake transport result is claimed as provider quality, and actual CLI descendant teardown/DNS/TLS stall behavior was not tested.
- M2-007 was adapted to the actual new httpcore socket write, not the obsolete transport callback. Disable ACK precedes one real local POST containing two images ([receipt](/tmp/visionflow-live-review-1-f5aeae3/teacher-disable-send.json)); final action is correctly suppressed, but privacy admission fails.
- M2-008: all twelve original invalid-confidence cases traverse actual HTTP. Valid 0.9/integer-1 controls remain uncertain. Malformed values do not retain the historical strict rejection boundary.
- Historical partial-send/framing risk: failed HTTP attempts consume LIVE's budget (passed control). Premature Content-Length EOF, missing chunk terminator and invalid Content-Length are rejected by httpx; correctly framed chunked response succeeds. These transport controls do not repair semantic dispatch.
- M3 activation/shadow/rollback paths are absent from this isolated app; unauthorized AutoLearn/Teacher routes return 404. No experimental Student was activated or claimed accepted.

## Verified behaviors

- Exactly two landing choices; no configured PIN in served static assets, no default PIN, server-side role checks, ordinary HTTP CSRF and hostile-origin rejection controls, opaque private pairing, cross-room HTTP frame/evidence rejection.
- Full unauthorized endpoint inventory: **28 legacy/upload/media/AutoLearn/Teacher paths return 404 through actual TCP**; live protected HTTP paths reject unauthenticated access; no permissive CORS header ([inventory](/tmp/visionflow-live-review-1-f5aeae3/endpoint-inventory.json)).
- Concrete separate-port deployment wiring booted locally with QA injection; legacy main API is not mounted. Actual external cloudflared/TLS configuration is unverified.
- Production worker uses genuine JPEG decoding and the accepted detector/tracker interface/temporal engine; one normal background CV worker and a latest-frame slot. Ordinary geometric control made zero Teacher calls and deduped repeated presence into one notification/evidence. Production YOLO implementation is genuine by source and the inspected root M1 receipt; independent live inference used scripted detections.
- Drafts do not auto-activate; canonical JSON is displayed; explicit approval posts that task; displayed-draft edits invalidate approval; unsupported class/action controls reject; HTML escaping and camera permission-error handling pass. Model invocation is argv/stdin, tool-less/MCP-disabled, shell=False, separate cwd and reduced environment under intercepted spawning; no generated code execution path was found.

## Findings

### LIVE-001 — P1

- File and line: `services/api/app/live/worker.py:188,215; services/api/app/live/planner.py:125`
- Reproduction: test_acceptance.py::test_semantic_condition_never_degrades_to_presence_alert: approve the simulated model proposal for “focus on the bottle if anybody opens it”; process two owned JPEGs with a scripted bottle track. Exercise unconfigured Teacher, closed/negative observation, and provider error.
- Expected behavior: Unavailable or uncalibrated opening semantics remain unsupported/unknown and cannot authorize an opening-conditioned action. A geometric presence task requires an explicitly separate user intent.
- Actual behavior: All three cases create one event and notification titled Bottle opening. The observation never gates dispatch; absent Teacher produces no unavailable observation at all. Preserving words in visual_observation does not preserve the requested condition.
- Minimal suggested fix: Reject/clarify semantic conditional tasks until they can be faithfully evaluated. Keep weak observations informational and expose unavailable/unknown. Offer geometric presence monitoring only as a separately disclosed and approved task.

### LIVE-002 — P1

- File and line: `services/api/app/live/app.py:405,473`
- Reproduction: Open camera/judge sockets, then logout or expire the server session. Send another JPEG or update the annotated feed. Also rebind a judge to room B while its room A socket remains open. Reproduced both in TestClient and actual uvicorn/TCP for logout.
- Expected behavior: Revoked/expired sessions and changed room membership immediately stop camera ingestion and private feed delivery.
- Actual behavior: HTTP correctly returns 401/403, but the existing camera socket accepts another frame and the judge receives new private bytes. Rebinding preserves access through the old room socket. Authorization is checked only at handshake.
- Minimal suggested fix: Track sockets by session/room and close them on logout, expiry and rebinding; revalidate authoritative session, role and room membership before each receive/send, including while idle. Frontends must stop 4401 reconnect loops and request reauthentication.

### LIVE-003 — P1

- File and line: `services/api/app/live/auth.py:162; services/api/app/live/app.py:164,384`
- Reproduction: Configure the exact allowed origin. Login with no Origin, with Origin=https://attacker.invalid and Host=attacker.invalid, or with the wrong scheme on the allowed host. Open a camera socket without Origin or without the corresponding CSRF cookie. Logout with a hostile Origin and no CSRF header.
- Expected behavior: Configured origin/host policy is authoritative, missing/spoofed origins are rejected on mutations and upgrades, and logout/WS cookies retain the specified CSRF boundary.
- Actual behavior: Every login returns 200; missing-Origin mutation and both deficient upgrades succeed. Logout also returns 200. Caller-controlled Host matching bypasses the allowlist, and logout has no mutation dependency.
- Minimal suggested fix: Validate the deployment host and exact scheme/host/port against server configuration using only trusted proxy metadata. Require allowed Origin for mutations/upgrades, apply the mutation guard to logout, and check the specified WS CSRF cookie/token against the authoritative session.

### LIVE-004 — P1

- File and line: `services/api/app/live/app.py:57; services/api/app/live/__main__.py:27`
- Reproduction: From one actual TCP client, submit seven wrong PINs with a different X-Forwarded-For value each time. Repeat through TestClient.
- Expected behavior: An untrusted header cannot evade the five-failure PIN limit or create arbitrary rate-limit identities.
- Actual behavior: All seven attempts return 401 rather than lockout 429. The handler trusts the first caller-supplied XFF address and the entrypoint trusts forwarding from every peer.
- Minimal suggested fix: Define the trusted proxy chain, strip/replace client forwarding headers at that boundary, and rate-limit using its verified client identity; reject direct spoofed forwarding. Bound/prune the failure-key registry. Actual cloudflared header rewriting remains NOT TESTED.

### LIVE-005 — P1

- File and line: `services/api/app/live/app.py:409,433; services/api/app/live/worker.py:87,114`
- Reproduction: Send an empty camera binary message, a small 1200x64 JPEG declared as 320x240, sequence numbers 9/9/8, NaN capture_ts, and 512-KiB HTTP JSON/WS metadata. Use the owned acceptance tests; the empty-message failure is also exercised through actual TCP and the actual worker loop.
- Expected behavior: Bound bytes and decoded dimensions before inference, validate finite metadata and increasing sequence, reject oversized HTTP/text messages, and isolate malformed frames so the worker survives.
- Actual behavior: Empty bytes raise cv2.error out of the sole worker; it dies while health still reports ok. Oversize decoded dimensions reach inference; all duplicate/stale frames are admitted; NaN events make state return 500. Oversize JSON and WS metadata are accepted.
- Minimal suggested fix: Add pre-parse body/text limits and strict frame metadata, inspect JPEG dimensions before allocating/inferencing, reject empty/non-JPEG/nonfinite/stale frames, and catch per-frame decode/inference failures inside the worker loop. Report worker liveness in readiness.

### LIVE-006 — P1

- File and line: `services/api/app/live/rooms.py:117,150; services/api/app/live/auth.py:130`
- Reproduction: Create a room with each of nine fresh camera sessions and log each owner out immediately; no judges remain. test_rooms_retire_on_owner_logout_and_new_users_can_start records the statuses.
- Expected behavior: Orphaned rooms, pairing codes and retained media expire/release capacity so later supported new users can create rooms.
- Actual behavior: The first eight creations return 200 and the ninth returns 503. close_room is never called by production code; room/judge tokens and evidence have no lifecycle/TTL cleanup. Logout does not retire the orphaned room.
- Minimal suggested fix: Wire owner logout/session expiry and an idle/retention deadline to deterministic room retirement, clear pairing/membership/media, and delete associated evidence. Remove expired judge memberships and release room/judge capacity.

### LIVE-007 — P1

- File and line: `services/api/app/live/rooms.py:215; services/api/app/live/app.py:348; services/api/app/live/static/judges.html:140`
- Reproduction: Activate a valid geometric task, disable it, then POST enabled=true and process three frames. Separately pause/resume while inference is held and release the old inference. POST enabled="false" as a contract control; execute renderState for a disabled task.
- Expected behavior: Re-enable restores an evaluated task without resetting the camera; pause invalidates old work; control payloads are typed and the UI offers re-enable.
- Actual behavior: Re-enable reports running with zero engines and zero notifications. Pause/resume leaves the generation unchanged and old inference produces a notification after the pause ACK. The string "false" becomes enabled=true. Disabled UI has no re-enable control.
- Minimal suggested fix: Use strict Boolean request models. Bump execution generation on revocation, rebuild valid engines on re-enable/resume with explicit timing semantics, and add a re-enable control using the same approved task without touching camera state.

### LIVE-008 — P1

- File and line: `services/api/app/live/worker.py:185,192; services/api/app/live/teacher.py:144`
- Reproduction: test_teacher_tcp.py::test_original_actual_write_revocation_boundary pauses the production httpcore socket write before POST headers, completes task disable over HTTP, then resumes the real write to an owned loopback Teacher fixture.
- Expected behavior: No new Teacher image request is sent after disable acknowledgment; authorization must cover the actual send boundary.
- Actual behavior: One actual POST containing two JPEGs arrives after disable ACK. The later local action is cancelled, but private frame admission has already occurred. The final version check protects notification dispatch only.
- Minimal suggested fix: Pass an authoritative room/task generation guard into Teacher admission and serialize its check with the actual first write and disable acknowledgment. Check again after semaphore waiting; cancel unsent work and retain capacity for already active work until it ends.

### LIVE-009 — P1

- File and line: `services/api/app/live/teacher.py:140,146; services/api/app/live/planner.py:275,286`
- Reproduction: Actual loopback Teacher returns a body in 16-byte chunks every 20 ms under a 60-ms configured timeout. Hold Teacher admission 120 ms under a 40-ms timeout. Hold planner admission 120 ms under 40 ms with subprocess.run intercepted; no CLI/model is spawned.
- Expected behavior: A single monotonic deadline includes admission, send/read and completion; expired waiting work never starts a new provider call.
- Actual behavior: Teacher returns ok after 282.5 ms; httpx timeout is a per-operation inactivity limit. A Teacher POST starts after the admission deadline, and the planner reaches the intercepted subprocess boundary after 120 ms. The inline Teacher call can stall the sole CV worker indefinitely on a paced response.
- Minimal suggested fix: Carry one absolute deadline through queue admission and every transport/process phase, use remaining time, bound response bytes and actively close expired transports. Keep concurrency capacity until underlying work stops; include planner queue time in its process deadline.

### LIVE-010 — P1

- File and line: `services/api/app/live/teacher.py:85,122,168`
- Reproduction: Route twelve original malformed confidence fixtures through actual HTTP to /probe; return the committed local Teacher candidate-scoring envelope with occupied/empty labels for an opening/closed request. Change room, requested labels and configured model while reusing image/question.
- Expected behavior: Strict finite numeric confidence and requested-label validation; unsupported/local scoring capabilities return unknown. Cache identity and exposed provenance reflect the actual room/schema/model/revision.
- Actual behavior: Boolean/string/out-of-range/missing confidence is accepted as ok or raw fallback; NaN/infinities poison JSON into 500. Occupancy candidate scoring is reported ok for a bottle-opening question. Requested labels are not sent to the provider. Changed room/model/label schema reuses the first observation without a new request.
- Minimal suggested fix: Validate a bounded typed provider contract, reject nonfinite/coerced confidence and out-of-schema labels, preserve actual scoring/model/revision/usage, and explicitly reject unsupported questions. Scope/version cache keys by room, task/prompt, labels, model/revision and ordered frame identity; invalidate expired entries.

### LIVE-011 — P1

- File and line: `services/api/app/live/static/judges.html:171,216`
- Reproduction: Execute the exact committed Judges script with a delayed simulated plan response. Edit the prompt while the request is pending, then resolve the old response.
- Expected behavior: Any prompt edit invalidates pending approval, including an in-flight request; an old result cannot become approvable.
- Actual behavior: The input handler only invalidates an existing currentDraft. The late response then installs the obsolete task and reveals Approve & activate. The same script correctly invalidates an already displayed draft.
- Minimal suggested fix: Increment a request/prompt generation on every edit/discard/new plan, clear approval immediately, and discard responses whose generation or submitted text no longer matches. Keep the approved payload tied to the displayed canonical task.

## Acceptance criteria

- **Passed portions:** A isolated legacy rejection, landing/PIN/ordinary role and HTTP room boundaries; B normal decode/temporal/local action/evidence/dedupe and single-worker path; C intercepted tool-less model branch, allowlisted supported task, disabled draft/canonical JSON/explicit click; D selective event/manual routing and geometric zero-Teacher controls; E valid API/frontend script contracts and local runnable isolated server.
- **Failed:** A live-session revocation, exact Origin/Host/WS/logout checks, verified-client rate limits, payload bounds and room retirement; B decoded dimension/finite sequence validation, worker resilience and frame identity/drop accounting; C semantic fidelity, pending-edit approval invalidation and complete runtime deadline; D post-disable Teacher admission, strict confidence/schema/model-aware cache, failure/unknown semantics; E disable/re-enable/pause generation and expiry recovery.
- **Deferrable discrepancies, also reproduced:** planner proposals tolerate extra fields/coerce scalar types and an overlong visual-observation question raises 500; four overwritten frames report zero drops; event payloads omit sequence/hash; missing cost is displayed as $0.0000. These are not accuracy, savings or cost evidence and should be corrected without rewriting accepted fallback.
- **NOT TESTED / UNVERIFIED:** public HTTPS/cloudflared trust chain, external devices/browsers, physical getUserMedia/phone reconnect/wake lock, real paid/subscription planner behavior and prompt fidelity, actual CLI process cleanup, genuine Teacher image reasoning/labels/model quality or provider authentication, real LIVE YOLO on phone frames, Student training/evaluation/activation/rollback, night/rain/local vehicle quality, actual billed usage/cost, savings, foveation and official final public deliverables. No fixture is genuine Teacher or phone evidence.

## Final recommendation

**Fix the P1 defects before public exposure or integration.** Keep the accepted fallback and historical BLOCKED closures unchanged. This report initiates no correction cycle and authorizes no publication or real activation. All review artifacts are owned QA_ONLY files under `/tmp/visionflow-live-review-1-f5aeae3`.

Final exact HEAD/status verification: HEAD `f5aeae3a9f0c04145671ffcdb51ab91f3a0fcc49`; porcelain status '' (clean); staged/unstaged diffs empty. No source, refs, historical reports, fetch, commit or push changes.
