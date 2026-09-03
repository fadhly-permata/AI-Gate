import { describe, it, expect, vi, beforeEach } from "vitest";

// i18n dict (window.I18N) so getStr() resolves labels during render.
import "../static/i18n.js";
// app.js exposes window.aigate.fetchJson / escapeHtml / getStr used by the module.
import "../static/app.js";
// The Combos module registers window.aigate.combos and wires its DOM (guarded).
import "../static/combos.js";

function withDom() {
  document.body.innerHTML =
    '<p id="comboMsg"></p>' +
    '<table id="comboTable"><tbody id="comboTableBody"></tbody></table>';
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
