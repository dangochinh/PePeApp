import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 30000,        // default per-test; pipeline tests override with test.setTimeout()
  workers: 1,            // run tests sequentially — pipeline tests share job state
  use: {
    baseURL: "http://localhost:3000",
    headless: true,
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 30000,
  },
  reporter: [["list"], ["html", { open: "never" }]],
  projects: [
    { name: "chromium", use: { channel: "chromium" } },
    {
      name: "brave",
      use: {
        headless: false,
        launchOptions: {
          executablePath: "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
        },
      },
    },
  ],
});
