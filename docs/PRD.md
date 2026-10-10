# VisionFlow AI — Product & Technical Requirements

**Version:** 1.0  
**Project type:** Automotive Computer Vision / Visual AI Agents  
**Duration:** 24-hour hackathon  
**Team:** 3 students  
**Primary vertical:** Automotive service operations  
**Product inspiration:** OpenVector  
**Differentiator:** AutoLearn — automatic specialization for recurring visual tasks

## 1. Mission

Build a deployed, working visual AI automation platform that allows a user to connect a camera or upload a video, describe a visual condition in natural language, detect matching events, and execute an authorized workflow.

The platform must additionally demonstrate how a frequently repeated visual task can be transferred from a general-purpose Vision-Language Model (Teacher) to a smaller specialized model (Student), subject to validation and human approval.

The GVERA robot is an optional physical output device, not a dependency of the core product.

## 2. Hackathon alignment

The team understands the judging criteria as:

| Criterion | Weight |
|---|---:|
| Technology | 25% |
| Innovation | 25% |
| Impact | 25% |
| Presentation | 15% |
| Business | 10% |

Expected deliverables, subject to verification against the original Final Task:

- A working frontend and backend, accessible during judging.
- Real end-to-end execution rather than static mockups.
- Ability to accept new inputs provided by judges.
- Clear data provenance and licensing.
- Measured accuracy, latency, and approximate operating cost.
- Privacy and consent considerations.
- A credible three-month pilot proposal.
- A seven-minute pitch and live demonstration.

**Source-of-truth rule:** If the official Final Task contradicts any item above, the official document takes precedence. Record all discrepancies in `docs/TRACEABILITY.md`.

## 3. Product scope

### P0 — Required MVP

1. Accept an uploaded MP4 video.
2. Support at least one live camera source where hardware allows.
3. Detect and track supported objects.
4. Let the user define a polygonal region of interest.
5. Support visual events:
   - Object enters zone.
   - Object exits zone.
   - Object remains in zone longer than a threshold.
   - Object count exceeds a threshold.
6. Accept a natural-language instruction and compile it into a validated, editable workflow.
7. Require user confirmation before enabling the workflow.
8. Execute a real authorized action when an event occurs.
9. Save timestamp, camera ID, rule ID, event type, and evidence image.
10. Display events and actions in a functional web interface.
11. Run automated tests and support reproducible deployment.

### P1 — Main innovation: AutoLearn

1. Identify recurring visual classification tasks.
2. Collect representative, non-duplicate image examples.
3. Use a Teacher VLM to propose labels, or explicitly fall back to manual labeling.
4. Provide a UI for correcting labels.
5. Extract visual embeddings using a pretrained model.
6. Train a small Student classifier on those embeddings.
7. Evaluate Student on held-out video sessions.
8. Compare Teacher and Student by accuracy, latency, and estimated cost.
9. Run Student in shadow mode before activation.
10. Activate only after explicit approval and a passed quality gate.
11. Support fallback to Teacher and model rollback.

### P2 — Stretch goals

- RTSP support.
- More complex VLM-based visual conditions.
- Telegram notifications.
- GVERA integration via documented and approved API.
- ONNX export.
- Multi-camera dashboards.
- Advanced foveated vision or adaptive frame sampling.

## 4. Primary use case

A Toyota or BYD service center wants to know when a vehicle enters a service bay, how long it remains there, and when it exits.

The user connects a camera, draws the service bay polygon, and writes:

"When a car stays in Service Bay A for more than ten minutes, create an alert for the service advisor."

The system compiles this instruction into a rule, tracks vehicles, detects the dwell event, stores evidence, and creates an alert.

A second use case demonstrates AutoLearn:

"Determine whether a vehicle's hood is open."

Initially, a Teacher VLM helps classify selected images. The platform then collects verified examples, trains a specialized classifier, evaluates it, and demonstrates lower-cost repeated inference where quality permits.

## 5. User interface

### Page A — Dashboard

- Active camera and uploaded-video sources.
- Active workflows.
- Recent events.
- Processing status.
- Teacher/Student inference counters.
- Error and health indicators.

### Page B — Camera Workspace

- Video player or live feed.
- Bounding boxes and track IDs.
- Editable polygon zones.
- Playback controls for uploaded videos.
- Evidence snapshot viewer.

### Page C — Workflow Builder

- Natural-language instruction input.
- Generated structured workflow.
- Editable trigger parameters.
- Camera and zone selection.
- Action selection.
- Validation errors.
- Explicit enable/disable control.

### Page D — Event Timeline

- Timestamp.
- Event name and confidence.
- Source camera.
- Evidence image.
- Action status.
- Filtering by rule, source, and time.

### Page E — AutoLearn

- Recurring task candidates.
- Teacher-labeled dataset with review controls.
- Positive/negative example counts.
- Train Student button.
- Training job status.
- Held-out evaluation metrics.
- Shadow-mode comparison.
- Activation, fallback, and rollback controls.

### Page F — Settings / Integrations

- Authorized webhook destinations.
- Optional Telegram configuration.
- Optional GVERA integration.
- Data retention settings.
- Consent and privacy information.

## 6. Core architecture

Pipeline:

Camera/Video → Frame Sampling → Object Detection → Tracking → Zone Logic → Temporal Event Engine → Workflow Engine → Authorized Action → Evidence & Event History.

For visual tasks that cannot be resolved by object detection alone:

Camera/Video → Selected Frame/ROI → Teacher VLM or Approved Student → Temporal Event Engine.

The frontend must not contain authoritative business logic. All event decisions and actions are validated server-side.

## 7. Recommended technology stack

- Frontend: Next.js, TypeScript, Tailwind CSS.
- Backend: FastAPI, Python, Pydantic.
- Video: OpenCV and FFmpeg.
- Detection: a suitable pretrained detector with verified model and code licenses.
- Tracking: ByteTrack or a simpler tested tracker.
- Event logic: deterministic Python state machines.
- LLM: structured JSON generation with schema validation.
- VLM: image-capable model for selected visual classifications.
- Embeddings: DINOv2, SigLIP, or another suitable pretrained encoder.
- Student: Logistic Regression or small MLP.
- Storage: SQLite for MVP; PostgreSQL optional.
- Updates: WebSocket or Server-Sent Events.
- Deployment: Docker Compose or an equivalent reproducible setup.

The team must verify that selected pretrained weights support the required object classes. Do not assume a model detects an automotive-specific object without testing it.

## 8. Workflow DSL

A workflow has:

- `id`
- `name`
- `source_id`
- `enabled`
- `object_class`
- `trigger.type`
- `trigger.zone_id`
- `trigger.duration_seconds`, where applicable
- `trigger.threshold`, where applicable
- `action.type`
- `action.config`
- `cooldown_seconds`
- `requires_approval`

Supported trigger types:

- `object_entered_zone`
- `object_exited_zone`
- `dwell_in_zone`
- `object_count_exceeded`
- `visual_condition_verified`

Supported actions:

- `create_notification`
- `create_service_event`
- `send_webhook`
- `robot_preset`, only when explicitly configured and authorized

The LLM must produce only a structured workflow. It must never generate arbitrary code that is executed by the backend.

Unsupported requests must produce a clear validation error rather than a fabricated workflow.

## 9. Event correctness

The event engine must implement:

- Track-based object identity where available.
- Polygon inclusion using a consistent object anchor point.
- Debounce or temporal smoothing.
- Cooldown to prevent duplicate alerts.
- Tolerance for brief tracking loss.
- State reset when an object truly leaves.
- Event IDs suitable for idempotent action execution.
- Explicit unknown/error states when confidence is insufficient.

A single object remaining in a zone must not trigger the same one-shot event repeatedly unless the workflow explicitly allows repetition.

## 10. AutoLearn design

### 10.1 Eligibility

A task may be proposed for AutoLearn when:

- It is sufficiently repetitive.
- It can be expressed as a stable visual classification.
- There are enough diverse positive and negative examples.
- The expected future inference cost justifies training.
- A reliable evaluation set can be constructed.

The system must not assume that repeated prompts automatically provide valid training labels.

### 10.2 Dataset collection

- Sample from multiple time intervals or videos.
- Avoid near-identical consecutive frames.
- Store image references, timestamps, source, and label provenance.
- Distinguish Teacher-generated labels from human-verified labels.
- Collect both positive and negative examples.
- Obtain permission to use recorded footage.
- Prevent train/test leakage by splitting at the video/session level.

### 10.3 Student training

- Keep the pretrained embedding encoder frozen in MVP.
- Train a small classifier on extracted embeddings.
- Save model weights, preprocessing configuration, class names, and dataset version.
- Save training duration and environment information.
- Ensure inference uses the exact same preprocessing as training.

### 10.4 Evaluation and activation

Report:

- Precision.
- Recall.
- F1.
- Confusion matrix.
- p50/p95 inference latency.
- Estimated cost per 1,000 checks.
- Teacher/Student disagreement rate.

Activation must require a predefined quality gate and explicit user approval. The system must remain on Teacher or hybrid mode if Student fails.

Shadow mode must not execute production actions based solely on Student output.

Support rollback to the previous active version.

### 10.5 Anti-drift controls

- Do not automatically retrain on Student's own unverified predictions.
- Sample uncertain cases for review.
- Monitor disagreement and quality changes.
- Preserve a known-good model version.
- Record all model activations and rollbacks.

## 11. API contract

Required endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Service readiness |
| POST | `/api/sources/upload` | Upload video |
| GET | `/api/sources` | List sources |
| POST | `/api/zones` | Create or update zone |
| POST | `/api/workflows/compile` | Text → validated draft |
| POST | `/api/workflows` | Save workflow |
| POST | `/api/workflows/{id}/enable` | Enable after validation |
| GET | `/api/workflows` | List workflows |
| GET | `/api/events` | Event timeline |
| GET | `/api/events/{id}` | Event and evidence |
| POST | `/api/autolearn/jobs` | Create dataset/training job |
| GET | `/api/autolearn/jobs/{id}` | Job status |
| POST | `/api/autolearn/jobs/{id}/labels` | Review labels |
| POST | `/api/autolearn/jobs/{id}/train` | Train Student |
| POST | `/api/autolearn/jobs/{id}/evaluate` | Evaluate Student |
| POST | `/api/autolearn/jobs/{id}/activate` | Approved activation |
| GET | `/api/metrics` | Processing metrics |

All API payloads must have Pydantic models. The frontend and backend must agree on shared field names and status values.

For the hackathon, asynchronous processing may be implemented with a simple background worker rather than a distributed queue.

## 12. Database entities

Minimum entities:

**VideoSource:** id, type, name, URI/path, status, created_at.

**Zone:** id, source_id, name, normalized polygon coordinates.

**Workflow:** id, source_id, name, compiled DSL, enabled, created_at.

**TrackEvent:** id, source_id, workflow_id, track_id, type, timestamp, confidence, evidence_path, action_status.

**ActionExecution:** id, event_id, action_type, status, attempt_count, error, executed_at.

**AutoLearnTask:** id, source_id, visual_prompt, status, teacher_model, student_model_version.

**TrainingSample:** id, task_id, image_path, label, label_source, verified, session_id.

**ModelVersion:** id, task_id, artifact_path, metrics, status, created_at.

## 13. Security and privacy

- Store secrets only in environment variables.
- Commit `.env.example`, never `.env`.
- Validate upload types and enforce file-size limits.
- Restrict file and evidence access.
- Validate webhook destinations; do not permit arbitrary internal-network requests.
- Require authorization for workflow actions and model activation.
- Provide visible notice and consent for recorded people.
- Minimize retention and support deletion.
- Do not claim that video is processed locally if frames are sent to a cloud VLM.
- Keep logs free of API keys and unnecessary personal data.

## 14. GVERA integration

The robot is optional.

If a documented and authorized control interface exists, implement a narrow adapter exposing only approved preset actions.

Requirements:

- Explicit enable switch.
- Allowlisted commands.
- No direct LLM-to-actuator commands.
- Safe workspace and human supervision.
- Emergency stop procedure.
- No dependency on the robot for the core demo.

If hardware or API access is unavailable, mark the integration as unavailable rather than simulating a successful robot command.

## 15. Quality and performance evaluation

Prepare held-out test videos not used to tune thresholds.

Measure:

- Event-level precision, recall, and F1.
- False events per hour.
- End-to-end event-to-action latency.
- p50/p95 frame-processing latency.
- Effective processing throughput.
- Teacher requests and token usage.
- Student inference time.
- Estimated processing cost per 1,000 checks.
- AutoLearn training time.
- Performance on changed lighting, occlusion, and tracking loss.

Do not invent performance numbers.

Where the sample size is small, state that results are preliminary.

## 16. Acceptance criteria

### Core MVP is accepted when:

1. A judge can upload a previously unseen supported video.
2. The backend genuinely processes the video.
3. The user can define a zone and enable a supported workflow.
4. At least one correct event is generated.
5. A real authorized action occurs.
6. The event is visible with timestamp and evidence.
7. The system can be restarted using documented instructions.
8. Automated tests run successfully.
9. Failures are visible and not silently disguised.

### AutoLearn is accepted when:

1. Real labeled examples exist.
2. A Student model is genuinely fitted and saved.
3. Held-out evaluation runs.
4. Metrics are displayed.
5. Shadow mode compares Teacher and Student.
6. Activation is gated.
7. Rollback works.

A decorative progress bar or hardcoded Student predictions do not count as AutoLearn.

## 17. Scope and fallback policy

If time is limited:

1. Protect the working video → event → action pipeline.
2. Protect support for new input videos.
3. Protect deployment and reproducibility.
4. Reduce the number of event types if necessary.
5. Use manual labeling as an explicitly disclosed fallback for AutoLearn.
6. Defer RTSP, Telegram, GVERA, and advanced foveated vision.
7. Never replace real functionality with an undisclosed mock.

## 18. Business and pilot

Target customer: service center operator or dealership operations manager.

Proposed value:

- Reduce manual monitoring.
- Improve event documentation.
- Provide auditable process timelines.
- Lower recurring AI inference cost through AutoLearn.

Three-month pilot:

**Month 1:** Deploy on one consented service bay, collect baseline data, define target events and evaluate reliability.

**Month 2:** Expand to several workflows, compare automated events against manual records, and measure false positives and operating cost.

**Month 3:** Run AutoLearn on a repeated visual task, evaluate Student against Teacher, measure operational impact, and decide whether expansion is justified.

Pricing is a hypothesis, not a verified market fact. Validate willingness to pay during pilot interviews.

## 19. Pitch requirements

Seven-minute pitch:

- 0:00–0:45 — Problem.
- 0:45–1:30 — Product and target customer.
- 1:30–3:30 — Live end-to-end demo.
- 3:30–4:30 — AutoLearn and technical differentiation.
- 4:30–5:15 — Real evaluation results.
- 5:15–6:00 — Business model and three-month pilot.
- 6:00–7:00 — Impact, limitations, and conclusion.

The live demo must remain functional without GVERA.

## 20. Definition of Done

A feature is complete only when:

- Code is committed.
- Tests relevant to the feature pass.
- API/UI integration works.
- Errors are handled.
- No secret is committed.
- Documentation reflects reality.
- The feature has been demonstrated on a real input.
- Any limitations are explicitly recorded.

A successful build without a working end-to-end demo is not sufficient.