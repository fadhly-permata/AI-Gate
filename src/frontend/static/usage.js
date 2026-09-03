/* ===== aigate Usage & Quota tracking (B5.5) — vanilla JS, no build ===== */
/* Spec: B5.5 frontend scope. Backend contracts (be-dev, verified):
   - GET /api/quota?provider_id= -> {object:"list", data:[{provider_id,
     provider_name, tier, remaining, limit, used, reset_at:ISO|null,
     reset_label, cost_est}]}
   - GET /api/usage/summary?provider_id=&range=day|week|month ->
     {range, totals:{requests,tokens_in,tokens_out,cost_est},
      by_provider:[{provider_id,provider_name,requests,tokens_in,tokens_out,cost_est}],
      by_model:[{model,requests,tokens_in,tokens_out,cost_est}]}
   Reuses fetchJson/escapeHtml/getStr exposed on window.aigate by app.js
   (mirrors Combos / Proxy Pools / Endpoints modules, ADR-001 no framework).
   ADR-011: errors surfaced via the visible status line, never swallowed. */

(function () {
  "use strict";

  var QUOTA_API = "/api/quota";
  var USAGE_API = "/api/usage";
  var USAGE_REFRESH_MS = 10000; // ~10s while the view is visible
  var refreshTimer = null;

  /* ---- Reuse shared helpers from app.js (or minimal fallbacks) ---- */
  function app() { return window.aigate || {}; }

  function getStr(key, loc) {
    loc = loc || document.documentElement.getAttribute("data-locale") || "en";
    var d = (window.I18N && window.I18N[loc]) || (window.I18N && window.I18N.en) || {};
    return d[key] !== undefined ? d[key]
         : (window.I18N && window.I18N.en && window.I18N.en[key] !== undefined
               ? window.I18N.en[key] : key);
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fetchJson(url, opts) {
    var a = app();
    if (typeof a.fetchJson === "function") return a.fetchJson(url, opts);
    opts = opts || {};
    opts.headers = Object.assign({ "Accept": "application/json" }, opts.headers || {});
    return fetch(url, opts).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (b) {
          var msg = (b && b.error && b.error.message) ? b.error.message : ("HTTP " + r.status);
          var e = new Error(msg); e.status = r.status; throw e;
        }, function () { throw new Error("HTTP " + r.status); });
      }
      return r.json();
    });
  }

  /* ---- Pure, testable formatters ---- */

  // Insert thousands separators into an integer digit string (locale-independent).
  function groupThousands(intStr) {
    var neg = intStr.charAt(0) === "-";
    var digits = neg ? intStr.slice(1) : intStr;
    var out = "";
    var count = 0;
    for (var i = digits.length - 1; i >= 0; i--) {
      out = digits.charAt(i) + out;
      count++;
      if (count % 3 === 0 && i !== 0) out = "," + out;
    }
    return (neg ? "-" : "") + out;
  }

  // Round to 1 decimal, strip a trailing ".0" (e.g. 150 -> "150", 1.5 -> "1.5").
  function trimUnit(x) {
    var r = Math.round(x * 10) / 10;
    return (r % 1 === 0) ? String(Math.round(r)) : String(r);
  }

  // Token count: thousands separators below 100k, then K / M above.
  //   12345 -> "12,345" | 150000 -> "150K" | 1500000 -> "1.5M"
  function formatTokens(n) {
    n = Number(n);
    if (n == null || isNaN(n) || !isFinite(n)) return "0";
    var abs = Math.abs(n);
    if (abs >= 1e6) return trimUnit(n / 1e6) + "M";
    if (abs >= 1e5) return trimUnit(n / 1e3) + "K";
    return groupThousands(String(Math.round(n)));
  }

  // Plain integer with thousands separators (for request counts).
  function formatNumber(n) {
    n = Number(n);
    if (isNaN(n) || !isFinite(n)) return "0";
    return groupThousands(String(Math.round(n)));
  }

  // Cost estimate as a compact currency string; null/invalid -> em dash.
  function formatCost(n) {
    if (n == null || n === "") return "\u2014";
    var v = Number(n);
    if (!isFinite(v)) return "\u2014";
    var dec = (v !== 0 && Math.abs(v) < 1) ? 4 : 2;
    return "$" + v.toFixed(dec);
  }

  // Countdown from a reset_at ISO timestamp vs `now` (ms or Date, default now).
  //   null/invalid -> "—" ; future -> "resets in Xh Ym" ; past -> "resets now".
  function formatCountdown(resetAtISO, now) {
    if (resetAtISO == null || resetAtISO === "") return "\u2014";
    var target = Date.parse(resetAtISO);
    if (isNaN(target)) return "\u2014";
    var base = (now == null) ? Date.now()
             : (typeof now === "number" ? now : Date.parse(now));
    if (isNaN(base)) base = Date.now();
    var diff = target - base;
    if (diff <= 0) return "resets now";
    if (diff < 60000) return "resets in " + Math.floor(diff / 1000) + "s";
    var totalMin = Math.floor(diff / 60000);
    var h = Math.floor(totalMin / 60);
    var m = totalMin % 60;
    if (h > 0) return "resets in " + h + "h " + m + "m";
    return "resets in " + m + "m";
  }

  // Used percentage: prefer (limit - remaining)/limit, fall back to `used`.
  function usedPercent(q) {
    q = q || {};
    var limit = Number(q.limit);
    var remaining = Number(q.remaining);
    if (isFinite(limit) && limit > 0 && isFinite(remaining)) {
      var pct = ((limit - remaining) / limit) * 100;
      return Math.max(0, Math.min(100, pct));
    }
    var used = Number(q.used);
    if (isFinite(used)) {
      var p = (used > 0 && used <= 1) ? used * 100 : used;
      return Math.max(0, Math.min(100, p));
    }
    return 0;
  }

  // Tier -> badge class (subscription / cheap / free).
  function tierBadge(tier) {
    var t = (tier == null ? "" : String(tier)).toLowerCase();
    var cls = t === "subscription" ? "badge-tier-sub"
            : t === "cheap" ? "badge-tier-cheap"
            : t === "free" ? "badge-tier-free"
            : "badge-off";
    return '<span class="badge ' + cls + '">' + escapeHtml(tier || "\u2014") + "</span>";
  }

  /* ---- DOM helpers ---- */
  function el(id) { return document.getElementById(id); }

  function setMsg(id, text, kind) {
    var m = el(id);
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function statCard(label, value) {
    return '<div class="usage-stat">' +
      '<div class="usage-stat-value">' + escapeHtml(value) + "</div>" +
      '<div class="usage-stat-label">' + escapeHtml(label) + "</div>" +
    "</div>";
  }

  /* ---- Quota panel ---- */
  function renderQuota(list) {
    var body = el("quotaTableBody");
    if (!body) return;
    list = list || [];
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty-cell">' +
        escapeHtml(getStr("usage.no_data")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(function (q) {
      q = q || {};
      var remaining = formatTokens(q.remaining);
      var limit = (q.limit == null || q.limit === "") ? "\u2014" : formatTokens(q.limit);
      var usedPct = Math.round(usedPercent(q)) + "%";
      var resetText = (q.reset_label != null && q.reset_label !== "")
        ? String(q.reset_label) : formatCountdown(q.reset_at);
      return '<tr class="quota-row" data-provider="' + escapeHtml(q.provider_id) + '">' +
        '<td class="quota-name">' + escapeHtml(q.provider_name) + "</td>" +
        "<td>" + tierBadge(q.tier) + "</td>" +
        '<td class="quota-remaining">' + escapeHtml(remaining + " / " + limit) + "</td>" +
        "<td>" + escapeHtml(usedPct) + "</td>" +
        '<td class="quota-reset">' + escapeHtml(resetText) + "</td>" +
        "<td>" + escapeHtml(formatCost(q.cost_est)) + "</td>" +
      "</tr>";
    }).join("");
  }

  // GET /api/quota -> renderQuota. Returns the list (or [] on error).
  function loadQuota() {
    setMsg("usageMsg", "");
    return fetchJson(QUOTA_API).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderQuota(list);
      return list;
    }).catch(function (err) {
      setMsg("usageMsg", err.message, "error");
      return [];
    });
  }

  /* ---- Usage summary panel ---- */
  // One breakdown table (name + requests + tokens_in + tokens_out + cost).
  function renderBreakdown(bodyId, rows, nameKey) {
    var body = el(bodyId);
    if (!body) return;
    rows = rows || [];
    if (!rows.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell">' +
        escapeHtml(getStr("usage.no_data")) + "</td></tr>";
      return;
    }
    body.innerHTML = rows.map(function (r) {
      r = r || {};
      return "<tr>" +
        "<td>" + escapeHtml(r[nameKey]) + "</td>" +
        "<td>" + escapeHtml(formatNumber(r.requests)) + "</td>" +
        "<td>" + escapeHtml(formatTokens(r.tokens_in)) + "</td>" +
        "<td>" + escapeHtml(formatTokens(r.tokens_out)) + "</td>" +
        "<td>" + escapeHtml(formatCost(r.cost_est)) + "</td>" +
      "</tr>";
    }).join("");
  }

  // Render a summary payload. `target` overrides container ids (used by the
  // provider-detail subsection); pass null to skip a section.
  function renderUsageSummary(summary, target) {
    summary = summary || {};
    target = target || {};
    var totals = summary.totals || {};
    var totalsEl = el(target.totals || "usageTotals");
    if (totalsEl) {
      totalsEl.innerHTML =
        statCard(getStr("usage.requests"), formatNumber(totals.requests)) +
        statCard(getStr("usage.tokens_in"), formatTokens(totals.tokens_in)) +
        statCard(getStr("usage.tokens_out"), formatTokens(totals.tokens_out)) +
        statCard(getStr("usage.cost"), formatCost(totals.cost_est));
    }
    if (target.providers !== null) {
      renderBreakdown(target.providers || "usageProviderBody", summary.by_provider, "provider_name");
    }
    if (target.models !== null) {
      renderBreakdown(target.models || "usageModelBody", summary.by_model, "model");
    }
  }

  function buildSummaryUrl(range, providerId) {
    var url = USAGE_API + "/summary?range=" + encodeURIComponent(range || "day");
    if (providerId != null && providerId !== "") {
      url += "&provider_id=" + encodeURIComponent(providerId);
    }
    return url;
  }

  // GET /api/usage/summary?range=&provider_id= -> renderUsageSummary.
  function loadUsageSummary(range, providerId, target) {
    setMsg("usageMsg", "");
    return fetchJson(buildSummaryUrl(range, providerId)).then(function (summary) {
      renderUsageSummary(summary || {}, target);
      return summary;
    }).catch(function (err) {
      setMsg("usageMsg", err.message, "error");
      return null;
    });
  }

  // Provider-detail subsection: totals + top models for one provider (day).
  function loadProviderUsage(providerId) {
    if (providerId == null) return Promise.resolve(null);
    setMsg("provUsageMsg", "");
    return fetchJson(buildSummaryUrl("day", providerId)).then(function (summary) {
      renderUsageSummary(summary || {}, {
        totals: "provUsageTotals", providers: null, models: "provUsageModelBody"
      });
      return summary;
    }).catch(function (err) {
      setMsg("provUsageMsg", err.message, "error");
      return null;
    });
  }

  /* ---- Auto-refresh (only while the view is visible) ---- */
  function currentRange() {
    var r = el("usageRange");
    return (r && r.value) ? r.value : "day";
  }

  function refreshAll() {
    loadQuota();
    loadUsageSummary(currentRange());
  }

  function startUsageAutoRefresh() {
    stopUsageAutoRefresh();
    refreshTimer = setInterval(refreshAll, USAGE_REFRESH_MS);
  }

  function stopUsageAutoRefresh() {
    if (refreshTimer !== null) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
  }

  function onShow() {
    refreshAll();
    startUsageAutoRefresh();
  }

  function onHide() { stopUsageAutoRefresh(); }

  /* ---- Wire up ---- */
  function init() {
    var rangeSel = el("usageRange");
    if (rangeSel) {
      rangeSel.addEventListener("change", function () {
        loadUsageSummary(rangeSel.value);
      });
    }
    var refreshBtn = el("usageRefreshBtn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () { refreshAll(); });
    }
  }

  /* ---- Expose helpers on window.aigate (DoD #4) + module hook ---- */
  window.aigate = window.aigate || {};
  window.aigate.formatCountdown = formatCountdown;
  window.aigate.formatTokens = formatTokens;
  window.aigate.formatNumber = formatNumber;
  window.aigate.formatCost = formatCost;
  window.aigate.renderQuota = renderQuota;
  window.aigate.renderUsageSummary = renderUsageSummary;
  window.aigate.loadQuota = loadQuota;
  window.aigate.loadUsageSummary = loadUsageSummary;
  window.aigate.startUsageAutoRefresh = startUsageAutoRefresh;
  window.aigate.stopUsageAutoRefresh = stopUsageAutoRefresh;

  window.aigate.usage = {
    onShow: onShow,
    onHide: onHide,
    loadQuota: loadQuota,
    loadUsageSummary: loadUsageSummary,
    loadProviderUsage: loadProviderUsage,
    renderQuota: renderQuota,
    renderUsageSummary: renderUsageSummary,
    formatCountdown: formatCountdown,
    formatTokens: formatTokens
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
