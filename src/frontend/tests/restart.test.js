import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";

// i18n.js attaches window.I18N + the loader; app.js is the IIFE that defines the
// DEV-RESTART handler and exposes it on window.aigate (init() runs on an empty
// jsdom body, so the flow tests re-mount + re-wire the button themselves).
import "../static/i18n.js";
import "../static/app.js";

// Shared cached, read-only parse of the shipped page + stylesheet (helpers/dom.js).
// The dev-only hiding is a pure CSS rule that jsdom does not apply on its own, so
// the source is the contract — same approach as views.test.js / logwindow.test.js.
import { indexDocument, stylesCss } from "./helpers/dom.js";

const shipped = indexDocument();
const css = stylesCss();

/* Route-based fetch stub: returns ok:true + JSON for every unmatched call so a
   background loadLogs()/loadSettings() poll never rejects unhandled. Pass a
   route(method, url) to override specific calls, or { __error } for a 4xx. */
function stubFetch(route) {
  const calls = [];
  const respond = (handler) => {
    if (handler && handler.__error) {
      return Promise.resolve({
        ok: false,
        status: handler.status || 500,
        headers: { get: () => "application/json" },
        json: () => Promise.resolve(handler.body || {}),
      });
    }
    return Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(handler || {}),
    });
  };
  const fn = vi.fn((url, opts) => {
    opts = opts || {};
    const method = (opts.method || "GET").toUpperCase();
    const u = String(url);
    calls.push({ method, url: u });
    return respond(route ? route(method, u) : null);
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}

const flush = () => new Promise((res) => setTimeout(res, 0));

/* ===== 1. The button is a DEV-ONLY surface (source contract) =====
   It reuses the SAME body[data-devmode="off"] gate as the Log Window / Device
   Sim / Self-Heal cards — no separate JS gate — and it is accessible. */
describe("DEV-RESTART — dev-only + accessible (shipped markup contract)", () => {
  it("ships the restart card + button inside the Settings view", () => {
    // Section, not the sidebar nav anchor that also carries data-view="settings".
    const settings = shipped.querySelector('section[data-view="settings"]');
    const card = shipped.getElementById("devRestartCard");
    const btn = shipped.getElementById("devRestartBtn");
    expect(settings).not.toBeNull();
    expect(card).not.toBeNull();
    expect(btn).not.toBeNull();
    // The card sits in the Settings view and the button lives inside it.
    expect(settings.contains(card)).toBe(true);
    expect(card.contains(btn)).toBe(true);
  });

  it("labels the button for text + screen readers (aria-label + i18n binding)", () => {
    const btn = shipped.getElementById("devRestartBtn");
    expect(btn.getAttribute("aria-label")).toBeTruthy();
    // Translated label + translated accessible name.
    expect(btn.getAttribute("data-i18n")).toBe("settings.dev_restart");
    expect(btn.getAttribute("data-i18n-aria")).toBe("settings.dev_restart");
  });

  it("exposes an aria-live status region for the Restarting… message", () => {
    const msg = shipped.getElementById("devRestartMsg");
    expect(msg).not.toBeNull();
    expect(msg.getAttribute("role")).toBe("status");
    expect(msg.getAttribute("aria-live")).toBe("polite");
  });

  it("hides the card via the EXISTING body[data-devmode=off] gate (no new gate)", () => {
    // Shared dev-only marker on the card...
    expect(shipped.getElementById("devRestartCard").className).toContain("dev-restart-card");
    // ...which is a selector in the dev-mode hide block (display:none), matched
    // alongside the other surfaces. Comment-stripped css = the real contract.
    expect(css).toMatch(/body\[data-devmode="off"\][^{]*\.dev-restart-card[^{]*\{[^}]*display:\s*none/);
  });
});

/* ===== 2. Runtime: the shared gate drives visibility =====
   jsdom DOES apply an injected <style>, so we can prove "hidden when off, shown
   when on" for real by reusing the exact gate rule and toggling applyDevMode(). */
describe("DEV-RESTART — visibility follows applyDevMode", () => {
  let style;
  beforeEach(() => {
    document.body.innerHTML =
      '<div class="card settings-card dev-restart-card" id="devRestartCard"></div>';
    style = document.createElement("style");
    // Verbatim copy of the shipped dev-only hide rule for this surface.
    style.textContent = 'body[data-devmode="off"] .dev-restart-card { display: none !important; }';
    document.head.appendChild(style);
    stubFetch(() => ({ data: [] })); // keep applyDevMode()'s loadLogs poll happy
  });
  afterEach(() => {
    window.aigate.stopLogAutoRefresh();
    if (style && style.parentNode) style.parentNode.removeChild(style);
    document.body.innerHTML = "";
    vi.unstubAllGlobals();
  });

  it("off -> card computed display:none; on -> not none", () => {
    window.aigate.applyDevMode(false);
    expect(getComputedStyle(document.getElementById("devRestartCard")).display).toBe("none");
    window.aigate.applyDevMode(true);
    expect(getComputedStyle(document.getElementById("devRestartCard")).display).not.toBe("none");
  });
});

/* ===== 3. The click -> confirm -> POST -> poll -> reload flow (mocked) ===== */
describe("DEV-RESTART — flow (mock fetch + location.reload, no real restart)", () => {
  let reloadSpy;
  const realLocation = window.location;

  beforeEach(() => {
    document.body.innerHTML =
      '<div class="card settings-card dev-restart-card" id="devRestartCard">' +
        '<button type="button" id="devRestartBtn">Restart</button>' +
        '<p id="devRestartMsg" role="status" aria-live="polite"></p>' +
      "</div>";
    // jsdom's Location.reload is non-configurable, so swap the whole location
    // object (redefined back in afterEach) — app.js reads window.location.reload()
    // at call time, so it picks up the stub. Nothing actually navigates.
    reloadSpy = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: { reload: reloadSpy, href: "http://localhost/" },
    });
    window.confirm = vi.fn(() => true);
    // Bind the shipped handler to the re-mounted button (same entry point init() uses).
    window.aigate.wireDevRestart();
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      configurable: true,
      writable: true,
      value: realLocation,
    });
    delete window.confirm;
    vi.useRealTimers();
    vi.unstubAllGlobals();
    document.body.innerHTML = "";
  });

  it("health already up -> POST once, show status, reload (no restart performed)", async () => {
    const calls = stubFetch((method, url) => {
      if (method === "POST" && url === "/api/dev/restart") return { status: "restarting" };
      if (method === "GET" && url === "/api/health") return { status: "ok" };
      return null;
    });

    document.getElementById("devRestartBtn").dispatchEvent(new Event("click"));
    await flush();
    await flush();

    // Confirm asked, then exactly one POST + at least one health poll, then reload.
    expect(window.confirm).toHaveBeenCalledTimes(1);
    expect(calls.some((c) => c.method === "POST" && c.url === "/api/dev/restart")).toBe(true);
    const healthCalls = calls.filter((c) => c.method === "GET" && c.url === "/api/health");
    expect(healthCalls.length).toBeGreaterThanOrEqual(1);
    expect(reloadSpy).toHaveBeenCalledTimes(1);
    // "Restarting…" surfaced in the aria-live status while waiting.
    expect(document.getElementById("devRestartMsg").textContent).toBeTruthy();
  });

  it("health down then up -> retries on the 500ms tick, reloads once back", async () => {
    vi.useFakeTimers();
    let polls = 0;
    stubFetch((method, url) => {
      if (method === "POST" && url === "/api/dev/restart") return { status: "restarting" };
      if (method === "GET" && url === "/api/health") {
        polls += 1;
        // First probe: still down (server mid-execv). Second+ : back up.
        if (polls === 1) return { __error: true, status: 500 };
        return { status: "ok" };
      }
      return null;
    });

    document.getElementById("devRestartBtn").dispatchEvent(new Event("click"));
    // Let the POST resolve and the first (failed) health probe run.
    await vi.advanceTimersByTimeAsync(0);
    expect(reloadSpy).not.toHaveBeenCalled();
    // One 500ms interval later the second probe succeeds -> reload.
    await vi.advanceTimersByTimeAsync(500);
    expect(polls).toBeGreaterThanOrEqual(2);
    expect(reloadSpy).toHaveBeenCalledTimes(1);
  });

  it("confirm=false -> no POST, no reload", async () => {
    const calls = stubFetch(() => ({}));
    window.confirm = vi.fn(() => false);

    document.getElementById("devRestartBtn").dispatchEvent(new Event("click"));
    await flush();

    expect(window.confirm).toHaveBeenCalled();
    expect(calls.some((c) => c.method === "POST" && c.url === "/api/dev/restart")).toBe(false);
    expect(reloadSpy).not.toHaveBeenCalled();
  });

  it("403 (dev_mode_required) -> error status, no reload", async () => {
    const calls = stubFetch((method, url) => {
      if (method === "POST" && url === "/api/dev/restart") {
        return { __error: true, status: 403, body: { error: { code: "dev_mode_required" } } };
      }
      return null;
    });

    document.getElementById("devRestartBtn").dispatchEvent(new Event("click"));
    await flush();
    await flush();

    expect(calls.some((c) => c.method === "POST" && c.url === "/api/dev/restart")).toBe(true);
    expect(reloadSpy).not.toHaveBeenCalled();
    // The never-recovers guard: no health poll loop was started on a failed POST.
    expect(calls.some((c) => c.method === "GET" && c.url === "/api/health")).toBe(false);
    expect(document.getElementById("devRestartMsg").textContent).toBeTruthy();
  });
});
