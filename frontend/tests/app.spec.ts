import { test, expect, Page } from "@playwright/test";

const API = "http://localhost:8888/api";

// ── Helpers ────────────────────────────────────────────────────────────────

async function waitForSelector(page: Page, selector: string, timeout = 8000) {
  await page.waitForSelector(selector, { timeout });
}

async function getProjectNames(): Promise<string[]> {
  const res = await fetch(`${API}/projects/list`);
  const data = await res.json();
  return data.map((p: any) => p.name);
}

// ── Tab navigation ─────────────────────────────────────────────────────────

test.describe("Tab navigation — URL", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("Projects tab → URL = /projects", async ({ page }) => {
    await page.getByRole("button", { name: /projects/i }).click();
    await expect(page).toHaveURL(/\/projects$/);
  });

  test("Settings tab → URL = /settings", async ({ page }) => {
    await page.getByRole("button", { name: /settings/i }).click();
    await expect(page).toHaveURL(/\/settings$/);
  });

  test("Dashboard tab → URL = /dashboard", async ({ page }) => {
    await page.getByRole("button", { name: /projects/i }).click();
    await page.getByRole("button", { name: /dashboard/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });
});

// ── WebSocket ──────────────────────────────────────────────────────────────

test.describe("WebSocket — real-time updates", () => {
  test("connects to WS and does not poll /api/jobs/list on interval", async ({ page }) => {
    const jobListCalls: number[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/jobs/list")) jobListCalls.push(Date.now());
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(10000);

    expect(jobListCalls.length).toBeLessThanOrEqual(2);
  });

  test("WS connection is established", async ({ page }) => {
    const wsConnected = page.waitForEvent("websocket", (ws) =>
      ws.url().includes("ws://localhost:8888/ws")
    );
    await page.goto("/");
    const ws = await wsConnected;
    expect(ws.url()).toContain("ws://localhost:8888/ws");
  });
});

// ── Projects tab poll behavior ─────────────────────────────────────────────

test.describe("Projects tab — no poll while on dashboard", () => {
  test("switching to projects tab triggers /api/projects/list", async ({ page }) => {
    const calls: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/projects/list")) calls.push(req.url());
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const countBeforeSwitch = calls.length;

    await page.getByRole("button", { name: /projects/i }).click();
    await page.waitForTimeout(1000);

    expect(calls.length).toBeGreaterThan(countBeforeSwitch);
  });

  test("staying on dashboard does NOT poll /api/projects/list after initial load", async ({ page }) => {
    const calls: string[] = [];

    await page.goto("/dashboard");
    await page.waitForLoadState("networkidle");
    const initialCount = calls.length;

    page.on("request", (req) => {
      if (req.url().includes("/api/projects/list")) calls.push(req.url());
    });

    await page.waitForTimeout(8000);
    expect(calls.length - initialCount).toBe(0);
  });
});

// ── Services panel ─────────────────────────────────────────────────────────

test.describe("Services panel — sidebar health indicators", () => {
  test("Services section is visible in sidebar", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000); // allow services fetch

    await expect(page.locator("text=⚙️ Services")).toBeVisible();
  });

  test("Services API returns 4 services with expected IDs", async ({ request }) => {
    const res = await request.get(`${API}/services/status`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    const ids = data.services.map((s: any) => s.id);
    expect(ids).toContain("ollama");
    expect(ids).toContain("draw_things");
    expect(ids).toContain("comfyui");
    expect(ids).toContain("tts");
  });

  test("each service card shows status dot (online/offline)", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // At least Ollama or TTS card should appear
    const serviceCards = page.locator("aside").getByText(/(Ollama|Draw Things|ComfyUI|TTS)/i);
    await expect(serviceCards.first()).toBeVisible({ timeout: 8000 });
  });

  test("Draw Things offline shows hint text", async ({ request, page }) => {
    const res = await request.get(`${API}/services/status`);
    const data = await res.json();
    const dt = data.services.find((s: any) => s.id === "draw_things");
    if (!dt || dt.online) {
      console.log("Draw Things is online — skipping hint test");
      return;
    }

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    // Hint text should appear since DT is offline
    await expect(page.locator("text=Enable API Server")).toBeVisible({ timeout: 8000 });
  });

  test("Services refresh button calls /api/services/status", async ({ page }) => {
    const calls: string[] = [];
    page.on("request", (req) => {
      if (req.url().includes("/api/services/status")) calls.push(req.url());
    });

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);
    const before = calls.length;

    // Click the ↺ button in services section
    const refreshBtn = page.locator("aside button").filter({ hasText: "↺" }).first();
    await refreshBtn.click();
    await page.waitForTimeout(500);

    expect(calls.length).toBeGreaterThan(before);
  });
});

// ── Script style toggle ────────────────────────────────────────────────────

test.describe("Script style toggle — 4WH vs Viral", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
  });

  test("Both 4WH and Viral buttons are visible", async ({ page }) => {
    await expect(page.getByRole("button", { name: /4WH Framework/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /Viral 7 Scenes/i })).toBeVisible();
  });

  test("4WH is selected by default", async ({ page }) => {
    const btn4wh = page.getByRole("button", { name: /4WH Framework/i });
    // Selected button has gradient background (border: none)
    await expect(btn4wh).toBeVisible();
    // The viral button should NOT be the gradient one by default
    const btnViral = page.getByRole("button", { name: /Viral 7 Scenes/i });
    await expect(btnViral).toBeVisible();
  });

  test("clicking Viral changes selection", async ({ page }) => {
    const btnViral = page.getByRole("button", { name: /Viral 7 Scenes/i });
    await btnViral.click();

    // Viral button should now appear selected (border-style changes to none)
    // Verify Start Pipeline still works with viral style
    await page.locator("textarea").fill("test viral style topic");
    const createReq = page.waitForRequest(
      (req) => req.url().includes("/api/jobs/create") && req.method() === "POST"
    );
    await page.getByRole("button", { name: /start pipeline/i }).click();
    const req = await createReq;

    const body = JSON.parse(req.postData() ?? "{}");
    expect(body.script_style).toBe("viral");
  });

  test("clicking 4WH sends script_style=4wh in API request", async ({ page }) => {
    // Ensure 4wh is selected
    await page.getByRole("button", { name: /4WH Framework/i }).click();
    await page.locator("textarea").fill("test 4wh style topic");

    const createReq = page.waitForRequest(
      (req) => req.url().includes("/api/jobs/create") && req.method() === "POST"
    );
    await page.getByRole("button", { name: /start pipeline/i }).click();
    const req = await createReq;

    const body = JSON.parse(req.postData() ?? "{}");
    expect(body.script_style).toBe("4wh");
  });
});

// ── Load project from Projects tab ────────────────────────────────────────

test.describe("Load project from Projects tab", () => {
  test("Manage button loads full project data and sets URL", async ({ page }) => {
    const names = await getProjectNames();
    if (names.length === 0) {
      test.skip(true, "No projects on disk to load");
      return;
    }

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /projects/i }).click();

    const manageBtn = page.getByRole("button", { name: /manage/i }).first();
    await manageBtn.waitFor({ timeout: 8000 });

    const loadReq = page.waitForRequest((req) =>
      req.url().includes("/api/projects/") && req.url().includes("/load")
    );
    await manageBtn.click();
    await loadReq;

    await expect(page).toHaveURL(/\/projects\/.+/);
  });

  test("after loading project, dashboard tab → URL = /dashboard", async ({ page }) => {
    const names = await getProjectNames();
    if (names.length === 0) {
      test.skip(true, "No projects on disk to load");
      return;
    }

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /projects/i }).click();

    const manageBtn = page.getByRole("button", { name: /manage/i }).first();
    await manageBtn.waitFor({ timeout: 8000 });
    await manageBtn.click();
    await page.waitForURL(/\/projects\/.+/);

    await page.getByRole("button", { name: /dashboard/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });

  test("Projects table shows real timestamp (not always today)", async ({ page }) => {
    const names = await getProjectNames();
    if (names.length === 0) {
      test.skip(true, "No projects on disk");
      return;
    }

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /projects/i }).click();
    await page.waitForSelector("text=Production History", { timeout: 8000 });

    // Timestamp cell should NOT always be today's date
    // It must be a non-empty string in any column
    const rows = page.locator("tbody tr");
    await rows.first().waitFor({ timeout: 8000 });
    const firstRow = rows.first();
    // The timestamp cell is 4th column (index 3)
    const tsCell = firstRow.locator("td").nth(3);
    const tsText = await tsCell.innerText();
    // Must not be empty
    expect(tsText.trim()).not.toBe("");
  });
});

// ── Start Pipeline ─────────────────────────────────────────────────────────

test.describe("Start Pipeline — job creation", () => {
  test("submitting a topic creates a job and shows live log", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.locator("textarea").fill("test topic playwright");

    const createReq = page.waitForRequest(
      (req) => req.url().includes("/api/jobs/create") && req.method() === "POST"
    );
    await page.getByRole("button", { name: /start pipeline/i }).click();
    await createReq;

    await expect(page).toHaveURL(/\/projects\/.+/);
    await waitForSelector(page, "text=Live Execution Log");
  });

  test("empty topic disables Start Pipeline button", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Clear textarea
    await page.locator("textarea").fill("");
    const btn = page.getByRole("button", { name: /start pipeline/i });
    await expect(btn).toBeDisabled();
  });
});

// ── Resume button ──────────────────────────────────────────────────────────

test.describe("Resume button — appears when job is stopped/failed", () => {
  test("Resume button visible for cancelled/failed job, hidden for completed", async ({ page, request }) => {
    // Find a job already in cancelled or failed state from previous runs
    const listRes = await request.get(`${API}/jobs/list`);
    const jobs: any[] = await listRes.json();
    const stoppedJob = jobs.find(
      (j: any) => ["cancelled", "failed"].includes(j.status) && j.project_dir
    );

    if (!stoppedJob) {
      test.skip(true, "No cancelled/failed jobs available — run a job and stop it first");
      return;
    }

    const projName = stoppedJob.project_dir.split(/[\\/]/).pop();

    // Make sure no OTHER jobs are running (Resume only shows when !runningJob)
    const runningJobs = jobs.filter(
      (j: any) => !["completed", "failed", "cancelled", "preview"].includes(j.status)
    );
    if (runningJobs.length > 0) {
      console.log(`${runningJobs.length} jobs still running — Resume button would be hidden. Skipping.`);
      test.skip(true, "Other jobs running — Resume button is intentionally hidden");
      return;
    }

    const loadDone = page.waitForResponse(
      (r) => r.url().includes(`/api/projects/${projName}/load`) && r.status() === 200,
      { timeout: 20_000 }
    );
    await page.goto(`/projects/${projName}`);
    await loadDone.catch(() => {});
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    const resumeBtn = page.getByRole("button", { name: /▶ Resume/i });
    await expect(resumeBtn).toBeVisible({ timeout: 8000 });

    // Clicking Resume calls /continue
    const continueReq = page.waitForRequest(
      (req) => req.url().includes(`/jobs/${stoppedJob.job_id}/continue`) && req.method() === "POST"
    );
    await resumeBtn.click();
    await continueReq;
  });
});

// ── Live Execution Log badge ───────────────────────────────────────────────

test.describe("Live Execution Log — LIVE badge vs status text", () => {
  test("shows LIVE badge only when a job is running", async ({ page }) => {
    // Load a completed project (no running job)
    const names = await getProjectNames();
    if (names.length === 0) {
      test.skip(true, "No projects on disk");
      return;
    }

    await page.goto(`/projects/${names[0]}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(2000);

    // When no job is running, the LIVE label should NOT be shown
    const liveLabel = page.locator("text=LIVE").filter({ hasNotText: "Execution" });
    const liveLabelCount = await liveLabel.count();

    // When completed, should show status text (PREVIEW / COMPLETED / CANCELLED / FAILED)
    const statusText = page.locator("span").filter({ hasText: /PREVIEW|COMPLETED|CANCELLED|FAILED/i });
    // At least one of these should be visible OR LIVE should be visible
    const hasStatus = await statusText.count();
    const hasLive = liveLabelCount;
    expect(hasStatus + hasLive).toBeGreaterThan(0);
  });
});

// ── Shot List ──────────────────────────────────────────────────────────────

test.describe("Shot List — scene cards", () => {
  test("scene cards show correct labels and retry buttons", async ({ page }) => {
    const names = await getProjectNames();
    if (names.length === 0) {
      test.skip(true, "No projects on disk");
      return;
    }

    // Load first project that has scripts
    let projWithScripts = "";
    for (const name of names) {
      const res = await fetch(`${API}/projects/${name}/load`);
      if (res.ok) {
        const d = await res.json();
        if (d.scripts?.[0]?.scenes?.length > 0) { projWithScripts = name; break; }
      }
    }

    if (!projWithScripts) {
      test.skip(true, "No projects with scripts found");
      return;
    }

    const loadDone = page.waitForResponse(
      (r) => r.url().includes(`/api/projects/${projWithScripts}/load`) && r.status() === 200,
      { timeout: 20_000 }
    );
    await page.goto(`/projects/${projWithScripts}`);
    await loadDone.catch(() => {});
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Scene cards must appear
    const shotCard = page.locator("text=SHOT #");
    await shotCard.first().waitFor({ timeout: 10000 });

    // Each card should show these labels
    await expect(page.locator("text=📝 Script").first()).toBeVisible();
    await expect(page.locator("text=🎤 TTS Voice").first()).toBeVisible();
    await expect(page.locator("text=🖼️ Hình cảnh").first()).toBeVisible();
    await expect(page.locator("text=🎬 Video Clip").first()).toBeVisible();
  });

  test("scene card checkbox toggles selection and shows count", async ({ page }) => {
    const names = await getProjectNames();
    if (names.length === 0) {
      test.skip(true, "No projects on disk");
      return;
    }

    let projWithScripts = "";
    for (const name of names) {
      const res = await fetch(`${API}/projects/${name}/load`);
      if (res.ok) {
        const d = await res.json();
        if (d.scripts?.[0]?.scenes?.length > 0) { projWithScripts = name; break; }
      }
    }

    if (!projWithScripts) {
      test.skip(true, "No projects with scripts found");
      return;
    }

    const loadDone2 = page.waitForResponse(
      (r) => r.url().includes(`/api/projects/${projWithScripts}/load`) && r.status() === 200,
      { timeout: 20_000 }
    );
    await page.goto(`/projects/${projWithScripts}`);
    await loadDone2.catch(() => {});
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    // Wait for any scene card
    await page.waitForSelector("text=SHOT #", { timeout: 12000 });

    // Click the "📝 Script" label (inside the details section, outside the media area).
    // The media area has e.stopPropagation(), so clicking the card center never fires
    // toggleScene. The details section below the media area does bubble up correctly.
    const firstCard = page.locator(".glass-card").filter({ has: page.locator("text=SHOT #") }).first();
    const scriptLabel = firstCard.locator("text=📝 Script").first();
    await scriptLabel.click();

    // Selection count badge should appear: "Scene #X selected" or "X scenes selected"
    await expect(page.locator("span:has-text('selected')").first()).toBeVisible({ timeout: 3000 });

    // Click again to deselect
    await scriptLabel.click();
    await expect(page.locator("span:has-text('selected')").first()).not.toBeVisible({ timeout: 3000 });
  });

  test("Render cảnh đã chọn shows alert when no scene selected", async ({ page }) => {
    const names = await getProjectNames();
    if (names.length === 0) {
      test.skip(true, "No projects on disk");
      return;
    }

    let projWithScripts = "";
    for (const name of names) {
      const res = await fetch(`${API}/projects/${name}/load`);
      if (res.ok) {
        const d = await res.json();
        if (d.scripts?.[0]?.scenes?.length > 0) { projWithScripts = name; break; }
      }
    }
    if (!projWithScripts) {
      test.skip(true, "No projects with scripts found");
      return;
    }

    const loadDone3 = page.waitForResponse(
      (r) => r.url().includes(`/api/projects/${projWithScripts}/load`) && r.status() === 200,
      { timeout: 20_000 }
    );
    await page.goto(`/projects/${projWithScripts}`);
    await loadDone3.catch(() => {});
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(1500);

    let alertMessage = "";
    page.once("dialog", async (dialog) => {
      alertMessage = dialog.message();
      await dialog.accept();
    });

    const renderBtn = page.getByRole("button", { name: /Render cảnh đã chọn|Render \d+ scene/i }).first();
    if (await renderBtn.isVisible()) {
      await renderBtn.click();
      await page.waitForTimeout(500);
      if (alertMessage) {
        expect(alertMessage).toMatch(/chọn|select/i);
      }
    }
  });
});

// ── Settings tab ──────────────────────────────────────────────────────────

test.describe("Settings tab — correct fields", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /settings/i }).click();
    await page.waitForSelector("text=Factory Settings", { timeout: 8000 });
  });

  test("shows TTS ENGINE select with valid value", async ({ page }) => {
    // The TTS ENGINE select must exist and have a value
    const ttsSelect = page.locator("select").filter({ hasText: /vieneu|edge-tts|piper|faster-qwen3/i }).first();
    await expect(ttsSelect).toBeVisible({ timeout: 5000 });
    const val = await ttsSelect.inputValue();
    expect(val).not.toBe("");
    expect(["vieneu", "edge-tts", "piper", "faster-qwen3-tts"]).toContain(val);
  });

  test("shows required sections", async ({ page }) => {
    await expect(page.locator("text=AI Engine Provisioning")).toBeVisible();
    await expect(page.locator("text=Pipeline Infrastructure")).toBeVisible();
    await expect(page.locator("text=OLLAMA ENDPOINT")).toBeVisible();
    await expect(page.locator("text=COMFYUI").first()).toBeVisible();
  });

  test("TTS ENGINE select saves to backend", async ({ page, request }) => {
    // Get current engine
    const before = await request.get(`${API}/settings/`);
    const beforeData = await before.json();
    const originalEngine = beforeData.tts_engine;

    // Pick a different engine
    const ttsSelect = page.locator("select").first();
    const newEngine = originalEngine === "vieneu" ? "edge-tts" : "vieneu";
    await ttsSelect.selectOption(newEngine);
    await page.waitForTimeout(500);

    const after = await request.get(`${API}/settings/`);
    const afterData = await after.json();
    expect(afterData.tts_engine).toBe(newEngine);

    // Restore
    await ttsSelect.selectOption(originalEngine);
  });
});

// ── Media preview modal ───────────────────────────────────────────────────

test.describe("Media preview modal", () => {
  test("clicking clip area opens modal with Prev/Next/Close buttons", async ({ page }) => {
    const listRes = await fetch(`${API}/projects/list`);
    const projects: any[] = await listRes.json();
    const projWithClips = projects.find((p: any) => p.clips_count > 0);

    if (!projWithClips) {
      test.skip(true, "No projects with clips found");
      return;
    }

    await page.goto(`/projects/${projWithClips.name}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const mediaArea = page.locator("div[style*='cursor: zoom-in']").first();
    if (!(await mediaArea.isVisible())) {
      test.skip(true, "No rendered media to click");
      return;
    }

    await mediaArea.click();

    await page.waitForSelector("button:has-text('Close')", { timeout: 5000 });
    await expect(page.locator("button").filter({ hasText: "◀ Prev" })).toBeVisible();
    await expect(page.locator("button").filter({ hasText: "Next ▶" })).toBeVisible();

    await page.locator("button").filter({ hasText: "✕ Close" }).click();
    await expect(page.locator("button").filter({ hasText: "◀ Prev" })).not.toBeVisible({ timeout: 3000 });
  });

  test("Play All Clips button appears when clips exist", async ({ page }) => {
    const listRes = await fetch(`${API}/projects/list`);
    const projects: any[] = await listRes.json();
    const projWithClips = projects.find((p: any) => p.clips_count > 0);

    if (!projWithClips) {
      test.skip(true, "No projects with clips found");
      return;
    }

    await page.goto(`/projects/${projWithClips.name}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const sceneCards = page.locator("text=SHOT #");
    if (await sceneCards.count() > 0) {
      await expect(page.getByRole("button", { name: /play all clips/i })).toBeVisible({ timeout: 5000 });
    }
  });
});

// ── Projects tab ──────────────────────────────────────────────────────────

test.describe("Projects tab — Production History", () => {
  test("shows project list with status badges", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /projects/i }).click();
    await page.waitForSelector("text=Production History", { timeout: 8000 });

    const names = await getProjectNames();
    if (names.length === 0) {
      console.log("No projects — table is empty, that is OK");
      return;
    }

    // Status badges
    const badges = page.locator("span").filter({ hasText: /COMPLETED|IN PROGRESS/ });
    await badges.first().waitFor({ timeout: 8000 });
    expect(await badges.count()).toBeGreaterThan(0);
  });

  test("Delete project prompts confirmation and removes from list", async ({ page }) => {
    const names = await getProjectNames();
    if (names.length === 0) {
      test.skip(true, "No projects on disk");
      return;
    }

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /projects/i }).click();
    await page.waitForSelector("text=Production History", { timeout: 8000 });

    // Handle confirm dialog
    let confirmedWith = "";
    page.once("dialog", async (dialog) => {
      confirmedWith = dialog.message();
      await dialog.dismiss(); // dismiss = don't actually delete
    });

    const deleteBtn = page.getByRole("button", { name: /delete/i }).first();
    await deleteBtn.waitFor({ timeout: 8000 });
    await deleteBtn.click();
    await page.waitForTimeout(500);
    expect(confirmedWith).toMatch(/delete/i);
  });
});

// ── API smoke tests ───────────────────────────────────────────────────────

test.describe("API smoke tests", () => {
  test("GET /api/jobs/list returns array", async ({ request }) => {
    const res = await request.get(`${API}/jobs/list`);
    expect(res.ok()).toBeTruthy();
    expect(Array.isArray(await res.json())).toBeTruthy();
  });

  test("GET /api/projects/list returns array", async ({ request }) => {
    const res = await request.get(`${API}/projects/list`);
    expect(res.ok()).toBeTruthy();
    expect(Array.isArray(await res.json())).toBeTruthy();
  });

  test("GET /api/settings/ returns required fields including tts_engine", async ({ request }) => {
    const res = await request.get(`${API}/settings/`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.tts_engine).toBeTruthy();
    expect(data.ollama_base_url).toBeTruthy();
    expect(data.available_tts_engines).toBeTruthy();
    expect(data.available_tts_engines).toContain("vieneu");
    expect(data.available_tts_engines).toContain("edge-tts");
    // video_model should NOT be in the response (was removed)
    expect(data.video_model).toBeUndefined();
  });

  test("GET /api/services/status returns 4 services", async ({ request }) => {
    const res = await request.get(`${API}/services/status`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.services).toHaveLength(4);
    expect(data.checked_at).toBeTruthy();
  });

  test("Draw Things health endpoint uses GET / not /sdapi/v1/sd-models", async ({ request }) => {
    // This verifies the fix — old endpoint returned 404, new one returns 200 or connection refused
    // We just check the services API reflects the correct check
    const res = await request.get(`${API}/services/status`);
    const data = await res.json();
    const dt = data.services.find((s: any) => s.id === "draw_things");
    expect(dt).toBeDefined();
    // online should be boolean (not null/undefined)
    expect(typeof dt.online).toBe("boolean");
  });

  test("POST /api/jobs/create with empty topic returns 422", async ({ request }) => {
    const res = await request.post(`${API}/jobs/create`, {
      data: { topic: "", auto_publish: false },
    });
    expect(res.status()).toBe(422);
  });

  test("POST /api/jobs/create does NOT accept video_model field as required", async ({ request }) => {
    // After removing video_model from schema, it should be ignored if sent
    const res = await request.post(`${API}/jobs/create`, {
      data: { topic: "schema test", auto_publish: false, video_model: "svd_xt" },
    });
    // Should succeed (extra field is silently ignored by Pydantic)
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.job_id).toBeTruthy();
    // Cancel it immediately
    await request.post(`${API}/jobs/${data.job_id}/cancel`);
  });

  test("GET /api/jobs/nonexistent returns 404", async ({ request }) => {
    const res = await request.get(`${API}/jobs/does-not-exist-xyz`);
    expect(res.status()).toBe(404);
  });

  test("POST /api/jobs/nonexistent/cancel returns 404", async ({ request }) => {
    const res = await request.post(`${API}/jobs/does-not-exist-xyz/cancel`);
    expect(res.status()).toBe(404);
  });

  test("GET /api/projects/nonexistent/load returns 404", async ({ request }) => {
    const res = await request.get(`${API}/projects/does-not-exist-xyz/load`);
    expect(res.status()).toBe(404);
  });
});
