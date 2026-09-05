import { describe, it, expect, vi, beforeEach } from "vitest";

// i18n.js attaches window.I18N + window.applyLocale (jsdom provides DOM).
import "../static/i18n.js";
// app.js wires the UI and exposes window.aigate.renderAccounts / addAccount /
// connectOAuth / deleteAccount / loadAccounts (B5.1).
import "../static/app.js";

// Let async .then chains (fetchJson) resolve on real timers.
const flush = () => new Promise((r) => setTimeout(r, 0));

// Build the Accounts DOM that lives inside the provider detail panel (#provDetail).
function withAccountsDom() {
  document.body.innerHTML =
    '<div id="provDetail">' +
      '<h3 id="provDetailTitle"></h3>' +
      '<p id="provModelMsg"></p>' +
      '<p id="provMsg"></p>' +
      '<p id="accountsMsg"></p>' +
      '<input id="accLabel" />' +
      '<select id="accAuthType">' +
        '<option value="api_key">API Key</option>' +
        '<option value="oauth">OAuth</option>' +
      '</select>' +
      '<input id="accApiKey" />' +
      '<button id="accAddBtn"></button>' +
      '<button id="provConnectOAuthBtn"></button>' +
      '<table id="accountsTable"><tbody id="accountsBody"></tbody></table>' +
    '</div>';
}

// Sample GET /api/accounts payload (mirrors be-dev receipt DTO).
function sampleAccounts() {
  return [
    {
      id: "a1", provider_id: 1, label: "Key Account",
      auth_type: "api_key", api_key: "sk-plaintext-secret",
      has_oauth_token: false, expires_at: null, enabled: true
    },
    {
      id: "a2", provider_id: 1, label: "OAuth Account",
      auth_type: "oauth", api_key: null,
      has_oauth_token: true, expires_at: "2026-12-31T23:59:59Z", enabled: true
    }
  ];
}

describe("renderAccounts (B5.1)", () => {
  beforeEach(() => { withAccountsDom(); });

  it("renders one row per account with label, auth_type and credential", () => {
    window.aigate.renderAccounts(sampleAccounts());
    const body = document.getElementById("accountsBody").innerHTML;
    // api_key account: plaintext key shown, no masking (ADR-007)
    expect(body).toContain("Key Account");
    expect(body).toContain("api_key");
    expect(body).toContain("sk-plaintext-secret");
    // oauth account: badge, no secret leaked
    expect(body).toContain("OAuth Account");
    expect(body).toContain("OAuth");        // badge text
    expect(body).not.toContain("undefined");
  });

  it("shows an empty-state message when there are no accounts", () => {
    window.aigate.renderAccounts([]);
    const body = document.getElementById("accountsBody").innerHTML;
    expect(body).toContain("No accounts yet."); // accounts.none (EN)
  });

  it("renders expires_at for oauth accounts when present", () => {
    window.aigate.renderAccounts([sampleAccounts()[1]]);
    const body = document.getElementById("accountsBody").innerHTML;
    expect(body).toContain("2026-12-31T23:59:59Z");
    expect(body).toContain("Expires"); // accounts.expires (EN)
  });
});

describe("addAccount (B5.1)", () => {
  beforeEach(() => { withAccountsDom(); });

  it("POSTs the correct body and re-renders the list", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      // POST creates the account; subsequent GET lists it back.
      if (opts && opts.method === "POST") {
        return Promise.resolve({
          ok: true,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve({
            id: "a3", provider_id: 1, label: "New Key",
            auth_type: "api_key", api_key: "new-secret",
            expires_at: null, enabled: true
          })
        });
      }
      if (url.indexOf("/api/accounts") !== -1) {
        return Promise.resolve({
          ok: true,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve({ object: "list", data: [{
            id: "a3", provider_id: 1, label: "New Key",
            auth_type: "api_key", api_key: "new-secret",
            expires_at: null, enabled: true
          }] })
        });
      }
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({}) });
    }));

    await window.aigate.addAccount({
      provider_id: 1, label: "New Key", auth_type: "api_key", api_key: "new-secret"
    });

    const postCall = calls.find((c) => (c.opts && c.opts.method) === "POST");
    expect(postCall).toBeTruthy();
    expect(postCall.url).toBe("/api/accounts");
    expect(JSON.parse(postCall.opts.body)).toEqual({
      provider_id: 1, label: "New Key", auth_type: "api_key", api_key: "new-secret"
    });

    const body = document.getElementById("accountsBody").innerHTML;
    expect(body).toContain("New Key");
    expect(body).toContain("new-secret");
    vi.unstubAllGlobals();
  });

  it("shows accounts.add_error inline on a 400/404 response", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: false, status: 400,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ error: { message: "invalid_auth_type" } })
    })));

    await window.aigate.addAccount({
      provider_id: 1, label: "Bad", auth_type: "bogus", api_key: "x"
    });

    const msg = document.getElementById("accountsMsg");
    expect(msg.textContent).toContain("Failed to add account");
    expect(msg.textContent).toContain("invalid_auth_type");
    expect(msg.className).toContain("settings-msg-error");
    vi.unstubAllGlobals();
  });
});

describe("deleteAccount (B5.1)", () => {
  beforeEach(() => { withAccountsDom(); });

  it("confirms then DELETEs /api/accounts/<id> and re-renders", async () => {
    const calls = [];
    window.confirm = vi.fn(() => true);
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({
        ok: true,
        headers: { get: () => "application/json" },
        json: () => Promise.resolve({ ok: true })
      });
    }));

    // Pre-seed a row so we can prove the list re-renders to empty afterward.
    window.aigate.renderAccounts(sampleAccounts());

    await window.aigate.deleteAccount("a1");

    expect(window.confirm).toHaveBeenCalled();
    const delCall = calls.find((c) => (c.opts && c.opts.method) === "DELETE");
    expect(delCall).toBeTruthy();
    expect(delCall.url).toBe("/api/accounts/a1");

    // Refresh (loadAccounts with no selected provider -> empty state) re-rendered.
    const body = document.getElementById("accountsBody").innerHTML;
    expect(body).toContain("No accounts yet.");
    vi.unstubAllGlobals();
  });

  it("does NOT call DELETE when the user cancels the confirm", async () => {
    const calls = [];
    window.confirm = vi.fn(() => false);
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({ ok: true }) });
    }));

    window.aigate.deleteAccount("a1");
    await flush();

    expect(window.confirm).toHaveBeenCalled();
    expect(calls.find((c) => (c.opts && c.opts.method) === "DELETE")).toBeFalsy();
    vi.unstubAllGlobals();
  });
});

describe("connectOAuth (B5.1)", () => {
  beforeEach(() => { withAccountsDom(); });
  // Ensure fake timers never leak into the next test if an assertion throws.
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it("starts OAuth, opens the authorize window, polls, and re-renders when the oauth account appears", async () => {
    vi.useFakeTimers();
    const calls = [];
    const openMock = vi.fn();
    vi.stubGlobal("open", openMock);
    window.open = openMock;
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      if (url.indexOf("/api/oauth/") !== -1) {
        return Promise.resolve({
          ok: true,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve({ authorize_url: "https://auth.example/start", state: "s1" })
        });
      }
      if (url.indexOf("/api/accounts") !== -1) {
        return Promise.resolve({
          ok: true,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve({ object: "list", data: [{
            id: "oa1", provider_id: 1, label: "OAuth Account",
            auth_type: "oauth", api_key: null,
            has_oauth_token: true, expires_at: null, enabled: true
          }] })
        });
      }
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({}) });
    }));

    window.aigate.connectOAuth(1);

    // Flush the startOAuth promise so its .then schedules the poll interval.
    await vi.advanceTimersByTimeAsync(0);
    // Fire the first poll tick (OAUTH_POLL_MS = 2000ms) — oauth account now present.
    await vi.advanceTimersByTimeAsync(2000);

    expect(openMock).toHaveBeenCalledWith("https://auth.example/start", "_blank");

    const body = document.getElementById("accountsBody").innerHTML;
    expect(body).toContain("OAuth Account");
    expect(document.getElementById("accountsMsg").textContent).toContain("OAuth connected");

    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("shows accounts.oauth_not_configured when the start endpoint rejects with that error", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: false, status: 400,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ error: "oauth_not_configured", message: "no oauth" })
    })));

    window.aigate.connectOAuth(1);
    await flush();

    const msg = document.getElementById("accountsMsg");
    expect(msg.textContent).toContain("OAuth is not configured for this provider.");
    expect(msg.className).toContain("settings-msg-error");
    vi.unstubAllGlobals();
  });
});
