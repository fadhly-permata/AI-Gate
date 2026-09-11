import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// i18n.js attaches window.I18N + window.applyLocale (jsdom provides DOM).
import "../static/i18n.js";
// app.js wires the UI and exposes window.aigate.renderAccounts / addAccount /
// connectOAuth / deleteAccount / loadAccounts (B5.1).
import "../static/app.js";

// Let async .then chains (fetchJson) resolve on real timers.
const flush = () => new Promise((r) => setTimeout(r, 0));

// Accounts DOM as stage-3 ships it: the cards live in KARTU C of the
// provider-detail page (#accList, a DIV — the 6-column table is gone), the
// add-form lives in its own modal (#accModal), and the status line of the card
// list is #accountsMsg.
function withAccountsDom() {
  document.body.innerHTML =
    '<section class="view is-active" data-view="provider-detail">' +
      '<h2 id="provDetailTitle"></h2>' +
      '<p id="provMsg"></p>' +
      '<p id="accountsMsg"></p>' +
      '<div id="accList"></div>' +
    "</section>" +
    '<div id="accModal">' +
      '<h3 id="accModalTitle"></h3>' +
      '<input id="accLabel" />' +
      '<select id="accAuthType">' +
        '<option value="api_key">API Key</option>' +
        '<option value="oauth">OAuth</option>' +
      "</select>" +
      '<div id="accApiKeyRow"><input id="accApiKey" /></div>' +
      '<p id="accOauthNote" hidden></p>' +
      '<div id="accEnabledRow" hidden><input type="checkbox" id="accEnabled" /></div>' +
      '<div id="accPriorityRow"><input id="accPriority" type="number" value="0" /></div>' +
      '<p id="accPriorityNote"></p>' +
      '<p id="accModalMsg"></p>' +
      '<button id="accAddBtn"></button>' +
    "</div>" +
    '<div id="provModal"><button id="provConnectOAuthBtn"></button></div>' +
    '<table id="provTable"><tbody id="provTableBody"></tbody></table>';
  window.applyLocale("en");
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

const cards = () => Array.from(document.querySelectorAll("#accList .acc-card"));

describe("renderAccounts (B5.1, stage-3 cards)", () => {
  beforeEach(() => { withAccountsDom(); });

  it("renders one CARD per account with label, auth type and credential", () => {
    window.aigate.renderAccounts(sampleAccounts());
    const rows = cards();
    expect(rows).toHaveLength(2);
    // api_key account: plaintext key shown, no masking (ADR-007 / J3)
    expect(rows[0].textContent).toContain("Key Account");
    expect(rows[0].textContent).toContain("api_key");
    expect(rows[0].textContent).toContain("sk-plaintext-secret");
    // oauth account: badge, no secret leaked
    expect(rows[1].textContent).toContain("OAuth Account");
    expect(rows[1].textContent).toContain("OAuth");
    expect(document.querySelector("#accList").innerHTML).not.toContain("undefined");
  });

  it("renders CARDS, not a table (a wide table cannot survive on a phone)", () => {
    window.aigate.renderAccounts(sampleAccounts());
    expect(document.querySelector("#accList table")).toBeNull();
    expect(document.querySelector("#accList thead")).toBeNull();
    expect(document.getElementById("accountsTable")).toBeNull();
    expect(document.getElementById("accountsBody")).toBeNull();
  });

  it("shows the empty state that explains the provider key is used meanwhile", () => {
    window.aigate.renderAccounts([]);
    const empty = document.querySelector("#accList .acc-empty");
    expect(empty).not.toBeNull();
    expect(empty.textContent).toBe(
      "No accounts yet. The provider uses its own API key until one exists."
    );
    expect(document.querySelector("#accList table")).toBeNull();
  });

  it("cuts the credential with CSS and keeps the whole value in title (no masking)", () => {
    const long = "sk-" + "x".repeat(200);
    window.aigate.renderAccounts([{ id: "k1", label: "L", auth_type: "api_key",
      api_key: long, priority: 0, last_used_at: null }]);
    const key = document.querySelector("#accList .acc-key");
    expect(key.classList.contains("acc-key")).toBe(true); // .acc-key has the ellipsis rule
    expect(key.getAttribute("title")).toBe(long);
    expect(key.textContent).toBe(long);
  });

  it("renders expires_at for oauth accounts when present", () => {
    window.aigate.renderAccounts([sampleAccounts()[1]]);
    const html = document.getElementById("accList").innerHTML;
    expect(html).toContain("2026-12-31T23:59:59Z");
    expect(html).toContain("Expires"); // accounts.expires (EN)
  });

  it("numbers the cards by POSITION (1..n), never with the raw DB integer", () => {
    window.aigate.renderAccounts(sampleAccounts());
    const pos = cards().map((c) => c.querySelector(".acc-pos").textContent);
    expect(pos).toEqual(["1", "2"]); // a2 carries priority 3 but is still #2
    expect(document.getElementById("accList").textContent).not.toMatch(/\bPriority\b/);
  });

  it("reads last_used_at (machine-owned, never editable) and the 'never' marker", () => {
    window.aigate.renderAccounts(sampleAccounts());
    const last = cards().map((c) => c.querySelector(".acc-last").textContent);
    expect(last[0]).toContain("2026-09-09T10:00:00Z");
    expect(last[1]).toContain("never used"); // provider_detail.never_used (EN)
    // Machine-owned: no editable control anywhere near it.
    expect(cards()[0].querySelector("input")).toBeNull();
  });

  it("treats a missing priority as 0 and a missing label as empty text", () => {
    window.aigate.renderAccounts([{ id: "x", auth_type: "api_key", api_key: "k" }]);
    expect(cards()[0].getAttribute("data-index")).toBe("0");
    expect(window.aigate.getAccountRows()[0].priority).toBeUndefined();
  });

  it("escapes account data (a label is never HTML)", () => {
    window.aigate.renderAccounts([{ id: "x", label: "<img src=x onerror=alert(1)>",
      auth_type: "api_key", api_key: "<script>", priority: 0, last_used_at: null }]);
    const card = cards()[0];
    expect(card.querySelector("img")).toBeNull();
    expect(card.querySelector("script")).toBeNull();
    expect(card.querySelector(".acc-label").textContent).toContain("<img");
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
        json: () => Promise.resolve({ object: "list", data: [] })
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
    expect(document.querySelector("#accList .acc-empty")).not.toBeNull();
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

describe("addAccount (B5.1, through the account modal)", () => {
  beforeEach(() => { withAccountsDom(); });

  it("POSTs the correct body and re-renders the cards", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      if (opts && opts.method === "POST") {
        return Promise.resolve({
          ok: true, headers: { get: () => "application/json" },
          json: () => Promise.resolve({ id: "a3", provider_id: 1, label: "New Key",
            auth_type: "api_key", api_key: "new-secret", expires_at: null, enabled: true })
        });
      }
      if (url.indexOf("/api/accounts") !== -1) {
        return Promise.resolve({
          ok: true, headers: { get: () => "application/json" },
          json: () => Promise.resolve({ object: "list", data: [{
            id: "a3", provider_id: 1, label: "New Key",
            auth_type: "api_key", api_key: "new-secret", priority: 0,
            expires_at: null, enabled: true
          }] })
        });
      }
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({}) });
    }));

    const res = await window.aigate.addAccount({
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
    expect(res.ok).toBe(true);
    const html = document.getElementById("accList").innerHTML;
    expect(html).toContain("New Key");
    expect(html).toContain("new-secret");
    vi.unstubAllGlobals();
  });

  it("reads the modal fields, including an explicit priority (stage-3 modal)", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ object: "list", data: [] })
      });
    }));

    document.getElementById("accLabel").value = "Second";
    document.getElementById("accApiKey").value = "sk-2";
    document.getElementById("accPriority").value = "7";
    // Only the provider id travels as an option; the rest is read from the modal.
    await window.aigate.addAccount({ provider_id: 1 });
    const post = calls.find((c) => c.opts && c.opts.method === "POST");
    expect(JSON.parse(post.opts.body)).toEqual({
      provider_id: 1, label: "Second", auth_type: "api_key", priority: 7, api_key: "sk-2"
    });
    vi.unstubAllGlobals();
  });

  it("refuses to invent a provider: no provider selected -> message, no POST", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({}) });
    }));
    // Make the test order-independent: with isolate:false a prior file may have
    // left a provider selected. Clear it so "no provider selected" is the real
    // precondition this test asserts, not an accident of run order.
    window.aigate.backToProviders();
    const res = await window.aigate.addAccount({ label: "x", auth_type: "api_key", api_key: "k" });
    expect(res.ok).toBe(false);
    expect(calls.find((c) => c.opts && c.opts.method === "POST")).toBeFalsy();
    expect(document.getElementById("accModalMsg").textContent)
      .toBe("Select a provider first.");
    vi.unstubAllGlobals();
  });

  it("shows accounts.add_error inline in the modal on a 400 response", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: false, status: 400,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ error: { message: "invalid_auth_type" } })
    })));

    const res = await window.aigate.addAccount({
      provider_id: 1, label: "Bad", auth_type: "bogus", api_key: "x"
    });

    const msg = document.getElementById("accModalMsg");
    expect(res.ok).toBe(false);
    expect(msg.textContent).toContain("Failed to add account");
    expect(msg.textContent).toContain("invalid_auth_type");
    expect(msg.className).toContain("settings-msg-error");
    vi.unstubAllGlobals();
  });

  it("an oauth account never sends an api_key field", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ object: "list", data: [] }) });
    }));
    await window.aigate.addAccount({ provider_id: 2, label: "OAuth", auth_type: "oauth", api_key: "ignored" });
    const body = JSON.parse(calls.find((c) => c.opts && c.opts.method === "POST").opts.body);
    expect(body).not.toHaveProperty("api_key");
    vi.unstubAllGlobals();
  });
});

/* ===== Edit-account modal (stage-5): the account card's "Ubah" + PUT =====
   The card edit button (rendered by accountCardHtml) opens the SAME #accModal in
   edit mode, seeded from `accountRows` (the last server read — never a refetch),
   and submit issues PUT /api/accounts/{id} carrying ONLY the fields edit mode
   shows: label + enabled, plus api_key for an api_key account. auth_type
   (immutable), priority (▲▼ own it) and last_used_at (machine-owned) never travel
   in the body. An oauth account sends no api_key — the backend 400s that. */
describe("editAccount (stage-5, PUT /api/accounts/{id})", () => {
  beforeEach(() => { withAccountsDom(); });

  // A PUT recorder: captures every call and answers per `putResult` (default:
  // a 200 DTO). The non-PUT branch is loadAccounts' re-read.
  function stubPut(putResult) {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      const method = (opts && opts.method) || "GET";
      if (method === "PUT") {
        if (putResult) return putResult();
        return Promise.resolve({
          ok: true, headers: { get: () => "application/json" },
          json: () => Promise.resolve({ id: "a1", enabled: true })
        });
      }
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ object: "list", data: sampleAccounts() })
      });
    }));
    return calls;
  }

  it("renders an Ubah button on every account card (same level as Hapus)", () => {
    window.aigate.renderAccounts(sampleAccounts());
    const rows = cards();
    expect(rows).toHaveLength(2);
    rows.forEach((c) => {
      const edit = c.querySelector(".acc-edit");
      expect(edit, "edit button present").not.toBeNull();
      expect(edit.getAttribute("aria-label")).toBe("Edit");
      expect(edit.getAttribute("title")).toBe("Edit");
      expect(edit.querySelector("i.fa-pen")).not.toBeNull();
    });
    // both actions live side by side in the footer
    expect(rows[0].querySelector(".acc-del")).not.toBeNull();
  });

  it("opens in edit mode seeded from accountRows (title + submit switch, priority hidden)", () => {
    window.aigate.renderAccounts(sampleAccounts());
    window.aigate.openAccountEditModal("a1");
    const m = window.aigate.getAccountModalMode();
    expect(m.mode).toBe("edit");
    expect(m.id).toBe("a1");
    expect(document.getElementById("accModal").hidden).toBe(false);
    // title + submit now speak of editing, not adding
    expect(document.getElementById("accModalTitle").textContent).toBe("Edit account");
    expect(document.getElementById("accAddBtn").textContent).toBe("Save changes");
    // filled from the row
    expect(document.getElementById("accLabel").value).toBe("Key Account");
    expect(document.getElementById("accApiKey").value).toBe("sk-plaintext-secret");
    expect(document.getElementById("accEnabled").checked).toBe(true);
    // auth_type is fixed on an existing account
    expect(document.getElementById("accAuthType").value).toBe("api_key");
    expect(document.getElementById("accAuthType").disabled).toBe(true);
    // priority is an add-time field only -> hidden while editing
    expect(document.getElementById("accPriorityRow").hidden).toBe(true);
    expect(document.getElementById("accPriorityNote").hidden).toBe(true);
    // enabled belongs to editing -> shown
    expect(document.getElementById("accEnabledRow").hidden).toBe(false);
  });

  it("PUTs ONLY {label, api_key, enabled} for an api_key account", async () => {
    const calls = stubPut();
    window.aigate.renderAccounts(sampleAccounts());
    window.aigate.openAccountEditModal("a1");
    document.getElementById("accLabel").value = "Renamed";
    document.getElementById("accApiKey").value = "sk-new";
    document.getElementById("accEnabled").checked = false;
    const res = await window.aigate.saveAccountEdit();
    expect(res.ok).toBe(true);
    const put = calls.find((c) => c.opts && c.opts.method === "PUT");
    expect(put.url).toBe("/api/accounts/a1");
    const body = JSON.parse(put.opts.body);
    expect(body).toEqual({ label: "Renamed", api_key: "sk-new", enabled: false });
    // never fields the backend does not accept from this form
    expect(body).not.toHaveProperty("auth_type");
    expect(body).not.toHaveProperty("priority");
    expect(body).not.toHaveProperty("last_used_at");
    expect(body).not.toHaveProperty("provider_id");
    vi.unstubAllGlobals();
  });

  it("PUTs ONLY {label, enabled} (no api_key) for an oauth account", async () => {
    const calls = stubPut();
    window.aigate.renderAccounts(sampleAccounts());
    window.aigate.openAccountEditModal("a2"); // the oauth row
    // an oauth account hides the key row and shows the explanatory note
    expect(document.getElementById("accApiKeyRow").hidden).toBe(true);
    expect(document.getElementById("accOauthNote").hidden).toBe(false);
    document.getElementById("accLabel").value = "OAuth relabel";
    const res = await window.aigate.saveAccountEdit();
    expect(res.ok).toBe(true);
    const put = calls.find((c) => c.opts && c.opts.method === "PUT");
    expect(put.url).toBe("/api/accounts/a2");
    const body = JSON.parse(put.opts.body);
    expect(body).toEqual({ label: "OAuth relabel", enabled: true });
    expect(body).not.toHaveProperty("api_key"); // would be a 400 oauth_account_key_readonly
    expect(body).not.toHaveProperty("auth_type");
    expect(body).not.toHaveProperty("priority");
    expect(body).not.toHaveProperty("last_used_at");
    vi.unstubAllGlobals();
  });

  it("a 400 keeps the modal open with the reason inline (typing not lost)", async () => {
    const calls = stubPut(() => Promise.resolve({
      ok: false, status: 400,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ error: { message: "oauth_account_key_readonly" } })
    }));
    window.aigate.renderAccounts(sampleAccounts());
    window.aigate.openAccountEditModal("a1");
    const res = await window.aigate.saveAccountEdit();
    expect(res.ok).toBe(false);
    const msg = document.getElementById("accModalMsg");
    expect(msg.textContent).toContain("Failed to save changes");
    expect(msg.textContent).toContain("oauth_account_key_readonly");
    expect(msg.className).toContain("settings-msg-error");
    // no reload on a 400 (only a 404 re-reads the list)
    expect(calls.some((c) => c.opts && c.opts.method === "PUT")).toBe(true);
    expect(calls.filter((c) => !c.opts || (c.opts.method || "GET") === "GET")).toHaveLength(0);
    vi.unstubAllGlobals();
  });

  it("a 404 shows the message and refreshes the list (account gone elsewhere)", async () => {
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      if (method === "PUT") {
        return Promise.resolve({
          ok: false, status: 404,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve({ error: { message: "account_not_found" } })
        });
      }
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ object: "list", data: [] })
      });
    }));
    window.aigate.renderAccounts(sampleAccounts());
    expect(window.aigate.getAccountRows()).toHaveLength(2);
    window.aigate.openAccountEditModal("a1");
    const res = await window.aigate.saveAccountEdit();
    expect(res.ok).toBe(false);
    const msg = document.getElementById("accModalMsg");
    expect(msg.textContent).toBe("This account no longer exists. The list was reloaded.");
    expect(msg.className).toContain("settings-msg-error");
    // loadAccounts ran and cleared the (now dead) rows: no edit modal on a ghost.
    expect(window.aigate.getAccountRows()).toHaveLength(0);
    vi.unstubAllGlobals();
  });

  it("success: submitAccountForm closes the modal and re-reads the list", async () => {
    const calls = stubPut();
    window.aigate.renderAccounts(sampleAccounts());
    window.aigate.openAccountEditModal("a1");
    calls.length = 0;
    const res = await window.aigate.submitAccountForm();
    expect(res.ok).toBe(true);
    expect(document.getElementById("accModal").hidden).toBe(true);
    // the write was a PUT (not a POST), and the list was re-read (loadAccounts)
    expect(calls.some((c) => c.opts && c.opts.method === "PUT")).toBe(true);
    expect(calls.some((c) => c.opts && c.opts.method === "POST")).toBe(false);
    vi.unstubAllGlobals();
  });

  it("closing then opening Add mode is clean (no edit values leak, chrome restored)", () => {
    window.aigate.renderAccounts(sampleAccounts());
    // enter edit mode, dirty the fields
    window.aigate.openAccountEditModal("a1");
    document.getElementById("accLabel").value = "Dirty";
    document.getElementById("accEnabled").checked = false;
    // closeAccountModal is wired to Cancel; call the exposed add-opener which
    // resets first, then assert the chrome is back to add mode.
    window.aigate.openAccountModal();
    const m = window.aigate.getAccountModalMode();
    expect(m.mode).toBe("add");
    expect(m.id).toBe(null);
    expect(document.getElementById("accModalTitle").textContent).toBe("New account for this provider");
    expect(document.getElementById("accAddBtn").textContent).toBe("Add Account");
    // add-mode chrome: priority back, enabled hidden, auth_type editable again
    expect(document.getElementById("accPriorityRow").hidden).toBe(false);
    expect(document.getElementById("accEnabledRow").hidden).toBe(true);
    expect(document.getElementById("accAuthType").disabled).toBe(false);
    // the form was reset, so no leftover row value is showing
    expect(document.getElementById("accLabel").value).toBe("");
  });

  it("a missing row (deleted before the tap) reloads instead of opening a blank modal", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true, headers: { get: () => "application/json" },
      json: () => Promise.resolve({ object: "list", data: [] })
    })));
    window.aigate.renderAccounts(sampleAccounts());
    document.getElementById("accModal").hidden = true;
    // openAccountEditModal returns the reload promise when the row is gone.
    await window.aigate.openAccountEditModal("nope");
    // modal NOT opened; the list message explains it and a reload was issued
    expect(document.getElementById("accModal").hidden).toBe(true);
    expect(document.getElementById("accountsMsg").textContent)
      .toBe("This account no longer exists. The list was reloaded.");
    expect(window.aigate.getAccountRows()).toHaveLength(0);
    vi.unstubAllGlobals();
  });
});

describe("connectOAuth (B5.1)", () => {
  beforeEach(() => { withAccountsDom(); });
  // Ensure fake timers never leak into the next test if an assertion throws.
  afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

  it("starts OAuth, opens the authorize window, polls, and re-renders the cards", async () => {
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
    expect(cards().map((c) => c.textContent).join(" ")).toContain("OAuth Account");
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
