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
 *   2. JS behaviour: a swipe is turned into a SYNTHETIC WHEEL GESTURE on
 *      xterm's root element, so xterm itself maps it to whatever the running
 *      app understands:
 *        - normal buffer  -> viewport pixel scroll (1:1 with the finger)
 *        - alternate buffer (TUI) -> the app's own scroll keys / mouse-wheel
 *          reports. term.scrollLines() is a no-op there, which is exactly why
 *          swiping a TUI used to feel dead.
 *      Direction follows xterm's own touch convention (finger up = newer
 *      content), which is why the old velocity-curve mapping felt inverted.
 *      Mouse gestures and the explicit TUI passthrough must stay untouched.
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
 * PROBLEM 2 (JS): the swipe handler drives xterm through wheel gestures.
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
  constructor() {
    this.cols = 80; this.rows = 24; this.options = {};
    this._vY = 5; this.bufferType = "normal";
    // xterm binds its wheel listener on the root element (`term.element`), so
    // the mock exposes one and records the gestures we synthesise.
    this.element = document.createElement("div");
    this.element.className = "xterm";
    this.wheels = [];
    this.element.addEventListener("wheel", (e) => {
      this.wheels.push({ deltaY: e.deltaY, deltaMode: e.deltaMode, clientX: e.clientX, clientY: e.clientY });
    });
  }
  loadAddon() {} open() {} write() {} onData() {} focus() {} dispose() {}
  paste() {}
  scrollLines() {}
  get buffer() {
    // viewportY mid-buffer so atEdge() is false (inertia is not edge-stopped).
    return { type: this.bufferType, active: { viewportY: this._vY, length: 100 } };
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
  return vi.spyOn(performance, "now").mockImplementation(() => (t += 16));
}

// Capture the scheduled inertia frames instead of letting rAF run on its own.
function mockRaf() {
  const queue = new Map();
  let id = 0;
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((cb) => {
    queue.set(++id, cb);
    return id;
  });
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation((handle) => { queue.delete(handle); });
  return {
    pending: () => queue.size,
    run(n = 1) {
      for (let i = 0; i < n; i++) {
        const first = queue.keys().next();
        if (first.done) return;
        const cb = queue.get(first.value);
        queue.delete(first.value);
        cb();
      }
    }
  };
}

// Run a full upward swipe (finger moves UP ~px over `frames` pointermove events).
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

// Run a downward swipe (finger moves DOWN).
function swipeDown(tab, { px = 150, frames = 5 } = {}) {
  const step = px / frames;
  fire(stage(), "pointerdown", { pointerType: "touch", clientX: 200, clientY: 200 });
  let y = 200;
  for (let i = 0; i < frames; i++) {
    y += step;
    fire(window, "pointermove", { pointerType: "touch", clientX: 200, clientY: y });
  }
  fire(window, "pointerup", { pointerType: "touch", clientX: 200, clientY: y });
}

afterEach(() => {
  vi.restoreAllMocks();
  const tabs = T()._tabs;
  tabs.forEach((tab) => { tab.userClosed = true; });
  tabs.clear();
});

/* ---- pure gesture math ---- */
describe("swipe math (pure helpers)", () => {
  it("swipeWheelDelta inverts finger direction so it matches native scrolling", () => {
    expect(T().swipeWheelDelta(-30)).toBe(30);  // finger up  -> newer content
    expect(T().swipeWheelDelta(30)).toBe(-30);  // finger down -> older content
    expect(T().swipeWheelDelta(0)).toBe(0);
  });

  it("swipeWheelDelta tracks the finger 1:1 but clamps a stalled frame", () => {
    expect(T().swipeWheelDelta(-42)).toBe(42);
    expect(T().swipeWheelDelta(-100000)).toBe(120); // maxStep guard (lag spike)
    expect(T().swipeWheelDelta(100000)).toBe(-120);
    expect(T().swipeWheelDelta(-30, { sensitivity: 2 })).toBe(60);
  });

  it("blendVelocity smooths the noisy per-frame velocity toward the new sample", () => {
    expect(T().blendVelocity(0, 1, 0.35)).toBeCloseTo(0.35, 5);
    expect(T().blendVelocity(1, 1, 0.35)).toBeCloseTo(1, 5);
  });

  it("decayVelocity is frame-rate independent and stops below the floor", () => {
    expect(T().decayVelocity(1, 16)).toBeCloseTo(0.9, 5);
    expect(T().decayVelocity(1, 32)).toBeCloseTo(0.81, 5); // two 16ms frames
    expect(T().decayVelocity(0.01, 16)).toBe(0);           // too slow -> stop
    expect(T().decayVelocity(1, 0)).toBe(1);               // no time -> no decay
  });
});

/* ---- gesture routing through the real setupSwipe() handlers ---- */
describe("PROBLEM 2 — swipe drives xterm scroll (setupSwipe handlers)", () => {
  it("a touch swipe-up emits wheel gestures with POSITIVE deltaY (scroll toward newer)", () => {
    mockClock();
    const tab = T().openTab();
    swipeUp(tab, { px: 150, frames: 5 });

    const drag = tab.term.wheels.slice(0, 5);
    expect(drag.length, "one wheel gesture per pointermove").toBe(5);
    expect(drag.every((w) => w.deltaY === 30), "1:1 pixel tracking").toBe(true);
    expect(drag.every((w) => w.deltaMode === 0), "pixel delta mode").toBe(true);
  });

  it("a swipe-DOWN emits negative deltaY (scroll toward older)", () => {
    mockClock();
    const tab = T().openTab();
    swipeDown(tab, { px: 150, frames: 5 });

    const drag = tab.term.wheels.slice(0, 5);
    expect(drag.length).toBe(5);
    expect(drag.every((w) => w.deltaY === -30)).toBe(true);
  });

  it("the gesture is delivered at the finger position (xterm needs coords for mouse reports)", () => {
    mockClock();
    const tab = T().openTab();
    swipeUp(tab, { px: 100, frames: 4 });
    expect(tab.term.wheels[0].clientX).toBe(200);
    expect(tab.term.wheels[0].clientY).toBe(375);
  });

  it("a TUI (alternate buffer) still gets the gesture — that is the TUI swipe fix", () => {
    mockClock();
    const tab = T().openTab();
    tab.term.bufferType = "alternate";
    const spy = vi.fn();
    tab.term.scrollLines = spy;

    swipeUp(tab, { px: 150, frames: 5 });

    expect(tab.term.wheels.length, "wheel gesture reaches the alt buffer").toBeGreaterThan(0);
    expect(tab.term.wheels.every((w) => w.deltaY > 0)).toBe(true);
    expect(spy, "scrollLines() is a no-op on the alt buffer, so it must not be used").not.toHaveBeenCalled();
  });

  it("a MOUSE drag never scrolls (xterm keeps mouse text-selection)", () => {
    mockClock();
    const tab = T().openTab();
    swipeUp(tab, { pointerType: "mouse" });
    expect(tab.term.wheels, "mouse gesture must not hijack selection into a scroll").toHaveLength(0);
  });

  it("TUI passthrough ON => gestures reach the app, no synthetic wheel", () => {
    mockClock();
    const tab = T().openTab();
    tab.tuiMode = true;

    swipeUp(tab);

    expect(tab.term.wheels, "passthrough: the app owns the gesture").toHaveLength(0);
  });

  it("release momentum keeps scrolling after the finger lifts (rAF inertia)", () => {
    mockClock();
    const raf = mockRaf();
    const tab = T().openTab();

    swipeUp(tab, { px: 150, frames: 5 });
    const duringDrag = tab.term.wheels.length;
    expect(duringDrag).toBe(5);
    expect(raf.pending(), "pointerup schedules a momentum frame").toBe(1);

    raf.run(3);
    expect(tab.term.wheels.length, "momentum adds wheel gestures").toBeGreaterThan(duringDrag);
    expect(tab.term.wheels.every((w) => w.deltaY > 0), "momentum keeps the swipe direction").toBe(true);
    // Friction: each frame is smaller than the one before it.
    const tail = tab.term.wheels.slice(duringDrag).map((w) => w.deltaY);
    for (let i = 1; i < tail.length; i++) expect(tail[i]).toBeLessThan(tail[i - 1]);
  });

  it("momentum stops at the buffer edge (soft damping)", () => {
    mockClock();
    const raf = mockRaf();
    const tab = T().openTab();
    tab.term._vY = 0; // top of the buffer

    swipeUp(tab, { px: 150, frames: 5 });
    const atRelease = tab.term.wheels.length;
    raf.run(4);

    expect(tab.term.wheels.length, "no momentum past the edge").toBe(atRelease);
    expect(raf.pending()).toBe(0);
  });

  it("a new touch interrupts the running momentum", () => {
    mockClock();
    const raf = mockRaf();
    const tab = T().openTab();

    swipeUp(tab, { px: 150, frames: 5 });
    expect(raf.pending()).toBe(1);
    fire(stage(), "pointerdown", { pointerType: "touch", clientX: 200, clientY: 400 });
    expect(raf.pending(), "pointerdown cancels the scheduled frame").toBe(0);
  });

  it("during an owned swipe the stage suppresses xterm's own touchmove (no double-scroll)", () => {
    mockClock();
    T().openTab();

    // Arm + cross the threshold so the swipe is "ours".
    fire(stage(), "pointerdown", { pointerType: "touch", clientX: 200, clientY: 400 });
    fire(window, "pointermove", { pointerType: "touch", clientX: 200, clientY: 360 }); // moved 40 > 10

    const tm = fire(stage(), "touchmove", { clientX: 200, clientY: 320 });
    expect(tm.defaultPrevented, "our capture handler preventDefaults the touchmove").toBe(true);

    fire(window, "pointerup", { pointerType: "touch", clientX: 200, clientY: 320 });
  });

  it("a tap that never crosses the threshold does NOT suppress touchmove", () => {
    mockClock();
    T().openTab();

    fire(stage(), "pointerdown", { pointerType: "touch", clientX: 200, clientY: 400 });
    // tiny move, below SWIPE_THRESHOLD (10px) -> not a swipe yet.
    fire(window, "pointermove", { pointerType: "touch", clientX: 200, clientY: 396 });

    const tm = fire(stage(), "touchmove", { clientX: 200, clientY: 395 });
    expect(tm.defaultPrevented, "sub-threshold gesture passes through to xterm").toBe(false);

    fire(window, "pointerup", { pointerType: "touch", clientX: 200, clientY: 395 });
  });
});
