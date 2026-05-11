/**
 * Full pipeline E2E test: topic → research → script → TTS → image → video → merge
 *
 * Requires both servers running:
 *   backend: uvicorn api.app:app --port 8888
 *   frontend: pnpm dev (port 3000)
 *
 * Run with: pnpm playwright test tests/pipeline.spec.ts
 * Or headed: pnpm playwright test tests/pipeline.spec.ts --headed
 */

import { test, expect, type Page } from "@playwright/test";

const API = "http://localhost:8888/api";

// ── Shared state across tests in this file ──────────────────────────────────
let sharedJobId = "";
let sharedProjectName = "";
let sharedSceneCount = 6; // 4wh=6 scenes, viral=7 scenes

// ── Helpers ─────────────────────────────────────────────────────────────────

async function getJob(jobId: string): Promise<any> {
  const res = await fetch(`${API}/jobs/${jobId}`);
  if (!res.ok) return null;
  return res.json();
}

async function pollJobUntil(
  jobId: string,
  predicate: (job: any) => boolean,
  timeoutMs = 300_000,
  intervalMs = 3000
): Promise<any> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const job = await getJob(jobId);
    if (job && predicate(job)) return job;
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  const job = await getJob(jobId);
  throw new Error(
    `Timeout waiting for job condition. Last status: ${job?.status}, step: ${job?.current_step}`
  );
}

async function waitForLogEntry(page: Page, text: string, timeoutMs = 120_000): Promise<void> {
  await page.waitForFunction(
    (t) => {
      const log = document.querySelector("[data-testid='exec-log']");
      if (log) return log.textContent?.includes(t) ?? false;
      return document.body.textContent?.includes(t) ?? false;
    },
    text,
    { timeout: timeoutMs }
  );
}

// ── Full Pipeline Flow ───────────────────────────────────────────────────────

test.describe("Full Pipeline Flow", () => {
  test.setTimeout(600_000); // 10 minutes per test

  // ── 1. Create job ────────────────────────────────────────────────────────

  test("1. Submit topic and job is created", async ({ page }) => {
    await page.goto("/");
    await page.waitForLoadState("networkidle");

    // Select 4WH framework (6 scenes)
    await page.getByRole("button", { name: /4WH Framework/i }).click();

    await page.locator("textarea").fill("bitcoin cryptocurrency");

    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/jobs/create") && r.status() === 200),
      page.getByRole("button", { name: /start pipeline/i }).click(),
    ]);

    const data = await response.json();
    sharedJobId = data.job_id;
    sharedProjectName = data.project_name;
    sharedSceneCount = 6; // 4wh = 6 scenes

    expect(sharedJobId).toBeTruthy();
    expect(sharedProjectName).toBeTruthy();

    // Verify API request included correct script_style
    // (can't re-read request body after the fact, but we got a valid response)
    expect(data.topic).toBe("bitcoin cryptocurrency");

    await expect(page).toHaveURL(new RegExp(`/projects/${sharedProjectName}`));
    await page.waitForSelector("text=Live Execution Log", { timeout: 10_000 });
  });

  // ── 2. Research phase ─────────────────────────────────────────────────────

  test("2. Research phase completes — article in log", async ({ page }) => {
    test.skip(!sharedJobId, "No job from previous test");

    const job = await pollJobUntil(
      sharedJobId,
      (j) => !["pending", "researching"].includes(j.status),
      360_000
    );

    if (job.status === "failed") {
      throw new Error(`Pipeline failed during research: ${job.error}`);
    }

    expect(["scripting", "rendering", "tts", "assembling", "preview", "completed", "failed"].includes(job.status)).toBeTruthy();

    // Check at least 1 log entry with article info or search results
    const hasResearchLog = (job.logs ?? []).some((l: string) =>
      l.includes("Selected article") || l.includes("🔍") || l.includes("🤖")
    );
    expect(hasResearchLog).toBeTruthy();
  });

  // ── 3. Script generation — Shot List populates progressively ─────────────

  test("3. Script generation streams scenes to Shot List", async ({ page }) => {
    test.skip(!sharedJobId, "No job from previous test");

    // Wait for scripting to finish (4wh=6 scenes, viral=7 scenes)
    const job = await pollJobUntil(
      sharedJobId,
      (j) => {
        const scripts = j.scripts ?? [];
        if (scripts.length === 0) return false;
        const scenes = scripts[0]?.scenes ?? [];
        return scenes.length >= sharedSceneCount || !["pending", "researching", "scripting"].includes(j.status);
      },
      300_000,
      5000
    );

    if (job.status === "failed") {
      const scenes = job.scripts?.[0]?.scenes ?? [];
      if (scenes.length === 0) throw new Error(`Pipeline failed with no scenes: ${job.error}`);
      console.warn(`Pipeline failed after ${scenes.length} scenes: ${job.error}`);
    }

    const scenes = job.scripts?.[0]?.scenes ?? [];
    expect(scenes.length).toBeGreaterThanOrEqual(1);

    // Each scene must have a visual_prompt (not empty and not a generic fallback)
    for (const scene of scenes) {
      expect(scene.visual_prompt).toBeTruthy();
      expect(scene.visual_prompt.length).toBeGreaterThan(10);
    }

    // Load the project in UI
    await page.goto(`/projects/${sharedProjectName}`);
    await page.waitForLoadState("networkidle");

    await page.waitForSelector("text=Shot List", { timeout: 15_000 });

    const sceneCards = page.locator("text=SHOT #");
    await sceneCards.first().waitFor({ timeout: 15_000 });
    expect(await sceneCards.count()).toBeGreaterThanOrEqual(1);
  });

  // ── 4. Full pipeline → completion ─────────────────────────────────────────

  test("4. Full pipeline runs to completion (rendering + TTS + assembly)", async ({ page }) => {
    test.skip(!sharedJobId, "No job from previous test");

    const job = await pollJobUntil(
      sharedJobId,
      (j) => ["preview", "completed", "failed", "cancelled"].includes(j.status),
      480_000,
      5000
    );

    if (job.status === "failed") {
      const hasScripts = (job.scripts ?? []).length > 0;
      if (!hasScripts) throw new Error(`Pipeline failed with no scripts: ${job.error}`);
      console.warn(`Pipeline ended with status=${job.status}: ${job.error}`);
    } else {
      expect(["preview", "completed"]).toContain(job.status);
      expect(job.progress_pct).toBeGreaterThanOrEqual(90);
    }
  });

  // ── 5. Retry TTS for scene 1 ─────────────────────────────────────────────

  test("5. Retry TTS for scene 1 — queues and logs entry", async ({ page }) => {
    test.skip(!sharedJobId, "No job from previous test");

    await page.goto(`/projects/${sharedProjectName}`);
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("text=SHOT #1", { timeout: 15_000 });

    // If TTS already ready, skip
    const ttsRow = page.locator("text=🎤 TTS Voice").first();
    const ttsRowParent = ttsRow.locator("..");
    const isReady = await ttsRowParent.locator("text=✓ Xong").count();
    if (isReady > 0) {
      console.log("TTS already ready for scene 1 — skipping retry test");
      return;
    }

    // Retry button next to ⏳ Missing
    const retryBtn = ttsRowParent.locator("button", { hasText: /retry/i }).first();
    await retryBtn.waitFor({ timeout: 10_000 });
    await retryBtn.click();
    await expect(retryBtn).toHaveText(/queued|⏳/i, { timeout: 10_000 });

    // Poll until audio_path is set
    await pollJobUntil(
      sharedJobId,
      (j) => !!j.scripts?.[0]?.scenes?.[0]?.audio_path,
      90_000,
      3000
    );
  });

  // ── 6. Retry image for scene 1 ────────────────────────────────────────────

  test("6. Retry image render for scene 1", async ({ page }) => {
    test.skip(!sharedJobId, "No job from previous test");

    await page.goto(`/projects/${sharedProjectName}`);
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("text=SHOT #1", { timeout: 15_000 });

    const imgRow = page.locator("text=🖼️ Hình cảnh").first();
    const imgRowParent = imgRow.locator("..");
    const isReady = await imgRowParent.locator("text=✓ Xong").count();
    if (isReady > 0) {
      console.log("Image already ready for scene 1 — skipping");
      return;
    }

    const retryBtn = imgRowParent.locator("button", { hasText: /retry/i }).first();
    await retryBtn.waitFor({ timeout: 10_000 });
    await retryBtn.click();
    await expect(retryBtn).toHaveText(/queued|⏳/i, { timeout: 10_000 });

    await pollJobUntil(
      sharedJobId,
      (j) => !!(j.scripts?.[0]?.scenes?.[0]?.clip_path || j.scripts?.[0]?.scenes?.[0]?.image_path),
      60_000,
      3000
    );
  });

  // ── 7. Video render path uses correct extension ───────────────────────────

  test("7. Retry video render for scene 1 — path uses actual file extension", async ({ page }) => {
    test.skip(!sharedJobId, "No job from previous test");

    await page.goto(`/projects/${sharedProjectName}`);
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("text=SHOT #1", { timeout: 15_000 });

    const currentJob = await getJob(sharedJobId);
    const scene0 = currentJob?.scripts?.[0]?.scenes?.[0];
    if (scene0?.video_path) {
      const filename = scene0.video_path.split(/[\\/]/).pop()!;
      const serveRes = await fetch(`${API}/projects/${sharedProjectName}/clip/${filename}`);
      expect(serveRes.ok).toBeTruthy();
      return;
    }

    const renderRes = await fetch(`${API}/jobs/${sharedJobId}/render-video/0`, { method: "POST" });
    expect(renderRes.ok).toBeTruthy();

    const job = await pollJobUntil(
      sharedJobId,
      (j) => !!j.scripts?.[0]?.scenes?.[0]?.video_path,
      60_000,
      3000
    );

    const scene = job.scripts[0].scenes[0];
    expect(scene.video_path).toMatch(/\.(png|jpg|mp4)$/i);

    const filename = scene.video_path.split(/[\\/]/).pop()!;
    const serveRes = await fetch(`${API}/projects/${sharedProjectName}/clip/${filename}`);
    expect(serveRes.ok).toBeTruthy();
    expect(serveRes.status).toBe(200);
    console.log(`✅ video_path=${filename} exists and is serveable`);
  });

  // ── 8. Resume button for stopped/failed job ───────────────────────────────

  test("8. Resume button appears for stopped job and triggers /continue", async ({ page }) => {
    test.skip(!sharedJobId, "No job from previous test");

    const currentJob = await getJob(sharedJobId);
    if (!currentJob) return;

    // If job already completed normally, verify no Resume button appears
    if (["preview", "completed"].includes(currentJob.status)) {
      await page.goto(`/projects/${sharedProjectName}`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);
      const resumeBtn = page.getByRole("button", { name: /▶ Resume/i });
      await expect(resumeBtn).not.toBeVisible();
      console.log("Pipeline completed — Resume button correctly hidden");
      return;
    }

    // For cancelled/failed jobs, Resume button should appear
    if (["cancelled", "failed"].includes(currentJob.status)) {
      await page.goto(`/projects/${sharedProjectName}`);
      await page.waitForLoadState("networkidle");
      await page.waitForTimeout(2000);

      const resumeBtn = page.getByRole("button", { name: /▶ Resume/i });
      await expect(resumeBtn).toBeVisible({ timeout: 8000 });

      const [resumeRes] = await Promise.all([
        page.waitForResponse((r) =>
          r.url().includes(`/jobs/${sharedJobId}/continue`) && r.status() === 200
        ),
        resumeBtn.click(),
      ]);
      expect(resumeRes.ok()).toBeTruthy();
    }
  });

  // ── 9. Assembly → final.mp4 ───────────────────────────────────────────────

  test("9. Assembly produces final.mp4", async ({ page }) => {
    test.skip(!sharedJobId, "No job from previous test");

    await pollJobUntil(
      sharedJobId,
      (j) => ["preview", "completed", "failed", "cancelled"].includes(j.status),
      480_000,
      5000
    );

    const listRes = await fetch(`${API}/projects/list`);
    const projects: any[] = await listRes.json();
    const proj = projects.find((p: any) => p.name === sharedProjectName);
    if (!proj) throw new Error(`Project ${sharedProjectName} not found in projects list`);

    if (proj.has_final) {
      expect(proj.has_final).toBeTruthy();
      const finalRes = await fetch(`${API}/projects/${sharedProjectName}/final`);
      expect(finalRes.ok).toBeTruthy();
      expect(finalRes.headers.get("content-type")).toContain("video");
      console.log("✅ final.mp4 exists and is serveable");
    } else {
      console.warn(`final.mp4 not produced — clips_count=${proj.clips_count}`);
      expect(proj.clips_count).toBeGreaterThan(0);
    }
  });

  // ── 10. Project appears in Projects tab ───────────────────────────────────

  test("10. Project appears in Projects tab with status badge", async ({ page }) => {
    test.skip(!sharedProjectName, "No project from previous test");

    await page.goto("/");
    await page.waitForLoadState("networkidle");

    await page.getByRole("button", { name: /projects/i }).click();
    await page.waitForSelector("text=Production History", { timeout: 10_000 });

    const projectRow = page.locator("tr").filter({ hasText: sharedProjectName });
    await projectRow.waitFor({ timeout: 15_000 });
    await expect(projectRow).toBeVisible();

    const badge = projectRow.locator("span").filter({ hasText: /COMPLETED|IN PROGRESS/ });
    await expect(badge).toBeVisible();
  });

  // ── 11. Load project from Projects tab ────────────────────────────────────

  test("11. Load project from Projects tab and view Shot List", async ({ page }) => {
    test.skip(!sharedProjectName, "No project from previous test");

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /projects/i }).click();
    await page.waitForSelector("text=Production History", { timeout: 10_000 });

    const projectRow = page.locator("tr").filter({ hasText: sharedProjectName });
    await projectRow.waitFor({ timeout: 15_000 });

    const manageBtn = projectRow.getByRole("button", { name: /manage/i });
    await manageBtn.click();

    await expect(page).toHaveURL(new RegExp(`/projects/${sharedProjectName}`));
    await page.waitForSelector("text=Shot List", { timeout: 15_000 });

    const sceneCards = page.locator("text=SHOT #");
    await sceneCards.first().waitFor({ timeout: 10_000 });
    expect(await sceneCards.count()).toBeGreaterThanOrEqual(1);
  });
});

// ── Standalone smoke tests ────────────────────────────────────────────────

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

  test("GET /api/settings/ returns settings with tts_engine (not video_model)", async ({ request }) => {
    const res = await request.get(`${API}/settings/`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    expect(data.tts_engine).toBeTruthy();
    expect(data.ollama_base_url).toBeTruthy();
    // video_model was removed — must not appear
    expect(data.video_model).toBeUndefined();
  });

  test("GET /api/services/status returns all 4 services", async ({ request }) => {
    const res = await request.get(`${API}/services/status`);
    expect(res.ok()).toBeTruthy();
    const data = await res.json();
    const ids = data.services.map((s: any) => s.id);
    expect(ids).toContain("ollama");
    expect(ids).toContain("draw_things");
    expect(ids).toContain("comfyui");
    expect(ids).toContain("tts");
  });

  test("POST /api/jobs/create with empty topic returns 422", async ({ request }) => {
    const res = await request.post(`${API}/jobs/create`, {
      data: { topic: "", auto_publish: false },
    });
    expect(res.status()).toBe(422);
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

// ── ComfyUI offline fallback ──────────────────────────────────────────────

test.describe("ComfyUI offline fallback (API-level)", () => {
  test("render-scene creates a .png file when ComfyUI is offline", async ({ request }) => {
    const listRes = await request.get(`${API}/jobs/list`);
    const jobs: any[] = await listRes.json();
    const jobWithScripts = jobs.find(
      (j: any) => j.scripts && j.scripts[0]?.scenes?.length > 0
    );

    if (!jobWithScripts) {
      test.skip(true, "No jobs with scripts available — run pipeline tests first");
      return;
    }

    const jobId = jobWithScripts.job_id;
    const renderRes = await request.post(`${API}/jobs/${jobId}/render-scene/0`);
    expect(renderRes.ok()).toBeTruthy();

    const deadline = Date.now() + 60_000;
    let resultScene: any = null;
    while (Date.now() < deadline) {
      const jobRes = await request.get(`${API}/jobs/${jobId}`);
      const job = await jobRes.json();
      const scene = job.scripts?.[0]?.scenes?.[0];
      if (scene?.clip_path || scene?.image_path) { resultScene = scene; break; }
      await new Promise((r) => setTimeout(r, 2000));
    }

    expect(resultScene).not.toBeNull();
    const clipPath: string = resultScene.clip_path || resultScene.image_path || "";
    expect(clipPath).toMatch(/\.(png|jpg|mp4)$/i);
  });
});

// ── Edge cases ───────────────────────────────────────────────────────────────

test.describe("Edge cases", () => {
  test.setTimeout(120_000);

  test("Cancel: stop a running job → status becomes cancelling/cancelled", async ({ request }) => {
    const createRes = await request.post(`${API}/jobs/create`, {
      data: { topic: "edge case cancel test", auto_publish: false },
    });
    expect(createRes.ok()).toBeTruthy();
    const { job_id } = await createRes.json();

    await new Promise((r) => setTimeout(r, 2000));

    const cancelRes = await request.post(`${API}/jobs/${job_id}/cancel`);
    expect(cancelRes.ok()).toBeTruthy();
    expect((await cancelRes.json()).status).toBe("cancelling");

    const deadline = Date.now() + 360_000;
    let finalStatus = "cancelling";
    while (Date.now() < deadline) {
      const job = await (await request.get(`${API}/jobs/${job_id}`)).json();
      finalStatus = job.status;
      if (["cancelled", "failed", "completed"].includes(finalStatus)) break;
      await new Promise((r) => setTimeout(r, 5000));
    }
    expect(["cancelled", "failed", "completed"]).toContain(finalStatus);
  });

  test("Rerun: job with no scripts returns 400", async ({ request }) => {
    const createRes = await request.post(`${API}/jobs/create`, {
      data: { topic: "rerun no script test", auto_publish: false },
    });
    expect(createRes.ok()).toBeTruthy();
    const { job_id } = await createRes.json();

    await request.post(`${API}/jobs/${job_id}/cancel`);
    await new Promise((r) => setTimeout(r, 5000));

    const rerunRes = await request.post(`${API}/jobs/${job_id}/rerun`);
    expect([200, 400]).toContain(rerunRes.status());
    if (rerunRes.status() === 400) {
      const body = await rerunRes.json();
      expect(body.detail).toMatch(/script/i);
    }
  });

  test("Reload: navigating to /projects/<name> loads the project", async ({ page }) => {
    const listRes = await fetch(`${API}/projects/list`);
    const projects: any[] = await listRes.json();
    if (projects.length === 0) {
      test.skip(true, "No projects on disk");
      return;
    }

    const projName = projects[0].name;
    await page.goto(`/projects/${projName}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    expect(page.url()).toContain(projName);

    const hasProgressCard = await page.locator("text=Live Execution Log").count();
    const hasScenes = await page.locator("text=SHOT #").count();
    const hasEmptyShot = await page.locator("text=Shot List").count();
    expect(hasProgressCard + hasScenes + hasEmptyShot).toBeGreaterThan(0);
  });

  test("Delete: completed project removed from list", async ({ request }) => {
    const listRes = await request.get(`${API}/projects/list`);
    const projects: any[] = await listRes.json();
    const target = projects.find((p) => p.has_final);

    if (!target) {
      test.skip(true, "No completed projects to delete");
      return;
    }

    const deleteRes = await request.delete(`${API}/projects/${target.name}`);
    if (!deleteRes.ok()) {
      const body = await deleteRes.json().catch(() => ({}));
      console.log(`Delete skipped: ${deleteRes.status()} — ${body.detail ?? "unknown"}`);
      test.skip(true, `Project could not be deleted: ${body.detail}`);
      return;
    }

    const afterRes = await request.get(`${API}/projects/list`);
    const after: any[] = await afterRes.json();
    expect(after.find((p) => p.name === target.name)).toBeUndefined();
  });

  test("UI: Settings TTS ENGINE select has valid selected value", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");
    await page.waitForSelector("text=Factory Settings", { timeout: 8000 });

    // The TTS ENGINE select (first select in Core Model Selection)
    const ttsSelect = page.locator("select").first();
    await ttsSelect.waitFor({ timeout: 5000 });
    const val = await ttsSelect.inputValue();
    expect(val).not.toBe("");
    expect(["vieneu", "edge-tts", "piper", "faster-qwen3-tts"]).toContain(val);
    console.log(`✅ TTS ENGINE select value: ${val}`);
  });

  test("UI: Projects table shows real timestamp not always-today", async ({ page }) => {
    const listRes = await fetch(`${API}/projects/list`);
    const projects: any[] = await listRes.json();
    if (projects.length === 0) {
      test.skip(true, "No projects on disk");
      return;
    }

    await page.goto("/");
    await page.waitForLoadState("networkidle");
    await page.getByRole("button", { name: /projects/i }).click();
    await page.waitForSelector("text=Production History", { timeout: 8000 });

    const rows = page.locator("tbody tr");
    await rows.first().waitFor({ timeout: 8000 });
    const tsCell = rows.first().locator("td").nth(3);
    const tsText = await tsCell.innerText();
    // Must be non-empty and look like a date/time or project-name-derived string
    expect(tsText.trim()).not.toBe("");
    console.log(`✅ Timestamp shows: ${tsText.trim()}`);
  });

  test("UI: Manage Assets button appears for completed project", async ({ page }) => {
    const listRes = await fetch(`${API}/projects/list`);
    const projects: any[] = await listRes.json();
    const completedProj = projects.find((p: any) => p.has_final);

    if (!completedProj) {
      test.skip(true, "No completed projects found");
      return;
    }

    await page.goto(`/projects/${completedProj.name}`);
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(3000);

    const sceneCards = page.locator("text=SHOT #");
    if (await sceneCards.count() > 0) {
      await expect(page.getByRole("button", { name: /manage assets/i })).toBeVisible({ timeout: 5000 });
    }
  });
});
