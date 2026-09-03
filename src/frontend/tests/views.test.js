import { describe, it, expect } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { JSDOM } from "jsdom";

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

  it("Log Window has collapse toggle + severity filter + refresh", () => {
    expect(doc.getElementById("logCollapseBtn")).not.toBeNull();
    expect(doc.getElementById("logSeverity")).not.toBeNull();
    expect(doc.getElementById("logRefreshBtn")).not.toBeNull();
  });
});
