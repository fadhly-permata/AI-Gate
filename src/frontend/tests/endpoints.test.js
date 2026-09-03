import { describe, it, expect, vi, beforeEach } from "vitest";

import "../static/i18n.js";
import "../static/app.js";
import "../static/endpoints.js";

function withDom() {
  document.body.innerHTML =
    '<p id="endpointMsg"></p>' +
    '<table id="endpointTable"><tbody id="endpointTableBody"></tbody></table>';
}

describe("endpoints mapper + render (B2.5)", () => {
  beforeEach(() => { withDom(); });

  it("mapEndpointToRow builds listen addr and binding text", () => {
    const row = window.aigate.endpoints.mapEndpointToRow({
      id: 1, name: "E", listen_host: "0.0.0.0", listen_port: 9000,
      access_control_enabled: true, proxy_pool_id: 5,
      binding: { bind_type: "provider", bind_id: 12 }
    });
    expect(row.listen).toBe("0.0.0.0:9000");
    expect(row.enabled).toBe(true);
    expect(row.proxy_pool_id).toBe(5);
    expect(row.binding_text).toBe("provider:12");
  });

  it("mapEndpointToRow falls back to defaults and '—' when no binding", () => {
    const row = window.aigate.endpoints.mapEndpointToRow({ id: 2, name: "E2" });
    expect(row.listen).toBe("127.0.0.1:8000");
    expect(row.enabled).toBe(false);
    expect(row.proxy_pool_id).toBeNull();
    expect(row.binding_text).toBe("—");
  });

  it("renderEndpoints renders rows with edit/delete buttons", () => {
    window.aigate.endpoints.renderEndpoints([
      { id: 8, name: "EP", listen_host: "127.0.0.1", listen_port: 8000,
        access_control_enabled: false, proxy_pool_id: null, binding: null }
    ]);
    const html = document.getElementById("endpointTableBody").innerHTML;
    expect(html).toContain('data-id="8"');
    expect(html).toContain("EP");
    expect(html).toContain("js-edit");
    expect(html).toContain("js-del");
  });

  it("renderEndpoints shows the empty-state message when there are no items", () => {
    window.aigate.endpoints.renderEndpoints([]);
    expect(document.getElementById("endpointTableBody").innerHTML)
      .toContain("No endpoints yet.");
  });

  it("loadEndpoints fetches /api/endpoints and renders", async () => {
    const data = {
      object: "list",
      data: [{ id: 5, name: "API", listen_host: "0.0.0.0", listen_port: 8080,
               access_control_enabled: true, proxy_pool_id: 2,
               binding: { bind_type: "combo", bind_id: 3 } }]
    };
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(data)
    })));
    await window.aigate.endpoints.loadEndpoints();
    const html = document.getElementById("endpointTableBody").innerHTML;
    expect(html).toContain("API");
    expect(html).toContain("combo:3");
    vi.unstubAllGlobals();
  });
});
