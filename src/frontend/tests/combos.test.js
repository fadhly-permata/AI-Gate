import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { indexDocument, indexHtml } from "./helpers/dom.js";
import { localeCodes } from "./helpers/i18n-dicts.js";

// i18n dict (window.I18N) so getStr() resolves labels during render.
import "../static/i18n.js";
// combobox.js exposes window.aigate.createCombobox (loaded before app.js /
// combos.js in index.html — same order here).
import "../static/combobox.js";
// app.js exposes window.aigate.fetchJson / escapeHtml / getStr used by the module.
import "../static/app.js";
// The Combos module registers window.aigate.combos and wires its DOM (guarded).
import "../static/combos.js";


// Fixture markup as constants, so each test can install it with ONE
// innerHTML assignment (see withComboModalDom below).
const LIST_HTML =
  '<p id="comboMsg"></p>' +
  '<table id="comboTable"><tbody id="comboTableBody"></tbody></table>';

function withDom() {
  document.body.innerHTML = LIST_HTML;
}

// Build the combo modal DOM (mirrors index.html #comboModal) incl. the
// members editor section, so the members helpers can be driven in tests.
// Structure mirrors the labeled add-member grid: each field wrapped in a
// .combo-member-field with a visible <label for=...>. Element ids unchanged.
// Stage-8: there is NO Priority field (the row order is the priority).
const MODAL_HTML =
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
        '<table id="comboMembersTable">' +
          '<thead><tr>' +
            '<th data-i18n="combos.member.enabled">Enabled</th>' +
            '<th data-i18n="combos.member.model">Model</th>' +
            '<th data-i18n="combos.member.weight">Weight</th>' +
            '<th></th>' +
          '</tr></thead>' +
          '<tbody id="comboMembersBody"></tbody>' +
        '</table>' +
        '<div class="combo-member-form" id="comboMemberForm">' +
          '<div class="combo-member-fields">' +
            '<div class="combo-member-field">' +
              '<label class="form-label" for="comboMemberProvider" data-i18n="combos.member.provider">Provider</label>' +
              '<select id="comboMemberProvider"></select>' +
            '</div>' +
            '<div class="combo-member-field">' +
              '<label class="form-label" for="comboMemberModel" data-i18n="combos.member.model">Model</label>' +
              '<div class="combo-model-control">' +
                '<div class="combo-model-select-row aigate-combo">' +
                  '<input type="text" id="comboMemberModel" autocomplete="off" />' +
                  '<ul id="comboMemberModelList" role="listbox" hidden></ul>' +
                  '<span class="combo-model-spinner" id="comboMemberModelSpinner" hidden aria-hidden="true"></span>' +
                '</div>' +
              '</div>' +
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

// One assignment instead of `withDom(); innerHTML += ...`: `+=` serialises the
// live DOM back to a string and then re-parses the WHOLE body, so this fixture
// was parsed twice per test (it is the beforeEach for most of this file).
// Resulting DOM is identical: LIST_HTML then MODAL_HTML, same order.
function withComboModalDom() {
  document.body.innerHTML = LIST_HTML + MODAL_HTML;
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

// ---- Model COMBOBOX readers (text input + custom <ul> panel; the old
// <select> + "__custom__" free-text box and any <datalist> are gone) ----

const modelInput = () => document.getElementById("comboMemberModel");
const modelList = () => document.getElementById("comboMemberModelList");

// The rendered option rows (data-value = model id), in DOM order.
const modelOptionEls = () => Array.from(modelList().querySelectorAll('li[role="option"]'));
const modelOptionValues = () => modelOptionEls().map((li) => li.getAttribute("data-value"));
// Groups are collapsed by default (combobox FIX 2), so child options are not in
// the DOM until a group is expanded (or a search auto-expands it). Helper to
// expand every still-collapsed group header.
function expandAllGroups() {
  // Re-query each iteration: clicking a header re-renders the DOM and detaches
  // the previously captured header nodes, so a single captured list won't all fire.
  let guard = 0;
  while (guard++ < 50) {
    const h = modelList().querySelector(
      ".aigate-combo-group.aigate-combo-group-collapsed");
    if (!h) break;
    h.dispatchEvent(new MouseEvent("click", { bubbles: true }));
  }
}
// Every rendered option is a real model id now (no placeholder / sentinel).
const modelIds = modelOptionValues;
const modelLabels = () => modelOptionEls().map((li) => li.textContent);

// Type into the combobox input (fires the delegated filter + open handler).
function typeModel(v) {
  modelInput().value = v;
  modelInput().dispatchEvent(new Event("input", { bubbles: true }));
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

  it("renderCombos fills the table body, escapes data, kebab menu", () => {
    window.aigate.combos.renderCombos([
      { id: 1, name: "Alpha <x>", strategy: "fallback", enabled: true, members: [] }
    ]);
    const html = document.getElementById("comboTableBody").innerHTML;
    expect(html).toContain("Alpha &lt;x&gt;");
    expect(html).toContain('data-id="1"');
    expect(html).toContain("js-row-menu");
    expect(html).toContain("row-actions");
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

  it("renders one row per member — provider NAME removed, enable toggle present, model + weight + ▲▼ kept", () => {
    window.aigate.combos.renderMembers(sampleCombo().members, {
      1: { id: 1, name: "OpenRouter" },
      2: { id: 2, name: "Ollama" }
    });
    const body = document.getElementById("comboMembersBody");
    expect(body.querySelectorAll("tr.member-row").length).toBe(2);
    const html = body.innerHTML;
    // (A) Provider NAME is gone from the row — only the model is shown.
    expect(html).not.toContain("OpenRouter");
    expect(html).not.toContain("Ollama");
    expect(html).not.toContain("#1");           // nor the unknown-provider fallback
    expect(html).toContain("llama-3.1");    // model
    expect(html).toContain("qwen");
    expect(html).toContain(">0.5<");        // weight
    // (B) Edit + Delete are now ONE kebab submenu trigger, not two buttons.
    expect(html).toContain("js-row-menu");
    expect(html).not.toContain("js-mem-edit");
    expect(html).not.toContain("js-mem-del");
    expect(html).toContain('data-id="7"');
    // (B) One enable/disable checkbox per row, with the i18n aria-label.
    const toggles = body.querySelectorAll(".js-mem-enabled");
    expect(toggles.length).toBe(2);
    expect(toggles[0].getAttribute("aria-label")).toBe("Enabled");
    // Members without an explicit `enabled` default ON (checkbox checked).
    expect(toggles[0].hasAttribute("checked")).toBe(true);
    // Stage-8: priority is the ROW ORDER, not a cell. Neither stored value (0 /
    // 1) survives into the markup, and the row has exactly 4 cells.
    const cells = body.querySelectorAll("tr.member-row")[0].querySelectorAll("td");
    expect(cells.length).toBe(4);
    expect(cells[2].textContent).toBe("1");           // weight of member #1
    expect(html).not.toContain("Priority");
    // ▲▼ per row, labelled from i18n.
    expect(body.querySelectorAll(".js-mem-up").length).toBe(2);
    expect(body.querySelectorAll(".js-mem-down").length).toBe(2);
    expect(body.querySelectorAll(".js-mem-up")[0].getAttribute("aria-label"))
      .toBe(window.I18N.en["combos.member.move_up"]);
    expect(body.querySelectorAll(".js-mem-down")[1].getAttribute("title"))
      .toBe(window.I18N.en["combos.member.already_last"]);
  });

  it("a disabled member row gets the greyed `is-disabled` class", () => {
    window.aigate.combos.renderMembers([
      { id: 7, combo_id: 5, provider_id: 1, provider_model: "llama-3.1", priority: 0, weight: 1, enabled: true },
      { id: 8, combo_id: 5, provider_id: 2, provider_model: "qwen", priority: 1, weight: 0.5, enabled: false }
    ], {});
    const rows = document.querySelectorAll("#comboMembersBody tr.member-row");
    expect(rows[0].classList.contains("is-disabled")).toBe(false);
    expect(rows[0].querySelector(".js-mem-enabled").hasAttribute("checked")).toBe(true);
    expect(rows[1].classList.contains("is-disabled")).toBe(true);
    expect(rows[1].querySelector(".js-mem-enabled").hasAttribute("checked")).toBe(false);
  });

  it("boundary arrows are aria-disabled with a reason, interior arrows are live", () => {
    window.aigate.combos.renderMembers(sampleCombo().members, {});
    const rows = document.querySelectorAll("#comboMembersBody tr.member-row");
    const first = rows[0];
    const last = rows[rows.length - 1];
    expect(first.querySelector(".js-mem-up").getAttribute("aria-disabled")).toBe("true");
    expect(first.querySelector(".js-mem-up").getAttribute("title"))
      .toBe(window.I18N.en["combos.member.already_first"]);
    expect(first.querySelector(".js-mem-down").hasAttribute("aria-disabled")).toBe(false);
    expect(last.querySelector(".js-mem-down").getAttribute("aria-disabled")).toBe("true");
    expect(last.querySelector(".js-mem-down").getAttribute("title"))
      .toBe(window.I18N.en["combos.member.already_last"]);
    expect(last.querySelector(".js-mem-up").hasAttribute("aria-disabled")).toBe(false);
    // A one-row combo explains BOTH boundaries at once.
    window.aigate.combos.renderMembers([sampleCombo().members[0]], {});
    const only = document.querySelector("#comboMembersBody tr.member-row");
    expect(only.querySelector(".js-mem-up").getAttribute("aria-disabled")).toBe("true");
    expect(only.querySelector(".js-mem-down").getAttribute("aria-disabled")).toBe("true");
  });

  it("escapes member data (no raw HTML injection)", () => {
    window.aigate.combos.renderMembers(
      [{ id: 1, provider_id: 9, provider_model: "<img src=x>", priority: 0, weight: 1 }],
      {}
    );
    const html = document.getElementById("comboMembersBody").innerHTML;
    expect(html).toContain("&lt;img src=x&gt;");
    expect(html).not.toContain("<img src=x>");
    // Provider NAME was removed (handover §A) — no provider label, never "undefined".
    expect(html).not.toContain("undefined");
    expect(html).toContain('class="js-mem-enabled"');
  });

  it("shows the empty-state message when there are no members", () => {
    window.aigate.combos.renderMembers([], {});
    expect(document.getElementById("comboMembersBody").innerHTML)
      .toContain("No members yet.");
  });

  it("the empty-state cell spans exactly the columns the table header ships", () => {
    window.aigate.combos.renderMembers([], {});
    const headCols = document.querySelectorAll("#comboMembersTable thead th").length;
    const span = parseInt(
      document.querySelector("#comboMembersBody td.empty-cell").getAttribute("colspan"), 10);
    expect(headCols).toBe(4);            // Provider | Model | Weight | actions
    expect(span).toBe(headCols);         // no orphaned empty cell after stage-8
  });

  it("every locale has the ▲▼ labels and the order hint (no raw key on screen)", () => {
    ["combos.member.move_up", "combos.member.move_down", "combos.member.already_first",
     "combos.member.already_last", "combos.member.order_hint"].forEach((k) => {
      expect(window.I18N.en[k], k).toBeTruthy();
    });
    // The hint is rendered from i18n by applyLocale (data-i18n hook exists).
    expect(indexDocument().querySelector('[data-i18n="combos.member.order_hint"]')).not.toBeNull();
  });
});

describe("combos members — kebab submenu (edit/delete) replaces pencil+trash", () => {
  beforeEach(() => { withComboModalDom(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  // (a) The toggle column header is now labelled "Enabled".
  it("member table header column 1 is labelled 'Enabled'", () => {
    const ths = document.querySelectorAll("#comboMembersTable thead th");
    expect(ths.length).toBe(4);
    expect(ths[0].getAttribute("data-i18n")).toBe("combos.member.enabled");
    expect(ths[0].textContent).toBe("Enabled");
  });

  // (b) Actions cell shows ONE kebab trigger, not the old separate buttons; ▲▼ stay.
  it("actions cell shows ONE kebab (js-row-menu), not separate edit/delete buttons", () => {
    window.aigate.combos.renderMembers(sampleCombo().members, {});
    const body = document.getElementById("comboMembersBody");
    expect(body.querySelectorAll(".js-row-menu").length).toBe(2);
    expect(body.querySelectorAll(".js-mem-edit").length).toBe(0);
    expect(body.querySelectorAll(".js-mem-del").length).toBe(0);
    // ▲▼ still present and OUTSIDE the kebab.
    expect(body.querySelectorAll(".js-mem-up").length).toBe(2);
    expect(body.querySelectorAll(".js-mem-down").length).toBe(2);
    expect(body.querySelectorAll(".member-move").length).toBe(2);
  });

  // (c) Clicking the kebab opens a submenu with Edit + Delete (danger).
  it("clicking the kebab opens a submenu with Edit + Delete", () => {
    window.aigate.combos.renderMembers(sampleCombo().members, {});
    const kebab = document.querySelector("#comboMembersBody .js-row-menu");
    kebab.click();
    const menu = document.querySelector(".row-menu");
    expect(menu).toBeTruthy();
    const actions = Array.from(menu.querySelectorAll("[data-action]"))
      .map((b) => b.getAttribute("data-action"));
    expect(actions).toEqual(["edit", "delete"]);
    // Delete item is flagged danger; Edit is not.
    expect(menu.querySelector('[data-action="delete"]').classList.contains("is-danger")).toBe(true);
    expect(menu.querySelector('[data-action="edit"]').classList.contains("is-danger")).toBe(false);
    // Labels come from i18n (reused keys, parity intact).
    expect(menu.querySelector('[data-action="edit"]').textContent)
      .toContain(window.I18N.en["combos.member.edit"]);
    expect(menu.querySelector('[data-action="delete"]').textContent)
      .toContain(window.I18N.en["combos.member.remove"]);
  });

  // (d) Kebab Edit loads the row into the sub-form (calls editMemberRow).
  it("kebab Edit loads the row into the sub-form (editMemberRow)", async () => {
    vi.stubGlobal("fetch", vi.fn((url) =>
      String(url).indexOf("/api/providers") !== -1 ? jsonResponse(sampleProviders()) : jsonResponse({})));
    await window.aigate.combos.openAddModal();
    // Row 0 = "a" (weight 1), Row 1 = "b" (weight 5).
    window.aigate.combos.bufferMemberLocal({ provider_id: 1, provider_model: "a", weight: "1" });
    window.aigate.combos.bufferMemberLocal({ provider_id: 1, provider_model: "b", weight: "5" });
    document.querySelector("#comboMembersBody .js-row-menu").click();
    document.querySelector('.row-menu [data-action="edit"]').click();
    // fillMemberForm (via editMemberRow) flips the form into edit mode and loads
    // member "a"'s weight.
    expect(document.getElementById("comboMemberAddBtn").textContent)
      .toBe(window.I18N.en["combos.member.update"]);
    expect(document.getElementById("comboMemberCancelEdit").hidden).toBe(false);
    expect(document.getElementById("comboMemberWeight").value).toBe("1");
  });

  // (e) Delete path: SAVED member -> removeMember (DELETE /api/combos/5/members/7).
  it("kebab Delete removes a SAVED member via DELETE /api/combos/:id/members/:mid", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url: String(url), opts });
      if (String(url) === "/api/providers") return jsonResponse(sampleProviders());
      if (String(url) === "/api/combos/5") return jsonResponse(sampleCombo());
      if (String(url).indexOf("/api/combos/5/members/") === 0) return jsonResponse({ ok: true });
      return jsonResponse({});
    }));
    window.confirm = vi.fn(() => true);
    await window.aigate.combos.openEditModal("5");
    document.querySelector("#comboMembersBody .js-row-menu").click();
    document.querySelector('.row-menu [data-action="delete"]').click();
    await new Promise((r) => setTimeout(r, 0));
    const del = calls.find((c) =>
      c.url === "/api/combos/5/members/7" && c.opts && c.opts.method === "DELETE");
    expect(del).toBeTruthy();
  });

  // (e) Delete path: BUFFER member -> removeMemberLocal (no request).
  it("kebab Delete removes a BUFFER member locally (no request, not Edit path)", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url: String(url), opts });
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({});
    }));
    await window.aigate.combos.openAddModal();
    window.aigate.combos.bufferMemberLocal({ provider_id: 1, provider_model: "a", weight: "1" });
    window.aigate.combos.bufferMemberLocal({ provider_id: 1, provider_model: "b", weight: "5" });
    expect(window.aigate.combos.getMembersBuffer().length).toBe(2);
    document.querySelector("#comboMembersBody .js-row-menu").click();
    document.querySelector('.row-menu [data-action="delete"]').click();
    await new Promise((r) => setTimeout(r, 0));
    // Buffer member dropped locally; no member endpoint hit.
    expect(window.aigate.combos.getMembersBuffer().length).toBe(1);
    expect(calls.filter((c) => c.url.indexOf("/members") !== -1).length).toBe(0);
    expect(document.querySelectorAll("#comboMembersBody tr.member-row").length).toBe(1);
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

  it("populateModelOptions fills the model COMBOBOX from the chosen provider's models", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({});
    }));
    await window.aigate.combos.loadProviders();
    const models = window.aigate.combos.populateModelOptions(1);
    // Cached models are now sorted by name (case-insensitive): GPT-4o < Llama 3.1.
    expect(models.map((m) => m.model_id)).toEqual(["gpt-4o", "llama-3.1"]);
    // The combobox panel groups models; groups start collapsed, so expand them
    // to reveal the full sorted model ids (no sentinel).
    expandAllGroups();
    expect(modelOptionValues()).toEqual(["gpt-4o", "llama-3.1"]);
    // Labels show the model NAME (id as fallback).
    expect(modelLabels()).toEqual(["GPT-4o", "Llama 3.1"]);
    // Provider with no discovered models -> empty option list, and free text
    // is still accepted (the input IS the value).
    expect(window.aigate.combos.populateModelOptions(2)).toEqual([]);
    expect(modelOptionValues()).toEqual([]);
    window.aigate.combos.setModelValue("hand-typed");
    expect(window.aigate.combos.modelFieldValue()).toBe("hand-typed");
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

  it("after a fetch #comboMemberModel is a combobox INPUT + custom <ul> panel", async () => {
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
    // A searchable combobox input (mobile-working + type-to-search), NOT a
    // <select> and NOT an <input list=...> + <datalist>.
    const inp = modelInput();
    expect(inp.tagName).toBe("INPUT");
    expect(inp.getAttribute("role")).toBe("combobox");
    expect(inp.getAttribute("list")).toBeNull();
    expect(inp.getAttribute("aria-controls")).toBe("comboMemberModelList");
    expect(inp.getAttribute("aria-autocomplete")).toBe("list");
    const ul = modelList();
    expect(ul.tagName).toBe("UL");
    expect(ul.getAttribute("role")).toBe("listbox");
    // Options: the sorted model ids, labels = model names (id fallback).
    // Groups start collapsed, so expand them to reveal the options.
    expandAllGroups();
    expect(modelIds()).toEqual(["Alpha", "mid", "zeta"]);
    expect(modelLabels()).toEqual(["alpha", "Mid", "Zeta"]);
    // Model names are DATA, never i18n hooks (they must not be translated).
    expect(ul.querySelectorAll("[data-i18n]").length).toBe(0);
    // Typing filters the fetched list (case-insensitive substring). While a
    // query is active every group auto-expands so matches are visible.
    typeModel("MI");
    expect(modelIds()).toEqual(["mid"]);
    typeModel("");
    expandAllGroups();
    expect(modelIds()).toEqual(["Alpha", "mid", "zeta"]);
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
    const inp = modelInput();
    const add = document.getElementById("comboMemberAddBtn");
    const form = document.getElementById("comboMemberForm");
    const spinner = document.getElementById("comboMemberModelSpinner");

    const pr = window.aigate.combos.fetchModelsForProvider(1);
    // Applied synchronously, BEFORE the fetch resolves: the combobox input is
    // disabled + aria-busy, the Add button locks, the spinner shows, and the
    // panel carries a "Loading models…" row instead of options.
    expect(inp.tagName).toBe("INPUT");
    expect(inp.disabled).toBe(true);
    expect(inp.getAttribute("aria-busy")).toBe("true");
    expect(add.disabled).toBe(true);
    expect(form.getAttribute("aria-busy")).toBe("true");
    expect(spinner.hidden).toBe(false);
    expect(modelList().textContent).toContain(window.I18N.en["combos.member.loading"]);
    expect(modelOptionValues()).toEqual([]);

    resolveDisc();
    await pr;
    // Cleared after resolve:
    expect(inp.disabled).toBe(false);
    expect(inp.getAttribute("aria-busy")).toBe("false");
    expect(add.disabled).toBe(false);
    expect(form.getAttribute("aria-busy")).toBe("false");
    expect(spinner.hidden).toBe(true);
    expect(modelList().textContent).not.toContain(window.I18N.en["combos.member.loading"]);
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
    expandAllGroups();
    expect(modelIds()).toEqual(["gpt-4o", "llama-3.1"]);
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
    expandAllGroups();
    expect(modelIds()).toEqual(["fresh-b"]);
    resolveA();          // stale resolves LATER -> must be ignored
    await tick();
    expandAllGroups();
    expect(modelIds()).toEqual(["fresh-b"]); // unchanged by the stale response
    expect(document.getElementById("comboMemberModel").disabled).toBe(false);
  });
});

describe("combos members — searchable combobox model field (free text native)", () => {
  beforeEach(() => { withComboModalDom(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  const tick = () => new Promise((r) => setTimeout(r, 0));
  const body = (payload) => Promise.resolve({
    ok: true, headers: { get: () => "application/json" },
    json: () => Promise.resolve(payload)
  });

  // Seed the combobox with provider 1's models (sorted) via the real path.
  async function withDiscoveredModels() {
    vi.stubGlobal("fetch", vi.fn((url) => {
      const u = String(url);
      if (u === "/api/providers") return jsonResponse(sampleProviders());
      if (u === "/api/providers/1/discover") {
        return body({ ok: true, models: [
          { id: 1, model_id: "llama-3.1", model_name: "Llama 3.1" },
          { id: 2, model_id: "gpt-4o", model_name: "GPT-4o" }
        ] });
      }
      return body({});
    }));
    await window.aigate.combos.loadProviders();
    await window.aigate.combos.fetchModelsForProvider(1);
  }

  it("memberFormValues() returns the SELECTED option value (weight stays manual, priority is gone)", async () => {
    await withDiscoveredModels();
    document.getElementById("comboMemberProvider").value = "1";
    document.getElementById("comboMemberWeight").value = "0.5";
    // Groups are collapsed by default — expand them so the options are in the DOM.
    expandAllGroups();
    // Click the "GPT-4o" option in the panel.
    const gpt = modelOptionEls().find((li) => li.getAttribute("data-value") === "gpt-4o");
    gpt.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    // Stage-8: the sub-form owns provider + model + weight ONLY. Priority is the
    // row position, so no number leaks out of here (and no field is read).
    expect(window.aigate.combos.memberFormValues()).toEqual({
      provider_id: 1, provider_model: "gpt-4o", weight: 0.5
    });
    // Selecting an option closes the panel.
    expect(modelList().hidden).toBe(true);
  });

  it("memberFormValues() returns the TYPED free-text value (custom model)", async () => {
    await withDiscoveredModels();
    document.getElementById("comboMemberProvider").value = "1";
    typeModel("   my-local-model   ");
    expect(window.aigate.combos.memberFormValues().provider_model).toBe("my-local-model");
    // An empty input resolves to "" (no phantom sentinel).
    typeModel("   ");
    expect(window.aigate.combos.memberFormValues().provider_model).toBe("");
  });

  it("typing filters the discovered list (case-insensitive substring)", async () => {
    await withDiscoveredModels();
    typeModel("LLAMA");
    expect(modelIds()).toEqual(["llama-3.1"]);
    typeModel("");
    expandAllGroups();
    expect(modelIds()).toEqual(["gpt-4o", "llama-3.1"]);
  });

  it("submitMemberForm blocks an empty model with combos.member.model_required (ADR-011)", async () => {
    await withDiscoveredModels();
    document.getElementById("comboMemberProvider").value = "1";
    window.aigate.combos.setModelValue("");
    await window.aigate.combos.submitMemberForm();
    const msg = document.getElementById("comboMemberMsg");
    expect(msg.textContent).toContain(window.I18N.en["combos.member.model_required"]);
    expect(msg.className).toContain("settings-msg-error");
  });

  it("fillMemberForm with an UNKNOWN model round-trips it as free text", async () => {
    await withDiscoveredModels();   // list knows llama-3.1 + gpt-4o only
    window.aigate.combos.fillMemberForm({
      provider_id: 1, provider_model: "not-discovered-yet", priority: 1, weight: 1
    });
    await tick();
    expect(modelInput().value).toBe("not-discovered-yet");
    expect(window.aigate.combos.memberFormValues().provider_model).toBe("not-discovered-yet");
  });

  it("fillMemberForm with a KNOWN model sets the value", async () => {
    await withDiscoveredModels();
    window.aigate.combos.fillMemberForm({
      provider_id: 1, provider_model: "llama-3.1", priority: 0, weight: 1
    });
    await tick();
    expect(modelInput().value).toBe("llama-3.1");
    expect(window.aigate.combos.memberFormValues().provider_model).toBe("llama-3.1");
  });

  it("renderModelOptions keeps the current value (free text is native, no reset)", async () => {
    await withDiscoveredModels();
    window.aigate.combos.setModelValue("gpt-4o");
    window.aigate.combos.populateModelOptions(1);      // same list -> kept
    expect(modelInput().value).toBe("gpt-4o");
    window.aigate.combos.populateModelOptions(2);      // provider 2 has no models
    // The value survives an option refresh even when the list goes empty —
    // the input holds ANY string (this is what replaced the __custom__ box).
    expect(modelInput().value).toBe("gpt-4o");
    expect(modelOptionValues()).toEqual([]);
  });

  it("setModelLoading(true) disables the input + shows the loading row, then re-enables", () => {
    window.aigate.combos.setModelLoading(true);
    expect(modelInput().disabled).toBe(true);
    expect(modelInput().getAttribute("aria-busy")).toBe("true");
    expect(document.getElementById("comboMemberModelSpinner").hidden).toBe(false);
    expect(modelList().textContent).toContain(window.I18N.en["combos.member.loading"]);
    window.aigate.combos.setModelLoading(false);
    expect(modelInput().disabled).toBe(false);
    expect(modelInput().getAttribute("aria-busy")).toBe("false");
    expect(modelList().textContent).not.toContain(window.I18N.en["combos.member.loading"]);
  });

  it("switching provider clears the model value", async () => {
    await withDiscoveredModels();
    window.aigate.combos.setModelValue("hand-typed");
    const prov = document.getElementById("comboMemberProvider");
    prov.value = "2";
    prov.dispatchEvent(new Event("change", { bubbles: true }));
    await tick();
    expect(modelInput().value).toBe("");
    expect(window.aigate.combos.modelFieldValue()).toBe("");
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

    // The typed priority values are IGNORED: a buffered member joins at the END
    // and the payload is numbered by position (stage-8).
    window.aigate.combos.bufferMemberLocal(
      { provider_id: 1, provider_model: "llama-3.1", weight: "1" });
    window.aigate.combos.bufferMemberLocal(
      { provider_id: 2, provider_model: "qwen", priority: 2, weight: 0.5 });

    expect(window.aigate.combos.buildMembersPayload()).toEqual([
      { provider_id: 1, provider_model: "llama-3.1", weight: 1, priority: 0 },
      { provider_id: 2, provider_model: "qwen", weight: 0.5, priority: 1 }
    ]);
    // Buffer renders in the modal table without any server call.
    expect(document.getElementById("comboMembersBody")
      .querySelectorAll("tr.member-row").length).toBe(2);

    // removeMemberLocal drops the buffered row by index.
    window.aigate.combos.removeMemberLocal(0);
    expect(window.aigate.combos.buildMembersPayload().length).toBe(1);
    expect(window.aigate.combos.buildMembersPayload()[0].provider_id).toBe(2);
    // ...and the surviving row is renumbered to the position it now holds.
    expect(window.aigate.combos.buildMembersPayload()[0].priority).toBe(0);
  });

  it("buffer mode: ▲▼ reorders the array with ZERO requests", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url: String(url), method: (opts && opts.method) || "GET" });
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({});
    }));
    await window.aigate.combos.openAddModal();
    calls.length = 0;
    window.aigate.combos.bufferMemberLocal({ provider_id: 1, provider_model: "a", weight: 1 });
    window.aigate.combos.bufferMemberLocal({ provider_id: 1, provider_model: "b", weight: 1 });
    window.aigate.combos.bufferMemberLocal({ provider_id: 2, provider_model: "c", weight: 1 });
    expect(calls).toHaveLength(0);   // even the ADD is buffer-only here

    const body = document.getElementById("comboMembersBody");
    const models = () => Array.from(body.querySelectorAll("tr.member-row"))
      .map((tr) => tr.querySelectorAll("td")[1].textContent);
    expect(models()).toEqual(["a", "b", "c"]);
    // Row 1 goes down, then row 3 comes up: still not one request.
    body.querySelectorAll(".js-mem-down")[0].click();
    body.querySelectorAll(".js-mem-up")[2].click();
    await new Promise((r) => setTimeout(r, 0));
    expect(models()).toEqual(["b", "c", "a"]);
    expect(calls).toHaveLength(0);
    // And the order the user built is what Save will send.
    expect(window.aigate.combos.buildMembersPayload()
      .map((m) => [m.provider_model, m.priority]))
      .toEqual([["b", 0], ["c", 1], ["a", 2]]);
  });

  it("buffer mode: a move while a row is open in the editor follows THAT row", async () => {
    vi.stubGlobal("fetch", vi.fn((url) => {
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({});
    }));
    await window.aigate.combos.openAddModal();
    ["a", "b", "c"].forEach((m) => window.aigate.combos.bufferMemberLocal(
      { provider_id: 1, provider_model: m, weight: 1 }));
    const body = document.getElementById("comboMembersBody");
    // Edit "a" (index 0), then move it down one BEFORE submitting: the pending
    // edit must follow the row, not stay pinned to index 0 (which is "b" now).
    body.querySelector(".js-row-menu").click();
    document.querySelector('.row-menu [data-action="edit"]').click();
    body.querySelectorAll(".js-mem-down")[0].click();
    await new Promise((r) => setTimeout(r, 0));
    document.getElementById("comboMemberWeight").value = "7";
    await window.aigate.combos.submitMemberForm();
    await new Promise((r) => setTimeout(r, 0));
    expect(window.aigate.combos.buildMembersPayload()
      .map((m) => [m.provider_model, m.weight]))
      .toEqual([["b", 1], ["a", 7], ["c", 1]]);
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
      { provider_id: 1, provider_model: "gpt-4o", weight: 1 });

    window.aigate.combos.saveCombo({ preventDefault: () => {} });
    await new Promise((r) => setTimeout(r, 0));

    const post = calls.find((c) => c.url === "/api/combos" && c.opts.method === "POST");
    expect(post).toBeTruthy();
    expect(JSON.parse(post.opts.body)).toEqual({
      name: "OneShot", strategy: "three_tier", enabled: true,
      members: [{ provider_id: 1, provider_model: "gpt-4o", weight: 1, priority: 0 }]
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

  it("openEditModal loads the combo and renders its members (no provider NAME, toggle present)", async () => {
    stubComboApi();
    await window.aigate.combos.openEditModal("5");
    expect(window.aigate.combos.getSelectedId()).toBe("5");
    const body = document.getElementById("comboMembersBody");
    const html = body.innerHTML;
    // (A) Provider NAME no longer rendered in the row.
    expect(html).not.toContain("OpenRouter");
    expect(html).not.toContain("Ollama");
    expect(html).toContain("llama-3.1");
    // (B) One enable toggle per member.
    expect(body.querySelectorAll(".js-mem-enabled").length).toBe(2);
  });

  it("addMember POSTs /api/combos/<id>/members and joins at the END, then reloads", async () => {
    const calls = stubComboApi();
    await window.aigate.combos.openEditModal("5");
    // The typed priority is ignored on purpose: with 2 members already loaded,
    // a new one is number 2 (the bottom of the retry queue), never 0 / 99.
    await window.aigate.combos.addMember(
      { provider_id: 1, provider_model: "gpt-4o", priority: "99", weight: "0.5" });

    const post = calls.find((c) => c.url === "/api/combos/5/members" && c.opts.method === "POST");
    expect(post).toBeTruthy();
    expect(JSON.parse(post.opts.body)).toEqual(
      { provider_id: 1, provider_model: "gpt-4o", weight: 0.5, priority: 2 });
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

  it("saveMember PUTs the partial patch it was given (no priority = order untouched)", async () => {
    const calls = stubComboApi();
    await window.aigate.combos.openEditModal("5");
    await window.aigate.combos.saveMember(7,
      { provider_id: 1, provider_model: "gpt-4o", weight: 2 });
    const put = calls.find((c) => c.url === "/api/combos/5/members/7" && c.opts.method === "PUT");
    expect(put).toBeTruthy();
    // The endpoint treats a missing field as "unchanged" (combos_router.py
    // :316-328), so an edit of model/weight can never move the row.
    expect(JSON.parse(put.opts.body)).toEqual(
      { provider_id: 1, provider_model: "gpt-4o", weight: 2 });
    expect(JSON.parse(put.opts.body)).not.toHaveProperty("priority");
  });

  it("editing a member through the sub-form never sends a priority", async () => {
    const calls = stubComboApi();
    await window.aigate.combos.openEditModal("5");
    // Row 1 -> Edit: the form has no priority field, so nothing can leak a 0
    // (which would have jumped the edited row to the front of the queue).
    document.getElementById("comboMembersBody")
      .querySelector(".js-row-menu").click();
    document.querySelector('.row-menu [data-action="edit"]').click();
    document.getElementById("comboMemberWeight").value = "3";
    await window.aigate.combos.submitMemberForm();
    const put = calls.find((c) => c.url === "/api/combos/5/members/7" && c.opts.method === "PUT");
    expect(put).toBeTruthy();
    expect(JSON.parse(put.opts.body)).toEqual(
      { provider_id: 1, provider_model: "llama-3.1", weight: 3 });
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

  it("(B) toggling a SAVED member PUTs { enabled } directly (not via normalizeMember)", async () => {
    const calls = stubComboApi();
    await window.aigate.combos.openEditModal("5");
    const toggle = document.querySelectorAll("#comboMembersBody .js-mem-enabled")[0];
    expect(toggle.hasAttribute("checked")).toBe(true);  // member #7 starts enabled
    // Disable it (set the post-toggle state, then fire `change` — the handler
    // reads `checked` which is already the new value by the time `change` runs).
    toggle.checked = false;
    toggle.dispatchEvent(new Event("change", { bubbles: true }));
    for (let i = 0; i < 4; i++) await new Promise((r) => setTimeout(r, 0));
    const put = calls.find((c) => c.url === "/api/combos/5/members/7" && c.opts.method === "PUT");
    expect(put).toBeTruthy();
    // The body is EXACTLY { enabled: false } — normalizeMember would have stripped it.
    expect(JSON.parse(put.opts.body)).toEqual({ enabled: false });
    expect(JSON.parse(put.opts.body)).not.toHaveProperty("provider_id");
    // A reload happened after the toggle (GET /api/combos/5 again).
    const gets = calls.filter((c) => c.url === "/api/combos/5" && (!c.opts || !c.opts.method));
    expect(gets.length).toBeGreaterThanOrEqual(2);
  });

  it("(B) toggling a BUFFER member updates the local object (sent on Save, no request)", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url: String(url), opts });
      if (String(url).indexOf("/api/providers") !== -1) return jsonResponse(sampleProviders());
      return jsonResponse({});
    }));
    await window.aigate.combos.openAddModal();
    window.aigate.combos.bufferMemberLocal(
      { provider_id: 1, provider_model: "llama-3.1", weight: 1 });
    const body = document.getElementById("comboMembersBody");
    const toggle = body.querySelector(".js-mem-enabled");
    expect(toggle.hasAttribute("checked")).toBe(true);   // new buffer row defaults ON
    toggle.checked = false;
    toggle.dispatchEvent(new Event("change", { bubbles: true }));
    await new Promise((r) => setTimeout(r, 0));
    // No member endpoint was hit in buffer mode.
    expect(calls.filter((c) => c.url.indexOf("/members") !== -1)).toHaveLength(0);
    // The buffered object now carries enabled:false.
    expect(window.aigate.combos.getMembersBuffer()[0].enabled).toBe(false);
    // And the row is greyed.
    expect(body.querySelector("tr.member-row").classList.contains("is-disabled")).toBe(true);
  });
});

describe("combos members — ▲▼ urutan (row order IS the priority)", () => {
  beforeEach(() => { withComboModalDom(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  // moveMember chains sequential PUTs and then reloads; give every micro- and
  // macrotask a chance to land.
  const flush = async (times) => {
    for (let i = 0; i < (times || 8); i++) await new Promise((r) => setTimeout(r, 0));
  };

  /* A tiny stand-in for the server: `state` is the truth, PUTs write into it and
     every GET /api/combos/5 re-reads it sorted by (priority, id) — the same
     order combos_router.py:117 sends. So a wrong payload shows up in the next
     render, and `events` proves whether requests ran one after another. */
  function moveStub(rows, opts) {
    opts = opts || {};
    const state = rows.map((r) => Object.assign({}, r));
    const calls = [];
    const events = [];
    const sorted = () => state.slice()
      .sort((a, b) => (a.priority - b.priority) || (a.id - b.id));
    const ok = (p) => Promise.resolve({
      ok: true, headers: { get: () => "application/json" },
      json: () => Promise.resolve(p)
    });
    vi.stubGlobal("fetch", vi.fn((url, o) => {
      const u = String(url);
      const method = (o && o.method) || "GET";
      calls.push({ url: u, method, body: o && o.body ? JSON.parse(o.body) : null });
      if (u === "/api/providers") return ok(sampleProviders());
      if (u === "/api/combos/5") {
        return ok({ id: 5, name: "Route", strategy: "fallback", enabled: true,
          members: sorted() });
      }
      if (u === "/api/combos") {
        return ok({ object: "list", data: [{ id: 5, name: "Route", strategy: "fallback",
          enabled: true, members: sorted() }] });
      }
      const one = u.match(/^\/api\/combos\/5\/members\/([^/]+)$/);
      if (one && method === "PUT") {
        const id = decodeURIComponent(one[1]);
        const body = JSON.parse(o.body);
        events.push("start:" + id);
        // Resolved on a later macrotask: a PARALLEL implementation would emit
        // start,start,end,end here — sequential ones cannot.
        return new Promise((resolve) => setTimeout(() => {
          events.push("end:" + id);
          if ((opts.fail || []).indexOf(id) !== -1) {
            resolve({ ok: false, status: 404,
              headers: { get: () => "application/json" },
              json: () => Promise.resolve({ error: { message: "combo_member_not_found" } }) });
            return;
          }
          const row = state.filter((r) => String(r.id) === id)[0];
          if (row) row.priority = body.priority;
          resolve(ok(row || {}));
        }, 0));
      }
      return ok({});
    }));
    return { calls, events, state };
  }

  const members = (spec) => spec.map((s, i) => ({
    id: s.id == null ? 11 + i : s.id, combo_id: 5, provider_id: s.p || 1,
    provider_model: s.m, priority: s.pr, weight: 1
  }));
  const shownModels = () => Array.from(
    document.querySelectorAll("#comboMembersBody tr.member-row"))
    .map((tr) => tr.querySelectorAll("td")[1].textContent);
  const arrow = (rowIdx, which) => document.querySelectorAll("#comboMembersBody tr.member-row")
    [rowIdx].querySelector(which);
  const putsOf = (calls) => calls.filter((c) => c.method === "PUT")
    .map((c) => [c.url, c.body.priority]);

  it("an untouched combo is NEVER rewritten when it is opened", async () => {
    const stub = moveStub(members([{ m: "a", pr: 0 }, { m: "b", pr: 5 }, { m: "c", pr: 9 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    // Odd stored numbers (5, 9) are a legal server state: opening must not
    // normalise them behind the user's back.
    expect(stub.calls.filter((c) => c.method === "PUT")).toHaveLength(0);
    expect(stub.state.map((r) => r.priority)).toEqual([0, 5, 9]);
    expect(shownModels()).toEqual(["a", "b", "c"]);
  });

  it("all-zero list: ▼ on row 1 renumbers and PUTs only what changed (2 PUTs)", async () => {
    // The design sheet's example: every member still at the DB default 0.
    const stub = moveStub(members([{ m: "a", pr: 0 }, { m: "b", pr: 0 }, { m: "c", pr: 0 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    arrow(0, ".js-mem-down").click();          // a trades place with b
    await flush();
    // Visible order is now b,a,c -> renumbered 0,1,2. b already holds 0, so only
    // a (0 -> 1) and c (0 -> 2) travel: two requests, not n.
    expect(putsOf(stub.calls)).toEqual([
      ["/api/combos/5/members/11", 1],
      ["/api/combos/5/members/13", 2]
    ]);
    // and the list is re-read from the server afterwards (never a lying view)
    expect(stub.calls.some((c) => c.method === "GET" && c.url === "/api/combos/5")).toBe(true);
    expect(shownModels()).toEqual(["b", "a", "c"]);
  });

  it("a tidy 0..n-1 list swap sends exactly the two rows that moved", async () => {
    const stub = moveStub(members([{ id: 21, m: "a", pr: 0 }, { id: 22, m: "b", pr: 1 },
      { id: 23, m: "c", pr: 2 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    arrow(0, ".js-mem-down").click();          // a trades place with b
    await flush();
    // b (1 -> 0) and a (0 -> 1) change; c keeps the 2 it already had.
    expect(putsOf(stub.calls)).toEqual([
      ["/api/combos/5/members/22", 0],
      ["/api/combos/5/members/21", 1]
    ]);
    expect(shownModels()).toEqual(["b", "a", "c"]);
  });

  it("PUTs run one after another, never side by side", async () => {
    const stub = moveStub(members([{ m: "a", pr: 0 }, { m: "b", pr: 0 }, { m: "c", pr: 0 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.events.length = 0;
    arrow(0, ".js-mem-down").click();
    await flush();
    expect(stub.events).toEqual(["start:11", "end:11", "start:13", "end:13"]);
  });

  it("five rows with scattered numbers: one PUT per row whose value changed", async () => {
    // Sorted by the server (priority asc, id asc) the display order is 22,24,25,21,23.
    const stub = moveStub(members([
      { id: 21, m: "a", pr: 3 }, { id: 22, m: "b", pr: 0 }, { id: 23, m: "c", pr: 7 },
      { id: 24, m: "d", pr: 1 }, { id: 25, m: "e", pr: 2 }
    ]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    expect(shownModels()).toEqual(["b", "d", "e", "a", "c"]);
    stub.calls.length = 0;
    arrow(2, ".js-mem-down").click();          // e (2) trades with a (3)
    await flush();
    // New order b,d,a,e,c -> 0,1,2,3,4. b and d already hold theirs; a:3->2,
    // e:2->3 and c:7->4 change => exactly 3 PUTs.
    const puts = stub.calls.filter((c) => c.method === "PUT");
    expect(puts.map((c) => c.url.split("/").pop()))
      .toEqual(["21", "25", "23"]);
    expect(stub.state.map((r) => [r.provider_model, r.priority].join(":"))
      .sort()).toEqual(["a:2", "b:0", "c:4", "d:1", "e:3"]);
    expect(shownModels()).toEqual(["b", "d", "a", "e", "c"]);
  });

  it("a failed PUT shows the reason inline AND still re-reads the server", async () => {
    // id 11 is the FIRST request of the chain, so the second never runs.
    const stub = moveStub(members([{ m: "a", pr: 0 }, { m: "b", pr: 0 }, { m: "c", pr: 0 }]),
      { fail: ["11"] });
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    arrow(0, ".js-mem-down").click();
    await flush();
    const msg = document.getElementById("comboMemberMsg");
    expect(msg.textContent).toContain("combo_member_not_found");
    expect(msg.className).toContain("settings-msg-error");
    // The view is re-read after the failure, so it shows the server's truth.
    expect(stub.calls.filter((c) => c.method === "GET" && c.url === "/api/combos/5").length)
      .toBeGreaterThanOrEqual(1);
    expect(shownModels()).toEqual(["a", "b", "c"]);
  });

  it("▲ on the first row and ▼ on the last row are explained no-ops (zero network)", async () => {
    const stub = moveStub(members([{ m: "a", pr: 0 }, { m: "b", pr: 1 }, { m: "c", pr: 2 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    arrow(0, ".js-mem-up").click();
    arrow(2, ".js-mem-down").click();
    await flush();
    expect(stub.calls).toHaveLength(0);
  });

  it("re-renders do not stack listeners: one ▼ fires one chain", async () => {
    const stub = moveStub(members([{ m: "a", pr: 0 }, { m: "b", pr: 0 }, { m: "c", pr: 0 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    // Three extra renders of the same tbody (openEditModal already re-rendered
    // once when the provider list arrived).
    for (let i = 0; i < 3; i++) {
      window.aigate.combos.renderMembers(window.aigate.combos.getCurrentMembers(), { 1: { id: 1, name: "OpenRouter" } });
    }
    stub.calls.length = 0;
    arrow(0, ".js-mem-down").click();
    await flush();
    expect(stub.calls.filter((c) => c.method === "PUT")).toHaveLength(2);
  });

  it("moveMember ignores out-of-range moves (defensive, still no request)", async () => {
    const stub = moveStub(members([{ m: "a", pr: 0 }, { m: "b", pr: 1 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    await window.aigate.combos.moveMember(0, -1);
    await window.aigate.combos.moveMember(1, 1);
    await flush();
    expect(stub.calls).toHaveLength(0);
  });
});

describe("combos members — shipped markup: no Priority column/field (stage-8)", () => {
  const doc = indexDocument();

  it("the members table has no Priority column and the sub-form no Priority field", () => {
    const heads = Array.from(doc.querySelectorAll("#comboMembersTable thead th"))
      .map((th) => th.getAttribute("data-i18n"));
    // (A) The first column is now labelled "Enabled" (it carries the enable
    // toggle + grip); the trailing actions column stays unlabeled. 4 cols.
    expect(heads).toEqual(["combos.member.enabled", "combos.member.model",
      "combos.member.weight", null]);
    expect(heads).not.toContain("combos.member.priority");
    expect(doc.getElementById("comboMemberPriority")).toBeNull();
    expect(doc.querySelector('[data-i18n="combos.member.priority"]')).toBeNull();
    // The shipped page carries no trace of the old field at all.
    expect(indexHtml()).not.toContain("comboMemberPriority");
    expect(indexHtml()).not.toContain("combos.member.priority");
  });

  it("an order hint sits above the table and is i18n-wired", () => {
    const hint = doc.querySelector('[data-i18n="combos.member.order_hint"]');
    expect(hint).not.toBeNull();
    const table = doc.getElementById("comboMembersTable");
    expect(hint.compareDocumentPosition(table) & 4).toBe(4); // FOLLOWING_NODE
    expect((hint.textContent || "").trim().length).toBeGreaterThan(0);
  });

  it("no dictionary still ships the dead combos.member.priority key", () => {
    localeCodes().forEach((code) => {
      expect(window.I18N[code]["combos.member.priority"], code).toBeUndefined();
      expect(window.I18N[code]["combos.member.move_up"], code).toBeTruthy();
      expect(window.I18N[code]["combos.member.order_hint"], code).toBeTruthy();
    });
  });
});

describe("combos strategy select — three_tier (B5.2)", () => {
  it("index.html strategy select keeps the old options and adds three_tier", () => {
    const doc = indexDocument();
    const sel = doc.getElementById("comboStrategy");
    const values = Array.from(sel.querySelectorAll("option")).map((o) => o.value);
    expect(values).toEqual(["fallback", "load_balance", "latency_cost", "three_tier", "round_robin"]);
    // i18n label wired on the new option.
    const opt = sel.querySelector('option[value="three_tier"]');
    expect(opt.getAttribute("data-i18n")).toBe("combos.strategy.three_tier");
    // round_robin option (B. UI) is wired to its own i18n key.
    const rr = sel.querySelector('option[value="round_robin"]');
    expect(rr).toBeTruthy();
    expect(rr.getAttribute("data-i18n")).toBe("combos.strategy.round_robin");
  });

  it("i18n has EN + ID labels for three_tier, every combos.member(s) key + the combobox keys", () => {
    expect(window.I18N.en["combos.strategy.three_tier"]).toContain("Three-tier");
    expect(window.I18N.id["combos.strategy.three_tier"]).toContain("Tiga tingkat");
    [
      "combos.members.none", "combos.member.add", "combos.member.update",
      "combos.member.provider", "combos.member.model",
      "combos.member.weight", "combos.member.remove", "combos.member.edit",
      "combos.member.move_up", "combos.member.move_down",
      "combos.member.already_first", "combos.member.already_last",
      "combos.member.order_hint",
      "combos.member.confirm_delete", "combos.member.provider_ph",
      "combos.member.cancel_edit", "combos.member.provider_required",
      "combos.member.loading", "combos.member.load_failed",
      "combos.member.model_required",
      "combobox.loading", "combobox.no_match", "combobox.search_ph"
    ].forEach((k) => {
      expect(window.I18N.en[k]).toBeDefined();
      expect(window.I18N.id[k]).toBeDefined();
    });
    // The combobox strings read as intended (EN + ID parity).
    expect(window.I18N.en["combobox.no_match"]).toContain("No models match");
    expect(window.I18N.id["combobox.no_match"]).toContain("Tidak ada model");
    expect(window.I18N.en["combobox.search_ph"]).toContain("Search");
    expect(window.I18N.id["combobox.search_ph"]).toContain("Cari");
    expect(window.I18N.en["combobox.loading"]).toBe(window.I18N.en["combos.member.loading"]);
    expect(window.I18N.id["combobox.loading"]).toBe(window.I18N.id["combos.member.loading"]);
    // The dead __custom__ sentinel keys are gone.
    expect(window.I18N.en["combos.member.model_custom"]).toBeUndefined();
    expect(window.I18N.en["combos.member.model_ph"]).toBeUndefined();
  });
});

describe("combos members — add-member sub-form layout + labels (visual fix)", () => {
  // Read the SHIPPED markup (source of truth for the visual fix), not the
  // simplified test DOM, so the layout/label structure is verified for real.
  const doc = indexDocument();

  // Stage-8: the sub-form owns 3 fields. Priority left it (the row order is the
  // priority), so any assertion below that counts fields proves the removal.
  const FIELDS = [
    { id: "comboMemberProvider", key: "combos.member.provider" },
    { id: "comboMemberModel", key: "combos.member.model" },
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
    // Every field is inside the grid, wrapped in .combo-member-field — and there
    // are exactly 3 of them (the Priority field is gone, not hidden).
    FIELDS.forEach(({ id }) => {
      const field = grid.querySelector('.combo-member-field #' + id);
      expect(field).not.toBeNull();
    });
    expect(grid.querySelectorAll(".combo-member-field").length).toBe(3);
    // Add/Cancel live in a separate actions row (never orphaned with a field).
    const actions = form.querySelector(".combo-member-actions");
    expect(actions).not.toBeNull();
    expect(actions.querySelector("#comboMemberAddBtn")).not.toBeNull();
    expect(actions.querySelector("#comboMemberCancelEdit")).not.toBeNull();
  });

  it("keeps every member-editor element id unchanged (logic/tests depend on them)", () => {
    [
      "comboMemberProvider", "comboMemberModel", "comboMemberModelList",
      "comboMemberWeight", "comboMemberAddBtn",
      "comboMemberCancelEdit", "comboMembersBody", "comboMembersTable",
      "comboMemberMsg"
    ].forEach((id) => {
      expect(doc.getElementById(id)).not.toBeNull();
    });
  });

  it("Model is a searchable combobox (input + <ul> panel), NOT a select/datalist", () => {
    const inp = doc.getElementById("comboMemberModel");
    expect(inp.tagName).toBe("INPUT");
    expect(inp.getAttribute("type")).toBe("text");
    expect(inp.getAttribute("role")).toBe("combobox");
    expect(inp.getAttribute("aria-controls")).toBe("comboMemberModelList");
    expect(inp.getAttribute("aria-autocomplete")).toBe("list");
    expect(inp.getAttribute("list")).toBeNull();
    // The custom <ul> panel (mobile-working) ships hidden.
    const ul = doc.getElementById("comboMemberModelList");
    expect(ul.tagName).toBe("UL");
    expect(ul.getAttribute("role")).toBe("listbox");
    expect(ul.hasAttribute("hidden")).toBe(true);
    // No <datalist> anywhere in the shipped page (Android does not render it),
    // and the old __custom__ free-text box is gone.
    expect(doc.querySelector("datalist")).toBeNull();
    expect(doc.getElementById("comboMemberModelCustom")).toBeNull();
    // Input + panel share the same control wrapper.
    expect(inp.closest(".combo-model-control")).toBe(ul.closest(".combo-model-control"));
  });
});

describe("combos members — drag-to-reorder (grip handle, optie b)", () => {
  beforeEach(() => { withComboModalDom(); });
  afterEach(() => { vi.unstubAllGlobals(); });

  const flush = async (times) => {
    for (let i = 0; i < (times || 8); i++) await new Promise((r) => setTimeout(r, 0));
  };

  /* Request-recording stand-in for the server: PUTs write priority, GET
     re-reads sorted by (priority, id) — the same order combos_router.py:117
     sends. So a wrong payload surfaces on the next render, and `events` proves
     the PUTs ran one after another (a PARALLEL impl would emit start,start,...). */
  function dragStub(rows, opts) {
    opts = opts || {};
    const state = rows.map((r) => Object.assign({}, r));
    const calls = [];
    const events = [];
    const sorted = () => state.slice().sort((a, b) => (a.priority - b.priority) || (a.id - b.id));
    const ok = (p) => Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve(p) });
    vi.stubGlobal("fetch", vi.fn((url, o) => {
      const u = String(url);
      const method = (o && o.method) || "GET";
      calls.push({ url: u, method, body: o && o.body ? JSON.parse(o.body) : null });
      if (u === "/api/providers") return ok(sampleProviders());
      if (u === "/api/combos/5") return ok({ id: 5, name: "Route", strategy: "fallback", enabled: true, members: sorted() });
      if (u === "/api/combos") return ok({ object: "list", data: [{ id: 5, name: "Route", strategy: "fallback", enabled: true, members: sorted() }] });
      const one = u.match(/^\/api\/combos\/5\/members\/([^/]+)$/);
      if (one && method === "PUT") {
        const id = decodeURIComponent(one[1]);
        const body = JSON.parse(o.body);
        events.push("start:" + id);
        return new Promise((resolve) => setTimeout(() => {
          events.push("end:" + id);
          if ((opts.fail || []).indexOf(id) !== -1) {
            resolve({ ok: false, status: 404, headers: { get: () => "application/json" }, json: () => Promise.resolve({ error: { message: "combo_member_not_found" } }) });
            return;
          }
          const row = state.filter((r) => String(r.id) === id)[0];
          if (row) row.priority = body.priority;
          resolve(ok(row || {}));
        }, 0));
      }
      return ok({});
    }));
    return { calls, events, state };
  }

  const dm = (spec) => spec.map((s, i) => ({ id: s.id == null ? 11 + i : s.id, combo_id: 5, provider_id: s.p || 1, provider_model: s.m, priority: s.pr, weight: 1 }));
  const shownModels = () => Array.from(document.querySelectorAll("#comboMembersBody tr.member-row")).map((tr) => tr.querySelectorAll("td")[1].textContent);
  const putsOf = (calls) => calls.filter((c) => c.method === "PUT").map((c) => [c.url, c.body.priority]);
  // jsdom returns all-zero rects; stub each row's geometry so computeDropIndex
  // (pointerY vs row midpoint) is deterministic. Row i owns [i*40,(i+1)*40).
  function stubRowRects(rows) {
    Array.from(rows).forEach((tr, i) => {
      tr.getBoundingClientRect = () => ({ top: i * 40, height: 40, bottom: (i + 1) * 40, left: 0, right: 100, width: 100 });
    });
  }
  function firePointer(type, target, clientY, pointerId) {
    const ev = new MouseEvent(type, { bubbles: true, cancelable: true, clientY: clientY });
    ev.pointerId = pointerId == null ? 1 : pointerId;
    (target || document).dispatchEvent(ev);
    return ev;
  }

  it("renders one grip handle per row, labelled from i18n, WITHOUT adding a column", () => {
    window.aigate.combos.renderMembers(sampleCombo().members, { 1: { id: 1, name: "OpenRouter" }, 2: { id: 2, name: "Ollama" } });
    const body = document.getElementById("comboMembersBody");
    expect(body.querySelectorAll(".js-mem-drag").length).toBe(2);
    const grip = body.querySelector(".js-mem-drag");
    expect(grip.tagName).toBe("BUTTON");
    expect(grip.querySelector("i.fa-grip-vertical")).not.toBeNull();
    // aria-label resolves to a real string, never the raw key.
    expect(grip.getAttribute("aria-label")).toBe(window.I18N.en["combos.member.drag"]);
    expect(grip.getAttribute("aria-label")).toBe("Drag to reorder");
    // The grip lives INSIDE the first (Provider) cell, so the row keeps the
    // same 4 cells as the ▲▼ build — no extra column, header stays 4 columns.
    expect(body.querySelectorAll("tr.member-row")[0].querySelectorAll("td").length).toBe(4);
    expect(document.querySelectorAll("#comboMembersTable thead th").length).toBe(4);
    expect(body.querySelectorAll("tr.member-row")[0].querySelectorAll("td")[0].querySelector(".js-mem-drag")).not.toBeNull();
  });

  it("computeDropIndex maps clientY to the row-before insertion index", () => {
    const fake = [0, 1, 2].map((i) => ({ getBoundingClientRect: () => ({ top: i * 40, height: 40 }) }));
    const f = window.aigate.combos.computeDropIndex;
    expect(f(fake, 5)).toBe(0);    // above row 0 midpoint (20)
    expect(f(fake, 35)).toBe(1);   // between row0 mid and row1 mid
    expect(f(fake, 65)).toBe(2);   // between row1 mid and row2 mid
    expect(f(fake, 200)).toBe(2);  // past the last row -> end index
    expect(f([], 0)).toBeNull();   // no rows
  });

  it("server mode: a drag reorders and PUTs ONLY the rows whose value changed", async () => {
    const stub = dragStub(dm([{ m: "a", pr: 0 }, { m: "b", pr: 0 }, { m: "c", pr: 0 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    // Drag row 0 (a) to the end: [b, a, c] -> renumber 0,1,2. b keeps 0, a 0->1,
    // c 0->2 change => exactly two PUTs, in that order (shared contract).
    await window.aigate.combos.reorderMembers(0, 2);
    await flush();
    expect(putsOf(stub.calls)).toEqual([
      ["/api/combos/5/members/11", 1],
      ["/api/combos/5/members/13", 2]
    ]);
    expect(shownModels()).toEqual(["b", "a", "c"]);
    // The list is re-read from the server afterwards (never a lying view).
    expect(stub.calls.some((c) => c.method === "GET" && c.url === "/api/combos/5")).toBe(true);
  });

  it("server mode: the drag PUTs run one after another, not in parallel", async () => {
    const stub = dragStub(dm([{ m: "a", pr: 0 }, { m: "b", pr: 0 }, { m: "c", pr: 0 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.events.length = 0;
    await window.aigate.combos.reorderMembers(0, 2);
    await flush();
    expect(stub.events).toEqual(["start:11", "end:11", "start:13", "end:13"]);
  });

  it("boundary: dropping the first row back on itself (top) is a no-op, zero requests", async () => {
    const stub = dragStub(dm([{ m: "a", pr: 0 }, { m: "b", pr: 1 }, { m: "c", pr: 2 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    await window.aigate.combos.reorderMembers(0, 0);
    await flush();
    expect(stub.calls).toHaveLength(0);
    expect(shownModels()).toEqual(["a", "b", "c"]);
  });

  it("boundary: a row can never be dragged past the bottom (clamped, no reorder)", async () => {
    const stub = dragStub(dm([{ m: "a", pr: 0 }, { m: "b", pr: 1 }, { m: "c", pr: 2 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    // insertIdx past the end == the last row's current slot -> no move.
    await window.aigate.combos.reorderMembers(2, 3);
    await flush();
    expect(stub.calls).toHaveLength(0);
    expect(shownModels()).toEqual(["a", "b", "c"]);
  });

  it("buffer mode: a drag reorders the array with ZERO requests", async () => {
    const calls = [];
    vi.stubGlobal("fetch", vi.fn((url, opts) => {
      calls.push({ url: String(url), method: (opts && opts.method) || "GET" });
      if (String(url).indexOf("/api/providers") !== -1) return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve(sampleProviders()) });
      return Promise.resolve({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({}) });
    }));
    await window.aigate.combos.openAddModal();
    calls.length = 0;
    window.aigate.combos.bufferMemberLocal({ provider_id: 1, provider_model: "a", weight: 1 });
    window.aigate.combos.bufferMemberLocal({ provider_id: 1, provider_model: "b", weight: 1 });
    window.aigate.combos.bufferMemberLocal({ provider_id: 2, provider_model: "c", weight: 1 });
    await window.aigate.combos.reorderMembers(0, 2);
    await flush();
    const body = document.getElementById("comboMembersBody");
    const models = () => Array.from(body.querySelectorAll("tr.member-row")).map((tr) => tr.querySelectorAll("td")[1].textContent);
    expect(models()).toEqual(["b", "a", "c"]);
    expect(calls).toHaveLength(0);
    // The order the user built is what Save sends (position => priority).
    expect(window.aigate.combos.buildMembersPayload().map((m) => [m.provider_model, m.priority]))
      .toEqual([["b", 0], ["a", 1], ["c", 2]]);
  });

  it("pointer wiring: grip pointerdown+pointerup reorders via the shared path (stubbed rects)", async () => {
    const stub = dragStub(dm([{ m: "a", pr: 0 }, { m: "b", pr: 0 }, { m: "c", pr: 0 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    const body = document.getElementById("comboMembersBody");
    const rows = body.querySelectorAll("tr.member-row");
    stubRowRects(rows);
    const grip = rows[0].querySelector(".js-mem-drag");
    firePointer("pointerdown", grip, 5);   // start drag on row 0
    firePointer("pointermove", document, 35);
    firePointer("pointerup", document, 70); // y=70 -> before row 2 -> [b,a,c]
    await flush();
    expect(putsOf(stub.calls)).toEqual([
      ["/api/combos/5/members/11", 1],
      ["/api/combos/5/members/13", 2]
    ]);
    expect(shownModels()).toEqual(["b", "a", "c"]);
  });

  it("▲▼ still works after a drag has reordered the list", async () => {
    const stub = dragStub(dm([{ m: "a", pr: 0 }, { m: "b", pr: 0 }, { m: "c", pr: 0 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    await window.aigate.combos.reorderMembers(0, 2);
    await flush();
    stub.calls.length = 0;
    // ▲ on what is now the last row (c) moves it up one.
    document.querySelectorAll("#comboMembersBody tr.member-row")[2].querySelector(".js-mem-up").click();
    await flush();
    expect(shownModels()).toEqual(["b", "c", "a"]);
    // grip handles are still present after the drag + arrow chain.
    expect(document.querySelectorAll("#comboMembersBody .js-mem-drag").length).toBe(3);
  });

  it("clicking the grip alone (no drag) triggers no arrow/edit/delete action", async () => {
    const stub = dragStub(dm([{ m: "a", pr: 0 }, { m: "b", pr: 1 }, { m: "c", pr: 2 }]));
    await window.aigate.combos.openEditModal("5");
    await flush(3);
    stub.calls.length = 0;
    const grip = document.querySelectorAll("#comboMembersBody tr.member-row")[0].querySelector(".js-mem-drag");
    grip.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    await flush();
    expect(stub.calls).toHaveLength(0);
    expect(shownModels()).toEqual(["a", "b", "c"]);
  });
});

describe("combos members — move animation (▲▼ + drag flash, reduced-motion safe)", () => {
  // membersBuffer is module-internal, so reset it via openAddModal (which sets
  // membersBuffer=[] and renders empty) before each test — withComboModalDom
  // alone does NOT clear it.
  const realMatchMedia = window.matchMedia;
  beforeEach(async () => {
    withComboModalDom();
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true, headers: { get: () => "application/json" },
      json: () => Promise.resolve({ object: "list", data: [] })
    })));
    await window.aigate.combos.openAddModal(); // resets membersBuffer=[] + empty render
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    if (realMatchMedia) window.matchMedia = realMatchMedia;
    else delete window.matchMedia;
  });

  // Fill the buffer (new-combo mode: no network, synchronous render).
  function fillBuffer(c) {
    ["a", "b", "c"].forEach((m) =>
      c.bufferMemberLocal({ provider_id: 1, provider_model: m, weight: 1 }));
  }

  it("▲▼ move adds .just-moved to the moved row, then it is removed after the flash", () => {
    vi.useFakeTimers();
    try {
      const c = window.aigate.combos;
      fillBuffer(c);
      c.moveMember(0, 1); // a trades with b -> a now at index 1
      const moved = document.querySelector("#comboMembersBody tr.member-row.just-moved");
      expect(moved).not.toBeNull();
      expect(moved.querySelectorAll("td")[1].textContent).toBe("a");
      // Exactly one row flashes — neighbours are left alone.
      expect(document.querySelectorAll("#comboMembersBody tr.member-row.just-moved").length).toBe(1);
      vi.advanceTimersByTime(700);
      expect(document.querySelector("#comboMembersBody tr.member-row.just-moved")).toBeNull();
    } finally {
      vi.useRealTimers();
    }
  });

  it("drag reorder adds .just-moved to the dropped row (shared contract)", () => {
    const c = window.aigate.combos;
    fillBuffer(c);
    c.reorderMembers(0, 2); // move a to the end -> [b, c, a]
    const moved = document.querySelector("#comboMembersBody tr.member-row.just-moved");
    expect(moved).not.toBeNull();
    expect(moved.querySelectorAll("td")[1].textContent).toBe("a");
  });

  it("prefers-reduced-motion: no .just-moved is added (no animation under minimal motion)", () => {
    const orig = window.matchMedia;
    window.matchMedia = () => ({
      matches: true, addEventListener() {}, removeEventListener() {},
      addListener() {}, removeListener() {}
    });
    try {
      const c = window.aigate.combos;
      fillBuffer(c);
      c.moveMember(0, 1);
      expect(document.querySelector("#comboMembersBody tr.member-row.just-moved")).toBeNull();
      // Rows still render correctly.
      expect(document.querySelectorAll("#comboMembersBody tr.member-row").length).toBe(3);
    } finally {
      if (orig) window.matchMedia = orig; else delete window.matchMedia;
    }
  });

  it("reduced-motion / matchMedia path never throws (missing or throwing matchMedia)", () => {
    const orig = window.matchMedia;
    // Case 1: matchMedia missing entirely.
    delete window.matchMedia;
    try {
      const c = window.aigate.combos;
      fillBuffer(c);
      expect(() => c.moveMember(0, 1)).not.toThrow();
      expect(document.querySelectorAll("#comboMembersBody tr.member-row").length).toBe(3);
      // Case 2: matchMedia that throws.
      window.matchMedia = () => { throw new Error("no matchMedia"); };
      expect(() => c.moveMember(1, 1)).not.toThrow();
      expect(document.querySelectorAll("#comboMembersBody tr.member-row").length).toBe(3);
    } finally {
      if (orig) window.matchMedia = orig; else delete window.matchMedia;
    }
  });

  it("drag adds .is-dragging on grab and removes it on release (no-op drop)", () => {
    const c = window.aigate.combos;
    fillBuffer(c);
    const grip = document.querySelectorAll("#comboMembersBody tr.member-row")[0]
      .querySelector(".js-mem-drag");
    // jsdom returns all-zero rects; stub geometry so a clientY above row0 mid
    // (20) drops back on row 0 = no-op reorder (no re-render, tr stays put).
    Array.from(document.querySelectorAll("#comboMembersBody tr.member-row")).forEach((tr, i) => {
      tr.getBoundingClientRect = () => ({ top: i * 40, height: 40, bottom: (i + 1) * 40, left: 0, right: 100, width: 100 });
    });
    const down = new MouseEvent("pointerdown", { bubbles: true, cancelable: true });
    down.pointerId = 1;
    grip.dispatchEvent(down);
    expect(document.querySelectorAll("#comboMembersBody tr.member-row")[0]
      .classList.contains("is-dragging")).toBe(true);
    const up = new MouseEvent("pointerup", { bubbles: true, cancelable: true, clientY: 5 });
    up.pointerId = 1;
    document.dispatchEvent(up);
    expect(document.querySelectorAll("#comboMembersBody tr.member-row.is-dragging").length).toBe(0);
  });
});
