# Review — LIVE / Judges

VERDICT: CHANGES_REQUIRED
TARGET_SHA: f5aeae3a9f0c04145671ffcdb51ab91f3a0fcc49

- Reviewed commit: `f5aeae3a9f0c04145671ffcdb51ab91f3a0fcc49`.
- Base commit: `d35eb21be8acc9565817949abf9d8d051e51fed8`.
- Review status: FAIL — eleven P1 findings. Additional findings exceed five because they are P1.
- One bounded fresh LIVE review. Historical M2/M3 BLOCKED verdicts, reports and accepted fallback remain unchanged. No correction cycle, integration or publication is authorized by this result.
- Read the handoff, AGENTS/CLAUDE, official extracted text, PRD acceptance/TRACEABILITY/protocol, deployment/security instructions, all 23 changed files and necessary dependencies. Original source PDF is absent.
- [Full structured report](../review-evidence/LIVE-f5aeae3/independent-scratch/LIVE.md); [JSON artifact](../review-evidence/LIVE-f5aeae3/independent-scratch/report.json). Source and `.agents` were read-only.

## Commands executed and results

- Read-only Git status/HEAD/history, base ancestry, diff stat/name-status/numstat/check; focused rg/cat/sed/nl reads.
- Inspected exact-SHA root receipts: make check exited 0 with 229 tests and legacy frontend build; make smoke exited 0 with real M1 YOLO/evidence/notification. These were not repeated and do not establish LIVE phone/planner/Teacher acceptance.
- Owned `run_pytest.py -p no:cacheprovider`: existing `tests/live` **34 passed**; fresh `test_acceptance.py` **10 passed, 32 failed**; actual-loopback `test_teacher_tcp.py` **5 passed, 17 failed**; additional framing/WS-CSRF checks **5 passed, 1 failed**, including two repeated controls. Initial harness WebSocket cookie-host mismatch was corrected before using results.
- `node frontend-contract.cjs`: committed scripts under simulated DOM/HTTP/media, **6 passed, 4 failed**. This establishes executable script contracts, not browser rendering or phone operation.
- `python live_tcp_probe.py`: actual local uvicorn/HTTP/WebSockets with owned JPEGs and scripted CV. Valid geometric control produced one notification and retrievable evidence; recorded post-logout leakage and worker death. All **28** inventoried legacy/upload/media/AutoLearn/Teacher paths returned 404 over actual TCP.
- Tests used a cleared environment, two CPU thread limits, PYTHONDONTWRITEBYTECODE=1, TMPDIR=/tmp, disabled pytest cache and owned data/basetemp paths. Python temporary artifacts stayed in the owned directory. Local TCP tests explicitly used insecure QA cookies, random PIN fixtures and scripted CV/model outputs.
- No coding CLI/agent, credentials, real provider/GPU, root experiment data, physical capture, Student activation or publication was used.

## Original fault-boundary adaptations

- **M2-001:** old keyword compilation is absent from LIVE. Tested novel truck/dwell wording through the actual model branch with intercepted subprocess output, plus semantic-condition dispatch. Real model translation remains NOT TESTED.
- **M2-003:** adapted admission/deadline checks to LIVE semaphore/httpx boundaries. Actual body trickle returned ok after **282.5 ms** against **60 ms**; expired Teacher admission still posted. Planner reached its intercepted subprocess boundary after **120 ms** against **40 ms**. Actual CLI descendants/DNS/TLS stalls were not tested.
- **M2-007:** intercepted the production httpcore first socket write, completed HTTP disable, then resumed the actual write. One local POST containing two images arrived after ACK; the later notification was correctly cancelled.
- **M2-008:** twelve malformed confidence fixtures traversed actual HTTP. Valid 0.9/integer-1 controls remained uncertain; malformed confidence rejection failed.
- **Historical transport controls:** failed HTTP attempts consume the budget; truncated Content-Length, absent chunk terminator and invalid length are rejected; correctly framed chunked response succeeds. These controls do not repair semantic dispatch.
- **M3:** isolated Student/AutoLearn routes are absent/rejected. No training, activation or rollback acceptance was inferred.

## Acceptance criteria

- **Passed portions:** exactly two landing entries; no default/bundled PIN; ordinary HTTP CSRF/role/private pairing/cross-room evidence controls; legacy rejection and no permissive CORS; concrete isolated local server startup. Actual JPEG decode/shared temporal engine/local notification/evidence/dedupe passed with scripted detections and zero geometric Teacher calls. Production source routes inference to genuine YOLO/tracking. Drafts stay inactive, canonical JSON and explicit approval work, displayed-draft edits invalidate approval, class/action rejection and escaping pass. Intercepted invocation verifies argv/stdin, shell=False, disabled tools/MCP and reduced environment.
- **Failed:** A session revocation, Origin/Host/WS/proxy trust, payload bounds and room retirement; B input validity, worker resilience and frame identity/drop accounting; C semantic fidelity, in-flight edit approval and complete deadlines; D actual-send revocation, strict confidence/labels/cache and unknown/error behavior; E re-enable/pause/expiry recovery. Valid controls do not negate these failures.
- **Deferrable discrepancies also reproduced:** extra/coerced proposal fields and overlong visual-observation question returning 500; overwritten frames reported as zero drops; events omit sequence/hash; missing cost displayed as $0.0000. No cost, accuracy or savings claims are inferred.
- **NOT TESTED / UNVERIFIED:** public HTTPS/cloudflared trust chain; external browser/device rendering; physical phone/getUserMedia/reconnect/wake lock; real subscription planner behavior and process cleanup; genuine Teacher image reasoning, authentication/model quality; real LIVE YOLO on phone frames; Student training/evaluation/activation/rollback; night/rain/local vehicle quality; billed usage/cost, savings, foveation and final public deliverables. Fixtures are not genuine Teacher or phone evidence.

## Final recommendation

Fix the P1 defects before public exposure or integration. Preserve accepted fallback and all historical BLOCKED reports. Review artifacts remain under `/tmp/visionflow-live-review-1-f5aeae3`; no source/ref changes, fetch, commit, push, real activation or publication occurred.

Final exact HEAD/status verification: HEAD `f5aeae3a9f0c04145671ffcdb51ab91f3a0fcc49`; `git status --porcelain=v1 --untracked-files=all` is empty; staged and unstaged diffs are empty. Frozen worktree is clean.
