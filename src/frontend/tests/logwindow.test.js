import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// i18n dict so window.I18N (and getStr resolution) is available — the show/hide
// tests exercise applyLogVisible/toggleLogVisible which read i18n labels.
import "../static/i18n.js";
// app.js is an IIFE that attaches pure helpers onto window.aigate and runs
// init() against the (jsdom) document. Importing for side effects exposes the
// helpers we assert below.
import "../static/app.js";

describe("severityClass (B3.1)", () => {
  it("maps known severities to CSS classes", () => {
    expect(window.aigate.severityClass("info")).toBe("sev-info");
    expect(window.aigate.severityClass("warning")).toBe("sev-warning");
    expect(window.aigate.severityClass("error")).toBe("sev-error");
  });

  it("is case-insensitive", () => {
    expect(window.aigate.severityClass("INFO")).toBe("sev-info");
    expect(window.aigate.severityClass("Error")).toBe("sev-error");
  });

  it("falls back to sev-unknown for empty/unknown values", () => {
    expect(window.aigate.severityClass("")).toBe("sev-unknown");
    expect(window.aigate.severityClass(null)).toBe("sev-unknown");
    expect(window.aigate.severityClass(undefined)).toBe("sev-unknown");
    expect(window.aigate.severityClass("debug")).toBe("sev-unknown");
  });
});

describe("formatLogRow (B3.1)", () => {
  it("normalizes a full LogEntry", () => {
    const entry = {
      id: "abc",
      timestamp: "2026-09-03T10:00:00Z",
      severity: "error",
      source: "gateway",
      message: "boom",
      stacktrace: "Traceback..."
    };
    expect(window.aigate.formatLogRow(entry)).toEqual({
      id: "abc",
      timestamp: "2026-09-03T10:00:00Z",
      severity: "error",
      source: "gateway",
      message: "boom",
      stacktrace: "Traceback...",
      resolved: false
    });
  });

  it("applies safe defaults when fields are missing", () => {
    expect(window.aigate.formatLogRow({})).toEqual({
      id: undefined,
      timestamp: "",
      severity: "info",
      source: "",
      message: "",
      stacktrace: null,
      resolved: false
    });
    expect(window.aigate.formatLogRow(null).severity).toBe("info");
  });

  it("converts empty stacktrace to null", () => {
    const row = window.aigate.formatLogRow({ stacktrace: "" });
    expect(row.stacktrace).toBeNull();
  });

  it("normalizes resolved: missing/undefined -> false, true passes through (T2)", () => {
    expect(window.aigate.formatLogRow({}).resolved).toBe(false);
    expect(window.aigate.formatLogRow({ resolved: undefined }).resolved).toBe(false);
    expect(window.aigate.formatLogRow({ resolved: false }).resolved).toBe(false);
    expect(window.aigate.formatLogRow({ resolved: true }).resolved).toBe(true);
  });
});

describe("buildLogsQuery (B3.1)", () => {
  it("returns empty string for 'all' severity and no limit", () => {
    expect(window.aigate.buildLogsQuery("all", undefined)).toBe("");
    expect(window.aigate.buildLogsQuery(undefined, undefined)).toBe("");
  });

  it("encodes a single severity", () => {
    expect(window.aigate.buildLogsQuery("error", undefined)).toBe("?severity=error");
  });

  it("adds limit when a positive number", () => {
    expect(window.aigate.buildLogsQuery("warning", 50)).toBe("?severity=warning&limit=50");
    expect(window.aigate.buildLogsQuery("all", 100)).toBe("?limit=100");
  });

  it("URL-encodes severity values", () => {
    expect(window.aigate.buildLogsQuery("info,warning", 10))
      .toBe("?severity=info%2Cwarning&limit=10");
  });

  it("ignores invalid/zero limits", () => {
    expect(window.aigate.buildLogsQuery("error", 0)).toBe("?severity=error");
    expect(window.aigate.buildLogsQuery("error", "abc")).toBe("?severity=error");
  });
});

describe("Log Window is global + show/hide (B3.1 rework)", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.className = "";
    document.documentElement.style.removeProperty("--log-h");
    document.body.innerHTML =
      '<header class="topbar"><div class="topbar-right">' +
        '<button id="logWindowToggle" class="icon-btn" type="button" aria-pressed="true"></button>' +
        '<button id="themeToggle" class="icon-btn" type="button"></button>' +
      '</div></header>' +
      '<main class="workspace"></main>' +
      '<div class="logwindow" id="logWindow">' +
        '<div class="logwindow-head">' +
          '<select id="logSeverity"></select>' +
          '<button id="logRefreshBtn"></button>' +
        '</div>' +
        '<div class="logwindow-body">' +
          '<p id="logMsg"></p>' +
          '<table id="logTable"><tbody id="logTableBody"></tbody></table>' +
        '</div>' +
      '</div>';
  });

  it("is visible by default and exposes toggle/state helpers", () => {
    expect(window.aigate.isLogVisible()).toBe(true);
    expect(typeof window.aigate.toggleLogVisible).toBe("function");
    expect(typeof window.aigate.applyLogVisible).toBe("function");
    expect(typeof window.aigate.measureLogHeight).toBe("function");
  });

  it("the old collapse API is gone", () => {
    expect(window.aigate.toggleLogCollapse).toBeUndefined();
    expect(window.aigate.applyLogCollapse).toBeUndefined();
    expect(window.aigate.isLogCollapsed).toBeUndefined();
  });

  it("toggleLogVisible hides the panel, drops body.log-visible, and persists", () => {
    // Start from a known-visible state.
    window.aigate.applyLogVisible(true);
    expect(document.getElementById("logWindow").hidden).toBe(false);
    expect(document.body.classList.contains("log-visible")).toBe(true);

    window.aigate.toggleLogVisible(); // -> hidden
    expect(window.aigate.isLogVisible()).toBe(false);
    expect(document.getElementById("logWindow").hidden).toBe(true);
    expect(document.body.classList.contains("log-visible")).toBe(false);
    expect(localStorage.getItem("aigate.logVisible")).toBe("0");
    // Hidden -> no reserved space.
    expect(document.documentElement.style.getPropertyValue("--log-h")).toBe("0px");

    window.aigate.toggleLogVisible(); // -> visible again
    expect(window.aigate.isLogVisible()).toBe(true);
    expect(document.getElementById("logWindow").hidden).toBe(false);
    expect(document.body.classList.contains("log-visible")).toBe(true);
    expect(localStorage.getItem("aigate.logVisible")).toBe("1");
  });

  it("applyLogVisible(true) sets body.log-visible + a --log-h reservation", () => {
    window.aigate.applyLogVisible(true);
    expect(document.body.classList.contains("log-visible")).toBe(true);
    expect(document.getElementById("logWindow").hidden).toBe(false);
    // The reservation var is always written when shown (jsdom measures 0px, but
    // the property must be present so the workspace padding rule has a value).
    expect(document.documentElement.style.getPropertyValue("--log-h")).toBe("0px");
  });

  it("applyLogVisible(false) removes the class and zeroes the reservation", () => {
    window.aigate.applyLogVisible(true);
    window.aigate.applyLogVisible(false);
    expect(document.body.classList.contains("log-visible")).toBe(false);
    expect(document.getElementById("logWindow").hidden).toBe(true);
    expect(document.documentElement.style.getPropertyValue("--log-h")).toBe("0px");
  });

  it("reflects state on the header toggle (aria-pressed + label)", () => {
    const btn = document.getElementById("logWindowToggle");
    window.aigate.applyLogVisible(true);
    expect(btn.getAttribute("aria-pressed")).toBe("true");
    expect(btn.getAttribute("aria-label")).toBe(window.I18N.en["log.hide"]);
    window.aigate.applyLogVisible(false);
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    expect(btn.getAttribute("aria-label")).toBe(window.I18N.en["log.show"]);
  });

  it("exposes auto-refresh controls that are safe to call repeatedly", () => {
    expect(typeof window.aigate.startLogAutoRefresh).toBe("function");
    expect(typeof window.aigate.stopLogAutoRefresh).toBe("function");
    // No timer running -> stop is a no-op and must not throw.
    expect(() => window.aigate.stopLogAutoRefresh()).not.toThrow();
  });
});

/* ===== T2 log cleanup ===== */

// DOM fixture mirroring the logwindow-controls block + clear dialog + body
// from index.html.
function setupLogDom() {
  document.body.innerHTML =
    '<div class="logwindow" id="logWindow">' +
      '<div class="logwindow-head">' +
        '<select id="logSeverity">' +
          '<option value="all">All</option>' +
          '<option value="info">Info</option>' +
          '<option value="warning">Warning</option>' +
          '<option value="error">Error</option>' +
        "</select>" +
        '<button id="logRefreshBtn" type="button"></button>' +
        '<button id="logClearBtn" type="button"></button>' +
        '<button id="logShowResolvedBtn" type="button" aria-pressed="false"></button>' +
        '<button id="logResolveAllBtn" type="button"></button>' +
      "</div>" +
      '<div class="logwindow-body">' +
        '<p id="logMsg"></p>' +
        '<table id="logTable"><tbody id="logTableBody"></tbody></table>' +
      "</div>" +
    "</div>" +
    // Clear-confirm dialog (scope lives here, not in the filter select).
    '<div class="modal-overlay" id="logClearModal" hidden>' +
      '<div class="modal">' +
        '<select id="logClearScope">' +
          '<option value="warning,error" selected></option>' +
          '<option value="all"></option>' +
        "</select>" +
        '<button id="logClearConfirmBtn" type="button"></button>' +
        '<button id="logClearCancelBtn" type="button"></button>' +
      "</div>" +
    "</div>";
}

// Stub global fetch: routes to handler by (method, url); records calls.
function stubFetch(route) {
  const calls = [];
  const fn = vi.fn(function (url, opts) {
    opts = opts || {};
    const method = (opts.method || "GET").toUpperCase();
    calls.push({ method: method, url: String(url), opts: opts });
    const handler = route ? route(method, String(url)) : null;
    if (!handler) {
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({ data: [] }) });
    }
    // { __error: true, status, body } -> non-2xx response (error-path tests).
    if (handler.__error) {
      return Promise.resolve({
        ok: false,
        status: handler.status || 500,
        headers: { get: () => "application/json" },
        json: () => Promise.resolve(handler.body || {})
      });
    }
    return Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(handler)
    });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

function flush() {
  return new Promise((res) => setTimeout(res, 0));
}

describe("buildClearLogsQuery (T2)", () => {
  it("wipe-all -> ?confirm=all", () => {
    expect(window.aigate.buildClearLogsQuery("all")).toBe("?confirm=all");
  });

  it("filtered -> ?severity=<value> (comma list URL-encoded)", () => {
    expect(window.aigate.buildClearLogsQuery("warning,error"))
      .toBe("?severity=warning%2Cerror");
  });
});

describe("renderLogs resolved rendering (T2)", () => {
  beforeEach(() => {
    localStorage.clear();
    setupLogDom();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolved rows get .log-row-resolved + resolved badge", () => {
    window.aigate.renderLogs([
      { id: "r1", severity: "error", message: "boom", resolved: true }
    ]);
    const tr = document.querySelector("#logTableBody tr");
    expect(tr.className).toBe("log-row-resolved");
    const badges = Array.from(tr.querySelectorAll("td:nth-child(2) .badge"));
    expect(badges.some((b) => b.classList.contains("log-resolved-badge"))).toBe(true);
    expect(badges.find((b) => b.classList.contains("log-resolved-badge")).textContent)
      .toBe(window.I18N.en["log.resolved"]);
    // Resolved rows get NO resolve button.
    expect(tr.querySelector(".log-resolve-btn")).toBeNull();
  });

  it("unresolved warning row gets a .log-resolve-btn; info row does not", () => {
    window.aigate.renderLogs([
      { id: "w1", severity: "warning", message: "meh" },
      { id: "i1", severity: "info", message: "fyi" }
    ]);
    const rows = Array.from(document.querySelectorAll("#logTableBody tr"));
    expect(rows[0].querySelector(".log-resolve-btn")).not.toBeNull();
    expect(rows[0].querySelector(".log-resolve-btn").getAttribute("data-id")).toBe("w1");
    expect(rows[1].querySelector(".log-resolve-btn")).toBeNull();
    // Case-insensitive severity: ERROR is resolvable too.
    window.aigate.renderLogs([{ id: "e1", severity: "ERROR", message: "x" }]);
    expect(document.querySelector("#logTableBody tr .log-resolve-btn")).not.toBeNull();
  });
});

describe("clearLogs dialog flow (T2)", () => {
  beforeEach(() => {
    localStorage.clear();
    setupLogDom();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("clearLogs() opens dialog with 'Warnings + Errors' preselected; no request yet", () => {
    const calls = stubFetch();
    window.aigate.clearLogs();
    const modal = document.getElementById("logClearModal");
    expect(modal.hidden).toBe(false);
    expect(document.getElementById("logClearScope").value).toBe("warning,error");
    expect(calls.length).toBe(0);
  });

  it("confirm (default scope) -> DELETE ?severity=warning,error + 'Deleted N' + reload", async () => {
    const calls = stubFetch((method, url) => {
      if (method === "DELETE" && url === "/api/logs?severity=warning%2Cerror") return { deleted: 7 };
      if (method === "GET" && url.startsWith("/api/logs")) return { data: [] };
      return null;
    });
    window.aigate.clearLogs();
    window.aigate.confirmClearLogs();
    await flush();
    const modal = document.getElementById("logClearModal");
    expect(modal.hidden).toBe(true); // dialog closed before/while deleting
    const del = calls.find((c) => c.method === "DELETE");
    expect(del).toBeTruthy();
    expect(del.url).toBe("/api/logs?severity=warning%2Cerror");
    expect(document.getElementById("logMsg").textContent)
      .toBe(window.I18N.en["log.cleared"].replace("{n}", "7"));
    // loadLogs() re-fetch followed the delete.
    expect(calls.some((c) => c.method === "GET" && c.url.startsWith("/api/logs"))).toBe(true);
  });

  it("scope=all -> DELETE ?confirm=all (backend wipe-all guard)", async () => {
    const calls = stubFetch((method, url) => {
      if (method === "DELETE" && url === "/api/logs?confirm=all") return { deleted: 42 };
      if (method === "GET" && url.startsWith("/api/logs")) return { data: [] };
      return null;
    });
    window.aigate.clearLogs();
    document.getElementById("logClearScope").value = "all";
    window.aigate.confirmClearLogs();
    await flush();
    const del = calls.find((c) => c.method === "DELETE");
    expect(del.url).toBe("/api/logs?confirm=all");
    expect(document.getElementById("logMsg").textContent)
      .toBe(window.I18N.en["log.cleared"].replace("{n}", "42"));
  });

  it("cancel -> dialog closes, no request", async () => {
    const calls = stubFetch();
    window.aigate.clearLogs();
    window.aigate.cancelClearLogs();
    await flush();
    expect(document.getElementById("logClearModal").hidden).toBe(true);
    expect(calls.length).toBe(0);
    expect(document.getElementById("logMsg").textContent).toBe("");
  });

  it("missing dialog DOM -> clearLogs is a no-op (no request)", async () => {
    document.getElementById("logClearModal").remove();
    const calls = stubFetch();
    expect(() => window.aigate.clearLogs()).not.toThrow();
    await flush();
    expect(calls.length).toBe(0);
  });

  it("DELETE failure -> error message via existing error pattern", async () => {
    stubFetch((method, url) => {
      if (method === "DELETE" && url === "/api/logs?severity=warning%2Cerror") {
        return { __error: true, status: 500, body: { error: { message: "boom" } } };
      }
      if (method === "GET" && url.startsWith("/api/logs")) return { data: [] };
      return null;
    });
    window.aigate.clearLogs();
    window.aigate.confirmClearLogs();
    await flush();
    expect(document.getElementById("logMsg").textContent).toContain("boom");
    expect(document.getElementById("logMsg").className).toContain("settings-msg-error");
  });
});

describe("show-resolved toggle (T2)", () => {
  beforeEach(() => {
    localStorage.clear();
    setupLogDom();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("default off; toggling flips aria-pressed + persists", () => {
    expect(window.aigate.isShowResolved()).toBe(false);
    expect(document.getElementById("logShowResolvedBtn").getAttribute("aria-pressed")).toBe("false");
    window.aigate.toggleShowResolved();
    expect(window.aigate.isShowResolved()).toBe(true);
    expect(localStorage.getItem("aigate.logShowResolved")).toBe("1");
    expect(document.getElementById("logShowResolvedBtn").getAttribute("aria-pressed")).toBe("true");
    expect(document.getElementById("logShowResolvedBtn").getAttribute("aria-label"))
      .toBe(window.I18N.en["log.show_resolved"]);
    window.aigate.toggleShowResolved();
    expect(window.aigate.isShowResolved()).toBe(false);
    expect(localStorage.getItem("aigate.logShowResolved")).toBe("0");
  });

  it("on -> next GET URL carries show_resolved=true", async () => {
    window.aigate.toggleShowResolved();
    const calls = stubFetch((method) => {
      if (method === "GET") return { data: [] };
      return null;
    });
    window.aigate.loadLogs();
    await flush();
    const get = calls.find((c) => c.method === "GET");
    expect(get.url).toContain("show_resolved=true");
  });

  it("off -> GET URL omits show_resolved", async () => {
    const calls = stubFetch((method) => {
      if (method === "GET") return { data: [] };
      return null;
    });
    window.aigate.loadLogs();
    await flush();
    const get = calls.find((c) => c.method === "GET");
    expect(get.url).not.toContain("show_resolved");
  });
});

describe("resolve flows (T2)", () => {
  beforeEach(() => {
    localStorage.clear();
    setupLogDom();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolve-all POSTs ids of rendered unresolved warning/error rows only", async () => {
    window.aigate.renderLogs([
      { id: "w1", severity: "warning" },
      { id: "e1", severity: "error" },
      { id: "i1", severity: "info" },
      { id: "w2", severity: "warning", resolved: true }
    ]);
    const calls = stubFetch((method, url) => {
      if (method === "POST" && url === "/api/logs/resolve") return { resolved: 2 };
      if (method === "GET" && url.startsWith("/api/logs")) return { data: [] };
      return null;
    });
    window.aigate.resolveAllLogs();
    await flush();
    const post = calls.find((c) => c.method === "POST");
    expect(post).toBeTruthy();
    expect(post.url).toBe("/api/logs/resolve");
    expect(JSON.parse(post.opts.body)).toEqual({ ids: ["w1", "e1"] });
    expect(document.getElementById("logMsg").textContent)
      .toBe(window.I18N.en["log.resolved_n"].replace("{n}", "2"));
  });

  it("resolve-all with no candidates -> no request", async () => {
    window.aigate.renderLogs([{ id: "i1", severity: "info" }]);
    const calls = stubFetch();
    window.aigate.resolveAllLogs();
    await flush();
    expect(calls.length).toBe(0);
  });

  it("resolveLog POSTs /api/logs/{id}/resolve + reloads", async () => {
    window.aigate.renderLogs([{ id: "w1", severity: "warning" }]);
    const calls = stubFetch((method, url) => {
      if (method === "POST" && url === "/api/logs/w1/resolve") return { resolved: 1 };
      if (method === "GET" && url.startsWith("/api/logs")) return { data: [] };
      return null;
    });
    window.aigate.resolveLog("w1");
    await flush();
    const post = calls.find((c) => c.method === "POST");
    expect(post.url).toBe("/api/logs/w1/resolve");
    expect(calls.some((c) => c.method === "GET")).toBe(true);
  });
});

