import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

/* Exit-sentinel flow (BE contract, TSD §3.1), reproducing the REAL runtime
 * sequence: the server sends the TEXT frame {"type":"exit","code":<int>} when
 * the shell dies (typed exit / Ctrl-D / crash / killed) and THEN closes the WS
 * with code 1000. Both signals must close the tab; a network drop (1006, no
 * exit frame) must keep the old reconnect/reattach behavior. A toast reports
 * the exit code after the tab is gone. */

import "../static/i18n.js";

/* ------------------------------------------------------------------
 * Mocks MUST exist before terminal.js is imported (its IIFE runs init()
 * against the live jsdom document and references WebSocket / Terminal).
 * ------------------------------------------------------------------ */

class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.sent = [];
    this._listeners = {};
    this.onopen = null;
    this.onclose = null;
    this.onmessage = null;
    this.onerror = null;
    MockWebSocket.instances.push(this);
  }
  send(data) { this.sent.push(String(data)); }
  addEventListener(type, fn) {
    (this._listeners[type] = this._listeners[type] || []).push(fn);
  }
  // Client-initiated close (closeTab / liveness force): browser reports 1000.
  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code: 1000 });
  }
  /* --- test drivers --- */
  _open() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) this.onopen();
    (this._listeners.open || []).forEach(function (f) { f(); });
  }
  _message(d) { if (this.onmessage) this.onmessage({ data: d }); }
  // Network drop / frozen tab: NO close frame arrives → the browser reports 1006.
  _unexpectedClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code: 1006 });
  }
  // The BE's clean close(1000) that follows the exit sentinel.
  _serverClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ code: 1000 });
  }
}
MockWebSocket.CONNECTING = 0;
MockWebSocket.OPEN = 1;
MockWebSocket.CLOSED = 3;
MockWebSocket.instances = [];

class MockTerminal {
  constructor() {
    this.cols = 80;
    this.rows = 24;
    this.writes = [];
    this.disposed = false;
    this._onData = null;
    this.options = {};
  }
  loadAddon() {}
  open() {}
  write(s) { this.writes.push(String(s)); }
  onData(cb) { this._onData = cb; }
  focus() {}
  dispose() { this.disposed = true; }
  scrollLines() {}
  paste() {}
  get buffer() { return { active: { viewportY: 0, length: 100 } }; }
}

global.WebSocket = MockWebSocket;
window.WebSocket = MockWebSocket;
window.Terminal = MockTerminal;
window.FitAddon = { FitAddon: class { fit() {} } };

// Stable DOM the single init() binds to (termEmpty included for the empty-state
// assertion — same ids as index.html).
document.body.innerHTML =
  '<div id="terminalBody"><div id="termStage">' +
    '<div id="termTabBar"><button id="termNewTab"></button></div>' +
    '<div id="termContainers"></div>' +
    '<div id="termEmpty" hidden><button id="termEmptyNewTab"></button></div>' +
  '</div></div>';

// Import AFTER mocks + DOM are in place so init() wires up correctly.
await import("../static/terminal.js");

const T = () => window.aigate.terminal;
const toastTexts = () =>
  Array.from(document.querySelectorAll(".term-toast")).map(e => e.textContent);

beforeEach(() => {
  vi.useFakeTimers();
  MockWebSocket.instances.length = 0;
  window.sessionStorage.clear();
  document.querySelectorAll(".term-toast").forEach(e => e.remove());
  // Drop any leftover tabs/timers from a previous test (module state persists
  // because terminal.js is imported only once).
  const tabs = T()._tabs;
  tabs.forEach(function (tab) {
    if (tab.reconnectTimer) clearTimeout(tab.reconnectTimer);
    if (tab.livenessTimer) clearTimeout(tab.livenessTimer);
    tab.userClosed = true;
  });
  tabs.clear();
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

/* ------------------------------------------------------------------ */

describe("exit sentinel closes the tab (DoD 1)", () => {
  it('a {"type":"exit","code":0} frame removes the tab, disposes xterm, clears registry', () => {
    const tab = T().openTab();
    tab.ws._open();
    const id = tab.id;
    expect(T()._readSavedTabIds()).toContain(id); // sanity: saved while live

    tab.ws._message('{"type":"exit","code":0}');

    expect(T()._tabs.has(id)).toBe(false);          // gone from the registry
    expect(tab.term.disposed).toBe(true);           // xterm disposed
    expect(document.body.contains(tab.button)).toBe(false);   // tab bar entry gone
    expect(document.body.contains(tab.container)).toBe(false); // pane gone
    expect(T()._readSavedTabIds()).not.toContain(id); // never resurrected on reload
  });

  it("exit code -1 (unknown) also closes the tab", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._message('{"type":"exit","code":-1}');
    expect(T()._tabs.has(tab.id)).toBe(false);
  });

  it("an exit frame without a code field still closes the tab", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._message('{"type":"exit"}');
    expect(T()._tabs.has(tab.id)).toBe(false);
  });

  it("the exit frame is never rendered into the terminal", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._message('{"type":"exit","code":0}');
    expect(tab.term.writes.some(w => w.indexOf('"exit"') !== -1)).toBe(false);
  });

  it("a duplicate exit frame is a harmless no-op", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._message('{"type":"exit","code":0}');
    expect(() => tab.ws._message('{"type":"exit","code":0}')).not.toThrow();
    expect(T()._tabs.size).toBe(0);
  });
});

describe("real runtime sequence: exit frame THEN server close(1000) (DoD 1+2)", () => {
  it("closes the tab on the frame; the follow-up close(1000) neither errors nor reconnects", () => {
    const tab = T().openTab();
    tab.ws._open();
    const n = MockWebSocket.instances.length;

    tab.ws._message('{"type":"exit","code":0}');   // t=1.202 in the BE transcript
    tab.ws._serverClose();                          // t=1.206: server close(1000)
    vi.advanceTimersByTime(60000);

    expect(T()._tabs.has(tab.id)).toBe(false);
    expect(MockWebSocket.instances.length).toBe(n); // no reattach, ever
  });

  it("if the exit FRAME is lost, the clean close(1000) alone still closes the tab", () => {
    const tab = T().openTab();
    tab.ws._open();
    const n = MockWebSocket.instances.length;

    tab.ws._serverClose();                          // sentinel missed (frozen renderer)

    expect(T()._tabs.has(tab.id)).toBe(false);      // tab NOT left hanging
    expect(tab.term.disposed).toBe(true);
    expect(T()._readSavedTabIds()).not.toContain(tab.id);
    expect(toastTexts()).toContain("Session ended (code -1)"); // unknown code

    vi.advanceTimersByTime(60000);                  // (also flushes the toast timer)
    expect(MockWebSocket.instances.length).toBe(n); // and no new shell spawned
  });

  it("a CLIENT-initiated close(1000) from the liveness watchdog still RECONNECTS", () => {
    // Regression for the 1000-fallback branch: checkLiveness() closes the dead
    // socket itself (also code 1000) and must reattach, not close the tab.
    const tab = T().openTab();
    const ws1 = tab.ws;
    const url = ws1.url;
    ws1._open();
    Object.defineProperty(document, "visibilityState", {
      configurable: true, get: () => "visible"
    });
    vi.advanceTimersByTime(45001);                  // watchdog → ws.close() → 1000
    expect(T()._tabs.has(tab.id)).toBe(true);       // tab kept alive
    const ws2 = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    expect(ws2).not.toBe(ws1);                      // reattached with a NEW socket
    expect(ws2.url).toBe(url);                      // SAME tab_id, not a close
  });
});

describe("no reconnect and no reply frame after exit (DoD 2)", () => {
  it("sends NO kill/close frame back to the server", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._message('{"type":"exit","code":0}');
    expect(tab.ws.sent).not.toContain('{"type":"close"}');
    expect(tab.ws.sent).not.toContain('{"type":"pong"}');
  });

  it("late frames on the dead socket are ignored (no pong, no write, no throw)", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._message('{"type":"exit","code":0}');
    const writes = tab.term.writes.length;
    expect(() => tab.ws._message('{"type":"ping","t":1}')).not.toThrow();
    expect(() => tab.ws._message("stale output")).not.toThrow();
    expect(tab.term.writes.length).toBe(writes);
    expect(tab.ws.sent).not.toContain('{"type":"pong"}');
  });
});

describe("other tabs are unaffected (DoD 3)", () => {
  it("exit of the ACTIVE tab activates a survivor, kills nothing else", () => {
    const a = T().openTab();                   // tab A
    const b = T().openTab();                   // tab B (active)
    a.ws._open();
    b.ws._open();

    a.ws._message('{"type":"exit","code":0}');

    expect(T()._tabs.has(b.id)).toBe(true);
    expect(T()._tabs.has(a.id)).toBe(false);
    expect(b.term.disposed).toBe(false);
    expect(b.ws.sent).not.toContain('{"type":"close"}');
    expect(b.ws.readyState).toBe(MockWebSocket.OPEN);
  });

  it("exit of an INACTIVE tab leaves the active tab active", () => {
    const a = T().openTab();                   // tab A
    const b = T().openTab();                   // tab B (active)
    a.ws._open();
    b.ws._open();

    b.ws._message('{"type":"exit","code":1}'); // exit the inactive one

    expect(T()._tabs.has(a.id)).toBe(true);
    expect(a.container.style.display).not.toBe("none"); // still the shown pane
    expect(a.ws.sent).not.toContain('{"type":"close"}');
  });
});

describe("last tab exit → empty state, no auto shell (DoD 4)", () => {
  it("shows #termEmpty and opens NO replacement tab", () => {
    const tab = T().openTab();
    tab.ws._open();
    const n = MockWebSocket.instances.length;

    tab.ws._message('{"type":"exit","code":0}');
    tab.ws._serverClose();                     // server's final close
    vi.advanceTimersByTime(60000);

    expect(T()._tabs.size).toBe(0);
    expect(MockWebSocket.instances.length).toBe(n); // no auto-opened shell
    expect(document.getElementById("termEmpty").hidden).toBe(false);
  });
});

describe("WS drop WITHOUT an exit frame keeps reconnecting (DoD 5)", () => {
  it("a 1006 close schedules a reattach to the SAME tab_id (tab stays open)", () => {
    const tab = T().openTab();
    tab.ws._open();
    const ws1 = tab.ws;
    const url = ws1.url;
    const id = tab.id;

    ws1._unexpectedClose();                    // network drop — no sentinel, code 1006
    vi.advanceTimersByTime(500);               // first backoff step

    const ws2 = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    expect(ws2).not.toBe(ws1);                 // a NEW socket was made
    expect(tab.ws).toBe(ws2);                  // tab points at it
    expect(ws2.url).toBe(url);                 // reattach, not exit
    expect(T()._tabs.has(id)).toBe(true);      // tab still registered
    expect(T()._readSavedTabIds()).toContain(id);
    expect(toastTexts().length).toBe(0);       // no "session ended" on a drop
  });

  it("a close frame is NOT sent on a transient drop (PTY stays alive)", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._unexpectedClose();
    expect(tab.ws.sent).not.toContain('{"type":"close"}');
  });
});

describe("session-ended toast (DoD 2 of round 2)", () => {
  it("shows the exit code and OUTLIVES the disposed tab", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._message('{"type":"exit","code":0}');

    expect(T()._tabs.size).toBe(0);            // tab gone first...
    expect(toastTexts()).toContain("Session ended (code 0)"); // ...toast remains
    expect(document.body.lastElementChild.className).toBe("term-toast");
    expect(document.body.lastElementChild.getAttribute("role")).toBe("status");
  });

  it("carries the real code (42) and the unknown code (-1)", () => {
    const a = T().openTab();
    a.ws._open();
    a.ws._message('{"type":"exit","code":42}');
    expect(toastTexts()).toContain("Session ended (code 42)");

    const b = T().openTab();
    b.ws._open();
    b.ws._message('{"type":"exit"}');          // no code → -1
    expect(toastTexts()).toContain("Session ended (code -1)");
  });

  it("auto-removes after ~4s", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._message('{"type":"exit","code":0}');
    expect(document.querySelectorAll(".term-toast").length).toBe(1);
    vi.advanceTimersByTime(4000);
    expect(document.querySelectorAll(".term-toast").length).toBe(0);
  });

  it("a DELIBERATE close shows NO toast (only session endings do)", () => {
    const tab = T().openTab();
    tab.ws._open();
    T().closeTab(tab.id);
    expect(toastTexts().length).toBe(0);
  });
});

describe("deliberate close behavior is unchanged (regression)", () => {
  it("closeTab still sends the kill frame and replaces the last tab", () => {
    const tab = T().openTab();
    tab.ws._open();
    const n = MockWebSocket.instances.length;

    T().closeTab(tab.id);

    expect(tab.ws.sent).toContain('{"type":"close"}');
    expect(T()._tabs.size).toBe(1);            // a replacement was opened
    expect(MockWebSocket.instances.length).toBe(n + 1);
    expect(document.getElementById("termEmpty").hidden).toBe(true);
  });
});
