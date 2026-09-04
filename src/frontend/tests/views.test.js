import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { JSDOM } from "jsdom";

// i18n.js is a side-effect module: attaches window.I18N (no document access at
// load). Imported so the collapse-key regression guard can read the dicts.
import "../static/i18n.js";

const __dirname = dirname(fileURLToPath(import.meta.url));
const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
const dom = new JSDOM(html);
const doc = dom.window.document;

describe("index.html structure — missing views + global Log Window", () => {
  it("has view sections for combos, proxies, endpoints", () => {
    expect(doc.querySelector('[data-view="combos"]')).not.toBeNull();
    expect(doc.querySelector('[data-view="proxies"]')).not.toBeNull();
    expect(doc.querySelector('[data-view="endpoints"]')).not.toBeNull();
  });

  it("sidebar + bottom-nav link to the three new views", () => {
    ["combos", "proxies", "endpoints"].forEach(function (v) {
      expect(doc.querySelector('.nav-item[data-view="' + v + '"]')).not.toBeNull();
      expect(doc.querySelector('.bn-item[data-view="' + v + '"]')).not.toBeNull();
    });
  });

  it("Log Window is GLOBAL: present but not inside any .view (and not in terminal)", () => {
    const log = doc.getElementById("logWindow");
    expect(log).not.toBeNull();
    expect(log.closest(".view")).toBeNull();
    const term = doc.querySelector('[data-view="terminal"]');
    expect(term.contains(log)).toBe(false);
  });

  it("add/edit modals exist for the three new views", () => {
    expect(doc.getElementById("comboModal")).not.toBeNull();
    expect(doc.getElementById("poolModal")).not.toBeNull();
    expect(doc.getElementById("endpointModal")).not.toBeNull();
  });

  it("loads the three new module scripts (after app.js)", () => {
    const srcs = Array.from(doc.querySelectorAll("script[src]")).map(function (s) {
      return s.getAttribute("src");
    });
    expect(srcs).toContain("combos.js");
    expect(srcs).toContain("proxies.js");
    expect(srcs).toContain("endpoints.js");
    expect(srcs.indexOf("app.js")).toBeLessThan(srcs.indexOf("combos.js"));
  });

  it("Log Window keeps severity filter + refresh; the old collapse button is gone", () => {
    expect(doc.getElementById("logSeverity")).not.toBeNull();
    expect(doc.getElementById("logRefreshBtn")).not.toBeNull();
    expect(doc.getElementById("logCollapseBtn")).toBeNull();
  });

  it("topbar has a Log Window toggle placed BEFORE the theme toggle", () => {
    const right = doc.querySelector(".topbar-right");
    expect(right).not.toBeNull();
    const logBtn = right.querySelector("#logWindowToggle");
    const themeBtn = right.querySelector("#themeToggle");
    expect(logBtn).not.toBeNull();
    expect(themeBtn).not.toBeNull();
    // logWindowToggle must precede themeToggle in document order.
    const btns = Array.from(right.querySelectorAll("button"));
    expect(btns.indexOf(logBtn)).toBeLessThan(btns.indexOf(themeBtn));
    // Accessible + toggle semantics.
    expect(logBtn.getAttribute("type")).toBe("button");
    expect(logBtn.hasAttribute("aria-pressed")).toBe(true);
    expect(logBtn.hasAttribute("aria-label")).toBe(true);
  });
});

describe("terminal expand/collapse feature removed (regression guard)", () => {
  it("#termCollapseBtn is gone from the terminal header", () => {
    expect(doc.getElementById("termCollapseBtn")).toBeNull();
    // No element anywhere carries the removed i18n binding.
    expect(doc.querySelector('[data-i18n-aria="term.collapse"]')).toBeNull();
    expect(doc.querySelector('[data-i18n-aria="term.expand"]')).toBeNull();
  });

  it("terminal header title bar is KEPT (header + title still present)", () => {
    const header = doc.querySelector(".terminal-header");
    expect(header).not.toBeNull();
    expect(header.querySelector(".terminal-title")).not.toBeNull();
    expect(header.querySelector('[data-i18n="nav.terminal"]')).not.toBeNull();
  });

  it("term.collapse / term.expand i18n keys removed from BOTH locales (parity)", () => {
    expect(window.I18N.en["term.collapse"]).toBeUndefined();
    expect(window.I18N.en["term.expand"]).toBeUndefined();
    expect(window.I18N.id["term.collapse"]).toBeUndefined();
    expect(window.I18N.id["term.expand"]).toBeUndefined();
    // EN/ID key-set parity is preserved after the removal.
    const en = Object.keys(window.I18N.en);
    const id = Object.keys(window.I18N.id);
    expect(en.filter((k) => !id.includes(k))).toEqual([]);
    expect(id.filter((k) => !en.includes(k))).toEqual([]);
  });
});

