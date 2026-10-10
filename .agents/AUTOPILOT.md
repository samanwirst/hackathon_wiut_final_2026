# VisionFlow autonomous controller

The operator's 2026-10-10 goal explicitly authorizes a main controller to
advance M1–M4, Claude to implement, and independent Codex to review exact
commits. This overrides manual milestone waiting for this execution only.
Ordinary manual reviews continue to follow AGENTS.md. No agent may spawn
another agent; only `scripts/orchestrate.py` schedules sequential CLI calls.

```sh
make autopilot
python3 scripts/orchestrate.py --from M1 --to M4
python3 scripts/orchestrate.py --resume
python3 scripts/orchestrate.py --dry-run
python3 scripts/orchestrate.py --detach
python3 scripts/orchestrate.py --stop
```

Prerequisites: clean `feature/visionflow`, authenticated `claude` and `codex`,
Python API venv, installed frontend dependencies, and authenticated origin
for pushes. No interactive authentication retry loop. `--no-push` is useful
for offline validation. The controller never merges main or rewrites history.

State machine: IMPLEMENT → TEST → REVIEW → REPORT → DECIDE → FIX → RETEST →
REVIEW → ACCEPT → PUSH → next milestone. An existing valid M1 handoff starts
at TEST. `make check` runs structure, all tests, frontend build; `make smoke`
runs real detector inference. Independent review branches start at the exact
tested SHA; the controller validates JSON and matching Markdown VERDICT and
TARGET_SHA, commits/pushes reports, and retains accepted reports on feature.
P2/P3 alone do not cause further agent calls. P0/P1 block acceptance.

Durable JSON, process IDs, prompts, stdout/stderr and usage metadata live in
ignored `.agents/runtime/`. Do not commit or share these logs without checking
for private content. Reports contain only safe test evidence. Runtime state
is not reset automatically; `--resume` reconciles committed handoffs and
report transactions and skips completed milestones. Unexpected dirty trees
or changed SHAs stop execution, preserving changes for inspection.

Defaults: 30 minutes implementation, 20 minutes review, 15 minutes test gate,
six hours total, 20 agent calls, two fix cycles (three reviews) per milestone,
and one retry for transient CLI failures only when HEAD/tree is unchanged.
Each limit is configurable via `--help`; fix cycles cannot exceed two.
Authentication, quota, dependency, deterministic test and compute failures
are recorded, never blindly retried. Failed tests enter bounded FIX; an
authentication/compute blocker requires operator recovery. Optional
`--claude-budget` adds the installed CLI's per-call budget cap without
enabling any paid service. Usage and cost fields are logged when exposed.
This Claude CLI does not expose a max-turns option; call/time limits apply.

SIGINT/SIGTERM kills the active subprocess group and records an interrupted
phase. `--stop` checks process identity before signaling the controller.
`--detach` survives terminal closure with a local log and explicit stop
command. tmux was not installed at initial inspection, so no tmux dependency
is required. No automatically restarting background service is installed.

Claude uses `dontAsk` plus a project command/tool allowlist, without permission
bypass. Codex uses an isolated workspace-write worktree, approval `never`,
network restricted for shell commands, a structured response schema, and
no recursive agents. The CLI transport uses saved account authentication.
Installed venv/node_modules are shared; reviewed Python source paths are
explicitly set to the isolated worktree. See [official Codex noninteractive
documentation](https://developers.openai.com/codex/noninteractive).

The official brief requires public access during judging; the operator's
goal separately requires explicit public deployment approval. M4 prepares
deployment and records this delivery limitation; it must never fabricate a
public URL or claim judging readiness before deployment is verified.
