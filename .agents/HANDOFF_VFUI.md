# HANDOFF — VFUI (VIDEO frontend) emergency recovery

- **Base SHA:** `e75554d91ddb15896a23c3b2b260657193cb8790`
- **Scope:** LIVE-VIDEO-009 (frontend portion) + frontend portion of LIVE-VIDEO-005.
- **Ownership edited:** `services/api/app/live/static/judges.html`, `services/api/app/live/static/upload.html`, NEW `tests/frontend/owner_final_video_contract.cjs`, this file. **No Python edits.**
- **Not pushed.** ROOT integrates on the exact SHA and runs full checks/build/YOLO + one fresh Codex review.

## Baseline reproduction (recorded before fixing)
`node /tmp/visionflow-live-review-2-e75554d/frontend-video-contract.cjs` against the base worktree → **3 PASS / 3 FAIL**:
- FAIL "source video has actual playback and source-timed progress" — judge only polled latest JPEG; no `<video>`/progress.
- FAIL "expired polling visibly revokes the stale running display" — 401 swallowed, stale state retained.
- FAIL "approval is bound to canonical draft hash/version" — activate sent only `{task}`; no hash/version.

## Fixes

### LIVE-VIDEO-009 — progress / job status / source clock / error / auth recovery
- **judges.html:** added `<video id="sourceVideo">` (authenticated `/api/live/rooms/{id}/video/source` replay) and `#jobInfo`. `renderState` now shows real `job_status`, `job_processed/job_total`, source-clock `t=…s / …s` (from `meta.fps`) and `job_error` — **independent of task enablement** (enabled ≠ running). Source player binds once a job exists for the room.
- **Auth recovery:** `isAuthError()` + `requireLogin()`. On 401/403 from any poll/mutation, timers stop, feed/source/events/task displays reset, `main` hides, sign-in re-shown, banner requests login. Non-auth (transient) errors keep last state.
- **upload.html:** same auth recovery; `#jobInfo` shows status + count/total + source clock + error; added source replay `<video>`; source bound after upload and during polling.

### LIVE-VIDEO-005 (frontend) — canonical digest + version approval binding
- **judges.html:** `showDraft` captures `draft_hash` + `expected_version` from plan/validate. `activate` sends strict `{task, draft_hash, expected_version}` (only fields the server issued); a stale/edited/discarded draft (`!currentDraft`) can never be approved. Server rejection shows its reason — no silent fallback. Decimal `duration_seconds` (1.25) preserved unchanged through preview → approval body.
- **Manual edit flow:** `#editJson` + `#validateBtn`. Any edit invalidates the pending approval (clears draft/hash/version, hides Approve); **Validate** POSTs `/task/validate` and re-renders the canonical preview + fresh digest/version before approval re-binds. Validation PREVIEW is shown before the human approves exactly that version.
- Unknown planner cost now renders **"cost unavailable"**, not `$0.0000`.

## Backend routes required from SEC (frontend fails closed without them)
See `.agents/runtime/ten-hour/VF/coordination-VFUI.json`. Summary:
1. `GET /api/live/rooms/{id}/video/source` — auth, same-room, `FileResponse` MP4, no raw paths.
2. `POST /api/live/rooms/{id}/task/validate` — `{task}` → canonical `{task, draft_hash, expected_version}`, strict extra-forbidden.
3. `plan` success augmented with `{draft_hash, expected_version}`; `activate` accepts/validates `{task, draft_hash, expected_version}`, rejects stale/mismatch with reason, preserves decimal cooldown.

## Tests (ID → file → original failure → current result)
- `tests/frontend/owner_final_video_contract.cjs` — **16/16 PASS** (node VM, simulated DOM/HTTP; not a browser).
  - LIVE-VIDEO-009: source `<video>`; real job status/count/total/source-clock; enabled≠running; job error; same-room source binding; 401/403 revoke + sign-in; transient errors keep state; operator progress/error/auth/source.
  - LIVE-VIDEO-005: hash+`expected_version` binding; edit invalidation; validate re-bind; validate rejection shows reason; unknown cost "unavailable".
- Baseline `frontend-video-contract.cjs`: **was 3/6 → now 5/6 PASS**. The 6th asserts `base_version`; canonical contract uses `expected_version` (owner instruction). **Explicit contract adaptation:** version field renamed `base_version`→`expected_version`; the `draft_hash` binding in that same probe now passes.
- Baseline `frontend-contract.cjs`: **8/10 PASS**; 2 FAIL are disabled-camera (C-class) tests outside VFUI ownership (camera stays disabled). The "unknown model cost stays unknown" probe now PASSES due to the cost fix.

## Limitations / honesty
- Simulated-DOM script contracts only — no browser rendering/codec claim.
- Source playback, `/task/validate`, and server-side hash/version enforcement depend on SEC's Python routes above; until integrated the frontend fails closed (no fabricated playback/approval).
- No camera UI; camera capture disabled. M2/M3 BLOCKED, Student OFF, geometric fallback `723a4a7` preserved. No pushes; no Python edits.
