import { defineConfig, devices } from "@playwright/test";

// ===========================================================================
// Cross-platform e2e config (Android/Termux + Linux + macOS + Windows)
// ---------------------------------------------------------------------------
// Di Android/Termux, Playwright biasanya GAK bisa download/run Chromium bawaan.
// Pakai browser yang SUDAH terpasang lewat env berikut (tidak perlu
// `npx playwright install`):
//   PW_EXECUTABLE  -> path ke chrome/chromium, cth Termux:
//                     /data/data/com.termux/files/usr/bin/chromium-browser
//   PW_CHANNEL     -> "chrome" | "msedge" | "chrome-beta" (pakai installan resmi)
//   PW_NO_SANDBOX  -> "1" wajib di Android/Termux (Chromium butuh --no-sandbox)
//   AIGATE_PORT    -> port gateway (default 8080)
//   AIGATE_URL     -> baseURL (default http://127.0.0.1:<port>)
//   AIGATE_SERVER_CMD -> override perintah start server (default: python ../../run.py)
// ===========================================================================

const PORT = process.env.AIGATE_PORT || "8080";
const BASE = process.env.AIGATE_URL || `http://127.0.0.1:${PORT}`;

const EXECUTABLE = process.env.PW_EXECUTABLE || undefined;
const CHANNEL = process.env.PW_CHANNEL || undefined;
const NO_SANDBOX = process.env.PW_NO_SANDBOX === "1";

const launchArgs = [];
if (NO_SANDBOX) {
  // Android/Termux: Chromium wajib no-sandbox + shm kecil.
  launchArgs.push("--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage");
}

export default defineConfig({
  testDir: "e2e",
  timeout: 30000,
  expect: { timeout: 10000 },
  use: {
    baseURL: BASE,
    headless: true,
    // Dukungan browser eksternal (Android/Termux). Bila kosong, Playwright pakai
    // browser bawaan (harus `npx playwright install` dulu).
    channel: CHANNEL,
    executablePath: EXECUTABLE,
    launchOptions: { args: launchArgs },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  // Jalankan server lewat run.py (tau PYTHONPATH ke src/backend). reuseExistingServer
  // true => kalau server sudah jalan (mis. `python run.py`), tidak di-spawn lagi.
  webServer: {
    command: process.env.AIGATE_SERVER_CMD || `python ../../run.py --port ${PORT}`,
    url: BASE,
    reuseExistingServer: true,
    timeout: 60000,
    stdout: "ignore",
    stderr: "pipe",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
