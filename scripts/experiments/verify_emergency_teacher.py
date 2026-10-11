#!/usr/bin/env python3
"""One fresh-image QA request to the unchanged private Teacher; no training.

No environment/credential reads, retries, generation repair, server changes,
network image fetching or paid resources. Full wire body stays in ignored
runtime evidence. Committed input/manifest can reconstruct its exact bytes.
"""
import argparse
import base64
import datetime
import hashlib
import json
import math
from pathlib import Path
import subprocess
import time
import urllib.request

BASE_URL = "http://127.0.0.1:18081/v1"
MODEL = "HuggingFaceTB/SmolVLM-500M-Instruct"
REVISION = "a7da5b986cb59b408707209984f360a5f4ad7e47"
PROMPT = (
    "Classify visible motor-vehicle presence in the supplied image. "
    "For this test, label occupied means at least one visible motor vehicle "
    "(car, truck, bus, or motorcycle), and label empty means no visible motor vehicle. "
    "Choose only occupied or empty. Do not infer an invisible vehicle."
)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(directory, name, data):
    (directory / name).write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--provenance", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--server-evidence", type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    marker = args.evidence / "POST-attempt.json"
    if marker.exists():
        raise SystemExit("This evidence directory already attempted its one POST; no implicit retry")
    raw_image = args.image.read_bytes()
    provenance = json.loads(args.provenance.read_text())
    if provenance.get("sha256") != sha(raw_image) or provenance.get("visually_inspected") is not True:
        raise SystemExit("Exact input SHA and completed visual/privacy inspection required")
    if len(raw_image) > 650_000 or provenance.get("synthetic") is not False:
        raise SystemExit("Input must be a bounded genuine natural photograph")
    with urllib.request.urlopen(BASE_URL + "/models", timeout=10) as response:
        models = json.load(response)
    identity = models["data"][0]
    mode = models["experimental"]
    if identity.get("id") != MODEL or identity.get("revision") != REVISION:
        raise SystemExit("Pinned server model changed; no POST made")
    if mode.get("active_request") or mode.get("scoring_labels") != ["occupied", "empty"]:
        raise SystemExit("Server occupied or label contract changed; no POST made")
    write(args.evidence, "models-before.json", models)
    model_metadata = json.loads((args.server_evidence / "model.json").read_text())
    write(args.evidence, "unchanged-server-model.json", model_metadata)
    gpu = subprocess.check_output([
        "nvidia-smi", "--query-gpu=name,memory.total,driver_version",
        "--format=csv,noheader,nounits",
    ], text=True).strip()
    write(args.evidence, "gpu-identity.json", {"observed": gpu, "command":
          "nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader,nounits"})
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {
                "url": "data:image/jpeg;base64," + base64.b64encode(raw_image).decode("ascii")
            }},
        ]}],
        "max_tokens": 64,
        "stream": False,
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    # Durable marker BEFORE the only real POST; never retry a possibly admitted call.
    attempted = datetime.datetime.now(datetime.timezone.utc).isoformat()
    write(args.evidence, "POST-attempt.json", {"attempted_utc": attempted,
          "image_sha256": sha(raw_image), "request_body_sha256": sha(body),
          "request_body_bytes": len(body), "POST_count": 1, "automatic_retries": 0})
    (args.evidence / "request-wire.json").write_bytes(body)
    manifest = {"method": "POST", "url": BASE_URL + "/chat/completions",
                "headers": {"Content-Type": "application/json"}, "model": MODEL,
                "revision": REVISION, "prompt": PROMPT, "max_tokens": 64,
                "stream": False, "image_sha256": sha(raw_image),
                "image_bytes": len(raw_image), "image_content_type": "image/jpeg",
                "image_encoding": "data:image/jpeg;base64, plus base64 of exact original file",
                "message_order": "one user message: text, then inline image_url",
                "serialization": "json.dumps(ensure_ascii=False,separators=(',',':')).encode('utf-8')",
                "request_body_sha256": sha(body), "request_body_bytes": len(body),
                "credentials_used": False, "automatic_retries": 0}
    write(args.evidence, "request-manifest.json", manifest)
    request = urllib.request.Request(manifest["url"], data=body,
                                     headers=manifest["headers"], method="POST")
    started = time.perf_counter()
    with urllib.request.urlopen(request, timeout=75) as response:
        response_bytes = response.read(1_000_001)
        status = response.status
    wall = time.perf_counter() - started
    if len(response_bytes) > 1_000_000:
        raise RuntimeError("Response exceeds evidence bound")
    (args.evidence / "response-wire.json").write_bytes(response_bytes)
    result = json.loads(response_bytes)
    write(args.evidence, "response.json", result)
    label = json.loads(result["choices"][0]["message"]["content"])
    confidence = label.get("confidence")
    valid = (label.get("label") in {"occupied", "empty"}
             and type(confidence) in {float, int} and math.isfinite(confidence)
             and 0 <= confidence <= 1)
    metrics = result["experimental_metrics"]
    scores = metrics["scoring"]["candidate_log_likelihoods"]
    shift = max(scores)
    reconstructed = [math.exp(value - shift) for value in scores]
    denominator = sum(reconstructed)
    reconstructed = [value / denominator for value in reconstructed]
    assert all(abs(a - b) < 1e-12 for a, b in zip(
        reconstructed, metrics["scoring"]["normalized_probabilities"], strict=True))
    log_matches = [json.loads(line) for line in
                   (args.server_evidence / "requests.jsonl").read_text().splitlines()
                   if json.loads(line).get("request_id") == metrics["request_id"]]
    assert len(log_matches) == 1 and log_matches[0] == metrics
    write(args.evidence, "server-request-log.json", log_matches[0])
    summary = {"HTTP_status": status, "HTTP_wall_seconds": wall,
               "POST_count": 1, "model_forward_calls": metrics["scoring"]["model_forward_calls"],
               "request_id": metrics["request_id"], "schema_valid": valid,
               "actual_reply": label, "server_log_exactly_matches_reply_metrics": True,
               "response_wire_sha256": sha(response_bytes),
               "reconstructed_candidate_probabilities": reconstructed,
               "output_is_model_generated_JSON": metrics["scoring"]["output_is_generated_json"],
               "confidence_is_uncalibrated_candidate_probability": True,
               "human_verified_ground_truth": False, "quality_benchmark": "UNVERIFIED",
               "GPU_kernel_time": "UNVERIFIED", "savings": "UNVERIFIED",
               "Student_training_or_activation": False, "server_changed": False}
    write(args.evidence, "measurement.json", summary)
    print(json.dumps(summary, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
