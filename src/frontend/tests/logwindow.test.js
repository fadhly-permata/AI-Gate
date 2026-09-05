import { describe, it, expect, beforeEach } from "vitest";

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
      stacktrace: "Traceback..."
    });
  });

  it("applies safe defaults when fields are missing", () => {
    expect(window.aigate.formatLogRow({})).toEqual({
      id: undefined,
      timestamp: "",
      severity: "info",
      source: "",
      message: "",
      stacktrace: null
    });
    expect(window.aigate.formatLogRow(null).severity).toBe("info");
  });

  it("converts empty stacktrace to null", () => {
    const row = window.aigate.formatLogRow({ stacktrace: "" });
    expect(row.stacktrace).toBeNull();
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

