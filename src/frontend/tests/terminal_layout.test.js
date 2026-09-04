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
  '<div id="terminalBody" class="terminal-body"><div id="termStage" class="term-stage">' +
    '<div id="termTabBar" class="term-tabs"><button id="termNewTab"></button></div>' +
    '<div id="termContainers" class="term-containers"></div>' +
  '</div></div>';

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
});
