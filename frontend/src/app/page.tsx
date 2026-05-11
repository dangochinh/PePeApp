"use client";

import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

const API_BASE = "http://localhost:8888/api";

type Job = {
  job_id: string;
  status: string;
  progress_pct: number;
  current_step: string;
  logs?: string[];
  error?: string;
  project_dir?: string;
  created_at?: string;
};

type Settings = {
  tts_engine: string;
  tts_voice: string;
  ollama_model: string;
  ollama_base_url: string;
  use_cloud_ai: boolean;
  openai_api_key: string;
  openai_base_url: string;
  openai_model: string;
  comfyui_base_url: string;
  scenes_per_video: number;
  available_tts_engines: string[];
  draw_things_steps: number;
  draw_things_cfg: number;
  image_style: string;
  transition_style: string;
  ken_burns: boolean;
  color_grade: string;
  available_image_styles: string[];
  available_transitions: string[];
  available_color_grades: string[];
  bg_music_path: string;
  bg_music_volume: number;
  watermark_path: string;
  watermark_position: string;
  watermark_opacity: number;
  available_watermark_positions: string[];
  enable_intro_card: boolean;
  enable_outro_card: boolean;
  outro_card_text: string;
  enable_upscale: boolean;
  use_img2img_ref: boolean;
  img2img_denoising: number;
  t2v_engine: string;
  available_t2v_engines: string[];
  replicate_api_key: string;
  replicate_t2v_model: string;
  wan_model_name: string;
  t2v_num_frames: number;
  t2v_fps: number;
  social: {
    youtube: { client_id: string; client_secret: string; refresh_token: string; };
    tiktok: { access_token: string; session_id: string; };
    facebook: { access_token: string; page_id: string; };
  };
};

function BgMusicPanel({ settings, updateSetting, apiBase }: { settings: any; updateSetting: (k: string, v: string) => void; apiBase: string }) {
  const [tracks, setTracks] = React.useState<{ name: string; path: string; size_mb: number }[]>([]);
  const [uploading, setUploading] = React.useState(false);

  const loadTracks = React.useCallback(() => {
    fetch(`${apiBase}/projects/music/list`).then(r => r.json()).then(setTracks).catch(() => {});
  }, [apiBase]);

  React.useEffect(() => { loadTracks(); }, [loadTracks]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    const fd = new FormData();
    fd.append("file", file);
    await fetch(`${apiBase}/projects/music/upload`, { method: "POST", body: fd });
    setUploading(false);
    loadTracks();
  };

  const handleDelete = async (name: string) => {
    await fetch(`${apiBase}/projects/music/${encodeURIComponent(name)}`, { method: "DELETE" });
    if (settings.bg_music_path?.includes(name)) updateSetting("bg_music_path", "");
    loadTracks();
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Track list */}
      <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 160, overflowY: "auto" }}>
        {tracks.length === 0
          ? <div style={{ fontSize: 12, color: "var(--text-secondary)", opacity: 0.5 }}>No tracks yet — upload an mp3/wav file</div>
          : tracks.map(t => {
              const active = settings.bg_music_path?.includes(t.name);
              return (
                <div key={t.name} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 12px", borderRadius: 8, background: active ? "rgba(234,179,8,0.1)" : "rgba(255,255,255,0.03)", border: `1px solid ${active ? "rgba(234,179,8,0.35)" : "var(--border)"}` }}>
                  <span style={{ fontSize: 14 }}>🎵</span>
                  <span style={{ flex: 1, fontSize: 12, fontWeight: active ? 700 : 400, color: active ? "var(--accent-gold)" : "white", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{t.name}</span>
                  <span style={{ fontSize: 10, color: "var(--text-secondary)", flexShrink: 0 }}>{t.size_mb}MB</span>
                  <button onClick={() => updateSetting("bg_music_path", active ? "" : t.path)} style={{ fontSize: 11, padding: "3px 10px", borderRadius: 6, border: `1px solid ${active ? "rgba(234,179,8,0.4)" : "rgba(255,255,255,0.15)"}`, background: "transparent", color: active ? "var(--accent-gold)" : "var(--text-secondary)", cursor: "pointer", fontWeight: active ? 700 : 400 }}>{active ? "✓ Active" : "Use"}</button>
                  <button onClick={() => handleDelete(t.name)} style={{ fontSize: 11, padding: "3px 8px", borderRadius: 6, border: "1px solid rgba(239,68,68,0.3)", background: "transparent", color: "#EF4444", cursor: "pointer" }}>✕</button>
                </div>
              );
            })
        }
      </div>
      {/* Volume slider */}
      {settings.bg_music_path && (
        <div>
          <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>
            VOLUME <span style={{ color: "var(--accent-gold)", fontWeight: 700 }}>{Math.round((settings.bg_music_volume ?? 0.12) * 100)}%</span>
            <span style={{ opacity: 0.5 }}> (relative to TTS voice)</span>
          </label>
          <input type="range" min={0} max={1} step={0.01} value={settings.bg_music_volume ?? 0.12}
            onChange={e => updateSetting("bg_music_volume", e.target.value)}
            style={{ width: "100%", accentColor: "var(--accent-gold)" }} />
        </div>
      )}
      {/* Upload */}
      <label style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 14px", borderRadius: 10, border: "1px dashed rgba(234,179,8,0.35)", background: "rgba(234,179,8,0.04)", cursor: "pointer", fontSize: 12, color: "var(--accent-gold)", fontWeight: 600 }}>
        {uploading ? "⏳ Uploading..." : "⬆ Upload mp3 / wav"}
        <input type="file" accept=".mp3,.wav,.m4a,.ogg" style={{ display: "none" }} onChange={handleUpload} disabled={uploading} />
      </label>
    </div>
  );
}

export default function Dashboard() {
  const [topic, setTopic] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"dashboard" | "projects" | "settings">("dashboard");
  
  // Modals state
  const [showPublisherConfig, setShowPublisherConfig] = useState<string | null>(null);
  const [editingScene, setEditingScene] = useState<{proj: string, scene: any} | null>(null);
  const [showTechnicalModal, setShowTechnicalModal] = useState(false);
  const [selectedScenes, setSelectedScenes] = useState<Set<number>>(new Set());
  const [activeJob, setActiveJob] = useState<any>(null);

  // Media preview modal
  const [mediaPreview, setMediaPreview] = useState<{
    url: string; isVideo: boolean; projName: string; allScenes: any[]; idx: number; audioUrl: string | null;
  } | null>(null);
  const [renderingScenes, setRenderingScenes] = useState<Set<number>>(new Set());
  const [scriptStyle, setScriptStyle] = useState<"4wh" | "viral">("4wh");
  const [publishForm, setPublishForm] = useState<{
    title: string; description: string; hashtags: string[];
    platforms: string[]; generating: boolean; publishing: boolean;
    results: Record<string, any> | null;
  }>({ title: "", description: "", hashtags: [], platforms: ["youtube", "tiktok", "facebook"], generating: false, publishing: false, results: null });
  const [logCollapsed, setLogCollapsed] = useState(true);

  type ServiceInfo = { id: string; name: string; online: boolean; busy: boolean; process: string; url?: string | null; engine?: string; model?: string; hint?: string | null; };
  const [services, setServices] = useState<ServiceInfo[]>([]);
  const [serviceLoading, setServiceLoading] = useState<Record<string, string>>({});

  async function fetchServices() {
    try {
      const res = await fetch(`${API_BASE}/services/status`);
      if (res.ok) {
        const data = await res.json();
        setServices(data.services ?? []);
      }
    } catch {}
  }

  async function serviceAction(id: string, action: "start" | "stop") {
    setServiceLoading(prev => ({ ...prev, [id]: action }));
    try {
      await fetch(`${API_BASE}/services/${id}/${action}`, { method: "POST" });
      await new Promise(r => setTimeout(r, 1500));
      await fetchServices();
    } catch {}
    setServiceLoading(prev => { const n = { ...prev }; delete n[id]; return n; });
  }

  useEffect(() => {
    fetchServices();
    const iv = setInterval(fetchServices, 10000);
    return () => clearInterval(iv);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleScene = (idx: number) =>
    setSelectedScenes(prev => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx); else next.add(idx);
      return next;
    });

  // Mount: initial load + WebSocket for real-time job updates
  useEffect(() => {
    let mounted = true;
    let ws: WebSocket | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let pingInterval: ReturnType<typeof setInterval> | null = null;

    async function init() {
      await fetchJobs();
      const projs = await fetchProjects();
      await fetchSettings();

      if (typeof window !== "undefined") {
        const searchParams = new URLSearchParams(window.location.search);
        let projectId = searchParams.get("project");
        if (!projectId && window.location.pathname.startsWith("/projects/")) {
          projectId = decodeURIComponent(window.location.pathname.split("/")[2]);
        }
        if (projectId && projs) {
          const found = projs.find((p: any) => p.name === projectId || p.job_id === projectId);
          if (found) loadProject(found.name);
        }
      }
    }

    function connectWS() {
      if (!mounted) return;
      ws = new WebSocket("ws://localhost:8888/ws");

      ws.onmessage = (event) => {
        if (event.data === "pong") return;
        try {
          const jobData = JSON.parse(event.data);
          if (!jobData.job_id) return;
          setJobs((prev: Job[]) => {
            const idx = prev.findIndex((j) => j.job_id === jobData.job_id);
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = jobData;
              return updated;
            }
            return [jobData, ...prev];
          });
          setActiveJob((prev: any) => {
            if (!prev || prev.job_id === jobData.job_id) return jobData;
            const isLive = !["completed", "failed", "cancelled"].includes(jobData.status);
            return isLive ? jobData : prev;
          });
        } catch {}
      };

      ws.onopen = () => {
        if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        if (pingInterval) clearInterval(pingInterval);
        pingInterval = setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) ws.send("ping");
        }, 25000);
      };

      ws.onclose = () => {
        if (pingInterval) { clearInterval(pingInterval); pingInterval = null; }
        if (mounted) reconnectTimer = setTimeout(connectWS, 3000);
      };
    }

    init();
    connectWS();

    return () => {
      mounted = false;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (pingInterval) clearInterval(pingInterval);
      ws?.close();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll projects list only when on projects tab
  useEffect(() => {
    if (activeTab !== "projects") return;
    fetchProjects();
    const interval = setInterval(fetchProjects, 5000);
    return () => clearInterval(interval);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab]);

  async function fetchJobs() {
    try {
      const res = await fetch(`${API_BASE}/jobs/list`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
        setActiveJob((prev: any) => {
          const liveJob = data.find((j: Job) => !["completed", "failed", "cancelled"].includes(j.status));
          if (liveJob) return liveJob;
          if (!prev) return data[0] ?? null;
          // Keep manually loaded project if it's not in the jobs list
          const stillInJobs = data.find((j: Job) => j.job_id === prev?.job_id);
          return stillInJobs ?? prev;
        });
        // After backend restart _jobs is empty — auto-load the most recent project from disk
        if (data.length === 0) {
          const projRes = await fetch(`${API_BASE}/projects/list`);
          if (projRes.ok) {
            const projs = await projRes.json();
            if (projs.length > 0) {
              const loadRes = await fetch(`${API_BASE}/projects/${projs[0].name}/load`);
              if (loadRes.ok) {
                const loaded = await loadRes.json();
                setActiveJob((prev: any) => {
                  // Always refresh with disk data (has accurate has_final), unless user loaded a different project
                  if (!prev || prev.job_id === loaded.job_id || prev.project_dir === loaded.project_dir) return loaded;
                  return prev;
                });
              }
            }
          }
        }
      }
    } catch {}
  }

  async function loadProject(projName: string) {
    const res = await fetch(`${API_BASE}/projects/${projName}/load`);
    if (res.ok) {
      const data = await res.json();
      setActiveJob(data);
      setActiveTab("dashboard");
      window.history.pushState(null, "", `/projects/${projName}`);
    }
  }

  async function fetchProjects() {
    try {
      const res = await fetch(`${API_BASE}/projects/list`);
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
        return data;
      }
    } catch {}
    return null;
  }

  async function fetchSettings() {
    try {
      const res = await fetch(`${API_BASE}/settings/`);
      if (res.ok) setSettings(await res.json());
    } catch {}
  }

  async function handleGenerate() {
    if (!topic.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/jobs/create`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, auto_publish: false, script_style: scriptStyle }),
      });
      if (res.ok) {
        const data = await res.json();
        setTopic("");
        if (data.project_name) {
          window.history.pushState(null, "", `/projects/${data.project_name}`);
        } else {
          window.history.pushState(null, "", "/");
        }
        setActiveJob(null);
        fetchJobs();
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  }

  async function updateSetting(key: string, value: string) {
    try {
      await fetch(`${API_BASE}/settings/`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ [key]: value }),
      });
      fetchSettings();
    } catch {}
  }

  // Auto-generate metadata when publish modal opens
  useEffect(() => {
    if (!showPublisherConfig) {
      setPublishForm(f => ({ ...f, results: null, generating: false, publishing: false }));
      return;
    }
    setPublishForm(f => ({ ...f, generating: true, title: "", description: "", hashtags: [], results: null }));
    fetch(`${API_BASE}/publish/${showPublisherConfig}/generate-metadata`, { method: "POST" })
      .then(r => r.json())
      .then(d => setPublishForm(f => ({ ...f, generating: false, title: d.title || "", description: d.description || "", hashtags: d.hashtags || [] })))
      .catch(() => setPublishForm(f => ({ ...f, generating: false })));
  }, [showPublisherConfig]);

  async function publishVideo() {
    if (!showPublisherConfig) return;
    setPublishForm(f => ({ ...f, publishing: true }));
    try {
      const r = await fetch(`${API_BASE}/publish/${showPublisherConfig}/publish`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: publishForm.title, description: publishForm.description, hashtags: publishForm.hashtags, platforms: publishForm.platforms }),
      });
      const data = await r.json();
      setPublishForm(f => ({ ...f, publishing: false, results: data.results || {} }));
    } catch {
      setPublishForm(f => ({ ...f, publishing: false }));
    }
  }

  function regenMetadata() {
    if (!showPublisherConfig) return;
    setPublishForm(f => ({ ...f, generating: true }));
    fetch(`${API_BASE}/publish/${showPublisherConfig}/generate-metadata`, { method: "POST" })
      .then(r => r.json())
      .then(d => setPublishForm(f => ({ ...f, generating: false, title: d.title || "", description: d.description || "", hashtags: d.hashtags || [] })))
      .catch(() => setPublishForm(f => ({ ...f, generating: false })));
  }

  const statusColor: Record<string, string> = {
    pending: "badge-pending",
    researching: "badge-researching",
    scripting: "badge-scripting",
    rendering: "badge-rendering",
    tts: "badge-tts",
    assembling: "badge-assembling",
    preview: "badge-preview",
    completed: "badge-completed",
    cancelling: "badge-failed",
    cancelled: "badge-failed",
    failed: "badge-failed",
  };

  return (
    <div style={{ display: "flex", height: "100vh", background: "var(--bg-primary)", overflow: "hidden" }}>
      {/* Sidebar */}
      <aside style={{ 
        width: 320, 
        borderRight: "1px solid var(--border)", 
        background: "var(--bg-secondary)", 
        display: "flex", 
        flexDirection: "column",
        padding: 24,
        gap: 24,
        overflowY: "auto"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 32 }}>🐸</span>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 800, background: "linear-gradient(135deg, #a855f7, #06b6d4)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              PePeApp
            </h1>
            <p style={{ fontSize: 11, color: "var(--text-secondary)" }}>AI Video Production Factory</p>
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, margin: 0, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1 }}>
            🚀 New Production
          </h3>
          {activeJob && (
            <button 
              onClick={() => {
                setActiveJob(null);
                setTopic("");
                window.history.pushState(null, "", "/");
              }}
              style={{ fontSize: 10, background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)", color: "var(--text-secondary)", padding: "4px 8px", borderRadius: 6, cursor: "pointer" }}
            >
              Clear
            </button>
          )}
        </div>
        <div>
          <textarea
            className="glow-input"
            style={{ 
              marginBottom: 12, 
              padding: "12px 16px", 
              fontSize: 14, 
              height: 120, 
              resize: "none",
              lineHeight: 1.5,
              background: "rgba(0,0,0,0.2)"
            }}
            placeholder="What's the video about? (Describe the topic, style, and goal...)"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
          />
          <div style={{ display: "flex", gap: 6, marginBottom: 10 }}>
            {(["4wh", "viral"] as const).map(s => (
              <button
                key={s}
                onClick={() => setScriptStyle(s)}
                style={{
                  flex: 1,
                  padding: "7px 0",
                  fontSize: 11,
                  fontWeight: 700,
                  borderRadius: 8,
                  border: scriptStyle === s ? "none" : "1px solid var(--border)",
                  background: scriptStyle === s
                    ? s === "viral"
                      ? "linear-gradient(135deg,#ef4444,#f97316)"
                      : "linear-gradient(135deg,#a855f7,#06b6d4)"
                    : "rgba(255,255,255,0.04)",
                  color: scriptStyle === s ? "white" : "var(--text-secondary)",
                  cursor: "pointer",
                  letterSpacing: 0.5,
                  transition: "all 0.15s",
                }}
              >
                {s === "4wh" ? "📐 4WH Framework" : "🔥 Viral 7 Scenes"}
              </button>
            ))}
          </div>
          <button
            className="btn-gradient"
            style={{ width: "100%", padding: 12, fontSize: 14 }}
            onClick={handleGenerate}
            disabled={loading || !topic.trim()}
          >
            {loading ? "⏳ Researching..." : "🔥 Start Pipeline"}
          </button>
        </div>

        <div style={{ marginTop: 20 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1 }}>
            📱 Publishers Status
          </h3>
          <div style={{ display: "flex", gap: 12 }}>
            {[
              { id: "youtube", color: "#FF0000", ready: !!settings?.social?.youtube?.refresh_token },
              { id: "tiktok", color: "#000000", ready: !!settings?.social?.tiktok?.session_id },
              { id: "facebook", color: "#1877F2", ready: !!settings?.social?.facebook?.page_id }
            ].map(p => (
              <div 
                key={p.id} 
                style={{ 
                  width: 48, 
                  height: 48, 
                  borderRadius: 14, 
                  background: p.color, 
                  color: "white", 
                  display: "flex", 
                  alignItems: "center", 
                  justifyContent: "center", 
                  position: "relative",
                  boxShadow: `0 4px 15px ${p.color}44`
                }}
              >
                <svg viewBox="0 0 24 24" style={{ width: 22, height: 22 }}>
                  {p.id === "youtube" && <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" fill="currentColor"/>}
                  {p.id === "tiktok" && <path d="M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.11-2.85-.56-4.06-1.35zM12.525.02v16.14c0 1.25-.41 2.45-1.15 3.42-.74.97-1.8 1.66-3 1.94s-2.47.11-3.56-.47c-1.09-.58-1.92-1.57-2.35-2.73s-.36-2.44.22-3.53c.58-1.09 1.57-1.92 2.73-2.35 1.16-.43 2.44-.36 3.53.22.61.32 1.13.78 1.52 1.34V.02h4.06z" fill="currentColor"/>}
                  {p.id === "facebook" && <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" fill="currentColor"/>}
                </svg>
                <div style={{ position: "absolute", top: -2, right: -2, width: 12, height: 12, borderRadius: "50%", background: p.ready ? "var(--accent-green)" : "#444", border: "2px solid var(--bg-secondary)" }} />
              </div>
            ))}
          </div>
        </div>

        {/* Services Section */}
        <div style={{ marginTop: 8 }}>
          <h3 style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1 }}>
            ⚙️ Services
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {services.length === 0 && (
              <div style={{ fontSize: 12, color: "var(--text-secondary)", opacity: 0.5 }}>Checking...</div>
            )}
            {services.map(svc => {
              const statusColor = svc.online ? (svc.busy ? "#f59e0b" : "#22c55e") : "#ef4444";
              const statusLabel = svc.busy ? "Busy" : svc.online ? "Online" : "Offline";
              const loading = serviceLoading[svc.id];
              return (
                <div key={svc.id} style={{ background: "rgba(0,0,0,0.2)", border: "1px solid var(--border)", borderRadius: 10, padding: "10px 12px" }}>
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 6 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <div style={{ width: 8, height: 8, borderRadius: "50%", background: statusColor, boxShadow: `0 0 6px ${statusColor}99`, flexShrink: 0 }} />
                      <span style={{ fontSize: 12, fontWeight: 600, color: "var(--text-primary)" }}>{svc.name}</span>
                    </div>
                    <span style={{ fontSize: 10, color: statusColor, fontWeight: 700 }}>{statusLabel}</span>
                  </div>
                  {(svc.model || svc.engine) && (
                    <div style={{ fontSize: 10, color: "var(--text-secondary)", marginBottom: 4, paddingLeft: 16, opacity: 0.7 }}>
                      {svc.model ?? svc.engine}
                    </div>
                  )}
                  {svc.hint && (
                    <div style={{ fontSize: 10, color: "#f59e0b", marginBottom: 4, paddingLeft: 16, lineHeight: 1.4 }}>
                      ⚠ {svc.hint}
                    </div>
                  )}
                  <div style={{ display: "flex", gap: 6, paddingLeft: 16 }}>
                    {svc.id !== "tts" && !svc.online && (
                      <button
                        onClick={() => serviceAction(svc.id, "start")}
                        disabled={!!loading}
                        style={{ fontSize: 10, padding: "3px 8px", borderRadius: 6, border: "1px solid #22c55e44", background: "rgba(34,197,94,0.1)", color: "#22c55e", cursor: "pointer", opacity: loading ? 0.5 : 1 }}
                      >
                        {loading === "start" ? "⏳" : "▶ Start"}
                      </button>
                    )}
                    {svc.id !== "tts" && svc.online && (
                      <button
                        onClick={() => serviceAction(svc.id, "stop")}
                        disabled={!!loading}
                        style={{ fontSize: 10, padding: "3px 8px", borderRadius: 6, border: "1px solid #ef444444", background: "rgba(239,68,68,0.1)", color: "#ef4444", cursor: "pointer", opacity: loading ? 0.5 : 1 }}
                      >
                        {loading === "stop" ? "⏳" : "■ Stop"}
                      </button>
                    )}
                    <button
                      onClick={fetchServices}
                      style={{ fontSize: 10, padding: "3px 8px", borderRadius: 6, border: "1px solid var(--border)", background: "rgba(255,255,255,0.05)", color: "var(--text-secondary)", cursor: "pointer" }}
                    >
                      ↺
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Top Navbar */}
        <nav style={{ height: 64, borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", padding: "0 32px", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
             <h2 style={{ fontSize: 16, fontWeight: 700 }}>Production Workspace</h2>
             <div style={{ width: 1, height: 20, background: "var(--border)" }} />
             <div style={{ display: "flex", gap: 8 }}>
                {["dashboard", "projects", "settings"].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => {
                      setActiveTab(tab as any);
                      if (tab === "dashboard") {
                        window.history.pushState(null, "", "/dashboard");
                      } else if (tab === "projects") {
                        window.history.pushState(null, "", "/projects");
                      } else if (tab === "settings") {
                        window.history.pushState(null, "", "/settings");
                      }
                    }}
                    style={{
                      padding: "6px 12px",
                      fontSize: 12,
                      borderRadius: 8,
                      border: "none",
                      background: activeTab === tab ? "rgba(168,85,247,0.15)" : "transparent",
                      color: activeTab === tab ? "var(--accent-purple)" : "var(--text-secondary)",
                      fontWeight: 700,
                      cursor: "pointer",
                      textTransform: "uppercase",
                      letterSpacing: 1
                    }}
                  >
                    {tab}
                  </button>
                ))}
             </div>
          </div>
          <div style={{ display: "flex", gap: 12 }}>
            <button 
              className="btn-gradient" 
              style={{ padding: "8px 20px", fontSize: 13 }} 
              onClick={async (e) => {
                const btn = e.currentTarget;
                btn.innerText = "⏳ Loading...";
                await fetchProjects();
                setTimeout(() => { btn.innerText = "📦 Refresh Assets"; }, 500);
              }}
            >
              📦 Refresh Assets
            </button>
          </div>
        </nav>

        {/* Workspace Content */}
        <div style={{ flex: 1, padding: 32, overflowY: "auto", display: "flex", flexDirection: "column", gap: 32 }}>
          
          {activeTab === "dashboard" && (
            <>
              {/* Pipeline Progress */}
              <section>
                {(() => {
                  const DONE_STATUSES = ["completed", "failed", "cancelled", "preview"];
                  const runningJob = jobs.find(j => !DONE_STATUSES.includes(j.status));
                  const displayJob = activeJob || runningJob;
                  const isCancelling = runningJob?.status === "cancelling";

                  return (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20 }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <h3 style={{ fontSize: 18, fontWeight: 700 }}>
                            {runningJob ? "Pipeline Execution" : activeJob ? "Project Preview" : "Factory Status"}
                          </h3>
                          {displayJob ? (
                            <div style={{ padding: "4px 12px", background: isCancelling ? "rgba(239,68,68,0.1)" : "rgba(168,85,247,0.1)", border: `1px solid ${isCancelling ? "rgba(239,68,68,0.3)" : "rgba(168,85,247,0.3)"}`, borderRadius: 12, fontSize: 12, color: isCancelling ? "#ef4444" : "var(--accent-purple)", fontWeight: 600 }}>
                              {displayJob.current_step || (activeJob ? `Project: ${activeJob.name}` : "Ready")}
                            </div>
                          ) : (
                            <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                              System online. Waiting for job input.
                            </span>
                          )}
                        </div>
                      </div>
                      {displayJob && (
                        <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                          {/* Resume button — shown when job is stopped or failed */}
                          {!runningJob && ["cancelled", "failed"].includes(displayJob.status) && (
                            <motion.button
                              whileHover={{ scale: 1.05 }}
                              onClick={async () => {
                                await fetch(`${API_BASE}/jobs/${displayJob.job_id}/continue`, { method: "POST" });
                                fetchJobs();
                              }}
                              style={{ padding: "6px 16px", borderRadius: 8, background: "rgba(34,197,94,0.12)", border: "1px solid rgba(34,197,94,0.4)", color: "#22c55e", fontWeight: 700, cursor: "pointer", fontSize: 13 }}
                            >
                              ▶ Resume
                            </motion.button>
                          )}
                          {/* Stop button — shown only while running */}
                          {runningJob && (
                            isCancelling ? (
                              <div style={{ padding: "6px 16px", borderRadius: 8, background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)", color: "#ef4444", fontWeight: 600, fontSize: 13, opacity: 0.7 }}>
                                ⏳ Stopping...
                              </div>
                            ) : (
                              <motion.button
                                whileHover={{ scale: 1.05 }}
                                onClick={async () => {
                                  await fetch(`${API_BASE}/jobs/${runningJob.job_id}/cancel`, { method: "POST" });
                                }}
                                style={{ padding: "6px 16px", borderRadius: 8, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", fontWeight: 600, cursor: "pointer" }}
                              >
                                🛑 Stop
                              </motion.button>
                            )
                          )}
                          <div style={{ textAlign: "right" }}>
                            {runningJob && (
                              <>
                                <span style={{ fontSize: 24, fontWeight: 800, color: "var(--accent-purple)" }}>{displayJob.progress_pct || 0}%</span>
                                <p style={{ fontSize: 11, color: "var(--text-secondary)" }}>GLOBAL PROGRESS</p>
                              </>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })()}

                {(() => {
                  // Priority: 
                  // 1. If an activeJob (from history) is explicitly selected, show it.
                  // 2. If there's a job currently running (not completed/failed), show it.
                  // 3. Otherwise, if we haven't selected anything, show the empty state.
                  
                  const runningJob = jobs.find(j => !["completed", "failed", "cancelled", "preview"].includes(j.status));
                  const displayJob = activeJob || runningJob;

                  if (!displayJob) {
                    return (
                      <div className="glass-card" style={{ padding: 48, textAlign: "center", borderStyle: "dashed" }}>
                        <p style={{ color: "var(--text-secondary)" }}>Ready for new production. Enter a topic in the sidebar to begin.</p>
                      </div>
                    );
                  }
                  
                  const currentStatus = displayJob.status || "pending";

                  return (
                    <>
                      <div className="glass-card" style={{ padding: "16px 24px" }}>
                        <div style={{ position: "relative" }}>
                          {/* Progress bar as the connector line */}
                          <div style={{ position: "absolute", top: 19, left: "10%", right: "10%", height: 2, background: "var(--border)", zIndex: 0 }} />
                          <div style={{ position: "absolute", top: 19, left: "10%", width: `calc(${displayJob.progress_pct || 0}% * 0.8)`, maxWidth: "80%", height: 2, background: "var(--accent-purple)", zIndex: 0, transition: "width 0.6s ease", boxShadow: "0 0 6px rgba(168,85,247,0.5)" }} />
                          <div style={{ display: "flex", justifyContent: "space-between", position: "relative" }}>
                            {["research", "script", "video", "tts", "merge"].map((step, idx) => {
                              const statusIdx = ["pending", "researching", "scripting", "rendering", "tts", "assembling", "completed"].indexOf(currentStatus);
                              const isDone = statusIdx >= 6
                                || (idx < statusIdx - 1)
                                || (idx === 0 && statusIdx > 1);
                              const isActive = currentStatus.includes(step)
                                || (step === "video" && currentStatus === "rendering")
                                || (step === "merge" && currentStatus === "assembling");
                              return (
                                <div key={step} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, zIndex: 1, flex: 1 }}>
                                  <div style={{
                                    width: 38, height: 38, borderRadius: "50%",
                                    background: isDone ? "var(--accent-green)" : isActive ? "var(--accent-purple)" : "var(--bg-secondary)",
                                    display: "flex", alignItems: "center", justifyContent: "center",
                                    border: isDone ? "2px solid var(--accent-green)" : isActive ? "2px solid var(--accent-purple)" : "2px solid var(--border)",
                                    boxShadow: isActive ? "0 0 16px rgba(168,85,247,0.4)" : isDone ? "0 0 8px rgba(34,197,94,0.3)" : "none",
                                    fontSize: isDone ? 14 : 13, fontWeight: 700,
                                    color: isDone || isActive ? "white" : "var(--text-secondary)",
                                    transition: "all 0.5s"
                                  }}>
                                    {isDone ? "✓" : idx + 1}
                                  </div>
                                  <span style={{ fontSize: 10, fontWeight: 600, color: isDone ? "var(--accent-green)" : isActive ? "white" : "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 0.5 }}>
                                    {step}
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                      
                      <motion.div 
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        className="glass-card" 
                        style={{ marginTop: 12, padding: 12, background: "rgba(0,0,0,0.3)", border: "1px solid rgba(168,85,247,0.2)" }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
                          <h4 style={{ fontSize: 13, fontWeight: 700, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: 1 }}>
                            📜 Live Execution Log
                          </h4>
                          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
                            {runningJob ? (
                              <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent-green)", animation: "pulse 1.5s infinite" }} />
                                <span style={{ fontSize: 10, color: "var(--accent-green)", fontWeight: 700 }}>LIVE</span>
                              </div>
                            ) : (
                              <span style={{ fontSize: 10, color: "var(--text-secondary)", opacity: 0.5 }}>
                                {displayJob.status?.toUpperCase()}
                              </span>
                            )}
                            <button
                              onClick={() => setLogCollapsed(c => !c)}
                              style={{ fontSize: 10, color: "var(--text-secondary)", background: "rgba(255,255,255,0.06)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: 4, padding: "2px 8px", cursor: "pointer" }}
                            >
                              {logCollapsed ? "▼ Xem thêm" : "▲ Thu gọn"}
                            </button>
                          </div>
                        </div>

                        {displayJob.status === "failed" && displayJob.error && (
                          <div style={{ marginBottom: 8, padding: "10px 12px", borderRadius: 8, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", fontSize: 12, fontWeight: 600 }}>
                            ❌ {displayJob.error}
                          </div>
                        )}
                        <div style={{ display: "flex", flexDirection: "column", gap: 6, ...(logCollapsed ? {} : { maxHeight: 240, overflowY: "auto" }), paddingRight: 8 }}>
                          {(displayJob.logs || []).length === 0 ? (
                            <p style={{ fontSize: 13, color: "var(--text-secondary)", fontStyle: "italic" }}>Initializing logging buffer...</p>
                          ) : (
                            [...(displayJob.logs || [])].reverse().slice(0, logCollapsed ? 3 : undefined).map((log: string, i: number, arr: string[]) => (
                              <motion.div 
                                initial={{ opacity: 0, x: -10 }}
                                animate={{ opacity: 1, x: 0 }}
                                key={i} 
                                style={{ 
                                  display: "flex", 
                                  gap: 8, 
                                  fontSize: 12, 
                                  color: i === 0 ? "white" : "var(--text-secondary)",
                                  borderLeft: `2px solid ${log.startsWith("📝") ? "var(--accent-purple)" : i === 0 ? "var(--accent-cyan)" : "var(--border)"}`,
                                  paddingLeft: 8,
                                  background: i === 0 ? "rgba(255,255,255,0.03)" : "transparent",
                                  padding: i === 0 ? "4px 8px" : "2px 8px",
                                  borderRadius: i === 0 ? 6 : 0
                                }}
                              >
                                <span style={{ opacity: 0.5, fontSize: 10, fontFamily: "monospace", marginTop: 2 }}>
                                  {arr.length - i}
                                </span>
                                <span style={{ 
                                  fontWeight: i === 0 ? 600 : 400,
                                  color: log.startsWith("📝") ? "var(--accent-purple)" : "inherit"
                                }}>
                                  {log}
                                </span>
                              </motion.div>
                            ))
                          )}
                        </div>
                      </motion.div>
                    </>
                  );
                })()}
              </section>


              {/* Scene Previews Section */}
              <section style={{ flex: 1 }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <h3 style={{ fontSize: 18, fontWeight: 700 }}>🎬 Shot List & Real-time Previews</h3>
                    {selectedScenes.size > 0 && (
                      <span style={{ fontSize: 12, padding: "3px 10px", borderRadius: 8, background: "rgba(234,179,8,0.15)", border: "1px solid rgba(234,179,8,0.4)", color: "var(--accent-gold)", fontWeight: 700 }}>
                        {selectedScenes.size === 1
                          ? `Scene #${[...selectedScenes][0] + 1} selected`
                          : `${selectedScenes.size} scenes selected`}
                      </span>
                    )}
                    {selectedScenes.size > 0 && (
                      <button onClick={() => setSelectedScenes(new Set())} style={{ fontSize: 10, padding: "2px 8px", borderRadius: 6, border: "1px solid rgba(255,255,255,0.15)", background: "transparent", color: "var(--text-secondary)", cursor: "pointer" }}>
                        Clear
                      </button>
                    )}
                  </div>
                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "flex-end" }}>
                    {/* Play All — sequential preview of all rendered clips */}
                    {(() => {
                      const displayProj = activeJob || projects[0];
                      const scenes = displayProj?.scripts?.[0]?.scenes ?? [];
                      const projName = displayProj?.name ?? displayProj?.project_dir?.split(/[\\/]/).pop() ?? "";
                      const hasAnyMedia = scenes.some((s: any) => s.video_path || s.clip_path || s.image_path);
                      if (!hasAnyMedia) return null;
                      return (
                        <motion.button
                          whileHover={{ scale: 1.05 }}
                          onClick={() => {
                            const firstIdx = scenes.findIndex((s: any) => s.video_path || s.clip_path || s.image_path);
                            if (firstIdx < 0) return;
                            const s = scenes[firstIdx];
                            const src = s.video_path || s.clip_path || s.image_path;
                            const filename = src.split(/[\\/]/).pop() ?? "";
                            const afn = s.audio_path ? (s.audio_path.split(/[\\/]/).pop() ?? "") : null;
                            setMediaPreview({
                              url: `http://localhost:8888/api/projects/${projName}/clip/${filename}`,
                              isVideo: /\.(mp4|webm|mov)$/i.test(filename),
                              projName,
                              allScenes: scenes,
                              idx: firstIdx,
                              audioUrl: afn ? `http://localhost:8888/api/projects/${projName}/audio/${afn}` : null,
                            });
                          }}
                          style={{ padding: "8px 16px", fontSize: 12, borderRadius: 10, border: "1px solid rgba(34,197,94,0.4)", background: "rgba(34,197,94,0.1)", color: "var(--accent-green)", fontWeight: 700, cursor: "pointer" }}
                        >
                          ▶ Play All Clips
                        </motion.button>
                      );
                    })()}

                    {/* Render selected scenes image */}
                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      onClick={async () => {
                        const job = activeJob || projects[0];
                        if (!job) return;
                        if (selectedScenes.size === 0) {
                          alert("Hãy tick chọn ít nhất một cảnh ở Shot List trước nhé!");
                          return;
                        }
                        setRenderingScenes(new Set(selectedScenes));
                        await Promise.all(
                          [...selectedScenes].map(i =>
                            fetch(`${API_BASE}/jobs/${job.job_id}/render-scene/${i}`, { method: "POST" })
                          )
                        );
                        setTimeout(() => setRenderingScenes(new Set()), 2000);
                      }}
                      style={{ padding: "8px 16px", fontSize: 12, borderRadius: 10, border: "1px solid rgba(234,179,8,0.3)", background: renderingScenes.size > 0 ? "rgba(234,179,8,0.2)" : "rgba(234,179,8,0.1)", color: "var(--accent-gold)", fontWeight: 700, cursor: "pointer" }}
                    >
                      {renderingScenes.size > 0
                        ? `⏳ Rendering ${renderingScenes.size} scene${renderingScenes.size > 1 ? "s" : ""}...`
                        : selectedScenes.size > 0
                          ? `🖼️ Render ${selectedScenes.size} scene${selectedScenes.size > 1 ? "s" : ""}`
                          : "🖼️ Render cảnh đã chọn"}
                    </motion.button>

                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      onClick={async (e) => {
                        const job = activeJob || projects[0];
                        if (!job) return;
                        const hasScripts = job.scripts && job.scripts.length > 0;
                        if (!hasScripts) {
                          alert("Chưa có script. Dùng nút \"▶ Continue Pipeline\" để chạy lại toàn bộ pipeline.");
                          return;
                        }
                        const btn = e.currentTarget;
                        const oldText = btn.innerText;
                        btn.innerText = "⏳ Processing...";
                        const res = await fetch(`${API_BASE}/jobs/${job.job_id}/rerun`, { method: "POST" });
                        if (!res.ok) {
                          const err = await res.json().catch(() => ({}));
                          alert(`Error: ${err.detail || res.statusText}`);
                        }
                        setTimeout(() => { btn.innerText = oldText; }, 1000);
                      }}
                      style={{ padding: "8px 16px", fontSize: 12, borderRadius: 10, border: "1px solid rgba(168,85,247,0.3)", background: "rgba(168,85,247,0.1)", color: "var(--accent-purple)", fontWeight: 700, cursor: "pointer" }}
                    >
                      🎬 Render lại toàn bộ
                    </motion.button>

                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      onClick={async (e) => {
                        const job = activeJob || projects[0];
                        if (!job) return;
                        const scenes = job.scripts?.[0]?.scenes ?? [];
                        if (scenes.length === 0) {
                          alert("Chưa có script.");
                          return;
                        }
                        const btn = e.currentTarget;
                        btn.setAttribute("disabled", "true");
                        // Render all scenes as video (skip ones that already have video)
                        const toRender = scenes
                          .map((_: any, i: number) => i)
                          .filter((i: number) => !scenes[i]?.video_path);
                        if (toRender.length > 0) {
                          btn.innerText = `⏳ Queueing ${toRender.length} clips...`;
                          await Promise.all(
                            toRender.map((i: number) =>
                              fetch(`${API_BASE}/jobs/${job.job_id}/render-video/${i}`, { method: "POST" })
                            )
                          );
                        }
                        // Trigger assembly
                        btn.innerText = "🔗 Ghép video...";
                        await fetch(`${API_BASE}/jobs/${job.job_id}/assemble`, { method: "POST" });
                        btn.innerText = "🎬 Render + Ghép video";
                        btn.removeAttribute("disabled");
                      }}
                      style={{ padding: "8px 16px", fontSize: 12, borderRadius: 10, border: "1px solid rgba(6,182,212,0.3)", background: "var(--accent-cyan)", color: "black", fontWeight: 800, cursor: "pointer", boxShadow: "0 0 15px rgba(6,182,212,0.3)" }}
                    >
                      🎬 Render + Ghép video
                    </motion.button>

                    <motion.button
                      whileHover={{ scale: 1.05 }}
                      onClick={async (e) => {
                        const job = activeJob || projects[0];
                        if (!job) return;
                        const btn = e.currentTarget;
                        btn.innerText = "⏳ Đang ghép...";
                        btn.setAttribute("disabled", "true");
                        const res = await fetch(`${API_BASE}/jobs/${job.job_id}/assemble`, { method: "POST" });
                        if (!res.ok) {
                          const err = await res.json().catch(() => ({}));
                          alert(`Lỗi: ${err.detail || res.statusText}`);
                        }
                        btn.innerText = "🔗 Ghép video";
                        btn.removeAttribute("disabled");
                      }}
                      style={{ padding: "8px 16px", fontSize: 12, borderRadius: 10, border: "1px solid rgba(34,197,94,0.4)", background: "rgba(34,197,94,0.1)", color: "var(--accent-green)", fontWeight: 700, cursor: "pointer" }}
                    >
                      🔗 Ghép video
                    </motion.button>
                  </div>
                </div>

                {/* Final Video — inline inside Shot List */}
                {(() => {
                  const displayProj = activeJob || projects[0];
                  const projName = displayProj?.name ?? displayProj?.project_dir?.split(/[\\/]/).pop() ?? "";
                  const showFinal = displayProj?.has_final
                    || displayProj?.status === "completed"
                    || displayProj?.current_step?.includes("Final video ready")
                    || displayProj?.current_step?.includes("Video ready");
                  if (!showFinal || !projName) return null;
                  const finalUrl = `${API_BASE}/projects/${projName}/final`;
                  return (
                    <motion.div
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      style={{ marginBottom: 24, borderRadius: 16, border: "1px solid rgba(6,182,212,0.4)", background: "linear-gradient(135deg, rgba(6,182,212,0.06), rgba(168,85,247,0.04))", overflow: "hidden", boxShadow: "0 0 24px rgba(6,182,212,0.1)" }}
                    >
                      <div style={{ padding: "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid rgba(6,182,212,0.2)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                          <span style={{ fontSize: 16 }}>🎬</span>
                          <span style={{ fontWeight: 800, fontSize: 14, color: "var(--accent-cyan)" }}>Final Video</span>
                          <span style={{ fontSize: 10, padding: "2px 8px", borderRadius: 10, background: "rgba(6,182,212,0.15)", border: "1px solid rgba(6,182,212,0.3)", color: "var(--accent-cyan)", fontWeight: 700 }}>READY</span>
                        </div>
                        <div style={{ display: "flex", gap: 8 }}>
                          <a href={finalUrl} download={`${projName}.mp4`} style={{ padding: "5px 12px", fontSize: 11, borderRadius: 8, border: "1px solid rgba(6,182,212,0.4)", background: "rgba(6,182,212,0.1)", color: "var(--accent-cyan)", fontWeight: 700, textDecoration: "none" }}>
                            ⬇ Download
                          </a>
                          <button
                            onClick={() => setShowPublisherConfig(projName)}
                            style={{ padding: "5px 12px", fontSize: 11, borderRadius: 8, border: "1px solid rgba(168,85,247,0.4)", background: "rgba(168,85,247,0.1)", color: "var(--accent-purple)", fontWeight: 700, cursor: "pointer" }}
                          >
                            🚀 Publish
                          </button>
                          <button
                            onClick={async () => { await fetch(`${API_BASE}/projects/${projName}/open-folder`, { method: "POST" }); }}
                            style={{ padding: "5px 12px", fontSize: 11, borderRadius: 8, border: "1px solid rgba(255,255,255,0.15)", background: "rgba(255,255,255,0.05)", color: "var(--text-secondary)", fontWeight: 700, cursor: "pointer" }}
                          >
                            📂 Open Folder
                          </button>
                        </div>
                      </div>
                      <video key={finalUrl} controls autoPlay={false} style={{ width: "100%", maxHeight: 400, background: "#000", display: "block" }}>
                        <source src={finalUrl} type="video/mp4" />
                      </video>
                    </motion.div>
                  );
                })()}

                {!(activeJob || projects[0])?.scripts?.[0]?.scenes?.length ? (
                  <div className="glass-card" style={{ padding: 100, textAlign: "center" }}>
                    <p style={{ fontSize: 64, marginBottom: 20 }}>🎞️</p>
                    <h4 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8 }}>No Clips Found</h4>
                    <p style={{ color: "var(--text-secondary)", maxWidth: 400, margin: "0 auto" }}>
                      Scripts and clips will appear here once you start a production.
                    </p>
                  </div>
                ) : (
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 24 }}>
                    {(activeJob || projects[0])?.scripts?.[0]?.scenes.map((scene: any, idx: number) => {
                      const isSelected = selectedScenes.has(idx);
                      const displayProj = activeJob || projects[0];
                      const projName = displayProj?.name ?? displayProj?.project_dir?.split(/[\\/]/).pop() ?? "";
                      const allScenes = displayProj?.scripts?.[0]?.scenes ?? [];
                      // Modal URL — video preferred for actual playback
                      const mediaSrc = scene.video_path || scene.clip_path || scene.image_path;
                      const mediaFilename = mediaSrc ? (mediaSrc.split(/[\\/]/).pop() ?? "") : "";
                      const mediaIsVideo = /\.(mp4|webm|mov)$/i.test(mediaFilename);
                      const mediaUrl = mediaSrc ? `http://localhost:8888/api/projects/${projName}/clip/${mediaFilename}` : "";
                      // Card thumbnail — image preferred (PNG shows first frame, avoids black video)
                      const thumbSrc = scene.clip_path || scene.image_path || scene.video_path;
                      const thumbFilename = thumbSrc ? (thumbSrc.split(/[\\/]/).pop() ?? "") : "";
                      const thumbIsVideo = !scene.clip_path && !scene.image_path && /\.(mp4|webm|mov)$/i.test(thumbFilename);
                      const thumbUrl = thumbSrc ? `http://localhost:8888/api/projects/${projName}/clip/${thumbFilename}` : "";
                      const audioFilename = scene.audio_path ? (scene.audio_path.split(/[\\/]/).pop() ?? "") : null;
                      const sceneAudioUrl = audioFilename ? `http://localhost:8888/api/projects/${projName}/audio/${audioFilename}` : null;

                      return (
                        <motion.div
                          key={idx}
                          className="glass-card"
                          whileHover={{ scale: 1.02 }}
                          onClick={() => toggleScene(idx)}
                          style={{
                            padding: 16,
                            position: "relative",
                            display: "flex",
                            flexDirection: "column",
                            border: isSelected ? "2px solid var(--accent-gold)" : "1px solid var(--border)",
                            background: isSelected ? "rgba(234,179,8,0.05)" : "rgba(255,255,255,0.02)",
                            boxShadow: isSelected ? "0 0 20px rgba(234,179,8,0.15)" : "none",
                            cursor: "pointer",
                          }}
                        >
                          {/* Checkbox — top-right corner, click to select/deselect */}
                          <div
                            onClick={(e) => { e.stopPropagation(); toggleScene(idx); }}
                            style={{
                              position: "absolute", top: 10, right: 10, zIndex: 10,
                              width: 22, height: 22, borderRadius: 6,
                              border: isSelected ? "2px solid var(--accent-gold)" : "2px solid rgba(255,255,255,0.3)",
                              background: isSelected ? "var(--accent-gold)" : "rgba(0,0,0,0.5)",
                              backdropFilter: "blur(4px)",
                              display: "flex", alignItems: "center", justifyContent: "center",
                              cursor: "pointer", transition: "all 0.15s",
                              boxShadow: isSelected ? "0 0 8px rgba(234,179,8,0.6)" : "none",
                            }}
                          >
                            {isSelected && (
                              <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                                <path d="M2 6.5L5.5 10L11 3" stroke="black" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                              </svg>
                            )}
                          </div>

                          {/* Media area — click to fullscreen preview */}
                          <div
                            onClick={(e) => {
                              e.stopPropagation();
                              if (mediaSrc) {
                                setMediaPreview({ url: mediaUrl, isVideo: mediaIsVideo, projName, allScenes, idx, audioUrl: sceneAudioUrl });
                              }
                            }}
                            style={{ position: "relative", aspectRatio: "9/16", background: "#000", borderRadius: 12, marginBottom: 16, overflow: "hidden", border: "1px solid var(--border)", cursor: mediaSrc ? "zoom-in" : "default" }}
                          >
                            {!thumbSrc ? (
                              <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12 }}>
                                <span style={{ fontSize: 32, opacity: 0.5 }}>🎬</span>
                                <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>NOT RENDERED</span>
                              </div>
                            ) : thumbIsVideo ? (
                              <>
                                <video src={thumbUrl} style={{ width: "100%", height: "100%", objectFit: "cover" }}
                                  muted preload="metadata" loop onMouseEnter={e => e.currentTarget.play()} onMouseLeave={e => { e.currentTarget.pause(); e.currentTarget.currentTime = 0; }} />
                                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", opacity: 0, transition: "opacity 0.2s" }}
                                  onMouseEnter={e => (e.currentTarget.style.opacity = "1")}
                                  onMouseLeave={e => (e.currentTarget.style.opacity = "0")}
                                >
                                  <div style={{ width: 48, height: 48, borderRadius: "50%", background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>▶</div>
                                </div>
                              </>
                            ) : (
                              <>
                                <img src={thumbUrl} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", opacity: 0, transition: "opacity 0.2s", background: "rgba(0,0,0,0.3)" }}
                                  onMouseEnter={e => (e.currentTarget.style.opacity = "1")}
                                  onMouseLeave={e => (e.currentTarget.style.opacity = "0")}
                                >
                                  <div style={{ width: 48, height: 48, borderRadius: "50%", background: "rgba(0,0,0,0.7)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20 }}>🔍</div>
                                </div>
                              </>
                            )}
                            <div style={{ position: "absolute", top: 12, left: 12 }}>
                              <span className="badge badge-pending" style={{ fontSize: 10, background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}>
                                SHOT #{scene.scene_number}
                              </span>
                            </div>
                          </div>
                          
                          <div style={{ flex: 1 }}>
                            <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 12, fontSize: 11 }}>
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                <span style={{ color: "var(--text-secondary)" }}>📝 Script</span>
                                <span style={{ color: "var(--accent-green)" }}>✓ Xong</span>
                              </div>
                              
                              {[
                                { label: "🎤 TTS Voice", ready: !!scene.audio_path, endpoint: `render-audio/${idx}`, color: "168,85,247" },
                                { label: "🖼️ Hình cảnh", ready: !!(scene.clip_path || scene.image_path), endpoint: `render-scene/${idx}`, color: "6,182,212" },
                                { label: "🎬 Video Clip", ready: !!scene.video_path, endpoint: `render-video/${idx}`, color: "234,179,8" },
                              ].map(({ label, ready, endpoint, color }) => (
                                <div key={endpoint} style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                  <span style={{ color: "var(--text-secondary)" }}>{label}</span>
                                  <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                    {ready ? (
                                      <span style={{ color: "var(--accent-green)" }}>✓ Xong</span>
                                    ) : (
                                      <>
                                        <span style={{ color: "var(--text-secondary)" }}>⏳ Missing</span>
                                        <button
                                          onClick={async (e) => {
                                            e.stopPropagation();
                                            const job = activeJob || projects[0];
                                            if (!job) return;
                                            const btn = e.currentTarget;
                                            btn.innerText = "⏳";
                                            btn.setAttribute("disabled", "true");
                                            try {
                                              const res = await fetch(`${API_BASE}/jobs/${job.job_id}/${endpoint}`, { method: "POST" });
                                              if (!res.ok) {
                                                const err = await res.json().catch(() => ({}));
                                                btn.innerText = "✗ Error";
                                                btn.style.color = "#ef4444";
                                                setTimeout(() => { btn.innerText = "Retry"; btn.style.color = ""; btn.removeAttribute("disabled"); }, 3000);
                                              } else {
                                                btn.innerText = "✓ Queued";
                                                setTimeout(() => { btn.innerText = "Retry"; btn.removeAttribute("disabled"); }, 2000);
                                              }
                                            } catch {
                                              btn.innerText = "✗ Error";
                                              setTimeout(() => { btn.innerText = "Retry"; btn.removeAttribute("disabled"); }, 3000);
                                            }
                                          }}
                                          style={{ padding: "2px 6px", fontSize: 10, borderRadius: 4, background: `rgba(${color},0.1)`, border: `1px solid rgba(${color},0.3)`, color: `rgb(${color})`, cursor: "pointer" }}
                                        >Retry</button>
                                      </>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                             
                            <div style={{ 
                              background: "rgba(0,0,0,0.2)", 
                              padding: 12, 
                              borderRadius: 8, 
                              fontSize: 12, 
                              color: "var(--text-primary)", 
                              lineHeight: 1.5,
                              minHeight: 64,
                              borderLeft: "2px solid var(--accent-purple)",
                              marginBottom: 16
                            }}>
                              {scene.narration_text}
                            </div>
                          </div>

                          <div style={{ display: "flex", gap: 8 }}>
                             <button 
                               onClick={(e) => { e.stopPropagation(); setEditingScene({proj: projName, scene}); }}
                               style={{ flex: 1, padding: "8px", fontSize: 12, borderRadius: 8, border: "1px solid var(--border)", background: "rgba(255,255,255,0.02)", color: "white", cursor: "pointer" }}
                             >
                               ✏️ Edit Script
                             </button>
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                )}
              </section>
            </>
          )}

          {activeTab === "projects" && (
            <section style={{ animation: "fadeIn 0.5s ease" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                   <h3 style={{ fontSize: 24, fontWeight: 800 }}>📂 Production History</h3>
                   <div style={{ display: "flex", gap: 12 }}>
                      <button 
                        className="btn-gradient" 
                        style={{ padding: "10px 20px" }} 
                        onClick={() => {
                          setActiveJob(null);
                          setTopic("");
                          setActiveTab("dashboard");
                          window.history.pushState(null, "", "/");
                        }}
                      >
                        ➕ New Project
                      </button>
                      <button 
                        style={{ padding: "10px 20px", borderRadius: 12, background: "rgba(255,255,255,0.05)", border: "1px solid var(--border)", color: "white", cursor: "pointer" }} 
                        onClick={() => fetchProjects()}
                      >
                        🔄 Refresh List
                      </button>
                   </div>
                </div>

               <div className="glass-card" style={{ overflow: "hidden" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", textAlign: "left" }}>
                    <thead>
                      <tr style={{ background: "rgba(255,255,255,0.02)", borderBottom: "1px solid var(--border)" }}>
                        <th style={{ padding: "16px 24px", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>PROJECT NAME</th>
                        <th style={{ padding: "16px 24px", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>STATUS</th>
                        <th style={{ padding: "16px 24px", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>ASSETS</th>
                        <th style={{ padding: "16px 24px", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>TIMESTAMP</th>
                        <th style={{ padding: "16px 24px", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)" }}>ACTIONS</th>
                      </tr>
                    </thead>
                    <tbody>
                      {projects.map((proj, idx) => (
                        <tr key={idx} style={{ borderBottom: "1px solid var(--border)", transition: "background 0.2s" }} onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.01)"} onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                          <td style={{ padding: "20px 24px" }}>
                             <div style={{ fontWeight: 700, fontSize: 14 }}>{proj.name}</div>
                             <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 4 }}>{proj.path}</div>
                          </td>
                          <td style={{ padding: "20px 24px" }}>
                             <span style={{ 
                               padding: "4px 12px", 
                               borderRadius: 20, 
                               fontSize: 10, 
                               fontWeight: 800,
                               background: proj.has_final ? "rgba(34,197,94,0.15)" : "rgba(234,179,8,0.15)",
                               color: proj.has_final ? "var(--accent-green)" : "var(--accent-gold)",
                               border: `1px solid ${proj.has_final ? "rgba(34,197,94,0.3)" : "rgba(234,179,8,0.3)"}`
                             }}>
                               {proj.has_final ? "COMPLETED" : "IN PROGRESS"}
                             </span>
                          </td>
                          <td style={{ padding: "20px 24px" }}>
                             <div style={{ fontSize: 13 }}>🎬 {proj.clips_count} Clips</div>
                             {proj.has_final && <div style={{ fontSize: 11, color: "var(--accent-cyan)", marginTop: 4 }}>✓ Master Video Ready</div>}
                          </td>
                          <td style={{ padding: "20px 24px", fontSize: 12, color: "var(--text-secondary)" }}>
                             {proj.created_at ? new Date(proj.created_at).toLocaleString() : proj.name.split("_").slice(-2).join(" ")}
                          </td>
                          <td style={{ padding: "20px 24px" }}>
                             <div style={{ display: "flex", gap: 8 }}>
                                <button className="btn-gradient" style={{ padding: "6px 12px", fontSize: 11 }} onClick={() => loadProject(proj.name)}>Manage</button>
                                <button 
                                   style={{ padding: "6px 12px", fontSize: 11, borderRadius: 8, border: "1px solid rgba(239,68,68,0.3)", background: "rgba(239,68,68,0.1)", color: "#ef4444", cursor: "pointer" }}
                                   onClick={async (e) => {
                                      if (window.confirm(`Delete project "${proj.name}"?`)) {
                                         const res = await fetch(`${API_BASE}/projects/${proj.name}`, { method: "DELETE" });
                                         if (res.ok) fetchProjects();
                                      }
                                   }}
                                 >Delete</button>
                             </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
               </div>
            </section>
          )}

          {activeTab === "settings" && settings && (
            <section style={{ animation: "fadeIn 0.5s ease", display: "flex", flexDirection: "column", gap: 32 }}>
               <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <h3 style={{ fontSize: 28, fontWeight: 800 }}>⚙️ Factory Settings</h3>
                  <div style={{ display: "flex", gap: 12 }}>
                     <span style={{ fontSize: 12, padding: "6px 12px", borderRadius: 20, background: "rgba(34,197,94,0.1)", color: "var(--accent-green)", border: "1px solid rgba(34,197,94,0.2)" }}>● SYSTEM ONLINE</span>
                  </div>
               </div>

               {/* Core Model Selection - MOVED TO TOP */}
               <div className="glass-card" style={{ padding: 24, border: "1px solid rgba(168,85,247,0.3)", background: "rgba(168,85,247,0.05)" }}>
                  <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "var(--accent-purple)" }}>🎭 Core Model Selection</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
                     <div>
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>TTS ENGINE</label>
                        <select
                          className="glow-input"
                          style={{ padding: 10, width: "100%", background: "var(--bg-secondary)" }}
                          value={settings.tts_engine}
                          onChange={(e) => updateSetting("tts_engine", e.target.value)}
                        >
                          {(settings.available_tts_engines ?? ["vieneu","edge-tts","piper","faster-qwen3-tts"]).map(e => (
                            <option key={e} value={e}>{e}</option>
                          ))}
                        </select>
                     </div>
                     <div>
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>TTS VOICE (edge-tts)</label>
                        <select
                          className="glow-input"
                          style={{ padding: 10, width: "100%", background: "var(--bg-secondary)" }}
                          value={settings.tts_voice}
                          onChange={(e) => updateSetting("tts_voice", e.target.value)}
                        >
                           <option value="vi-VN-HoaiMyNeural">vi-VN-HoaiMyNeural (Default)</option>
                           <option value="vi-VN-NamMinhNeural">vi-VN-NamMinhNeural (Male)</option>
                           <option value="default">default</option>
                        </select>
                     </div>
                  </div>
               </div>

               {/* ── Image Quality & Style ───────────────────────────────── */}
               <div className="glass-card" style={{ padding: 24, marginBottom: 0 }}>
                  <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "var(--accent-cyan)" }}>🎨 Image Quality & Style</h4>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                     {/* Style preset */}
                     <div style={{ gridColumn: "1 / -1" }}>
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 8 }}>IMAGE STYLE</label>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                           {(settings.available_image_styles ?? ["cinematic","anime","watercolor","oil_painting","neon","photorealistic"]).map(s => (
                              <button key={s}
                                 onClick={() => updateSetting("image_style", s)}
                                 style={{ padding: "6px 14px", borderRadius: 20, border: `1px solid ${settings.image_style === s ? "var(--accent-cyan)" : "rgba(255,255,255,0.15)"}`, background: settings.image_style === s ? "rgba(6,182,212,0.15)" : "rgba(255,255,255,0.03)", color: settings.image_style === s ? "var(--accent-cyan)" : "var(--text-secondary)", fontWeight: settings.image_style === s ? 700 : 400, cursor: "pointer", fontSize: 12, transition: "all 0.15s" }}>
                                 {s.replace("_", " ")}
                              </button>
                           ))}
                        </div>
                     </div>
                     {/* Steps */}
                     <div>
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                           STEPS <span style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>{settings.draw_things_steps ?? 20}</span>
                           <span style={{ opacity: 0.5 }}> (10–50, more = quality)</span>
                        </label>
                        <input type="range" min={10} max={50} step={5}
                           value={settings.draw_things_steps ?? 20}
                           onChange={e => updateSetting("draw_things_steps", e.target.value)}
                           style={{ width: "100%", accentColor: "var(--accent-cyan)" }}
                        />
                     </div>
                     {/* CFG */}
                     <div>
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                           CFG SCALE <span style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>{settings.draw_things_cfg ?? 5.0}</span>
                           <span style={{ opacity: 0.5 }}> (1–12, higher = strict)</span>
                        </label>
                        <input type="range" min={1} max={12} step={0.5}
                           value={settings.draw_things_cfg ?? 5.0}
                           onChange={e => updateSetting("draw_things_cfg", e.target.value)}
                           style={{ width: "100%", accentColor: "var(--accent-cyan)" }}
                        />
                     </div>
                     {/* Transition */}
                     <div style={{ gridColumn: "1 / -1" }}>
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>TRANSITION STYLE</label>
                        <select className="glow-input" style={{ padding: 10, width: "100%", background: "var(--bg-secondary)" }}
                           value={settings.transition_style ?? "auto"}
                           onChange={e => updateSetting("transition_style", e.target.value)}>
                           {(settings.available_transitions ?? ["auto","fade","slideleft","slideright","slideup","wipeleft","wiperight","dissolve","pixelize","radial"]).map(t => (
                              <option key={t} value={t}>{t === "auto" ? "auto (random per scene)" : t}</option>
                           ))}
                        </select>
                     </div>
                     {/* Ken Burns */}
                     <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 14px", borderRadius: 10, background: "rgba(255,255,255,0.03)", border: "1px solid var(--border)" }}>
                        <div>
                           <div style={{ fontSize: 13, fontWeight: 700 }}>🎥 Ken Burns Effect</div>
                           <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>Zoom-pan animation on still images</div>
                        </div>
                        <button onClick={() => updateSetting("ken_burns", (!settings.ken_burns).toString())}
                           style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: settings.ken_burns ? "var(--accent-cyan)" : "var(--bg-secondary)", color: settings.ken_burns ? "#000" : "var(--text-secondary)", fontWeight: 700, cursor: "pointer", fontSize: 12, transition: "all 0.15s" }}>
                           {settings.ken_burns ? "ON" : "OFF"}
                        </button>
                     </div>
                     {/* Color Grade */}
                     <div>
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 8 }}>COLOR GRADE</label>
                        <div style={{ display: "flex", gap: 7, flexWrap: "wrap" }}>
                           {(settings.available_color_grades ?? ["none","warm","cool","noir","vibrant","muted","golden"]).map(g => {
                              const colors: Record<string,string> = { none:"rgba(255,255,255,0.3)", warm:"#F59E0B", cool:"#38BDF8", noir:"#6B7280", vibrant:"#A855F7", muted:"#94A3B8", golden:"#EAB308" };
                              const active = (settings.color_grade ?? "none") === g;
                              return (
                                 <button key={g} onClick={() => updateSetting("color_grade", g)}
                                    style={{ padding: "5px 12px", borderRadius: 16, border: `1px solid ${active ? colors[g] : "rgba(255,255,255,0.1)"}`, background: active ? `${colors[g]}22` : "rgba(255,255,255,0.02)", color: active ? colors[g] : "var(--text-secondary)", fontWeight: active ? 700 : 400, cursor: "pointer", fontSize: 11, transition: "all 0.15s" }}>
                                    {g}
                                 </button>
                              );
                           })}
                        </div>
                     </div>
                  </div>
               </div>

               {/* Visual Consistency */}
               <div className="glass-card" style={{ padding: 24 }}>
                 <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "var(--accent-green, #4ade80)" }}>🔬 Visual Consistency (Phase 5)</h4>
                 <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                   {/* Upscale */}
                   <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                     <div>
                       <div style={{ fontSize: 13, fontWeight: 700 }}>⬆️ PNG Upscale</div>
                       <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>Upscale 768×1344 → 1080×1920 (Real-ESRGAN if available, else PIL Lanczos)</div>
                     </div>
                     <button onClick={() => updateSetting("enable_upscale", (!settings.enable_upscale).toString())}
                       style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: settings.enable_upscale ? "#4ade80" : "var(--bg-secondary)", color: settings.enable_upscale ? "#000" : "var(--text-secondary)", fontWeight: 700, cursor: "pointer", fontSize: 12, transition: "all 0.15s", flexShrink: 0 }}>
                       {settings.enable_upscale ? "ON" : "OFF"}
                     </button>
                   </div>
                   {/* img2img reference */}
                   <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                     <div>
                       <div style={{ fontSize: 13, fontWeight: 700 }}>🔗 img2img Scene Reference</div>
                       <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>Use Scene N-1 image as reference for Scene N — reduces style drift between scenes</div>
                     </div>
                     <button onClick={() => updateSetting("use_img2img_ref", (!settings.use_img2img_ref).toString())}
                       style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: settings.use_img2img_ref ? "#4ade80" : "var(--bg-secondary)", color: settings.use_img2img_ref ? "#000" : "var(--text-secondary)", fontWeight: 700, cursor: "pointer", fontSize: 12, transition: "all 0.15s", flexShrink: 0 }}>
                       {settings.use_img2img_ref ? "ON" : "OFF"}
                     </button>
                   </div>
                   {settings.use_img2img_ref && (
                     <div>
                       <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                         DENOISING STRENGTH <span style={{ color: "#4ade80", fontWeight: 700 }}>{(settings.img2img_denoising ?? 0.35).toFixed(2)}</span>
                         <span style={{ color: "var(--text-secondary)", marginLeft: 8 }}>(0.2 = very similar, 0.6 = more creative)</span>
                       </label>
                       <input type="range" min={0.1} max={0.7} step={0.05} value={settings.img2img_denoising ?? 0.35}
                         onChange={e => updateSetting("img2img_denoising", e.target.value)}
                         style={{ width: "100%", accentColor: "#4ade80" }} />
                     </div>
                   )}
                 </div>
               </div>

               {/* Text-to-Video (Phase 6) */}
               <div className="glass-card" style={{ padding: 24 }}>
                 <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "#f59e0b" }}>🎥 Text-to-Video Engine (Phase 6)</h4>
                 <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                   {/* Engine selector */}
                   <div>
                     <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 8 }}>T2V ENGINE</label>
                     <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                       {(settings.available_t2v_engines ?? ["none", "comfyui_wan", "replicate"]).map((eng: string) => {
                         const active = (settings.t2v_engine ?? "none") === eng;
                         const labels: Record<string, string> = { none: "Off (AnimateDiff)", comfyui_wan: "ComfyUI Wan2.1", replicate: "Replicate Cloud" };
                         return (
                           <button key={eng} onClick={() => updateSetting("t2v_engine", eng)}
                             style={{ padding: "7px 16px", borderRadius: 10, border: `1px solid ${active ? "#f59e0b" : "rgba(255,255,255,0.15)"}`, background: active ? "rgba(245,158,11,0.15)" : "rgba(255,255,255,0.03)", color: active ? "#f59e0b" : "var(--text-secondary)", fontWeight: active ? 700 : 400, cursor: "pointer", fontSize: 12 }}>
                             {labels[eng] ?? eng}
                           </button>
                         );
                       })}
                     </div>
                   </div>

                   {/* Replicate config */}
                   {settings.t2v_engine === "replicate" && (
                     <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: 14, borderRadius: 10, background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.15)" }}>
                       <div>
                         <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>REPLICATE API KEY</label>
                         <input type="password" className="glow-input" style={{ padding: 10 }} placeholder="r8_..."
                           value={settings.replicate_api_key ?? ""}
                           onChange={e => updateSetting("replicate_api_key", e.target.value)} />
                       </div>
                       <div>
                         <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>MODEL SLUG</label>
                         <input className="glow-input" style={{ padding: 10 }} placeholder="wan-ai/wan2.1-i2v-480p"
                           value={settings.replicate_t2v_model ?? "wan-ai/wan2.1-i2v-480p"}
                           onChange={e => updateSetting("replicate_t2v_model", e.target.value)} />
                       </div>
                     </div>
                   )}

                   {/* ComfyUI Wan2.1 config */}
                   {settings.t2v_engine === "comfyui_wan" && (
                     <div style={{ padding: 14, borderRadius: 10, background: "rgba(245,158,11,0.05)", border: "1px solid rgba(245,158,11,0.15)" }}>
                       <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>WAN MODEL FILENAME (in ComfyUI models/)</label>
                       <input className="glow-input" style={{ padding: 10 }} placeholder="Wan2_1-I2V-14B-480P_fp8_e4m3fn.safetensors"
                         value={settings.wan_model_name ?? ""}
                         onChange={e => updateSetting("wan_model_name", e.target.value)} />
                     </div>
                   )}

                   {/* Shared T2V params */}
                   {settings.t2v_engine !== "none" && (
                     <div style={{ display: "flex", gap: 16 }}>
                       <div style={{ flex: 1 }}>
                         <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                           FRAMES <span style={{ color: "#f59e0b", fontWeight: 700 }}>{settings.t2v_num_frames ?? 81}</span>
                           <span style={{ color: "var(--text-secondary)", marginLeft: 6 }}>({((settings.t2v_num_frames ?? 81) / (settings.t2v_fps ?? 16)).toFixed(1)}s @ {settings.t2v_fps ?? 16}fps)</span>
                         </label>
                         <input type="range" min={16} max={121} step={8} value={settings.t2v_num_frames ?? 81}
                           onChange={e => updateSetting("t2v_num_frames", e.target.value)}
                           style={{ width: "100%", accentColor: "#f59e0b" }} />
                       </div>
                       <div style={{ flex: 1 }}>
                         <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                           FPS <span style={{ color: "#f59e0b", fontWeight: 700 }}>{settings.t2v_fps ?? 16}</span>
                         </label>
                         <input type="range" min={8} max={30} step={2} value={settings.t2v_fps ?? 16}
                           onChange={e => updateSetting("t2v_fps", e.target.value)}
                           style={{ width: "100%", accentColor: "#f59e0b" }} />
                       </div>
                     </div>
                   )}
                 </div>
               </div>

               <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 32 }}>
                  {/* AI & Infrastructure */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                    <div className="glass-card" style={{ padding: 24 }}>
                       <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "var(--accent-purple)" }}>🤖 AI Engine Provisioning</h4>
                       <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                          <div style={{ padding: 16, borderRadius: 12, background: "rgba(168,85,247,0.05)", border: "1px solid rgba(168,85,247,0.1)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                             <div>
                                <div style={{ fontSize: 14, fontWeight: 700 }}>AI Mode</div>
                                <div style={{ fontSize: 11, color: "var(--text-secondary)" }}>Ollama (Local) vs Cloud API</div>
                             </div>
                             <button 
                               onClick={() => updateSetting("use_cloud_ai", (!settings.use_cloud_ai).toString())}
                               style={{ padding: "8px 20px", borderRadius: 8, border: "none", background: settings.use_cloud_ai ? "var(--accent-purple)" : "var(--bg-secondary)", color: "white", fontWeight: 700, cursor: "pointer" }}
                             >
                               {settings.use_cloud_ai ? "☁️ CLOUD" : "🏠 LOCAL"}
                             </button>
                          </div>

                          {settings.use_cloud_ai && (
                            <div style={{ display: "flex", flexDirection: "column", gap: 12, padding: 16, borderRadius: 12, background: "rgba(0,0,0,0.2)", border: "1px solid var(--border)" }}>
                               <div>
                                  <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>API KEY</label>
                                  <input type="password" placeholder="sk-..." className="glow-input" style={{ padding: 10 }} value={settings.openai_api_key} onChange={(e) => updateSetting("openai_api_key", e.target.value)} />
                               </div>
                               <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                                  <div>
                                     <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>MODEL</label>
                                     <input className="glow-input" style={{ padding: 10 }} value={settings.openai_model} onChange={(e) => updateSetting("openai_model", e.target.value)} />
                                  </div>
                                  <div>
                                     <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>ENDPOINT URL</label>
                                     <input className="glow-input" style={{ padding: 10 }} value={settings.openai_base_url} onChange={(e) => updateSetting("openai_base_url", e.target.value)} />
                                  </div>
                               </div>
                            </div>
                          )}
                       </div>
                    </div>

                    <div className="glass-card" style={{ padding: 24 }}>
                       <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "var(--accent-cyan)" }}>⚙️ Pipeline Infrastructure</h4>
                       <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>OLLAMA ENDPOINT</label>
                             <input className="glow-input" style={{ padding: 10 }} value={settings.ollama_base_url} onChange={(e) => updateSetting("ollama_base_url", e.target.value)} />
                          </div>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>OLLAMA MODEL NAME</label>
                             <input className="glow-input" style={{ padding: 10 }} placeholder="e.g. mistral, llama3, phi3" value={settings.ollama_model} onChange={(e) => updateSetting("ollama_model", e.target.value)} />
                          </div>
                          <div style={{ height: 1, background: "var(--border)", margin: "8px 0" }} />
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>COMFYUI (VIDEO NODE)</label>
                             <input className="glow-input" style={{ padding: 10 }} value={settings.comfyui_base_url} onChange={(e) => updateSetting("comfyui_base_url", e.target.value)} />
                          </div>
                       </div>
                    </div>
                  </div>

                  {/* Background Music + Publishers */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
                    {/* Background Music */}
                    <div className="glass-card" style={{ padding: 24 }}>
                      <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 16, color: "var(--accent-gold)" }}>🎵 Background Music</h4>
                      <BgMusicPanel settings={settings} updateSetting={updateSetting} apiBase={API_BASE} />
                    </div>

                    {/* Branding Overlay */}
                    <div className="glass-card" style={{ padding: 24 }}>
                      <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "var(--accent-cyan)" }}>🏷️ Branding Overlay</h4>
                      <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
                        {/* Watermark path */}
                        <div>
                          <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>WATERMARK / LOGO (PNG path)</label>
                          <input className="glow-input" style={{ padding: 10 }}
                            placeholder="e.g. /Users/you/logo.png — leave blank to disable"
                            value={settings.watermark_path ?? ""}
                            onChange={e => updateSetting("watermark_path", e.target.value)} />
                        </div>
                        {/* Position + opacity (only show when path set) */}
                        {settings.watermark_path && (
                          <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
                            <div style={{ flex: 1, minWidth: 160 }}>
                              <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>POSITION</label>
                              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                                {(settings.available_watermark_positions ?? ["topleft","topright","bottomleft","bottomright"]).map((pos: string) => {
                                  const active = (settings.watermark_position ?? "topright") === pos;
                                  return (
                                    <button key={pos} onClick={() => updateSetting("watermark_position", pos)}
                                      style={{ padding: "5px 12px", borderRadius: 8, border: `1px solid ${active ? "var(--accent-cyan)" : "rgba(255,255,255,0.15)"}`, background: active ? "rgba(6,182,212,0.15)" : "rgba(255,255,255,0.03)", color: active ? "var(--accent-cyan)" : "var(--text-secondary)", fontWeight: active ? 700 : 400, cursor: "pointer", fontSize: 11 }}>
                                      {pos}
                                    </button>
                                  );
                                })}
                              </div>
                            </div>
                            <div style={{ flex: 1, minWidth: 160 }}>
                              <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>
                                OPACITY <span style={{ color: "var(--accent-cyan)", fontWeight: 700 }}>{Math.round((settings.watermark_opacity ?? 0.7) * 100)}%</span>
                              </label>
                              <input type="range" min={0} max={1} step={0.05} value={settings.watermark_opacity ?? 0.7}
                                onChange={e => updateSetting("watermark_opacity", e.target.value)}
                                style={{ width: "100%", accentColor: "var(--accent-cyan)" }} />
                            </div>
                          </div>
                        )}
                        {/* Intro card */}
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 700 }}>🎬 Intro Title Card</div>
                            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>Prepend 3-second title card before Scene 1</div>
                          </div>
                          <button onClick={() => updateSetting("enable_intro_card", (!settings.enable_intro_card).toString())}
                            style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: settings.enable_intro_card ? "var(--accent-cyan)" : "var(--bg-secondary)", color: settings.enable_intro_card ? "#000" : "var(--text-secondary)", fontWeight: 700, cursor: "pointer", fontSize: 12, transition: "all 0.15s" }}>
                            {settings.enable_intro_card ? "ON" : "OFF"}
                          </button>
                        </div>
                        {/* Outro card */}
                        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                          <div>
                            <div style={{ fontSize: 13, fontWeight: 700 }}>🎯 Outro CTA Card</div>
                            <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 2 }}>Append 3-second call-to-action card</div>
                          </div>
                          <button onClick={() => updateSetting("enable_outro_card", (!settings.enable_outro_card).toString())}
                            style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: settings.enable_outro_card ? "var(--accent-cyan)" : "var(--bg-secondary)", color: settings.enable_outro_card ? "#000" : "var(--text-secondary)", fontWeight: 700, cursor: "pointer", fontSize: 12, transition: "all 0.15s" }}>
                            {settings.enable_outro_card ? "ON" : "OFF"}
                          </button>
                        </div>
                        {settings.enable_outro_card && (
                          <div>
                            <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>OUTRO TEXT</label>
                            <input className="glow-input" style={{ padding: 10 }}
                              value={settings.outro_card_text ?? "Like · Share · Follow!"}
                              onChange={e => updateSetting("outro_card_text", e.target.value)} />
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="glass-card" style={{ padding: 24 }}>
                       <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "#FF0000" }}>🎬 YouTube Shorts Configuration</h4>
                       <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>CLIENT ID</label>
                             <input className="glow-input" style={{ padding: 10 }} value={settings?.social?.youtube?.client_id || ""} onChange={(e) => updateSetting("youtube_client_id", e.target.value)} />
                          </div>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>CLIENT SECRET</label>
                             <input type="password" placeholder="OAuth client secret" className="glow-input" style={{ padding: 10 }} value={settings?.social?.youtube?.client_secret || ""} onChange={(e) => updateSetting("youtube_client_secret", e.target.value)} />
                          </div>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>REFRESH TOKEN</label>
                             <input type="password" placeholder="OAuth refresh token" className="glow-input" style={{ padding: 10 }} value={settings?.social?.youtube?.refresh_token || ""} onChange={(e) => updateSetting("youtube_refresh_token", e.target.value)} />
                          </div>
                       </div>
                    </div>

                    <div className="glass-card" style={{ padding: 24 }}>
                       <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "#000000" }}>📱 TikTok Configuration</h4>
                       <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>SESSION ID (COOKIE)</label>
                             <input type="password" placeholder="session_id from browser" className="glow-input" style={{ padding: 10 }} value={settings?.social?.tiktok?.session_id || ""} onChange={(e) => updateSetting("tiktok_session_id", e.target.value)} />
                          </div>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>ACCESS TOKEN (API)</label>
                             <input type="password" placeholder="Official API Token" className="glow-input" style={{ padding: 10 }} value={settings?.social?.tiktok?.access_token || ""} onChange={(e) => updateSetting("tiktok_access_token", e.target.value)} />
                          </div>
                       </div>
                    </div>

                    <div className="glass-card" style={{ padding: 24 }}>
                       <h4 style={{ fontSize: 16, fontWeight: 700, marginBottom: 20, color: "#1877F2" }}>💙 Facebook Reels Configuration</h4>
                       <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>PAGE ID</label>
                             <input placeholder="Enter Fanpage ID" className="glow-input" style={{ padding: 10 }} value={settings?.social?.facebook?.page_id || ""} onChange={(e) => updateSetting("facebook_page_id", e.target.value)} />
                          </div>
                          <div>
                             <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>PAGE ACCESS TOKEN (PAT)</label>
                             <input type="password" placeholder="Graph API Token" className="glow-input" style={{ padding: 10 }} value={settings?.social?.facebook?.access_token || ""} onChange={(e) => updateSetting("facebook_access_token", e.target.value)} />
                          </div>
                       </div>
                    </div>
                  </div>
               </div>
            </section>
          )}
        </div>
      </main>

      {/* Media Preview Modal — fullscreen clip viewer with sequential playback */}
      <AnimatePresence>
        {mediaPreview && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setMediaPreview(null)}
            style={{ position: "fixed", inset: 0, zIndex: 200, background: "rgba(0,0,0,0.97)", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 16 }}
          >
            {/* Media */}
            <div onClick={e => e.stopPropagation()} style={{ position: "relative", maxHeight: "80vh", maxWidth: "min(480px, 90vw)" }}>
              {/* Audio track — plays TTS alongside video or image */}
              {mediaPreview.audioUrl && (
                <audio
                  key={mediaPreview.audioUrl}
                  src={mediaPreview.audioUrl}
                  autoPlay
                  style={{ display: "none" }}
                  onEnded={() => {
                    for (let i = mediaPreview.idx + 1; i < mediaPreview.allScenes.length; i++) {
                      const next = mediaPreview.allScenes[i];
                      const src = next.video_path || next.clip_path || next.image_path;
                      if (src) {
                        const fn = src.split(/[\\/]/).pop() ?? "";
                        const afn = next.audio_path ? (next.audio_path.split(/[\\/]/).pop() ?? "") : null;
                        setMediaPreview({ ...mediaPreview, url: `http://localhost:8888/api/projects/${mediaPreview.projName}/clip/${fn}`, isVideo: /\.(mp4|webm|mov)$/i.test(fn), idx: i, audioUrl: afn ? `http://localhost:8888/api/projects/${mediaPreview.projName}/audio/${afn}` : null });
                        return;
                      }
                    }
                  }}
                />
              )}
              {mediaPreview.isVideo ? (
                <video
                  key={mediaPreview.url}
                  src={mediaPreview.url}
                  autoPlay
                  controls
                  muted={!!mediaPreview.audioUrl}
                  style={{ maxHeight: "80vh", maxWidth: "min(480px, 90vw)", borderRadius: 12, display: "block" }}
                  onEnded={!mediaPreview.audioUrl ? () => {
                    for (let i = mediaPreview.idx + 1; i < mediaPreview.allScenes.length; i++) {
                      const next = mediaPreview.allScenes[i];
                      const src = next.video_path || next.clip_path || next.image_path;
                      if (src) {
                        const fn = src.split(/[\\/]/).pop() ?? "";
                        setMediaPreview({ ...mediaPreview, url: `http://localhost:8888/api/projects/${mediaPreview.projName}/clip/${fn}`, isVideo: /\.(mp4|webm|mov)$/i.test(fn), idx: i, audioUrl: null });
                        return;
                      }
                    }
                  } : undefined}
                />
              ) : (
                <img key={mediaPreview.url} src={mediaPreview.url} style={{ maxHeight: "80vh", maxWidth: "min(480px, 90vw)", borderRadius: 12, display: "block", objectFit: "contain" }} />
              )}
            </div>

            {/* Navigation controls */}
            <div onClick={e => e.stopPropagation()} style={{ display: "flex", alignItems: "center", gap: 20 }}>
              <button
                disabled={mediaPreview.idx === 0}
                onClick={() => {
                  for (let i = mediaPreview.idx - 1; i >= 0; i--) {
                    const prev = mediaPreview.allScenes[i];
                    const src = prev.video_path || prev.clip_path || prev.image_path;
                    if (src) {
                      const fn = src.split(/[\\/]/).pop() ?? "";
                      const afn = prev.audio_path ? (prev.audio_path.split(/[\\/]/).pop() ?? "") : null;
                      setMediaPreview({ ...mediaPreview, url: `http://localhost:8888/api/projects/${mediaPreview.projName}/clip/${fn}`, isVideo: /\.(mp4|webm|mov)$/i.test(fn), idx: i, audioUrl: afn ? `http://localhost:8888/api/projects/${mediaPreview.projName}/audio/${afn}` : null });
                      return;
                    }
                  }
                }}
                style={{ padding: "8px 20px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.2)", background: "rgba(255,255,255,0.05)", color: "white", cursor: "pointer", fontSize: 14, opacity: mediaPreview.idx === 0 ? 0.3 : 1 }}
              >
                ◀ Prev
              </button>
              <span style={{ color: "white", fontSize: 13, fontWeight: 700, minWidth: 80, textAlign: "center" }}>
                Shot #{mediaPreview.allScenes[mediaPreview.idx]?.scene_number ?? mediaPreview.idx + 1}
                <br />
                <span style={{ fontSize: 10, opacity: 0.5 }}>({mediaPreview.idx + 1} / {mediaPreview.allScenes.length})</span>
              </span>
              <button
                disabled={mediaPreview.idx >= mediaPreview.allScenes.length - 1}
                onClick={() => {
                  for (let i = mediaPreview.idx + 1; i < mediaPreview.allScenes.length; i++) {
                    const next = mediaPreview.allScenes[i];
                    const src = next.video_path || next.clip_path || next.image_path;
                    if (src) {
                      const fn = src.split(/[\\/]/).pop() ?? "";
                      const afn = next.audio_path ? (next.audio_path.split(/[\\/]/).pop() ?? "") : null;
                      setMediaPreview({ ...mediaPreview, url: `http://localhost:8888/api/projects/${mediaPreview.projName}/clip/${fn}`, isVideo: /\.(mp4|webm|mov)$/i.test(fn), idx: i, audioUrl: afn ? `http://localhost:8888/api/projects/${mediaPreview.projName}/audio/${afn}` : null });
                      return;
                    }
                  }
                }}
                style={{ padding: "8px 20px", borderRadius: 8, border: "1px solid rgba(255,255,255,0.2)", background: "rgba(255,255,255,0.05)", color: "white", cursor: "pointer", fontSize: 14, opacity: mediaPreview.idx >= mediaPreview.allScenes.length - 1 ? 0.3 : 1 }}
              >
                Next ▶
              </button>
              <button
                onClick={() => setMediaPreview(null)}
                style={{ padding: "8px 16px", borderRadius: 8, border: "1px solid rgba(239,68,68,0.4)", background: "rgba(239,68,68,0.1)", color: "#ef4444", cursor: "pointer", fontSize: 13 }}
              >
                ✕ Close
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Edit Scene Modal */}
      <AnimatePresence>
        {editingScene && (
          <div style={{ position: "fixed", inset: 0, zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center" }}>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setEditingScene(null)} style={{ position: "absolute", inset: 0, background: "rgba(0,0,0,0.8)", backdropFilter: "blur(10px)" }} />
            <motion.div 
              initial={{ x: 300, opacity: 0 }} 
              animate={{ x: 0, opacity: 1 }} 
              exit={{ x: 300, opacity: 0 }}
              className="glass-card" 
              style={{ width: 600, padding: 32, position: "relative", zIndex: 101 }}
            >
              <h2 style={{ fontSize: 24, fontWeight: 800, marginBottom: 24 }}>Edit Shot #{editingScene.scene.scene_number}</h2>
              
              <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
                 <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 8 }}>NARRATION SCRIPT</label>
                    <textarea 
                      style={{ width: "100%", height: 120, padding: 16, borderRadius: 12, background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "white", fontSize: 14, resize: "none" }}
                      defaultValue={editingScene.scene.narration_text}
                    />
                 </div>
                 
                 <div>
                    <label style={{ display: "block", fontSize: 12, fontWeight: 700, color: "var(--text-secondary)", marginBottom: 8 }}>VISUAL PROMPT</label>
                    <input 
                      className="glow-input"
                      style={{ padding: 12, fontSize: 13 }}
                      defaultValue={editingScene.scene.visual_prompt}
                    />
                 </div>
              </div>

              <div style={{ display: "flex", gap: 12, marginTop: 32 }}>
                <button style={{ flex: 1, padding: 14, borderRadius: 12, background: "transparent", border: "1px solid var(--border)", color: "white" }} onClick={() => setEditingScene(null)}>
                  Cancel
                </button>
                <button className="btn-gradient" style={{ flex: 2, padding: 14 }} onClick={() => setEditingScene(null)}>
                  Save Changes
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ── Publish Modal ─────────────────────────────────────────────── */}
      <AnimatePresence>
        {showPublisherConfig && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            onClick={() => setShowPublisherConfig(null)}
            style={{ position: "fixed", inset: 0, zIndex: 300, background: "rgba(0,0,0,0.88)", display: "flex", alignItems: "center", justifyContent: "center" }}
          >
            <motion.div
              initial={{ scale: 0.92, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.92, opacity: 0 }}
              onClick={e => e.stopPropagation()}
              className="glass-card"
              style={{ width: 560, maxHeight: "92vh", overflowY: "auto", padding: 32, position: "relative" }}
            >
              {/* Header */}
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 28 }}>
                <div>
                  <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 2 }}>🚀 Publish Video</h2>
                  <p style={{ fontSize: 12, color: "var(--text-secondary)", margin: 0 }}>{showPublisherConfig}</p>
                </div>
                <button onClick={() => setShowPublisherConfig(null)} style={{ background: "rgba(255,255,255,0.08)", border: "1px solid var(--border)", color: "white", width: 32, height: 32, borderRadius: 8, cursor: "pointer", fontSize: 16, display: "flex", alignItems: "center", justifyContent: "center" }}>✕</button>
              </div>

              {/* Platform toggles */}
              <div style={{ marginBottom: 24 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", display: "block", marginBottom: 12, letterSpacing: 1 }}>PLATFORMS</label>
                <div style={{ display: "flex", gap: 10 }}>
                  {[
                    { id: "youtube", icon: "🎬", label: "YouTube Shorts", color: "#FF4444" },
                    { id: "tiktok",  icon: "🎵", label: "TikTok",         color: "#00F2EA" },
                    { id: "facebook",icon: "💙", label: "Facebook Reels", color: "#1877F2" },
                  ].map(p => {
                    const on = publishForm.platforms.includes(p.id);
                    return (
                      <button key={p.id}
                        onClick={() => setPublishForm(f => ({ ...f, platforms: on ? f.platforms.filter(x => x !== p.id) : [...f.platforms, p.id] }))}
                        style={{ flex: 1, padding: "12px 8px", borderRadius: 12, border: `2px solid ${on ? p.color : "rgba(255,255,255,0.1)"}`, background: on ? `${p.color}1a` : "rgba(255,255,255,0.02)", color: on ? p.color : "var(--text-secondary)", cursor: "pointer", transition: "all 0.15s", fontWeight: 700, fontSize: 11, display: "flex", flexDirection: "column", alignItems: "center", gap: 5 }}
                      >
                        <span style={{ fontSize: 22 }}>{p.icon}</span>
                        {p.label}
                        {on && <span style={{ fontSize: 9, opacity: 0.7 }}>✓ Selected</span>}
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Title */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", display: "block", marginBottom: 8, letterSpacing: 1 }}>TITLE</label>
                <input className="glow-input" style={{ padding: 12, fontSize: 13 }}
                  value={publishForm.title}
                  onChange={e => setPublishForm(f => ({ ...f, title: e.target.value }))}
                  placeholder={publishForm.generating ? "✨ AI đang tạo tiêu đề..." : "Tiêu đề video..."}
                  disabled={publishForm.generating}
                />
              </div>

              {/* Description */}
              <div style={{ marginBottom: 16 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", display: "block", marginBottom: 8, letterSpacing: 1 }}>DESCRIPTION</label>
                <textarea style={{ width: "100%", boxSizing: "border-box", height: 90, padding: 12, borderRadius: 12, background: "var(--bg-secondary)", border: "1px solid var(--border)", color: "white", fontSize: 13, resize: "none", fontFamily: "inherit", lineHeight: 1.6 }}
                  value={publishForm.description}
                  onChange={e => setPublishForm(f => ({ ...f, description: e.target.value }))}
                  placeholder={publishForm.generating ? "✨ AI đang tạo mô tả..." : "Mô tả video..."}
                  disabled={publishForm.generating}
                />
              </div>

              {/* Hashtags */}
              <div style={{ marginBottom: 24 }}>
                <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", display: "block", marginBottom: 8, letterSpacing: 1 }}>HASHTAGS <span style={{ fontWeight: 400, opacity: 0.6 }}>(click để xóa)</span></label>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 7, padding: "10px 12px", borderRadius: 12, background: "var(--bg-secondary)", border: "1px solid var(--border)", minHeight: 48, marginBottom: 8 }}>
                  {publishForm.generating
                    ? <span style={{ color: "var(--text-secondary)", fontSize: 12, lineHeight: "28px" }}>✨ Generating hashtags...</span>
                    : publishForm.hashtags.length === 0
                    ? <span style={{ color: "var(--text-secondary)", fontSize: 12, lineHeight: "28px", opacity: 0.5 }}>No hashtags yet</span>
                    : publishForm.hashtags.map((tag, i) => (
                        <span key={i} onClick={() => setPublishForm(f => ({ ...f, hashtags: f.hashtags.filter((_, j) => j !== i) }))}
                          style={{ padding: "3px 12px", borderRadius: 20, background: "rgba(168,85,247,0.15)", border: "1px solid rgba(168,85,247,0.35)", color: "var(--accent-purple)", fontSize: 12, fontWeight: 600, cursor: "pointer", userSelect: "none" }}>
                          #{tag}
                        </span>
                      ))
                  }
                </div>
                <input className="glow-input" style={{ padding: 9, fontSize: 12 }}
                  placeholder="Thêm hashtag → Enter"
                  onKeyDown={e => {
                    if (e.key !== "Enter") return;
                    const val = (e.target as HTMLInputElement).value.replace(/^#/, "").trim();
                    if (val) { setPublishForm(f => ({ ...f, hashtags: [...f.hashtags, val] })); (e.target as HTMLInputElement).value = ""; }
                  }}
                />
              </div>

              {/* Action buttons */}
              <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
                <button onClick={regenMetadata} disabled={publishForm.generating || publishForm.publishing}
                  style={{ flex: 1, padding: "11px 14px", borderRadius: 12, border: "1px solid rgba(168,85,247,0.4)", background: "rgba(168,85,247,0.1)", color: "var(--accent-purple)", fontWeight: 700, cursor: "pointer", fontSize: 12, opacity: publishForm.generating ? 0.5 : 1, transition: "opacity 0.15s" }}
                >
                  {publishForm.generating ? "⏳ Generating..." : "✨ Regenerate AI"}
                </button>
                <button onClick={publishVideo}
                  disabled={publishForm.publishing || publishForm.generating || publishForm.platforms.length === 0}
                  className="btn-gradient"
                  style={{ flex: 2, padding: "11px 14px", fontSize: 14, fontWeight: 800, opacity: (publishForm.publishing || publishForm.generating || publishForm.platforms.length === 0) ? 0.5 : 1, transition: "opacity 0.15s" }}
                >
                  {publishForm.publishing ? "📡 Publishing..." : `🚀 Publish to ${publishForm.platforms.length} Platform${publishForm.platforms.length !== 1 ? "s" : ""}`}
                </button>
              </div>

              {/* Results */}
              {publishForm.results && (
                <div style={{ borderTop: "1px solid var(--border)", paddingTop: 20 }}>
                  <label style={{ fontSize: 11, fontWeight: 700, color: "var(--text-secondary)", display: "block", marginBottom: 12, letterSpacing: 1 }}>PUBLISH RESULTS</label>
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {Object.entries(publishForm.results).map(([platform, res]: [string, any]) => (
                      <div key={platform} style={{ padding: "12px 16px", borderRadius: 10, background: res.status === "success" ? "rgba(34,197,94,0.07)" : "rgba(239,68,68,0.07)", border: `1px solid ${res.status === "success" ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}` }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <span style={{ fontWeight: 700, fontSize: 13 }}>{res.icon} {res.message}</span>
                          {res.url && <a href={res.url} target="_blank" rel="noreferrer" style={{ fontSize: 11, color: "var(--accent-cyan)", textDecoration: "none", fontWeight: 600 }}>View ↗</a>}
                        </div>
                        <div style={{ fontSize: 11, color: "var(--text-secondary)", marginTop: 5 }}>
                          ID: <code style={{ fontFamily: "monospace" }}>{res.video_id}</code> · {res.file_size_mb} MB
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
