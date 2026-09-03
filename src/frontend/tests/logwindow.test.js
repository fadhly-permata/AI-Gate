import { describe, it, expect, beforeEach } from "vitest";

// i18n dict so window.I18N (and getStr resolution) is available — the collapse
// tests exercise applyLogCollapse/toggleLogCollapse which read i18n labels.
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

describe("Log Window is global + collapsible (B3.1)", () => {
  beforeEach(() => {
    localStorage.clear();
    document.body.innerHTML =
      '<div class="logwindow" id="logWindow">' +
        '<div class="logwindow-head">' +
          '<button id="logCollapseBtn"><i class="fa fa-chevron-up"></i></button>' +
        '</div>' +
        '<div class="logwindow-body">' +
          '<p id="logMsg"></p>' +
          '<table id="logTable"><tbody id="logTableBody"></tbody></table>' +
        '</div>' +
      '</div>';
  });

  it("is expanded by default and exposes toggle/state helpers", () => {
    expect(window.aigate.isLogCollapsed()).toBe(false);
    expect(typeof window.aigate.toggleLogCollapse).toBe("function");
    expect(typeof window.aigate.applyLogCollapse).toBe("function");
  });

  it("toggleLogCollapse flips state, toggles the class, and persists to localStorage", () => {
    window.aigate.toggleLogCollapse();
    expect(window.aigate.isLogCollapsed()).toBe(true);
    expect(document.getElementById("logWindow").classList.contains("logwindow-collapsed")).toBe(true);
    expect(localStorage.getItem("aigate.logCollapsed")).toBe("collapsed");

    window.aigate.toggleLogCollapse();
    expect(window.aigate.isLogCollapsed()).toBe(false);
    expect(localStorage.getItem("aigate.logCollapsed")).toBe("expanded");
  });

  it("applyLogCollapse(true) collapses and (false) expands via class", () => {
    window.aigate.applyLogCollapse(true);
    expect(document.getElementById("logWindow").classList.contains("logwindow-collapsed")).toBe(true);
    window.aigate.applyLogCollapse(false);
    expect(document.getElementById("logWindow").classList.contains("logwindow-collapsed")).toBe(false);
  });

  it("exposes auto-refresh controls that are safe to call repeatedly", () => {
    expect(typeof window.aigate.startLogAutoRefresh).toBe("function");
    expect(typeof window.aigate.stopLogAutoRefresh).toBe("function");
    // No timer running -> stop is a no-op and must not throw.
    expect(() => window.aigate.stopLogAutoRefresh()).not.toThrow();
  });
});

