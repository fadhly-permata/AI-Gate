import { describe, it, expect } from "vitest";

import { indexDocument, indexHtml, stylesCss, staticSource, htmlRefBase } from "./helpers/dom.js";

// i18n.js is a side-effect module: attaches window.I18N (no document access at
// load). Imported so the collapse-key regression guard can read the dicts.
import "../static/i18n.js";

// Shared cached parse of the shipped page (READ-ONLY — see helpers/dom.js).
const doc = indexDocument();

// CSS source assertions (same approach as terminal_layout.test.js): the sticky
// behaviour lives entirely in the stylesheet, so jsdom cannot exercise it and
// the rule text is the contract.
const css = stylesCss();
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

  /* ===== The provider-detail page is the ONE exception to "view = menu" =====
     stage-3 (Opsi A): it is a sub-page of Providers, opened from a row name, so
     it must NOT grow a sidebar or bottom-nav entry — otherwise the mirror list
     below (and the phone shell's reachability contract) changes shape. app.js
     keeps .nav-item[data-view="providers"] highlighted while it is shown. */
  it("provider-detail view exists but has NO nav or bottom-nav entry", () => {
    const view = doc.querySelector('section.view[data-view="provider-detail"]');
    expect(view, "detail view section present").not.toBeNull();
    expect(view.classList.contains("view")).toBe(true);
    expect(doc.querySelector('.nav-item[data-view="provider-detail"]')).toBeNull();
    expect(doc.querySelector('.bn-item[data-view="provider-detail"]')).toBeNull();
    // It is still reachable by keyboard/mouse: the entry point is a real button.
    expect(doc.querySelector('.nav-item[data-view="providers"]')).not.toBeNull();
  });

  it("provider-detail is one vertical column of cards (no grid, no wide table)", () => {
    const view = doc.querySelector('section.view[data-view="provider-detail"]');
    const cards = view.querySelectorAll(":scope > .card");
    expect(cards.length, "head + 4 cards").toBeGreaterThanOrEqual(5);
    // The only table left inside it is the B5.5 top-models one that usage.js
    // owns; the 6-column accounts table must not come back.
    expect(view.querySelector("#accList").tagName).toBe("DIV");
    expect(view.querySelector("#accList table")).toBeNull();
    expect(doc.getElementById("accountsTable")).toBeNull();
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
    // Version-aware (stage-8 follow-up): every module now carries a `?v=`
    // cache-buster, so compare BASENAMES — the presence + order contract is
    // unchanged, it just survives version bumps.
    const bases = Array.from(doc.querySelectorAll("script[src]"))
      .map((s) => htmlRefBase(s.getAttribute("src")));
    expect(bases).toContain("combos.js");
    expect(bases).toContain("proxies.js");
    expect(bases).toContain("endpoints.js");
    expect(bases.indexOf("app.js")).toBeLessThan(bases.indexOf("combos.js"));
    expect(bases.indexOf("app.js")).toBeLessThan(bases.indexOf("proxies.js"));
    expect(bases.indexOf("app.js")).toBeLessThan(bases.indexOf("endpoints.js"));
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
    const appSrc = staticSource("app.js");
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
    // Label diminta user 2026-09-07: "aigate Repo" — nama produk, jadi SAMA di EN & ID.
    expect(window.I18N.en["nav.repo"]).toBe("aigate Repo");
    expect(window.I18N.id["nav.repo"]).toBe("aigate Repo");
    // Decision 2026-09-06: one key = one value, never "Repositori/Repository".
    expect(window.I18N.en["nav.repo"]).not.toMatch(/\/|Repositori/);
    expect(window.I18N.id["nav.repo"]).not.toMatch(/\/|Repository/);
  });

  it("collapsed mode keeps the label in the DOM (hidden by CSS, not markup)", () => {
    const label = repoLink().querySelector(".nav-label");
    expect(label.textContent).toBe("aigate Repo");
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

  it("phones reach the repo too: sidebar hidden, repo link added to .bottom-nav", () => {
    expect(css).toMatch(/@media \(max-width: 600px\)[\s\S]{0,400}\.sidebar\s*\{\s*display:\s*none/);
    expect(ruleBlock(/(^|\n)body\[data-device="phone"\] \.sidebar\s*\{[^}]*\}/))
      .toMatch(/display:\s*none/);
    // Request 2026-09-09: the sticky sidebar footer stays the tablet/desktop
    // entry point, but the phone shell (sidebar hidden) must also reach the
    // repo — icon-only as the last .bn-item, a real external link.
    const navRepo = doc.querySelector('.bottom-nav a.bn-item[href*="github"]');
    expect(navRepo, "repo link present in .bottom-nav").not.toBeNull();
    expect(navRepo.getAttribute("href")).toBe(REPO_URL);
    expect(navRepo.getAttribute("target")).toBe("_blank");
    const navRel = (navRepo.getAttribute("rel") || "").split(/\s+/);
    expect(navRel).toContain("noopener");
    expect(navRel).toContain("noreferrer");
    // No data-view -> app.js keeps native link behaviour (binding above).
    expect(navRepo.hasAttribute("data-view")).toBe(false);
    // 9 app views + repo = 10 items in the bottom nav.
    expect(doc.querySelectorAll(".bottom-nav .bn-item")).toHaveLength(10);
  });
});

/* ===== Phone shell: hamburger hidden, bottom nav scrolls sideways =====
   User report 2026-09-09: on the phone shell the sidebar is replaced by
   .bottom-nav, so #sidebarToggle toggles nothing (dead tap) and the icons were
   squeezed to ~50px each — the last ones unreachable. Fix = hide the hamburger
   in BOTH phone contexts and let the nav scroll horizontally instead of clip.
   Retest the same day: menus still "unreachable", because .bottom-nav only had
   7 of the sidebar's 9 app views — usage and analytics were never rendered on a
   phone. Fix = mirror the sidebar 1:1; 9 x min-width overflows a 360px row, so
   the scroll rule above is now what makes the LAST item reachable.
    jsdom evaluates neither @media nor flex layout, so the rule TEXT is the
    contract (same approach as the sticky-footer checks above).
    Follow-up 2026-09-09: the repo link joined the nav as a 10th icon-only
    item, and .bn-sep dividers were added at the sidebar's group boundaries —
    the nav now mirrors the grouping, not just the item list. */
describe("phone shell — hamburger hidden, bottom nav scrollable", () => {
  const PHONE_QUERY = "@media (max-width: 600px)";
  const TABLET_QUERY = "@media (max-width: 960px)";
  const NARROW_PHONE_PX = 360;  // smallest phone viewport we design for

  /** Index just past the "}" matching the "{" at `open`; -1 when unbalanced. */
  function blockEnd(text, open) {
    let depth = 0;
    for (let i = open; i < text.length; i += 1) {
      if (text[i] === "{") depth += 1;
      else if (text[i] === "}" && (depth -= 1) === 0) return i + 1;
    }
    return -1;
  }

  /** Inner text of every @media block whose header contains `query`. */
  function mediaBodies(query) {
    const bodies = [];
    let i = css.indexOf(query);
    while (i !== -1) {
      const open = css.indexOf("{", i);
      const end = blockEnd(css, open);
      if (end !== -1) bodies.push(css.slice(open + 1, end - 1));
      i = css.indexOf(query, i + query.length);
    }
    return bodies;
  }

  // The file has two 600px blocks; the phone SHELL is the one that hides the
  // sidebar (the other only tucks the app subtitle away).
  const phoneShell = () => mediaBodies(PHONE_QUERY).find(function (body) {
    return /\.sidebar\s*\{/.test(body);
  });

  it("hides #sidebarToggle in both phone shells and nowhere else", function () {
    const shell = phoneShell();
    expect(shell, "phone-shell @media block found").toBeTruthy();
    expect(shell).toMatch(/\.sidebar\s*\{\s*display:\s*none/);       // nothing left to toggle
    expect(shell).toMatch(/#sidebarToggle\s*\{\s*display:\s*none/);  // so the button goes too
    expect(ruleBlock(/(^|\n)body\[data-device="phone"\] #sidebarToggle\s*\{[^}]*\}/))
      .toMatch(/display:\s*none/);                                   // simulation shell mirrors it
    // display:none takes it out of layout AND the tab order, so the dead tap in
    // app.js can never fire on a phone. Exactly one rule per phone context:
    expect(css.match(/#sidebarToggle\s*\{/g), "two phone shells = two rules").toHaveLength(2);
    // Tablet (>600px) keeps the AdminLTE sidebar, so the hamburger must stay.
    const tablet = mediaBodies(TABLET_QUERY);
    expect(tablet, "single tablet block").toHaveLength(1);
    expect(tablet[0]).toMatch(/--sidebar-w:/);                       // really the tablet block
    expect(tablet[0]).not.toMatch(/#sidebarToggle/);
  });

  it("renders EVERY sidebar view in the bottom nav (no phone-unreachable menu)", function () {
    // Root cause of the 2026-09-09 retest: usage + analytics existed in the
    // sidebar only, so on a phone they were literally never rendered. Compare the
    // two lists (same order too: the nav is the phone mirror of the menu).
    const sidebarViews = Array.from(
      doc.querySelectorAll(".sidebar .nav-item[data-view]")
    ).map(function (item) { return item.getAttribute("data-view"); });
    // [data-view] only: the repo link is also a .bn-item but is an external
    // anchor, not a view — including it would inject a null into the mirror.
    const navViews = Array.from(doc.querySelectorAll(".bottom-nav .bn-item[data-view]")).map(function (item) {
      return item.getAttribute("data-view");
    });
    expect(sidebarViews).toEqual([
      "providers", "combos", "proxies", "endpoints", "terminal", "cli",
      "usage", "analytics", "settings"
    ]);
    expect(navViews).toEqual(sidebarViews);
    // Every mirrored item keeps the shared i18n aria key, so its label is
    // localized in both locales (app.js binds taps generically by data-view).
    navViews.forEach(function (v) {
      const item = doc.querySelector('.bottom-nav .bn-item[data-view="' + v + '"]');
      expect(item.getAttribute("data-i18n-aria")).toBe("nav." + v);
      expect(window.I18N.en["nav." + v]).toBeTruthy();
      expect(window.I18N.id["nav." + v]).toBeTruthy();
    });
  });

  it("scrolls .bottom-nav sideways so all 10 items stay reachable", function () {
    const shell = phoneShell();
    expect(shell, "phone-shell @media block found").toBeTruthy();
    const nav = ruleBlock(/(^|\n)\.bottom-nav\s*\{[^}]*\}/);
    expect(nav, ".bottom-nav base rule present").not.toBeNull();
    expect(nav).toMatch(/overflow-x:\s*auto/);                   // scroll, never clip
    expect(nav).toMatch(/-webkit-overflow-scrolling:\s*touch/);  // momentum in mobile webviews
    expect(nav).toMatch(/justify-content:\s*flex-start/);        // centring would overflow BOTH ends
    expect(nav).toMatch(/align-items:\s*center/);                // vertical centring untouched
    const item = ruleBlock(/(^|\n)\.bn-item\s*\{[^}]*\}/);
    const minTap = item && item.match(/min-width:\s*(\d+)px/);
    expect(minTap, ".bn-item keeps a min-width (overflow -> scroll, no squeeze)").not.toBeNull();
    expect(Number(minTap[1]), "still a comfortable tap target").toBeGreaterThanOrEqual(44);
    expect(item).toMatch(/justify-content:\s*center/);           // icon stays centred in its cell
    // flex-shrink must NOT be able to win over min-width, or the items squeeze
    // back into the viewport and the scroll disappears (the reported symptom).
    expect(item).toMatch(/flex:\s*1 1 0/);
    const items = doc.querySelectorAll(".bottom-nav .bn-item");
    expect(items).toHaveLength(10);
    // 10 x 60px = 600px > 360px (separators only add width): the row cannot
    // fit, so it must scroll — and no item can shrink below the tap target,
    // i.e. none is clipped out of reach.
    expect(items.length * Number(minTap[1])).toBeGreaterThan(NARROW_PHONE_PX);
    // Both phone shells only switch the nav ON; undoing the base row would kill
    // the scroll again (space-around / a hidden overflow were the old bug).
    const shellNav = shell.match(/\.bottom-nav\s*\{[^}]*\}/);
    [shellNav && shellNav[0],
     ruleBlock(/body\[data-device="phone"\] \.bottom-nav\s*\{[^}]*\}/)].forEach(function (rule) {
      expect(rule, ".bottom-nav rule in the phone shell").not.toBeNull();
      expect(rule).toMatch(/display:\s*flex/);
      expect(rule, "no justify-content/override inside the phone shell")
        .not.toMatch(/justify-content|overflow/);
    });
    // Active/hover feedback that makes the row usable survives the change.
    expect(ruleBlock(/\.bn-item\.active\s*\{[^}]*\}/)).toMatch(/background:/);
  });

  it("divides the nav into the sidebar's groups with 4 separators", function () {
    // Gateway | Operations | Insights | System | Repo = 5 clusters -> 4 dividers.
    const seps = doc.querySelectorAll(".bottom-nav .bn-sep");
    expect(seps, "one separator at every group boundary").toHaveLength(4);
    seps.forEach(function (sep) {
      // Decorative: keep it out of the accessible name of the nav.
      expect(sep.getAttribute("aria-hidden")).toBe("true");
    });
    // Count alone is not enough: each divider must sit at a real boundary,
    // mirroring the sidebar .nav-section edges (aria keys identify the sides).
    const boundaries = Array.from(seps).map(function (sep) {
      return [sep.previousElementSibling.getAttribute("data-i18n-aria"),
              sep.nextElementSibling.getAttribute("data-i18n-aria")];
    });
    expect(boundaries).toEqual([
      ["nav.endpoints", "nav.terminal"],  // Gateway  -> Operations
      ["nav.cli", "nav.usage"],           // Operations -> Insights
      ["nav.analytics", "nav.settings"],  // Insights -> System
      ["nav.settings", "nav.repo"]        // System   -> Repo
    ]);
    // jsdom has no layout: the rule text carries the visible-divider contract.
    const rule = ruleBlock(/(^|\n)\.bn-sep\s*\{[^}]*\}/);
    expect(rule, ".bn-sep base rule present").not.toBeNull();
    expect(rule).toMatch(/flex:\s*0 0 auto/);                 // never squeezed by the row
    expect(rule).toMatch(/width:\s*1px/);                     // hairline
    expect(rule).toMatch(/background:\s*var\(--panel-border\)/); // token, light+dark aware
    expect(rule).not.toMatch(/#[0-9a-fA-F]{3,8}/);            // no new hex
  });
});

/* ===== Cache-buster guard — every LOCAL script/stylesheet carries ?v= =====
   Stage-8 follow-up (2026-09-12): six modules (device/combos/proxies/endpoints/
   usage/clitools) shipped with a bare src, so a browser holding a stale cached
   copy ran the OLD code after an update — the exact "kok tab-nya gak ada"
   incident class. This guard makes a bare local ref fail loudly: it scans the
   RENDERED markup (jsdom parses out HTML comments, so no commented-out tag can
   satisfy it — proven by temporarily reverting one ?v= and watching it fail).
   Rule: local .js/.css refs must match ?v=<digits>. External refs are banned
   outright by vendor_assets.test.js (G3), so "local" needs no extra check. */
describe("cache-buster guard — every local script/stylesheet has ?v=", () => {
  // EXPLICIT exceptions, each with its reason. Keep this list empty unless a
  // ref genuinely cannot carry a static ?v=, and say WHY next to it.
  const EXEMPT = [];

  const CACHEABLE = /\.(?:js|mjs|css)$/;
  // V is a single source of truth per release day; ?raw= / ?data= style dynamic
  // refs would slip past a `[?&]v=` test, so only ?v=<digits> counts as busted.
  const BUSTED = /\?v=\d+$/;

  it("every <script src> of a local .js carries ?v=<digits> (or is exempted)", () => {
    const offenders = Array.from(doc.querySelectorAll("script[src]"))
      .map((s) => s.getAttribute("src"))
      .filter((src) => CACHEABLE.test(htmlRefBase(src)) && !EXEMPT.includes(src))
      .filter((src) => {
        const q = src.indexOf("?");
        const query = q === -1 ? "" : src.slice(q).split("#")[0];
        return !BUSTED.test(query);
      });
    expect(offenders, "scripts missing ?v=").toEqual([]);
  });

  it("every <link rel=stylesheet href> of a local .css carries ?v=<digits> (or is exempted)", () => {
    const offenders = Array.from(doc.querySelectorAll('link[rel~="stylesheet"][href]'))
      .map((l) => l.getAttribute("href"))
      .filter((href) => CACHEABLE.test(htmlRefBase(href)) && !EXEMPT.includes(href))
      .filter((href) => {
        const q = href.indexOf("?");
        const query = q === -1 ? "" : href.slice(q).split("#")[0];
        return !BUSTED.test(query);
      });
    expect(offenders, "stylesheets missing ?v=").toEqual([]);
  });

  it("the guard is not vacuous (it sees the real module + css refs)", () => {
    // If these ever hit 0, the scan broke (selector/markup change) and the two
    // tests above would pass on an empty list — the exact silent failure this
    // whole block exists to prevent.
    const scripts = Array.from(doc.querySelectorAll("script[src]"))
      .map((s) => s.getAttribute("src"))
      .filter((src) => CACHEABLE.test(htmlRefBase(src)));
    expect(scripts.length, "cacheable <script src> count").toBeGreaterThanOrEqual(13);
    expect(scripts.some((s) => htmlRefBase(s) === "combos.js")).toBe(true);
    const csses = Array.from(doc.querySelectorAll('link[rel~="stylesheet"][href]'))
      .map((l) => l.getAttribute("href"))
      .filter((href) => CACHEABLE.test(htmlRefBase(href)));
    expect(csses.length, "cacheable stylesheet count").toBeGreaterThanOrEqual(2);
    // i18n preloader (inline in <head>) is NOT covered by the scan above: its
    // dictionary tags are document.write'd at runtime and already carry the
    // shared V (window.I18N_VER). Pinned here, straight from the raw source,
    // so removing the runtime ?v= also fails this file.
    expect(indexHtml()).toMatch(/\.js\?v="\s*\+\s*V/);
  });
});

