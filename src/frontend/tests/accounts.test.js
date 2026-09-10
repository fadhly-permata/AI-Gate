import { describe, it, expect, vi, beforeEach } from "vitest";

// i18n.js attaches window.I18N + window.applyLocale (jsdom provides DOM).
import "../static/i18n.js";
// app.js wires the UI and exposes window.aigate.renderAccounts / addAccount /
// connectOAuth / deleteAccount / loadAccounts (B5.1).
import "../static/app.js";

// Let async .then chains (fetchJson) resolve on real timers.
const flush = () => new Promise((r) => setTimeout(r, 0));

// Build the Accounts DOM that lives inside the provider modal's Accounts tab
// (#provPanelAccounts) — stage-2: it moved out of the detail card.
function withAccountsDom() {
  document.body.innerHTML =
    '<div id="provDetail">' +
      '<h3 id="provDetailTitle"></h3>' +
      '<p id="provMsg"></p>' +
      '<p id="accountsMsg"></p>' +
      '<input id="accLabel" />' +
      '<select id="accAuthType">' +
        '<option value="api_key">API Key</option>' +
        '<option value="oauth">OAuth</option>' +
      '</select>' +
      '<input id="accApiKey" />' +
      '<input id="accPriority" type="number" value="0" />' +
      '<button id="accAddBtn"></button>' +
      '<button id="provConnectOAuthBtn"></button>' +
      '<table id="accountsTable"><tbody id="accountsBody"></tbody></table>' +
      '<table id="provTable"><tbody id="provTableBody"></tbody></table>' +
    '</div>';
}

// Sample GET /api/accounts payload (mirrors the stage-1 backend DTO: rows come
// sorted priority asc / id asc, each carrying priority + last_used_at).
function sampleAccounts() {
  return [
    {
      id: "a1", provider_id: 1, label: "Key Account",
      auth_type: "api_key", api_key: "sk-plaintext-secret",
      has_oauth_token: false, expires_at: null, enabled: true,
      priority: 0, last_used_at: "2026-09-09T10:00:00Z"
    },
    {
      id: "a2", provider_id: 1, label: "OAuth Account",
      auth_type: "oauth", api_key: null,
      has_oauth_token: true, expires_at: "2026-12-31T23:59:59Z", enabled: true,
      priority: 3, last_used_at: null
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

  it("shows a Priority number input (min 0) per row with the DTO value", () => {
    window.aigate.renderAccounts(sampleAccounts());
    const rows = document.querySelectorAll("#accountsBody tr.acc-row");
    expect(rows).toHaveLength(2);
    const inputs = document.querySelectorAll("#accountsBody .acc-priority");
    expect(inputs).toHaveLength(2);
    expect(inputs[0].getAttribute("type")).toBe("number");
    expect(inputs[0].getAttribute("min")).toBe("0");
    expect(inputs[0].value).toBe("0");
    expect(inputs[1].value).toBe("3");
    // Screen readers get the column name (the cell has no visible label).
    expect(inputs[0].getAttribute("aria-label")).toBe("Priority");
  });

  it("renders last_used_at read-only and the i18n 'never used' marker for null", () => {
    window.aigate.renderAccounts(sampleAccounts());
    const cells = document.querySelectorAll("#accountsBody .acc-last-used");
    expect(cells).toHaveLength(2);
    expect(cells[0].textContent).toContain("2026-09-09T10:00:00Z");
    expect(cells[1].textContent).toBe("Never used"); // accounts.never_used (EN)
    // Machine-owned: never an editable control (no input inside).
    expect(cells[0].querySelector("input")).toBeNull();
    expect(cells[1].querySelector("input")).toBeNull();
  });

  it("defaults a missing priority to 0 and keeps the empty-cell colspan at 6", () => {
    window.aigate.renderAccounts([{ id: "x", label: "L", auth_type: "api_key", api_key: "k" }]);
    expect(document.querySelector("#accountsBody .acc-priority").value).toBe("0");
    window.aigate.renderAccounts([]);
    expect(document.querySelector("#accountsBody .empty-cell").getAttribute("colspan")).toBe("6");
  });
});

describe("priority editing (stage-2 PUT contract)", () => {
  beforeEach(() => { withAccountsDom(); });

  // Commit the change like a real user: type into the row input, then blur ->
  // 'change' fires (commit-on-change, not per keystroke).
  function changePriority(rowId, value) {
    const row = document.querySelector(`#accountsBody .acc-row[data-id="${rowId}"]`);
    const inp = row.querySelector(".acc-priority");
    inp.value = String(value);
    inp.dispatchEvent(new Event("change", { bubbles: true }));
  }

  it("a changed priority sends PUT /api/accounts/<id> with ONLY {priority}", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ object: "list", data: [] })
      });
    }));

    window.aigate.renderAccounts(sampleAccounts());
    changePriority("a1", 5);
    await flush();

    const put = calls.find((c) => c.opts && c.opts.method === "PUT");
    expect(put).toBeTruthy();
    expect(put.url).toBe("/api/accounts/a1");
    // Contract: PUT accepts ONLY the priority — never last_used_at or others.
    expect(JSON.parse(put.opts.body)).toEqual({ priority: 5 });
    vi.unstubAllGlobals();
  });

  it("reloads the accounts list after a successful PUT (commit-on-change)", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      calls.push({ url: String(url), method, body: opts && opts.body });
      let payload = { data: [] };
      if (method === "PUT") payload = { ok: true };
      else if (String(url).indexOf("/api/accounts?") === 0) {
        // The re-read comes back in the NEW priority order (contract).
        payload = { object: "list", data: [{ id: "a1", provider_id: "p1", label: "Moved",
          auth_type: "api_key", api_key: "k", priority: 5, last_used_at: null }] };
      } else if (String(url).indexOf("/discover") !== -1) payload = { ok: true, models: [] };
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve(payload)
      });
    }));

    // Select provider p1 the way the UI does: the row name button opens the
    // detail card (stage-2 entry point) and sets the current provider.
    window.aigate.renderProviders([
      { id: "p1", name: "ACME", type: "openai-compatible", base_url: "u", enabled: true, models: [] }
    ]);
    document.querySelector("#provTableBody .js-prov-detail").click();
    await flush();

    window.aigate.renderAccounts(sampleAccounts());
    const inp = document.querySelector('#accountsBody .acc-row[data-id="a1"] .acc-priority');
    inp.value = "5";
    inp.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();
    await flush();

    const put = calls.find((c) => c.method === "PUT");
    expect(put).toBeTruthy();
    expect(put.url).toBe("/api/accounts/a1");
    // The refresh GET ran after the PUT and its result was rendered.
    expect(calls.some((c) => c.method === "GET" && c.url.indexOf("/api/accounts?provider_id=p1") === 0))
      .toBe(true);
    expect(document.getElementById("accountsBody").innerHTML).toContain("Moved");
    expect(document.querySelector('#accountsBody .acc-row[data-id="a1"] .acc-priority').value)
      .toBe("5");
    vi.unstubAllGlobals();
  });

  it("an unchanged (or invalid -> 0-clamped) value never sends a PUT", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({}) });
    }));

    window.aigate.renderAccounts(sampleAccounts());
    changePriority("a2", 3); // same as rendered priority -> no-op
    changePriority("a1", "abc"); // invalid -> clamps to 0 == current -> no-op
    await flush();

    expect(calls.find((c) => c.opts && c.opts.method === "PUT")).toBeFalsy();
    vi.unstubAllGlobals();
  });

  it("shows the backend error inline when the PUT fails (404 account_not_found)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: false, status: 404,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ error: { message: "account_not_found" } })
    })));

    window.aigate.renderAccounts(sampleAccounts());
    changePriority("a1", 1); // a1 renders at 0, so 1 is a real change -> PUT
    await flush();

    const msg = document.getElementById("accountsMsg");
    expect(msg.textContent).toContain("account_not_found");
    expect(msg.className).toContain("settings-msg-error");
    vi.unstubAllGlobals();
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
    // Stage-1 contract: POST accepts priority (default 0 — small = tried first).
    expect(JSON.parse(postCall.opts.body)).toEqual({
      provider_id: 1, label: "New Key", auth_type: "api_key", api_key: "new-secret",
      priority: 0
    });

    const body = document.getElementById("accountsBody").innerHTML;
    expect(body).toContain("New Key");
    expect(body).toContain("new-secret");
    vi.unstubAllGlobals();
  });

  it("sends an explicit priority from the form/opts (stage-2)", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ object: "list", data: [] })
      });
    }));

    await window.aigate.addAccount({
      provider_id: 1, label: "Backup", auth_type: "api_key", api_key: "k2", priority: "7"
    });
    const postCall = calls.find((c) => c.opts && c.opts.method === "POST");
    expect(JSON.parse(postCall.opts.body).priority).toBe(7);

    // Form path: the #accPriority input feeds the body too.
    document.getElementById("accPriority").value = "2";
    await window.aigate.addAccount({ provider_id: 1, label: "Mid", auth_type: "api_key", api_key: "k3" });
    const second = calls.filter((c) => c.opts && c.opts.method === "POST")[1];
    expect(JSON.parse(second.opts.body).priority).toBe(2);
    // After a successful add the form resets its priority to the default 0.
    expect(document.getElementById("accPriority").value).toBe("0");
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
