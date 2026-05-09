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
  video_model: string;
  ollama_model: string;
  ollama_base_url: string;
  use_cloud_ai: boolean;
  openai_api_key: string;
  openai_base_url: string;
  openai_model: string;
  comfyui_base_url: string;
  scenes_per_video: number;
  available_tts_engines: string[];
  available_video_models: string[];
  social: {
    youtube: { client_id: string; client_secret: string; refresh_token: string; };
    tiktok: { access_token: string; session_id: string; };
    facebook: { access_token: string; page_id: string; };
  };
};

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
  const [activeSceneIdx, setActiveSceneIdx] = useState<number | null>(0);
  const [activeJob, setActiveJob] = useState<any>(null);

  // Fetch jobs periodically
  useEffect(() => {
    let initialProjectLoaded = false;
    
    async function init() {
      await fetchJobs();
      const projs = await fetchProjects();
      await fetchSettings();
      
      // Load project from URL if present
      if (!initialProjectLoaded && typeof window !== "undefined") {
        const searchParams = new URLSearchParams(window.location.search);
        let projectId = searchParams.get("project");
        if (!projectId && window.location.pathname.startsWith("/projects/")) {
          projectId = window.location.pathname.split("/")[2];
        }
        if (projectId && projs) {
          const found = projs.find((p: any) => p.name === projectId || p.job_id === projectId);
          if (found) {
            setActiveJob(found);
            setActiveTab("dashboard");
          }
        }
        initialProjectLoaded = true;
      }
    }
    
    init();
    
    const interval = setInterval(() => {
      fetchJobs();
      if (activeTab === "projects" || activeTab === "dashboard") fetchProjects();
    }, 3000);
    return () => clearInterval(interval);
  }, [activeTab]);

  async function fetchJobs() {
    try {
      const res = await fetch(`${API_BASE}/jobs/list`);
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
        // If there's a live job, it should always take precedence in the dashboard
        if (data.length > 0) {
          setActiveJob(data[0]);
        }
      }
    } catch {}
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
        body: JSON.stringify({ topic, auto_publish: false }),
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

  const statusColor: Record<string, string> = {
    pending: "badge-pending",
    researching: "badge-researching",
    scripting: "badge-scripting",
    rendering: "badge-rendering",
    tts: "badge-tts",
    assembling: "badge-assembling",
    preview: "badge-preview",
    completed: "badge-completed",
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
                      if (tab === "dashboard" && jobs.length === 0) {
                        setActiveJob(null);
                        window.history.pushState(null, "", "/");
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
                  const runningJob = jobs.find(j => j.status !== "completed" && j.status !== "failed" && j.status !== "cancelled");
                  const displayJob = activeJob || runningJob;
                  
                  return (
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20 }}>
                      <div>
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <h3 style={{ fontSize: 18, fontWeight: 700 }}>
                            {runningJob ? "Pipeline Execution" : activeJob ? "Project Preview" : "Factory Status"}
                          </h3>
                          {displayJob ? (
                            <div style={{ padding: "4px 12px", background: "rgba(168,85,247,0.1)", border: "1px solid rgba(168,85,247,0.3)", borderRadius: 12, fontSize: 12, color: "var(--accent-purple)", fontWeight: 600 }}>
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
                        <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                          {runningJob && (
                            <motion.button
                              whileHover={{ scale: 1.05 }}
                              onClick={async () => {
                                await fetch(`${API_BASE}/jobs/${runningJob.job_id}/cancel`, { method: "POST" });
                              }}
                              style={{ padding: "6px 16px", borderRadius: 8, background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", color: "#ef4444", fontWeight: 600, cursor: "pointer" }}
                            >
                              🛑 Stop
                            </motion.button>
                          )}
                          <div style={{ textAlign: "right" }}>
                            <span style={{ fontSize: 24, fontWeight: 800, color: "var(--accent-purple)" }}>{displayJob.progress_pct || 0}%</span>
                            <p style={{ fontSize: 11, color: "var(--text-secondary)" }}>{runningJob ? "GLOBAL PROGRESS" : "LOADED PROJECT"}</p>
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
                  
                  const runningJob = jobs.find(j => j.status !== "completed" && j.status !== "failed" && j.status !== "cancelled");
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
                      <div className="glass-card" style={{ padding: 24 }}>
                        <div style={{ display: "flex", justifyContent: "space-between", position: "relative", marginBottom: 12 }}>
                          {["research", "script", "video", "tts", "merge"].map((step, idx) => {
                            const statusIdx = ["pending", "researching", "scripting", "rendering", "tts", "assembling", "completed"].indexOf(currentStatus);
                            const isDone = idx < statusIdx - 1 || (idx === 0 && statusIdx > 1);
                            const isActive = currentStatus.includes(step) || (step === "video" && currentStatus === "rendering");
                            return (
                              <div key={step} style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, zIndex: 1, flex: 1 }}>
                                <div style={{ 
                                  width: 40, height: 40, borderRadius: "50%", 
                                  background: isDone ? "var(--accent-green)" : isActive ? "var(--accent-purple)" : "var(--bg-secondary)",
                                  display: "flex", alignItems: "center", justifyContent: "center",
                                  border: isActive ? "2px solid var(--accent-purple)" : "2px solid var(--border)",
                                  boxShadow: isActive ? "0 0 20px rgba(168,85,247,0.3)" : "none",
                                  transition: "all 0.5s"
                                }}>
                                  {isDone ? "✓" : idx + 1}
                                </div>
                                <span style={{ fontSize: 11, fontWeight: 600, color: isActive ? "white" : "var(--text-secondary)", textTransform: "uppercase" }}>
                                  {step}
                                </span>
                              </div>
                            );
                          })}
                          <div style={{ position: "absolute", top: 20, left: "10%", right: "10%", height: 2, background: "var(--border)", zIndex: 0 }} />
                        </div>
                        <div className="progress-track" style={{ height: 4 }}>
                          <div className="progress-fill" style={{ width: `${displayJob.progress_pct || 0}%` }} />
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
                          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                            <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--accent-green)", animation: "pulse 1.5s infinite" }} />
                            <span style={{ fontSize: 10, color: "var(--accent-green)", fontWeight: 700 }}>STREAMING...</span>
                          </div>
                        </div>
                        
                        <div style={{ display: "flex", flexDirection: "column", gap: 6, maxHeight: 150, overflowY: "auto", paddingRight: 8 }}>
                          {(displayJob.logs || []).length === 0 ? (
                            <p style={{ fontSize: 13, color: "var(--text-secondary)", fontStyle: "italic" }}>Initializing logging buffer...</p>
                          ) : (
                            [...(displayJob.logs || [])].reverse().map((log: string, i: number, arr: string[]) => (
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
                  <h3 style={{ fontSize: 18, fontWeight: 700 }}>🎬 Shot List & Real-time Previews</h3>
                  <div style={{ display: "flex", gap: 12 }}>
                    <motion.button 
                      whileHover={{ scale: 1.05 }}
                      onClick={() => {
                        const job = activeJob || projects[0];
                        if (job && activeSceneIdx !== null) {
                          fetch(`http://localhost:8888/api/jobs/${job.job_id}/render-scene/${activeSceneIdx}`, { method: "POST" });
                        }
                      }}
                      style={{ padding: "8px 16px", fontSize: 12, borderRadius: 10, border: "1px solid rgba(234,179,8,0.3)", background: "rgba(234,179,8,0.1)", color: "var(--accent-gold)", fontWeight: 700, cursor: "pointer" }}
                    >
                      🎬 Render cảnh đã chọn
                    </motion.button>
                    <motion.button 
                      whileHover={{ scale: 1.05 }}
                      onClick={async (e) => {
                        const job = activeJob || projects[0];
                        if (job) {
                          const btn = e.currentTarget;
                          const oldText = btn.innerText;
                          btn.innerText = "⏳ Processing...";
                          await fetch(`http://localhost:8888/api/jobs/${job.job_id}/rerun`, { method: "POST" });
                          setTimeout(() => { btn.innerText = oldText; }, 1000);
                        }
                      }}
                      style={{ padding: "8px 16px", fontSize: 12, borderRadius: 10, border: "1px solid rgba(168,85,247,0.3)", background: "rgba(168,85,247,0.1)", color: "var(--accent-purple)", fontWeight: 700, cursor: "pointer" }}
                    >
                      🎬 Render lại toàn bộ
                    </motion.button>
                    <motion.button 
                      whileHover={{ scale: 1.05 }}
                      onClick={() => {
                        const job = activeJob || projects[0];
                        if (job && activeSceneIdx !== null) {
                          fetch(`http://localhost:8888/api/jobs/${job.job_id}/render-video/${activeSceneIdx}`, { method: "POST" });
                        }
                      }}
                      style={{ padding: "8px 16px", fontSize: 12, borderRadius: 10, border: "1px solid rgba(6,182,212,0.3)", background: "var(--accent-cyan)", color: "black", fontWeight: 800, cursor: "pointer", boxShadow: "0 0 15px rgba(6,182,212,0.3)" }}
                    >
                      🎬 Render + Ghép video
                    </motion.button>
                  </div>
                </div>

                {projects.length === 0 ? (
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
                      const isSelected = activeSceneIdx === idx;
                      const projName = activeJob ? activeJob.project_dir.split(/[\\/]/).pop() : projects[0].name;
                      
                      return (
                        <motion.div
                          key={idx}
                          className="glass-card"
                          whileHover={{ scale: 1.02 }}
                          onClick={() => setActiveSceneIdx(idx)}
                          style={{ 
                            padding: 16, 
                            position: "relative", 
                            display: "flex", 
                            flexDirection: "column",
                            border: isSelected ? "2px solid var(--accent-gold)" : "1px solid var(--border)",
                            background: isSelected ? "rgba(234,179,8,0.05)" : "rgba(255,255,255,0.02)"
                          }}
                        >
                          <div style={{ position: "relative", aspectRatio: "16/9", background: "#000", borderRadius: 12, marginBottom: 16, overflow: "hidden", border: "1px solid var(--border)" }}>
                            {scene.video_path || scene.clip_path ? (
                              <video 
                                src={`http://localhost:8888/projects/${projName}/clips/${(scene.video_path || scene.clip_path).split(/[\\/]/).pop()}`} 
                                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                                muted loop onMouseEnter={e => e.currentTarget.play()} onMouseLeave={e => e.currentTarget.pause()}
                              />
                            ) : scene.image_path ? (
                              <img 
                                src={`http://localhost:8888/projects/${projName}/clips/${scene.image_path.split(/[\\/]/).pop()}`} 
                                style={{ width: "100%", height: "100%", objectFit: "cover" }}
                              />
                            ) : (
                              <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 12 }}>
                                 <span style={{ fontSize: 32, opacity: 0.5 }}>🎬</span>
                                 <span style={{ fontSize: 11, color: "var(--text-secondary)" }}>NOT RENDERED</span>
                              </div>
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
                              
                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                <span style={{ color: "var(--text-secondary)" }}>🎤 TTS Voice</span>
                                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                  {scene.audio_path ? (
                                    <span style={{ color: "var(--accent-green)" }}>✓ Ready</span>
                                  ) : (
                                    <>
                                      <span style={{ color: "var(--text-secondary)" }}>⏳ Missing</span>
                                      <button 
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          const job = activeJob || projects[0];
                                          if (job) fetch(`${API_BASE}/jobs/${job.job_id}/render-audio/${idx}`, { method: "POST" });
                                        }}
                                        style={{ padding: "2px 6px", fontSize: 10, borderRadius: 4, background: "rgba(168,85,247,0.1)", border: "1px solid rgba(168,85,247,0.3)", color: "var(--accent-purple)", cursor: "pointer" }}
                                      >Retry</button>
                                    </>
                                  )}
                                </div>
                              </div>

                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                <span style={{ color: "var(--text-secondary)" }}>🖼️ Hình cảnh</span>
                                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                  {scene.clip_path || scene.image_path ? (
                                    <span style={{ color: "var(--accent-green)" }}>✓ Ready</span>
                                  ) : (
                                    <>
                                      <span style={{ color: "var(--text-secondary)" }}>⏳ Missing</span>
                                      <button 
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          const job = activeJob || projects[0];
                                          if (job) fetch(`${API_BASE}/jobs/${job.job_id}/render-scene/${idx}`, { method: "POST" });
                                        }}
                                        style={{ padding: "2px 6px", fontSize: 10, borderRadius: 4, background: "rgba(6,182,212,0.1)", border: "1px solid rgba(6,182,212,0.3)", color: "var(--accent-cyan)", cursor: "pointer" }}
                                      >Retry</button>
                                    </>
                                  )}
                                </div>
                              </div>

                              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                                <span style={{ color: "var(--text-secondary)" }}>🎬 Video Clip</span>
                                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                                  {scene.video_path ? (
                                    <span style={{ color: "var(--accent-green)" }}>✓ Ready</span>
                                  ) : (
                                    <>
                                      <span style={{ color: "var(--text-secondary)" }}>⏳ Missing</span>
                                      <button 
                                        onClick={(e) => {
                                          e.stopPropagation();
                                          const job = activeJob || projects[0];
                                          if (job) fetch(`${API_BASE}/jobs/${job.job_id}/render-video/${idx}`, { method: "POST" });
                                        }}
                                        style={{ padding: "2px 6px", fontSize: 10, borderRadius: 4, background: "rgba(234,179,8,0.1)", border: "1px solid rgba(234,179,8,0.3)", color: "var(--accent-gold)", cursor: "pointer" }}
                                      >Retry</button>
                                    </>
                                  )}
                                </div>
                              </div>
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
                             {new Date().toLocaleDateString()}
                          </td>
                          <td style={{ padding: "20px 24px" }}>
                             <div style={{ display: "flex", gap: 8 }}>
                                <button className="btn-gradient" style={{ padding: "6px 12px", fontSize: 11 }} onClick={() => {
                                   setActiveJob(proj);
                                   setActiveTab("dashboard");
                                   window.history.pushState(null, "", `/projects/${proj.name}`);
                                }}>Manage</button>
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
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>VIDEO GENERATION MODEL</label>
                        <select 
                          className="glow-input" 
                          style={{ padding: 10, width: "100%", background: "var(--bg-secondary)" }} 
                          value={settings.video_model} 
                          onChange={(e) => updateSetting("video_model", e.target.value)}
                        >
                           <option value="svd_xt">SVD-XT (Fastest Animation)</option>
                           <option value="cogvideox">CogVideoX (Highest Quality)</option>
                           <option value="animatediff">AnimateDiff (Stylized)</option>
                        </select>
                     </div>
                     <div>
                        <label style={{ fontSize: 11, color: "var(--text-secondary)", display: "block", marginBottom: 6 }}>TTS VOICE CHARACTER</label>
                        <select 
                          className="glow-input" 
                          style={{ padding: 10, width: "100%", background: "var(--bg-secondary)" }} 
                          value={settings.tts_voice} 
                          onChange={(e) => updateSetting("tts_voice", e.target.value)}
                        >
                           <option value="default">Default Male</option>
                           <option value="female_1">Energetic Female</option>
                           <option value="narrator">Professional Narrator</option>
                           <option value="hoai_anh">Hoài Anh (Vietnamese)</option>
                        </select>
                     </div>
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

                  {/* Publishers */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
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
    </div>
  );
}
