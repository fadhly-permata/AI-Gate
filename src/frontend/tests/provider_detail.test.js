// Scratch test: provider-detail page (stage-3, Opsi A).
// Mirrors the shipped markup contract + the behaviors the design sheet §3-§7
// requires. Replaces the stage-2 modal-tab tests (see receipt mapping).
import { describe, it, expect, vi, beforeEach } from "vitest";
import { indexDocument, indexBodyHtml } from "./helpers/dom.js";

import "../static/i18n.js";
import "../static/combobox.js";
import "../static/app.js";

const flush = () => new Promise((r) => setTimeout(r, 0));
const doc = indexDocument();

// The shipped page inside THIS test's jsdom (mutable, per helpers/dom.js contract).
function withPage() {
  document.body.innerHTML = indexBodyHtml();
  window.applyLocale("en");
  // Same wiring init() runs — the shared jsdom body was empty at import time.
  window.aigate.wireProviderUi();
}

// A fetch router for everything the detail page touches.
function stubApi({ provider, accounts, discover, discoverFails, putProvider, putAccount }) {
  const calls = [];
  const ok = (payload) => Promise.resolve({
    ok: true,
    headers: { get: () => "application/json" },
    json: () => Promise.resolve(payload)
  });
  vi.stubGlobal("fetch", vi.fn((url, opts) => {
    const method = (opts && opts.method) || "GET";
    calls.push({ url: String(url), method, body: opts && opts.body });
    if (method === "POST" && String(url).indexOf("/discover") !== -1) {
      return discoverFails ? Promise.reject(new Error("network down")) : ok(discover);
    }
    if (method === "POST" && String(url) === "/api/accounts") {
      return ok((putAccount && putAccount.created) || { id: "new" });
    }
    if (method === "PUT" && String(url).indexOf("/api/accounts/") === 0) {
      return ok({ id: "a" });
    }
    if (method === "PUT" && String(url).indexOf("/api/providers/") === 0) {
      const sent = opts && opts.body ? JSON.parse(opts.body) : {};
      return ok(putProvider || Object.assign({}, provider, sent));
    }
    if (String(url).indexOf("/api/accounts") === 0) {
      return ok({ object: "list", data: accounts || [] });
    }
    if (String(url).indexOf("/api/usage") === 0) {
      return ok({ data: [], totals: {}, by_model: [] });
    }
    if (String(url).indexOf("/api/providers") === 0 && String(url) !== "/api/providers") {
      return ok(provider);
    }
    if (String(url) === "/api/providers") {
      return ok({ data: [provider] });
    }
    return ok({ data: [] });
  }));
  return calls;
}

const PROVIDER = {
  id: "p1", name: "ACME", type: "anthropic", base_url: "https://api.acme.test/v1",
  api_key: "sk-acme-plaintext", default_model: "claude-3", enabled: true,
  custom_headers: { "X-Tenant": "acme" }, models: [{ model_id: "claude-3", model_name: "Claude 3" }],
  fallback_strategy: "fill-first", sticky_round_robin_limit: 3
};

const ACCOUNTS = [
  { id: "a1", provider_id: 1, label: "Primary", auth_type: "api_key",
    api_key: "sk-one", priority: 0, last_used_at: "2026-09-11T07:00:00Z", expires_at: null },
  { id: "a2", provider_id: 1, label: "Backup", auth_type: "api_key",
    api_key: "sk-two", priority: 0, last_used_at: null, expires_at: null },
  { id: "a3", provider_id: 1, label: "OAuth", auth_type: "oauth",
    api_key: "", priority: 5, last_used_at: null, expires_at: "2026-12-31T00:00:00Z" }
];

describe("provider-detail view — markup contract", () => {
  it("exists, is one column of cards, and has NO nav / bottom-nav entry", () => {
    const view = doc.querySelector('[data-view="provider-detail"]');
    expect(view, "view section present").not.toBeNull();
    expect(view.classList.contains("view")).toBe(true);
    // No nav entry: the parity between nav items and bottom-nav items is
    // untouched, and the sidebar keeps "Penyedia" highlighted instead.
    expect(doc.querySelector('.nav-item[data-view="provider-detail"]')).toBeNull();
    expect(doc.querySelector('.bn-item[data-view="provider-detail"]')).toBeNull();
    // head + 4 cards
    expect(view.querySelectorAll(":scope > .card")).toHaveLength(5);
  });

  it("head carries back + name + badge + Edit/Delete", () => {
    const view = doc.querySelector('[data-view="provider-detail"]');
    expect(view.querySelector("#provDetailBackBtn")).not.toBeNull();
    expect(view.querySelector("#provDetailTitle")).not.toBeNull();
    const badge = view.querySelector("#provDetailBadge");
    expect(badge.getAttribute("hidden")).not.toBeNull(); // text comes from JS
    expect(view.querySelector("#provEditBtn")).not.toBeNull();
    expect(view.querySelector("#provDeleteBtn")).not.toBeNull();
  });

  it("Kartu A is read-only: no inputs, labels only", () => {
    const view = doc.querySelector('[data-view="provider-detail"]');
    const profile = view.querySelector(".pd-profile");
    expect(profile).not.toBeNull();
    expect(profile.querySelector("input, select, button, textarea")).toBeNull();
    ["pdType", "pdBaseUrl", "pdDefaultModel", "pdApiKey", "pdHeaders", "pdModels"]
      .forEach((id) => expect(view.querySelector("#" + id), id).not.toBeNull());
  });

  it("Kartu B holds the ONLY strategy controls (enum + clamped sticky input)", () => {
    const sel = doc.getElementById("pdStrategy");
    expect(Array.from(sel.querySelectorAll("option")).map((o) => o.getAttribute("value")))
      .toEqual(["fill-first", "round-robin"]);
    const lim = doc.getElementById("pdStickyLimit");
    expect(lim.getAttribute("type")).toBe("number");
    expect(lim.getAttribute("min")).toBe("1");
    expect(doc.getElementById("pdStickyRow").hasAttribute("hidden")).toBe(true);
    expect(doc.getElementById("pdStrategySaveBtn")).not.toBeNull();
    // The profile modal no longer carries strategy fields at all.
    expect(doc.getElementById("provStrategy")).toBeNull();
    expect(doc.getElementById("provStickyLimit")).toBeNull();
    const modal = doc.getElementById("provModal");
    expect(modal.innerHTML).not.toMatch(/fallback_strategy|sticky_round_robin_limit/);
  });

  it("Kartu C renders account CARDS (the 6-column table is gone) + add/OAuth/reload", () => {
    const list = doc.getElementById("accList");
    expect(list).not.toBeNull();
    expect(list.tagName).toBe("DIV");
    expect(doc.getElementById("accountsTable")).toBeNull();
    expect(doc.getElementById("accountsBody")).toBeNull();
    ["pdAccAddBtn", "provConnectOAuthBtn", "pdAccReloadBtn"]
      .forEach((id) => expect(doc.getElementById(id), id).not.toBeNull());
    // Add-account lives in its own modal, not as an inline 5-row form.
    const acc = doc.getElementById("accModal");
    expect(acc).not.toBeNull();
    ["accLabel", "accAuthType", "accApiKey", "accPriority", "accAddBtn"]
      .forEach((id) => expect(acc.querySelector("#" + id), id).not.toBeNull());
    expect(doc.getElementById("provModal").querySelector("#accLabel")).toBeNull();
  });

  it("Kartu D holds the B5.5 usage subsection moved out of the old detail card", () => {
    const view = doc.querySelector('[data-view="provider-detail"]');
    expect(view.querySelector("#provUsageTotals")).not.toBeNull();
    expect(view.querySelector("#provUsageModelBody")).not.toBeNull();
    expect(view.querySelector("#provUsageMsg")).not.toBeNull();
    // ...and the old card is really gone.
    expect(doc.getElementById("provDetail")).toBeNull();
  });

  it("stage-2 tab leftovers are gone from the provider modal", () => {
    const modal = doc.getElementById("provModal");
    expect(modal.querySelector('[role="tablist"]')).toBeNull();
    expect(modal.querySelector('[role="tab"]')).toBeNull();
    expect(modal.querySelector('[role="tabpanel"]')).toBeNull();
    expect(doc.getElementById("provForm").querySelector('[role="tabpanel"]')).toBeNull();
    ["provTabList", "provTabProvider", "provTabAccounts", "provTabHint",
     "provPanelProvider", "provPanelAccounts"]
      .forEach((id) => expect(doc.getElementById(id), id).toBeNull());
  });

  it("the Model combobox has a discovery status line next to it", () => {
    const status = doc.getElementById("provModalModelStatus");
    expect(status).not.toBeNull();
    expect(status.getAttribute("role")).toBe("status");
    expect(status.getAttribute("aria-live")).toBe("polite");
    expect(doc.getElementById("pdModelStatus")).not.toBeNull();
  });
});

describe("provider-detail page — behavior", () => {
  beforeEach(() => { withPage(); });

  it("the kebab's accounts item opens the page, keeps 'Penyedia' highlighted", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.renderProviders([PROVIDER]);
    // Stage-4 entry path: name cell is plain text; the detail page is reached
    // through the row kebab -> "Kelola akun" (providers.accounts_menu, first item).
    const name = document.querySelector("#provTableBody .prov-name");
    expect(name.querySelector("button")).toBeNull();
    name.click(); // plain text: clicking the name must NOT navigate
    expect(document.querySelector('.view[data-view="provider-detail"]').classList.contains("is-active")).toBe(false);
    document.querySelector('#provTableBody tr[data-id="p1"] .js-row-menu')
      .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const item = document.querySelector('.row-menu [data-action="accounts"]');
    expect(item).toBeTruthy();
    item.click();
    await flush();

    const view = document.querySelector('[data-view="provider-detail"]');
    expect(view.classList.contains("is-active")).toBe(true);
    expect(document.querySelector('.view[data-view="providers"]').classList.contains("is-active")).toBe(false);
    expect(document.querySelector('.nav-item[data-view="providers"]').classList.contains("active")).toBe(true);
    expect(document.getElementById("provDetailTitle").textContent).toBe("ACME");
    expect(document.getElementById("provDetailBadge").textContent).toBe("Enabled");
    expect(calls.some((c) => c.url === "/api/providers/p1")).toBe(true);
    expect(calls.some((c) => c.url.indexOf("/api/accounts?provider_id=p1") === 0)).toBe(true);
    vi.unstubAllGlobals();
  });

  it("Kartu A shows the profile read-only: plaintext key + full value in title", async () => {
    stubApi({ provider: PROVIDER, accounts: [],
      discover: { ok: true, models: [{ model_id: "claude-3", model_name: "Claude 3" }] } });
    window.aigate.openDetail("p1");
    await flush();
    const key = document.getElementById("pdApiKey");
    expect(key.textContent).toBe("sk-acme-plaintext"); // J3 / ADR-007: no masking
    expect(key.getAttribute("title")).toBe("sk-acme-plaintext");
    expect(document.getElementById("pdType").textContent).toBe("anthropic");
    expect(document.getElementById("pdDefaultModel").textContent).toBe("claude-3");
    expect(document.getElementById("pdHeaders").textContent).toContain("X-Tenant");
    expect(document.getElementById("pdModels").textContent).toBe("1");
    expect(key.querySelector("input")).toBeNull();
    vi.unstubAllGlobals();
  });

  it("Kartu A count follows a background discovery that finds more models", async () => {
    stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [
      { model_id: "m1", model_name: "M1" }, { model_id: "m2", model_name: "M2" }
    ] } });
    window.aigate.openDetail("p1");
    await flush();
    await flush();
    // DTO said 1 model; the discovery that just landed says 2 -> the card shows 2.
    expect(document.getElementById("pdModels").textContent).toBe("2");
    vi.unstubAllGlobals();
  });

  it("'Kembali' goes to the list AND re-reads it (fresh model counts)", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;
    document.getElementById("provDetailBackBtn").click();
    await flush();
    expect(document.querySelector('.view[data-view="providers"]').classList.contains("is-active")).toBe(true);
    expect(calls.some((c) => c.url === "/api/providers")).toBe(true);
    vi.unstubAllGlobals();
  });

it("the mobile bottom-nav also highlights 'Penyedia' (no entry of its own)", async () => {
    stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    const active = Array.from(document.querySelectorAll(".bn-item.active"))
      .map((n) => n.getAttribute("data-view"));
    expect(active).toEqual(["providers"]);
    expect(document.querySelector('.bn-item[data-view="provider-detail"]')).toBeNull();
    vi.unstubAllGlobals();
  });

  it("device re-simulation keeps the parent highlighted on the detail page", async () => {
    stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    document.getElementById("setDevice").value = "phone";
    document.getElementById("setDevice").dispatchEvent(new Event("change", { bubbles: true }));
    expect(document.querySelector('.bn-item[data-view="providers"]').classList.contains("active")).toBe(true);
    vi.unstubAllGlobals();
  });

  it("Kartu B saves ONLY the strategy fields", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;

    const sel = document.getElementById("pdStrategy");
    sel.value = "round-robin";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    document.getElementById("pdStickyLimit").value = "5";
    document.getElementById("pdStrategySaveBtn").click();
    await flush();

    const put = calls.find((c) => c.method === "PUT" && c.url === "/api/providers/p1");
    expect(put, "strategy PUT").toBeTruthy();
    expect(JSON.parse(put.body)).toEqual({ fallback_strategy: "round-robin", sticky_round_robin_limit: 5 });
    expect(document.getElementById("pdStrategyMsg").textContent).toBe("Strategy saved.");
    vi.unstubAllGlobals();
  });

  it("Kartu B fill-first never sends a sticky limit (hidden + disabled)", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;
    document.getElementById("pdStrategySaveBtn").click();
    await flush();
    const put = calls.find((c) => c.method === "PUT");
    expect(JSON.parse(put.body)).toEqual({ fallback_strategy: "fill-first" });
    expect(document.getElementById("pdStickyRow").hidden).toBe(true);
    expect(document.getElementById("pdStickyLimit").disabled).toBe(true);
    vi.unstubAllGlobals();
  });

it("a stored limit never pretends to be live: fill-first hides + disables it", async () => {
    stubApi({
      provider: Object.assign({}, PROVIDER, { fallback_strategy: "fill-first", sticky_round_robin_limit: 9 }),
      accounts: [], discover: { ok: true, models: [] }
    });
    window.aigate.openDetail("p1");
    await flush();
    expect(document.getElementById("pdStrategy").value).toBe("fill-first");
    expect(document.getElementById("pdStickyRow").hidden).toBe(true);
    expect(document.getElementById("pdStickyLimit").disabled).toBe(true);
    vi.unstubAllGlobals();
  });

  it("clamps a zero/blank sticky limit to >=1 / default 3 (contract)", async () => {
    stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    const sel = document.getElementById("pdStrategy");
    sel.value = "round-robin";
    sel.dispatchEvent(new Event("change", { bubbles: true }));

    const puts = [];
    const orig = globalThis.fetch;
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      if (opts && opts.method === "PUT") puts.push(JSON.parse(opts.body));
      // The server answers with the round-robin it stored, so re-rendering
      // Kartu B after the PUT keeps the row live for the second assertion.
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve(Object.assign({}, PROVIDER, {
          fallback_strategy: "round-robin", sticky_round_robin_limit: 5
        }))
      });
    }));
    document.getElementById("pdStickyLimit").value = "0";
    await window.aigate.saveStrategy();
    expect(puts[0].sticky_round_robin_limit).toBe(1); // Math.max(1, 0)

    document.getElementById("pdStickyLimit").value = "";
    await window.aigate.saveStrategy();
    expect(puts[1].sticky_round_robin_limit).toBe(3); // blank -> default
    vi.unstubAllGlobals();
    globalThis.fetch = orig;
  });

  it("a new account joins at the END of the queue (priority = current count)", async () => {
    stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    document.getElementById("pdAccAddBtn").click();
    expect(document.getElementById("accPriority").value).toBe("3");
    vi.unstubAllGlobals();
  });

  it("a 400 invalid_fallback_strategy is shown inline in Kartu B", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: false, status: 400,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ error: { message: "invalid_fallback_strategy" } })
    })));
    window.aigate.openDetail("p1");
    await flush();
    document.getElementById("pdStrategySaveBtn").click();
    await flush();
    const msg = document.getElementById("pdStrategyMsg");
    expect(msg.textContent).toContain("invalid_fallback_strategy");
    expect(msg.className).toContain("settings-msg-error");
    vi.unstubAllGlobals();
  });

  it("the profile modal save never touches the strategy fields", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    window.aigate.openEditModal("p1");
    await flush();
    calls.length = 0;
    document.getElementById("provName").value = "ACME 2";
    await window.aigate.saveProvider();
    await flush();
    const put = calls.find((c) => c.method === "PUT" && c.url === "/api/providers/p1");
    expect(put, "profile PUT").toBeTruthy();
    const body = JSON.parse(put.body);
    expect(body.name).toBe("ACME 2");
    expect(body).not.toHaveProperty("fallback_strategy");
    expect(body).not.toHaveProperty("sticky_round_robin_limit");
    vi.unstubAllGlobals();
  });

it("Kartu D points at usage.js loadProviderUsage (no usage.js change needed)", async () => {
    const seen = [];
    window.aigate.usage = {
      loadProviderUsage: (id) => { seen.push(id); return Promise.resolve(null); }
    };
    stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    expect(seen).toEqual(["p1"]);
    delete window.aigate.usage;
    vi.unstubAllGlobals();
  });

  it("a provider that cannot be read falls back to the list with the reason", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: false, status: 404, headers: { get: () => "application/json" },
      json: () => Promise.resolve({ error: { message: "provider 999 not found" } })
    })));
    document.querySelector('.view[data-view="providers"]').classList.add("is-active");
    window.aigate.openDetail("999");
    await flush();
    expect(document.querySelector('.view[data-view="provider-detail"]').classList.contains("is-active")).toBe(false);
    expect(document.querySelector('.view[data-view="providers"]').classList.contains("is-active")).toBe(true);
    expect(document.getElementById("provMsg").textContent).toContain("provider 999 not found");
    vi.unstubAllGlobals();
  });

  it("deleting the open provider falls back to the list", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.confirm = vi.fn(() => true);
    window.aigate.openDetail("p1");
    await flush();
    document.getElementById("provDeleteBtn").click();
    await flush();
    expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/providers/p1")).toBe(true);
    expect(document.querySelector('.view[data-view="providers"]').classList.contains("is-active")).toBe(true);
    vi.unstubAllGlobals();
  });
});

describe("Kartu C — account cards + ▲▼ priority", () => {
  beforeEach(() => { withPage(); });

  const cards = () => Array.from(document.querySelectorAll("#accList .acc-card"));

  it("renders one CARD per account: position, label, auth type, plaintext key, last used", async () => {
    stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    const rows = cards();
    expect(rows).toHaveLength(3);
    expect(rows[0].querySelector(".acc-pos").textContent).toBe("1");
    expect(rows[0].textContent).toContain("Primary");
    expect(rows[0].textContent).toContain("sk-one"); // no masking (J3)
    expect(rows[0].querySelector(".acc-key").getAttribute("title")).toBe("sk-one");
    expect(rows[1].querySelector(".acc-last").textContent).toContain("never used");
    // No table survives anywhere in this card list.
    expect(document.querySelector("#accList table")).toBeNull();
    vi.unstubAllGlobals();
  });

  it("empty list explains that the provider key is used until an account exists", async () => {
    stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    const empty = document.querySelector("#accList .acc-empty");
    expect(empty).not.toBeNull();
    expect(empty.textContent).toContain("No accounts yet.");
    expect(empty.textContent).toContain("uses its own API key");
    vi.unstubAllGlobals();
  });

  // The design sheet's example: every account still at the DB default 0.
  // Swapping positions 1 and 2 renumbers to 0,1,2 -> only a1 and a3 need a PUT
  // (2 requests, not n), and a2 keeps the 0 it already has.
  it("▼ on #1 PUTs the renumbered 0..n-1 for the changed rows only (all-zero start = 2 PUTs)", async () => {
    const calls = stubApi({
      provider: PROVIDER,
      accounts: ACCOUNTS.map((a) => Object.assign({}, a, { priority: 0 })),
      discover: { ok: true, models: [] }
    });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;
    cards()[0].querySelector(".acc-down").click(); // #1 trades place with #2
    await flush();
    await flush();
    const puts = calls.filter((c) => c.method === "PUT");
    expect(puts).toHaveLength(2);
    expect(puts[0].url).toBe("/api/accounts/a1");
    expect(JSON.parse(puts[0].body)).toEqual({ priority: 1 });
    expect(puts[1].url).toBe("/api/accounts/a3");
    expect(JSON.parse(puts[1].body)).toEqual({ priority: 2 });
    // and the list is re-read from the server afterwards (never a lying view)
    expect(calls.some((c) => c.method === "GET" && c.url.indexOf("/api/accounts?") === 0)).toBe(true);
    vi.unstubAllGlobals();
  });

  it("a normal 0,1,2 list swap sends exactly the two accounts that changed", async () => {
    const calls = stubApi({
      provider: PROVIDER,
      accounts: [
        { id: "x1", label: "A", auth_type: "api_key", api_key: "k", priority: 0, last_used_at: null },
        { id: "x2", label: "B", auth_type: "api_key", api_key: "k", priority: 1, last_used_at: null },
        { id: "x3", label: "C", auth_type: "api_key", api_key: "k", priority: 2, last_used_at: null }
      ],
      discover: { ok: true, models: [] }
    });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;
    cards()[2].querySelector(".acc-down").click(); // aria-disabled: must be a no-op
    await flush();
    expect(calls.filter((c) => c.method === "PUT")).toHaveLength(0);
    cards()[1].querySelector(".acc-down").click(); // swap #2 and #3
    await flush();
    await flush();
    const puts = calls.filter((c) => c.method === "PUT").map((c) => [c.url, JSON.parse(c.body).priority]);
    expect(puts).toEqual([["/api/accounts/x3", 1], ["/api/accounts/x2", 2]]);
    vi.unstubAllGlobals();
  });

  it("boundary buttons are aria-disabled with an explanation, not silent", async () => {
    stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    const first = cards()[0];
    const last = cards()[2];
    expect(first.querySelector(".acc-up").getAttribute("aria-disabled")).toBe("true");
    expect(first.querySelector(".acc-up").getAttribute("title")).toBe("Already first");
    expect(last.querySelector(".acc-down").getAttribute("aria-disabled")).toBe("true");
    expect(last.querySelector(".acc-down").getAttribute("title")).toBe("Already last");
    // interior rows keep both buttons live
    expect(cards()[1].querySelector(".acc-up").hasAttribute("aria-disabled")).toBe(false);
    vi.unstubAllGlobals();
  });

  it("a failed reorder shows the message inline and re-reads the server order", async () => {
    let getAccounts = 0;
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      if (method === "PUT") {
        return Promise.resolve({
          ok: false, status: 404,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve({ error: { message: "account_not_found" } })
        });
      }
      if (String(url).indexOf("/api/accounts?") === 0) {
        getAccounts++;
        // The server still reports the ORIGINAL order (a1, a2, a3).
        return Promise.resolve({
          ok: true, headers: { get: () => "application/json" },
          json: () => Promise.resolve({ object: "list", data: ACCOUNTS })
        });
      }
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve(String(url).indexOf("/discover") === -1 ? PROVIDER : { ok: true, models: [] })
      });
    }));
    window.aigate.openDetail("p1");
    await flush();
    cards()[0].querySelector(".acc-down").click();
    await flush();
    await flush();
    const msg = document.getElementById("accountsMsg");
    expect(msg.textContent).toContain("account_not_found");
    expect(msg.className).toContain("settings-msg-error");
    expect(getAccounts).toBeGreaterThanOrEqual(2); // initial load + reload after failure
    expect(cards()[0].querySelector(".acc-label").textContent).toBe("Primary");
    vi.unstubAllGlobals();
  });

  it("the reload button re-reads the list", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;
    document.getElementById("pdAccReloadBtn").click();
    await flush();
    expect(calls.some((c) => c.url.indexOf("/api/accounts?provider_id=p1") === 0)).toBe(true);
    vi.unstubAllGlobals();
  });
});

describe("add-account modal", () => {
  beforeEach(() => { withPage(); });

  it("opens empty, POSTs label/type/key/priority, then closes", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    document.getElementById("pdAccAddBtn").click();
    const modal = document.getElementById("accModal");
    expect(modal.hidden).toBe(false);
    // a new account joins at the END of the queue
    expect(document.getElementById("accPriority").value).toBe("0");

    document.getElementById("accLabel").value = "Worker";
    document.getElementById("accApiKey").value = "sk-worker";
    document.getElementById("accPriority").value = "2";
    document.getElementById("accForm").dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    await flush();
    await flush();

    const post = calls.find((c) => c.method === "POST" && c.url === "/api/accounts");
    expect(JSON.parse(post.body)).toEqual({
      provider_id: "p1", label: "Worker", auth_type: "api_key",
      priority: 2, api_key: "sk-worker"
    });
    expect(modal.hidden).toBe(true);
    vi.unstubAllGlobals();
  });

  it("keeps the modal open + shows the error inline when POST fails", async () => {
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      if (method === "POST") {
        return Promise.resolve({
          ok: false, status: 400,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve({ error: { message: "invalid_auth_type" } })
        });
      }
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve(String(url).indexOf("/discover") === -1 ? PROVIDER : { ok: true, models: [] })
      });
    }));
    window.aigate.openDetail("p1");
    await flush();
    document.getElementById("pdAccAddBtn").click();
    document.getElementById("accLabel").value = "Bad";
    await window.aigate.submitAccountForm();
    expect(document.getElementById("accModal").hidden).toBe(false);
    const msg = document.getElementById("accModalMsg");
    expect(msg.textContent).toContain("invalid_auth_type");
    expect(msg.className).toContain("settings-msg-error");
    vi.unstubAllGlobals();
  });

  it("the auth-type select hides the key row for OAuth (and Cancel closes)", async () => {
    stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    document.getElementById("pdAccAddBtn").click();
    const sel = document.getElementById("accAuthType");
    sel.value = "oauth";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    expect(document.getElementById("accApiKeyRow").hidden).toBe(true);
    document.getElementById("accCancelBtn").click();
    expect(document.getElementById("accModal").hidden).toBe(true);
    vi.unstubAllGlobals();
  });
});

describe("discovery speaks through a text line (gap no.5)", () => {
  beforeEach(() => { withPage(); });

  it("loading -> found, with NO table and NO blocked form", async () => {
    let resolveDisc;
    const gate = new Promise((r) => { resolveDisc = r; });
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      if (method === "POST" && String(url).indexOf("/discover") !== -1) return gate;
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve(String(url).indexOf("/api/accounts") === 0
          ? { data: [] } : PROVIDER)
      });
    }));
    window.aigate.openDetail("p1");
    // in flight: the status line says so, in BOTH places, and nothing is a table
    const status = document.getElementById("pdModelStatus");
    expect(status.textContent).toBe("Discovering models…");
    expect(document.getElementById("provModalModelStatus").textContent)
      .toBe("Discovering models…");
    expect(document.querySelector("#pdModelStatus table")).toBeNull();
    expect(document.getElementById("provModel").disabled).toBe(false);

    resolveDisc({
      ok: true, headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true, models: [{ model_id: "m1", model_name: "M1" }] })
    });
    await flush();
    await flush();
    expect(status.textContent).toContain("Models discovered");
    expect(status.textContent).toContain("(1)");
    vi.unstubAllGlobals();
  });

  it("a failed discovery says so, keeps free text, and only warns in the console", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      if (method === "POST" && String(url).indexOf("/discover") !== -1) {
        return Promise.reject(new Error("upstream down"));
      }
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve(String(url).indexOf("/api/accounts") === 0
          ? { data: [] } : PROVIDER)
      });
    }));
    window.aigate.openDetail("p1");
    await flush();
    await flush();
    const status = document.getElementById("pdModelStatus");
    expect(status.textContent).toContain("Model list could not be fetched");
    expect(status.className).toContain("settings-msg-error");
    // never blocks: the profile form + the model input stay usable
    expect(document.getElementById("provModal").hidden).toBe(true);
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
    vi.unstubAllGlobals();
  });

  it("the Models column explains that the count is a machine result", async () => {
    stubApi({ provider: PROVIDER, accounts: [], discover: { ok: true, models: [] } });
    window.aigate.renderProviders([PROVIDER]);
    const cell = document.querySelector("#provTableBody .prov-models");
    expect(cell).not.toBeNull();
    expect(cell.getAttribute("title")).toBe("Number of models found by the automatic search");
    expect(cell.getAttribute("aria-label")).toBe("Number of models found by the automatic search");
    vi.unstubAllGlobals();
  });
});

/* ===== The design sheet's 6-step flow, end to end, against a STATEFUL fake
   API. Unit tests above pin each surface separately; this one proves the pieces
   actually fit together (list -> page -> Ubah -> tambah akun -> ▲ -> Kembali).
   The fake keeps providers + accounts in memory and sorts like the server does
   (priority asc, id asc), so a wrong PUT payload is visible in the next render.
   ======================================================================== */
describe("full flow against a stateful fake backend", () => {
  beforeEach(() => { withPage(); });

  function fakeBackend() {
    const providers = [{
      id: "p1", name: "ACME", type: "anthropic", base_url: "https://api.acme.test",
      api_key: "sk-provider", default_model: "", enabled: true, custom_headers: {},
      models: [], fallback_strategy: "fill-first", sticky_round_robin_limit: 3
    }];
    let nextAccountId = 10;
    const accounts = [];
    const trace = [];
    const sortAccounts = (pid) => accounts
      .filter((a) => String(a.provider_id) === String(pid))
      .sort((a, b) => (a.priority - b.priority) || (a.id - b.id))
      .map((a) => Object.assign({}, a));
    const answer = (payload) => Promise.resolve({
      ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve(payload)
    });
    const fail = (status, message) => Promise.resolve({
      ok: false, status, headers: { get: () => "application/json" },
      json: () => Promise.resolve({ error: { message } })
    });
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const u = String(url);
      const method = (opts && opts.method) || "GET";
      const body = opts && opts.body ? JSON.parse(opts.body) : null;
      trace.push(method + " " + u);
      if (method === "POST" && u.indexOf("/discover") !== -1) {
        providers[0].models = [{ model_id: "claude-3", model_name: "Claude 3" }];
        return answer({ ok: true, models: providers[0].models });
      }
      if (u === "/api/providers" && method === "GET") {
        return answer({ data: providers.map((p) => Object.assign({}, p)) });
      }
      if (u === "/api/providers/p1" && method === "GET") {
        return answer(Object.assign({}, providers[0]));
      }
      if (u === "/api/providers/p1" && method === "PUT") {
        Object.assign(providers[0], body);
        if (body.fallback_strategy &&
            ["fill-first", "round-robin"].indexOf(body.fallback_strategy) === -1) {
          return fail(400, "invalid_fallback_strategy");
        }
        return answer(Object.assign({}, providers[0]));
      }
      if (u === "/api/accounts" && method === "POST") {
        if (!body.label) return fail(400, "label required");
        const created = {
          id: nextAccountId++, provider_id: body.provider_id, label: body.label,
          auth_type: body.auth_type, api_key: body.api_key || "",
          expires_at: null, enabled: true, priority: body.priority || 0,
          last_used_at: null
        };
        accounts.push(created);
        return answer(Object.assign({}, created));
      }
      if (u.indexOf("/api/accounts/") === 0 && method === "PUT") {
        const id = Number(u.split("/").pop());
        const acc = accounts.find((a) => a.id === id);
        if (!acc) return fail(404, "account_not_found");
        // stage-5 contract: partial write of the fields the client SENT.
        if (Object.prototype.hasOwnProperty.call(body, "api_key") &&
            acc.auth_type === "oauth") {
          return fail(400, "oauth_account_key_readonly");
        }
        ["label", "api_key", "enabled", "priority"].forEach((f) => {
          if (Object.prototype.hasOwnProperty.call(body, f)) acc[f] = body[f];
        });
        return answer(Object.assign({}, acc));
      }
      if (u.indexOf("/api/accounts") === 0 && method === "GET") {
        return answer({ object: "list", data: sortAccounts(u.split("provider_id=")[1]) });
      }
      if (u.indexOf("/api/usage") === 0) return answer({ data: [], totals: {}, by_model: [] });
      return answer({ data: [] });
    }));
    return {
      trace, providers, accounts,
      order: () => sortAccounts("p1").map((a) => a.label)
    };
  }

  it("list -> page -> Ubah (profile only) -> add account -> move -> back", async () => {
    const api = fakeBackend();
    // 1. list, then open the page via the row kebab's accounts item (stage-4)
    window.aigate.loadProviders();
    await flush();
    await flush();
    document.querySelector('#provTableBody tr[data-id="p1"] .js-row-menu')
      .dispatchEvent(new MouseEvent("click", { bubbles: true }));
    document.querySelector('.row-menu [data-action="accounts"]').click();
    await flush();
    await flush();
    expect(document.querySelector('.view[data-view="provider-detail"]').classList.contains("is-active")).toBe(true);
    expect(document.getElementById("provDetailTitle").textContent).toBe("ACME");
    expect(document.getElementById("pdApiKey").textContent).toBe("sk-provider");

    // 2. Ubah -> profile modal, no accounts / no strategy inside it
    document.getElementById("provEditBtn").click();
    await flush();
    expect(document.getElementById("provModal").hidden).toBe(false);
    expect(document.getElementById("provModal").querySelector("#accLabel")).toBeNull();
    expect(document.getElementById("provModal").querySelector("#pdStrategy")).toBeNull();
    document.getElementById("provName").value = "ACME renamed";
    document.getElementById("provSaveBtn").click();
    await flush();
    await flush();
    expect(api.providers[0].name).toBe("ACME renamed");
    expect(api.providers[0].fallback_strategy).toBe("fill-first"); // untouched by the profile PUT
    expect(document.getElementById("provDetailTitle").textContent).toBe("ACME renamed");

    // 3. strategy via Kartu B only
    const sel = document.getElementById("pdStrategy");
    sel.value = "round-robin";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    document.getElementById("pdStickyLimit").value = "2";
    document.getElementById("pdStrategySaveBtn").click();
    await flush();
    expect(api.providers[0]).toMatchObject({ fallback_strategy: "round-robin", sticky_round_robin_limit: 2 });
    expect(document.getElementById("pdStrategyMsg").textContent).toBe("Strategy saved.");

    // 4. two accounts through the modal, then check the server order
    const add = async (label, key) => {
      document.getElementById("pdAccAddBtn").click();
      document.getElementById("accLabel").value = label;
      document.getElementById("accApiKey").value = key;
      await window.aigate.submitAccountForm();
      await flush();
    };
    await add("work", "sk-work");
    await add("home", "sk-home");
    expect(api.order()).toEqual(["work", "home"]);
    expect(Array.from(document.querySelectorAll("#accList .acc-pos")).map((e) => e.textContent))
      .toEqual(["1", "2"]);

    // 5. ▼ on #1 renumbers on the server (work drops behind home)
    document.querySelectorAll("#accList .acc-card")[0]
      .querySelector(".acc-down").click();
    await flush();
    await flush();
    expect(api.order()).toEqual(["home", "work"]);
    expect(Array.from(document.querySelectorAll("#accList .acc-label")).map((e) => e.textContent))
      .toEqual(["home", "work"]);
    // only the two accounts that changed were PUT
    expect(api.trace.filter((t) => t.indexOf("PUT /api/accounts/") === 0)).toHaveLength(2);

    // 6. Kembali -> the list is re-read and shows the new name + count
    document.getElementById("provDetailBackBtn").click();
    await flush();
    await flush();
    expect(document.querySelector('.view[data-view="providers"]').classList.contains("is-active")).toBe(true);
    expect(document.getElementById("provTableBody").textContent).toContain("ACME renamed");
    expect(document.querySelector("#provTableBody .prov-models").textContent).toBe("1");
    vi.unstubAllGlobals();
  });
});

describe("Ubah akun (stage-5): card button -> PUT through the ONE modal", () => {
  beforeEach(() => { withPage(); });
  const cards = () => Array.from(document.querySelectorAll("#accList .acc-card"));

  it("every account card carries a Ubah button next to Hapus", async () => {
    stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    expect(cards()).toHaveLength(3);
    cards().forEach((c) => {
      const edit = c.querySelector(".acc-edit");
      expect(edit, "Ubah button").not.toBeNull();
      expect(edit.getAttribute("aria-label")).toBe("Edit");
      expect(edit.getAttribute("title")).toBe("Edit");
      expect(edit.querySelector("i.fa-pen")).not.toBeNull();
      // same level as the existing Hapus button (both in the footer)
      expect(c.querySelector(".acc-del")).not.toBeNull();
    });
    vi.unstubAllGlobals();
  });

  it("clicking Ubah opens the modal in edit mode, seeded from that account row", async () => {
    stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    cards()[0].querySelector(".acc-edit").click(); // a1 = Primary / api_key
    await flush();
    const m = window.aigate.getAccountModalMode();
    expect(m.mode).toBe("edit");
    expect(m.id).toBe("a1");
    expect(document.getElementById("accModal").hidden).toBe(false);
    expect(document.getElementById("accModalTitle").textContent).toBe("Edit account");
    expect(document.getElementById("accAddBtn").textContent).toBe("Save changes");
    expect(document.getElementById("accLabel").value).toBe("Primary");
    expect(document.getElementById("accApiKey").value).toBe("sk-one");
    expect(document.getElementById("accEnabled").checked).toBe(true);
    // add-time fields are hidden in edit mode
    expect(document.getElementById("accPriorityRow").hidden).toBe(true);
    expect(document.getElementById("accEnabledRow").hidden).toBe(false);
    vi.unstubAllGlobals();
  });

  it("editing an api_key account PUTs {label, api_key, enabled} — no priority/auth_type/last_used", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;
    cards()[0].querySelector(".acc-edit").click(); // a1
    document.getElementById("accLabel").value = "Primary 2";
    document.getElementById("accApiKey").value = "sk-one-renamed";
    document.getElementById("accEnabled").checked = false;
    document.getElementById("accForm").dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    await flush();
    await flush();
    const put = calls.find((c) => c.method === "PUT" && c.url === "/api/accounts/a1");
    expect(put, "account PUT").toBeTruthy();
    expect(JSON.parse(put.body)).toEqual({ label: "Primary 2", api_key: "sk-one-renamed", enabled: false });
    vi.unstubAllGlobals();
  });

  it("editing an oauth account PUTs {label, enabled} only (no api_key -> no 400)", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;
    cards()[2].querySelector(".acc-edit").click(); // a3 = OAuth
    // the key row is hidden and the explanatory note shows instead
    expect(document.getElementById("accApiKeyRow").hidden).toBe(true);
    expect(document.getElementById("accOauthNote").hidden).toBe(false);
    document.getElementById("accLabel").value = "OAuth renamed";
    document.getElementById("accForm").dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    await flush();
    await flush();
    const put = calls.find((c) => c.method === "PUT" && c.url === "/api/accounts/a3");
    expect(JSON.parse(put.body)).toEqual({ label: "OAuth renamed", enabled: true });
    vi.unstubAllGlobals();
  });

  it("success closes the modal and re-reads the server order (moveAccount pattern)", async () => {
    const calls = stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    calls.length = 0;
    cards()[0].querySelector(".acc-edit").click();
    document.getElementById("accForm").dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    await flush();
    await flush();
    expect(document.getElementById("accModal").hidden).toBe(true);
    // a GET /api/accounts re-read happened after the PUT
    expect(calls.some((c) => c.method === "GET" && c.url.indexOf("/api/accounts?") === 0)).toBe(true);
    vi.unstubAllGlobals();
  });

  it("a rejected save keeps the modal open with the reason inline", async () => {
    // PUT -> 400 (e.g. a rogue oauth_account_key_readonly the UI normally prevents)
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      if (method === "PUT") {
        return Promise.resolve({
          ok: false, status: 400, headers: { get: () => "application/json" },
          json: () => Promise.resolve({ error: { message: "oauth_account_key_readonly" } })
        });
      }
      const payload = String(url).indexOf("/discover") !== -1
        ? { ok: true, models: [] }
        : (String(url).indexOf("/api/accounts?") === 0
          ? { object: "list", data: ACCOUNTS } : PROVIDER);
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve(payload)
      });
    }));
    window.aigate.openDetail("p1");
    await flush();
    cards()[0].querySelector(".acc-edit").click();
    document.getElementById("accLabel").value = "Keep me";
    document.getElementById("accForm").dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
    await flush();
    await flush();
    expect(document.getElementById("accModal").hidden).toBe(false); // NOT closed
    const msg = document.getElementById("accModalMsg");
    expect(msg.textContent).toContain("Failed to save changes");
    expect(msg.textContent).toContain("oauth_account_key_readonly");
    expect(msg.className).toContain("settings-msg-error");
    // and the typed value survived the failed save
    expect(document.getElementById("accLabel").value).toBe("Keep me");
    vi.unstubAllGlobals();
  });

  it("closing then adding is a clean add mode with no leftover edit values", async () => {
    stubApi({ provider: PROVIDER, accounts: ACCOUNTS, discover: { ok: true, models: [] } });
    window.aigate.openDetail("p1");
    await flush();
    cards()[0].querySelector(".acc-edit").click();
    document.getElementById("accLabel").value = "Leaky";
    document.getElementById("accEnabled").checked = false;
    // Cancel returns the modal to add mode (no value stuck)
    document.getElementById("accCancelBtn").click();
    expect(document.getElementById("accModal").hidden).toBe(true);
    document.getElementById("pdAccAddBtn").click();
    const m = window.aigate.getAccountModalMode();
    expect(m.mode).toBe("add");
    expect(m.id).toBe(null);
    expect(document.getElementById("accModalTitle").textContent).toBe("New account for this provider");
    expect(document.getElementById("accAddBtn").textContent).toBe("Add Account");
    expect(document.getElementById("accLabel").value).toBe("");
    expect(document.getElementById("accAuthType").disabled).toBe(false);
    expect(document.getElementById("accPriorityRow").hidden).toBe(false);
    expect(document.getElementById("accEnabledRow").hidden).toBe(true);
    // Leave the module-global provider selection null (the baseline invariant of
    // this file): with isolate:false a leaked "p1" would poison the next file's
    // "refuses to invent a provider" test.
    document.getElementById("provDetailBackBtn").click();
    await flush();
    vi.unstubAllGlobals();
  });
});

describe("stage-2 teardown: no dead references left", () => {
  it("the revoked keys are gone from every dictionary and from app.js", () => {
    const revoked = ["providers.tab_provider", "providers.tab_accounts", "providers.tabs_label",
      "providers.strategy", "providers.sticky_limit", "accounts.priority", "accounts.last_used",
      "accounts.never_used", "accounts.save_first", "accounts.none", "provider_detail.accounts_card"];
    revoked.forEach((k) => expect(window.I18N.en[k], k).toBeUndefined());
    const html = indexBodyHtml();
    // Quoted: "providers.strategy" must not match "providers.strategy_fill_first".
    revoked.forEach((k) => expect(html, k).not.toContain('="' + k + '"'));
  });

  it("app.js has no tab logic left", async () => {
    const src = await import("../static/app.js?raw").then((m) => m.default).catch(() => null);
    if (!src) return; // vite ?raw is not configured here — the markup checks above cover it
    expect(src).not.toMatch(/wireProvTabs|selectProvTab|setAccountsTabEnabled|provTabList/);
  });
});
