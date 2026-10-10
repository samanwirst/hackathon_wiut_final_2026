# Separate demo deliverable

- Branch: `feature/demo-safe`; base `088b17aded860bd5d926600573184c883919d20e`.
- Exact tested implementation handoff: `99e8670216a8aa9161cfb2517a2e5b4b955edd0b`.
- Application code: `7f3b5ebe459eab07dca68ee27b31f655cb3189cb`.
- Local desktop demo verified: explicit geometric builder, canonical JSON,
  human approval, real YOLO events/evidence/local notifications, editing,
  disabling and reviewed re-enabling.
- Full check: 195 tests, production frontend build; real YOLO smoke; actual
  Chromium journey. Evidence: [validation](demo-evidence/99e8670/VALIDATION.md).
- Known P2: loaded-source phone layout overflows at 390px. Use desktop >=1024px.
- NL compilation and Teacher-backed automation disabled server-side by default.
- Real Teacher, Student/AutoLearn, foveation, held-out accuracy, GPU costs and
  savings UNVERIFIED. No public deployment, deck or recorded backup delivered.
- M1 remains accepted; M2 remains **BLOCKED**. M3/M4 not started. No milestone
  verdict is changed, no M2 recovery was launched and no acceptance gate passed.
- Original milestone state, report, handoff, protected algorithms and branch
  history remain intact. This file does not replace `.agents/STATE.md`.
