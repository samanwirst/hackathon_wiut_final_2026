# Handoff — M1 review fix cycle 1 ready for re-review

- **Milestone:** M1 — vision-to-action pipeline (fix cycle 1)
- **Implementation HEAD:** `dbe61a24bc5d3cf44577c033be118359bf834482`
- **Base SHA:** `b131c50cce4937ac41137922d3246f2124241271`
- **Previous review base:** `a622572` (review/M1 — five P1 findings)
- **Branch:** `feature/visionflow`

## Findings addressed (all five P1 → FIXED)

| ID | Resolution | Reason |
| --- | --- | --- |
| M1-001 | FIXED | Webhook authorization canonicalizes the URL, rejects embedded userinfo, compares scheme/hostname/effective-port exactly, enforces the permitted path prefix, and blocks hosts that resolve to loopback/private/link-local/reserved addresses. An injectable `webhook_transport` lets tests observe that a userinfo-disguised URL never reaches delivery. |
| M1-002 | FIXED | The engine keeps a deterministic `_count_episode` counter that advances on every rising threshold crossing; aggregate events pass it to `_emit`, so each crossing yields a distinct dedupe key (`...:visitN`) and persistence no longer discards later crossings. |
| M1-003 | FIXED | The worker advances each engine once per frame, then re-reads the workflow's authoritative `enabled` state via a fresh short-lived session before persisting events or executing actions; a disable committed mid-run revokes further output immediately. |
| M1-004 | FIXED | A module-level `_session_lock` serializes the entire processing session (detector reset + every frame call), so a second source cannot reset or contaminate an active source's tracker state. Low peak RAM, matching the CPU-only target. |
| M1-005 | FIXED | Startup (`pipeline.recover_interrupted_sources`, called from app startup) marks any stale `processing` row failed with an explanatory error; the process endpoint then permits a retry. |

## Changed files

- `packages/vision/visionflow_vision/events.py` — aggregate episode counter + dedupe key.
- `services/api/app/actions.py` — SSRF-safe webhook authorization + injectable transport.
- `services/api/app/pipeline.py` — session serialization, per-frame enabled recheck, interrupted-source recovery.
- `services/api/app/main.py` — call recovery at startup.
- `tests/unit/test_webhook_auth.py` (new), `tests/unit/test_events.py` (count re-arm case), `tests/integration/test_m1_fixes.py` (new: disable/serialize/recover).
- `docs/TRACEABILITY.md`, `.agents/STATE.md` — fix records, test count.

## Commands executed and actual results (2026-10-10)

- `services/api/.venv/bin/python -m pytest tests/unit tests/integration -q` → **44 passed**.
- `services/api/.venv/bin/python -m pytest tests/ -q` → **60 passed** (~6.2 s; includes 16 controller tests, unchanged).
- `services/api/.venv/bin/python scripts/smoke_e2e.py` → **SMOKE PASS**: real YOLO detected bus (conf 0.76), `object_entered_zone` at t=4.2 s, 30 frames, avg inference 59.0 ms, evidence JPEG + notification persisted.

## Known limitations

- Session serialization makes concurrent sources fully sequential by design (M1 target, limited RAM); a job queue / per-source workers with leases is future (M2+) work.
- The `enabled` recheck issues one small fresh-session query per workflow per sampled frame; negligible at the M1 frame budget but not optimized for many workflows.
- Internal-resolution guard calls `socket.getaddrinfo`; tests avoid DNS by using IP-literal allowlists and the userinfo rejection path (no network).
- Carried from M1: no live camera source, no NL→DSL compile, no API auth, no deployment (M2–M4 scope).

## Questions for Codex

1. M1-003: dropping output while still advancing engine state (so semantics stay consistent if re-enabled) — is that the desired revocation semantics, or should the engine be frozen/torn down on disable?
2. M1-004: full-session serialization vs per-source detector instances — acceptable for M1 given RAM constraints, or prefer isolated instances now?
3. M1-001: internal-resolution guard trusts explicit IP-literal allowlist entries (so a demo `http://127.0.0.1:PORT` webhook works). Confirm that exception is acceptable.
