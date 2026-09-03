import { describe, it, expect, vi, beforeEach } from "vitest";

// i18n.js attaches window.I18N + window.applyLocale (jsdom provides DOM).
import "../static/i18n.js";
// app.js wires the UI and exposes window.aigate.mapProviderToRow /
// window.aigate.buildHeadersDict / window.aigate.headersToRows.
import "../static/app.js";

// Let async .then chains (fetchJson / testProviderConnection) resolve.
const flush = () => new Promise((r) => setTimeout(r, 0));

// Build the provider add/edit modal DOM the functions expect.
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
        '<input id="provModel" />' +
        '<input type="checkbox" id="provEnabled" />' +
        '<div id="provHeaders"></div>' +
      '</form>' +
      '<button type="button" id="provTestBtn">Test Connection</button>' +
      '<p id="provModalMsg"></p>' +
      '<p id="provMsg"></p>' +
    '</div>';
}

// Build the detail/datalist DOM discoverModels() + populateModelDatalist() use.
function withDetailDom() {
  document.body.innerHTML =
    '<div id="provDetail">' +
      '<h3 id="provDetailTitle"></h3>' +
      '<p id="provModelMsg"></p>' +
      '<tbody id="provModelsBody"></tbody>' +
    '</div>' +
    '<datalist id="provModelList"></datalist>' +
    '<p id="provMsg"></p>';
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

describe("saveProvider persists default_model (B2.2)", () => {
  beforeEach(() => { withProviderModalDom(); });

  it("includes default_model in the POST/PUT body", async () => {
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
});

describe("discoverModels populates the Model datalist (B2.2)", () => {
  beforeEach(() => { withDetailDom(); });

  it("fills #provModelList with discovered model_ids", async () => {
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

    const opts = Array.from(document.getElementById("provModelList").options)
      .map((o) => o.value);
    expect(opts).toContain("gpt-4");
    expect(opts).toContain("gpt-3.5");
    vi.unstubAllGlobals();
  });
});
