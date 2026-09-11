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
//   B5.1   : nav providers -> baris #provTableBody -> menu ⋮ -> item
//            [data-action="accounts"] ("Akun alternatif/sekunder", stage-4) ->
//            HALAMAN RINCI (view [data-view="provider-detail"] aktif, menu
//            "Penyedia" tetap sorot): kepala #provDetailTitle + badge,
//            Kartu A #pdApiKey (teks polos), Kartu B #pdStrategy +
//            #pdStrategySaveBtn, Kartu C #accList berisi .acc-card "e2e-acc"
//            dengan tombol ▲▼, Kartu D #provUsageTotals; modal akun #accModal
//            (#accLabel/#accAuthType/#accApiKey/#accPriority) lalu #accModal
//            ditutup lewat Kembali.
//            CATATAN stage-3: tab modal + tabel 6 kolom HILANG — akun jadi
//            kartu di halaman rinci, prioritas jadi tombol ▲▼ (PUT + renumber),
//            discovery tetap di belakang layar dengan satu baris status teks.
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

/* ---- B5.1: Providers -> halaman rinci -> kartu akun -> modal akun ---- */
async function testProvidersAccounts(pg, providerId) {
  await gotoView(pg, "providers");
  const rowSel = '#provTableBody tr.prov-row[data-id="' + providerId + '"]';
  await pg.waitForSelector(rowSel, { visible: true, timeout: WAIT });
  const name = await pg.$eval(rowSel + " .prov-name", (el) => el.textContent);
  assert((name || "").indexOf("e2e-anth") !== -1,
    "sel nama provider seed salah: " + JSON.stringify(name));
  // stage-3: kolom Model menjelaskan asal angkanya (hasil pencarian otomatis).
  const modelsTitle = await pg.$eval(rowSel + " .prov-models", (el) => el.getAttribute("title"));
  assert(modelsTitle && modelsTitle.length > 0, "tooltip kolom Model hilang");

  // Nama baris = teks biasa (stage-4): tidak ada tombol di dalam .prov-name.
  assert((await pg.$(rowSel + " .prov-name button")) === null,
    "sel nama masih berisi tombol (harusnya teks biasa)");
  // 1) Satu-satunya jalur masuk halaman rinci (stage-4) = menu ⋮ baris ->
  //    item "accounts" (app.js renderProviders -> data-action="accounts" ->
  //    openDetail). Menu singleton menempel di <body>, bukan di dalam baris.
  await pg.click(rowSel + " .js-row-menu");
  await pg.waitForSelector('.row-menu [data-action="accounts"]', { visible: true, timeout: WAIT });
  await pg.click('.row-menu [data-action="accounts"]');
  await pg.waitForFunction(() => {
    const v = document.querySelector('.view[data-view="provider-detail"]');
    return !!v && v.classList.contains("is-active");
  }, { timeout: WAIT });

  // Paritas nav tidak berubah: halaman rinci TANPA entri menu sendiri, jadi
  // "Penyedia" yang sorot.
  await pg.waitForFunction(() => {
    const n = document.querySelector('.nav-item[data-view="providers"]');
    return !!n && n.classList.contains("active");
  }, { timeout: WAIT });

  // 2) Kepala + Kartu A (baca-saja): nama + badge + kunci API teks polos.
  await pg.waitForFunction(() => {
    const t = document.getElementById("provDetailTitle");
    return !!t && (t.textContent || "").indexOf("e2e-anth") !== -1;
  }, { timeout: WAIT, polling: 300 });
  for (const sel of ["#provDetailBadge", "#provEditBtn", "#provDeleteBtn",
                     "#provDetailBackBtn", "#pdType", "#pdBaseUrl", "#pdApiKey"]) {
    assert(await pg.$(sel), "kontrol kepala/Kartu A hilang: " + sel);
  }
  const keyPlain = await pg.$eval("#pdApiKey", (el) => el.getAttribute("title") || el.textContent);
  assert(keyPlain === "sk-e2e", "Kartu A tidak menampilkan kunci apa adanya: " + keyPlain);

  // 3) Kartu B: strategi + simpan sendiri (satu permukaan untuk strategi).
  const strategy = await pg.$eval("#pdStrategy", (el) => el.value);
  assert(strategy === "fill-first" || strategy === "round-robin",
    "select strategi bukan enum kontrak: " + strategy);
  assert(await pg.$("#pdStrategySaveBtn"), "tombol simpan strategi hilang");

  // 4) Kartu C: akun dirender KARTU (bukan tabel), dengan posisi + ▲▼.
  await pg.waitForFunction(() => {
    return Array.prototype.some.call(
      document.querySelectorAll("#accList .acc-card"),
      (c) => (c.textContent || "").indexOf("e2e-acc") !== -1
    );
  }, { timeout: WAIT, polling: 300 });
  const noTable = await pg.$eval("#accList", (el) => !el.querySelector("table"));
  assert(noTable, "Kartu C masih berisi tabel");
  const move = await pg.$$eval("#accList .acc-card:first-child .acc-move button",
    (bs) => bs.map((b) => b.getAttribute("aria-label")));
  assert(move.length === 2, "tombol ▲/▼ tidak dua: " + JSON.stringify(move));
  assert(await pg.$("#provConnectOAuthBtn"), "tombol OAuth hilang dari Kartu C");
  assert(await pg.$("#pdAccReloadBtn"), "tombol muat ulang hilang dari Kartu C");

  // 5) Modal akun: satu permukaan khusus akun (label/jenis/kunci/prioritas).
  await pg.click("#pdAccAddBtn");
  await pg.waitForFunction(() => {
    const m = document.getElementById("accModal");
    return !!m && !m.hidden;
  }, { timeout: WAIT });
  for (const sel of ["#accLabel", "#accAuthType", "#accApiKey", "#accPriority", "#accAddBtn"]) {
    assert(await pg.$(sel), "kontrol modal akun hilang: " + sel);
  }
  await pg.click("#accCancelBtn");
  await pg.waitForFunction(() => {
    const m = document.getElementById("accModal");
    return !!m && m.hidden;
  }, { timeout: WAIT });

  // 6) Kartu D (B5.5) ikut pindah ke halaman rinci.
  assert(await pg.$("#provUsageTotals"), "Kartu D pemakaian hilang");

  // 7) "Kembali" -> daftar, dan daftar dibaca ulang.
  await pg.click("#provDetailBackBtn");
  await pg.waitForFunction(() => {
    const v = document.querySelector('.view[data-view="providers"]');
    return !!v && v.classList.contains("is-active");
  }, { timeout: WAIT });
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
