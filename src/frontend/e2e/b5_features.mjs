// B5.1–B5.7 feature e2e runner — drives the REAL views in a real Chromium.
//
// Kontrak env sama dengan e2e/android.mjs (puppeteer-core, BUKAN Playwright —
// core-nya menolak platform "android" di Termux):
//   PW_EXECUTABLE  -> path ke chromium/chrome, cth Termux:
//                     /data/data/com.termux/files/usr/bin/chromium-browser
//   PW_NO_SANDBOX  -> "1" (wajib di Android/Termux)
//   AIGATE_URL     -> baseURL server (default http://127.0.0.1:8080)
//
// Yang di-drive (semua selector diverifikasi dari app.js / index.html /
// usage.js / analytics.js — bukan asumsi):
//   seed   : POST /api/providers + POST /api/accounts (via page.evaluate fetch)
//   B5.1   : nav providers -> baris #provTableBody -> .js-disc -> #provDetail
//            -> #accountsBody berisi "e2e-acc" + #provConnectOAuthBtn
//            CATATAN: klik baris = buka modal EDIT (renderProviders app.js);
//            jalur nyata ke #provDetail adalah tombol discover (.js-disc).
//   B5.5   : nav usage -> #quotaTableBody tr.quota-row (provider seed muncul,
//            kemungkinan "unlimited") + #usageTotals .usage-stat
//   B5.6   : nav analytics -> #analyticsChart .trend-col >= 1 +
//            #analyticsExportBtn visible
//   B5.7   : nav settings -> #exportBtn + #importFile (+ #importBtn)
//
// Jalankan (server aigate sudah nyala): npm run test:e2e:b5
// Exit 0 = PASS, non-zero = FAIL. Cleanup seed best-effort di akhir.

import puppeteer from "puppeteer-core";

const BASE = process.env.AIGATE_URL || "http://127.0.0.1:8080";
const EXEC = process.env.PW_EXECUTABLE;

if (!EXEC) {
  console.error("B5 E2E butuh env PW_EXECUTABLE = path ke chromium/chrome.");
  process.exit(2);
}

const WAIT = 15000; // per-assertion wait (SPA load data async)
const GO_WAIT = 30000;

const args = [
  "--no-sandbox",
  "--disable-setuid-sandbox",
  "--disable-dev-shm-usage",
  "--disable-gpu",
];

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}

let browser = null;
let page = null;
let seededProviderId = null;

/* ---- Seed data lewat API (jalan offline; discovery model yg gagal
       ditangani server-side, tidak mempengaruhi test ini) ---- */
async function seedData(pg) {
  return pg.evaluate(async () => {
    async function post(url, body) {
      const r = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(body),
      });
      let j = null;
      try { j = await r.json(); } catch (e) { /* non-JSON */ }
      return { ok: r.ok, status: r.status, body: j };
    }
    const p = await post("/api/providers", {
      name: "e2e-anth",
      type: "anthropic",
      base_url: "https://api.anthropic.com",
      api_key: "sk-e2e",
    });
    if (!p.ok) {
      throw new Error("seed POST /api/providers -> HTTP " + p.status + " " + JSON.stringify(p.body));
    }
    let id = (p.body && p.body.id != null) ? p.body.id : null;
    if (id == null) {
      // Fallback: response shape beda -> cari nama di list GET /api/providers.
      const l = await fetch("/api/providers");
      const lj = await l.json().catch(() => null);
      const list = (lj && lj.data) || [];
      for (const it of list) { if (it && it.name === "e2e-anth") id = it.id; }
    }
    if (id == null) throw new Error("seed provider: id tidak ada di response POST maupun list");
    const a = await post("/api/accounts", {
      provider_id: id,
      label: "e2e-acc",
      auth_type: "api_key",
      api_key: "sk-acc",
    });
    if (!a.ok) {
      throw new Error("seed POST /api/accounts -> HTTP " + a.status + " " + JSON.stringify(a.body));
    }
    return String(id);
  });
}

/* ---- Cleanup best-effort: hapus account + provider seed (rerun bersih) ---- */
async function cleanupSeed() {
  if (!page || seededProviderId == null) return;
  try {
    await page.evaluate(async (pid) => {
      try {
        const r = await fetch("/api/accounts?provider_id=" + encodeURIComponent(pid));
        const j = await r.json().catch(() => null);
        const list = (j && j.data) || [];
        for (const a of list) {
          try {
            await fetch("/api/accounts/" + encodeURIComponent(a.id), { method: "DELETE" });
          } catch (e) { /* ignore */ }
        }
      } catch (e) { /* ignore */ }
      try {
        await fetch("/api/providers/" + encodeURIComponent(pid), { method: "DELETE" });
      } catch (e) { /* ignore */ }
    }, seededProviderId);
  } catch (e) {
    console.log("cleanup seed gagal (diabaikan): " + e.message);
  }
}

async function gotoView(pg, view) {
  await pg.click('.nav-item[data-view="' + view + '"]');
}

/* ---- B5.1: Providers -> detail -> Accounts ---- */
async function testProvidersAccounts(pg, providerId) {
  await gotoView(pg, "providers");
  const rowSel = '#provTableBody tr.prov-row[data-id="' + providerId + '"]';
  await pg.waitForSelector(rowSel, { visible: true, timeout: WAIT });
  const name = await pg.$eval(rowSel + " .prov-name", (el) => el.textContent);
  assert((name || "").indexOf("e2e-anth") !== -1,
    "sel nama provider seed salah: " + JSON.stringify(name));

  // Buka DETAIL via tombol discover di baris (openDetail -> loadAccounts).
  await pg.click(rowSel + " .js-disc");
  await pg.waitForFunction(() => {
    const d = document.getElementById("provDetail");
    return !!d && !d.hidden;
  }, { timeout: WAIT });

  // Accounts section merender account seed (label + auth_type di baris sama).
  await pg.waitForFunction(() => {
    return Array.prototype.some.call(
      document.querySelectorAll("#accountsBody tr.acc-row"),
      (tr) => {
        const t = tr.textContent || "";
        return t.indexOf("e2e-acc") !== -1 && t.indexOf("api_key") !== -1;
      }
    );
  }, { timeout: WAIT, polling: 300 });

  // Kontrol OAuth + form add-account ada di dalam detail.
  await pg.waitForSelector("#provConnectOAuthBtn", { visible: true, timeout: WAIT });
  for (const sel of ["#accountsTable", "#accLabel", "#accAuthType", "#accApiKey", "#accAddBtn"]) {
    assert(await pg.$(sel), "kontrol accounts hilang: " + sel);
  }
}

/* ---- B5.5: Usage & Quota ---- */
async function testUsageQuota(pg) {
  await gotoView(pg, "usage");
  await pg.waitForSelector("#quotaTableBody tr.quota-row", { visible: true, timeout: WAIT });
  await pg.waitForFunction(() => {
    return Array.prototype.some.call(
      document.querySelectorAll("#quotaTableBody tr.quota-row"),
      (tr) => (tr.textContent || "").indexOf("e2e-anth") !== -1
    );
  }, { timeout: WAIT, polling: 300 });
  // Area totals summary (4 stat card) hadir setelah /api/usage/summary render.
  await pg.waitForSelector("#usageTotals .usage-stat", { visible: true, timeout: WAIT });
}

/* ---- B5.6: Analytics + Export CSV ---- */
async function testAnalytics(pg) {
  await gotoView(pg, "analytics");
  // Trend chart CSS-bar: buckets kontinu (month -> 30 kolom) walau data kosong.
  await pg.waitForSelector("#analyticsChart .trend-col", { visible: true, timeout: WAIT });
  const cols = await pg.$$eval("#analyticsChart .trend-col", (els) => els.length);
  assert(cols >= 1, "trend chart tidak punya kolom (.trend-col): " + cols);
  await pg.waitForSelector("#analyticsExportBtn", { visible: true, timeout: WAIT });
}

/* ---- B5.7: Backup & Restore (export/import) ---- */
async function testBackupRestore(pg) {
  await gotoView(pg, "settings");
  await pg.waitForSelector("#exportBtn", { visible: true, timeout: WAIT });
  await pg.waitForSelector("#importFile", { timeout: WAIT });
  assert(await pg.$("#importBtn"), "tombol #importBtn hilang");
}

/* ================= main ================= */
let exitCode = 0;
try {
  browser = await puppeteer.launch({ executablePath: EXEC, headless: true, args });
  page = await browser.newPage();

  await page.goto(BASE + "/", { waitUntil: "domcontentloaded", timeout: GO_WAIT });
  const title = await page.title();
  assert(/aigate/i.test(title), "title tidak mengandung 'aigate': " + title);

  // Semua modul view sudah dieksekusi (app.js + usage.js + analytics.js, defer).
  await page.waitForFunction(() =>
    !!window.aigate && !!window.aigate.usage && !!window.aigate.analytics &&
    typeof window.aigate.loadAccounts === "function",
  { timeout: GO_WAIT });

  console.log("[b5-e2e] seed provider + account ...");
  seededProviderId = await seedData(page);
  console.log("[b5-e2e] seed OK (provider id=" + seededProviderId + ")");

  console.log("[b5-e2e] B5.1 providers -> accounts ...");
  await testProvidersAccounts(page, seededProviderId);
  console.log("[b5-e2e] B5.1 OK");

  console.log("[b5-e2e] B5.5 usage & quota ...");
  await testUsageQuota(page);
  console.log("[b5-e2e] B5.5 OK");

  console.log("[b5-e2e] B5.6 analytics + export csv ...");
  await testAnalytics(page);
  console.log("[b5-e2e] B5.6 OK");

  console.log("[b5-e2e] B5.7 backup & restore ...");
  await testBackupRestore(page);
  console.log("[b5-e2e] B5.7 OK");

  console.log("B5 E2E PASS: seed + B5.1 accounts + B5.5 quota + B5.6 analytics/csv + B5.7 backup");
} catch (e) {
  console.error("B5 E2E FAIL:", e.message);
  exitCode = 1;
} finally {
  await cleanupSeed();
  if (browser) {
    try { await browser.close(); } catch (e) { /* ignore */ }
  }
  process.exit(exitCode);
}
