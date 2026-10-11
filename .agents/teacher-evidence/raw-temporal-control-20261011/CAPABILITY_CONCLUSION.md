# Capability conclusion — actual inference, failed temporal control

**Two genuine raw-generation inferences executed. Semantic temporal alerts are not qualified.**

Model: HuggingFaceTB/SmolVLM-500M-Instruct, pinned revision a7da5b986cb59b408707209984f360a5f4ad7e47, executing locally on RTX3050 Laptop GPU in BF16. The unchanged harness was started privately in raw-generation mode for this probe. No model download or source change occurred.

- One-image caption succeeded technically and described the visible cliff/trees: client1.491519962s; server1.471950849s;11generatedtokens.
- Two identical images yielded actual text: `MATCH\n\nThe two images are identical.` Requested structured JSON was absent. The requested physical-change semantics were contradicted. Client0.289195260s; server0.270117365s;11generatedtokens.
- Both inputs in the comparison were the same unmodified public-domain NPS photograph; SHA2560969a507c3def0e0c73d3cef020df494b1884da6a4b95070049dc325e38e7279. This is a no-change static-image control, not two different live captures.

A strict runtime must reject the malformed/contradictory output and return UNCERTAIN/nonactioning. This probe establishes technical multi-image ingestion and genuine generated text. It does not establish native video understanding, reliable generic state changes, bottle opening, calibrated confidence, temporal accuracy, or savings. Those remain UNVERIFIED. No canned response or model-repaired result was substituted.

Owned secondary PID1070611/loopback18082 was stopped after12.184003051s. Original TeacherPID989679/loopback18081 remained alive and its model endpoint responded after cleanup. No Student activation, public deployment, spending, or app source change occurred.

See EVIDENCE_SUMMARY.md, VERIFICATION.json, exact raw responses, requests.jsonl, model metadata, request manifests, explicit argv/environment, runner and CLEANUP.json in this directory. Wire image bodies stay ignored.
