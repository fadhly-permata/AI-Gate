import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { JSDOM } from "jsdom";

// i18n dict (window.I18N) so getStr() resolves labels during render.
import "../static/i18n.js";
// app.js exposes window.aigate.fetchJson / escapeHtml / getStr used by the module.
import "../static/app.js";
// The Usage module registers window.aigate.usage + render/load/format helpers.
import "../static/usage.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Let async .then chains resolve.
const flush = () => new Promise((r) => setTimeout(r, 0));

// Build the usage view DOM the render/load functions expect.
function withUsageDom() {
  document.body.innerHTML =
    '<p id="usageMsg"></p>' +
    '<select id="usageRange">' +
      '<option value="day" selected>day</option>' +
      '<option value="week">week</option>' +
      '<option value="month">month</option>' +
    '</select>' +
    '<button id="usageRefreshBtn" type="button">Refresh</button>' +
    '<table><tbody id="quotaTableBody"></tbody></table>' +
    '<div id="usageTotals"></div>' +
    '<table><tbody id="usageProviderBody"></tbody></table>' +
    '<table><tbody id="usageModelBody"></tbody></table>' +
    '<table><tbody id="recentUsageBody"></tbody></table>' +
    '<p id="provUsageMsg"></p>' +
    '<div id="provUsageTotals"></div>' +
    '<table><tbody id="provUsageModelBody"></tbody></table>';
}

// REAL backend shapes (verbatim from the be-dev receipt).
const QUOTA_PAYLOAD = {
  object: "list",
  data: [
    {
      provider_id: 1, provider_name: "alpha", tier: "subscription",
      quota_limit: 1000, quota_window: "day", used: 300, remaining: 700,
      unlimited: false, window_start: "2026-09-03T00:00:00",
      reset_at: "2026-09-04T00:00:00", seconds_to_reset: 60479,
      cost_est: 0.00225
    },
    {
      provider_id: 2, provider_name: "beta", tier: "free",
      quota_limit: null, quota_window: "day", used: 5, remaining: null,
      unlimited: true, window_start: "2026-09-03T00:00:00",
      reset_at: "2026-09-04T00:00:00", seconds_to_reset: null,
      cost_est: 0
    }
  ]
};

const SUMMARY_PAYLOAD = {
  object: "usage_summary", range: "day", since: "2026-09-02T07:12:03",
  totals: { requests: 3, tokens_in: 310, tokens_out: 160, cost_est: 0.033 },
  by_provider: [
    { provider_id: 1, provider_name: "alpha", requests: 2,
      tokens_in: 300, tokens_out: 150, cost_est: 0.03 }
  ],
  by_model: [
    { model: "gpt-4o", requests: 2,
      tokens_in: 300, tokens_out: 150, cost_est: 0.03 }
  ]
};

const USAGE_LIST_PAYLOAD = {
  object: "list", range: "day",
  data: [
    { id: 1, endpoint_id: null, provider_id: 1, account_id: null,
      model: "gpt-4o", tokens_in: 1, tokens_out: 2,
      cost_est: 0.0000225, ts: "2026-09-03T07:12:03.123456" }
  ]
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
  window.aigate.stopUsageAutoRefresh();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("formatCountdown (pure, seconds-based per real API)", () => {
  it("formats seconds_to_reset like the real payload", () => {
    expect(window.aigate.formatCountdown(60479)).toBe("16h 47m");
    expect(window.aigate.formatCountdown(7560)).toBe("2h 6m");
    expect(window.aigate.formatCountdown(3600)).toBe("1h 0m");
  });
  it("formats sub-hour and sub-minute values", () => {
    expect(window.aigate.formatCountdown(120)).toBe("2m");
    expect(window.aigate.formatCountdown(59)).toBe("59s");
    expect(window.aigate.formatCountdown(0)).toBe("0s");
  });
  it("null / invalid -> em dash", () => {
    expect(window.aigate.formatCountdown(null)).toBe("\u2014");
    expect(window.aigate.formatCountdown(undefined)).toBe("\u2014");
    expect(window.aigate.formatCountdown("nope")).toBe("\u2014");
  });
});

describe("formatTokens / formatNumber / formatCost (pure)", () => {
  it("formatTokens: thousands separators, then K / M", () => {
    expect(window.aigate.formatTokens(310)).toBe("310");
    expect(window.aigate.formatTokens(1000)).toBe("1,000");
    expect(window.aigate.formatTokens(12345)).toBe("12,345");
    expect(window.aigate.formatTokens(150000)).toBe("150K");
    expect(window.aigate.formatTokens(1500000)).toBe("1.5M");
    expect(window.aigate.formatTokens(null)).toBe("0");
  });
  it("formatNumber: plain integer with separators", () => {
    expect(window.aigate.formatNumber(3)).toBe("3");
    expect(window.aigate.formatNumber(12345)).toBe("12,345");
  });
  it("formatCost: compact currency", () => {
    expect(window.aigate.formatCost(0.033)).toBe("$0.033");
    expect(window.aigate.formatCost(0.03)).toBe("$0.03");
    expect(window.aigate.formatCost(0.00225)).toBe("$0.00225");
    expect(window.aigate.formatCost(12.5)).toBe("$12.50");
    expect(window.aigate.formatCost(0)).toBe("$0.00");
    expect(window.aigate.formatCost(null)).toBe("\u2014");
  });
});

describe("renderQuota (real /api/quota shape)", () => {
  beforeEach(() => { withUsageDom(); });

  it("renders used/limit, progress bar, countdown and cost", () => {
    window.aigate.renderQuota(QUOTA_PAYLOAD.data);
    const html = document.getElementById("quotaTableBody").innerHTML;
    expect(html).toContain("alpha");
    expect(html).toContain("300 / 1,000");
    expect(html).toContain("16h 47m");
    expect(html).toContain("usage-progress-fill");
    expect(html).toContain("width:30.0%");
    expect(html).toContain("$0.00225");
    expect(html).toContain("subscription");
    // remaining surfaced via title (plaintext, no masking)
    expect(html).toContain("Remaining: 700");
  });

  it("unlimited:true hides the progress bar and shows 'unlimited'", () => {
    window.aigate.renderQuota(QUOTA_PAYLOAD.data);
    const rows = document.querySelectorAll("#quotaTableBody .quota-row");
    expect(rows.length).toBe(2);
    const beta = rows[1];
    expect(beta.innerHTML).not.toContain("usage-progress-fill");
    expect(beta.textContent).toContain("unlimited");
    expect(beta.querySelector(".quota-reset").textContent).toBe("\u2014");
    // alpha (limited) DOES have the bar
    expect(rows[0].innerHTML).toContain("usage-progress-fill");
  });

  it("empty list -> empty-state message", () => {
    window.aigate.renderQuota([]);
    expect(document.getElementById("quotaTableBody").innerHTML)
      .toContain("No data.");
  });

  it("escapes provider names (XSS)", () => {
    window.aigate.renderQuota([{ provider_id: 1, provider_name: "<img src=x>",
      tier: "free", quota_limit: 10, used: 1, remaining: 9,
      unlimited: false, seconds_to_reset: 5, cost_est: 0 }]);
    const html = document.getElementById("quotaTableBody").innerHTML;
    expect(html).toContain("&lt;img src=x&gt;");
    expect(html).not.toContain("<img src=x>");
  });
});

describe("renderUsageSummary (real /api/usage/summary shape)", () => {
  beforeEach(() => { withUsageDom(); });

  it("renders totals cards + by_provider + by_model", () => {
    window.aigate.renderUsageSummary(SUMMARY_PAYLOAD);
    const totals = document.getElementById("usageTotals").textContent;
    expect(totals).toContain("3");        // requests
    expect(totals).toContain("310");      // tokens_in
    expect(totals).toContain("160");      // tokens_out
    expect(totals).toContain("$0.033");   // cost_est
    expect(document.getElementById("usageProviderBody").innerHTML)
      .toContain("alpha");
    expect(document.getElementById("usageModelBody").innerHTML)
      .toContain("gpt-4o");
  });

  it("empty breakdowns show the empty-state", () => {
    window.aigate.renderUsageSummary({
      totals: { requests: 0, tokens_in: 0, tokens_out: 0, cost_est: 0 },
      by_provider: [], by_model: []
    });
    expect(document.getElementById("usageProviderBody").innerHTML)
      .toContain("No data.");
    expect(document.getElementById("usageModelBody").innerHTML)
      .toContain("No data.");
  });
});

describe("renderRecentUsage (real /api/usage shape)", () => {
  beforeEach(() => { withUsageDom(); });

  it("renders model / tokens / cost / ts rows", () => {
    window.aigate.renderRecentUsage(USAGE_LIST_PAYLOAD.data);
    const html = document.getElementById("recentUsageBody").innerHTML;
    expect(html).toContain("gpt-4o");
    expect(html).toContain("$0.000023"); // 0.0000225 rounded at 6dp
    expect(html).toContain("2026-09-03 07:12:03"); // T->space, fraction trimmed
  });
});

describe("loadQuota / loadUsageSummary / loadUsage hit the right URLs", () => {
  beforeEach(() => { withUsageDom(); });

  it("loadQuota GETs /api/quota and renders", async () => {
    const calls = stubFetchFor({ "/api/quota": QUOTA_PAYLOAD });
    const list = await window.aigate.loadQuota();
    expect(calls.some((c) => c.url === "/api/quota")).toBe(true);
    expect(list.length).toBe(2);
    expect(document.getElementById("quotaTableBody").innerHTML).toContain("alpha");
  });

  it("loadUsageSummary GETs range-only URL", async () => {
    const calls = stubFetchFor({ "/api/usage/summary": SUMMARY_PAYLOAD });
    await window.aigate.loadUsageSummary("week");
    expect(calls.some((c) => c.url === "/api/usage/summary?range=week")).toBe(true);
    expect(document.getElementById("usageTotals").textContent).toContain("$0.033");
  });

  it("loadUsageSummary GETs provider-filtered URL", async () => {
    const calls = stubFetchFor({ "/api/usage/summary": SUMMARY_PAYLOAD });
    await window.aigate.loadUsageSummary("day", 1);
    expect(calls.some((c) =>
      c.url === "/api/usage/summary?range=day&provider_id=1")).toBe(true);
  });

  it("loadUsage GETs /api/usage?range= and renders recent rows", async () => {
    const calls = stubFetchFor({ "/api/usage?": USAGE_LIST_PAYLOAD });
    await window.aigate.loadUsage("month");
    expect(calls.some((c) => c.url === "/api/usage?range=month")).toBe(true);
    expect(document.getElementById("recentUsageBody").innerHTML).toContain("gpt-4o");
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
    await window.aigate.loadUsageSummary("nope");
    const msg = document.getElementById("usageMsg");
    expect(msg.textContent).toContain("range must be day|week|month");
    expect(msg.className).toContain("settings-msg-error");
  });
});

describe("loadProviderUsage (provider-detail subsection)", () => {
  beforeEach(() => { withUsageDom(); });

  it("GETs day summary for the provider and renders totals + models only", async () => {
    const calls = stubFetchFor({ "/api/usage/summary": SUMMARY_PAYLOAD });
    await window.aigate.usage.loadProviderUsage(1);
    expect(calls.some((c) =>
      c.url === "/api/usage/summary?range=day&provider_id=1")).toBe(true);
    expect(document.getElementById("provUsageTotals").textContent).toContain("$0.033");
    expect(document.getElementById("provUsageModelBody").innerHTML).toContain("gpt-4o");
    // main view containers untouched
    expect(document.getElementById("usageProviderBody").innerHTML).toBe("");
  });
});

describe("auto-refresh lifecycle (Log Window pattern)", () => {
  beforeEach(() => { withUsageDom(); });

  const usageCalls = (calls) =>
    calls.filter((c) => c.url.indexOf("/api/usage") === 0 ||
                        c.url.indexOf("/api/quota") === 0);

  it("onShow polls quota+summary+recent; stops on onHide", async () => {
    vi.useFakeTimers();
    const calls = stubFetchFor({
      "/api/quota": QUOTA_PAYLOAD,
      "/api/usage/summary": SUMMARY_PAYLOAD,
      "/api/usage?": USAGE_LIST_PAYLOAD
    });
    window.aigate.usage.onShow();
    await vi.advanceTimersByTimeAsync(0);
    expect(usageCalls(calls).length).toBe(3);

    await vi.advanceTimersByTimeAsync(10000); // one refresh tick
    expect(usageCalls(calls).length).toBe(6);

    window.aigate.usage.onHide();
    await vi.advanceTimersByTimeAsync(25000); // no more polls while hidden
    expect(usageCalls(calls).length).toBe(6);
  });

  it("countdown ticks down client-side every second between polls", async () => {
    vi.useFakeTimers();
    stubFetchFor({ "/api/quota": QUOTA_PAYLOAD });
    window.aigate.renderQuota([{ provider_id: 1, provider_name: "alpha",
      tier: "free", quota_limit: 100, quota_window: "day", used: 10,
      remaining: 90, unlimited: false, seconds_to_reset: 10, cost_est: 0 }]);
    window.aigate.startUsageAutoRefresh();
    await vi.advanceTimersByTimeAsync(3000);
    const cell = document.querySelector("#quotaTableBody .quota-reset");
    expect(cell.textContent).toBe("7s");
    window.aigate.stopUsageAutoRefresh();
  });
});

describe("index.html wiring (B5.5 structure)", () => {
  const html = readFileSync(join(__dirname, "..", "static", "index.html"), "utf8");
  const dom = new JSDOM(html);
  const doc = dom.window.document;

  it("sidebar nav has the Usage & Quota item", () => {
    const item = doc.querySelector('.nav-item[data-view="usage"]');
    expect(item).not.toBeNull();
    expect(item.querySelector("[data-i18n='nav.usage']")).not.toBeNull();
  });

  it("usage view section exists with quota/summary/recent containers", () => {
    const view = doc.querySelector('.view[data-view="usage"]');
    expect(view).not.toBeNull();
    ["quotaTableBody", "usageRange", "usageTotals", "usageProviderBody",
     "usageModelBody", "recentUsageBody", "usageMsg", "usageRefreshBtn"]
      .forEach((id) => expect(view.querySelector("#" + id)).not.toBeNull());
  });

  it("provider detail has the Usage subsection", () => {
    const detail = doc.getElementById("provDetail");
    expect(detail.querySelector("#provUsageTotals")).not.toBeNull();
    expect(detail.querySelector("#provUsageModelBody")).not.toBeNull();
  });

  it("loads usage.js after app.js", () => {
    const srcs = Array.from(doc.querySelectorAll("script[src]"))
      .map((s) => s.getAttribute("src"));
    expect(srcs).toContain("usage.js");
    expect(srcs.indexOf("app.js")).toBeLessThan(srcs.indexOf("usage.js"));
  });
});

describe("i18n usage keys (EN/ID parity)", () => {
  it("every usage.* / nav.usage key exists in both dictionaries", () => {
    const enKeys = Object.keys(window.I18N.en).filter(
      (k) => k.indexOf("usage.") === 0 || k === "nav.usage");
    expect(enKeys.length).toBeGreaterThan(15);
    enKeys.forEach((k) => {
      expect(window.I18N.id[k]).toBeDefined();
    });
    expect(window.I18N.en["nav.usage"]).toBe("Usage & Quota");
    expect(window.I18N.id["nav.usage"]).toBe("Pemakaian & Kuota");
  });
});
