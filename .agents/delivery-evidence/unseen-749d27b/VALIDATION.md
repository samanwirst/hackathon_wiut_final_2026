# Fresh supported-input container smoke

Actual application container source: `749d27b` (accepted fallback application;
later delivery commits changed documentation/evidence only). This is a real
inference/action check, not M2 or M3 acceptance.

A newly generated 1280x720, 20fps, 200-frame MP4 moved a bus-only photo crop from
right to left, held it in a left-side polygon, then moved it out. Resolution,
direction, size and timing differ from the prior demonstration. Parameters were
chosen before inference. Exact source/crop/video hashes are in the manifest.
It reuses the same upstream photograph and synthetic motion: **not unseen
natural footage, independent visual content, or natural-video accuracy**.

The actual private unprivileged container processed 50 samples, with reported
mean inference time 63.307 ms. Entry and two-second dwell rules each emitted a
real event with a JPEG evidence hash, exactly one successful local action and
exactly one persisted notification. Teacher was disabled; Student was never
activated. Rules were approved only as disclosed QA workflow fixtures.

Executed command from the root working checkout:
`services/api/.venv/bin/python .agents/runtime/ten-hour/delivery/container/unseen_clip_smoke.py`.
The runner source and actual JSON results are archived here; the original MP4
is ignored. The first harness call used an unsupported trigger spelling and
received HTTP422; it was corrected to the accepted `dwell_in_zone` contract
before the successful full run. This was a fixture error, not a product finding.
No source changes, fake predictions or inferred savings were used.
