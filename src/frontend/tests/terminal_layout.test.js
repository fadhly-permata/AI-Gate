import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { JSDOM } from "jsdom";

/* =====================================================================
 * Terminal layout regression tests — BUG1 (half-height stage) + BUG2
 * (fullscreen clipped on mobile).
 *
 * Two layers, deliberately light-touch:
 *   1. CSS structure: assert the height chain flex-fills and that
 *      fullscreen uses the dynamic viewport (dvh) instead of the fragile
 *      `calc(100vh - 43px)`. We check for the PRESENCE of the fix and the
 *      ABSENCE of the old magic numbers — not exact pixel values.
 *   2. JS behaviour: with a stubbed ResizeObserver, assert the stage box is
 *      observed on open and a real size change refits xterm, and that the
 *      closed tab's box is un-observed (no leak).
 * ===================================================================== */

const __dirname = dirname(fileURLToPath(import.meta.url));
const cssRaw = readFileSync(join(__dirname, "..", "static", "styles.css"), "utf8");
// Strip /* ... */ comments so the "old value is gone" assertions aren't
// tripped by the explanatory comments that still NAME the removed values.
const css = cssRaw.replace(/\/\*[\s\S]*?\*\//g, "");

// Pull one top-level rule block out of the stylesheet by its selector regex.
function ruleBlock(selectorRe) {
  const m = css.match(selectorRe);
  return m ? m[0] : null;
}

describe("BUG1 — terminal view height chain fills the workspace (CSS)", () => {
  it("active terminal view is a flex column that fills + clips its parent", () => {
    const block = ruleBlock(/\.view\[data-view="terminal"\]\.is-active[^{]*\{[^}]*\}/);
    expect(block, ".view[data-view=terminal].is-active rule present").toBeTruthy();
    expect(block).toMatch(/display:\s*flex/);
    expect(block).toMatch(/flex-direction:\s*column/);
    expect(block).toMatch(/height:\s*100%/);
    expect(block).toMatch(/min-height:\s*0/);
    expect(block).toMatch(/overflow:\s*hidden/); // exact fit -> never scrolls
  });

  it("container chrome CSS is GONE (card / pane / header flattened away)", () => {
    expect(ruleBlock(/(^|\n)\.terminal-card\s*\{[^}]*\}/)).toBeNull();
    expect(ruleBlock(/(^|\n)\.terminal-pane\s*\{[^}]*\}/)).toBeNull();
    expect(ruleBlock(/(^|\n)\.terminal-header\s*\{[^}]*\}/)).toBeNull();
    expect(ruleBlock(/(^|\n)\.terminal-title\s*\{[^}]*\}/)).toBeNull();
  });

  it(".terminal-body flex-fills with NO floor (min-height:0, no vh/px pin)", () => {
    const body = ruleBlock(/(^|\n)\.terminal-body\s*\{[^}]*\}/);
    expect(body).toMatch(/flex:\s*1/);
    expect(body).toMatch(/min-height:\s*0/);
    expect(body).not.toMatch(/min-height:\s*\d+(vh|px)/); // the 28vh floor is gone
  });

  it(".term-stage flex-fills with NO floor (min-height:0, no vh/px pin)", () => {
    const stage = ruleBlock(/(^|\n)\.term-stage\s*\{[^}]*\}/);
    expect(stage, ".term-stage rule present").toBeTruthy();
    expect(stage).toMatch(/flex:\s*1/);
    expect(stage).toMatch(/min-height:\s*0/);
    expect(stage).not.toMatch(/min-height:\s*\d+(vh|px)/); // the 28vh floor is gone
  });

  it("no vh floor survives anywhere in the terminal size chain", () => {
    expect(css).not.toMatch(/min-height:\s*28vh/);
  });
});

/* =====================================================================
 * NO-PAGE-SCROLL guard (light-touch, structural). The scroll bug was a
 * min-height floor taller than the leftover space. Exact fit = the view
 * clips (overflow:hidden) and every child flex-fills with min-height:0,
 * so scrollHeight == clientHeight. We assert the STRUCTURE that guarantees
 * it — not pixel values (jsdom has no layout engine).
 * ===================================================================== */
describe("terminal view cannot page-scroll (structural guard)", () => {
  const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
  const doc = new JSDOM(html).window.document;

  it("HTML: #terminalBody is a direct child of the terminal view (no wrappers)", () => {
    const view = doc.querySelector('.view[data-view="terminal"]');
    const body = doc.getElementById("terminalBody");
    expect(view).not.toBeNull();
    expect(body.parentElement).toBe(view);
    expect(view.querySelector(".terminal-card")).toBeNull();
    expect(view.querySelector(".terminal-pane")).toBeNull();
    expect(view.querySelector(".terminal-header")).toBeNull();
    // The stage is a direct child of the body (toolbar + stage only).
    expect(doc.getElementById("termStage").parentElement).toBe(body);
  });

  it("CSS: view clips + body/stage flex-fill with min-height:0 (no floor)", () => {
    const view = ruleBlock(/\.view\[data-view="terminal"\]\.is-active[^{]*\{[^}]*\}/);
    const body = ruleBlock(/(^|\n)\.terminal-body\s*\{[^}]*\}/);
    const stage = ruleBlock(/(^|\n)\.term-stage\s*\{[^}]*\}/);
    const toolbar = ruleBlock(/(^|\n)\.term-toolbar\s*\{[^}]*\}/);
    expect(view).toMatch(/overflow:\s*hidden/);
    expect(view).toMatch(/height:\s*100%/);
    expect(body).toMatch(/flex:\s*1 1 auto/);
    expect(body).toMatch(/min-height:\s*0/);
    expect(toolbar).toMatch(/flex:\s*0 0 auto/);
    expect(stage).toMatch(/flex:\s*1 1 auto/);
    expect(stage).toMatch(/min-height:\s*0/);
    // No vh/px floor anywhere in the chain (the old 28vh caused the overflow).
    [view, body, stage].forEach((b) => expect(b).not.toMatch(/min-height:\s*\d+(vh|px)/));
  });
});

describe("BUG2 — fullscreen fills the dynamic viewport (CSS)", () => {
  it("fullscreen body uses 100dvh with a 100vh fallback", () => {
    const block = ruleBlock(/\.terminal-fullscreen\s*\{[^}]*\}/);
    expect(block, ".terminal-fullscreen rule present").toBeTruthy();
    expect(block).toMatch(/position:\s*fixed/);
    expect(block).toMatch(/inset:\s*0/);
    expect(block).toMatch(/display:\s*flex/);
    expect(block).toMatch(/flex-direction:\s*column/);
    expect(block).toMatch(/height:\s*100vh/);   // fallback first
    expect(block).toMatch(/height:\s*100dvh/);  // dynamic viewport wins
    // fallback must precede the dvh override so unsupported engines keep 100vh
    expect(block.indexOf("100vh")).toBeLessThan(block.indexOf("100dvh"));
  });

  it("fullscreen stage flex-fills; the fragile calc(100vh - 43px) is gone", () => {
    expect(css).not.toMatch(/calc\(100vh\s*-\s*43px\)/);
    const stage = ruleBlock(/\.terminal-fullscreen\s+\.term-stage\s*\{[^}]*\}/);
    expect(stage, "fullscreen .term-stage rule present").toBeTruthy();
    expect(stage).toMatch(/flex:\s*1/);
    expect(stage).toMatch(/min-height:\s*0/);
    expect(stage).toMatch(/height:\s*auto/);
  });

  it("floating controls stay above the stage in fullscreen", () => {
    const ctl = ruleBlock(/\.terminal-fullscreen\s+\.term-floating\s*\{[^}]*\}/);
    expect(ctl, "fullscreen .term-floating rule present").toBeTruthy();
    expect(ctl).toMatch(/z-index:\s*\d+/);
  });
});

describe("terminal expand/collapse CSS removed (regression guard)", () => {
  it("no .terminal-collapsed rules remain in the stylesheet", () => {
    expect(css).not.toMatch(/\.terminal-collapsed/);
    expect(css).not.toMatch(/:has\(\.terminal-pane\.terminal-collapsed\)/);
  });

  it("fill chain intact: body still grows with min-height:0 (no floor steals space)", () => {
    const body = ruleBlock(/(^|\n)\.terminal-body\s*\{[^}]*\}/);
    expect(body).toMatch(/flex:\s*1/);
    expect(body).toMatch(/min-height:\s*0/);
  });

  it(".terminal-header title bar styling is GONE (chrome flattened away)", () => {
    expect(ruleBlock(/(^|\n)\.terminal-header\s*\{[^}]*\}/)).toBeNull();
  });
});


/* =====================================================================
 * Terminal panel redesign — cohesion + symmetry guards (structural).
 * The old layout had the tab strip inset 8px and the terminal inset 4px, so
 * the glyph column and the tab strip did not line up and the two read as
 * separate boxes. These guards pin the fix: ONE inset token shared by both
 * rows, one framed panel, one control height, and the controls docked in the
 * strip (never over the first line of output).
 * ===================================================================== */
describe("terminal panel is one cohesive, symmetric unit (CSS)", () => {
  it("a single --term-pad token drives BOTH the toolbar and the terminal surface", () => {
    expect(css).toMatch(/--term-pad:\s*\d+px/);
    const toolbar = ruleBlock(/(^|\n)\.term-toolbar\s*\{[^}]*\}/);
    const container = ruleBlock(/(^|\n)\.term-tab-container\s*\{[^}]*\}/);
    const xterm = ruleBlock(/\.term-tab-container \.xterm\s*\{[^}]*\}/);
    expect(toolbar).toMatch(/padding:\s*var\(--term-pad\)/);
    // Horizontal inset on the surface (left only -> the scrollbar is the gutter).
    expect(container).toMatch(/padding:\s*0 0 0 var\(--term-pad\)/);
    // Vertical inset lives on the .xterm box, which FitAddon DOES subtract from
    // the row budget (padding on the parent is not -> clipped last row).
    expect(xterm).toMatch(/padding-top:\s*var\(--term-pad\)/);
    expect(xterm).toMatch(/padding-bottom:\s*var\(--term-pad\)/);
    // No magic per-row padding left behind (that is what let them drift).
    expect(toolbar).not.toMatch(/padding:\s*\d/);
    expect(container).not.toMatch(/padding:\s*[\d.]+px/);
    expect(xterm).not.toMatch(/padding[^:]*:\s*[\d.]+px/);
  });

  it("the xterm scrollbar is sized to the same token, so left inset == right inset", () => {
    const sb = ruleBlock(/\.xterm-viewport::-webkit-scrollbar\s*\{[^}]*\}/);
    expect(sb, "xterm viewport scrollbar rule present").toBeTruthy();
    expect(sb).toMatch(/width:\s*var\(--term-pad\)/);
    // FitAddon reads the real scrollbar width, so the glyph column shrinks by
    // exactly the gutter -> symmetric margins.
    const vp = ruleBlock(/\.xterm \.xterm-viewport\s*\{[^}]*\}/);
    expect(vp).toMatch(/background-color:\s*var\(--term-surface\)/);
  });

  it("one framed panel: body clips + rounds, toolbar/stage share the surface family", () => {
    const body = ruleBlock(/(^|\n)\.terminal-body\s*\{[^}]*\}/);
    const toolbar = ruleBlock(/(^|\n)\.term-toolbar\s*\{[^}]*\}/);
    const stage = ruleBlock(/(^|\n)\.term-stage\s*\{[^}]*\}/);
    expect(body).toMatch(/border:\s*1px solid var\(--term-frame\)/);
    expect(body).toMatch(/border-radius:\s*var\(--radius\)/);
    expect(body).toMatch(/overflow:\s*hidden/);
    expect(body).toMatch(/background:\s*var\(--term-surface\)/);
    expect(stage).toMatch(/background:\s*var\(--term-surface\)/);
    expect(toolbar).toMatch(/background:\s*var\(--term-chrome\)/);
    // The only separation between the two rows is a 1px seam.
    expect(toolbar).toMatch(/border-bottom:\s*1px solid var\(--term-divider\)/);
  });

  it("tabs, + button and controls share ONE height token; strip still scrolls", () => {
    expect(css).toMatch(/--term-ctl:\s*\d+px/);
    const tab = ruleBlock(/(^|\n)\.term-tab\s*\{[^}]*\}/);
    const newtab = ruleBlock(/\.term-toolbar \.term-newtab\s*\{[^}]*\}/);
    const ctl = ruleBlock(/\.term-floating \.term-ctl\s*\{[^}]*\}/);
    expect(tab).toMatch(/height:\s*var\(--term-ctl\)/);
    expect(newtab).toMatch(/height:\s*var\(--term-ctl\)/);
    expect(ctl).toMatch(/height:\s*var\(--term-ctl\)/);
    const tabs = ruleBlock(/(^|\n)\.term-tabs\s*\{[^}]*\}/);
    expect(tabs).toMatch(/overflow-x:\s*auto/); // many tabs -> scroll, keep behaviour
  });

  it("size chain stays relative (no px/vh height pin reintroduced)", () => {
    const body = ruleBlock(/(^|\n)\.terminal-body\s*\{[^}]*\}/);
    const stage = ruleBlock(/(^|\n)\.term-stage\s*\{[^}]*\}/);
    const toolbar = ruleBlock(/(^|\n)\.term-toolbar\s*\{[^}]*\}/);
    [body, stage, toolbar].forEach((b) => {
      expect(b).not.toMatch(/(^|[^-])height:\s*\d+(px|vh|dvh)/);
      expect(b).not.toMatch(/min-height:\s*\d+(px|vh)/);
    });
  });
});

describe("terminal panel redesign — HTML structure", () => {
  const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
  const doc = new JSDOM(html).window.document;

  it("controls are docked in the tab strip, not floating over the surface", () => {
    const floating = doc.getElementById("termFloating");
    const stage = doc.getElementById("termStage");
    expect(floating).not.toBeNull();
    expect(floating.parentElement.classList.contains("term-toolbar")).toBe(true);
    expect(stage.contains(floating)).toBe(false);
    expect(floating.getAttribute("role")).toBe("group");
    expect(floating.hasAttribute("data-i18n-aria")).toBe(true);
    // All three control hooks still live inside the cluster.
    ["termFullscreen", "termPaste", "termTui"].forEach((id) => {
      expect(floating.querySelector("#" + id)).not.toBeNull();
    });
  });

  it("empty state exists in the stage, hidden by default, i18n-bound", () => {
    const empty = doc.getElementById("termEmpty");
    const stage = doc.getElementById("termStage");
    expect(empty, "#termEmpty present").not.toBeNull();
    expect(stage.contains(empty)).toBe(true);
    expect(empty.hasAttribute("hidden")).toBe(true);
    expect(empty.querySelector('[data-i18n="term.empty"]')).not.toBeNull();
    expect(empty.querySelector("#termEmptyNewTab")).not.toBeNull();
  });

  it("tabs + controls sit in ONE row (toolbar), surface below (stage)", () => {
    const body = doc.getElementById("terminalBody");
    const kids = Array.from(body.children).map((el) => el.className);
    expect(kids).toEqual(["term-toolbar", "term-stage"]);
    const toolbar = body.querySelector(".term-toolbar");
    expect(toolbar.querySelector("#termTabBar")).not.toBeNull();
    expect(toolbar.querySelector("#termNewTab")).not.toBeNull();
    // "+" is a sibling of the scrolling strip, not inside it -> stays pinned
    // (reachable) when many tabs overflow.
    expect(doc.getElementById("termNewTab").parentElement.id).not.toBe("termTabBar");
    expect(doc.getElementById("termTabBar").children.length).toBe(0);
  });

  it("term.empty / term.controls exist in BOTH locales (parity)", () => {
    return import("../static/i18n.js").then(() => {
      const I18N = global.window.I18N || window.I18N;
      ["term.empty", "term.controls"].forEach((k) => {
        expect(typeof I18N.en[k]).toBe("string");
        expect(typeof I18N.id[k]).toBe("string");
        expect(I18N.en[k].length).toBeGreaterThan(5);
        expect(I18N.id[k].length).toBeGreaterThan(5);
      });
    });
  });
});


/* =====================================================================
 * JS behaviour — ResizeObserver refit wiring.
 * Mocks MUST exist before terminal.js is imported (its IIFE runs init()).
 * ===================================================================== */

let fitCalls = 0;

class MockWebSocket {
  constructor(url) { this.url = url; this.readyState = MockWebSocket.CONNECTING; this.sent = []; }
  send(d) { this.sent.push(String(d)); }
  addEventListener() {}
  close() { this.readyState = MockWebSocket.CLOSED; if (this.onclose) this.onclose(); }
}
MockWebSocket.CONNECTING = 0; MockWebSocket.OPEN = 1; MockWebSocket.CLOSED = 3;

class MockTerminal {
  constructor() { this.cols = 80; this.rows = 24; this.options = {}; }
  loadAddon() {} open() {} write() {} onData() {} focus() {} dispose() {}
  scrollLines() {} paste() {}
  get buffer() { return { active: { viewportY: 0, length: 100 } }; }
}

// A ResizeObserver stub that records what it observes / unobserves / disconnects
// and lets the test fire a size change manually.
class MockResizeObserver {
  constructor(cb) { this.cb = cb; this.targets = []; MockResizeObserver.instances.push(this); }
  observe(el) { if (this.targets.indexOf(el) === -1) this.targets.push(el); }
  unobserve(el) { this.targets = this.targets.filter((t) => t !== el); }
  disconnect() { this.targets = []; }
  _fire() { this.cb(this.targets.slice(), this); }
}
MockResizeObserver.instances = [];

global.WebSocket = MockWebSocket;
window.WebSocket = MockWebSocket;
window.Terminal = MockTerminal;
window.FitAddon = { FitAddon: class { fit() { fitCalls += 1; } } };
global.ResizeObserver = MockResizeObserver;
window.ResizeObserver = MockResizeObserver;

document.body.innerHTML =
  '<div id="terminalBody" class="terminal-body">' +
    '<div class="term-toolbar">' +
      '<div id="termTabBar" class="term-tabs"></div>' +
      '<button id="termNewTab"></button>' +
      '<div id="termFloating" class="term-floating">' +
        '<button id="termFullscreen"></button><button id="termPaste"></button>' +
        '<button id="termTui"></button>' +
      '</div>' +
    '</div>' +
    '<div id="termStage" class="term-stage">' +
      '<div id="termContainers" class="term-containers"></div>' +
      '<div id="termEmpty" class="term-empty" hidden></div>' +
    '</div>' +
  '</div>';

await import("../static/i18n.js");
await import("../static/terminal.js");

const T = () => window.aigate.terminal;
const theObserver = () => MockResizeObserver.instances[MockResizeObserver.instances.length - 1];

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
  // Drop leftover tabs so module state is clean between tests.
  const tabs = T()._tabs;
  tabs.forEach((tab) => {
    if (tab.reconnectTimer) clearTimeout(tab.reconnectTimer);
    if (tab.livenessTimer) clearTimeout(tab.livenessTimer);
    tab.userClosed = true;
  });
  tabs.clear();
});

describe("BUG2 — terminal.js ResizeObserver wiring", () => {
  it("init() creates exactly one ResizeObserver", () => {
    expect(MockResizeObserver.instances.length).toBe(1);
  });

  it("opening a tab observes that tab's stage container", () => {
    const tab = T().openTab();
    expect(theObserver().targets).toContain(tab.container);
  });

  it("a real size change on the observed box refits xterm (debounced)", () => {
    T().openTab();
    const before = fitCalls;
    theObserver()._fire();          // simulate the box actually resizing
    expect(fitCalls).toBe(before);  // debounced: not yet
    vi.advanceTimersByTime(100);    // after the debounce window
    expect(fitCalls).toBeGreaterThan(before);
  });

  it("closing the ACTIVE tab re-targets the observer at the survivor (no leak)", () => {
    const a = T().openTab();
    const b = T().openTab();        // b is active (last opened)
    T().closeTab(b.id);             // close the active one
    expect(theObserver().targets).not.toContain(b.container);
    expect(theObserver().targets).toContain(a.container);
  });

  it("opening a tab clears the empty-state hint (panel is never a blank box)", () => {
    const empty = document.getElementById("termEmpty");
    expect(empty).not.toBeNull();
    empty.hidden = false;               // simulate "no tabs yet"
    const tab = T().openTab();
    expect(empty.hidden).toBe(true);    // hint gone as soon as a session exists
    T().closeTab(tab.id);               // closing re-opens one -> still no hint
    expect(empty.hidden).toBe(true);
  });

  it("the active tab is marked aria-selected (tablist semantics survive redesign)", () => {
    const tab = T().openTab();
    expect(tab.button.getAttribute("aria-selected")).toBe("true");
    const other = T().openTab();
    expect(tab.button.getAttribute("aria-selected")).toBe("false");
    expect(other.button.getAttribute("aria-selected")).toBe("true");
    T().closeTab(other.id);
  });
});
