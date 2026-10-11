# Final isolated AutoLearn snapshot — checks passed, independent QA failed

Handoff SHA: `ff48ca9756e179e1bda1f9556e44d20c24776a8b`.
Implementation/test SHA: `8e9d95fe0c4d6939d793e086cf2820b80231a5a8`.
Base for the final correction: `5938b6d1f1396c1513d52ee9d9c3cdb377dc43a4`.
The implementation worktree was clean before and after both commands.

Executed from worktree C with OMP/MKL/OPENBLAS threads set to 2:

```sh
make check
make smoke
```

`make check`: exit 0 in 32.636 seconds; repository structure check,
**249 tests passed** (4 warnings), Next production build and TypeScript check.
`make smoke`: exit 0 in 5.452 seconds; genuine YOLO end-to-end inference,
event/evidence/local action. Actual command logs and exact SHA/exit/duration
receipts are adjacent; these are independently executed root checks.

One fresh independent Codex review ran on this exact tested commit from
2026-10-10 23:34:28 to 23:53:12 UTC, within its 1500-second limit.
**CHANGES_REQUIRED: six P1 and one P2**. It independently ran54 focused
AutoLearn tests and36 safety checks, plus original and new real TCP/CPU/UI
reproductions. [Final report](../../reviews/AUTOLEARN-TEN-HOUR-FINAL.md),
archived on review branch commit8c252af. This was conclusive, not a timeout.
Tests/build/smoke do not override QA. No further normal correction cycle is
authorized; C is BLOCKED and not integrated. M2 remains BLOCKED.

This code is not integrated into the delivery application, no Student is
activated and no public application is published. The real 24-image/6-held-out
Student experiment and paired measurements belong to the earlier `5938b6d`
snapshot; they are not measurements of this new snapshot. Re-evaluation on the
exact reviewed code is required before extending those claims. Natural-video
quality, foveated gains, paid inference cost and savings remain UNVERIFIED.
