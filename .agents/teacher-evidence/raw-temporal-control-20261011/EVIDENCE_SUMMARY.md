# Actual raw-generation and multi-image capability probe

- Executed: 2026-10-11 04:46:11–04:46:24 UTC. Two actual loopback HTTP POSTs, two genuine image-conditioned generation runs, no retries.
- Model: `HuggingFaceTB/SmolVLM-500M-Instruct`, revision `a7da5b986cb59b408707209984f360a5f4ad7e47`; RTX 3050 Laptop GPU, BF16, Torch 2.7.1+cu118.
- Unchanged standalone harness SHA256: `930be3d3b307993ed6bb712622ae75c6ed2b2e2477e95460642137b43f340d95`. Existing cached model only; network fetch disabled. One real worker; max two images and 96 generated tokens.
- Input: the original public-domain NPS El Capitan photograph, 118385 bytes, SHA256 `0969a507c3def0e0c73d3cef020df494b1884da6a4b95070049dc325e38e7279`. This probe used the exact same photograph twice for the comparison control. No real temporal camera sequence or physical bottle action was available. Source license/provenance is in the parent `input-provenance.json`.

## Actual outputs

1. Single-image caption: “A large cliff face with trees at the bottom.” HTTP200; client elapsed 1.491519962s, model inference 1.471950849s, 96 input tokens and 11 generated tokens.
2. Identical-image no-change comparison: “MATCH\n\nThe two images are identical.” HTTP200; client elapsed 0.289195260s, model inference 0.270117365s, 258 input tokens and 11 generated tokens.

The second request explicitly required JSON with MATCH/NO_MATCH/UNCERTAIN, supporting frame identifiers and visible evidence; it instructed that identical images mean NO_MATCH. The actual response fails JSON validation and contradicts the required transition semantics. A correct runtime must reject it and abstain.

## Verdict and limits

Genuine raw generation and two-image ingestion are **EXECUTED**. Reliable semantic transition recognition is **NOT QUALIFIED** by this probe; its sole no-change control **FAILED**. This small experiment does not prove generic temporal reasoning is impossible, nor establish a general accuracy estimate. Native video, positive temporal recognition, bottle opening, live-camera evidence, calibrated confidence, GPU billed time, and monetary savings remain **UNVERIFIED**.

The secondary server listened only on 127.0.0.1:18082, PID1070611, and was stopped after the probe. The original Teacher PID989679 on port18081 remained alive and its model endpoint responded after cleanup. No application code, model weights, Student activation, rental, credential, or public deployment was changed.

`probe_runner.py` preserves the complete executed request construction, explicit credential-free environment, limits and cleanup. Exact request wire bodies remain ignored runtime evidence because they contain base64 image bytes. Safe metadata, actual responses, server request records, source hashes and verification are separate files.
