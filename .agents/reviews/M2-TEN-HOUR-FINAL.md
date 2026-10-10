# Review — Final A M2 defect resolution

VERDICT: CHANGES_REQUIRED

TARGET_SHA: 25bccee269bde978745c168852a716670b7f999b

- Reviewed commit: `25bccee269bde978745c168852a716670b7f999b`
- Implementation commit: `f04c48d393d10fb4dc45ff5d65cfc316306d1aa4`
- Base commit: `9d69f6891ebd514876f2b9bff0aa6ab041516c6d`
- Review status: FAIL — four independently reproduced P1 defects.
- Scope: ONE final bounded A review. This does not override historical M2 BLOCKED. M1 and fallback remain untouched.
- Snapshot: HEAD equals the exact target; tracked, staged and untracked status is clean. Implementation-to-handoff diff contains only the handoff. No source, refs, HEAD or historical reports changed. Scratch evidence and this report are under the authorized `/tmp/visionflow-a-qa-25bccee`; `.agents` was not written. No fetch, commit, push, agents, coding CLIs, credential access, real provider, rental, publication or model operation.

## Commands executed

- `git status --short`, `git rev-parse HEAD`, commit/history inspection, base ancestry, changed-file diff, implementation-to-handoff diff, final unstaged/staged diffs and full status.
- Read the supplied official source text, relevant PRD M2 acceptance, traceability/protocol, exact A handoff, prior fresh consolidated report and relevant changed implementation/tests/dependencies. Inspected the self-hosted security documentation and frontend contract.
- `services/api/.venv/bin/python -m pytest -p no:cacheprovider tests/unit/test_nl_compiler.py tests/unit/test_teacher.py tests/unit/test_transport.py tests/unit/test_transport_realtcp.py tests/unit/test_vlm_router.py tests/integration/test_m2_visual.py -q --basetemp=/tmp/visionflow-a-qa-25bccee/pytest`.
- Independent `grammar_probe.py` and `network_probe.py` in the scratch directory, using the production raw-socket path and owned loopback TCP/HTTP servers. DNS/admission/connect delays and the actual socket-write pause are disclosed deterministic fault injection; TLS handshake stall occurs over an actual owned TCP connection. No MockTransport is used by these independent network probes.
- `pytest -p no:cacheprovider /tmp/visionflow-a-qa-25bccee/test_acceptance.py -q`: desired acceptance assertions over recorded independent results.
- Execution used `TMPDIR=/tmp`, bytecode/cache writes disabled, blank provider configuration, two CPU threads and individual 60-second command limits. Review completed within the 1,500-second bound.

## Test results

- Independently executed focused suite: **113 passed, three deprecation warnings, 8.98 seconds**.
- Supported compiler matrix: **240/240 correct validated drafts**, spanning six classes, four trigger families, no visual condition/four supported predicates, both action positions and decimal dwell duration. Initial test-generator plural mistakes were corrected; they were not application findings.
- Original six grammar reproductions now reject through the real HTTP compile endpoint. Six additional unsupported/ambiguous texts still return successful drafts; the highest-value cases are M2-001 below. Supported `more than 2.5 minutes` is also falsely rejected as two trigger families.
- Independent network harness completed successfully. Four desired-behavior assertions **failed**, corresponding to the four P1 findings below.
- Root receipts/logs inspected for the exact target: `make check` exit 0 in **33.09 seconds**, including **179 tests** and Next production build; `make smoke` exit 0 in **8.89 seconds**, with real YOLO event, evidence and notification. These are root results, not independently rerun checks. No full build or actual model operation was repeated.
- Evidence: [grammar results](/tmp/visionflow-a-qa-25bccee/grammar-results.json), [network results](/tmp/visionflow-a-qa-25bccee/network-results.json), [focused tests](/tmp/visionflow-a-qa-25bccee/focused-pytest.log), [acceptance failures](/tmp/visionflow-a-qa-25bccee/acceptance.log). Reproduction scripts are adjacent.

## Verified behaviors

- **M2-007 corresponding connection race is fixed.** Pausing actual `socket.create_connection`, disabling through real HTTP, then resuming produces disable 200 in 3.44 ms, zero POST bytes/attempts, `cancelled` event/action and zero notifications.
- **Actual write boundary is serialized.** Pausing the real socket's `sendall` after approval makes disable wait. Releasing the write lets both paths complete; one already-admitted request is counted and the eventual local action is cancelled. No deadlock occurred. Response waiting is outside the admission lock. Disable prevents new unsent work after acknowledgment; already-written work may still finish. The changed `on_attempt(remaining, send=...)` contract was exercised through the production router, not claimed to pass the old callback script verbatim. There is no production httpx Client-construction phase now; the connection and actual-write scenarios remain meaningful.
- Header trickle every 40 ms, headers at 160 ms followed by body stall, and chunked-body trickle each stop at **200.7–201.7 ms** against 200 ms overall. Actual TCP closure is observed before the subsequent request; the permit is free and the next request succeeds. No abandoned transport reader was observed. Slow admission/connect now prevent late POSTs, but still exceed the deadline themselves.
- **M2-008 preserved:** twelve invalid confidence fixtures (Boolean, missing, null, string, NaN/infinities, range errors and containers) traverse real HTTP provider → router → event → action and produce `invalid_response`, zero notifications. Low confidence remains non-actioning. Valid 0.9 and integer 1 controls each create one real notification. Fixtures are not model-quality evidence.
- Real HTTP 503→200 retry consumes two attempts; identical input hits cache; a different input is budget-suppressed. HTTP 401/403/422 each send once and do not confirm. Response-byte cap rejects an oversized real response. A correctly framed chunked response confirms as a positive control.
- Focused integration tests verify geometric zero-Teacher routing, sampling/cooldown/deduplication, unavailable/error handling, disabled drafts, schema validation and explicit enable. No generated-code execution path was found. Webhook action remains removed/rejected. Endpoint/model/key configuration stays server-side; docs require a private authenticated tunnel or authenticated TLS gateway. Actual deployment/authentication was not exercised.

## Findings

### M2-001 — P1 — complete intent is still reduced to a partial rule

- File and line: `services/api/app/nl_compiler.py:407`; related `:295`, `:601`, `:648`.
- Reproduction: POST `/api/workflows/compile` with “Create an alert for 5 minutes when a car stays in Service Bay A”; “When a car enters Service Bay A with hood and trunk open, create an alert”; “When 3 or more or 5 or more cars are in Service Bay A, create an alert”.
- Expected behavior: reject unsupported alert duration, multiple conditions or multiple comparisons; do not donate action parameters or discard condition terms.
- Actual behavior: HTTP 200, `ok=true`, schema-valid drafts. The alert duration becomes dwell ≥300 s despite no dwell duration being specified. Hood-and-trunk becomes trunk-only. Two inclusive comparisons become threshold 2, ignoring the second. A bare “with hood” also disappears into a geometric rule. The residual checker blanks unmatched part/state vocabulary, and action-first splitting treats all text after the action phrase as trigger text.
- Minimal suggested fix: delimit the trigger clause in both action orders; validate the intervening action tail. Consume only matched condition spans and count every comparison syntax, including inclusive suffix forms; reject remaining semantic terms. Preserve supported decimal comparison parsing.

### M2-003 — P1 — DNS, approval and TLS still escape the overall deadline

- File and line: `services/api/app/teacher.py:555`; related `:561`, `:610`; `services/api/app/vlm_router.py:325`.
- Reproduction: add a disclosed 250 ms delay around `getaddrinfo` resolving the owned loopback target with a 100 ms overall deadline; separately delay resolution 160 ms, then let the owned TCP server stall the real TLS handshake with a 200 ms overall deadline. Repeat the previous 250 ms authoritative `admit()` delay under a 100 ms deadline.
- Expected behavior: one overall deadline bounds active resolution/approval/connect/TLS/send/recv; expired work never posts, and raw transport failures become non-confirming timeout/error results.
- Actual behavior: resolution takes **250.9 ms** against 100 ms; approval takes **251.0 ms** against 100 ms. TLS takes **369.9 ms** against 200 ms and raises uncaught `TimeoutError`. No late POST is sent, but the worker/permit remains occupied until the blocking phase returns. `create_connection`'s timeout does not bound synchronous DNS, TLS inherits a stale timeout, and `admit()` itself is unbounded. A configured 40 ms read timeout is ignored until the 500 ms overall deadline. Direct connection refusal likewise escapes as `ConnectionRefusedError`; the router catches it, preventing action but losing normal transport retry/timing handling.
- Minimal suggested fix: bound resolution and the authoritative lookup, recompute remaining time before TLS and every blocking phase, honor configured phase limits, and normalize socket/SSL failures into adapter results. If work remains active after caller timeout, retain capacity until it terminates; merely rechecking before send is insufficient.

### M2-004 — P1 — partial sends bypass the attempt budget and counters

- File and line: `services/api/app/vlm_router.py:339`; related `:341`; `services/api/app/teacher.py:570`.
- Reproduction: production transport, one shared attempt budget, three distinct supported-size 4 MiB fixture images, 120 ms deadline. Owned server reads the first 8 KiB of each actual POST then stalls, causing real `sendall` timeouts. No send failure is mocked.
- Expected behavior: each started write consumes an outbound attempt even if it partially fails; budget 1 suppresses subsequent sends and counters reflect image transmission.
- Actual behavior: **three connections each receive 8,192 bytes**, while `outbound_attempts=0`, `completed=0`, shared budget remains empty and no call is budget-suppressed. Each route becomes generic `adapter raised: timed out`. Accounting occurs only after successful `sendall`, which can fail after disclosing request/image bytes.
- Minimal suggested fix: charge an admitted write before invoking `sendall`, after the final pre-send expiry/approval checks; do not refund an indeterminate partial failure. Preserve zero accounting for genuine preflight/revoked/expired-before-write cases. Normalize send errors and enforce the same budget on classified retries.

### M2-010 — P1 — malformed or incomplete HTTP responses authorize actions

- File and line: `services/api/app/teacher.py:651`; related `:655`, `:686`, `:703`.
- Reproduction: owned TCP server sends a valid positive JSON envelope, then (1) closes 500 bytes before declared Content-Length, (2) closes a chunked response without the terminal zero chunk, or (3) declares `Content-Length: garbage`. Route each through the real provider, router, event and notification dispatcher.
- Expected behavior: reject invalid/incomplete HTTP framing before label validation; transport failures cannot confirm an action.
- Actual behavior: **all three responses produce `visual_status=ok`, `action_status=done` and one persisted notification each**. EOF returns a partial body as success; invalid length becomes zero and the already-buffered body is parsed. Correctly framed chunked control also succeeds.
- Minimal suggested fix: require valid nonnegative unambiguous length and exact completion; require chunk boundaries, CRLF and terminating chunk/trailers. Raise a non-confirming transport error on premature EOF or malformed framing before constructing the successful response.

## Acceptance criteria

- **Passed portions:** M2-AC1 supported drafts/validation/explicit approval/no generated execution; M2-AC2 geometric zero-call and candidate routing; M2-AC3 strict confidence and ordinary error outcomes; M2-AC4 normal retry/cache/sampling/cooldown/deduplication; M2-AC5 corresponding disable-to-send authorization race and local-action revocation.
- **Failed:** M2-AC1 unsupported/ambiguous intent rejection; M2-AC3/AC3a overall deadline and malformed transport non-confirmation; M2-AC4/AC5 actual outbound-attempt budgets/counters on partial send.
- **Deferred risk:** unchanged M2-009 completed-result retention outside the bounded primary cache remains present at `vlm_router.py:405`; prior reproduction is preserved, not rerun. Historical UI routing-setting exposure and unfinished input strategies remain disclosed limitations.
- **NOT TESTED / UNVERIFIED:** real Teacher semantic quality, actual GPU/image inference, provider authentication/model identity/billable usage, live tunnel/TLS gateway deployment, foveated performance and cost savings, full browser/new-user journey and optional hardware. The original source PDF is unavailable; supplied source text was reviewed. No acceptance is inferred from fixture labels or test counts.

## Final recommendation

**Fix blockers.** Preserve the verified disable serialization and confidence checks. This final A snapshot requires changes; historical M2 BLOCKED remains unchanged. No further review/fix cycle is authorized by this report.

## Controller closure

This exact review returned CHANGES_REQUIRED. The authorized A workstream is
now BLOCKED and closed: no additional automatic implementation or review cycle.
Historical M1/M2 verdicts/reports and the protected fallback remain unchanged.
No A application commit is integrated into delivery. Safe original reproductions
and results are archived in `.agents/review-evidence/A-25bccee/`.
