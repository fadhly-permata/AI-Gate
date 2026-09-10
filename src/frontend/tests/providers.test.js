import { describe, it, expect, vi, beforeEach } from "vitest";
import { indexDocument, indexHtml } from "./helpers/dom.js";

// i18n.js attaches window.I18N + window.applyLocale (jsdom provides DOM).
import "../static/i18n.js";
// combobox.js attaches window.aigate.createCombobox (loaded before app.js in
// index.html — same order here).
import "../static/combobox.js";
// app.js wires the UI and exposes window.aigate.mapProviderToRow /
// window.aigate.buildHeadersDict / window.aigate.headersToRows.
import "../static/app.js";


// Let async .then chains (fetchJson / testProviderConnection) resolve.
const flush = () => new Promise((r) => setTimeout(r, 0));

// The modal DOM as stage-2 ships it: an ARIA tablist ([Provider] | [Accounts])
// + a hint, the form wrapped in its tabpanel, the (empty) Accounts panel, and
// the strategy controls inside the form. #provModel is a searchable COMBOBOX:
// a text input + a custom <ul> panel (NOT <datalist>).
function withProviderModalDom() {
  document.body.innerHTML =
    '<div id="provModal">' +
      '<h3 id="provModalTitle"></h3>' +
      '<div id="provTabList" role="tablist">' +
        '<button type="button" class="modal-tab is-active" id="provTabProvider" role="tab" ' +
          'aria-selected="true" aria-controls="provPanelProvider" tabindex="0">Provider</button>' +
        '<button type="button" class="modal-tab" id="provTabAccounts" role="tab" ' +
          'aria-selected="false" aria-controls="provPanelAccounts" tabindex="-1">Accounts</button>' +
      '</div>' +
      '<p id="provTabHint" hidden></p>' +
      '<form id="provForm">' +
        '<div id="provPanelProvider" role="tabpanel" aria-labelledby="provTabProvider">' +
          '<input type="hidden" id="provId" />' +
          '<input id="provName" />' +
          '<select id="provType">' +
            '<option value="openai-compatible">openai-compatible</option>' +
          '</select>' +
          '<input id="provBaseUrl" />' +
          '<input id="provApiKey" />' +
          '<div class="aigate-combo">' +
            '<input type="text" id="provModel" />' +
            '<ul id="provModelList" role="listbox" hidden></ul>' +
          '</div>' +
          '<input type="checkbox" id="provEnabled" />' +
          '<select id="provStrategy">' +
            '<option value="fill-first">Fill first</option>' +
            '<option value="round-robin">Round-robin</option>' +
          '</select>' +
          '<div id="provStickyRow" hidden>' +
            '<input type="number" id="provStickyLimit" min="1" step="1" value="3" />' +
          '</div>' +
          '<div id="provHeaders"></div>' +
        '</div>' +
      '</form>' +
      '<div id="provPanelAccounts" role="tabpanel" aria-labelledby="provTabAccounts" hidden></div>' +
      '<button type="button" id="provTestBtn">Test Connection</button>' +
      '<p id="provModalMsg"></p>' +
      '<p id="provMsg"></p>' +
    '</div>';
}

// The legacy DETAIL card DOM (kept reachable through the provider-name button
// and the legacy window.aigate.discoverModels export). The discovered-models
// TABLE is gone from the shipped page (stage-2): discovery is silent now.
function withDetailDom() {
  document.body.innerHTML =
    '<div id="provDetail">' +
      '<h3 id="provDetailTitle"></h3>' +
      '<p id="provModelMsg"></p>' +
      '<p id="provMsg"></p>' +
    '</div>' +
    '<div class="aigate-combo">' +
      '<input type="text" id="provModel" />' +
      '<ul id="provModelList" role="listbox" hidden></ul>' +
    '</div>';
}

// The combobox panel's rendered option values (model ids), in DOM order.
const provModelOptionValues = () => Array.from(
  document.getElementById("provModelList").querySelectorAll('li[role="option"]')
).map((li) => li.getAttribute("data-value"));

// Minimal fetch router for the openEditModal flow: answers the provider GET,
// the silent POST /discover, the accounts GET and the list refresh.
function stubEditModalApi({ provider, discover, accounts }) {
  const calls = [];
  vi.stubGlobal("fetch", vi.fn((url, opts) => {
    const method = (opts && opts.method) || "GET";
    calls.push({ url: String(url), method, body: opts && opts.body });
    let payload = { data: [] };
    if (method === "POST" && String(url).indexOf("/discover") !== -1) payload = discover;
    else if (String(url).indexOf("/accounts") !== -1) payload = accounts;
    else if (String(url) === "/api/providers/p1") payload = provider;
    return Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(payload)
    });
  }));
  return calls;
}

describe("mapProviderToRow (pure helper)", () => {
  it("flattens a ProviderDTO into table-row data", () => {
    const dto = {
      id: "p1",
      name: "OpenAI",
      type: "openai-compatible",
      base_url: "https://api.openai.com/v1",
      api_key: "sk-secret",
      enabled: true,
      custom_headers: { "X-Tenant": "acme" },
      models: [
        { id: "m1", model_id: "gpt-4", model_name: "GPT-4" },
        { id: "m2", model_id: "gpt-3.5", model_name: "GPT-3.5" }
      ]
    };
    const row = window.aigate.mapProviderToRow(dto);
    expect(row).toEqual({
      id: "p1",
      name: "OpenAI",
      type: "openai-compatible",
      base_url: "https://api.openai.com/v1",
      enabled: true,
      modelCount: 2
    });
  });

  it("treats missing models as 0 and coerces enabled to boolean", () => {
    const row = window.aigate.mapProviderToRow({ id: "x", enabled: 0 });
    expect(row.enabled).toBe(false);
    expect(row.modelCount).toBe(0);
    expect(row.name).toBeUndefined();
    expect(row.type).toBeUndefined();
  });

  it("is independent of api_key (no redaction logic, ADR-007)", () => {
    const row = window.aigate.mapProviderToRow({ id: "k", api_key: "plain-secret" });
    // key is intentionally NOT part of the row datum, proving no masking logic.
    expect(row).not.toHaveProperty("api_key");
  });
});

describe("buildHeadersDict (pure helper)", () => {
  it("builds a dict from key/value editor rows", () => {
    const rows = [
      { key: "X-Auth", value: "abc" },
      { key: "X-Tenant", value: "acme" }
    ];
    expect(window.aigate.buildHeadersDict(rows)).toEqual({
      "X-Auth": "abc",
      "X-Tenant": "acme"
    });
  });

  it("skips rows with empty/whitespace keys but keeps the value dict shape", () => {
    const rows = [
      { key: "", value: "ignored" },
      { key: "   ", value: "ignored-too" },
      { key: "X-Ok", value: "" }
    ];
    expect(window.aigate.buildHeadersDict(rows)).toEqual({ "X-Ok": "" });
  });

  it("trims keys and tolerates null/undefined values", () => {
    const rows = [{ key: "  X-Trim  ", value: null }, { key: "X-B", value: undefined }];
    const dict = window.aigate.buildHeadersDict(rows);
    expect(dict).toEqual({ "X-Trim": "", "X-B": "" });
  });

  it("returns an empty dict for no rows / null input", () => {
    expect(window.aigate.buildHeadersDict([])).toEqual({});
    expect(window.aigate.buildHeadersDict(null)).toEqual({});
  });
});

describe("headersToRows (pure helper, inverse)", () => {
  it("expands a dict back into editor rows", () => {
    const rows = window.aigate.headersToRows({ "X-A": "1", "X-B": "2" });
    expect(rows).toEqual([{ key: "X-A", value: "1" }, { key: "X-B", value: "2" }]);
  });

  it("round-trips with buildHeadersDict", () => {
    const dict = { "X-A": "1", "X-B": "2" };
    const back = window.aigate.buildHeadersDict(window.aigate.headersToRows(dict));
    expect(back).toEqual(dict);
  });
});

describe("Test Connection button (B2.2)", () => {
  beforeEach(() => { withProviderModalDom(); });

  it("POSTs form values to /api/providers/test and shows OK on {ok:true}", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, body: opts && opts.body });
      return Promise.resolve({
        ok: true,
        headers: { get: () => "application/json" },
        json: () => Promise.resolve({ ok: true })
      });
    }));

    document.getElementById("provType").value = "openai-compatible";
    document.getElementById("provBaseUrl").value = "https://api.openai.com/v1";
    document.getElementById("provApiKey").value = "sk-xyz";
    document.getElementById("provModel").value = "gpt-4";

    // Wire the button exactly as init() does, then click it (true wiring test).
    document.getElementById("provTestBtn")
      .addEventListener("click", window.aigate.testProviderConnection);
    document.getElementById("provTestBtn").click();

    await flush();

    const testCall = calls.find((c) => c.url === "/api/providers/test");
    expect(testCall).toBeTruthy();
    expect(JSON.parse(testCall.body)).toEqual({
      type: "openai-compatible",
      base_url: "https://api.openai.com/v1",
      api_key: "sk-xyz",
      model: "gpt-4"
    });
    expect(document.getElementById("provModalMsg").textContent).toContain("Connection OK");
    expect(document.getElementById("provModalMsg").className).toContain("settings-msg-ok");
    vi.unstubAllGlobals();
  });

  it("shows the error inline on {ok:false}", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: false, error: "bad key" })
    })));

    window.aigate.testProviderConnection();
    await flush();

    const msg = document.getElementById("provModalMsg");
    expect(msg.textContent).toContain("Connection failed: ");
    expect(msg.textContent).toContain("bad key");
    expect(msg.className).toContain("settings-msg-error");
    vi.unstubAllGlobals();
  });

  it("disables the button while in flight then re-enables it", async () => {
    let resolveFetch;
    vi.stubGlobal("fetch", vi.fn(() => new Promise((res) => {
      resolveFetch = res;
    })));

    const btn = document.getElementById("provTestBtn");
    window.aigate.testProviderConnection();
    // Synchronously the request is in flight.
    expect(btn.disabled).toBe(true);
    expect(btn.textContent).toBe("...");

    resolveFetch({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true })
    });
    await flush();

    expect(btn.disabled).toBe(false);
    expect(btn.textContent).toBe("Test Connection");
    vi.unstubAllGlobals();
  });
});

describe("saveProvider persists default_model + strategy (B2.2 / stage-2)", () => {
  beforeEach(() => { withProviderModalDom(); });

  it("includes default_model + fallback_strategy in the POST body (add, fill-first)", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, body: opts && opts.body });
      return Promise.resolve({
        ok: true,
        headers: { get: () => "application/json" },
        json: () => Promise.resolve({ data: [] })
      });
    }));

    document.getElementById("provId").value = ""; // add -> POST
    document.getElementById("provName").value = "ACME";
    document.getElementById("provType").value = "openai-compatible";
    document.getElementById("provBaseUrl").value = "https://api.acme.com";
    document.getElementById("provApiKey").value = "sk-acme";
    document.getElementById("provModel").value = "claude-3";
    document.getElementById("provEnabled").checked = true;

    window.aigate.saveProvider();
    await flush();

    const saved = calls.find((c) => c.url === "/api/providers" && c.body);
    expect(saved).toBeTruthy();
    const body = JSON.parse(saved.body);
    expect(body.default_model).toBe("claude-3");
    // Strategy always travels; the sticky limit only when round-robin (the
    // hidden+disabled row must not masquerade as a live value).
    expect(body.fallback_strategy).toBe("fill-first");
    expect(body).not.toHaveProperty("sticky_round_robin_limit");
    // sanity: other fields still present
    expect(body.name).toBe("ACME");
    expect(body.api_key).toBe("sk-acme");
    vi.unstubAllGlobals();
  });

  it("sends both strategy fields when round-robin (PUT on edit)", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({
        ok: true,
        headers: { get: () => "application/json" },
        json: () => Promise.resolve({ data: [] })
      });
    }));

    document.getElementById("provId").value = "p1"; // edit -> PUT
    document.getElementById("provStrategy").value = "round-robin";
    window.aigate.syncStickyLimitRow(); // init() wires this to the change event
    document.getElementById("provStickyLimit").value = "4";

    window.aigate.saveProvider();
    await flush();

    const put = calls.find((c) => c.url === "/api/providers/p1" && c.opts.method === "PUT");
    expect(put).toBeTruthy();
    const body = JSON.parse(put.opts.body);
    expect(body.fallback_strategy).toBe("round-robin");
    expect(body.sticky_round_robin_limit).toBe(4);
    vi.unstubAllGlobals();
  });

  it("clamps a zero/blank sticky limit to >=1 / default 3", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ data: [] })
      });
    }));

    document.getElementById("provStrategy").value = "round-robin";
    document.getElementById("provStickyLimit").value = "0";
    window.aigate.saveProvider();
    await flush();
    const post1 = calls.find((c) => c.opts && c.opts.body);
    expect(JSON.parse(post1.opts.body).sticky_round_robin_limit).toBe(1); // Math.max(1, 0)

    calls.length = 0;
    document.getElementById("provStickyLimit").value = "";
    window.aigate.saveProvider();
    await flush();
    const post2 = calls.find((c) => c.opts && c.opts.body);
    expect(JSON.parse(post2.opts.body).sticky_round_robin_limit).toBe(3); // blank -> default
    vi.unstubAllGlobals();
  });
});

describe("sticky limit row sync (stage-2)", () => {
  beforeEach(() => { withProviderModalDom(); });

  it("fill-first hides + disables the row; round-robin shows + enables it", () => {
    // Wire the select exactly as init() does.
    document.getElementById("provStrategy")
      .addEventListener("change", window.aigate.syncStickyLimitRow);
    const row = document.getElementById("provStickyRow");
    const inp = document.getElementById("provStickyLimit");

    const sel = document.getElementById("provStrategy");
    sel.value = "fill-first";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    expect(row.hidden).toBe(true);
    expect(inp.disabled).toBe(true);

    sel.value = "round-robin";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    expect(row.hidden).toBe(false);
    expect(inp.disabled).toBe(false);
  });
});

describe("provider modal tabs — index.html structure (stage-2)", () => {
  const doc = indexDocument();
  const html = indexHtml();

  it("provTabList is an ARIA tablist with two tabs bound to their panels", () => {
    const list = doc.getElementById("provTabList");
    expect(list).not.toBeNull();
    expect(list.getAttribute("role")).toBe("tablist");
    expect(list.getAttribute("data-i18n-aria")).toBe("providers.tabs_label");
    const tabs = list.querySelectorAll('[role="tab"]');
    expect(tabs).toHaveLength(2);
    tabs.forEach((t) => {
      const panel = doc.getElementById(t.getAttribute("aria-controls"));
      expect(panel, t.id + " controls a real panel").not.toBeNull();
      expect(panel.getAttribute("role")).toBe("tabpanel");
      expect(panel.getAttribute("aria-labelledby")).toBe(t.id);
    });
    // Exactly one panel active; the other hidden.
    const provider = doc.getElementById("provTabProvider");
    const accounts = doc.getElementById("provTabAccounts");
    expect(provider.getAttribute("aria-selected")).toBe("true");
    expect(accounts.getAttribute("aria-selected")).toBe("false");
    expect(doc.getElementById("provPanelProvider").hasAttribute("hidden")).toBe(false);
    expect(doc.getElementById("provPanelAccounts").hasAttribute("hidden")).toBe(true);
    // Roving tabindex: only the selected tab is in the tab order.
    expect(accounts.getAttribute("tabindex")).toBe("-1");
  });

  it("the Accounts subsection lives in the modal Accounts panel now", () => {
    const panel = doc.getElementById("provPanelAccounts");
    ["accountsTable", "accountsBody", "accountsMsg", "accLabel", "accAuthType",
      "accApiKey", "accPriority", "accAddBtn", "provConnectOAuthBtn"]
      .forEach((id) => expect(panel.querySelector("#" + id), id).not.toBeNull());
    // And it is NOT in the detail card anymore.
    expect(doc.getElementById("provDetail").querySelector("#accountsBody")).toBeNull();
  });

  it("the discovery UI is gone from the shipped page (silent /discover instead)", () => {
    expect(doc.getElementById("provModelsTable")).toBeNull();
    expect(doc.getElementById("provModelsBody")).toBeNull();
    expect(doc.getElementById("provDiscoverBtn")).toBeNull();
    expect(doc.getElementById("provModelMsg")).toBeNull();
    expect(html).not.toContain("providers.discover\""); // no binding left in markup
    // The accounts add form exposes a priority input (contract default 0).
    const pr = doc.getElementById("accPriority");
    expect(pr.getAttribute("type")).toBe("number");
    expect(pr.getAttribute("min")).toBe("0");
  });

  it("strategy controls carry the exact contract enum + sane sticky input", () => {
    const sel = doc.getElementById("provStrategy");
    expect(sel.tagName).toBe("SELECT");
    const opts = Array.from(sel.querySelectorAll("option"));
    expect(opts.map((o) => o.getAttribute("value")))
      .toEqual(["fill-first", "round-robin"]);
    // Human labels via i18n, never the raw enum as visible text.
    opts.forEach((o) => expect(o.getAttribute("data-i18n")).toBeTruthy());
    expect(opts.map((o) => o.getAttribute("data-i18n"))).toEqual([
      "providers.strategy_fill_first", "providers.strategy_round_robin"
    ]);
    const lim = doc.getElementById("provStickyLimit");
    expect(lim.getAttribute("type")).toBe("number");
    expect(lim.getAttribute("min")).toBe("1");
    expect(lim.getAttribute("step")).toBe("1");
    expect(lim.getAttribute("name")).toBe("sticky_round_robin_limit");
    // Default strategy is fill-first, so the sticky row starts hidden.
    expect(doc.getElementById("provStickyRow").hasAttribute("hidden")).toBe(true);
    // The add-mode hint is hidden by default and bound to the i18n key.
    const hint = doc.getElementById("provTabHint");
    expect(hint.hasAttribute("hidden")).toBe(true);
    expect(hint.getAttribute("data-i18n")).toBe("accounts.save_first");
  });

  it("detail card is tidy: title + Edit/Delete + usage, no dead controls", () => {
    const detail = doc.getElementById("provDetail");
    expect(detail.querySelector("#provDetailTitle")).not.toBeNull();
    expect(detail.querySelector("#provEditBtn")).not.toBeNull();
    expect(detail.querySelector("#provDeleteBtn")).not.toBeNull();
    // B5.5 usage subsection survives (usage.js renders into it).
    expect(detail.querySelector("#provUsageTotals")).not.toBeNull();
    expect(detail.querySelector("#provUsageModelBody")).not.toBeNull();
    expect(detail.querySelector("button")).not.toBeNull(); // Edit/Delete wired
  });
});

describe("modal tab behavior (roving tabindex + keyboard)", () => {
  const press = (key) => {
    document.activeElement.dispatchEvent(
      new KeyboardEvent("keydown", { key, bubbles: true })
    );
  };

  beforeEach(() => {
    withProviderModalDom();
    // Wire exactly as init() does.
    window.aigate.wireProvTabs();
  });

  it("clicking a tab activates it: one panel visible, aria + tabindex synced", () => {
    document.getElementById("provTabAccounts").click();
    expect(document.getElementById("provTabAccounts").getAttribute("aria-selected")).toBe("true");
    expect(document.getElementById("provTabProvider").getAttribute("aria-selected")).toBe("false");
    expect(document.getElementById("provPanelAccounts").hidden).toBe(false);
    expect(document.getElementById("provPanelProvider").hidden).toBe(true);
    expect(document.getElementById("provTabAccounts").tabIndex).toBe(0);
    expect(document.getElementById("provTabProvider").tabIndex).toBe(-1);
  });

  it("ArrowRight/ArrowLeft wrap, Home/End jump between the two tabs", () => {
    document.getElementById("provTabProvider").focus();
    press("ArrowRight");
    expect(document.getElementById("provTabAccounts").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement.id).toBe("provTabAccounts");
    press("ArrowRight"); // wraps back (only two enabled tabs)
    expect(document.getElementById("provTabProvider").getAttribute("aria-selected")).toBe("true");
    press("ArrowLeft");
    expect(document.activeElement.id).toBe("provTabAccounts");
    press("Home");
    expect(document.activeElement.id).toBe("provTabProvider");
    press("End");
    expect(document.activeElement.id).toBe("provTabAccounts");
  });

  it("ADD mode: Accounts tab is aria-disabled, the hint explains, arrows never land on it", () => {
    window.aigate.openAddModal();
    const acc = document.getElementById("provTabAccounts");
    const hint = document.getElementById("provTabHint");
    expect(acc.getAttribute("aria-disabled")).toBe("true");
    expect(hint.hidden).toBe(false); // "save the provider first", not a dead tab
    expect(document.getElementById("provTabProvider").getAttribute("aria-selected")).toBe("true");
    acc.click(); // clicking a disabled tab must not activate it
    expect(acc.getAttribute("aria-selected")).toBe("false");
    expect(document.getElementById("provPanelAccounts").hidden).toBe(true);
    document.getElementById("provTabProvider").focus();
    press("ArrowRight");
    expect(document.activeElement.id).toBe("provTabProvider");
    press("End");
    expect(document.activeElement.id).toBe("provTabProvider");
  });
});

describe("openEditModal: strategy load + silent discovery (stage-2)", () => {
  beforeEach(() => {
    withProviderModalDom();
    window.aigate.wireProvTabs();
  });

  // default_model stays empty on purpose: the combobox filters its panel by
  // the typed value, so a seed text would hide the discovered options.
  const baseProvider = {
    id: "p1", name: "ACME", type: "openai-compatible",
    base_url: "", api_key: "", default_model: "", enabled: true,
    custom_headers: {}, models: [{ model_id: "old1", model_name: "Old" }],
    fallback_strategy: "round-robin", sticky_round_robin_limit: 5
  };

  it("fills the strategy fields, enables the Accounts tab, loads accounts", async () => {
    const calls = stubEditModalApi({
      provider: baseProvider,
      discover: { ok: true, models: [] },
      accounts: { object: "list", data: [] }
    });

    window.aigate.openEditModal("p1");
    await flush();

    expect(document.getElementById("provStrategy").value).toBe("round-robin");
    expect(document.getElementById("provStickyLimit").value).toBe("5");
    expect(document.getElementById("provStickyRow").hidden).toBe(false);
    expect(document.getElementById("provStickyLimit").disabled).toBe(false);
    expect(document.getElementById("provTabAccounts").hasAttribute("aria-disabled")).toBe(false);
    expect(document.getElementById("provTabHint").hidden).toBe(true);
    // Accounts moved into the modal -> editing a provider fetches its list.
    expect(calls.some((c) => c.url.indexOf("/api/accounts?provider_id=p1") === 0)).toBe(true);
    vi.unstubAllGlobals();
  });

  it("POSTs /discover silently: combobox fed, NO status text, no model table", async () => {
    const calls = stubEditModalApi({
      provider: baseProvider,
      discover: { ok: true, models: [{ model_id: "gpt-4", model_name: "GPT-4" }] },
      accounts: { object: "list", data: [] }
    });

    window.aigate.openEditModal("p1");
    await flush();
    await flush(); // let the silent discovery + list refresh land

    const disc = calls.find((c) => c.method === "POST" && c.url === "/api/providers/p1/discover");
    expect(disc, "discovery still runs — just without the button").toBeTruthy();
    // The fresh list replaced the DTO-seeded options in the combobox panel.
    expect(provModelOptionValues()).toEqual(["gpt-4"]);
    // Silent: no status chatter anywhere, and the shipped page has no table.
    expect(document.getElementById("provMsg").textContent).toBe("");
    expect(document.getElementById("provModalMsg").textContent).toBe("");
    expect(document.getElementById("provModelsBody")).toBeNull();
    expect(document.getElementById("provModelsTable")).toBeNull();
    vi.unstubAllGlobals();
  });

  it("a FAILED silent discovery stays invisible and never blocks the form", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      // Only the silent discovery fails; the form's own GET stays healthy.
      if (method === "POST" && String(url).indexOf("/discover") !== -1) {
        return Promise.reject(new Error("network down"));
      }
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve(
          String(url) === "/api/providers/p1"
            ? { ...baseProvider, fallback_strategy: "fill-first" }
            : { data: [] }
        )
      });
    }));

    window.aigate.openEditModal("p1");
    await flush();
    await flush();

    expect(document.getElementById("provMsg").textContent).toBe(""); // silent
    expect(document.getElementById("provModal").hidden).toBe(false); // form open
    expect(document.getElementById("provName").value).toBe("ACME"); // fields intact
    // Not swallowed though (R12): the console keeps the reason.
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
    vi.unstubAllGlobals();
  });

  it("fill-first from the DTO hides + disables the sticky row even with a stored limit", async () => {
    stubEditModalApi({
      provider: { ...baseProvider, fallback_strategy: "fill-first", sticky_round_robin_limit: 9 },
      discover: { ok: true, models: [] },
      accounts: { object: "list", data: [] }
    });

    window.aigate.openEditModal("p1");
    await flush();

    expect(document.getElementById("provStrategy").value).toBe("fill-first");
    expect(document.getElementById("provStickyRow").hidden).toBe(true);
    expect(document.getElementById("provStickyLimit").disabled).toBe(true);
    vi.unstubAllGlobals();
  });

  it("a stale silent discovery cannot overwrite a newer provider's options", async () => {
    // p1's discover resolves late; meanwhile p2's modal load + discover land.
    let resolveP1;
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      calls.push({ url: String(url), method });
      if (String(url) === "/api/providers/p1") {
        return Promise.resolve({ ok: true, headers: { get: () => "application/json" },
          json: () => Promise.resolve({ ...baseProvider, id: "p1", name: "ONE" }) });
      }
      if (String(url) === "/api/providers/p2") {
        return Promise.resolve({ ok: true, headers: { get: () => "application/json" },
          json: () => Promise.resolve({ ...baseProvider, id: "p2", name: "TWO" }) });
      }
      if (String(url) === "/api/providers/p1/discover") {
        return new Promise((res) => {
          resolveP1 = () => res({ ok: true, headers: { get: () => "application/json" },
            json: () => Promise.resolve({ ok: true, models: [{ model_id: "p1-model", model_name: "P1" }] }) });
        });
      }
      if (String(url) === "/api/providers/p2/discover") {
        return Promise.resolve({ ok: true, headers: { get: () => "application/json" },
          json: () => Promise.resolve({ ok: true, models: [{ model_id: "p2-model", model_name: "P2" }] }) });
      }
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ data: [], object: "list" }) });
    }));

    window.aigate.openEditModal("p1");
    await flush(); // p1 discover is in flight, unresolved
    window.aigate.openEditModal("p2");
    await flush();
    await flush(); // p2's discovery landed
    expect(provModelOptionValues()).toEqual(["p2-model"]);
    resolveP1(); // the late p1 response must now be DISCARDED
    await flush();
    await flush();
    expect(provModelOptionValues()).toEqual(["p2-model"]);
    expect(document.getElementById("provName").value).toBe("TWO");
    vi.unstubAllGlobals();
  });
});

describe("discoverModels — legacy visible path (export kept, stage-2)", () => {
  beforeEach(() => { withDetailDom(); });

  it("fills the #provModel combobox panel with discovered model_ids (sorted)", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(
        url.indexOf("/discover") !== -1
          ? { ok: true, models: [
              { model_id: "gpt-4", model_name: "GPT-4" },
              { model_id: "gpt-3.5", model_name: "GPT-3.5" }
            ] }
          : { id: "p1", name: "ACME", models: [] }
      )
    })));

    window.aigate.discoverModels("p1");
    await flush();

    // The combobox panel offers the discovered ids, sorted by name:
    // GPT-3.5 < GPT-4. NOT a <datalist> (Android never pops one).
    expect(provModelOptionValues()).toEqual(["gpt-3.5", "gpt-4"]);
    expect(document.getElementById("provModelList").tagName).toBe("UL");
    expect(document.getElementById("provModel").getAttribute("role")).toBe("combobox");
    // Loading cleared once the fetch landed (field usable again).
    expect(document.getElementById("provModel").disabled).toBe(false);
    expect(document.getElementById("provModel").getAttribute("aria-busy")).toBe("false");
    vi.unstubAllGlobals();
  });

  it("shows the loading state on the combobox while the fetch is in flight", async () => {
    let resolveDisc;
    const gate = new Promise((r) => { resolveDisc = r; });
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).indexOf("/discover") !== -1) return gate;
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ id: "p1", name: "ACME", models: [] })
      });
    }));

    window.aigate.discoverModels("p1");
    // Synchronously (before the fetch resolves): input locked + loading row.
    expect(document.getElementById("provModel").disabled).toBe(true);
    expect(document.getElementById("provModel").getAttribute("aria-busy")).toBe("true");
    expect(document.getElementById("provModelList").textContent)
      .toContain(window.I18N.en["combobox.loading"]);

    resolveDisc({
      ok: true, headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true, models: [{ model_id: "m1", model_name: "M1" }] })
    });
    await flush();
    expect(document.getElementById("provModel").disabled).toBe(false);
    expect(document.getElementById("provModelList").textContent)
      .not.toContain(window.I18N.en["combobox.loading"]);
    vi.unstubAllGlobals();
  });
});

describe("index.html wires #provModel as a combobox (mobile fix)", () => {
  const doc = indexDocument();

  it("provModel is a role=combobox input + a <ul role=listbox> panel, no datalist", () => {
    const inp = doc.getElementById("provModel");
    expect(inp.tagName).toBe("INPUT");
    expect(inp.getAttribute("role")).toBe("combobox");
    expect(inp.getAttribute("aria-controls")).toBe("provModelList");
    expect(inp.getAttribute("list")).toBeNull();
    const ul = doc.getElementById("provModelList");
    expect(ul.tagName).toBe("UL");
    expect(ul.getAttribute("role")).toBe("listbox");
    expect(ul.hasAttribute("hidden")).toBe(true);
    expect(doc.querySelector("datalist")).toBeNull();
  });
});
