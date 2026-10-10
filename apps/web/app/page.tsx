"use client";

import { useCallback, useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Source = {
  id: number;
  name: string;
  status: string;
  error: string | null;
  width: number | null;
  height: number | null;
  frames_processed: number;
  avg_inference_ms: number | null;
};

type Zone = { id: number; source_id: number; name: string; polygon: [number, number][] };

type VisualPredicate = {
  prompt: string;
  labels: string[];
  expected_label: string;
  description?: string;
  sample_interval_seconds?: number | null;
  cooldown_seconds?: number | null;
  budget?: number | null;
};

type Workflow = {
  id: number;
  source_id: number;
  name: string;
  enabled: boolean;
  dsl: {
    object_class: string;
    trigger: { type: string; zone_id: number; duration_seconds?: number; threshold?: number };
    visual_predicate?: VisualPredicate | null;
  };
};

type Event = {
  id: number;
  type: string;
  class_name: string | null;
  track_id: number | null;
  video_timestamp: number;
  confidence: number;
  detail: string;
  evidence_url: string | null;
  action_status: string;
  visual_status: string | null;
  visual_label: string | null;
  visual_confidence: number | null;
  created_at: string;
};

type Notification = { id: number; event_id: number; title: string; message: string; created_at: string };

type CompileResponse = {
  ok: boolean;
  draft: {
    name: string;
    object_class: string;
    trigger: { type: string; zone_id: number; duration_seconds?: number; threshold?: number };
    visual_predicate?: VisualPredicate | null;
  } | null;
  errors: string[];
  warnings: string[];
  explanation: string;
};

type VlmStats = {
  live: {
    calls: number;
    cache_hits: number;
    cache_misses: number;
    suppressed_budget: number;
    suppressed_cooldown: number;
    suppressed_sampling: number;
    failed: number;
    confirmed: number;
    unknown: number;
    teacher_provider: string;
    teacher_available: boolean;
  };
  total_decisions: number;
};

const TRIGGER_TYPES = [
  { value: "object_entered_zone", label: "Object enters zone" },
  { value: "object_exited_zone", label: "Object exits zone" },
  { value: "dwell_in_zone", label: "Object stays in zone (dwell)" },
  { value: "object_count_exceeded", label: "Object count exceeds threshold" },
];

const CLASSES = ["car", "truck", "bus", "motorcycle", "bicycle", "person"];

export default function Home() {
  const [sources, setSources] = useState<Source[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [vlmStats, setVlmStats] = useState<VlmStats | null>(null);
  const [selectedSource, setSelectedSource] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  // NL compile state
  const [nlText, setNlText] = useState("When a car enters Service Bay A, create an alert");
  const [compileResult, setCompileResult] = useState<CompileResponse | null>(null);
  const [visualPredicate, setVisualPredicate] = useState<VisualPredicate | null>(null);

  // zone drawing state
  const [drawing, setDrawing] = useState(false);
  const [points, setPoints] = useState<[number, number][]>([]);
  const [zoneName, setZoneName] = useState("Service Bay A");
  const imgRef = useRef<HTMLImageElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // workflow form state
  const [wfName, setWfName] = useState("Car entered bay");
  const [wfClass, setWfClass] = useState("car");
  const [wfTrigger, setWfTrigger] = useState("object_entered_zone");
  const [wfZone, setWfZone] = useState<number | null>(null);
  const [wfDuration, setWfDuration] = useState(10);
  const [wfThreshold, setWfThreshold] = useState(2);

  const apiError = async (r: Response) => {
    let detail = `${r.status}`;
    try {
      const body = await r.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    setError(detail);
  };

  const refresh = useCallback(async () => {
    try {
      const [s, e, n, v] = await Promise.all([
        fetch(`${API}/api/sources`).then((r) => r.json()),
        fetch(`${API}/api/events?limit=50`).then((r) => r.json()),
        fetch(`${API}/api/notifications?limit=20`).then((r) => r.json()),
        fetch(`${API}/api/vlm/stats`).then((r) => r.json()),
      ]);
      setSources(s);
      setEvents(e);
      setNotifications(n);
      setVlmStats(v);
      if (selectedSource) {
        const [z, w] = await Promise.all([
          fetch(`${API}/api/zones?source_id=${selectedSource}`).then((r) => r.json()),
          fetch(`${API}/api/workflows?source_id=${selectedSource}`).then((r) => r.json()),
        ]);
        setZones(z);
        setWorkflows(w);
      }
    } catch {
      setError(`API unreachable at ${API}`);
    }
  }, [selectedSource]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 2500);
    return () => clearInterval(t);
  }, [refresh]);

  const upload = async (file: File) => {
    setUploading(true);
    setError(null);
    const form = new FormData();
    form.append("file", file);
    const r = await fetch(`${API}/api/sources/upload`, { method: "POST", body: form });
    setUploading(false);
    if (!r.ok) return apiError(r);
    const s = await r.json();
    setSelectedSource(s.id);
    refresh();
  };

  const drawOverlay = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img) return;
    canvas.width = img.clientWidth;
    canvas.height = img.clientHeight;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // saved zones
    for (const z of zones) {
      ctx.strokeStyle = "#f59e0b";
      ctx.lineWidth = 2;
      ctx.beginPath();
      z.polygon.forEach(([x, y], i) => {
        const px = x * canvas.width;
        const py = y * canvas.height;
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      });
      ctx.closePath();
      ctx.stroke();
      ctx.fillStyle = "rgba(245, 158, 11, 0.15)";
      ctx.fill();
    }

    // in-progress polygon
    if (points.length > 0) {
      ctx.strokeStyle = "#3b82f6";
      ctx.lineWidth = 2;
      ctx.beginPath();
      points.forEach(([x, y], i) => {
        const px = x * canvas.width;
        const py = y * canvas.height;
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      });
      ctx.stroke();
      for (const [x, y] of points) {
        ctx.fillStyle = "#3b82f6";
        ctx.beginPath();
        ctx.arc(x * canvas.width, y * canvas.height, 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }, [zones, points]);

  useEffect(() => {
    drawOverlay();
  }, [drawOverlay]);

  const canvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!drawing || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;
    setPoints((p) => [...p, [Math.min(1, Math.max(0, x)), Math.min(1, Math.max(0, y))]]);
  };

  const saveZone = async () => {
    if (!selectedSource || points.length < 3) return;
    const r = await fetch(`${API}/api/zones`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_id: selectedSource, name: zoneName, polygon: points }),
    });
    if (!r.ok) return apiError(r);
    setPoints([]);
    setDrawing(false);
    refresh();
  };

  const compile = async () => {
    if (!selectedSource) {
      setError("select a source first");
      return;
    }
    setError(null);
    const r = await fetch(`${API}/api/workflows/compile`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_id: selectedSource, text: nlText }),
    });
    if (!r.ok) return apiError(r);
    const body: CompileResponse = await r.json();
    setCompileResult(body);
  };

  const applyDraft = () => {
    const d = compileResult?.draft;
    if (!d) return;
    setWfName(d.name);
    setWfClass(d.object_class);
    setWfTrigger(d.trigger.type);
    setWfZone(d.trigger.zone_id);
    if (d.trigger.duration_seconds) setWfDuration(Math.round(d.trigger.duration_seconds));
    if (d.trigger.threshold) setWfThreshold(d.trigger.threshold);
    setVisualPredicate(d.visual_predicate ?? null);
  };

  const createWorkflow = async () => {
    if (!selectedSource || !wfZone) {
      setError("select a source and a zone first");
      return;
    }
    setError(null);
    const trigger: Record<string, unknown> = { type: wfTrigger, zone_id: wfZone };
    if (wfTrigger === "dwell_in_zone") trigger.duration_seconds = wfDuration;
    if (wfTrigger === "object_count_exceeded") trigger.threshold = wfThreshold;
    const payload: Record<string, unknown> = {
      name: wfName,
      source_id: selectedSource,
      object_class: wfClass,
      trigger,
      action: { type: "create_notification", config: { title: wfName } },
      cooldown_seconds: 10,
    };
    if (visualPredicate) payload.visual_predicate = visualPredicate;
    const r = await fetch(`${API}/api/workflows`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!r.ok) return apiError(r);
    setVisualPredicate(null);
    setCompileResult(null);
    refresh();
  };

  const toggleWorkflow = async (wf: Workflow) => {
    const action = wf.enabled ? "disable" : "enable";
    const r = await fetch(`${API}/api/workflows/${wf.id}/${action}`, { method: "POST" });
    if (!r.ok) return apiError(r);
    refresh();
  };

  const processSource = async (id: number) => {
    setError(null);
    const r = await fetch(`${API}/api/sources/${id}/process`, { method: "POST" });
    if (!r.ok) return apiError(r);
    refresh();
  };

  const current = sources.find((s) => s.id === selectedSource) || null;

  return (
    <main>
      <h1>VisionFlow AI</h1>
      <p className="muted">
        Upload a video, draw a zone, enable a workflow, process — real detections become events
        and authorized actions.
      </p>
      {error && <div className="error-banner">⚠ {error}</div>}

      <section className="card">
        <h2>1 · Video sources</h2>
        <div className="row" style={{ marginBottom: 12 }}>
          <input
            type="file"
            accept="video/mp4"
            disabled={uploading}
            onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
          />
          {uploading && <span className="muted">uploading…</span>}
        </div>
        {sources.length > 0 && (
          <table>
            <thead>
              <tr><th>ID</th><th>Name</th><th>Status</th><th>Frames</th><th>Inference</th><th></th></tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} style={{ background: s.id === selectedSource ? "#1e2430" : undefined }}>
                  <td>{s.id}</td>
                  <td>{s.name}</td>
                  <td>
                    <span className={`status-${s.status}`}>{s.status}</span>
                    {s.error && <span className="muted"> — {s.error}</span>}
                  </td>
                  <td>{s.frames_processed}</td>
                  <td>{s.avg_inference_ms ? `${s.avg_inference_ms.toFixed(0)} ms` : "—"}</td>
                  <td className="row">
                    <button className="secondary" onClick={() => setSelectedSource(s.id)}>Select</button>
                    <button
                      onClick={() => processSource(s.id)}
                      disabled={s.status === "processing"}
                    >
                      {s.status === "processing" ? "Processing…" : "Process"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {current && (
        <section className="card">
          <h2>2 · Zones for “{current.name}”</h2>
          <div className="row" style={{ marginBottom: 10 }}>
            <input value={zoneName} onChange={(e) => setZoneName(e.target.value)} placeholder="Zone name" />
            {!drawing ? (
              <button onClick={() => { setDrawing(true); setPoints([]); }}>Draw zone</button>
            ) : (
              <>
                <button onClick={saveZone} disabled={points.length < 3}>
                  Save zone ({points.length} pts)
                </button>
                <button className="secondary" onClick={() => { setDrawing(false); setPoints([]); }}>
                  Cancel
                </button>
                <span className="muted">click on the image to add polygon points</span>
              </>
            )}
          </div>
          <div className="canvas-wrap">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imgRef}
              src={`${API}/api/sources/${current.id}/snapshot`}
              alt="first frame"
              onLoad={drawOverlay}
            />
            <canvas ref={canvasRef} onClick={canvasClick} />
          </div>
          {zones.length > 0 && (
            <p className="muted">Saved zones: {zones.map((z) => `${z.name} (#${z.id})`).join(", ")}</p>
          )}
        </section>
      )}

      {current && (
        <section className="card">
          <h2>3 · Workflows</h2>

          <div style={{ marginBottom: 16, padding: 12, border: "1px solid #2a3140", borderRadius: 8 }}>
            <h3 style={{ margin: "0 0 8px" }}>Describe a rule in plain language</h3>
            <div className="row" style={{ marginBottom: 8 }}>
              <textarea
                value={nlText}
                onChange={(e) => setNlText(e.target.value)}
                rows={2}
                style={{ flex: 1, minWidth: 320 }}
                placeholder="e.g. When a car stays in Service Bay A for more than 10 minutes, create an alert"
              />
              <button onClick={compile}>Compile</button>
            </div>
            {compileResult && (
              <div className="muted" style={{ fontSize: 13 }}>
                {compileResult.ok ? (
                  <>
                    <div style={{ color: "#4ade80" }}>✓ {compileResult.explanation}</div>
                    {compileResult.warnings.map((w, i) => (
                      <div key={i} style={{ color: "#fbbf24" }}>⚠ {w}</div>
                    ))}
                    <button className="secondary" style={{ marginTop: 6 }} onClick={applyDraft}>
                      Apply draft to form below (review, then create)
                    </button>
                  </>
                ) : (
                  <div style={{ color: "#f87171" }}>
                    ✗ Could not compile:
                    {compileResult.errors.map((er, i) => (
                      <div key={i}>• {er}</div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {visualPredicate && (
            <div className="muted" style={{ marginBottom: 8, color: "#a78bfa" }}>
              🔎 Visual predicate attached: “{visualPredicate.prompt}” (expects “
              {visualPredicate.expected_label}”). Routed to the Teacher VLM on candidate events
              only.{" "}
              <button className="secondary" onClick={() => setVisualPredicate(null)}>
                remove
              </button>
            </div>
          )}

          <div className="row" style={{ marginBottom: 12 }}>
            <input value={wfName} onChange={(e) => setWfName(e.target.value)} placeholder="Workflow name" />
            <select value={wfClass} onChange={(e) => setWfClass(e.target.value)}>
              {CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <select value={wfTrigger} onChange={(e) => setWfTrigger(e.target.value)}>
              {TRIGGER_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <select value={wfZone ?? ""} onChange={(e) => setWfZone(Number(e.target.value) || null)}>
              <option value="">— zone —</option>
              {zones.map((z) => <option key={z.id} value={z.id}>{z.name}</option>)}
            </select>
            {wfTrigger === "dwell_in_zone" && (
              <label className="muted">
                dwell s:{" "}
                <input
                  type="number" min={1} style={{ width: 70 }}
                  value={wfDuration} onChange={(e) => setWfDuration(Number(e.target.value))}
                />
              </label>
            )}
            {wfTrigger === "object_count_exceeded" && (
              <label className="muted">
                threshold:{" "}
                <input
                  type="number" min={1} style={{ width: 70 }}
                  value={wfThreshold} onChange={(e) => setWfThreshold(Number(e.target.value))}
                />
              </label>
            )}
            <button onClick={createWorkflow}>Create (disabled by default)</button>
          </div>
          {workflows.length > 0 && (
            <table>
              <thead><tr><th>ID</th><th>Name</th><th>Rule</th><th>Status</th><th></th></tr></thead>
              <tbody>
                {workflows.map((w) => (
                  <tr key={w.id}>
                    <td>{w.id}</td>
                    <td>{w.name}</td>
                    <td className="muted">
                      {w.dsl.object_class} · {w.dsl.trigger.type}
                      {w.dsl.trigger.duration_seconds ? ` ≥${w.dsl.trigger.duration_seconds}s` : ""}
                      {w.dsl.trigger.threshold ? ` >${w.dsl.trigger.threshold}` : ""}
                      {w.dsl.visual_predicate ? (
                        <span style={{ color: "#a78bfa" }}> · 🔎 visual</span>
                      ) : null}
                    </td>
                    <td>{w.enabled ? <span className="status-processed">enabled</span> : <span className="muted">disabled</span>}</td>
                    <td><button className="secondary" onClick={() => toggleWorkflow(w)}>{w.enabled ? "Disable" : "Enable"}</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      <section className="card">
        <h2>4 · Event timeline</h2>
        {events.length === 0 ? (
          <p className="muted">No events yet. Upload, draw a zone, enable a workflow, then Process.</p>
        ) : (
          <table>
            <thead>
              <tr><th>ID</th><th>Event</th><th>Video time</th><th>Conf</th><th>Visual</th><th>Evidence</th><th>Action</th></tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id}>
                  <td>{e.id}</td>
                  <td>{e.detail || e.type}</td>
                  <td>{e.video_timestamp.toFixed(1)}s</td>
                  <td>{(e.confidence * 100).toFixed(0)}%</td>
                  <td className="muted">
                    {e.visual_status ? (
                      <span style={{ color: e.visual_status === "ok" ? "#4ade80" : "#fbbf24" }}>
                        {e.visual_status}
                        {e.visual_label ? ` → ${e.visual_label}` : ""}
                      </span>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>
                    {e.evidence_url && (
                      <a href={`${API}${e.evidence_url}`} target="_blank" rel="noreferrer">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img className="evidence-thumb" src={`${API}${e.evidence_url}`} alt="evidence" />
                      </a>
                    )}
                  </td>
                  <td>
                    <span className={e.action_status === "done" ? "status-processed" : "status-failed"}>
                      {e.action_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h2>5 · Notifications (executed actions)</h2>
        {notifications.length === 0 ? (
          <p className="muted">No notifications yet.</p>
        ) : (
          <table>
            <thead><tr><th>ID</th><th>Title</th><th>Message</th><th>At</th></tr></thead>
            <tbody>
              {notifications.map((n) => (
                <tr key={n.id}>
                  <td>{n.id}</td>
                  <td>{n.title}</td>
                  <td>{n.message}</td>
                  <td className="muted">{new Date(n.created_at).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h2>6 · Teacher VLM routing (cost-efficient path)</h2>
        {vlmStats ? (
          <>
            <p className="muted">
              Provider: <strong>{vlmStats.live.teacher_provider}</strong> ·{" "}
              {vlmStats.live.teacher_available ? (
                <span className="status-processed">available</span>
              ) : (
                <span className="status-failed">
                  not configured — visual predicates cannot confirm (documented blocker)
                </span>
              )}
            </p>
            <table>
              <thead>
                <tr>
                  <th>Teacher calls</th><th>Cache hits</th><th>Confirmed</th><th>Unknown</th>
                  <th>Failed</th><th>Suppr. budget</th><th>Suppr. cooldown</th><th>Suppr. sampling</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>{vlmStats.live.calls}</td>
                  <td>{vlmStats.live.cache_hits}</td>
                  <td>{vlmStats.live.confirmed}</td>
                  <td>{vlmStats.live.unknown}</td>
                  <td>{vlmStats.live.failed}</td>
                  <td>{vlmStats.live.suppressed_budget}</td>
                  <td>{vlmStats.live.suppressed_cooldown}</td>
                  <td>{vlmStats.live.suppressed_sampling}</td>
                </tr>
              </tbody>
            </table>
            <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
              Geometric rules make zero Teacher calls. Teacher calls occur only for a visual
              predicate on an eligible candidate event, with sampling, cooldown, budget,
              in-flight dedup and a versioned cache.
            </p>
          </>
        ) : (
          <p className="muted">No routing stats yet.</p>
        )}
      </section>
    </main>
  );
}
