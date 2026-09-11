import { describe, it, expect, vi, beforeEach } from "vitest";
import { indexDocument, indexHtml, staticSource } from "./helpers/dom.js";

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

// The provider modal as stage-3 ships it: PROFILE ONLY (no tablist, no accounts
// panel, no strategy controls) + the discovery status line under the model
// combobox. #provModel is a searchable COMBOBOX: a text input + a custom <ul>
// panel (NOT <datalist>).
function withProviderModalDom() {
  document.body.innerHTML =
    '<div id="provModal">' +
      '<h3 id="provModalTitle"></h3>' +
      '<form id="provForm">' +
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
        '<p class="pd-status" id="provModalModelStatus" role="status" aria-live="polite"></p>' +
        '<input type="checkbox" id="provEnabled" />' +
        '<div class="form-row form-row-stack">' +
          '<div id="provHeaders"></div>' +
          '<button type="button" id="provAddHeaderBtn"></button>' +
        '</div>' +
        '<p id="provModalMsg"></p>' +
        '<button type="button" id="provTestBtn">Test Connection</button>' +
        '<button type="submit" id="provSaveBtn"></button>' +
        '<button type="button" id="provCancel"></button>' +
      '</form>' +
      '<p id="provMsg"></p>' +
    '</div>';
  window.applyLocale("en");
}

// The DETAIL PAGE DOM (stage-3): one column of cards. Kept minimal but real:
// the head, Kartu A/B/C containers.
function withDetailDom() {
  document.body.innerHTML =
    '<nav><a class="nav-item" data-view="providers" href="#"></a></nav>' +
    '<section class="view is-active" data-view="providers">' +
      '<table><tbody id="provTableBody"></tbody></table>' +
      '<p id="provMsg"></p>' +
    '</section>' +
    '<section class="view" data-view="provider-detail">' +
      '<h2 id="provDetailTitle"></h2><span id="provDetailBadge" hidden></span>' +
      '<button id="provDetailBackBtn"></button>' +
      '<dl><dd id="pdType"></dd><dd id="pdBaseUrl" class="pd-clip"></dd>' +
        '<dd id="pdDefaultModel"></dd><dd id="pdApiKey" class="pd-clip"></dd>' +
        '<dd id="pdHeaders"></dd><dd id="pdModels"></dd></dl>' +
      '<p class="pd-status" id="pdModelStatus"></p>' +
      '<select id="pdStrategy">' +
        '<option value="fill-first">Fill first</option>' +
        '<option value="round-robin">Round-robin</option>' +
      '</select>' +
      '<div id="pdStickyRow" hidden><input type="number" id="pdStickyLimit" min="1" value="3" /></div>' +
      '<p id="pdStrategyMsg"></p>' +
      '<p id="accountsMsg"></p><div id="accList"></div>' +
    '</section>' +
    '<div class="aigate-combo">' +
      '<input type="text" id="provModel" role="combobox" />' +
      '<ul id="provModelList" role="listbox" hidden></ul>' +
    '</div>';
  window.applyLocale("en");
  window.aigate.wireProviderUi();
}

// The combobox panel's rendered option values (model ids), in DOM order.
const provModelOptionValues = () => Array.from(
  document.getElementById("provModelList").querySelectorAll('li[role="option"]')
).map((li) => li.getAttribute("data-value"));

// Minimal fetch router for the openEditModal flow: answers the provider GET,
// the background POST /discover and the list refresh.
function stubEditModalApi({ provider, discover }) {
  const calls = [];
  vi.stubGlobal("fetch", vi.fn((url, opts) => {
    const method = (opts && opts.method) || "GET";
    calls.push({ url: String(url), method, body: opts && opts.body });
    let payload = { data: [] };
    if (method === "POST" && String(url).indexOf("/discover") !== -1) payload = discover;
    else if (String(url) === "/api/providers/p1") payload = provider;
    else if (String(url) === "/api/providers/p2") payload = { ...provider, id: "p2", name: "TWO" };
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
    window.aigate.wireProviderUi();
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

describe("saveProvider sends PROFILE fields only (B2.2 / stage-3)", () => {
  beforeEach(() => { withProviderModalDom(); });

  it("includes default_model in the POST body (add mode)", async () => {
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
    // sanity: other fields still present
    expect(body.name).toBe("ACME");
    expect(body.api_key).toBe("sk-acme");
    vi.unstubAllGlobals();
  });

  // The point of stage-3: the profile save must NOT carry the routing fields,
  // or it would silently overwrite whatever Kartu B just stored.
  it("never sends fallback_strategy / sticky_round_robin_limit (PUT on edit)", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url, opts });
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve({ data: [] })
      });
    }));

    document.getElementById("provId").value = "p1"; // edit -> PUT
    document.getElementById("provName").value = "ACME";
    window.aigate.saveProvider();
    await flush();

    const put = calls.find((c) => c.url === "/api/providers/p1" && c.opts.method === "PUT");
    expect(put).toBeTruthy();
    const body = JSON.parse(put.opts.body);
    expect(body).not.toHaveProperty("fallback_strategy");
    expect(body).not.toHaveProperty("sticky_round_robin_limit");
    vi.unstubAllGlobals();
  });

  it("closes the modal and refreshes the list on success", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true, headers: { get: () => "application/json" },
      json: () => Promise.resolve({ data: [] })
    })));
    document.getElementById("provId").value = "";
    document.getElementById("provModal").hidden = false;
    window.aigate.saveProvider();
    await flush();
    await flush();
    expect(document.getElementById("provModal").hidden).toBe(true);
    vi.unstubAllGlobals();
  });
});

describe("provider modal — index.html structure (stage-3, profile only)", () => {
  const doc = indexDocument();
  const html = indexHtml();

  it("has no tablist, no hint and no accounts panel any more", () => {
    const modal = doc.getElementById("provModal");
    expect(modal.querySelector('[role="tablist"]')).toBeNull();
    expect(modal.querySelector('[role="tab"]')).toBeNull();
    expect(modal.querySelector('[role="tabpanel"]')).toBeNull();
    ["provTabList", "provTabProvider", "provTabAccounts", "provTabHint",
      "provPanelAccounts", "provPanelProvider"].forEach((id) => {
      expect(doc.getElementById(id), id).toBeNull();
    });
    // No accounts UI inside the provider modal: it has its own modal + page.
    expect(modal.querySelector("#accLabel")).toBeNull();
    expect(modal.querySelector("#accountsTable")).toBeNull();
    expect(modal.querySelector("#provConnectOAuthBtn")).toBeNull();
    expect(doc.getElementById("accModal")).not.toBeNull();
  });

  it("carries no strategy fields (they belong to Kartu B of the detail page)", () => {
    expect(doc.getElementById("provStrategy")).toBeNull();
    expect(doc.getElementById("provStickyRow")).toBeNull();
    expect(doc.getElementById("provStickyLimit")).toBeNull();
    expect(html).not.toMatch(/name="fallback_strategy"/);
    expect(html).not.toMatch(/name="sticky_round_robin_limit"/);
    // The detail page owns them instead, with the exact contract enum.
    const sel = doc.getElementById("pdStrategy");
    expect(Array.from(sel.querySelectorAll("option")).map((o) => o.getAttribute("value")))
      .toEqual(["fill-first", "round-robin"]);
    const lim = doc.getElementById("pdStickyLimit");
    expect(lim.getAttribute("type")).toBe("number");
    expect(lim.getAttribute("min")).toBe("1");
    expect(doc.getElementById("pdStickyRow").hasAttribute("hidden")).toBe(true);
  });

  it("the discovery UI is still not a table, but it is no longer mute", () => {
    expect(doc.getElementById("provModelsTable")).toBeNull();
    expect(doc.getElementById("provModelsBody")).toBeNull();
    expect(doc.getElementById("provDiscoverBtn")).toBeNull();
    expect(doc.getElementById("provModelMsg")).toBeNull();
    expect(html).not.toContain('providers.discover"'); // no binding left in markup
    // stage-3: one status paragraph under the combobox + one in Kartu A.
    const status = doc.getElementById("provModalModelStatus");
    expect(status.tagName).toBe("P");
    expect(status.getAttribute("role")).toBe("status");
    expect(doc.getElementById("pdModelStatus")).not.toBeNull();
  });

  it("the add-account form is a modal with the contract's priority input", () => {
    const pr = doc.getElementById("accPriority");
    expect(pr.getAttribute("type")).toBe("number");
    expect(pr.getAttribute("min")).toBe("0");
    expect(doc.getElementById("accAuthType")).not.toBeNull();
    expect(doc.getElementById("accApiKey")).not.toBeNull();
    // One surface per job: the modal has no table, the page has no inline form.
    expect(doc.getElementById("accModal").querySelector("table")).toBeNull();
  });

  it("the Models column explains where its number comes from", async () => {
    // The cell is rendered by app.js (the rows are built in JS), so the tooltip
    // contract lives there + in the dictionary.
    const appSrc = staticSource("app.js");
    // The Models cell carries BOTH a title and an aria-label built from the key.
    expect(appSrc).toMatch(/class="prov-models"[^\n]*title[^\n]*aria-label/);
    expect(appSrc).toContain('var modelsHint = escapeHtml(getStr("providers.models_hint"))');
    expect(window.I18N.en["providers.models_hint"]).toBeTruthy();
  });
});

describe("openEditModal: profile load + background discovery (stage-3)", () => {
  beforeEach(() => {
    withProviderModalDom();
  });

  // default_model stays empty on purpose: the combobox filters its panel by
  // the typed value, so a seed text would hide the discovered options.
  const baseProvider = {
    id: "p1", name: "ACME", type: "openai-compatible",
    base_url: "", api_key: "", default_model: "", enabled: true,
    custom_headers: {}, models: [{ model_id: "old1", model_name: "Old" }],
    fallback_strategy: "round-robin", sticky_round_robin_limit: 5
  };

  it("fills the profile fields and opens the modal", async () => {
    stubEditModalApi({ provider: baseProvider, discover: { ok: true, models: [] } });
    window.aigate.openEditModal("p1");
    await flush();

    expect(document.getElementById("provName").value).toBe("ACME");
    expect(document.getElementById("provModal").hidden).toBe(false);
    expect(document.getElementById("provModalTitle").textContent).toBe("Edit Provider");
    vi.unstubAllGlobals();
  });

  it("POSTs /discover in the background: combobox fed + a status line, no table", async () => {
    let resolveDisc;
    const gate = new Promise((r) => { resolveDisc = r; });
    const calls = [];
    const answer = (payload) => Promise.resolve({
      ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve(payload)
    });
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      calls.push({ url: String(url), method, body: opts && opts.body });
      if (method === "POST" && String(url).indexOf("/discover") !== -1) return gate;
      if (String(url) === "/api/providers/p1") return answer(baseProvider);
      return answer({ data: [] });
    }));

    window.aigate.openEditModal("p1");
    await flush(); // the GET landed; the discovery POST is now in flight
    const status = document.getElementById("provModalModelStatus");
    expect(status.textContent).toBe("Discovering models…"); // not mute while waiting
    expect(document.getElementById("provModel").disabled).toBe(false); // never blocks
    resolveDisc({
      ok: true, headers: { get: () => "application/json" },
      json: () => Promise.resolve({ ok: true, models: [{ model_id: "gpt-4", model_name: "GPT-4" }] })
    });
    await flush(); // let the discovery + list refresh land

    const disc = calls.find((c) => c.method === "POST" && c.url === "/api/providers/p1/discover");
    expect(disc, "discovery still runs — just without a button").toBeTruthy();
    // The fresh list replaced the DTO-seeded options in the combobox panel.
    expect(provModelOptionValues()).toEqual(["gpt-4"]);
    expect(status.textContent).toContain("Models discovered");
    expect(status.textContent).toContain("(1)");
    // Nothing anywhere pretends to be a model table.
    expect(status.querySelector("table")).toBeNull();
    expect(document.getElementById("provModelsBody")).toBeNull();
    // The provider list message stays clean: discovery is not a form error.
    expect(document.getElementById("provMsg").textContent).toBe("");
    expect(document.getElementById("provModalMsg").textContent).toBe("");
    vi.unstubAllGlobals();
  });

  it("a FAILED discovery shows a text hint, keeps the form open and warns", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
      // Only the background discovery fails; the form's own GET stays healthy.
      if (method === "POST" && String(url).indexOf("/discover") !== -1) {
        return Promise.reject(new Error("network down"));
      }
      return Promise.resolve({
        ok: true, headers: { get: () => "application/json" },
        json: () => Promise.resolve(
          String(url) === "/api/providers/p1" ? baseProvider : { data: [] }
        )
      });
    }));

    window.aigate.openEditModal("p1");
    await flush();
    await flush();

    const status = document.getElementById("provModalModelStatus");
    expect(status.textContent).toContain("Model list could not be fetched");
    expect(status.textContent).not.toMatch(/<table/);
    expect(document.getElementById("provModal").hidden).toBe(false); // form open
    expect(document.getElementById("provName").value).toBe("ACME"); // fields intact
    expect(document.getElementById("provModalMsg").textContent).toBe(""); // not blocked
    // Not swallowed though (R12): the console keeps the reason.
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
    vi.unstubAllGlobals();
  });

  it("a stale discovery cannot overwrite a newer provider's options", async () => {
    // p1's discover resolves late; meanwhile p2's modal load + discover land.
    let resolveP1;
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const method = (opts && opts.method) || "GET";
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
    // ...and the discarded answer never rewrote the status line either.
    expect(document.getElementById("provModalModelStatus").textContent)
      .toContain("Models discovered (1)");
    vi.unstubAllGlobals();
  });
});

describe("discoverModels — legacy visible path (export kept)", () => {
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
