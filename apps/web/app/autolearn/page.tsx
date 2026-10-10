"use client";

/* AutoLearn — experimental Teacher -> human-reviewed -> Student vertical slice (M3).
 *
 * This page is intentionally honest about its experimental, UNVERIFIED status. It
 * drives the isolated backend slice: create a binary task, import disclosed
 * QA_ONLY synthetic sessions (or upload real images), run offline Teacher
 * labeling (pending when no provider is configured), verify labels, train a real
 * Student on frozen ResNet18 embeddings, read held-out metrics, compare in shadow
 * mode, and gate activation/rollback. No workflow action is ever dispatched. */

import { useCallback, useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

type Task = {
  id: number;
  name: string;
  visual_prompt: string;
  positive_label: string;
  negative_label: string;
  status: string;
  active_version_id: number | null;
};

type Version = {
  id: number;
  version: number;
  status: string;
  threshold: number;
  metrics: Record<string, unknown> | null;
  train_count: number;
  val_count: number;
  test_count: number;
  train_duration_ms: number;
  dataset_hash: string;
  split_hash: string;
};

type Sample = {
  id: number;
  session_id: string;
  image_hash: string;
  origin: string;
  image_url: string;
  teacher_status: string;
  teacher_label: string | null;
  verified: boolean;
  verified_label: string | null;
  split: string | null;
};

type TaskDetail = {
  task: Task;
  counts: { samples: number; verified: number; pending_teacher: number; sessions: number };
  versions: Version[];
};

async function jget<T>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `GET ${path} ${r.status}`);
  return r.json();
}
async function jpost<T>(path: string, body?: unknown): Promise<T> {
  const r = await fetch(`${API}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `POST ${path} ${r.status}`);
  return r.json();
}

export default function AutoLearnPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [status, setStatus] = useState<{ provider_configured: boolean; gate: { min_f1: number; min_test: number } } | null>(null);
  const [sel, setSel] = useState<number | null>(null);
  const [detail, setDetail] = useState<TaskDetail | null>(null);
  const [samples, setSamples] = useState<Sample[]>([]);
  const [shadow, setShadow] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [reviewer, setReviewer] = useState("operator");

  const [form, setForm] = useState({ name: "", visual_prompt: "", positive_label: "occupied", negative_label: "empty" });

  const refreshTasks = useCallback(async () => {
    try {
      setTasks(await jget<Task[]>("/api/autolearn/tasks"));
      setStatus(await jget("/api/autolearn/status"));
    } catch (e) { setErr(String(e)); }
  }, []);

  const refreshDetail = useCallback(async (id: number) => {
    try {
      setDetail(await jget<TaskDetail>(`/api/autolearn/tasks/${id}`));
      setSamples(await jget<Sample[]>(`/api/autolearn/tasks/${id}/samples`));
    } catch (e) { setErr(String(e)); }
  }, []);

  useEffect(() => { refreshTasks(); }, [refreshTasks]);
  useEffect(() => { if (sel != null) refreshDetail(sel); }, [sel, refreshDetail]);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(label); setErr(null);
    try { await fn(); } catch (e) { setErr(String(e)); } finally { setBusy(null); }
  };

  const createTask = () => run("create", async () => {
    if (!form.name.trim() || form.visual_prompt.trim().length < 3) { setErr("Name and a prompt (≥3 chars) are required."); return; }
    const t = await jpost<Task>("/api/autolearn/tasks", form);
    setForm({ ...form, name: "", visual_prompt: "" });
    await refreshTasks();
    setSel(t.id);
  });

  const latest = detail?.versions[0];

  return (
    <>
      <header className="appbar">
        <div className="appbar-inner">
          <div className="brand">
            <div className="brand-text">
              <h1>VisionFlow AI · AutoLearn</h1>
              <p>Teacher → human review → Student · experimental vertical slice</p>
            </div>
          </div>
          <div className="chips">
            <span className="chip warn"><span className="dot" /> Experimental · UNVERIFIED</span>
            {status && (status.provider_configured
              ? <span className="chip on"><span className="dot" /> Teacher provider set</span>
              : <span className="chip unavailable"><span className="dot" /> Teacher provider · none</span>)}
            <a className="chip planned" href="/" style={{ textDecoration: "none" }}>← Home (demo-safe)</a>
          </div>
        </div>
      </header>

      <main className="shell">
        <div className="hint warn" style={{ marginTop: 0 }}>
          <div>
            This is an isolated, explicitly <strong>UNVERIFIED</strong> experiment. The Student is a real
            classifier fitted on frozen ResNet18 embeddings; it is used only for offline classification and
            <strong> never dispatches a workflow action</strong>. Synthetic data is QA_ONLY and carries no
            real-world quality claim. Only human-verified labels enter training.
          </div>
        </div>

        {err && <div className="banner error"><span>{err}</span><button className="ghost sm" onClick={() => setErr(null)}>Dismiss</button></div>}

        {/* ------------------------------------------------ create / select */}
        <section className="card">
          <div className="card-head"><span className="idx">1</span><h2>Classification task</h2><span className="sub">configurable binary labels</span></div>
          <div className="form-grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 10 }}>
            <input placeholder="Task name (e.g. Bay occupancy)" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
            <input placeholder="Visual prompt (question the Teacher answers)" value={form.visual_prompt} onChange={e => setForm({ ...form, visual_prompt: e.target.value })} />
            <input placeholder="Positive label" value={form.positive_label} onChange={e => setForm({ ...form, positive_label: e.target.value })} />
            <input placeholder="Negative label" value={form.negative_label} onChange={e => setForm({ ...form, negative_label: e.target.value })} />
          </div>
          <div className="row" style={{ marginTop: 12 }}>
            <button className="secondary" disabled={busy === "create"} onClick={createTask}>{busy === "create" ? <span className="spinner" /> : null} Create task</button>
          </div>
          {tasks.length > 0 && (
            <div className="row" style={{ marginTop: 14, flexWrap: "wrap", gap: 8 }}>
              {tasks.map(t => (
                <button key={t.id} className={sel === t.id ? "sm" : "secondary sm"} onClick={() => setSel(t.id)}>
                  #{t.id} {t.name} <span className="faint">· {t.status}</span>
                </button>
              ))}
            </div>
          )}
        </section>

        {sel != null && detail && (
          <>
            {/* ------------------------------------------------ dataset */}
            <section className="card">
              <div className="card-head"><span className="idx">2</span><h2>Dataset & labeling</h2>
                <span className="sub">{detail.counts.samples} images · {detail.counts.sessions} sessions · {detail.counts.verified} verified</span></div>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <button className="secondary sm" disabled={!!busy} onClick={() => run("import", async () => { await jpost(`/api/autolearn/tasks/${sel}/import-synthetic`, { n_sessions: 5, per_class_per_session: 3 }); await refreshDetail(sel); })}>
                  {busy === "import" ? <span className="spinner" /> : null} Import QA_ONLY synthetic sessions
                </button>
                <button className="secondary sm" disabled={!!busy} onClick={() => run("label", async () => { const r = await jpost<{ status: string; detail?: string }>(`/api/autolearn/tasks/${sel}/label`); if (r.status === "unavailable") setErr("Teacher provider not configured — labels remain pending (no synthetic labels invented)."); await refreshDetail(sel); })}>
                  {busy === "label" ? <span className="spinner" /> : null} Run Teacher labeling
                </button>
              </div>
              <p className="faint" style={{ marginTop: 8 }}>Synthetic import is disclosed QA_ONLY data. With no VLM provider set, Teacher labeling returns an honest pending/unavailable state.</p>

              {samples.length > 0 && (
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10, marginTop: 14 }}>
                  {samples.slice(0, 40).map(s => (
                    <div key={s.id} className="card" style={{ margin: 0, padding: 8 }}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={`${API}${s.image_url}`} alt={`sample ${s.id}`} style={{ width: "100%", borderRadius: 6, border: "1px solid var(--border)" }} />
                      <div className="faint" style={{ marginTop: 4 }}>{s.session_id}</div>
                      <div className="faint">teacher: {s.teacher_status}{s.teacher_label ? ` (${s.teacher_label})` : ""}</div>
                      {s.verified
                        ? <span className="badge done" style={{ marginTop: 4 }}><span className="dot" />verified: {s.verified_label}</span>
                        : (
                          <div className="row" style={{ marginTop: 6, gap: 4 }}>
                            <button className="ghost sm" disabled={!!busy} onClick={() => run("rev", async () => { await jpost(`/api/autolearn/samples/${s.id}/review`, { verified_label: detail.task.positive_label, reviewer }); await refreshDetail(sel); })}>{detail.task.positive_label}</button>
                            <button className="ghost sm" disabled={!!busy} onClick={() => run("rev", async () => { await jpost(`/api/autolearn/samples/${s.id}/review`, { verified_label: detail.task.negative_label, reviewer }); await refreshDetail(sel); })}>{detail.task.negative_label}</button>
                          </div>
                        )}
                    </div>
                  ))}
                </div>
              )}
            </section>

            {/* ------------------------------------------------ train / eval */}
            <section className="card">
              <div className="card-head"><span className="idx">3</span><h2>Train & evaluate Student</h2>
                <span className="sub">frozen ResNet18 embeddings · logistic regression</span></div>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                <button className="secondary sm" disabled={!!busy} onClick={() => run("train", async () => { await jpost(`/api/autolearn/tasks/${sel}/train`); await refreshDetail(sel); })}>
                  {busy === "train" ? <span className="spinner" /> : null} Train Student
                </button>
                {latest && <button className="secondary sm" disabled={!!busy} onClick={() => run("shadow", async () => { setShadow(await jget(`/api/autolearn/tasks/${sel}/shadow`)); })}>Run shadow comparison</button>}
              </div>

              {detail.versions.length > 0 && (
                <table style={{ marginTop: 14 }}>
                  <thead><tr><th>v</th><th>status</th><th>train/val/test</th><th>F1</th><th>precision</th><th>recall</th><th>thr</th><th>gate / act</th></tr></thead>
                  <tbody>
                    {detail.versions.map(v => {
                      const m = (v.metrics || {}) as Record<string, number>;
                      return (
                        <tr key={v.id}>
                          <td>{v.version}</td>
                          <td><span className={`badge ${v.status === "active" ? "enabled" : "neutral"}`}><span className="dot" />{v.status}</span></td>
                          <td className="faint">{v.train_count}/{v.val_count}/{v.test_count}</td>
                          <td>{m.f1 ?? "—"}</td><td>{m.precision ?? "—"}</td><td>{m.recall ?? "—"}</td>
                          <td className="faint">{v.threshold}</td>
                          <td className="row" style={{ gap: 4, justifyContent: "flex-end" }}>
                            <button className="ghost sm" disabled={!!busy} onClick={() => run("eval", async () => { await jpost(`/api/autolearn/versions/${v.id}/evaluate`); await refreshDetail(sel); })}>Eval</button>
                            <button className="sm" disabled={!!busy} onClick={() => run("act", async () => { const r = await jpost<{ activated: boolean; reason?: string }>(`/api/autolearn/versions/${v.id}/activate`, { approve: true, approver: reviewer }); if (!r.activated) setErr(`Not activated: ${r.reason}`); await refreshDetail(sel); })}>Activate</button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
              <p className="faint" style={{ marginTop: 10 }}>
                Activation requires a passed held-out gate (F1 ≥ {status?.gate.min_f1}, test ≥ {status?.gate.min_test}) <em>and</em> this explicit approval. Metrics come from real held-out predictions.
              </p>
              <div className="row" style={{ marginTop: 6, gap: 8 }}>
                {detail.task.active_version_id && <button className="ghost sm" disabled={!!busy} onClick={() => run("rb", async () => { await jpost(`/api/autolearn/tasks/${sel}/rollback`, { approver: reviewer }); await refreshDetail(sel); })}>Roll back active version</button>}
              </div>
            </section>

            {shadow && (
              <section className="card">
                <div className="card-head"><span className="idx">4</span><h2>Shadow comparison</h2><span className="sub">zero actions · Teacher vs Student</span></div>
                <pre className="faint" style={{ whiteSpace: "pre-wrap", fontSize: "0.75rem", overflowX: "auto" }}>{JSON.stringify(shadow, null, 2)}</pre>
              </section>
            )}
          </>
        )}
      </main>
    </>
  );
}
