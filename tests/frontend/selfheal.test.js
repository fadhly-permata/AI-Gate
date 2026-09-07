import { describe, it, expect } from "vitest";

// Pure helpers for the B4.1 Self-Heal UI. Import the i18n dictionary first so
// `window.I18N` is populated, then the module under test. No DOM needed for
// renderSelfHealStatus / renderAgenticCheck — they are pure.
import "../../src/frontend/static/i18n.js";
import "../../src/frontend/static/selfheal.js";

const renderSelfHealStatus = window.aigate.renderSelfHealStatus;
const renderAgenticCheck = window.aigate.renderAgenticCheck;

describe("renderAgenticCheck (GET /api/self-heal/agentic-cli)", () => {
  it("flags missing CLI and returns the no-agentic-CLI message (EN)", () => {
    const v = renderAgenticCheck({ available: false, cli: null }, "en");
    expect(v.available).toBe(false);
    expect(v.message).toBe("Self-Heal can't run: no agentic CLI installed");
  });

  it("flags missing CLI with null body and returns ID message", () => {
    const v = renderAgenticCheck(null, "id");
    expect(v.available).toBe(false);
    expect(v.message).toBe("Self-Heal tidak bisa berjalan: tidak ada agentic CLI terinstall");
  });

  it("reports available CLI name (EN)", () => {
    const v = renderAgenticCheck({ available: true, cli: "claude" }, "en");
    expect(v.available).toBe(true);
    expect(v.cli).toBe("claude");
    expect(v.message).toBe("Agentic CLI detected: claude");
  });

  it("reports available CLI name (ID)", () => {
    const v = renderAgenticCheck({ available: true, cli: "aider" }, "id");
    expect(v.available).toBe(true);
    expect(v.message).toBe("Agentic CLI terdeteksi: aider");
  });
});

describe("renderSelfHealStatus (POST /api/self-heal/run)", () => {
  it("no_agentic_cli -> error with no-CLI message (EN)", () => {
    const v = renderSelfHealStatus({ ok: false, reason: "no_agentic_cli" }, "en");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Self-Heal can't run: no agentic CLI installed");
  });

  it("no_agentic_cli -> ID message", () => {
    const v = renderSelfHealStatus({ ok: false, reason: "no_agentic_cli" }, "id");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Self-Heal tidak bisa berjalan: tidak ada agentic CLI terinstall");
  });

  it("git_failed -> error with detail appended (EN)", () => {
    const v = renderSelfHealStatus({ ok: false, reason: "git_failed", detail: "not a repo" }, "en");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Git operation failed (not a repo)");
  });

  it("git_failed -> ID message + detail", () => {
    const v = renderSelfHealStatus({ ok: false, reason: "git_failed", detail: "bukan repo" }, "id");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Operasi git gagal (bukan repo)");
  });

  it("merged:true -> ok with iteration count (EN)", () => {
    const v = renderSelfHealStatus({ ok: true, merged: true, iterations: 3 }, "en");
    expect(v.kind).toBe("ok");
    expect(v.message).toBe("Self-Heal complete: all issues resolved & merged to main (3 iterations).");
  });

  it("merged:true -> ID with iteration count", () => {
    const v = renderSelfHealStatus({ ok: true, merged: true, iterations: 3 }, "id");
    expect(v.kind).toBe("ok");
    expect(v.message).toBe("Self-Heal selesai: semua issue teratasi & di-merge ke main. (3 iterasi).");
  });

  it("merged:false -> warn with remaining count (EN)", () => {
    const v = renderSelfHealStatus({ ok: true, merged: false, remaining: 2 }, "en");
    expect(v.kind).toBe("warn");
    expect(v.message).toBe("Self-Heal ran but 2 issue(s) remain unresolved.");
  });

  it("merged:false -> ID with remaining count", () => {
    const v = renderSelfHealStatus({ ok: true, merged: false, remaining: 2 }, "id");
    expect(v.kind).toBe("warn");
    expect(v.message).toBe("Self-Heal berjalan tapi 2 issue belum teratasi.");
  });

  it("unexpected 500 error envelope -> error with message", () => {
    const v = renderSelfHealStatus(
      { error: { message: "boom", type: "internal", code: "self_heal_failed" } }, "en"
    );
    expect(v.kind).toBe("error");
    expect(v.message).toBe("boom");
  });

  it("network failure sentinel -> generic error (EN)", () => {
    const v = renderSelfHealStatus({ _networkError: true }, "en");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Self-Heal failed unexpectedly.");
  });

  it("null result -> generic error (EN)", () => {
    const v = renderSelfHealStatus(null, "en");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Self-Heal failed unexpectedly.");
  });
});


/* =====================================================================
 * Async run flow (B4.2): POST /run starts a background run bound to the
 * backend tab key "self-heal" (live PTY), and the final result arrives via
 * GET /status -> status.last. The DOM module is re-imported with the view
 * DOM mounted (fresh init wires the real buttons); fetch is stubbed with
 * realistic statuses and fake timers drive the poller.
 * ===================================================================== */
import { vi, beforeEach, afterEach } from "vitest";

const _t = window.aigate.selfHeal._test;

/* Mount the minimal DOM the module talks to. */
function mountSelfHealDom() {
  document.body.innerHTML =
    '<p id="selfHealCheckMsg" role="status"></p>' +
    '<div id="selfHealResult" role="status" aria-live="polite"></div>' +
    '<button id="selfHealRunBtn" type="button">Run</button>' +
    '<nav><a class="nav-item" data-view="terminal" href="#"></a></nav>';
}

/* Fresh module instance so init() wires listeners against the mounted DOM. */
async function freshSelfHeal() {
  vi.resetModules();
  await import("../static/selfheal.js");
  return window.aigate.selfHeal;
}

/* fetch stub with realistic HTTP statuses.
 * Route value: {status, body} | body (= 200) | Error (network failure).
 * The routes object stays live: tests can retarget a route mid-test. */
function stubFetch(routes) {
  const fn = vi.fn(function (url, opts) {
    const key = url + " " + ((opts && opts.method) || "GET");
    const spec = routes[key];
    if (!spec) return Promise.reject(new Error("unrouted: " + key));
    if (spec instanceof Error) return Promise.reject(spec);
    const status = typeof spec.status === "number" ? spec.status : 200;
    const body = spec.body !== undefined ? spec.body : spec;
    return Promise.resolve({
      ok: status >= 200 && status < 300,
      status: status,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(body)
    });
  });
  fn.routes = routes;
  return fn;
}

const RUN_STARTED = { status: 200, body: { ok: true, started: true, tab: "self-heal" } };
const RUN_409 = { status: 409, body: { ok: false, reason: "already_running", tab: "self-heal" } };
const CLI_OK = { available: true, cli: "claude" };

function mockTerminalManager() {
  const openTab = vi.fn(function () { return { id: "self-heal" }; });
  window.aigate.terminalManager = { openTab: openTab };
  return openTab;
}

const runResultEl = () => document.getElementById("selfHealResult");
const runBtnEl = () => document.getElementById("selfHealRunBtn");
const navTerminalEl = () => document.querySelector('.nav-item[data-view="terminal"]');

let SH;
let navClicks;

beforeEach(() => {
  vi.useFakeTimers();
  mountSelfHealDom();
  navClicks = 0;
  navTerminalEl().addEventListener("click", function (e) { e.preventDefault(); navClicks++; });
  document.documentElement.setAttribute("data-locale", "en");
});

afterEach(() => {
  _t.stopStatusPolling();
  vi.useRealTimers();
  vi.restoreAllMocks();
  delete window.aigate.terminalManager;
  delete global.fetch;
  document.body.innerHTML = "";
});

/* Run the real flow: fresh module -> CLI check passes -> Run button click. */
async function clickRun(routes) {
  routes["/api/self-heal/agentic-cli GET"] = CLI_OK;
  const fetchMock = stubFetch(routes);
  global.fetch = fetchMock;
  mockTerminalManager();
  SH = await freshSelfHeal();
  SH.checkAgenticCli();
  await vi.advanceTimersByTimeAsync(0); // flush microtasks (no interval fires)
  expect(runBtnEl().disabled).toBe(false); // CLI present -> Run armed
  runBtnEl().click();
  await vi.advanceTimersByTimeAsync(0); // flush microtasks (no interval fires)
  return fetchMock;
}

const statusCalls = (fm) => fm.mock.calls.filter((c) => c[0] === "/api/self-heal/status").length;

describe("runSelfHeal — async started flow (200 {started:true})", () => {
  it("shows the started message, opens the self-heal terminal tab, switches view", async () => {
    const fm = await clickRun({
      "/api/self-heal/run POST": RUN_STARTED,
      "/api/self-heal/status GET": { running: true, last: null }
    });
    expect(fm).toHaveBeenCalledWith("/api/self-heal/run",
      expect.objectContaining({ method: "POST" }));
    expect(runResultEl().textContent).toBe(window.I18N.en["selfheal.started"]);
    expect(runResultEl().className).toContain("selfheal-result-info");
    expect(window.aigate.terminalManager.openTab).toHaveBeenCalledWith("self-heal");
    expect(navClicks).toBe(1);
    expect(runBtnEl().disabled).toBe(true); // stays disabled while running
  });

  it("starts polling: immediate fetch + 5s cadence, stops on finished result", async () => {
    const fm = await clickRun({
      "/api/self-heal/run POST": RUN_STARTED,
      "/api/self-heal/status GET": { running: true, last: null }
    });
    expect(statusCalls(fm)).toBe(1); // immediate first poll
    await vi.advanceTimersByTimeAsync(5000);
    expect(statusCalls(fm)).toBe(2);
    // Backend finishes: merged:true -> ok render, Run stays disabled.
    fm.routes["/api/self-heal/status GET"] =
      { running: false, last: { ok: true, merged: true, iterations: 2 } };
    await vi.advanceTimersByTimeAsync(5000);
    expect(statusCalls(fm)).toBe(3);
    expect(runResultEl().textContent).toContain("2 iterations");
    expect(runResultEl().className).toContain("selfheal-result-ok");
    expect(runBtnEl().disabled).toBe(true);
    await vi.advanceTimersByTimeAsync(15000);
    expect(statusCalls(fm)).toBe(3); // poller stopped — no further fetches
  });

  it("renders partial result (merged:false) from status.last and re-enables Run", async () => {
    await clickRun({
      "/api/self-heal/run POST": RUN_STARTED,
      "/api/self-heal/status GET":
        { running: false, last: { ok: true, merged: false, remaining: 3 } }
    });
    expect(runResultEl().textContent).toBe(
      window.I18N.en["selfheal.partial"].replace("{n}", "3"));
    expect(runResultEl().className).toContain("selfheal-result-warn");
    expect(runBtnEl().disabled).toBe(false);
  });

  it("renders no_agentic_cli from status.last as an error", async () => {
    await clickRun({
      "/api/self-heal/run POST": RUN_STARTED,
      "/api/self-heal/status GET":
        { running: false, last: { ok: false, reason: "no_agentic_cli" } }
    });
    expect(runResultEl().textContent).toBe(window.I18N.en["selfheal.no_cli"]);
    expect(runResultEl().className).toContain("selfheal-result-error");
    expect(runBtnEl().disabled).toBe(false);
  });
});

describe("runSelfHeal — 409 already_running", () => {
  it("warns AND still opens the self-heal tab, keeps polling", async () => {
    const fm = await clickRun({
      "/api/self-heal/run POST": RUN_409,
      "/api/self-heal/status GET": { running: true, last: null }
    });
    expect(runResultEl().textContent).toBe(window.I18N.en["selfheal.already_running"]);
    expect(runResultEl().className).toContain("selfheal-result-warn");
    expect(window.aigate.terminalManager.openTab).toHaveBeenCalledWith("self-heal");
    expect(navClicks).toBe(1);
    expect(statusCalls(fm)).toBe(1); // immediate poll
    await vi.advanceTimersByTimeAsync(5000);
    expect(statusCalls(fm)).toBe(2); // poller runs in the 409 path too
  });
});

describe("runSelfHeal — poller robustness", () => {
  it("does not stack pollers when runSelfHeal runs twice", async () => {
    const fm = await clickRun({
      "/api/self-heal/run POST": RUN_STARTED,
      "/api/self-heal/status GET": { running: true, last: null }
    });
    expect(statusCalls(fm)).toBe(1); // first run: immediate poll only
    // Second attempt hits already_running -> poller restarted, not stacked.
    fm.routes["/api/self-heal/run POST"] = RUN_409;
    runBtnEl().disabled = false;
    runBtnEl().click();
    await vi.advanceTimersByTimeAsync(0);
    expect(statusCalls(fm)).toBe(2); // restart polls immediately ONCE more
    await vi.advanceTimersByTimeAsync(5000);
    expect(statusCalls(fm)).toBe(3); // exactly ONE interval remains
    await vi.advanceTimersByTimeAsync(5000);
    expect(statusCalls(fm)).toBe(4);
  });

  it("a failed status poll logs to the result area and never crashes the page", async () => {
    await clickRun({
      "/api/self-heal/run POST": RUN_STARTED,
      "/api/self-heal/status GET": { status: 500, body: { error: { message: "boom" } } }
    });
    // fetchJson flattens non-2xx to "HTTP <status>" (pre-existing behavior):
    // the failure is surfaced in the result area, nothing throws.
    expect(runResultEl().textContent).toContain("Status: HTTP 500");
    expect(runResultEl().className).toContain("selfheal-result-warn");
    // Retarget to a healthy status: the poller must still be alive.
    global.fetch.routes["/api/self-heal/status GET"] =
      { running: false, last: { ok: true, merged: true, iterations: 2 } };
    await vi.advanceTimersByTimeAsync(5000);
    expect(runResultEl().textContent).toContain("2 iterations");
  });
});

describe("i18n — selfheal async keys (all locales)", () => {
  it("started / already_running / status exist in en + id", () => {
    for (const key of ["selfheal.started", "selfheal.already_running", "selfheal.status"]) {
      expect(window.I18N.en[key]).toBeTruthy();
      expect(window.I18N.id[key]).toBeTruthy();
    }
    expect(window.I18N.en["selfheal.started"])
      .toBe("Self-Heal is running — watch the new terminal tab.");
    expect(window.I18N.id["selfheal.started"])
      .toBe("Self-Heal jalan — lihat tab terminal baru.");
    expect(window.I18N.en["selfheal.already_running"])
      .toBe("Self-Heal is already running — watch the terminal tab.");
    expect(window.I18N.id["selfheal.already_running"])
      .toBe("Self-Heal masih jalan — lihat tab terminal.");
  });
});
