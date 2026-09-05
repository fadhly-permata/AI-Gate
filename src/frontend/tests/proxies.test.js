import { describe, it, expect, vi, beforeEach } from "vitest";

import "../static/i18n.js";
import "../static/app.js";
import "../static/proxies.js";

function withDom() {
  document.body.innerHTML =
    '<p id="poolMsg"></p>' +
    '<table id="poolTable"><tbody id="poolTableBody"></tbody></table>';
}

describe("proxies (Proxy Pools) mapper + render (B2.3)", () => {
  beforeEach(() => { withDom(); });

  it("mapPoolToRow flattens a ProxyPoolDTO and counts nodes", () => {
    const row = window.aigate.proxies.mapPoolToRow({
      id: 3, name: "P", rotation_strategy: "round_robin", enabled: true,
      nodes: [{ id: 1 }, { id: 2 }, { id: 3 }]
    });
    expect(row).toEqual({
      id: 3, name: "P", strategy: "round_robin", enabled: true, nodeCount: 3
    });
  });

  it("mapPoolToRow treats missing nodes as 0", () => {
    const row = window.aigate.proxies.mapPoolToRow({ id: 1 });
    expect(row.nodeCount).toBe(0);
    expect(row.enabled).toBe(false);
  });

  it("renderPools renders rows with edit/delete/health buttons", () => {
    window.aigate.proxies.renderPools([
      { id: 9, name: "Pool A", rotation_strategy: "random", enabled: false, nodes: [] }
    ]);
    const html = document.getElementById("poolTableBody").innerHTML;
    expect(html).toContain('data-id="9"');
    expect(html).toContain("Pool A");
    expect(html).toContain("js-edit");
    expect(html).toContain("js-del");
    expect(html).toContain("js-check");
  });

  it("renderPools shows the empty-state message when there are no items", () => {
    window.aigate.proxies.renderPools([]);
    expect(document.getElementById("poolTableBody").innerHTML)
      .toContain("No proxy pools yet.");
  });

  it("loadPools fetches /api/proxy-pools and renders", async () => {
    const data = {
      object: "list",
      data: [{ id: 4, name: "P1", rotation_strategy: "random", enabled: true, nodes: [{}] }]
    };
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(data)
    })));
    await window.aigate.proxies.loadPools();
    expect(document.getElementById("poolTableBody").innerHTML).toContain("P1");
    vi.unstubAllGlobals();
  });

  it("healthCheck POSTs to /api/proxy-pools/{id}/health-check and reports results", async () => {
    const urls = [];
    vi.stubGlobal("fetch", vi.fn((url) => {
      urls.push(url);
      return Promise.resolve({
        ok: true,
        headers: { get: () => "application/json" },
        json: () => Promise.resolve({ ok: true, results: [{ status: "healthy" }, { status: "dead" }] })
      });
    }));
    await window.aigate.proxies.healthCheck(4);
    // health-check runs first, then loadPools() refreshes the list.
    expect(urls).toContain("/api/proxy-pools/4/health-check");
    expect(document.getElementById("poolMsg").textContent).toContain("1/2");
    vi.unstubAllGlobals();
  });
});
