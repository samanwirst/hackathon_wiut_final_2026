# Supplemental M2 recovery QA

Reviewed application snapshot: `0250feb7de89a6bc6df06a3d293dbc3b1cd93595`.
Base: `2127d207a7bf2e1401d40e5ad82d926eb0f66a57`.

These desired-behavior tests were run on a separate clean worktree at exactly
that snapshot, before adding evidence/report commits. They failed:
**2 failed, 3 warnings in 0.68 seconds**. They are supplementary controller QA,
not another implementation or independent review call. No production code changed.
The standalone test and runner are safe to commit; original raw logs and hashes
are retained in ignored runtime storage.

## Reproductions

- M2-001: entry `for 10 minutes` is accepted as immediate entry; its duration
  disappears. `log it` also becomes a notification. Expected: explicitly
  supported complete semantics, otherwise reject with no draft.
- M2-007: pause `_post_with_deadline` at entry, after the approval/budget grant
  but before the worker or HTTP POST starts. Disable via the API returns 200
  with `enabled=false` while there are zero requests. Release the pause: one
  HTTP POST starts after the acknowledgment and returns a positive result.
  Local dispatch remains cancelled, with zero notifications. The original
  read/grant race is repaired; the grant/send gap remains.

The fresh independent review returned CHANGES_REQUIRED for M2-001 and M2-003,
and judged M2-007 fixed at the earlier read/grant boundary. This supplementary
test checks the distinct actual-send boundary required by the human instruction:
once disable returns, no new Teacher request may start. A granted budget unit
with no worker/request yet started does not demonstrate that guarantee.

## Run on the frozen source

Use the installed project environment and an isolated detached worktree.
From the repository root (replace the worktree path if needed):

```sh
git worktree add --detach /tmp/visionflow-m2-0250-qa 0250feb7de89a6bc6df06a3d293dbc3b1cd93595
PYTHONPATH=/tmp/visionflow-m2-0250-qa/services/api:/tmp/visionflow-m2-0250-qa/packages/vision services/api/.venv/bin/python .agents/review-evidence/M2-0250feb/run_pytest.py --heartbeat .agents/review-evidence/M2-0250feb/test_gate_probes.py -q -s
```

The temporary 10 ms asyncio heartbeat affects only the test runner. Provider
responses are controlled fixtures; no real Teacher inference, GPU measurement,
foveated improvement, accuracy, or cost savings is verified by these tests.

## Smallest safe hackathon scope

Use manually reviewed JSON geometric workflows, uploaded-video detection/tracking,
temporal events, evidence and local notifications. Keep the disclosed unavailable
Teacher fallback. Disable or avoid NL compilation and Teacher-backed automation
until the complete grammar and transport gates are satisfied. This is a proposed
scope reduction, not another fix cycle or an M2 PASS. M1 remains accepted.
