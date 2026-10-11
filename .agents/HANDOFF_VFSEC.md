# HANDOFF — VFSEC owner-final emergency round

Base reviewed SHA: `e75554d91ddb15896a23c3b2b260657193cb8790`
Review: `.agents/reviews/VIDEO-FINAL.md` (CHANGES_REQUIRED, nine P1).
Scope (owner-assigned): **LIVE-VIDEO-001, 005, 006, 007, 008** only.
Owned files: `services/api/app/live/{app,auth,dsl,planner,config}.py` (+ `__main__.py` — no change needed),
new `tests/live/test_owner_final_security.py`, plus transparent source-contract/harness updates to
`tests/live/test_acceptance.py` and `tests/live/test_live_planner.py`.
NOT touched: `video.py`, `rooms.py`, `static/*` (findings 002/003/004/009 — VIDEO owner).
No push. M2/M3 BLOCKED, Student OFF, fallback `723a4a7` preserved. Camera/Teacher paths stay inaccessible.

## Baseline reproductions (run on e75554d BEFORE fix, from /tmp/visionflow-live-review-2-e75554d)
- 001 `test_video_acceptance.py::test_semantic_opening_request_is_unsupported_and_nonactioning` — FAILED (presence alert fired).
- 005 `test_video_acceptance.py::test_activation_dsl_strictness` — all 5 cases FAILED (bool/str coerced, extras+cooldown dropped).
- 005 `test_additional_boundaries.py::test_unconsumed_proposal_constraint_cannot_be_ignored` — FAILED (approval not bound).
- 006 `test_video_acceptance.py::test_host_allowlist_applies_with_allowed_origin` — FAILED (hostile Host accepted).
- 007 `test_video_acceptance.py::test_chunked_json_actual_body_cap` — FAILED (chunked bypass -> 200).
- 008 `test_additional_boundaries.py::test_owned_planner_timeout_does_not_release_live_descendant_capacity` — FAILED (descendants outlive permit).

## Fixes (ID -> change -> covering test)
- **LIVE-VIDEO-001** — `planner._finalize` + `dsl.LiveTask` + `dsl.capabilities_doc` + planner system prompt reject
  semantic/visual_observation/state-change requests fail-closed when `CAMERA_INGEST_ENABLED` is False (enabled VIDEO);
  NO closest-geometry fallback. `/probe` route returns 404 in VIDEO mode (Teacher path inaccessible). Legacy camera path
  (camera enabled, local QA) unchanged. Tests: `test_owner_final_security.py::test_001_*`;
  updated `test_live_planner.py` (new `test_semantic_request_is_unsupported_in_video_mode` +
  `test_temporal_semantic_preserves_intent_on_legacy_camera`).
- **LIVE-VIDEO-005** — `dsl.LiveTask`/`ZoneSpec` strict `extra=forbid` (recursive), `focus` StrictBool, bool rejected for
  duration/threshold/cooldown; NEW supported `cooldown_seconds` (float, default None -> VIDEO uses
  `config.DEFAULT_COOLDOWN_SECONDS=10`); full_frame + conflicting polygon now REJECTED (intent not silently lost);
  dwell 1.25 exact preserved. Canonical server-bound approval drafts in `app._drafts`/`_drafts_lock` (NOT rooms.py):
  `plan` and new `POST /task/validate` expose `draft_hash`+`expected_version`; `activate` enforces them when supplied
  (wrong/missing-counterpart/stale/replay/source-change -> 409/422; draft consumed one-shot). `{task}`-only activation
  still 200 (preserves reviewer VIDEO happy path). Tests: `test_005_*`.
- **LIVE-VIDEO-006** — `auth.origin_allowed` now also requires `host_trusted(host)` when `ALLOWED_HOSTS` set (Host
  authoritative on HTTP+WS); `auth.client_identity` honors X-Forwarded-For ONLY from a direct peer in
  `FORWARDED_ALLOW_IPS` (or `*`), so untrusted-peer raw XFF cannot bypass PIN lockout. `__main__.py` already wires
  `proxy_headers=True`+`forwarded_allow_ips` correctly (no change). Tests: `test_006_*`.
- **LIVE-VIDEO-007** — replaced the header-only body check with a pure-ASGI `_BodyBoundMiddleware` that counts ACTUAL
  received bytes before JSON parsing (chunked bypass closed, independent of Content-Length) with a
  `config.REQUEST_RECEIVE_DEADLINE_SECONDS` receive deadline; video upload streams under its own byte cap (not buffered).
  Tests: `test_007_*`.
- **LIVE-VIDEO-008** — `planner._run_cli` uses `Popen(start_new_session)` + bounded drain threads
  (`config.PLANNER_MAX_OUTPUT_BYTES`, no unbounded `communicate`); on timeout the whole process GROUP is SIGKILLed and
  reaped BEFORE the concurrency permit is released, so descendants cannot outlive a timeout. Tests: `test_008_*`;
  updated `test_acceptance.py::test_model_branch_novel_wording_and_invocation_contract` to the Popen contract and fixed
  its fixed-ROOT path harness assumption (preserving all real security assertions: shell=False, tools empty, STDIN-only
  text, minimal env, safe-mode/strict-mcp, isolated cwd outside repo, start_new_session).

## Explicit contract adaptations (owner-authorized)
1. Reviewer `test_activation_dsl_strictness[cooldown_seconds=1.25]` expected 422; owner mandated SUPPORTING
   `cooldown_seconds`, so 1.25 now returns 200 (faithfully carried, not silently dropped).
2. Approval binding is enforce-when-present (not hard-required) because the reviewer's own accepted VIDEO acceptance
   activates with `{task}` only and asserts 200. The full plan/validate/activate binding is available and the UI must
   send it.
3. Reviewer `test_video_probe_route_is_noninvocable_without_camera_input` expected 409; the route now returns 404 in
   VIDEO mode — stronger fail-closed, per "disable Teacher /probe route in VIDEO".

## Commands run (2 CPU threads)
- `pytest tests/live/test_owner_final_security.py` -> **21 passed**.
- Five findings' baseline repros (/tmp) after fix -> **10 passed**, only `cooldown_seconds-1.25` flips to 200 (adaptation #1).
- Non-baseline repo live files (`test_live_planner/auth/frames/hardening/video_pipeline/semantic/teacher`) -> **81 passed**.
- `tests/live/test_acceptance.py` -> 32 passed / 11 failed; the 11 are the documented pre-existing baseline C/H nodes
  (camera/judge WS revocation, rooms-retire, jpeg/empty-frame/ws-metadata/latest-queue bounds, event frame identity =
  findings 002/003/004/009). `test_model_branch` and `test_exact_source_imports` now PASS.
- Reviewer `test_video_acceptance.py` -> 14 passed / 9 failed; 7 failures are findings 002/003/004 (VIDEO owner),
  2 are adaptations (#1, #3). `{task}`-only activation returns 200.

## Coordination for ROOT / VIDEO / UI owners
- `/.agents/runtime/ten-hour/VF/coordination-VFSEC.json` records the draft/approval contract + all changes.
- VIDEO owner: consume `task["cooldown_seconds"]` in `rooms.build_engines` as
  `(task.get("cooldown_seconds") or config.DEFAULT_COOLDOWN_SECONDS)`, replacing the hardcoded `10.0`.
- UI owner: after plan/manual-edit call `POST /task/validate`, then activate with `{task, draft_hash, expected_version}`.
- ROOT: runs full `make check` / frontend build / real-YOLO smoke once on the integrated exact SHA; then ONE fresh Codex review.

## Known limitations
- Findings 002/003/004/009 remain open (other owner's files). Full-regression gate and all historical BLOCKED reports
  remain as-is. No push performed.
