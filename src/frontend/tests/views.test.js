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

// CSS source assertions (same approach as terminal_layout.test.js): the sticky
// behaviour lives entirely in the stylesheet, so jsdom cannot exercise it and
// the rule text is the contract.
const cssRaw = readFileSync(join(__dirname, "..", "static", "styles.css"), "utf8");
const css = cssRaw.replace(/\/\*[\s\S]*?\*\//g, "");
function ruleBlock(selectorRe) {
  const m = css.match(selectorRe);
  return m ? m[0] : null;
}

describe("index.html structure — missing views + global Log Window", () => {
  it("groups sidebar items by user need without changing data-view values", () => {
    const groups = [
      ["nav.group.gateway", ["providers", "combos", "proxies", "endpoints"]],
      ["nav.group.operations", ["terminal", "cli"]],
      ["nav.group.insights", ["usage", "analytics"]],
      ["nav.group.system", ["settings"]]
    ];
    const sections = Array.from(doc.querySelectorAll(".nav-section"));
    expect(sections).toHaveLength(groups.length);
    groups.forEach(function (group, index) {
      const section = sections[index];
      expect(section.querySelector(".nav-section-heading").getAttribute("data-i18n")).toBe(group[0]);
      expect(Array.from(section.querySelectorAll(".nav-item")).map(function (item) {
        return item.getAttribute("data-view");
      })).toEqual(group[1]);
    });
  });

  it("keeps section headings localized in EN and ID", () => {
    ["gateway", "operations", "insights", "system"].forEach(function (group) {
      expect(window.I18N.en["nav.group." + group]).toBeTruthy();
      expect(window.I18N.id["nav.group." + group]).toBeTruthy();
    });
  });

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

describe("terminal container chrome removed — flattened view (regression guard)", () => {
  it("#termCollapseBtn is gone (collapse feature removed)", () => {
    expect(doc.getElementById("termCollapseBtn")).toBeNull();
    // No element anywhere carries the removed i18n binding.
    expect(doc.querySelector('[data-i18n-aria="term.collapse"]')).toBeNull();
    expect(doc.querySelector('[data-i18n-aria="term.expand"]')).toBeNull();
  });

  it("terminal view is FLATTENED: no card / pane / header wrappers", () => {
    const term = doc.querySelector('.view[data-view="terminal"]');
    expect(term).not.toBeNull();
    expect(term.classList.contains("terminal-view")).toBe(true);
    expect(term.querySelector(".terminal-card")).toBeNull();
    expect(term.querySelector(".terminal-pane")).toBeNull();
    expect(term.querySelector(".terminal-header")).toBeNull();
    expect(doc.getElementById("terminalPane")).toBeNull();
    expect(doc.getElementById("terminalHeader")).toBeNull();
    // #terminalBody is a DIRECT child of the view — just toolbar + stage.
    const body = doc.getElementById("terminalBody");
    expect(body).not.toBeNull();
    expect(body.parentElement).toBe(term);
    expect(body.querySelector(".term-toolbar")).not.toBeNull();
    expect(body.querySelector(".term-stage")).not.toBeNull();
  });

  it("JS-referenced terminal IDs survive the flattening", () => {
    ["terminalBody", "termStage", "termContainers", "termTabBar", "termNewTab",
     "termFloating", "termFullscreen", "termPaste", "termSettings", "termMenuTui", "termMenuKeepAwake"].forEach(function (id) {
      expect(doc.getElementById(id), "#" + id + " present").not.toBeNull();
    });
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

/* ===== Sidebar footer: link to the aigate repository, pinned to the bottom =====
   Contract: an external <a> (never a view switch), wrapped in .sidebar-footer so
   it can stick to the panel bottom, styled off the existing .nav-item rules,
   localized through nav.repo, and inert on phones (sidebar stays hidden). */
describe("sidebar Repository link — sticky footer", () => {
  const REPO_URL = "https://github.com/fadhly-permata/AI-Gate";
  const repoLink = () => doc.querySelector(".sidebar-footer a.nav-item");

  it("is a real external anchor with safe target/rel", () => {
    const link = repoLink();
    expect(link, ".sidebar-footer a.nav-item present").not.toBeNull();
    expect(link.tagName).toBe("A");
    expect(link.getAttribute("href")).toBe(REPO_URL);
    expect(link.getAttribute("target")).toBe("_blank");
    const rel = (link.getAttribute("rel") || "").split(/\s+/);
    expect(rel).toContain("noopener");
    expect(rel).toContain("noreferrer");
  });

  it("carries no data-view, and app.js only hijacks data-view items", () => {
    // data-view is what the view-switching handler keys on; without it the
    // browser keeps native link behaviour (a preventDefault() here would kill
    // the repo link — regression guard on the app.js binding).
    expect(repoLink().hasAttribute("data-view")).toBe(false);
    const appSrc = readFileSync(join(__dirname, "..", "static", "app.js"), "utf8");
    const binding = appSrc.match(
      /querySelectorAll\("\.nav-item, \.bn-item"\)\.forEach\(function \(item\) \{[\s\S]*?\n    \}\);/
    );
    expect(binding, "nav click binding present").not.toBeNull();
    expect(binding[0]).toMatch(/hasAttribute\("data-view"\)/);
    expect(binding[0].indexOf("data-view")).toBeLessThan(binding[0].indexOf("addEventListener"));
  });

  it("wrapper is the last child of .sidebar and outside <nav>", () => {
    const sidebar = doc.querySelector("aside.sidebar");
    const footer = sidebar.querySelector(":scope > .sidebar-footer");
    expect(footer, ".sidebar-footer is a direct child of .sidebar").not.toBeNull();
    expect(sidebar.lastElementChild).toBe(footer);
    // Outside <nav> on purpose: .nav's last child must stay a .nav-section so
    // `.nav-section:last-child { border-bottom: 0 }` keeps its original meaning.
    expect(footer.closest("nav")).toBeNull();
    const sections = doc.querySelectorAll(".nav-section");
    expect(sections).toHaveLength(4);
    expect(sections[3].nextElementSibling).toBeNull();
    // Not part of any group -> the grouping test above is unaffected.
    expect(repoLink().closest(".nav-section")).toBeNull();
  });

  it("reuses the nav markup: icon + localized label + readable when collapsed", () => {
    const link = repoLink();
    expect(link.querySelector("i.nav-icon.fa-github")).not.toBeNull();
    const label = link.querySelector("span.nav-label");
    expect(label.getAttribute("data-i18n")).toBe("nav.repo");
    // Collapsed mode hides .nav-label via CSS only, so aria-label/title carry it.
    expect(link.getAttribute("data-i18n-aria")).toBe("nav.repo");
    expect((link.getAttribute("aria-label") || "").trim()).toBeTruthy();
    expect((link.getAttribute("title") || "").trim()).toBeTruthy();
  });

  it("nav.repo is present in EN and ID, one value each (no bilingual string)", () => {
    expect(window.I18N.en["nav.repo"]).toBe("Repository");
    expect(window.I18N.id["nav.repo"]).toBe("Repositori");
    // Decision 2026-09-06: one key = one value, never "Repositori/Repository".
    expect(window.I18N.en["nav.repo"]).not.toMatch(/\/|Repositori/);
    expect(window.I18N.id["nav.repo"]).not.toMatch(/\/|Repository/);
  });

  it("collapsed mode keeps the label in the DOM (hidden by CSS, not markup)", () => {
    const label = repoLink().querySelector(".nav-label");
    expect(label.textContent).toBe("Repository");
    expect(label.hasAttribute("hidden")).toBe(false);
    expect(label.getAttribute("style")).toBeNull();
    // The collapse rules still target the shared classes the footer uses.
    expect(ruleBlock(/(^|\n)body\.sidebar-collapsed \.nav-label[^{]*\{[^}]*\}/))
      .toMatch(/display:\s*none/);
    expect(ruleBlock(/(^|\n)body\.sidebar-collapsed \.sidebar-footer[^{]*\{[^}]*\}/))
      .toBeTruthy();
  });

  it("CSS pins the footer to the panel bottom with existing tokens", () => {
    const footer = ruleBlock(/(^|\n)\.sidebar-footer\s*\{[^}]*\}/);
    expect(footer, ".sidebar-footer rule present").not.toBeNull();
    expect(footer).toMatch(/position:\s*sticky/);   // stays visible while .nav scrolls
    expect(footer).toMatch(/bottom:\s*0/);
    expect(footer).toMatch(/margin-top:\s*auto/);   // sits at the bottom when menu is short
    expect(footer).toMatch(/flex:\s*0 0 auto/);     // never squished by the flex line
    expect(footer).toMatch(/background:\s*var\(--sidebar-bg\)/); // opaque: menu scrolls under
    expect(footer).not.toMatch(/#[0-9a-fA-F]{3,8}/); // no new hex — design tokens only
    // margin-top:auto needs .sidebar to be a flex column.
    const sidebar = ruleBlock(/(^|\n)\.sidebar\s*\{[^}]*\}/);
    expect(sidebar).toMatch(/display:\s*flex/);
    expect(sidebar).toMatch(/flex-direction:\s*column/);
    expect(sidebar).toMatch(/overflow-y:\s*auto/);  // still the scroll container
  });

  it("phones are unchanged: sidebar stays hidden, no repo item in .bottom-nav", () => {
    expect(css).toMatch(/@media \(max-width: 600px\)[\s\S]{0,400}\.sidebar\s*\{\s*display:\s*none/);
    expect(ruleBlock(/(^|\n)body\[data-device="phone"\] \.sidebar\s*\{[^}]*\}/))
      .toMatch(/display:\s*none/);
    expect(doc.querySelector('.bottom-nav a[href*="github"]')).toBeNull();
    // 7 = current bottom-nav items; guards that the repo link was NOT added here.
    expect(doc.querySelectorAll(".bottom-nav .bn-item")).toHaveLength(7);
  });
});

