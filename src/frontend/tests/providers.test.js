import { describe, it, expect } from "vitest";

// i18n.js attaches window.I18N + window.applyLocale (jsdom provides DOM).
import "../static/i18n.js";
// app.js wires the UI and exposes window.aigate.mapProviderToRow /
// window.aigate.buildHeadersDict / window.aigate.headersToRows.
import "../static/app.js";

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
