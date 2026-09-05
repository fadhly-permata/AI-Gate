import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { JSDOM } from "jsdom";

/* =====================================================================
 * Terminal toolbar — the three control-cluster features that sit on top of
 * the shared split-button dropdown:
 *
 *   F1 Keep Screen On  — Screen Wake Lock. The interesting part is NOT the
 *      happy path, it's the degradation: navigator.wakeLock only exists in a
 *      secure context, so an http://LAN-address deployment must render the
 *      button disabled instead of throwing on every tap. The browser also
 *      auto-releases the lock when the tab hides, so user INTENT is tracked
 *      separately from the sentinel and re-acquired on visibilitychange.
 *   F2 Fullscreen dropdown — the main button must STILL do what it always did
 *      (the .terminal-fullscreen CSS class = "Full Page"); the caret adds the
 *      choice, including TRUE browser fullscreen via the Fullscreen API.
 *   F3 Paste dropdown — same shape: the main button keeps normal paste, the
 *      caret adds "Paste as Code Block", whose whole contract is the EXACT
 *      fenced string, so that is asserted by equality, not by containment.
 *
 * Mocks MUST exist before terminal.js is imported: its IIFE runs init()
 * against the live jsdom document.
 * ===================================================================== */

const __dirname = dirname(fileURLToPath(import.meta.url));

/* ---- xterm / WS stubs (same shape as the other terminal suites) ---- */
class MockWebSocket {
  constructor(url) { this.url = url; this.readyState = MockWebSocket.CONNECTING; this.sent = []; }
  send(d) { this.sent.push(String(d)); }
  addEventListener() {}
  close() { this.readyState = MockWebSocket.CLOSED; if (this.onclose) this.onclose(); }
}
MockWebSocket.CONNECTING = 0; MockWebSocket.OPEN = 1; MockWebSocket.CLOSED = 3;

class MockTerminal {
  constructor() {
    this.cols = 80; this.rows = 24; this.options = {};
    this.pastes = []; this.focusCalls = 0;
    this.element = document.createElement("div");
  }
  loadAddon() {} open() {} write() {} onData() {} dispose() {} scrollLines() {}
  paste(t) { this.pastes.push(String(t)); }
  focus() { this.focusCalls += 1; }
  get buffer() { return { active: { viewportY: 0, length: 100 } }; }
}

global.WebSocket = MockWebSocket;
window.WebSocket = MockWebSocket;
window.Terminal = MockTerminal;
window.FitAddon = { FitAddon: class { fit() {} } };
global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} };
window.ResizeObserver = global.ResizeObserver;

/* ---- navigator.wakeLock stub ------------------------------------------
 * Records every request() type and hands back a sentinel that behaves like
 * the real WakeLockSentinel: it is an EventTarget-ish thing with a release()
 * that fires its own `release` listeners, plus a test-only _drop() to simulate
 * the BROWSER releasing it (tab hidden) without us asking. */
function makeWakeLock(opts) {
  opts = opts || {};
  const wl = {
    calls: [],
    sentinels: [],
    request(type) {
      wl.calls.push(type);
      if (opts.reject) return Promise.reject(new Error("NotSupportedError"));
      if (opts.throwSync) throw new Error("boom");
      const s = {
        type, released: false, _h: {},
        addEventListener(n, f) { (s._h[n] = s._h[n] || []).push(f); },
        _fire(n) { (s._h[n] || []).forEach((f) => f()); },
        release() {
          if (opts.releaseThrows) throw new Error("InvalidStateError");
          s.released = true;
          s._fire("release");
          return Promise.resolve();
        },
        _drop() { s.released = true; s._fire("release"); } // the browser took it back
      };
      wl.sentinels.push(s);
      return Promise.resolve(s);
    }
  };
  return wl;
}

/* ---- Fullscreen API stub ----------------------------------------------
 * jsdom ships neither element.requestFullscreen nor document.fullscreenElement,
 * so both are installed by hand. The mock fires the change event the way a real
 * engine does, which is what the sync path is actually tested against. */
let fsEl = null;
function installFullscreen(body) {
  fsEl = null;
  Object.defineProperty(document, "fullscreenElement", {
    configurable: true, get: () => fsEl
  });
  body.requestFullscreen = function () {
    fsEl = body;
    document.dispatchEvent(new Event("fullscreenchange"));
    return Promise.resolve();
  };
  document.exitFullscreen = function () {
    fsEl = null;
    document.dispatchEvent(new Event("fullscreenchange"));
    return Promise.resolve();
  };
}

/* The toolbar cluster, mirrored from static/index.html (ids + roles + the
   data-i18n hooks), so the tests exercise the same contract the page ships. */
const TOOLBAR =
  '<div id="terminalBody" class="terminal-body">' +
    '<div class="term-toolbar">' +
      '<div id="termTabBar" class="term-tabs"></div>' +
      '<button id="termNewTab"></button>' +
      '<div id="termFloating" class="term-floating" role="group">' +
        '<button class="icon-btn term-ctl" id="termKeepAwake" type="button" aria-pressed="false">' +
          '<i class="fa fa-sun"></i></button>' +
        '<span class="term-split" id="termFullscreenSplit">' +
          '<button class="icon-btn term-ctl" id="termFullscreen" type="button" aria-pressed="false">' +
            '<i class="fa fa-expand"></i></button>' +
          '<button class="icon-btn term-ctl term-caret" id="termFullscreenCaret" type="button"' +
            ' aria-haspopup="true" aria-expanded="false" aria-controls="termFullscreenMenu">' +
            '<i class="fa fa-caret-down"></i></button>' +
          '<span class="term-menu" id="termFullscreenMenu" role="menu" hidden>' +
            '<button class="term-menu-item" type="button" role="menuitemcheckbox"' +
              ' aria-checked="false" id="termMenuFullPage" data-action="full-page">Full Page</button>' +
            '<button class="term-menu-item" type="button" role="menuitemcheckbox"' +
              ' aria-checked="false" id="termMenuFullscreen" data-action="fullscreen">Fullscreen</button>' +
          '</span>' +
        '</span>' +
        '<span class="term-split" id="termPasteSplit">' +
          '<button class="icon-btn term-ctl" id="termPaste" type="button">' +
            '<i class="fa fa-paste"></i></button>' +
          '<button class="icon-btn term-ctl term-caret" id="termPasteCaret" type="button"' +
            ' aria-haspopup="true" aria-expanded="false" aria-controls="termPasteMenu">' +
            '<i class="fa fa-caret-down"></i></button>' +
          '<span class="term-menu" id="termPasteMenu" role="menu" hidden>' +
            '<button class="term-menu-item" type="button" role="menuitem"' +
              ' id="termMenuPaste" data-action="paste">Paste</button>' +
            '<button class="term-menu-item" type="button" role="menuitem"' +
              ' id="termMenuPasteCode" data-action="paste-code">Paste as Code Block</button>' +
          '</span>' +
        '</span>' +
        '<button class="icon-btn term-ctl" id="termTui" type="button" aria-pressed="false">' +
          '<i class="fa fa-hand-pointer"></i></button>' +
      '</div>' +
    '</div>' +
    '<div id="termStage" class="term-stage">' +
      '<div id="termContainers" class="term-containers"></div>' +
      '<div id="termEmpty" class="term-empty" hidden></div>' +
    '</div>' +
  '</div>';

document.body.innerHTML = TOOLBAR;
installFullscreen(document.getElementById("terminalBody"));

let wakeLock = makeWakeLock();
Object.defineProperty(navigator, "wakeLock", { configurable: true, writable: true, value: wakeLock });

await import("../static/i18n.js");
await import("../static/terminal.js");

const T = () => window.aigate.terminal;
const $ = (id) => document.getElementById(id);
const flush = () => new Promise((r) => setTimeout(r, 0));

/* Let the page's own locale machinery resolve the data-i18n hooks. */
function setLocale(loc) { window.applyLocale(loc); }

/* Swap navigator.wakeLock for a case. NOT restored per case — beforeEach
   reinstalls a fresh default mock, which also means the swap must still be in
   effect when the CLICK happens (a with-scope that closed before the tap would
   silently test the wrong stub). */
function setWakeLock(value) {
  if (value === null) delete navigator.wakeLock;
  else Object.defineProperty(navigator, "wakeLock", { configurable: true, writable: true, value });
  wakeLock = value || wakeLock;
}

/* Drive the engine side of fullscreen (the mock's fsEl is what
   document.fullscreenElement reports), the way a real browser would. */
function engineExitFullscreen() {
  fsEl = null;
  document.dispatchEvent(new Event("fullscreenchange"));
}

function setClipboard(text) {
  const orig = Object.getOwnPropertyDescriptor(navigator, "clipboard");
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { readText: () => Promise.resolve(text) }
  });
  return () => {
    if (orig) Object.defineProperty(navigator, "clipboard", orig);
    else delete navigator.clipboard;
  };
}

beforeEach(async () => {
  sessionStorage.clear();
  wakeLock = makeWakeLock();
  Object.defineProperty(navigator, "wakeLock", { configurable: true, writable: true, value: wakeLock });
  // Reset the module's wake-lock singleton between cases.
  T()._keepAwake.desired = false;
  T()._keepAwake.sentinel = null;
  T()._keepAwake.supported = true;
  // terminal.js is imported ONCE, so its module state (open menu, fullscreen
  // carry-over, the DOM classes it paints) outlives every case. Reset it the
  // way the code itself would, so no case inherits the last case's UI state.
  const om = T()._openMenu();
  if (om) om.close(false);
  fsEl = null;
  T()._onFullscreenChange();                             // engine-exit sync
  if ($("terminalBody").classList.contains("terminal-fullscreen")) {
    $("termFullscreen").click();                         // user-level full page OFF
  }
  T()._setupControlMenus();
  T()._setupKeepAwake();
  await T().openTab();
});

afterEach(() => {
  vi.restoreAllMocks();
  const tabs = T()._tabs;
  tabs.forEach((tab) => {
    if (tab.reconnectTimer) clearTimeout(tab.reconnectTimer);
    if (tab.livenessTimer) clearTimeout(tab.livenessTimer);
    tab.userClosed = true;
  });
  tabs.clear();
});

/* =====================================================================
 * F1 — Keep Screen On
 * ===================================================================== */
describe("F1 wakeLockSupported (pure)", () => {
  it("no wakeLock on the navigator → false (insecure context: http LAN address)", () => {
    expect(T().wakeLockSupported({})).toBe(false);
  });
  it("wakeLock with a request() function → true (secure context)", () => {
    expect(T().wakeLockSupported({ wakeLock: { request() {} } })).toBe(true);
  });
  it("wakeLock present but request is not a function → false (feature-detected)", () => {
    expect(T().wakeLockSupported({ wakeLock: {} })).toBe(false);
    expect(T().wakeLockSupported({ wakeLock: { request: 42 } })).toBe(false);
  });
});

describe("F1 Keep Screen On — feature detection / insecure context", () => {
  it("wakeLock missing → button disabled with an explanatory title, no throw", () => {
    setWakeLock(null);
    expect(T()._setupKeepAwake()).toBeUndefined();       // must not throw
    const btn = $("termKeepAwake");
    expect(btn.disabled).toBe(true);
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    expect(btn.title).toBe(window.I18N.en["term.keep_awake_unsupported"]);
    expect(btn.title).toMatch(/HTTPS|localhost/i);       // says WHAT is missing
  });

  it("tapping the disabled button never requests a lock and never throws", () => {
    setWakeLock(null);
    T()._setupKeepAwake();
    const btn = $("termKeepAwake");
    expect(() => btn.click()).not.toThrow();
    expect(T()._keepAwake.sentinel).toBeNull();
    expect(T()._keepAwake.desired).toBe(false);
  });

  it("wakeLock present → the button is enabled and labelled", () => {
    const btn = $("termKeepAwake");
    expect(btn.disabled).toBe(false);
    expect(btn.hasAttribute("aria-disabled")).toBe(false);
    expect(btn.getAttribute("aria-pressed")).toBe("false");
  });
});

describe("F1 Keep Screen On — acquire / release", () => {
  it("toggle calls navigator.wakeLock.request('screen') and presses the button", async () => {
    $("termKeepAwake").click();
    await flush();
    expect(wakeLock.calls).toEqual(["screen"]);          // exactly the SCREEN lock
    const btn = $("termKeepAwake");
    expect(btn.getAttribute("aria-pressed")).toBe("true");
    expect(btn.title).toBe(window.I18N.en["term.keep_awake_on"]);
    expect(T()._keepAwake.sentinel).toBeTruthy();
  });

  it("second toggle releases the sentinel and un-presses the button", async () => {
    const btn = $("termKeepAwake");
    btn.click();
    await flush();
    const s = wakeLock.sentinels[0];
    btn.click();
    await flush();
    expect(s.released).toBe(true);                       // sentinel.release() ran
    expect(T()._keepAwake.sentinel).toBeNull();
    expect(btn.getAttribute("aria-pressed")).toBe("false");
  });

  it("persists the intent in sessionStorage as 1/0", async () => {
    const btn = $("termKeepAwake");
    btn.click();
    await flush();
    expect(sessionStorage.getItem("aigate.term.keepAwake")).toBe("1");
    btn.click();
    await flush();
    expect(sessionStorage.getItem("aigate.term.keepAwake")).toBe("0");
  });

  it("a rejected request() reverts to OFF + an error title (no silent swallow)", async () => {
    setWakeLock(makeWakeLock({ reject: true }));
    T()._setupKeepAwake();
    const btn = $("termKeepAwake");
    btn.click();
    await flush();
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    expect(btn.title).toBe(window.I18N.en["term.keep_awake_error"]);
    expect(T()._keepAwake.desired).toBe(false);          // intent rolled back too
    expect(sessionStorage.getItem("aigate.term.keepAwake")).toBe("0");
  });

  it("a request() that throws synchronously is caught, not propagated", async () => {
    setWakeLock(makeWakeLock({ throwSync: true }));
    T()._setupKeepAwake();
    expect(() => $("termKeepAwake").click()).not.toThrow();
    await flush();
    expect($("termKeepAwake").getAttribute("aria-pressed")).toBe("false");
  });
});

describe("F1 Keep Screen On — auto-release + re-acquire", () => {
  it("the browser releasing the sentinel reflects OFF visually but KEEPS intent", async () => {
    const btn = $("termKeepAwake");
    btn.click();
    await flush();
    wakeLock.sentinels[0]._drop();                       // tab hidden → auto-release
    expect(btn.getAttribute("aria-pressed")).toBe("false");
    expect(T()._keepAwake.desired).toBe(true);           // the user still wants it
    expect(sessionStorage.getItem("aigate.term.keepAwake")).toBe("1");
  });

  it("visibilitychange re-acquires when intent is on and no sentinel is held", async () => {
    const btn = $("termKeepAwake");
    btn.click();
    await flush();
    wakeLock.sentinels[0]._drop();
    document.dispatchEvent(new Event("visibilitychange"));
    await flush();
    expect(wakeLock.calls).toEqual(["screen", "screen"]); // requested a SECOND time
    expect(btn.getAttribute("aria-pressed")).toBe("true");
  });

  it("visibilitychange does NOT re-acquire once the user turned it off", async () => {
    const btn = $("termKeepAwake");
    btn.click();
    await flush();
    btn.click();                                          // explicit OFF
    await flush();
    document.dispatchEvent(new Event("visibilitychange"));
    await flush();
    expect(wakeLock.calls).toEqual(["screen"]);           // no second request
  });

  it("init/onShow auto-acquires a persisted intent (no user gesture needed)", async () => {
    sessionStorage.setItem("aigate.term.keepAwake", "1");
    T()._setupKeepAwake();
    await flush();
    expect(wakeLock.calls).toEqual(["screen"]);
    expect($("termKeepAwake").getAttribute("aria-pressed")).toBe("true");
  });

  it("a persisted intent is ignored when the context is not secure", () => {
    sessionStorage.setItem("aigate.term.keepAwake", "1");
    setWakeLock(null);
    T()._setupKeepAwake();
    expect($("termKeepAwake").disabled).toBe(true);
    expect(T()._keepAwake.desired).toBe(false);
  });
});

/* =====================================================================
 * F2 — Fullscreen dropdown
 * ===================================================================== */
describe("F2 Fullscreen dropdown — defaults preserved", () => {
  it("the MAIN button still toggles the .terminal-fullscreen CSS class (Full Page)", () => {
    const body = $("terminalBody");
    const btn = $("termFullscreen");
    btn.click();
    expect(body.classList.contains("terminal-fullscreen")).toBe(true);
    expect(btn.getAttribute("aria-pressed")).toBe("true");
    expect(btn.querySelector("i").className).toBe("fa fa-compress");
    expect(btn.title).toBe(window.I18N.en["term.exit_full_page"]);
    expect(fsEl).toBeNull();                              // NOT true fullscreen
    btn.click();
    expect(body.classList.contains("terminal-fullscreen")).toBe(false);
    expect(btn.querySelector("i").className).toBe("fa fa-expand");
  });

  it("the caret opens the menu on TAP and lists both choices", () => {
    const caret = $("termFullscreenCaret"), menu = $("termFullscreenMenu");
    expect(menu.hidden).toBe(true);
    caret.click();
    expect(menu.hidden).toBe(false);
    expect(caret.getAttribute("aria-expanded")).toBe("true");
    expect(menu.querySelectorAll(".term-menu-item").length).toBe(2);
  });

  it("menu 'Full Page' toggles the same CSS class as the main button", () => {
    const body = $("terminalBody");
    $("termFullscreenCaret").click();
    $("termMenuFullPage").click();
    expect(body.classList.contains("terminal-fullscreen")).toBe(true);
    expect(fsEl).toBeNull();
  });

  it("menu 'Fullscreen' calls requestFullscreen on #terminalBody", () => {
    const spy = vi.spyOn($("terminalBody"), "requestFullscreen");
    $("termFullscreenCaret").click();
    $("termMenuFullscreen").click();
    expect(spy).toHaveBeenCalledTimes(1);
    expect($("terminalBody").classList.contains("terminal-fullscreen")).toBe(true);
  });

  it("fullscreenchange syncs aria-checked / title, and exit goes through exitFullscreen", async () => {
    const item = $("termMenuFullscreen"), caret = $("termFullscreenCaret");
    caret.click();
    item.click();                                         // enter
    expect(item.getAttribute("aria-checked")).toBe("true");
    expect(item.title).toBe(window.I18N.en["term.exit_fullscreen"]);
    expect(caret.getAttribute("data-fs")).toBe("on");
    const ex = vi.spyOn(document, "exitFullscreen");
    caret.click();
    item.click();                                         // same item is a TOGGLE
    expect(ex).toHaveBeenCalledTimes(1);
    expect(fsEl).toBeNull();
    expect(item.getAttribute("aria-checked")).toBe("false");
    expect(item.title).toBe(window.I18N.en["term.fullscreen"]);
    expect(caret.getAttribute("data-fs")).toBe("off");
  });

  it("true fullscreen carries the full-page class and drops it again on exit", () => {
    const body = $("terminalBody");
    expect(body.classList.contains("terminal-fullscreen")).toBe(false);
    $("termFullscreenCaret").click();
    $("termMenuFullscreen").click();                      // enter (carries the class)
    expect(body.classList.contains("terminal-fullscreen")).toBe(true);
    expect(T()._fsCarriedFullPage()).toBe(true);
    engineExitFullscreen();                                // engine left on its own
    expect(body.classList.contains("terminal-fullscreen")).toBe(false);
    expect(T()._fsCarriedFullPage()).toBe(false);
  });

  it("a full-page choice the user made himself survives leaving true fullscreen", () => {
    const body = $("terminalBody");
    $("termFullscreen").click();                           // user: Full Page ON
    $("termFullscreenCaret").click();
    $("termMenuFullscreen").click();                       // + true fullscreen
    engineExitFullscreen();
    expect(body.classList.contains("terminal-fullscreen")).toBe(true); // stays ON
  });

  it("no requestFullscreen on the element → the item is disabled + explained", () => {
    const body = $("terminalBody");
    const saved = body.requestFullscreen;
    delete body.requestFullscreen;
    try {
      T()._setupControlMenus();
      const item = $("termMenuFullscreen");
      expect(item.disabled).toBe(true);
      expect(item.getAttribute("aria-disabled")).toBe("true");
      expect(item.title).toBe(window.I18N.en["term.fullscreen_unsupported"]);
      expect(() => T()._toggleTrueFullscreen()).not.toThrow();
    } finally {
      body.requestFullscreen = saved;
      T()._setupControlMenus();
    }
  });
});

/* =====================================================================
 * F3 — Paste dropdown
 * ===================================================================== */
describe("F3 Paste dropdown", () => {
  it("the MAIN button still sends the raw clipboard text", async () => {
    const restore = setClipboard("echo hi");
    $("termPaste").click();
    await flush();
    restore();
    const term = Array.from(T()._tabs.values())[0].term;
    expect(term.pastes).toEqual(["echo hi"]);
    expect(term.focusCalls).toBeGreaterThan(0);
  });

  it("'Paste as Code Block' sends EXACTLY the fenced string", async () => {
    const text = "if (a) {\n  b();\n}";
    const restore = setClipboard(text);
    $("termPasteCaret").click();
    $("termMenuPasteCode").click();
    await flush();
    restore();
    const term = Array.from(T()._tabs.values())[0].term;
    expect(term.pastes).toEqual(["```" + "\n" + text + "\n" + "```"]);
    // Spelled out once more so a "helpful" reformat can never pass silently.
    expect(term.pastes[0]).toBe("```\nif (a) {\n  b();\n}\n```");
    expect(term.pastes[0].endsWith("```")).toBe(true);    // NO trailing newline
    expect(term.focusCalls).toBeGreaterThan(0);
  });

  it("the menu 'Paste' item is the same normal paste as the main button", async () => {
    const restore = setClipboard("ls -la");
    $("termPasteCaret").click();
    $("termMenuPaste").click();
    await flush();
    restore();
    expect(Array.from(T()._tabs.values())[0].term.pastes).toEqual(["ls -la"]);
  });

  it("an empty clipboard pastes nothing but still returns focus", async () => {
    const restore = setClipboard("");
    $("termPasteCaret").click();
    $("termMenuPasteCode").click();
    await flush();
    restore();
    const term = Array.from(T()._tabs.values())[0].term;
    expect(term.pastes).toEqual([]);
    expect(term.focusCalls).toBeGreaterThan(0);
  });

  it("wrapCodeBlock is pure and adds NO indentation", () => {
    // The EXACT contract from the handover: fence + \n + verbatim + \n + fence,
    // no trailing newline, no added indentation.
    expect(T().wrapCodeBlock("abc")).toBe("```" + "\n" + "abc" + "\n" + "```");
    expect(T().wrapCodeBlock("abc")).toBe("```\nabc\n```");
    expect(T().wrapCodeBlock("abc").endsWith("```")).toBe(true);   // NO trailing \n
    expect(T().wrapCodeBlock("abc").startsWith("```")).toBe(true); // NO leading \n
    expect(T().wrapCodeBlock("a\nb")).toBe("```\na\nb\n```");
    expect(T().wrapCodeBlock("  indented")).toBe("```\n  indented\n```"); // verbatim
    expect(T().wrapCodeBlock("")).toBe("```\n\n```");                     // empty-ish
  });
});

/* =====================================================================
 * The shared dropdown component (both menus)
 * ===================================================================== */
describe("Shared dropdown — open/close semantics", () => {
  it("tapping OUTSIDE closes the open menu", () => {
    $("termPasteCaret").click();
    expect($("termPasteMenu").hidden).toBe(false);
    document.body.click();                                // a tap anywhere else
    expect($("termPasteMenu").hidden).toBe(true);
    expect($("termPasteCaret").getAttribute("aria-expanded")).toBe("false");
  });

  it("an item tap closes the menu (the action ran, nothing left hanging)", () => {
    $("termPasteCaret").click();
    $("termMenuPaste").click();
    expect($("termPasteMenu").hidden).toBe(true);
    expect($("termPasteCaret").getAttribute("aria-expanded")).toBe("false");
  });

  it("Esc closes the menu and returns focus to the caret", () => {
    const caret = $("termFullscreenCaret"), menu = $("termFullscreenMenu");
    caret.click();
    expect(menu.hidden).toBe(false);
    menu.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(menu.hidden).toBe(true);
    expect(document.activeElement).toBe(caret);
  });

  it("only ONE menu can be open at a time", () => {
    $("termFullscreenCaret").click();
    expect($("termFullscreenMenu").hidden).toBe(false);
    $("termPasteCaret").click();
    expect($("termPasteMenu").hidden).toBe(false);
    expect($("termFullscreenMenu").hidden).toBe(true);    // the first one gave way
    expect($("termFullscreenCaret").getAttribute("aria-expanded")).toBe("false");
  });

  it("the caret tap toggles: a second tap closes it again", () => {
    const caret = $("termPasteCaret"), menu = $("termPasteMenu");
    caret.click();
    expect(menu.hidden).toBe(false);
    caret.click();
    expect(menu.hidden).toBe(true);
  });

  it("arrow keys move focus between items and wrap", () => {
    const menu = $("termPasteMenu");
    $("termPasteCaret").click();
    expect(document.activeElement).toBe($("termMenuPaste")); // opened → first item
    menu.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    expect(document.activeElement).toBe($("termMenuPasteCode"));
    menu.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
    expect(document.activeElement).toBe($("termMenuPaste")); // wrapped
    menu.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowUp", bubbles: true }));
    expect(document.activeElement).toBe($("termMenuPasteCode")); // wrapped back
  });

  it("a disabled item is skipped by keyboard navigation", () => {
    const body = $("terminalBody"), saved = body.requestFullscreen;
    delete body.requestFullscreen;
    try {
      T()._setupControlMenus();
      const menu = $("termFullscreenMenu");
      $("termFullscreenCaret").click();
      expect(document.activeElement).toBe($("termMenuFullPage"));
      menu.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
      expect(document.activeElement).toBe($("termMenuFullPage")); // never lands on it
    } finally {
      body.requestFullscreen = saved;
      T()._setupControlMenus();
    }
  });

  it("the caret exposes the menu-button contract", () => {
    ["termFullscreenCaret", "termPasteCaret"].forEach((id) => {
      const c = $(id);
      expect(c.getAttribute("aria-haspopup")).toBe("true");
      expect(["true", "false"]).toContain(c.getAttribute("aria-expanded"));
      expect(c.getAttribute("aria-controls")).toMatch(/Menu$/);
    });
  });
});

/* =====================================================================
 * Markup + i18n parity (the shipped page, not the fixture)
 * ===================================================================== */
describe("Toolbar markup shipped in index.html", () => {
  const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
  const doc = new JSDOM(html).window.document;
  const floating = doc.getElementById("termFloating");

  it("the cluster holds keep-awake + two split buttons + TUI", () => {
    expect(floating.querySelector("#termKeepAwake")).not.toBeNull();
    expect(floating.querySelector("#termFullscreenCaret")).not.toBeNull();
    expect(floating.querySelector("#termPasteCaret")).not.toBeNull();
    // The pre-existing hooks are all still there (no regression).
    ["termFullscreen", "termPaste", "termTui"].forEach((id) => {
      expect(floating.querySelector("#" + id)).not.toBeNull();
    });
  });

  it("every menu item is a real <button> with a data-action", () => {
    const items = floating.querySelectorAll(".term-menu-item");
    expect(items.length).toBe(4);
    items.forEach((b) => {
      expect(b.tagName.toLowerCase()).toBe("button");
      expect(b.getAttribute("data-action")).toBeTruthy();
    });
  });

  it("no user-facing string is hardcoded without a data-i18n hook", () => {
    floating.querySelectorAll(".term-menu-item").forEach((b) => {
      expect(b.hasAttribute("data-i18n")).toBe(true);
    });
    ["termKeepAwake", "termFullscreenCaret", "termPasteCaret"].forEach((id) => {
      expect(doc.getElementById(id).hasAttribute("data-i18n-aria")).toBe(true);
    });
  });
});

describe("Toolbar i18n keys (EN + ID parity, no drift)", () => {
  const KEYS = [
    "term.full_page", "term.exit_full_page", "term.fullscreen", "term.exit_fullscreen",
    "term.fullscreen_unsupported", "term.fullscreen_menu",
    "term.paste", "term.paste_menu", "term.paste_code",
    "term.keep_awake", "term.keep_awake_on", "term.keep_awake_off",
    "term.keep_awake_unsupported", "term.keep_awake_error"
  ];
  KEYS.forEach((k) => {
    it(k + " exists in BOTH locales and differs (a real translation)", () => {
      expect(typeof window.I18N.en[k]).toBe("string");
      expect(typeof window.I18N.id[k]).toBe("string");
      expect(window.I18N.en[k].length).toBeGreaterThan(3);
      expect(window.I18N.id[k]).not.toBe(window.I18N.en[k]);
    });
  });

  it("the handover wording is honoured: Keep Screen On / Layar Tetap Nyala", () => {
    expect(window.I18N.en["term.keep_awake"]).toBe("Keep Screen On");
    expect(window.I18N.id["term.keep_awake"]).toBe("Layar Tetap Nyala");
    expect(window.I18N.id["term.full_page"]).toBe("Sepenuh Halaman");
    expect(window.I18N.id["term.fullscreen"]).toBe("Layar Penuh");
    expect(window.I18N.id["term.paste_code"]).toBe("Tempel sebagai Blok Kode");
  });

  it("the toolbar labels resolve through applyLocale, not hardcoded JS", () => {
    // A THROWAWAY node: rewriting document.body would detach the live toolbar
    // that terminal.js bound its listeners to at import time.
    const probe = document.createElement("b");
    probe.setAttribute("data-i18n", "term.paste_code");
    document.body.appendChild(probe);
    try {
      setLocale("id");
      expect(probe.textContent).toBe(window.I18N.id["term.paste_code"]);
      setLocale("en");
      expect(probe.textContent).toBe(window.I18N.en["term.paste_code"]);
    } finally {
      probe.remove();
    }
  });
});

/* =====================================================================
 * The dropdown styling contract (structural, like terminal_layout.test.js:
 * presence of the fix, not pixel values — jsdom has no layout engine).
 * ===================================================================== */
describe("Dropdown CSS contract", () => {
  const cssRaw = readFileSync(join(__dirname, "..", "static", "styles.css"), "utf8");
  const css = cssRaw.replace(/\/\*[\s\S]*?\*\//g, "");
  const block = (re) => { const m = css.match(re); return m ? m[0] : null; };

  it("the popover is anchored to the split and opts back into pointer events", () => {
    const menu = block(/(^|\n)\.term-menu\s*\{[^}]*\}/);
    expect(menu, ".term-menu rule present").toBeTruthy();
    expect(menu).toMatch(/position:\s*absolute/);
    expect(menu).toMatch(/pointer-events:\s*auto/); // .term-floating is pointer-events:none
    expect(menu).toMatch(/z-index:\s*\d+/);         // must clear the xterm stage
    expect(block(/\.term-menu\[hidden\]\s*\{[^}]*\}/)).toMatch(/display:\s*none/);
  });

  it("items are finger-sized buttons, not tiny links", () => {
    const item = block(/(^|\n)\.term-menu-item\s*\{[^}]*\}/);
    expect(item, ".term-menu-item rule present").toBeTruthy();
    expect(item).toMatch(/min-height:\s*\d+px/);
    const h = Number(item.match(/min-height:\s*(\d+)px/)[1]);
    expect(h).toBeGreaterThanOrEqual(40);            // Android touch target floor
  });

  it("the split keeps the shared control height and the caret reads as separate", () => {
    expect(block(/(^|\n)\.term-split\s*\{[^}]*\}/)).toMatch(/position:\s*relative/);
    const caret = block(/\.term-split \.term-caret\s*\{[^}]*\}/);
    expect(caret, ".term-caret rule present").toBeTruthy();
    expect(caret).toMatch(/border-left:/);           // visible seam from the main btn
    // The main control sizing still comes from the ONE shared token.
    expect(block(/\.term-floating \.term-ctl\s*\{[^}]*\}/)).toMatch(/height:\s*var\(--term-ctl\)/);
  });

  it("a disabled control is visibly off (keep-awake insecure / unsupported FS)", () => {
    const dis = block(/\.term-floating \.term-ctl\[aria-disabled="true"\]\s*\{[^}]*\}/);
    expect(dis, "disabled control rule present").toBeTruthy();
    expect(dis).toMatch(/opacity:/);
    expect(dis).toMatch(/cursor:\s*not-allowed/);
    expect(block(/\.term-menu-item\[aria-disabled="true"\]\s*\{[^}]*\}/)).toMatch(/opacity:/);
  });
});
