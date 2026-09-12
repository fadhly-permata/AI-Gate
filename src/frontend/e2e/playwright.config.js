import path from "path";
import { fileURLToPath } from "url";
import { defineConfig, devices } from "@playwright/test";

// Resolusi absolut ke run.py di root project (config ini ada di
// src/frontend/e2e, jadi naik 3 level). Pakai absolut biar webServer jalan
// benar terlepas dari direktori eksekusi.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..", "..");
const RUN_PY = path.join(ROOT, "run.py");

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
//
// ---------------------------------------------------------------------------
// CARA JALAN — gunakan runner, JANGAN `playwright test` polos. Dua sebab runner
// ini ada (keduanya terukur di Termux):
//  1. Berkas config ini ada di src/frontend/e2e/, sedangkan perintah npm jalan
//     dari src/frontend/. Playwright hanya mencari `playwright.config.*` di
//     folder kerja, jadi config ini TIDAK terbaca: tanpa config, testDir default
//     = src/frontend/ -> CLI ikut mengumpulkan src/frontend/tests/*.test.js
//     (vitest) dan gagal dengan "Vitest failed to access its internal state".
//     Runner ini selalu mengirim --config <folder ini>.
//  2. Di Termux/Android, `playwright` CLI CRASH saat modulnya di-import,
//     SEBELUM env apa pun dibaca:
//       Error: Unsupported platform: android
//         at .../playwright-core/lib/coreBundle.js:32822
//     (registry playwright-core menghitung platform saat module-init).
//     Shim yang terbukti jalan: preload yang mengubah process.platform ->
//     "linux" lewat `--import data:` (Node 24 men-supportnya; TIDAK menyentuh
//     node_modules):
//       NODE_OPTIONS="--import data:text/javascript,<encoded-js>" \
//       node node_modules/@playwright/test/cli.js test --config e2e/playwright.config.js
//     encoded-js = encodeURIComponent(
//       "Object.defineProperty(process,'platform',{value:'linux'});")
//     `e2e/run.mjs` (dipanggil `npm run test:e2e`) sudah melakukan keduanya.
//     Jangan pakai ts-node/--experimental-detect-module; jangan patch node_modules.
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
  // testDir DINILAI RELATIF TERHADAP FOLDER CONFIG, bukan folder kerja.
  // Nilai lama "e2e" -> jadi src/frontend/e2e/e2e -> "Error: No tests found".
  // Pakai path absolut folder ini supaya berisi smoke.spec.js di mana pun
  // diperintahkan dari dalam repo.
  testDir: HERE,
  // outputDir tidak disetel: default Playwright menaruh artefak (trace,
  // error-context, screenshot "only-on-failure") di <folder kerja>/test-results.
  // Terukur di sini: src/frontend/test-results/ — BUANG direktori itu setelah
  // jalan kalau `git status --short` mau bersih (aturan B5, nol file sisa).
  timeout: 30000,
  expect: { timeout: 10000 },
  use: {
    baseURL: BASE,
    headless: true,
    // Dukungan browser eksternal (Android/Termux). Bila kosong, Playwright pakai
    // browser bawaan (harus `npx playwright install` dulu).
    channel: CHANNEL,
    // executablePath BUKAN opsi `use` Playwright Test (0 kemunculan di
    // node_modules/playwright/types/test.d.ts) -> dulu diabaikan DIAM-DIAM dan
    // tetap mencari headless_shell bawaan yang tidak ada. Yang benar:
    // launchOptions.executablePath.
    launchOptions: { executablePath: EXECUTABLE, args: launchArgs },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  // Jalankan server lewat run.py (tau PYTHONPATH ke src/backend). reuseExistingServer
  // true => kalau server sudah jalan (mis. `python run.py`), tidak di-spawn lagi.
  webServer: {
    command: process.env.AIGATE_SERVER_CMD || `python ${RUN_PY} --port ${PORT}`,
    url: BASE,
    reuseExistingServer: true,
    timeout: 60000,
    stdout: "ignore",
    stderr: "pipe",
  },
  projects: [
    {
      // Desktop Chrome = viewport 1280x720 EKSPLISIT dari devices[]. Viewport di
      // sini dinaikkan ke 1280x900 dan ditulis eksplisit (bukan warisan devices[])
      // supaya terbaca di config: Log Window (#logWindow) tampil bawaan dan
      // dipaku ke bawah layar (position:fixed, styles.css:1637-1648) sehingga di
      // jendela sempit puncaknya naik menutupi tombol ⋮ baris (diukur pada
      // 800x600: tombol 294-322px vs puncak panel 219px -> klik mendarat di panel
      // log, menu tidak pernah terbuka).
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 900 } },
    },
  ],
});
