# Offline backend fallback — executed

Application/container source: `749d27b33bcec03883d4a1b1ac481ee9a95fd91e`.
A one-shot copy of the actual running API image executed under Docker
`--network none`, default unprivileged UID10001, with read-only mounts of the
cached YOLO weights and the previously inspected privacy-safe photographic crop.
No published ports, credentials, host database or Student model were mounted.
The ordinary private deployment was not stopped or modified.

The owned Python QA runner started the actual Uvicorn API on the container's
loopback, uploaded a fresh 200-frame MP4, defined a polygon, explicitly approved
entry/dwell geometric rules and fetched real results. Result: **exit0**, **50
YOLO samples**, mean inference **49.291ms**, two events with evidence JPEG hashes,
one successful local action/notification each. Teacher disabled; no Student
activation. Docker removed the temporary container after completion.

`execution.json` contains the exact Docker argv/image ID/duration; the runner
is `offline_smoke.py`, actual API responses are `actual-result.json` and stdout
is `execution.txt`. The input crop/provenance is in
[the distinct-photo evidence](../new-photo-749d27b/VALIDATION.md).

This proves **backend inference and local actions without external networking**
using cached dependencies/weights. It does not prove an offline frontend browser
session or public hosting. The MP4 uses a photographic upper-bus crop with
synthetic motion, not natural footage. Timing under shared-host load is an
observation, not a baseline/optimized throughput or cost comparison.
