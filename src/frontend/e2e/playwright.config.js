import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  use: {
    baseURL: process.env.AIGATE_URL || "http://localhost:8080"
  },
  webServer: {
    command: "uvicorn backend.server:app --port 8080",
    url: "http://localhost:8080",
    reuseExistingServer: true,
    timeout: 60000
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
