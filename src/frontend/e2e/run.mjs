// Runner e2e Playwright untuk repo ini — INI PILIHAN RESMI:
//   npm run test:e2e            -> package.json menjalankan berkas ini
//   node e2e/run.mjs [arg...]   -> sama, dipanggil langsung (npx rusak di sini)
// Argumen tambahan diteruskan apa adanya ke `playwright test`, jadi
// `npm run test:e2e -- smoke.spec.js` dan `-- --list` tetap bisa.
//
// Kenapa perlu runner, dan bukan `playwright test` polos di folder ini:
//
//   1. Config ada di src/frontend/e2e/playwright.config.js, sedangkan perintah
//      npm berjalan dari src/frontend/. Playwright hanya mencari
//      `playwright.config.*` di folder kerja -> config tidak terbaca -> CLI
//      memakai testDir default (src/frontend/) lalu ikut mengumpulkan
//      tests/*.test.js milik vitest dan gagal ("Vitest failed to access its
//      internal state"). Runner ini selalu mengirim --config <folder ini>.
//   2. Di Termux, `require("playwright-core")` CRASH saat module-init,
//      sebelum env apa pun dibaca:
//        Error: Unsupported platform: android
//          at .../playwright-core/lib/coreBundle.js:32822
//      Shim: preload yang mengganti process.platform -> "linux". Node 24
//      menerima `--import data:` sehingga tidak perlu menulis berkas temp dan
//      TIDAK ada node_modules yang ditambal. Ditaruh di NODE_OPTIONS supaya
//      diwarisi ke semua child process Playwright (CLI + worker + server).
//
// Pemakaian (dari src/frontend/):
//   PW_EXECUTABLE=/data/data/com.termux/files/usr/bin/chromium-browser \
//   PW_NO_SANDBOX=1 AIGATE_URL=http://127.0.0.1:8080 \
//   npm run test:e2e                     # semua tes
//   npm run test:e2e -- smoke.spec.js    # filter
// (variabel env di atas dibutuhkan di Android/Termux; di host dengan
//  `npx playwright install` cukup AIGATE_URL saja).

import { spawn } from "child_process";
import path from "path";
import { fileURLToPath } from "url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FE_ROOT = path.resolve(HERE, "..");
const CONFIG = path.join(HERE, "playwright.config.js");
const CLI = path.join(FE_ROOT, "node_modules", "@playwright", "test", "cli.js");

// Playwright menghitung platform pada saat modul dimuat, dari process.platform.
// "android" tidak ada di daftarnya. Node di Termux melapor "android"
// (Object.getOwnPropertyDescriptor(process,"platform") -> configurable:true),
// jadi bisa ditimpa sebelum modul itu sempat dimuat.
const SHIM_SRC = "Object.defineProperty(process,'platform',{value:'linux'});";
const SHIM = "--import=data:text/javascript," + encodeURIComponent(SHIM_SRC);

const childEnv = { ...process.env };
childEnv.NODE_OPTIONS = [childEnv.NODE_OPTIONS, SHIM].filter(Boolean).join(" ");

const child = spawn(process.execPath, [CLI, "test", "--config", CONFIG, ...process.argv.slice(2)], {
  cwd: FE_ROOT,
  env: childEnv,
  stdio: "inherit",
});

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  else process.exit(code == null ? 1 : code);
});
