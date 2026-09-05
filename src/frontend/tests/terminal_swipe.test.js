import { describe, it, expect, afterEach, vi } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

/* =====================================================================
 * Mobile terminal fixes — PROBLEM 1 (dvh height) + PROBLEM 2 (swipe).
 *
 *   1. CSS structure: `.layout` must size to the DYNAMIC viewport (100dvh
 *      with a 100vh fallback) so the terminal bottom is never pushed below
 *      the Android URL bar; and `touch-action: none` must reach the xterm
 *      layers INSIDE the stage so the browser stops stealing the touch
 *      gesture (native pan -> pointercancel) before our swipe handler runs.
 *   2. JS behaviour: drive the real setupSwipe() handlers with synthetic
 *      pointer events and assert they call term.scrollLines() — i.e. a swipe
 *      actually scrolls — while mouse gestures and TUI passthrough do NOT.
 * ===================================================================== */

const __dirname = dirname(fileURLToPath(import.meta.url));
const cssRaw = readFileSync(join(__dirname, "..", "static", "styles.css"), "utf8");
const css = cssRaw.replace(/\/\*[\s\S]*?\*\//g, ""); // drop comments

function ruleBlock(selectorRe) {
  const m = css.match(selectorRe);
  return m ? m[0] : null;
}

/* ---- PROBLEM 1: dynamic-viewport height ---- */
describe("PROBLEM 1 — .layout fits the visible (dynamic) viewport", () => {
  it(".layout uses 100dvh with a 100vh fallback (fallback first)", () => {
    const block = ruleBlock(/(^|\n)\.layout\s*\{[^}]*\}/);
    expect(block, ".layout rule present").toBeTruthy();
    expect(block).toMatch(/height:\s*100vh/);   // fallback
    expect(block).toMatch(/height:\s*100dvh/);  // dynamic viewport wins
    expect(block.indexOf("100vh")).toBeLessThan(block.indexOf("100dvh"));
  });
});

/* ---- PROBLEM 2 (CSS): touch-action reaches the xterm layers ---- */
describe("PROBLEM 2 — touch-action:none covers the xterm layers in the stage", () => {
  it("the stage itself keeps touch-action:none", () => {
    const stage = ruleBlock(/(^|\n)\.term-stage\s*\{[^}]*\}/);
    expect(stage).toMatch(/touch-action:\s*none/);
  });

  it("xterm / viewport / screen / helper-textarea inside the stage get touch-action:none", () => {
    // One grouped selector block covering all four interactive xterm layers.
    const block = ruleBlock(
      /\.term-stage \.xterm,[^}]*\.term-stage \.xterm-viewport,[^}]*\.term-stage \.xterm-screen,[^}]*\.term-stage \.xterm-helper-textarea\s*\{[^}]*\}/
    );
    expect(block, "grouped xterm touch-action rule present").toBeTruthy();
    expect(block).toMatch(/touch-action:\s*none/);
    [".xterm", ".xterm-viewport", ".xterm-screen", ".xterm-helper-textarea"].forEach((sel) => {
      expect(block).toContain(".term-stage " + sel);
    });
  });
});

/* =====================================================================
 * PROBLEM 2 (JS): the swipe handler drives scrollLines().
 * Mocks MUST exist before terminal.js is imported (its IIFE runs init()).
 * ===================================================================== */
class MockWebSocket {
  constructor(url) { this.url = url; this.readyState = MockWebSocket.OPEN; this.sent = []; }
  send(d) { this.sent.push(String(d)); }
  addEventListener() {}
  close() { this.readyState = MockWebSocket.CLOSED; if (this.onclose) this.onclose(); }
}
MockWebSocket.OPEN = 1; MockWebSocket.CONNECTING = 0; MockWebSocket.CLOSED = 3;

class MockTerminal {
  constructor() { this.cols = 80; this.rows = 24; this.options = {}; this._vY = 5; }
  loadAddon() {} open() {} write() {} onData() {} focus() {} dispose() {}
  paste() {}
  scrollLines() {}
  get buffer() {
    // viewportY mid-buffer so atEdge() is false (no edge damping to zero out).
    return { active: { viewportY: this._vY, length: 100 } };
  }
}

global.WebSocket = MockWebSocket;
window.WebSocket = MockWebSocket;
window.Terminal = MockTerminal;
window.FitAddon = { FitAddon: class { fit() {} } };
global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
window.ResizeObserver = global.ResizeObserver;

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
const stage = () => document.getElementById("termStage");

// Build a bubbling+cancelable event carrying the pointer/touch fields the
// handlers read (jsdom has no PointerEvent, so we attach the props by hand).
function fire(target, type, props) {
  const ev = new Event(type, { bubbles: true, cancelable: true });
  Object.assign(ev, props);
  target.dispatchEvent(ev);
  return ev;
}

// Deterministic clock: each read advances 16ms so dt>0 in the velocity math.
function mockClock() {
  let t = 0;
  const spy = vi.spyOn(performance, "now").mockImplementation(() => (t += 16));
  return spy;
}

// Run a full upward swipe (finger moves UP ~150px over several frames).
function swipeUp(tab, { pointerType = "touch", px = 150, frames = 5 } = {}) {
  const step = px / frames;
  fire(stage(), "pointerdown", { pointerType, clientX: 200, clientY: 400 });
  let y = 400;
  for (let i = 0; i < frames; i++) {
    y -= step;
    fire(window, "pointermove", { pointerType, clientX: 200, clientY: y });
  }
  fire(window, "pointerup", { pointerType, clientX: 200, clientY: y });
}

afterEach(() => {
  vi.restoreAllMocks();
  const tabs = T()._tabs;
  tabs.forEach((tab) => { tab.userClosed = true; });
  tabs.clear();
});

describe("PROBLEM 2 — swipe drives terminal scroll (setupSwipe handlers)", () => {
  it("a touch swipe-up calls scrollLines() with a NEGATIVE delta (scroll toward top)", () => {
    mockClock();
    const tab = T().openTab();
    const deltas = [];
    tab.term.scrollLines = (d) => deltas.push(d);

    const frames = 5;
    swipeUp(tab, { frames });

    expect(deltas.length, "scrollLines called during the swipe").toBeGreaterThan(0);
    expect(deltas.every((d) => d < 0), "up-swipe scrolls up").toBe(true);
    expect(deltas.reduce((a, b) => a + b, 0)).toBeLessThan(0);
    // Momentum: pointerup adds exactly one release-velocity scroll on top of the
    // per-move scrolls. Guards the ptr.active ordering in the pointerup handler.
    expect(deltas.length, "per-move scrolls + one momentum scroll on release").toBe(frames + 1);
  });

  it("a swipe-DOWN scrolls down (positive delta)", () => {
    mockClock();
    const tab = T().openTab();
    const deltas = [];
    tab.term.scrollLines = (d) => deltas.push(d);

    // finger moves DOWN: content scrolls toward the buffer bottom.
    fire(stage(), "pointerdown", { pointerType: "touch", clientX: 200, clientY: 200 });
    let y = 200;
    for (let i = 0; i < 5; i++) { y += 30; fire(window, "pointermove", { pointerType: "touch", clientX: 200, clientY: y }); }
    fire(window, "pointerup", { pointerType: "touch", clientX: 200, clientY: y });

    expect(deltas.length).toBeGreaterThan(0);
    expect(deltas.every((d) => d > 0)).toBe(true);
  });

  it("a MOUSE drag never scrolls (xterm keeps mouse text-selection)", () => {
    mockClock();
    const tab = T().openTab();
    const spy = vi.fn();
    tab.term.scrollLines = spy;

    swipeUp(tab, { pointerType: "mouse" });

    expect(spy, "mouse gesture must not hijack selection into a scroll").not.toHaveBeenCalled();
  });

  it("TUI mode ON => gestures pass through, no scrollLines()", () => {
    mockClock();
    const tab = T().openTab();
    tab.tuiMode = true;
    const spy = vi.fn();
    tab.term.scrollLines = spy;

    swipeUp(tab);

    expect(spy, "TUI passthrough: the app owns the gesture").not.toHaveBeenCalled();
  });

  it("during an owned swipe the stage suppresses xterm's own touchmove (no double-scroll)", () => {
    mockClock();
    const tab = T().openTab();
    tab.term.scrollLines = () => {};

    // Arm + cross the threshold so the swipe is "ours".
    fire(stage(), "pointerdown", { pointerType: "touch", clientX: 200, clientY: 400 });
    fire(window, "pointermove", { pointerType: "touch", clientX: 200, clientY: 360 }); // moved 40 > 10

    const tm = fire(stage(), "touchmove", { clientX: 200, clientY: 320 });
    expect(tm.defaultPrevented, "our capture handler preventDefaults the touchmove").toBe(true);

    fire(window, "pointerup", { pointerType: "touch", clientX: 200, clientY: 320 });
  });

  it("a tap that never crosses the threshold does NOT suppress touchmove", () => {
    mockClock();
    const tab = T().openTab();
    tab.term.scrollLines = () => {};

    fire(stage(), "pointerdown", { pointerType: "touch", clientX: 200, clientY: 400 });
    // tiny move, below SWIPE_THRESHOLD (10px) -> not a swipe yet.
    fire(window, "pointermove", { pointerType: "touch", clientX: 200, clientY: 396 });

    const tm = fire(stage(), "touchmove", { clientX: 200, clientY: 395 });
    expect(tm.defaultPrevented, "sub-threshold gesture passes through to xterm").toBe(false);

    fire(window, "pointerup", { pointerType: "touch", clientX: 200, clientY: 395 });
  });
});
