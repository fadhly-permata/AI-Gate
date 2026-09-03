import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { JSDOM } from "jsdom";

// i18n dict (window.I18N) so getStr() resolves labels during render.
import "../static/i18n.js";
// app.js exposes window.aigate.fetchJson / escapeHtml / getStr used by the module.
import "../static/app.js";
// usage.js exposes the shared formatters (formatTokens/formatCost/...) that
// analytics.js delegates to — same load order as index.html.
import "../static/usage.js";
// The Analytics module registers window.aigate.analytics + render/load helpers.
import "../static/analytics.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Let async .then chains resolve.
const flushAll = () => new Promise((r) => setTimeout(r, 0));

// Build the analytics view DOM the render/load functions expect.
function withAnalyticsDom() {
  document.body.innerHTML =
    '<p id="analyticsMsg"></p>' +
    '<select id="analyticsRange">' +
      '<option value="day">day</option>' +
      '<option value="week">week</option>' +
      '<option value="month" selected>month</option>' +
    '</select>' +
    '<select id="analyticsGroup">' +
      '<option value="model" selected>model</option>' +
      '<option value="provider">provider</option>' +
    '</select>' +
    '<select id="analyticsMetric">' +
      '<option value="tokens" selected>tokens</option>' +
      '<option value="requests">requests</option>' +
      '<option value="cost">cost</option>' +
    '</select>' +
    '<button id="analyticsRefreshBtn" type="button">Refresh</button>' +
    '<div id="analyticsTotals"></div>' +
    '<div id="analyticsChart"></div>' +
    '<table><tbody id="analyticsGroupBody"></tbody></table>' +
    '<input type="checkbox" id="reqlogEnabled" />' +
    '<button id="reqlogRefreshBtn" type="button">Refresh</button>' +
    '<p id="reqlogMsg"></p>' +
    '<table><tbody id="reqlogTableBody"></tbody></table>';
}

// REAL backend shapes (verbatim from the be-dev receipt).
const ANALYTICS_PAYLOAD = {
  object: "analytics", range: "month", group_by: "model",
  buckets: [
    { label: "2026-09-01", requests: 2, tokens_in: 110, tokens_out: 60,
      cost_est: 0.11, saved_tokens_est: 8 },
    { label: "2026-09-02", requests: 0, tokens_in: 0, tokens_out: 0,
      cost_est: 0, saved_tokens_est: 0 },
    { label: "2026-09-03", requests: 2, tokens_in: 21, tokens_out: 21,
      cost_est: 0.021, saved_tokens_est: 4 }
  ],
  totals: { requests: 4, tokens_in: 131, tokens_out: 81, cost_est: 0.131,
            saved_tokens_est: 12 },
  by_group: [
    { key: "gpt-4o", requests: 3, tokens_in: 111, tokens_out: 61,
      cost_est: 0.111, saved_tokens_est: 8 },
    { key: "claude-3-5-sonnet", requests: 1, tokens_in: 20, tokens_out: 20,
      cost_est: 0.02, saved_tokens_est: 4 }
  ]
};

// request/response arrive as JSON STRINGS (headers redacted server-side).
const REQLOG_PAYLOAD = {
  object: "list",
  data: [
    {
      id: 3, endpoint_id: 1, model: "gpt-4o", ts: "2026-09-03T10:00:00",
      duration_ms: 300,
      request: '{"headers":{"authorization":"Bearer redacted"},"body":{"model":"gpt-4o","messages":[{"role":"user","content":"hi"}]}}',
      response: '{"status":"ok","choices":[{"message":{"content":"hello"}}]}'
    },
    {
      id: 2, endpoint_id: 2, model: "claude-3-5-sonnet", ts: "2026-09-03T09:59:00",
      duration_ms: 250,
      // cut mid-payload -> no longer parses + carries the truncation marker
      request: '{"headers":{"x":"y"},"body":{"messages":[{"content":"very long… [truncated 1234 chars]',
      response: '{"status":"ok"}'
    }
  ]
};

const SETTINGS_PAYLOAD = {
  port: "8080", dev_mode: "false", theme: "light", locale: "en",
  request_log_enabled: "true"
};

function stubFetchFor(payloads) {
  const calls = [];
  vi.stubGlobal("fetch", vi.fn((url, opts) => {
    calls.push({ url, opts });
    const key = Object.keys(payloads).find((k) => url.indexOf(k) !== -1);
    const body = key ? payloads[key] : { object: "list", data: [] };
    return Promise.resolve({
      ok: true,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve(body)
    });
  }));
  return calls;
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("parseMaybeJson (pure)", () => {
  it("parses a valid JSON string", () => {
    const r = window.aigate.parseMaybeJson('{"a":1,"b":[2,3]}');
    expect(r.ok).toBe(true);
    expect(r.value).toEqual({ a: 1, b: [2, 3] });
    expect(r.truncated).toBe(false);
  });
  it("invalid JSON -> ok:false with the raw text preserved", () => {
    const r = window.aigate.parseMaybeJson("not json {{{");
    expect(r.ok).toBe(false);
    expect(r.raw).toBe("not json {{{");
  });
  it("detects the ...[truncated N chars] marker", () => {
    const r = window.aigate.parseMaybeJson(
      '{"headers":{"x":"y"},"body":{"messages":[{"content":"long… [truncated 1234 chars]');
    expect(r.ok).toBe(false);
    expect(r.truncated).toBe(true);
    expect(r.raw).toContain("[truncated 1234 chars]");
  });
  it("null / empty -> ok:false, empty raw", () => {
    expect(window.aigate.parseMaybeJson(null)).toEqual(
      { ok: false, raw: "", truncated: false });
    expect(window.aigate.parseMaybeJson("").ok).toBe(false);
  });
});

describe("renderAnalytics (real /api/analytics shape)", () => {
  beforeEach(() => { withAnalyticsDom(); });

  it("renders totals cards incl. estimated savings", () => {
    window.aigate.renderAnalytics(ANALYTICS_PAYLOAD);
    const totals = document.getElementById("analyticsTotals");
    const text = totals.textContent;
    expect(text).toContain("4");          // requests
    expect(text).toContain("131");        // tokens_in
    expect(text).toContain("81");         // tokens_out
    expect(text).toContain("$0.131");     // cost_est
    expect(text).toContain("12");         // saved_tokens_est
    expect(text).toContain("Est. savings (tokens)");
    expect(totals.querySelectorAll(".usage-stat").length).toBe(5);
  });

  it("renders the by_group table rows (key + metrics + savings)", () => {
    window.aigate.renderAnalytics(ANALYTICS_PAYLOAD);
    const body = document.getElementById("analyticsGroupBody");
    const rows = body.querySelectorAll(".analytics-group-row");
    expect(rows.length).toBe(2);
    expect(body.innerHTML).toContain("gpt-4o");
    expect(body.innerHTML).toContain("claude-3-5-sonnet");
    expect(rows[0].textContent).toContain("$0.111");
    expect(rows[0].textContent).toContain("111");
  });

  it("renders the trend chart from buckets", () => {
    window.aigate.renderAnalytics(ANALYTICS_PAYLOAD);
    expect(document.querySelectorAll("#analyticsChart .trend-bar").length)
      .toBe(3);
  });

  it("escapes group keys (XSS)", () => {
    window.aigate.renderAnalytics({
      totals: {}, buckets: [],
      by_group: [{ key: "<img src=x>", requests: 1 }]
    });
    const html = document.getElementById("analyticsGroupBody").innerHTML;
    expect(html).toContain("&lt;img src=x&gt;");
    expect(html).not.toContain("<img src=x>");
  });
});

describe("renderTrendChart (CSS bars, no chart lib)", () => {
  beforeEach(() => { withAnalyticsDom(); });

  it("produces one bar per bucket incl. zero buckets, with labels", () => {
    window.aigate.renderTrendChart(ANALYTICS_PAYLOAD.buckets);
    const bars = document.querySelectorAll("#analyticsChart .trend-bar");
    expect(bars.length).toBe(3);
    const cols = document.querySelectorAll("#analyticsChart .trend-col");
    expect(cols.length).toBe(3);
    const html = document.getElementById("analyticsChart").innerHTML;
    expect(html).toContain("2026-09-01");
    // zero bucket -> flat baseline tick, not a full-height bar
    expect(bars[1].className).toContain("trend-bar-zero");
  });

  it("scales bar heights to the max of the selected metric", () => {
    window.aigate.renderTrendChart(ANALYTICS_PAYLOAD.buckets, "tokens");
    const bars = document.querySelectorAll("#analyticsChart .trend-bar");
    // tokens: 170 / 0 / 42 -> max 170 -> 100% and 42/170 = 24.7%
    expect(bars[0].getAttribute("style")).toContain("height:100.0%");
    expect(bars[2].getAttribute("style")).toContain("height:24.7%");
  });

  it("requests metric uses the requests field", () => {
    window.aigate.renderTrendChart(ANALYTICS_PAYLOAD.buckets, "requests");
    const bars = document.querySelectorAll("#analyticsChart .trend-bar");
    expect(bars[0].getAttribute("style")).toContain("height:100.0%");
    expect(bars[2].getAttribute("style")).toContain("height:100.0%");
  });

  it("thins x labels on crowded ranges (24 hourly buckets -> 12 labels)", () => {
    const hourly = [];
    for (let i = 0; i < 24; i++) {
      hourly.push({ label: "2026-09-03 " + (i < 10 ? "0" + i : i) + ":00",
                    requests: 1, tokens_in: 10, tokens_out: 5,
                    cost_est: 0.01, saved_tokens_est: 0 });
    }
    window.aigate.renderTrendChart(hourly);
    const labels = document.querySelectorAll("#analyticsChart .trend-label");
    expect(labels.length).toBe(24);
    const shown = Array.prototype.filter.call(labels,
      (l) => l.textContent !== "").length;
    expect(shown).toBe(12);
    expect(labels[0].textContent).toBe("2026-09-03 00:00");
    expect(labels[1].textContent).toBe("");
  });

  it("empty buckets -> empty-state message", () => {
    window.aigate.renderTrendChart([]);
    expect(document.getElementById("analyticsChart").textContent)
      .toContain("No data.");
  });
});

describe("renderByGroup empty state", () => {
  beforeEach(() => { withAnalyticsDom(); });
  it("empty list -> analytics.no_data row", () => {
    window.aigate.renderByGroup([]);
    expect(document.getElementById("analyticsGroupBody").innerHTML)
      .toContain("No data.");
  });
});

describe("renderRequestLogs (real /api/request-logs shape)", () => {
  beforeEach(() => { withAnalyticsDom(); });

  it("renders ts / model / endpoint / duration rows", () => {
    window.aigate.renderRequestLogs(REQLOG_PAYLOAD.data);
    const rows = document.querySelectorAll("#reqlogTableBody .reqlog-row");
    expect(rows.length).toBe(2);
    const first = rows[0];
    expect(first.textContent).toContain("2026-09-03 10:00:00"); // T->space
    expect(first.textContent).toContain("gpt-4o");
    expect(first.textContent).toContain("300 ms");
    expect(first.getAttribute("data-id")).toBe("3");
  });

  it("pretty-prints parsed request/response JSON inside <details>", () => {
    window.aigate.renderRequestLogs(REQLOG_PAYLOAD.data);
    const first = document.querySelector("#reqlogTableBody .reqlog-row");
    const pres = first.querySelectorAll("pre");
    expect(pres.length).toBe(2); // request + response
    // JSON.stringify(value, null, 2) -> indented key: value line
    expect(pres[0].textContent).toContain('"authorization": "Bearer redacted"');
    expect(pres[1].textContent).toContain('"status": "ok"');
    expect(first.querySelector("details")).not.toBeNull();
  });

  it("unparseable truncated payload -> raw text shown + truncation note", () => {
    window.aigate.renderRequestLogs(REQLOG_PAYLOAD.data);
    const rows = document.querySelectorAll("#reqlogTableBody .reqlog-row");
    const second = rows[1];
    const pre = second.querySelectorAll("pre")[0];
    expect(pre.textContent).toContain("[truncated 1234 chars]");
    expect(second.querySelector(".reqlog-truncated")).not.toBeNull();
    expect(second.textContent).toContain("payload truncated");
    // the valid response block on the same row has NO truncation note
    expect(second.querySelectorAll(".reqlog-truncated").length).toBe(1);
  });

  it("empty list -> reqlog.empty message", () => {
    window.aigate.renderRequestLogs([]);
    expect(document.getElementById("reqlogTableBody").innerHTML)
      .toContain("Request logging is off or no logs yet.");
  });

  it("escapes payload text (XSS)", () => {
    window.aigate.renderRequestLogs([{
      id: 1, endpoint_id: 1, model: "<script>alert(1)</script>",
      ts: "2026-09-03T00:00:00", duration_ms: 1,
      request: "<img src=x>", response: "{}"
    }]);
    const html = document.getElementById("reqlogTableBody").innerHTML;
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).toContain("&lt;script&gt;");
    expect(html).toContain("&lt;img src=x&gt;");
  });
});

describe("loadAnalytics / loadRequestLogs hit the right URLs", () => {
  beforeEach(() => { withAnalyticsDom(); });

  it("loadAnalytics GETs range+group_by URL and renders", async () => {
    const calls = stubFetchFor({ "/api/analytics": ANALYTICS_PAYLOAD });
    const data = await window.aigate.loadAnalytics("month", "provider");
    expect(calls.some((c) =>
      c.url === "/api/analytics?range=month&group_by=provider")).toBe(true);
    expect(data.object).toBe("analytics");
    expect(document.getElementById("analyticsTotals").textContent)
      .toContain("$0.131");
    expect(document.querySelectorAll("#analyticsChart .trend-bar").length)
      .toBe(3);
  });

  it("loadAnalytics falls back to the control values", async () => {
    const calls = stubFetchFor({ "/api/analytics": ANALYTICS_PAYLOAD });
    await window.aigate.loadAnalytics();
    expect(calls.some((c) =>
      c.url === "/api/analytics?range=month&group_by=model")).toBe(true);
  });

  it("loadRequestLogs GETs /api/request-logs?limit= and renders rows", async () => {
    const calls = stubFetchFor({ "/api/request-logs": REQLOG_PAYLOAD });
    const list = await window.aigate.loadRequestLogs();
    expect(calls.some((c) => c.url === "/api/request-logs?limit=50")).toBe(true);
    expect(list.length).toBe(2);
    expect(document.querySelectorAll("#reqlogTableBody .reqlog-row").length)
      .toBe(2);
  });

  it("loadRequestLogs honors a custom limit", async () => {
    const calls = stubFetchFor({ "/api/request-logs": REQLOG_PAYLOAD });
    await window.aigate.loadRequestLogs(10);
    expect(calls.some((c) => c.url === "/api/request-logs?limit=10")).toBe(true);
  });

  it("surfaces backend 400 error text in the status line (ADR-011)", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: false, status: 400,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({
        error: { message: "range must be day|week|month",
                 type: "invalid_request_error", code: "invalid_range" }
      })
    })));
    await window.aigate.loadAnalytics("nope", "model");
    const msg = document.getElementById("analyticsMsg");
    expect(msg.textContent).toContain("range must be day|week|month");
    expect(msg.className).toContain("settings-msg-error");
  });
});

describe("setRequestLogEnabled (PUT /api/settings)", () => {
  beforeEach(() => { withAnalyticsDom(); });

  it("PUTs {key:'request_log_enabled', value:'true'} then reloads logs", async () => {
    const calls = stubFetchFor({
      "/api/settings": { ok: true },
      "/api/request-logs": REQLOG_PAYLOAD
    });
    await window.aigate.setRequestLogEnabled(true);
    const put = calls.find((c) => c.opts && c.opts.method === "PUT");
    expect(put).toBeDefined();
    expect(put.url).toBe("/api/settings");
    expect(JSON.parse(put.opts.body))
      .toEqual({ key: "request_log_enabled", value: "true" });
    // follow-up refresh of the log table
    expect(calls.some((c) => c.url === "/api/request-logs?limit=50")).toBe(true);
    expect(document.getElementById("reqlogMsg").textContent)
      .toContain("Request logging enabled.");
  });

  it("sends 'false' when disabling", async () => {
    const calls = stubFetchFor({ "/api/settings": { ok: true } });
    await window.aigate.setRequestLogEnabled(false);
    const put = calls.find((c) => c.opts && c.opts.method === "PUT");
    expect(JSON.parse(put.opts.body).value).toBe("false");
  });

  it("on failure: reverts the checkbox + surfaces the error (ADR-011)", async () => {
    const cb = document.getElementById("reqlogEnabled");
    cb.checked = true;
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({
      ok: false, status: 400,
      headers: { get: () => "application/json" },
      json: () => Promise.resolve({
        error: { message: "unknown settings key",
                 type: "invalid_request_error", code: "invalid_key" }
      })
    })));
    await window.aigate.setRequestLogEnabled(true);
    expect(cb.checked).toBe(false); // reverted
    const msg = document.getElementById("reqlogMsg");
    expect(msg.textContent).toContain("unknown settings key");
    expect(msg.className).toContain("settings-msg-error");
  });
});

describe("loadRequestLogSetting (GET /api/settings)", () => {
  beforeEach(() => { withAnalyticsDom(); });

  it("syncs the checkbox from the stored flag", async () => {
    stubFetchFor({ "/api/settings": SETTINGS_PAYLOAD });
    const on = await window.aigate.analytics.loadRequestLogSetting();
    expect(on).toBe(true);
    expect(document.getElementById("reqlogEnabled").checked).toBe(true);
  });

  it("absent/false flag leaves the checkbox unchecked", async () => {
    stubFetchFor({ "/api/settings": {
      port: "8080", request_log_enabled: "false" } });
    const on = await window.aigate.analytics.loadRequestLogSetting();
    expect(on).toBe(false);
    expect(document.getElementById("reqlogEnabled").checked).toBe(false);
  });
});

describe("analytics.onShow loads dashboard + setting + logs", () => {
  beforeEach(() => { withAnalyticsDom(); });

  it("fires the three initial GETs", async () => {
    const calls = stubFetchFor({
      "/api/analytics": ANALYTICS_PAYLOAD,
      "/api/settings": SETTINGS_PAYLOAD,
      "/api/request-logs": REQLOG_PAYLOAD
    });
    window.aigate.analytics.onShow();
    await Promise.resolve(); await Promise.resolve(); await flushAll();
    expect(calls.some((c) =>
      c.url === "/api/analytics?range=month&group_by=model")).toBe(true);
    expect(calls.some((c) => c.url === "/api/settings")).toBe(true);
    expect(calls.some((c) => c.url === "/api/request-logs?limit=50")).toBe(true);
    expect(document.getElementById("analyticsTotals").textContent)
      .toContain("$0.131");
  });
});

describe("index.html wiring (B5.6 structure)", () => {
  const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
  const dom = new JSDOM(html);
  const doc = dom.window.document;

  it("sidebar nav has the Analytics item", () => {
    const item = doc.querySelector('.nav-item[data-view="analytics"]');
    expect(item).not.toBeNull();
    expect(item.querySelector("[data-i18n='nav.analytics']")).not.toBeNull();
  });

  it("analytics view section exists with all containers", () => {
    const view = doc.querySelector('.view[data-view="analytics"]');
    expect(view).not.toBeNull();
    ["analyticsMsg", "analyticsRange", "analyticsGroup", "analyticsMetric",
     "analyticsRefreshBtn", "analyticsTotals", "analyticsChart",
     "analyticsGroupBody", "reqlogEnabled", "reqlogRefreshBtn", "reqlogMsg",
     "reqlogTableBody"]
      .forEach((id) => expect(view.querySelector("#" + id)).not.toBeNull());
  });

  it("loads analytics.js after app.js + usage.js", () => {
    const srcs = Array.from(doc.querySelectorAll("script[src]"))
      .map((s) => s.getAttribute("src"));
    expect(srcs).toContain("analytics.js");
    expect(srcs.indexOf("app.js")).toBeLessThan(srcs.indexOf("analytics.js"));
    expect(srcs.indexOf("usage.js")).toBeLessThan(srcs.indexOf("analytics.js"));
  });
});

describe("i18n analytics/reqlog keys (EN/ID parity)", () => {
  it("every analytics.* / reqlog.* / nav.analytics key exists in both dicts", () => {
    const enKeys = Object.keys(window.I18N.en).filter(
      (k) => k.indexOf("analytics.") === 0 || k.indexOf("reqlog.") === 0 ||
             k === "nav.analytics");
    expect(enKeys.length).toBeGreaterThan(20);
    enKeys.forEach((k) => {
      expect(window.I18N.id[k]).toBeDefined();
    });
    expect(window.I18N.en["nav.analytics"]).toBe("Analytics");
    expect(window.I18N.id["nav.analytics"]).toBe("Analitik");
    expect(window.I18N.en["analytics.savings"]).toBe("Est. savings (tokens)");
    expect(window.I18N.id["reqlog.enable"]).toBe("Aktifkan log permintaan");
  });
});
