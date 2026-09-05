import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { JSDOM } from "jsdom";

// i18n dict (window.I18N) so getStr() resolves labels during render.
import "../static/i18n.js";
// app.js exposes window.aigate.exportSettings / importSettingsFromFile /
// renderImportResult (B5.7 Backup & Restore).
import "../static/app.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Let async .then chains resolve on real timers.
const flush = () => new Promise((r) => setTimeout(r, 0));

// REAL export doc shape (verbatim from the be-dev receipt).
const EXPORT_DOC = {
  aigate_export: { version: 1, exported_at: "2026-09-04T00:00:00", app_version: "0.0.1" },
  providers: [{ id: 1, name: "openai", api_key: "sk-secret" }],
  provider_accounts: [],
  provider_models: [],
  proxy_pools: [],
  proxy_nodes: [],
  combos: [],
  combo_members: [],
  endpoints: [],
  endpoint_bindings: [],
  cli_tool_groups: [],
  cli_tools: [],
  settings: [{ key: "port", value: "8080" }]
};

// Build the Backup & Restore DOM the export/import helpers expect. Also carries
// the settings form + provider table so reloadAfterImport()'s loaders run clean.
function withBackupDom() {
  document.body.innerHTML =
    '<form id="settingsForm">' +
      '<input type="number" id="setPort" value="8080" />' +
      '<input type="checkbox" id="setDevMode" />' +
      '<select id="setTheme"><option value="light" selected>Light</option></select>' +
      '<select id="setLocale"><option value="en" selected>EN</option></select>' +
      '<p id="settingsMsg"></p>' +
    '</form>' +
    '<div class="card backup-card">' +
      '<a id="exportBtn" href="/api/settings/export">Export</a>' +
      '<select id="importMode">' +
        '<option value="replace" selected>Replace</option>' +
        '<option value="merge">Merge</option>' +
      '</select>' +
      '<input type="file" id="importFile" />' +
      '<button id="importBtn" type="button">Import</button>' +
      '<p id="backupMsg" class="settings-msg" role="status"></p>' +
    '</div>' +
    '<table><tbody id="provTableBody"></tbody></table>';
}

// Stub FileReader: readAsText resolves with the file's __text (or an error).
function stubFileReader(opts) {
  opts = opts || {};
  vi.stubGlobal("FileReader", function FakeFileReader() {
    var self = this;
    this.readAsText = function (file) {
      setTimeout(function () {
        if (opts.error) {
          self.error = new Error(opts.error);
          if (typeof self.onerror === "function") self.onerror();
          return;
        }
        self.result = (file && file.__text != null) ? file.__text : "";
        if (typeof self.onload === "function") self.onload();
      }, 0);
    };
  });
}

// Stub fetch: POST /api/settings/import returns importResult (or an error
// status); every other URL (the reload GETs) returns a benign empty list.
function stubImportFetch(importResult, opts) {
  opts = opts || {};
  const calls = [];
  vi.stubGlobal("fetch", vi.fn((url, o) => {
    calls.push({ url, opts: o });
    if (String(url).indexOf("/api/settings/import") === 0) {
      if (opts.importStatus) {
        return Promise.resolve({
          ok: false, status: opts.importStatus,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve(opts.importBody || {})
        });
      }
      return Promise.resolve({
        ok: true, status: 200,
        headers: { get: () => "application/json" },
        json: () => Promise.resolve(importResult)
      });
    }
    return Promise.resolve({
      ok: true, status: 200,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ data: [] })
    });
  }));
  return calls;
}

const fakeFile = (text) => ({ name: "aigate-settings.json", __text: text });

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.innerHTML = "";
});

describe("exportSettings (B5.7)", () => {
  beforeEach(() => { withBackupDom(); });

  it("triggers a download anchored at /api/settings/export + shows status", () => {
    const clicked = [];
    const spy = vi.spyOn(window.HTMLElement.prototype, "click").mockImplementation(function () {
      clicked.push(this.getAttribute("href"));
    });

    const url = window.aigate.exportSettings();

    expect(url).toBe("/api/settings/export");
    expect(clicked).toContain("/api/settings/export");
    spy.mockRestore();

    const msg = document.getElementById("backupMsg");
    expect(msg.textContent).toContain("Export started");
    expect(msg.className).toContain("settings-msg-ok");
  });
});

describe("importSettingsFromFile (B5.7)", () => {
  beforeEach(() => { withBackupDom(); });

  it("reads + confirms + POSTs the parsed doc, then shows per-table counts", async () => {
    window.confirm = vi.fn(() => true);
    stubFileReader();
    const calls = stubImportFetch({ ok: true, imported: { providers: 2, settings: 5 } });

    const result = await window.aigate.importSettingsFromFile(fakeFile(JSON.stringify(EXPORT_DOC)));

    expect(window.confirm).toHaveBeenCalled();
    const post = calls.find((c) =>
      c.opts && c.opts.method === "POST" &&
      String(c.url).indexOf("/api/settings/import") === 0);
    expect(post).toBeTruthy();
    // The raw export doc is POSTed verbatim (plaintext secrets intended, R11).
    expect(JSON.parse(post.opts.body)).toEqual(EXPORT_DOC);
    expect(post.url).toContain("mode=replace");
    expect(post.opts.headers["Content-Type"]).toBe("application/json");

    expect(result.ok).toBe(true);
    expect(result.imported.providers).toBe(2);

    const msg = document.getElementById("backupMsg");
    expect(msg.textContent).toContain("2");
    expect(msg.textContent).toContain("5");
    expect(msg.className).toContain("settings-msg-ok");
  });

  it("merge mode POSTs with ?mode=merge", async () => {
    document.getElementById("importMode").value = "merge";
    window.confirm = vi.fn(() => true);
    stubFileReader();
    const calls = stubImportFetch({ ok: true, imported: { providers: 1 } });

    await window.aigate.importSettingsFromFile(fakeFile(JSON.stringify(EXPORT_DOC)));

    const post = calls.find((c) => c.opts && c.opts.method === "POST");
    expect(post.url).toContain("mode=merge");
    // merge uses its own (non-destructive) confirm copy
    expect(window.confirm.mock.calls[0][0]).toContain("merge");
  });

  it("bad JSON -> error status, no confirm, no POST", async () => {
    window.confirm = vi.fn(() => true);
    stubFileReader();
    const calls = stubImportFetch({ ok: true, imported: {} });

    const result = await window.aigate.importSettingsFromFile(fakeFile("{ not json "));

    expect(result.ok).toBe(false);
    expect(result.error).toBe("invalid_json");
    expect(window.confirm).not.toHaveBeenCalled();
    expect(calls.some((c) => c.opts && c.opts.method === "POST")).toBe(false);
    const msg = document.getElementById("backupMsg");
    expect(msg.textContent).toContain("Invalid file");
    expect(msg.className).toContain("settings-msg-error");
  });

  it("confirm=false -> no POST", async () => {
    window.confirm = vi.fn(() => false);
    stubFileReader();
    const calls = stubImportFetch({ ok: true, imported: {} });

    const result = await window.aigate.importSettingsFromFile(fakeFile(JSON.stringify(EXPORT_DOC)));

    expect(window.confirm).toHaveBeenCalled();
    expect(result.ok).toBe(false);
    expect(result.cancelled).toBe(true);
    expect(calls.some((c) => c.opts && c.opts.method === "POST")).toBe(false);
  });

  it("backend 400 invalid_format -> 'invalid file' status", async () => {
    window.confirm = vi.fn(() => true);
    stubFileReader();
    stubImportFetch(null, {
      importStatus: 400,
      importBody: { ok: false, error: "invalid_format" }
    });

    const result = await window.aigate.importSettingsFromFile(fakeFile(JSON.stringify(EXPORT_DOC)));

    expect(result.ok).toBe(false);
    expect(result.error).toBe("invalid_format");
    const msg = document.getElementById("backupMsg");
    expect(msg.textContent).toContain("Invalid file");
    expect(msg.className).toContain("settings-msg-error");
  });

  it("backend 500 -> error status carrying the reason (ADR-011)", async () => {
    window.confirm = vi.fn(() => true);
    stubFileReader();
    stubImportFetch(null, {
      importStatus: 500,
      importBody: { ok: false, error: "db_locked" }
    });

    const result = await window.aigate.importSettingsFromFile(fakeFile(JSON.stringify(EXPORT_DOC)));

    expect(result.ok).toBe(false);
    expect(result.error).toBe("db_locked");
    const msg = document.getElementById("backupMsg");
    expect(msg.textContent).toContain("db_locked");
    expect(msg.className).toContain("settings-msg-error");
  });

  it("FileReader error -> error status, no POST", async () => {
    window.confirm = vi.fn(() => true);
    stubFileReader({ error: "read failure" });
    const calls = stubImportFetch({ ok: true, imported: {} });

    const result = await window.aigate.importSettingsFromFile(fakeFile("ignored"));

    expect(result.ok).toBe(false);
    expect(calls.some((c) => c.opts && c.opts.method === "POST")).toBe(false);
    expect(document.getElementById("backupMsg").className).toContain("settings-msg-error");
  });
});

describe("renderImportResult (pure)", () => {
  it("formats the imported counts into a status string", () => {
    const s = window.aigate.renderImportResult({ ok: true, imported: { providers: 2, settings: 5 } });
    expect(s).toContain("2");
    expect(s).toContain("5");
    expect(s).toContain("Import complete");
  });

  it("non-ok / missing imported -> generic error string", () => {
    expect(window.aigate.renderImportResult({ ok: false })).toContain("Import failed");
    expect(window.aigate.renderImportResult(null)).toContain("Import failed");
  });
});

describe("index.html wiring (B5.7 structure)", () => {
  const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
  const dom = new JSDOM(html);
  const doc = dom.window.document;

  it("settings view carries the Backup & Restore section + controls", () => {
    const view = doc.querySelector('.view[data-view="settings"]');
    expect(view).not.toBeNull();
    expect(view.querySelector('[data-i18n="settings.backup.title"]')).not.toBeNull();
    ["exportBtn", "importMode", "importFile", "importBtn", "backupMsg"]
      .forEach((id) => expect(view.querySelector("#" + id)).not.toBeNull());
  });

  it("export anchor points at /api/settings/export; file input accepts JSON", () => {
    const a = doc.querySelector("#exportBtn");
    expect(a.getAttribute("href")).toBe("/api/settings/export");
    const file = doc.querySelector("#importFile");
    expect(file.getAttribute("type")).toBe("file");
    expect(file.getAttribute("accept")).toBe("application/json");
  });
});

describe("i18n backup/export/import keys (EN/ID parity)", () => {
  it("every settings.backup/export/import key exists in both dicts", () => {
    const enKeys = Object.keys(window.I18N.en).filter(
      (k) => k.indexOf("settings.backup.") === 0 ||
             k.indexOf("settings.export") === 0 ||
             k.indexOf("settings.import") === 0);
    expect(enKeys.length).toBeGreaterThanOrEqual(15);
    enKeys.forEach((k) => expect(window.I18N.id[k]).toBeDefined());
    expect(window.I18N.en["settings.backup.title"]).toBe("Backup & Restore (local)");
    expect(window.I18N.id["settings.backup.title"]).toBe("Cadangkan & Pulihkan (lokal)");
    expect(window.I18N.en["settings.export.ok"]).toBe("Export started.");
    expect(window.I18N.id["settings.import.confirm"]).toContain("Ganti");
  });
});
