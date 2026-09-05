// On-device Android/Termux e2e runner.
//
// Playwright tidak mendukung platform "android" (guard di playwright-core), jadi
// untuk jalanin e2e LANGSUNG di Android kita pakai puppeteer-core yang cuma
// spawn Chromium via CDP (tanpa platform guard). Butuh browser yg SUDAH terpasang:
//   PW_EXECUTABLE  -> path ke chromium/chrome, cth Termux:
//                     /data/data/com.termux/files/usr/bin/chromium-browser
//   PW_NO_SANDBOX  -> "1" (wajib di Android/Termux)
//   AIGATE_URL     -> baseURL server (default http://127.0.0.1:8080)
//
// Jalankan (server aigate sudah nyala): npm run test:e2e:android

import puppeteer from "puppeteer-core";

const BASE = process.env.AIGATE_URL || "http://127.0.0.1:8080";
const EXEC = process.env.PW_EXECUTABLE;

if (!EXEC) {
  console.error("E2E Android butuh env PW_EXECUTABLE = path ke chromium/chrome.");
  process.exit(2);
}

const args = [
  "--no-sandbox",
  "--disable-setuid-sandbox",
  "--disable-dev-shm-usage",
  "--disable-gpu",
];

let browser;
try {
  browser = await puppeteer.launch({ executablePath: EXEC, headless: true, args });
  const page = await browser.newPage();

  await page.goto(BASE + "/", { waitUntil: "networkidle2", timeout: 30000 });

  const title = await page.title();
  if (!/aigate/i.test(title)) throw new Error(`title tidak mengandung 'aigate': ${title}`);

  const sidebar = await page.$("aside.sidebar");
  if (!sidebar) throw new Error("aside.sidebar tidak ditemukan");

  const healthOk = await page.evaluate(async () => {
    try {
      return (await fetch("/api/health")).ok;
    } catch {
      return false;
    }
  });
  if (!healthOk) throw new Error("/api/health tidak ok");

  const provOk = await page.evaluate(async () => {
    try {
      const r = await fetch("/api/providers");
      if (!r.ok) return false;
      const j = await r.json();
      return j && j.object === "list";
    } catch {
      return false;
    }
  });
  if (!provOk) throw new Error("/api/providers tidak ok");

  console.log("ANDROID E2E PASS: title + sidebar + /api/health + /api/providers");
  process.exit(0);
} catch (e) {
  console.error("ANDROID E2E FAIL:", e.message);
  process.exit(1);
} finally {
  if (browser) await browser.close();
}
