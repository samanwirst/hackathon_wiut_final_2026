# Local Teacher recovery — same pinned model; cause unknown

The old Teacher PID **677309** disappeared after the preserved natural-image
request. Port 18081 was free and GPU usage fell to 15 MiB. Its scoring server
log ended at successful startup, with no shutdown, error or exit reason. The
original exec session was no longer available; the kernel journal had no
accessible matching entries and reading `dmesg` was denied. **Exit cause is
UNKNOWN**: these observations cannot distinguish OOM from session cleanup or
another termination. No exact cause is asserted.

The same unchanged harness/model was restored at **2026-10-11 03:38:42 UTC**
as the detached owned user service
`visionflow-local-teacher-emergency-20261011.service`, new PID **989679**.
At **03:38:53 UTC**, `GET http://127.0.0.1:18081/v1/models` confirmed the same
SmolVLM-500M model, revision `a7da5b986cb59b408707209984f360a5f4ad7e47`,
`occupied`/`empty` candidate scoring, one worker and no active request. The
unchanged harness SHA256 is
`930be3d3b307993ed6bb712622ae75c6ed2b2e2477e95460642137b43f340d95`.

The service binds only loopback, uses the already installed isolated B CUDA
environment/pinned weights, and runs with Hub/Transformers offline mode.
No package, credential, model or production application change occurred.
The user service survives the tool shell's lifetime. Its restart policy is
on-failure after 10 seconds, limited to two starts in 300 seconds; repeated
failure becomes visible rather than an unbounded reload loop. Its unit,
logs and process are explicitly owned; no unrelated process was stopped.

GPU model load took **4.765589 seconds**, with 1,014,973,440 allocated and
1,061,158,912 reserved bytes. `nvidia-smi` observed **1102 / 4096 MiB** after
startup. Before recovery the host had about **1230 MiB available RAM**, 5267
MiB free swap, and other processes were already using most system memory.
The harness retains two CPU threads, direct CUDA BF16 loading, 512px image
processing and genuinely bounded one-worker admission. These constraints do
not guarantee that a future host-wide OOM or GPU failure is impossible.

**No POST was made during recovery.** The natural-image request
`local-b90eeca3ce964b968ffdaf2f93548efa`, its false-positive result and all
original input/response/log evidence were not repeated or altered. The current
service is GET-ready; actual inference after recovery remains **UNVERIFIED**
until a future authorized live-phone request is made. It still cannot provide
validated quality or calibrated confidence, and Teacher actions remain disabled.

Runtime paths are under
`.agents/runtime/ten-hour/TEACHER_EMERGENCY/recovery/`: `server.log`,
`evidence/model.json`, future `evidence/requests.jsonl`, `start-receipt.json`,
`models-after.json` and `readiness.json`. The old log/model receipt remains in
the original B runtime; it must not be mistaken for the new process's log.

Inspect or stop **only** the owned unit:

```bash
systemctl --user show visionflow-local-teacher-emergency-20261011.service \
  --property=MainPID --property=ActiveState --property=SubState \
  --property=NRestarts --property=Result --property=ExecMainStatus
systemctl --user stop visionflow-local-teacher-emergency-20261011.service
```

Restart, if root requests it and the port is still owned by this unit:

```bash
systemctl --user restart visionflow-local-teacher-emergency-20261011.service
```

After any restart, record its new PID and inspect GET readiness before use;
never reuse an old process receipt as current proof. Safe startup, GET identity,
memory constraints and cause evidence are retained in
[teacher-recovery-20261011](../../../.agents/teacher-evidence/teacher-recovery-20261011/readiness.json).
No spending, public exposure, Student training or Student activation occurred.
