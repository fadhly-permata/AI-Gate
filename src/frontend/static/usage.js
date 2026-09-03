/* ===== aigate Usage & Quota tracking (B5.5) — vanilla JS, no build ===== */
/* Spec: B5.5 frontend scope. Backend contracts (be-dev, verified — EXACT shapes):
   - GET /api/quota?provider_id= -> {object:"list", data:[{provider_id,
     provider_name, tier, quota_limit, quota_window, used, remaining,
     unlimited, window_start, reset_at, seconds_to_reset, cost_est}]}
     unlimited:true => remaining:null, quota_limit:null (no quota set).
   - GET /api/usage/summary?provider_id=&range=day|week|month ->
     {object:"usage_summary", range, since,
      totals:{requests,tokens_in,tokens_out,cost_est},
      by_provider:[{provider_id,provider_name,requests,tokens_in,tokens_out,cost_est}],
      by_model:[{model,requests,tokens_in,tokens_out,cost_est}]}
   - GET /api/usage?provider_id=&endpoint_id=&range= -> {object:"list", range,
     data:[{id,endpoint_id,provider_id,account_id,model,tokens_in,tokens_out,
            cost_est,ts}]}  (newest first)
   Errors: 400 {error:{message,type,code}} — surfaced via the visible status line.
   Reuses fetchJson/escapeHtml/getStr exposed on window.aigate by app.js
   (mirrors Combos / Proxy Pools / Endpoints modules, ADR-001 no framework).
   ADR-011: errors surfaced visibly (status line + console), never swallowed. */

(function () {
  "use strict";

  var QUOTA_API = "/api/quota";
  var USAGE_API = "/api/usage";
  var USAGE_REFRESH_MS = 10000; // re-poll ~10s while the view is visible
  var COUNTDOWN_TICK_MS = 1000; // live-tick the reset countdown every second
  var RECENT_LIMIT = 20;        // rows shown in the recent-usage table

  var refreshTimer = null;
  var tickTimer = null;
  var lastQuota = []; // stored for client-side countdown ticking

  /* ---- Reuse shared helpers from app.js (or minimal fallbacks) ---- */
  function app() { return window.aigate || {}; }

  function getStr(key, loc) {
    var a = app();
    if (typeof a.getStr === "function") return a.getStr(key, loc);
    loc = loc || document.documentElement.getAttribute("data-locale") || "en";
    var d = (window.I18N && window.I18N[loc]) || (window.I18N && window.I18N.en) || {};
    return d[key] !== undefined ? d[key]
         : (window.I18N && window.I18N.en && window.I18N.en[key] !== undefined
                ? window.I18N.en[key] : key);
  }

  function escapeHtml(s) {
    var a = app();
    if (typeof a.escapeHtml === "function") return a.escapeHtml(s);
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
  //   310 -> "310" | 12345 -> "12,345" | 150000 -> "150K" | 1500000 -> "1.5M"
  function formatTokens(n) {
    var v = Number(n);
    if (n == null || n === "" || isNaN(v) || !isFinite(v)) return "0";
    var abs = Math.abs(v);
    if (abs >= 1e6) return trimUnit(v / 1e6) + "M";
    if (abs >= 1e5) return trimUnit(v / 1e3) + "K";
    return groupThousands(String(Math.round(v)));
  }

  // Plain integer with thousands separators (for request counts).
  function formatNumber(n) {
    var v = Number(n);
    if (n == null || n === "" || isNaN(v) || !isFinite(v)) return "0";
    return groupThousands(String(Math.round(v)));
  }

  // Cost estimate as a compact currency string: "$0.033" / "$12.50" / "—".
  function formatCost(n) {
    if (n == null || n === "") return "\u2014";
    var v = Number(n);
    if (isNaN(v) || !isFinite(v)) return "\u2014";
    var s;
    if (v === 0) s = "0.00";
    else if (Math.abs(v) >= 1) s = v.toFixed(2);
    else {
      s = v.toFixed(6).replace(/0+$/, "");
      if (s.charAt(s.length - 1) === ".") s += "0";
    }
    return "$" + s;
  }

  // Pure countdown formatter: seconds -> "16h 47m" / "45m" / "9s"; null -> "—".
  function formatCountdown(seconds) {
    if (seconds == null || seconds === "") return "\u2014";
    var s = Number(seconds);
    if (isNaN(s) || !isFinite(s)) return "\u2014";
    if (s < 0) s = 0;
    s = Math.floor(s);
    if (s < 60) return s + "s";
    var m = Math.floor(s / 60);
    if (m < 60) return m + "m";
    var h = Math.floor(m / 60);
    return h + "h " + (m % 60) + "m";
  }

  // "2026-09-03T07:12:03.123456" -> "2026-09-03 07:12:03" (plaintext, no TZ math).
  function formatTs(ts) {
    if (ts == null || ts === "") return "\u2014";
    var s = String(ts).replace("T", " ");
    var dot = s.indexOf(".");
    if (dot !== -1) s = s.slice(0, dot);
    return s;
  }

  // Tier -> badge (subscription=blue, free=green, other/unknown=muted).
  function tierBadge(tier) {
    var t = (tier == null ? "" : String(tier)).toLowerCase();
    var cls = t === "subscription" ? "sev-info"
            : t === "free" ? "badge-ok"
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
    if (kind === "error" && text) {
      // ADR-011: never swallow — also log to console.
      if (typeof console !== "undefined" && console.error) console.error("[usage]", text);
    }
  }

  function statCard(label, value) {
    return '<div class="usage-stat">' +
      '<div class="usage-stat-value">' + escapeHtml(value) + "</div>" +
      '<div class="usage-stat-label">' + escapeHtml(label) + "</div>" +
    "</div>";
  }

  /* ---- Quota panel (GET /api/quota) ---- */
  function renderQuota(list) {
    lastQuota = Array.isArray(list) ? list.slice() : [];
    var body = el("quotaTableBody");
    if (!body) return;
    if (!lastQuota.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty-cell">' +
        escapeHtml(getStr("usage.no_data")) + "</td></tr>";
      return;
    }
    body.innerHTML = lastQuota.map(function (q) {
      q = q || {};
      var unlimited = !!q.unlimited;
      var usedTxt = formatTokens(q.used);
      var limitTxt = unlimited ? getStr("usage.unlimited") : formatTokens(q.quota_limit);
      var remainTxt = unlimited ? "" : formatTokens(q.remaining);
      var cellTitle = remainTxt
        ? escapeHtml(getStr("usage.remaining") + ": " + remainTxt) : "";
      // Progress bar: hidden entirely when unlimited (no quota set).
      var bar = "";
      if (unlimited) {
        bar = '<span class="badge badge-off">' +
          escapeHtml(getStr("usage.unlimited")) + "</span>";
      } else {
        var limit = Number(q.quota_limit);
        var used = Number(q.used) || 0;
        if (isFinite(limit) && limit > 0) {
          var pct = Math.max(0, Math.min(100, (used / limit) * 100));
          bar = '<span class="usage-progress" role="progressbar" aria-valuenow="' +
            Math.round(pct) + '" aria-valuemin="0" aria-valuemax="100">' +
            '<span class="usage-progress-fill' + (pct >= 90 ? " usage-progress-high" : "") +
            '" style="width:' + pct.toFixed(1) + '%"></span></span>' +
            '<span class="usage-progress-pct">' + Math.round(pct) + "%</span>";
        } else {
          bar = "\u2014";
        }
      }
      var resetTxt = unlimited ? "\u2014" : formatCountdown(q.seconds_to_reset);
      return '<tr class="quota-row" data-provider="' + escapeHtml(q.provider_id) +
        '" data-seconds="' + (q.seconds_to_reset == null ? "" : escapeHtml(q.seconds_to_reset)) + '">' +
        '<td class="quota-name">' + escapeHtml(q.provider_name) + "</td>" +
        "<td>" + tierBadge(q.tier) + "</td>" +
        '<td class="quota-used" title="' + cellTitle + '">' +
          escapeHtml(usedTxt + " / " + limitTxt) + "</td>" +
        '<td class="quota-progress">' + bar + "</td>" +
        '<td class="quota-reset">' + escapeHtml(resetTxt) + "</td>" +
        "<td>" + escapeHtml(formatCost(q.cost_est)) + "</td>" +
      "</tr>";
    }).join("");
  }

  // Live-tick: decrement stored seconds_to_reset and rewrite the reset cells.
  function tickCountdowns() {
    var body = el("quotaTableBody");
    if (!body) return;
    var rows = body.querySelectorAll(".quota-row");
    Array.prototype.forEach.call(rows, function (tr, i) {
      var q = lastQuota[i];
      if (!q || q.unlimited || q.seconds_to_reset == null) return;
      q.seconds_to_reset = Math.max(0, Number(q.seconds_to_reset) - 1);
      var cell = tr.querySelector(".quota-reset");
      if (cell) cell.textContent = formatCountdown(q.seconds_to_reset);
    });
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

  /* ---- Usage summary panel (GET /api/usage/summary) ---- */
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
      renderBreakdown(target.providers || "usageProviderBody",
        summary.by_provider, "provider_name");
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

  /* ---- Recent usage table (GET /api/usage) ---- */
  function buildUsageUrl(range, providerId) {
    var url = USAGE_API + "?range=" + encodeURIComponent(range || "day");
    if (providerId != null && providerId !== "") {
      url += "&provider_id=" + encodeURIComponent(providerId);
    }
    return url;
  }

  function renderRecentUsage(list) {
    var body = el("recentUsageBody");
    if (!body) return;
    list = list || [];
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell">' +
        escapeHtml(getStr("usage.no_data")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.slice(0, RECENT_LIMIT).map(function (r) {
      r = r || {};
      return "<tr>" +
        "<td>" + escapeHtml(r.model) + "</td>" +
        "<td>" + escapeHtml(formatTokens(r.tokens_in)) + "</td>" +
        "<td>" + escapeHtml(formatTokens(r.tokens_out)) + "</td>" +
        "<td>" + escapeHtml(formatCost(r.cost_est)) + "</td>" +
        '<td class="usage-ts">' + escapeHtml(formatTs(r.ts)) + "</td>" +
      "</tr>";
    }).join("");
  }

  // GET /api/usage?range= -> renderRecentUsage (newest first from backend).
  function loadUsage(range, providerId) {
    return fetchJson(buildUsageUrl(range, providerId)).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderRecentUsage(list);
      return list;
    }).catch(function (err) {
      setMsg("usageMsg", err.message, "error");
      return [];
    });
  }

  /* ---- Provider-detail subsection (totals + top models, range=day) ---- */
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

  /* ---- Auto-refresh (only while the view is visible — Log Window pattern) ---- */
  function currentRange() {
    var r = el("usageRange");
    return (r && r.value) ? r.value : "day";
  }

  function refreshAll() {
    loadQuota();
    loadUsageSummary(currentRange());
    loadUsage(currentRange());
  }

  function startUsageAutoRefresh() {
    stopUsageAutoRefresh();
    refreshTimer = setInterval(refreshAll, USAGE_REFRESH_MS);
    tickTimer = setInterval(tickCountdowns, COUNTDOWN_TICK_MS);
  }

  function stopUsageAutoRefresh() {
    if (refreshTimer !== null) {
      clearInterval(refreshTimer);
      refreshTimer = null;
    }
    if (tickTimer !== null) {
      clearInterval(tickTimer);
      tickTimer = null;
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
        loadUsage(rangeSel.value);
      });
    }
    var refreshBtn = el("usageRefreshBtn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () { refreshAll(); });
    }
  }

  /* ---- Expose testable helpers on window.aigate (DoD #6) + module hook ---- */
  window.aigate = window.aigate || {};
  window.aigate.formatCountdown = formatCountdown;
  window.aigate.formatTokens = formatTokens;
  window.aigate.formatNumber = formatNumber;
  window.aigate.formatCost = formatCost;
  window.aigate.formatTs = formatTs;
  window.aigate.renderQuota = renderQuota;
  window.aigate.renderUsageSummary = renderUsageSummary;
  window.aigate.renderRecentUsage = renderRecentUsage;
  window.aigate.loadQuota = loadQuota;
  window.aigate.loadUsageSummary = loadUsageSummary;
  window.aigate.loadUsage = loadUsage;
  window.aigate.startUsageAutoRefresh = startUsageAutoRefresh;
  window.aigate.stopUsageAutoRefresh = stopUsageAutoRefresh;

  window.aigate.usage = {
    onShow: onShow,
    onHide: onHide,
    loadQuota: loadQuota,
    loadUsage: loadUsage,
    loadUsageSummary: loadUsageSummary,
    loadProviderUsage: loadProviderUsage,
    renderQuota: renderQuota,
    renderUsageSummary: renderUsageSummary,
    renderRecentUsage: renderRecentUsage,
    formatCountdown: formatCountdown,
    formatTokens: formatTokens,
    formatCost: formatCost,
    buildSummaryUrl: buildSummaryUrl,
    buildUsageUrl: buildUsageUrl
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
