import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// i18n dict so terminal.js's t() resolves term.reconnecting / term.reconnected.
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
  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose();
  }
  /* --- test drivers --- */
  _open() {
    this.readyState = MockWebSocket.OPEN;
    if (this.onopen) this.onopen();
    (this._listeners.open || []).forEach(function (f) { f(); });
  }
  _message(d) { if (this.onmessage) this.onmessage({ data: d }); }
  // A drop NOT initiated by us (Chrome froze a backgrounded tab).
  _unexpectedClose() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose();
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
    this._onData = null;
    this.options = {};
  }
  loadAddon() {}
  open() {}
  write(s) { this.writes.push(String(s)); }
  onData(cb) { this._onData = cb; }
  focus() {}
  dispose() {}
  scrollLines() {}
  paste() {}
  get buffer() { return { active: { viewportY: 0, length: 100 } }; }
}

global.WebSocket = MockWebSocket;
window.WebSocket = MockWebSocket;
window.Terminal = MockTerminal;
window.FitAddon = { FitAddon: class { fit() {} } };

// Stable DOM the single init() binds to (do NOT rebuild per test — the
// visibilitychange listener is bound once at import time).
document.body.innerHTML =
  '<div id="terminalBody"><div id="termStage">' +
    '<div id="termTabBar"><button id="termNewTab"></button></div>' +
    '<div id="termContainers"></div>' +
  '</div></div>';

// Import AFTER mocks + DOM are in place so init() wires up correctly.
await import("../static/terminal.js");

const T = () => window.aigate.terminal;

beforeEach(() => {
  vi.useFakeTimers();
  MockWebSocket.instances.length = 0;
  // Drop any leftover tabs/timers from a previous test (module state persists
  // across tests because terminal.js is imported only once).
  const tabs = T()._tabs;
  tabs.forEach(function (tab) {
    if (tab.reconnectTimer) clearTimeout(tab.reconnectTimer);
    tab.userClosed = true;
  });
  tabs.clear();
});

afterEach(() => {
  vi.runOnlyPendingTimers();
  vi.useRealTimers();
});

/* ------------------------------------------------------------------ */

describe("computeBackoffDelay (pure)", () => {
  it("grows exponentially 0.5s,1s,2s,4s,8s then caps at ~15s", () => {
    expect(T().computeBackoffDelay(0)).toBe(500);
    expect(T().computeBackoffDelay(1)).toBe(1000);
    expect(T().computeBackoffDelay(2)).toBe(2000);
    expect(T().computeBackoffDelay(3)).toBe(4000);
    expect(T().computeBackoffDelay(4)).toBe(8000);
    expect(T().computeBackoffDelay(5)).toBe(15000); // 16000 -> capped
    expect(T().computeBackoffDelay(10)).toBe(15000);
  });
});

describe("buildCloseFrame (pure)", () => {
  it("is the deliberate-kill control frame", () => {
    expect(T().buildCloseFrame()).toBe('{"type":"close"}');
  });
});

describe("auto-reconnect + reattach", () => {
  it("unexpected onclose schedules a reconnect that REUSES the same tab_id URL", () => {
    const tab = T().openTab();
    const ws1 = tab.ws;
    const firstUrl = ws1.url;
    const id = tab.id;
    ws1._open();

    ws1._unexpectedClose();                    // transient drop, userClosed false
    vi.advanceTimersByTime(500);               // first backoff step

    const ws2 = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    expect(ws2).not.toBe(ws1);                 // a NEW socket was made
    expect(tab.ws).toBe(ws2);                  // tab now points at the new socket
    expect(ws2.url).toBe(firstUrl);            // SAME tab_id -> reattach + replay
    expect(ws2.url).toContain(encodeURIComponent(id));
  });

  it("does NOT mint a new tab_id on reconnect", () => {
    const tab = T().openTab();
    const id = tab.id;
    tab.ws._open();
    tab.ws._unexpectedClose();
    vi.advanceTimersByTime(500);
    expect(tab.id).toBe(id);                 // tab identity unchanged
    expect(T()._tabs.has(id)).toBe(true);    // still the same registered tab
  });

  it("backoff increases between successive failed attempts", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._unexpectedClose();               // schedules attempt0 -> 500ms

    let n = MockWebSocket.instances.length;
    vi.advanceTimersByTime(499);
    expect(MockWebSocket.instances.length).toBe(n);   // not yet
    vi.advanceTimersByTime(1);
    expect(MockWebSocket.instances.length).toBe(n + 1); // fired at 500ms

    // second socket drops without opening -> attempt1 -> 1000ms
    const ws2 = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    ws2._unexpectedClose();
    n = MockWebSocket.instances.length;
    vi.advanceTimersByTime(999);
    expect(MockWebSocket.instances.length).toBe(n);   // still waiting (longer)
    vi.advanceTimersByTime(1);
    expect(MockWebSocket.instances.length).toBe(n + 1);
  });

  it("writes a dim 'Reconnecting…' status once (no spam across retries)", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._unexpectedClose();
    expect(tab.term.writes.some(w => w.indexOf("Reconnecting") !== -1)).toBe(true);

    // second retry must NOT add another Reconnecting line
    vi.advanceTimersByTime(500);
    const ws2 = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    const before = tab.term.writes.filter(w => w.indexOf("Reconnecting") !== -1).length;
    ws2._unexpectedClose();
    vi.advanceTimersByTime(1000);
    const after = tab.term.writes.filter(w => w.indexOf("Reconnecting") !== -1).length;
    expect(after).toBe(before);
  });
});

describe("deliberate close (closeTab)", () => {
  it("sends {\"type\":\"close\"} then closes, and does NOT reconnect", () => {
    T().openTab();                 // tab A (will be closed)
    const b = T().openTab();       // tab B (active) so closing A spawns nothing
    const a = Array.from(T()._tabs.values()).find(t => t.id !== b.id);
    a.ws._open();

    const nBefore = MockWebSocket.instances.length;
    T().closeTab(a.id);

    expect(a.ws.sent).toContain('{"type":"close"}');   // kill frame
    expect(a.ws.readyState).toBe(MockWebSocket.CLOSED); // socket closed
    expect(a.userClosed).toBe(true);

    vi.advanceTimersByTime(60000);                      // no reconnect ever
    expect(MockWebSocket.instances.length).toBe(nBefore);
  });

  it("close frame is sent BEFORE ws.close()", () => {
    T().openTab();
    const b = T().openTab();
    const a = Array.from(T()._tabs.values()).find(t => t.id !== b.id);
    a.ws._open();
    const order = [];
    a.ws.send = function (d) { order.push("send:" + d); };
    a.ws.close = function () { order.push("close"); };
    T().closeTab(a.id);
    expect(order[0]).toBe('send:{"type":"close"}');
    expect(order[1]).toBe("close");
  });
});

describe("visibilitychange fast-path", () => {
  it("becoming visible with a closed ACTIVE ws reconnects immediately (skips backoff)", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._unexpectedClose();     // schedules a 500ms backoff reconnect

    Object.defineProperty(document, "visibilityState", {
      configurable: true, get: () => "visible"
    });
    const n = MockWebSocket.instances.length;
    document.dispatchEvent(new Event("visibilitychange"));
    vi.advanceTimersByTime(1);     // immediate, not 500ms
    expect(MockWebSocket.instances.length).toBe(n + 1);
  });

  it("does nothing on visibilitychange when the active ws is healthy", () => {
    const tab = T().openTab();
    tab.ws._open();
    Object.defineProperty(document, "visibilityState", {
      configurable: true, get: () => "visible"
    });
    const n = MockWebSocket.instances.length;
    document.dispatchEvent(new Event("visibilitychange"));
    vi.advanceTimersByTime(1);
    expect(MockWebSocket.instances.length).toBe(n);
  });
});

describe("re-send resize on reattach", () => {
  it("sends a resize frame after a successful reconnect", () => {
    const tab = T().openTab();
    tab.ws._open();
    tab.ws._unexpectedClose();
    vi.advanceTimersByTime(500);

    const ws2 = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    ws2._open();                   // reattach succeeds
    const resize = ws2.sent
      .map(s => { try { return JSON.parse(s); } catch (e) { return null; } })
      .find(f => f && f.type === "resize");
    expect(resize).toBeTruthy();
    expect(resize.cols).toBe(tab.term.cols);
    expect(resize.rows).toBe(tab.term.rows);
  });
});
