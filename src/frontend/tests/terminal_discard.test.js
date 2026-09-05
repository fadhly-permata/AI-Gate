import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

/* ------------------------------------------------------------------
 * Chrome tab DISCARD survival: the terminal must REATTACH to the same
 * backend PTY after a reload by persisting its tab ids in sessionStorage.
 *
 * A discard kills the renderer and reloads the page, so every test here
 * needs a FRESH module instance (fresh `tabs` Map + fresh `activeId`):
 * `vi.resetModules()` + a re-import replays the IIFE (and its init())
 * exactly like a browser reload does.
 * ------------------------------------------------------------------ */

// i18n dict so terminal.js's t() resolves its status strings.
import "../static/i18n.js";

/* Mocks MUST exist before terminal.js is imported (its IIFE runs init()
 * against the live jsdom document and references WebSocket / Terminal). */

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
  _unexpectedClose() {                    // a drop we did not ask for
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

const DOM =
  '<div id="terminalBody"><div id="termStage">' +
    '<div id="termTabBar"><button id="termNewTab"></button></div>' +
    '<div id="termContainers"></div>' +
    '<div id="termEmpty" hidden></div>' +
  '</div></div>';

/* Simulate a page (re)load: clean DOM, clean socket log, fresh module. */
async function reloadPage() {
  document.body.innerHTML = DOM;
  MockWebSocket.instances.length = 0;
  vi.resetModules();
  await import("../static/terminal.js");
  return window.aigate.terminal;
}

const idsOf = (T) => Array.from(T._tabs.keys());
const urlsOf = () => MockWebSocket.instances.map(ws => ws.url);

/* Replace window.sessionStorage with a throwing getter (private mode / a
 * blocked origin). Restores the real descriptor afterwards. */
async function withStorageThrowing(fn) {
  const orig = Object.getOwnPropertyDescriptor(window, "sessionStorage");
  Object.defineProperty(window, "sessionStorage", {
    configurable: true,
    get() { throw new Error("SecurityError: sessionStorage is unavailable"); }
  });
  try { return await fn(); }
  finally { Object.defineProperty(window, "sessionStorage", orig); }
}

/* Replace window.sessionStorage with a stub whose setItem throws (quota). */
async function withStorageWriteFailing(fn) {
  const orig = Object.getOwnPropertyDescriptor(window, "sessionStorage");
  Object.defineProperty(window, "sessionStorage", {
    configurable: true,
    value: { getItem: () => null, setItem: () => { throw new Error("QuotaExceededError"); } }
  });
  try { return await fn(); }
  finally { Object.defineProperty(window, "sessionStorage", orig); }
}

beforeEach(() => {
  window.sessionStorage.clear();
  MockWebSocket.instances.length = 0;
});

afterEach(() => {
  vi.useRealTimers();
});

/* ------------------------------------------------------------------
 * (a) openTab() persists its id
 * ------------------------------------------------------------------ */

describe("openTab() persists the live tab ids", () => {
  it("stores the freshly minted id in sessionStorage", async () => {
    const T = await reloadPage();
    const tab = T.openTab();

    const raw = window.sessionStorage.getItem(T._TAB_IDS_KEY);
    expect(raw).toBeTruthy();
    const saved = JSON.parse(raw);
    expect(Array.isArray(saved)).toBe(true);
    expect(saved).toEqual([tab.id]);
    // sessionStorage (per-tab), NOT localStorage (shared across tabs).
    expect(window.localStorage.getItem(T._TAB_IDS_KEY)).toBe(null);
  });

  it("accumulates every tab id in open order, without duplicates", async () => {
    const T = await reloadPage();
    const a = T.openTab();
    const b = T.openTab();
    expect(JSON.parse(window.sessionStorage.getItem(T._TAB_IDS_KEY))).toEqual([a.id, b.id]);

    T.openTab(a.id); // re-opening a live id must not duplicate the entry
    expect(JSON.parse(window.sessionStorage.getItem(T._TAB_IDS_KEY))).toEqual([a.id, b.id]);
  });

  it("openTab(id) reuses the given id instead of minting a new one", async () => {
    const T = await reloadPage();
    const tab = T.openTab("persisted-xyz");
    expect(tab.id).toBe("persisted-xyz");
    expect(tab.ws.url).toBe(T.buildTerminalWsUrl("persisted-xyz"));
    expect(JSON.parse(window.sessionStorage.getItem(T._TAB_IDS_KEY))).toEqual(["persisted-xyz"]);
  });

  it("openTab() with a non-string arg (e.g. a click Event) still mints a fresh id", async () => {
    const T = await reloadPage();
    const tab = T.openTab({ type: "click" });
    expect(typeof tab.id).toBe("string");
    expect(tab.id).not.toBe("[object Object]");
    expect(tab.ws.url).toBe(T.buildTerminalWsUrl(tab.id));
  });
});

/* ------------------------------------------------------------------
 * (b) restore-on-first-show reattaches with the PERSISTED id
 * ------------------------------------------------------------------ */

describe("reload restore (survive a Chrome tab discard)", () => {
  it("restores saved ids and opens the WS with the PERSISTED id, not a fresh uuid", async () => {
    const saved = ["discard-tab-1", "discard-tab-2"];
    window.sessionStorage.setItem("aigate.term.tabIds", JSON.stringify(saved));

    const T = await reloadPage();          // renderer was killed + reloaded
    T.onShow();                            // user navigates back to the terminal

    expect(idsOf(T)).toEqual(saved);       // same ids -> same backend PTYs
    expect(urlsOf()).toEqual([
      T.buildTerminalWsUrl("discard-tab-1"),
      T.buildTerminalWsUrl("discard-tab-2")
    ]);
    urlsOf().forEach(function (u) {
      expect(u).toContain(encodeURIComponent("discard-tab-"));
    });
  });

  it("does NOT open a fresh tab in addition to the restored ones", async () => {
    window.sessionStorage.setItem("aigate.term.tabIds", JSON.stringify(["only-tab"]));
    const T = await reloadPage();
    T.onShow();
    expect(T._tabs.size).toBe(1);
    expect(MockWebSocket.instances.length).toBe(1);   // exactly one socket
    T.onShow();                                      // a second show changes nothing
    expect(T._tabs.size).toBe(1);
    expect(MockWebSocket.instances.length).toBe(1);
  });

  it("restoring twice is idempotent (double-open guard)", async () => {
    window.sessionStorage.setItem("aigate.term.tabIds", JSON.stringify(["dup"]));
    const T = await reloadPage();
    const first = T.openTab("dup");
    const again = T.openTab("dup");
    expect(again).toBe(first);
    expect(T._restoreTabs()).toBe(true);
    expect(T._tabs.size).toBe(1);
    expect(MockWebSocket.instances.length).toBe(1);
  });

  it("empty / absent saved list behaves like a first load: exactly one fresh tab", async () => {
    const T = await reloadPage();
    T.onShow();
    expect(T._tabs.size).toBe(1);
    expect(MockWebSocket.instances.length).toBe(1);
    expect(idsOf(T)[0]).not.toBe("undefined");

    window.sessionStorage.setItem("aigate.term.tabIds", JSON.stringify([]));
    const T2 = await reloadPage();
    T2.onShow();
    expect(T2._tabs.size).toBe(1);
    expect(MockWebSocket.instances.length).toBe(1);
  });

  it("corrupt stored values are ignored (fall back to one fresh tab)", async () => {
    for (const bad of ["not json at all", '{"type":"close"}', '[null,42,"",{}]', '"just-a-string"']) {
      window.sessionStorage.setItem("aigate.term.tabIds", bad);
      const T = await reloadPage();
      T.onShow();
      expect(T._tabs.size).toBe(1);                   // one fresh tab, no throw
      expect(MockWebSocket.instances.length).toBe(1);
      expect(idsOf(T)[0]).toBeTruthy();
    }
  });

  it("a restored tab keeps the FREEZE path: a WS drop reattaches on the same id", async () => {
    vi.useFakeTimers();
    window.sessionStorage.setItem("aigate.term.tabIds", JSON.stringify(["frozen-tab"]));
    const T = await reloadPage();
    T.onShow();

    const tab = T._tabs.get("frozen-tab");
    const ws1 = tab.ws;
    const url = ws1.url;
    ws1._open();
    ws1._unexpectedClose();                // Chrome froze then dropped the socket
    vi.advanceTimersByTime(500);

    const ws2 = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    expect(ws2).not.toBe(ws1);             // a NEW socket was made
    expect(tab.ws).toBe(ws2);
    expect(ws2.url).toBe(url);             // SAME tab_id -> reattach + replay
    expect(tab.id).toBe("frozen-tab");     // identity never re-minted
  });
});

/* ------------------------------------------------------------------
 * (c) deliberate close removes the id
 * ------------------------------------------------------------------ */

describe("closeTab() forgets the id", () => {
  it("removes exactly that id from the persisted set", async () => {
    const T = await reloadPage();
    const a = T.openTab();
    const b = T.openTab();                 // b is active -> closing a spawns nothing
    expect(JSON.parse(window.sessionStorage.getItem(T._TAB_IDS_KEY))).toEqual([a.id, b.id]);

    T.closeTab(a.id);
    expect(JSON.parse(window.sessionStorage.getItem(T._TAB_IDS_KEY))).toEqual([b.id]);
  });

  it("keeps the 'at least one tab' invariant and persists the replacement id", async () => {
    const T = await reloadPage();
    const a = T.openTab();
    T.closeTab(a.id);                      // last tab -> a fresh one must take over

    const saved = JSON.parse(window.sessionStorage.getItem(T._TAB_IDS_KEY));
    expect(saved).not.toContain(a.id);
    expect(saved.length).toBe(1);
    expect(idsOf(T)).toEqual(saved);
    expect(T._tabs.size).toBe(1);
  });

  it("a user-closed tab is never resurrected by a later reload", async () => {
    const T = await reloadPage();
    const a = T.openTab();
    const b = T.openTab();
    T.closeTab(a.id);
    const survivor = idsOf(T)[0];
    expect(survivor).toBe(b.id);

    const T2 = await reloadPage();         // discard + reload
    T2.onShow();
    expect(idsOf(T2)).toEqual([b.id]);     // only the still-open tab comes back
    expect(idsOf(T2)).not.toContain(a.id);
    expect(urlsOf()).toEqual([T2.buildTerminalWsUrl(b.id)]);
    expect(survivor).toBe(b.id);
  });
});

/* ------------------------------------------------------------------
 * (d) graceful degradation when sessionStorage is unavailable
 * ------------------------------------------------------------------ */

describe("storage failure never blocks the terminal", () => {
  it("openTab() returns a working tab when sessionStorage throws", async () => {
    await withStorageThrowing(async () => {
      const T = await reloadPage();        // init() itself must not blow up
      const tab = T.openTab();

      expect(tab).toBeTruthy();
      expect(typeof tab.id).toBe("string");
      expect(tab.id.length).toBeGreaterThan(0);
      expect(tab.ws.url).toBe(T.buildTerminalWsUrl(tab.id));
      expect(T._tabs.has(tab.id)).toBe(true);

      expect(T._readSavedTabIds()).toEqual([]);   // reads degrade to "nothing saved"
      T.onShow();                                 // restore path is safe too
      expect(T._tabs.size).toBe(1);               // no extra tab, no throw
      T.closeTab(tab.id);                          // and so is the forget path
      expect(T._tabs.size).toBe(1);                // replacement tab opened anyway
    });
  });

  it("a failing setItem (quota) still opens a fully working tab", async () => {
    await withStorageWriteFailing(async () => {
      const T = await reloadPage();
      const tab = T.openTab();
      expect(tab).toBeTruthy();
      expect(tab.ws.url).toContain(encodeURIComponent(tab.id));
      T.closeTab(tab.id);
      expect(T._tabs.size).toBe(1);
    });
  });

  it("without storage the terminal behaves exactly as before (fresh id every load)", async () => {
    await withStorageThrowing(async () => {
      const T1 = await reloadPage();
      T1.onShow();
      const first = idsOf(T1)[0];

      const T2 = await reloadPage();       // simulated discard + reload
      T2.onShow();
      expect(idsOf(T2)).not.toEqual([first]);   // nothing persisted -> new shell
      expect(T2._tabs.size).toBe(1);
    });
  });
});
