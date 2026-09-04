import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { JSDOM } from "jsdom";

// i18n dict (window.I18N) so getStr() resolves labels during render.
import "../static/i18n.js";
// app.js exposes window.aigate.fetchJson / escapeHtml / getStr used by the module.
import "../static/app.js";
// The Combos module registers window.aigate.combos and wires its DOM (guarded).
import "../static/combos.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

function withDom() {
  document.body.innerHTML =
    '<p id="comboMsg"></p>' +
    '<table id="comboTable"><tbody id="comboTableBody"></tbody></table>';
}

// Build the combo modal DOM (mirrors index.html #comboModal) incl. the
// members editor section, so the members helpers can be driven in tests.
// Structure mirrors the labeled add-member grid: each field wrapped in a
// .combo-member-field with a visible <label for=...>. Element ids unchanged.
function withComboModalDom() {
  withDom();
  document.body.innerHTML +=
    '<div id="comboModal">' +
      '<h3 id="comboModalTitle"></h3>' +
      '<form id="comboForm">' +
        '<input type="hidden" id="comboId" />' +
        '<input id="comboName" />' +
        '<select id="comboStrategy">' +
          '<option value="fallback">fallback</option>' +
          '<option value="load_balance">load_balance</option>' +
          '<option value="latency_cost">latency_cost</option>' +
          '<option value="three_tier">three_tier</option>' +
        '</select>' +
        '<input type="checkbox" id="comboEnabled" />' +
        '<p id="comboMemberMsg"></p>' +
        '<table id="comboMembersTable"><tbody id="comboMembersBody"></tbody></table>' +
        '<div class="combo-member-form" id="comboMemberForm">' +
          '<div class="combo-member-fields">' +
            '<div class="combo-member-field">' +
              '<label class="form-label" for="comboMemberProvider" data-i18n="combos.member.provider">Provider</label>' +
              '<select id="comboMemberProvider"></select>' +
            '</div>' +
            '<div class="combo-member-field">' +
              '<label class="form-label" for="comboMemberModel" data-i18n="combos.member.model">Model</label>' +
              '<div class="combo-model-control">' +
                '<input id="comboMemberModel" list="comboMemberModelList" />' +
                '<span class="combo-model-spinner" id="comboMemberModelSpinner" hidden aria-hidden="true"></span>' +
              '</div>' +
              '<datalist id="comboMemberModelList"></datalist>' +
            '</div>' +
            '<div class="combo-member-field">' +
              '<label class="form-label" for="comboMemberPriority" data-i18n="combos.member.priority">Priority</label>' +
              '<input type="number" id="comboMemberPriority" value="0" />' +
            '</div>' +
            '<div class="combo-member-field">' +
              '<label class="form-label" for="comboMemberWeight" data-i18n="combos.member.weight">Weight</label>' +
              '<input type="number" id="comboMemberWeight" value="1" step="0.1" />' +
            '</div>' +
          '</div>' +
          '<div class="combo-member-actions">' +
            '<button type="button" id="comboMemberAddBtn">Add member</button>' +
            '<button type="button" id="comboMemberCancelEdit" hidden>Cancel edit</button>' +
          '</div>' +
        '</div>' +
      '</form>' +
    '</div>';
}

const jsonResponse = (payload) => Promise.resolve({
  ok: true,
  headers: { get: () => "application/json" },
  json: () => Promise.resolve(payload)
});

// Sample GET /api/providers payload (mirrors providers_router ModelDTO shape).
function sampleProviders() {
  return {
    object: "list",
    data: [
      {
        id: 1, name: "OpenRouter", type: "openai-compatible",
        models: [
          { id: 11, model_id: "llama-3.1", model_name: "Llama 3.1", capabilities: "" },
          { id: 12, model_id: "gpt-4o", model_name: "GPT-4o", capabilities: "" }
        ]
      },
      { id: 2, name: "Ollama", type: "openai-compatible", models: [] }
    ]
  };
}

// Sample GET /api/combos/5 payload with two members.
function sampleCombo(members) {
  return {
    id: 5, name: "Route", strategy: "three_tier", enabled: true,
    members: members === undefined
      ? [
          { id: 7, combo_id: 5, provider_id: 1, provider_model: "llama-3.1", priority: 0, weight: 1 },
          { id: 8, combo_id: 5, provider_id: 2, provider_model: "qwen", priority: 1, weight: 0.5 }
        ]
      : members
  };
}

describe("combos mapper + render (B2.4)", () => {
  beforeEach(() => { withDom(); });

  it("mapComboToRow flattens a ComboDTO", () => {
    const row = window.aigate.combos.mapComboToRow({
      id: 7, name: "X", strategy: "latency_cost", enabled: false, members: [1, 2]
    });
    expect(row).toEqual({
      id: 7, name: "X", strategy: "latency_cost", enabled: false, memberCount: 2
    });
  });

  it("mapComboToRow tolerates missing fields", () => {
    const row = window.aigate.combos.mapComboToRow({});
    expect(row).toEqual({
      id: undefined, name: undefined, strategy: undefined,
      enabled: false, memberCount: 0
    });
  });

  it("renderCombos fills the table body and escapes data", () => {
    window.aigate.combos.renderCombos([
      { id: 1, name: "Alpha <x>", strategy: "fallback", enabled: true, members: [] }
    ]);
    const html = document.getElementById("comboTableBody").innerHTML;
    expect(html).toContain("Alpha &lt;x&gt;");
    expect(html).toContain('data-id="1"');
    expect(html).toContain("js-edit");
    expect(html).toContain("js-del");
  });

  it("renderCombos shows the empty-state message when there are no items", () => {
    window.aigate.combos.renderCombos([]);
    expect(document.getElementById("comboTableBody").innerHTML)
      .toContain("No combos yet.");
  });

  it("loadCombos fetches /api/combos and renders rows", async () => {
    const data = {
      object: "list",
      data: [{ id: 2, name: "B", strategy: "load_balance", enabled: true, members: [{}, {}] }]
    };
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(data)
    })));
    await window.aigate.combos.loadCombos();
    const html = document.getElementById("comboTableBody").innerHTML;
    expect(html).toContain("B");
    expect(html).toContain("2"); // member count
    vi.unstubAllGlobals();
  });
});

describe("combos members — renderMembers", () => {
  beforeEach(() => { withComboModalDom(); });

  it("renders one row per member with provider NAME (not id) + model + priority + weight", () => {
    window.aigate.combos.renderMembers(sampleCombo().members, {
      1: { id: 1, name: "OpenRouter" },
      2: { id: 2, name: "Ollama" }
    });
    const body = document.getElementById("comboMembersBody");
    expect(body.querySelectorAll("tr.member-row").length).toBe(2);
    const html = body.innerHTML;
    expect(html).toContain("OpenRouter");   // provider NAME, not raw id
    expect(html).toContain("Ollama");
    expect(html).toContain("llama-3.1");    // model
    expect(html).toContain("qwen");
    expect(html).toContain(">0<");          // priority
    expect(html).toContain(">0.5<");        // weight
    expect(html).toContain("js-mem-edit");
    expect(html).toContain("js-mem-del");
    expect(html).toContain('data-id="7"');
  });

  it("escapes member data (no raw HTML injection)", () => {
    window.aigate.combos.renderMembers(
      [{ id: 1, provider_id: 9, provider_model: "<img src=x>", priority: 0, weight: 1 }],
      {}
    );
    const html = document.getElementById("comboMembersBody").innerHTML;
    expect(html).toContain("&lt;img src=x&gt;");
    expect(html).not.toContain("<img src=x>");
    // Unknown provider id -> fallback label, never "undefined".
    expect(html).toContain("#9");
    expect(html).not.toContain("undefined");
  });

  it("shows the empty-state message when there are no members", () => {
    window.aigate.combos.renderMembers([], {});
    expect(document.getElementById("comboMembersBody").innerHTML)
      .toContain("No members yet.");
  });
});

describe("combos members — provider/model dropdown chaining", () => {
  beforeEach(() => { withComboModalDom(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("loadProviders populates the provider select from GET /api/providers", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({});
    }));
    await window.aigate.combos.loadProviders();
    const opts = Array.from(
      document.getElementById("comboMemberProvider").querySelectorAll("option")
    ).map((o) => o.value);
    expect(opts).toEqual(["", "1", "2"]);
  });

  it("populateModelOptions fills the model datalist from the chosen provider's models", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({});
    }));
    await window.aigate.combos.loadProviders();
    const models = window.aigate.combos.populateModelOptions(1);
    // Cached models are now sorted by name (case-insensitive): GPT-4o < Llama 3.1.
    expect(models.map((m) => m.model_id)).toEqual(["gpt-4o", "llama-3.1"]);
    const dl = document.getElementById("comboMemberModelList").innerHTML;
    expect(dl).toContain('value="llama-3.1"');
    expect(dl).toContain('value="gpt-4o"');
    // Provider with no discovered models -> empty options, free-text still allowed.
    expect(window.aigate.combos.populateModelOptions(2)).toEqual([]);
    expect(document.getElementById("comboMemberModelList").innerHTML).toBe("");
  });
});

describe("combos members — auto model fetch on provider change", () => {
  beforeEach(() => { withComboModalDom(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  // Flush pending microtasks (fetchJson chains .then/.catch) to completion.
  const tick = () => new Promise((r) => setTimeout(r, 0));
  // A 200 JSON response (discover always returns HTTP 200, even on ok:false).
  const body = (payload) => Promise.resolve({
    ok: true, headers: { get: () => "application/json" },
    json: () => Promise.resolve(payload)
  });
  const dlValues = () => Array.from(
    document.getElementById("comboMemberModelList").querySelectorAll("option")
  ).map((o) => o.getAttribute("value"));

  it("changing the provider POSTs /api/providers/<id>/discover", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const u = String(url);
      calls.push({ url: u, method: opts && opts.method });
      if (u === "/api/providers") return jsonResponse(sampleProviders());
      if (u === "/api/providers/1/discover") return body({ ok: true, models: [] });
      return body({});
    }));
    await window.aigate.combos.loadProviders();
    const sel = document.getElementById("comboMemberProvider");
    sel.value = "1";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    await tick();
    const disc = calls.find((c) => c.url === "/api/providers/1/discover" && c.method === "POST");
    expect(disc).toBeTruthy();
  });

  it("discover models are sorted by name (case-insensitive) in the datalist", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      const u = String(url);
      if (u === "/api/providers") return jsonResponse(sampleProviders());
      if (u === "/api/providers/1/discover") {
        return body({ ok: true, models: [
          { id: 1, model_id: "zeta", model_name: "Zeta" },
          { id: 2, model_id: "Alpha", model_name: "alpha" },
          { id: 3, model_id: "mid", model_name: "Mid" }
        ] });
      }
      return body({});
    }));
    await window.aigate.combos.loadProviders();
    const models = await window.aigate.combos.fetchModelsForProvider(1);
    // Sort key = model_name (lowercased): alpha < Mid < Zeta.
    expect(models.map((m) => m.model_id)).toEqual(["Alpha", "mid", "zeta"]);
    expect(dlValues()).toEqual(["Alpha", "mid", "zeta"]);
  });

  it("loading state is applied first, then cleared after the fetch resolves", async () => {
    let resolveDisc;
    const gate = new Promise((r) => { resolveDisc = r; });
    vi.stubGlobal("fetch", vi.fn((url) => {
      const u = String(url);
      if (u === "/api/providers") return jsonResponse(sampleProviders());
      if (u === "/api/providers/1/discover") return gate.then(() => body({ ok: true, models: [] }));
      return body({});
    }));
    await window.aigate.combos.loadProviders();
    const mo = document.getElementById("comboMemberModel");
    const add = document.getElementById("comboMemberAddBtn");
    const form = document.getElementById("comboMemberForm");
    const spinner = document.getElementById("comboMemberModelSpinner");

    const pr = window.aigate.combos.fetchModelsForProvider(1);
    // Applied synchronously, BEFORE the fetch resolves:
    expect(mo.disabled).toBe(true);
    expect(add.disabled).toBe(true);
    expect(form.getAttribute("aria-busy")).toBe("true");
    expect(spinner.hidden).toBe(false);
    expect(mo.placeholder).toBe(window.I18N.en["combos.member.loading"]);

    resolveDisc();
    await pr;
    // Cleared after resolve:
    expect(mo.disabled).toBe(false);
    expect(add.disabled).toBe(false);
    expect(form.getAttribute("aria-busy")).toBe("false");
    expect(spinner.hidden).toBe(true);
    expect(mo.placeholder).toBe(window.I18N.en["combos.member.model_ph"]);
  });

  it("discover {ok:false} falls back to cached models (sorted) + load_failed note", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      const u = String(url);
      if (u === "/api/providers") return jsonResponse(sampleProviders());
      if (u === "/api/providers/1/discover") return body({ ok: false, error: "no network" });
      return body({});
    }));
    await window.aigate.combos.loadProviders();
    const models = await window.aigate.combos.fetchModelsForProvider(1);
    // provider 1 cached: Llama 3.1 + GPT-4o -> sorted by name: GPT-4o, Llama 3.1.
    expect(models.map((m) => m.model_id)).toEqual(["gpt-4o", "llama-3.1"]);
    expect(dlValues()).toEqual(["gpt-4o", "llama-3.1"]);
    const msg = document.getElementById("comboMemberMsg");
    expect(msg.textContent).toContain(window.I18N.en["combos.member.load_failed"]);
    expect(msg.className).toContain("settings-msg-warn");
    // Loading cleared even on the fallback path (field usable again).
    expect(document.getElementById("comboMemberModel").disabled).toBe(false);
  });

  it("race guard: only the latest provider fetch is applied (stale ignored)", async () => {
    let resolveA, resolveB;
    const gateA = new Promise((r) => { resolveA = r; });
    const gateB = new Promise((r) => { resolveB = r; });
    vi.stubGlobal("fetch", vi.fn((url) => {
      const u = String(url);
      if (u === "/api/providers") return jsonResponse(sampleProviders());
      if (u === "/api/providers/1/discover") {
        return gateA.then(() => body({ ok: true, models: [{ id: 1, model_id: "stale-a", model_name: "Stale A" }] }));
      }
      if (u === "/api/providers/2/discover") {
        return gateB.then(() => body({ ok: true, models: [{ id: 2, model_id: "fresh-b", model_name: "Fresh B" }] }));
      }
      return body({});
    }));
    await window.aigate.combos.loadProviders();
    const sel = document.getElementById("comboMemberProvider");
    sel.value = "1"; sel.dispatchEvent(new Event("change", { bubbles: true })); // seq 1 (will be stale)
    sel.value = "2"; sel.dispatchEvent(new Event("change", { bubbles: true })); // seq 2 (latest)
    resolveB();          // latest resolves FIRST
    await tick();
    expect(dlValues()).toEqual(["fresh-b"]);
    resolveA();          // stale resolves LATER -> must be ignored
    await tick();
    expect(dlValues()).toEqual(["fresh-b"]); // unchanged by the stale response
    expect(document.getElementById("comboMemberModel").disabled).toBe(false);
  });
});

describe("combos members — NEW combo mode (client-side buffer)", () => {
  beforeEach(() => { withComboModalDom(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  it("bufferMemberLocal + buildMembersPayload returns the array sent on create", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({});
    }));
    await window.aigate.combos.openAddModal();
    expect(window.aigate.combos.getSelectedId()).toBe(null);

    window.aigate.combos.bufferMemberLocal(
      { provider_id: 1, provider_model: "llama-3.1", priority: "0", weight: "1" });
    window.aigate.combos.bufferMemberLocal(
      { provider_id: 2, provider_model: "qwen", priority: 2, weight: 0.5 });

    expect(window.aigate.combos.buildMembersPayload()).toEqual([
      { provider_id: 1, provider_model: "llama-3.1", priority: 0, weight: 1 },
      { provider_id: 2, provider_model: "qwen", priority: 2, weight: 0.5 }
    ]);
    // Buffer renders in the modal table without any server call.
    expect(document.getElementById("comboMembersBody")
      .querySelectorAll("tr.member-row").length).toBe(2);

    // removeMemberLocal drops the buffered row by index.
    window.aigate.combos.removeMemberLocal(0);
    expect(window.aigate.combos.buildMembersPayload().length).toBe(1);
    expect(window.aigate.combos.buildMembersPayload()[0].provider_id).toBe(2);
  });

  it("Save (create) POSTs name/strategy/enabled + buffered members in one shot", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url: String(url), opts });
      if (String(url) === "/api/combos" && opts && opts.method === "POST") {
        return jsonResponse(sampleCombo([]));
      }
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({ object: "list", data: [] });
    }));
    await window.aigate.combos.openAddModal();
    document.getElementById("comboName").value = "OneShot";
    document.getElementById("comboStrategy").value = "three_tier";
    document.getElementById("comboEnabled").checked = true;
    window.aigate.combos.bufferMemberLocal(
      { provider_id: 1, provider_model: "gpt-4o", priority: 0, weight: 1 });

    window.aigate.combos.saveCombo({ preventDefault: () => {} });
    await new Promise((r) => setTimeout(r, 0));

    const post = calls.find((c) => c.url === "/api/combos" && c.opts.method === "POST");
    expect(post).toBeTruthy();
    expect(JSON.parse(post.opts.body)).toEqual({
      name: "OneShot", strategy: "three_tier", enabled: true,
      members: [{ provider_id: 1, provider_model: "gpt-4o", priority: 0, weight: 1 }]
    });
    // Buffer cleared after a successful create.
    expect(window.aigate.combos.buildMembersPayload()).toEqual([]);
  });
});

describe("combos members — EXISTING combo mode (member endpoints)", () => {
  beforeEach(() => { withComboModalDom(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  // Stub routing every combos/providers endpoint the members editor touches.
  function stubComboApi(members) {
    const calls = [];
    const combo = () => sampleCombo(members === undefined ? sampleCombo().members : members);
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const u = String(url);
      calls.push({ url: u, opts });
      if (u === "/api/providers") return jsonResponse(sampleProviders());
      if (u === "/api/combos/5/members" && opts && opts.method === "POST") {
        return jsonResponse({ id: 9, combo_id: 5, ...JSON.parse(opts.body) });
      }
      if (u.indexOf("/api/combos/5/members/") === 0) {
        if (opts && opts.method === "PUT") {
          return jsonResponse({ id: 7, combo_id: 5, provider_id: 1,
            provider_model: "gpt-4o", priority: 3, weight: 2,
            ...JSON.parse(opts.body) });
        }
        return jsonResponse({ ok: true });
      }
      if (u === "/api/combos/5") return jsonResponse(combo());
      if (u === "/api/combos") return jsonResponse({ object: "list", data: [combo()] });
      return jsonResponse({});
    }));
    return calls;
  }

  it("openEditModal loads the combo and renders its members with provider names", async () => {
    stubComboApi();
    await window.aigate.combos.openEditModal("5");
    expect(window.aigate.combos.getSelectedId()).toBe("5");
    const body = document.getElementById("comboMembersBody").innerHTML;
    expect(body).toContain("OpenRouter");
    expect(body).toContain("Ollama");
    expect(body).toContain("llama-3.1");
  });

  it("addMember POSTs /api/combos/<id>/members with the normalized body, then reloads", async () => {
    const calls = stubComboApi();
    await window.aigate.combos.openEditModal("5");
    await window.aigate.combos.addMember(
      { provider_id: 1, provider_model: "gpt-4o", priority: "2", weight: "0.5" });

    const post = calls.find((c) => c.url === "/api/combos/5/members" && c.opts.method === "POST");
    expect(post).toBeTruthy();
    expect(JSON.parse(post.opts.body)).toEqual(
      { provider_id: 1, provider_model: "gpt-4o", priority: 2, weight: 0.5 });
    // Combo reloaded after the mutation (GET /api/combos/5 again).
    const gets = calls.filter((c) => c.url === "/api/combos/5" && (!c.opts || !c.opts.method));
    expect(gets.length).toBeGreaterThanOrEqual(2);
  });

  it("addMember without provider_id surfaces combos.member.provider_required (ADR-011)", async () => {
    stubComboApi();
    await window.aigate.combos.openEditModal("5");
    await window.aigate.combos.addMember({ provider_id: null, provider_model: "x" });
    const msg = document.getElementById("comboMemberMsg");
    expect(msg.textContent).toContain("Select a provider first.");
    expect(msg.className).toContain("settings-msg-error");
  });

  it("removeMember confirms then DELETEs /api/combos/<id>/members/<mid>", async () => {
    const calls = stubComboApi();
    window.confirm = vi.fn(() => true);
    await window.aigate.combos.openEditModal("5");
    await window.aigate.combos.removeMember(7);
    expect(window.confirm).toHaveBeenCalled();
    const del = calls.find((c) => c.url === "/api/combos/5/members/7" && c.opts.method === "DELETE");
    expect(del).toBeTruthy();
  });

  it("removeMember does NOT call DELETE when the user cancels the confirm", async () => {
    const calls = stubComboApi();
    window.confirm = vi.fn(() => false);
    await window.aigate.combos.openEditModal("5");
    await window.aigate.combos.removeMember(7);
    expect(calls.find((c) => c.opts && c.opts.method === "DELETE")).toBeFalsy();
  });

  it("saveMember PUTs the patch to /api/combos/<id>/members/<mid>", async () => {
    const calls = stubComboApi();
    await window.aigate.combos.openEditModal("5");
    await window.aigate.combos.saveMember(7,
      { provider_id: 1, provider_model: "gpt-4o", priority: 3, weight: 2 });
    const put = calls.find((c) => c.url === "/api/combos/5/members/7" && c.opts.method === "PUT");
    expect(put).toBeTruthy();
    expect(JSON.parse(put.opts.body)).toEqual(
      { provider_id: 1, provider_model: "gpt-4o", priority: 3, weight: 2 });
  });

  it("member endpoint errors surface in #comboMemberMsg (ADR-011)", async () => {
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      const u = String(url);
      if (u === "/api/providers") return jsonResponse(sampleProviders());
      if (u === "/api/combos/5") return jsonResponse(sampleCombo());
      if (u.indexOf("/members") !== -1 && opts && opts.method === "POST") {
        return Promise.resolve({
          ok: false, status: 404,
          headers: { get: () => "application/json" },
          json: () => Promise.resolve({ error: { message: "combo 5 not found" } })
        });
      }
      return jsonResponse({ object: "list", data: [] });
    }));
    await window.aigate.combos.openEditModal("5");
    await window.aigate.combos.addMember(
      { provider_id: 1, provider_model: "m", priority: 0, weight: 1 });
    const msg = document.getElementById("comboMemberMsg");
    expect(msg.textContent).toContain("combo 5 not found");
    expect(msg.className).toContain("settings-msg-error");
  });
});

describe("combos strategy select — three_tier (B5.2)", () => {
  it("index.html strategy select keeps the old options and adds three_tier", () => {
    const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
    const doc = new JSDOM(html).window.document;
    const sel = doc.getElementById("comboStrategy");
    const values = Array.from(sel.querySelectorAll("option")).map((o) => o.value);
    expect(values).toEqual(["fallback", "load_balance", "latency_cost", "three_tier"]);
    // i18n label wired on the new option.
    const opt = sel.querySelector('option[value="three_tier"]');
    expect(opt.getAttribute("data-i18n")).toBe("combos.strategy.three_tier");
  });

  it("i18n has EN + ID labels for three_tier and every combos.member(s) key", () => {
    expect(window.I18N.en["combos.strategy.three_tier"]).toContain("Three-tier");
    expect(window.I18N.id["combos.strategy.three_tier"]).toContain("Tiga tingkat");
    [
      "combos.members.none", "combos.member.add", "combos.member.update",
      "combos.member.provider", "combos.member.model", "combos.member.priority",
      "combos.member.weight", "combos.member.remove", "combos.member.edit",
      "combos.member.confirm_delete", "combos.member.provider_ph",
      "combos.member.model_ph", "combos.member.cancel_edit",
      "combos.member.provider_required", "combos.member.loading",
      "combos.member.load_failed"
    ].forEach((k) => {
      expect(window.I18N.en[k]).toBeDefined();
      expect(window.I18N.id[k]).toBeDefined();
    });
  });
});

describe("combos members — add-member sub-form layout + labels (visual fix)", () => {
  // Read the SHIPPED markup (source of truth for the visual fix), not the
  // simplified test DOM, so the layout/label structure is verified for real.
  const doc = new JSDOM(
    readFileSync(join(__dirname, "..", "static", "index.html"), "utf8")
  ).window.document;

  const FIELDS = [
    { id: "comboMemberProvider", key: "combos.member.provider" },
    { id: "comboMemberModel", key: "combos.member.model" },
    { id: "comboMemberPriority", key: "combos.member.priority" },
    { id: "comboMemberWeight", key: "combos.member.weight" }
  ];

  it("every sub-form field has a VISIBLE associated <label for=...> (a11y)", () => {
    FIELDS.forEach(({ id, key }) => {
      const label = doc.querySelector('label[for="' + id + '"]');
      expect(label).not.toBeNull();               // associated, not just aria-label
      expect(label.classList.contains("form-label")).toBe(true);
      expect(label.getAttribute("data-i18n")).toBe(key); // i18n-wired
      expect((label.textContent || "").trim().length).toBeGreaterThan(0); // visible copy
    });
  });

  it("no field relies solely on aria-label (visible label replaces it)", () => {
    // The provider select previously had only aria-label; it must now be gone
    // in favour of the real <label for=...>.
    const sel = doc.getElementById("comboMemberProvider");
    expect(sel).not.toBeNull();
    expect(sel.getAttribute("aria-label")).toBeNull();
  });

  it("fields sit in a labeled grid; buttons on their own aligned row", () => {
    const form = doc.querySelector(".combo-member-form");
    expect(form).not.toBeNull();
    const grid = form.querySelector(".combo-member-fields");
    expect(grid).not.toBeNull();
    // All four fields are inside the grid, each wrapped in .combo-member-field.
    FIELDS.forEach(({ id }) => {
      const field = grid.querySelector('.combo-member-field #' + id);
      expect(field).not.toBeNull();
    });
    expect(grid.querySelectorAll(".combo-member-field").length).toBe(4);
    // Add/Cancel live in a separate actions row (never orphaned with a field).
    const actions = form.querySelector(".combo-member-actions");
    expect(actions).not.toBeNull();
    expect(actions.querySelector("#comboMemberAddBtn")).not.toBeNull();
    expect(actions.querySelector("#comboMemberCancelEdit")).not.toBeNull();
  });

  it("keeps every member-editor element id unchanged (logic/tests depend on them)", () => {
    [
      "comboMemberProvider", "comboMemberModel", "comboMemberModelList",
      "comboMemberPriority", "comboMemberWeight", "comboMemberAddBtn",
      "comboMemberCancelEdit", "comboMembersBody", "comboMembersTable",
      "comboMemberMsg"
    ].forEach((id) => {
      expect(doc.getElementById(id)).not.toBeNull();
    });
  });
});
