/* ===== aigate Usage Analytics + Request Log viewer (B5.6) — vanilla JS, no build ===== */
/* Spec: PRD §2.4.3 (Usage Analytics + Request Logging debug mode).
   Backend contracts (be-dev, verified — EXACT shapes):
   - GET /api/analytics?range=day|week|month&group_by=provider|model ->
     {object:"analytics", range, group_by,
      buckets:[{label,requests,tokens_in,tokens_out,cost_est,saved_tokens_est}],
      totals:{requests,tokens_in,tokens_out,cost_est,saved_tokens_est},
      by_group:[{key,requests,tokens_in,tokens_out,cost_est,saved_tokens_est}]}
     buckets are chronological asc and CONTINUOUS (empty periods = zeros).
     day -> 24 hourly ("YYYY-MM-DD HH:00"), week -> 7 daily, month -> 30 daily.
   - GET /api/request-logs?endpoint_id=&limit=50 (newest first, limit cap 500) ->
     {object:"list", data:[{id,endpoint_id,model,ts,duration_ms,
                            request:"<JSON string>", response:"<JSON string>"}]}
     request/response arrive with secret headers redacted SERVER-side; display
     as-is (R11/ADR-007). May carry a "...[truncated N chars]" marker.
   - Enable/disable debug logging: PUT /api/settings
     {"key":"request_log_enabled","value":"true"|"false"};
     read current via GET /api/settings (flat settings object).
   Errors: 400 {error:{message,type,code}} — surfaced via the visible status line.
   Reuses fetchJson/escapeHtml/getStr (app.js) + formatTokens/formatNumber/
   formatCost/formatTs (usage.js) exposed on window.aigate. ADR-011: errors
   surfaced visibly (status line + console), never swallowed. R13: no chart lib —
   trend rendered as plain CSS bars (div heights). */

(function () {
  "use strict";

  var ANALYTICS_API = "/api/analytics";
  var REQLOG_API = "/api/request-logs";
  var SETTINGS_API = "/api/settings";
  var REQLOG_LIMIT = 50;        // default rows in the request-log table
  var CHART_MAX_LABELS = 12;    // thin x labels so the chart stays readable

  var lastBuckets = [];         // stored so the metric selector re-renders cheaply
  var lastGroupBy = "model";

  /* ---- Reuse shared helpers from app.js / usage.js (or minimal fallbacks) ---- */
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

  // Formatters live in usage.js (loaded first in index.html and in tests).
  function formatTokens(n) {
    var a = app();
    if (typeof a.formatTokens === "function") return a.formatTokens(n);
    return String(n == null ? 0 : n);
  }
  function formatNumber(n) {
    var a = app();
    if (typeof a.formatNumber === "function") return a.formatNumber(n);
    return String(n == null ? 0 : n);
  }
  function formatCost(n) {
    var a = app();
    if (typeof a.formatCost === "function") return a.formatCost(n);
    return n == null ? "\u2014" : "$" + n;
  }
  function formatTs(ts) {
    var a = app();
    if (typeof a.formatTs === "function") return a.formatTs(ts);
    return ts == null ? "\u2014" : String(ts).replace("T", " ");
  }

  /* ---- Pure helper: parse a JSON string payload, tolerate raw text ---- */
  // Backend stores request/response as JSON STRINGS (secret headers already
  // redacted server-side). A cut payload carries "...[truncated N chars]" and
  // no longer parses — fall back to the raw text and flag the truncation.
  function parseMaybeJson(str) {
    if (str == null || str === "") return { ok: false, raw: "", truncated: false };
    if (typeof str === "object") {
      return { ok: true, value: str, raw: JSON.stringify(str), truncated: false };
    }
    var s = String(str);
    var truncated = /\[truncated\s+\d+\s+chars?\]/i.test(s);
    try {
      return { ok: true, value: JSON.parse(s), raw: s, truncated: truncated };
    } catch (e) {
      return { ok: false, raw: s, truncated: truncated };
    }
  }

  // Pretty-print one payload cell: parsed -> indented JSON, else raw text.
  function formatPayload(raw) {
    var p = parseMaybeJson(raw);
    var text = p.ok ? JSON.stringify(p.value, null, 2) : p.raw;
    return { text: text, truncated: p.truncated, parsed: p.ok };
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
      if (typeof console !== "undefined" && console.error) console.error("[analytics]", text);
    }
  }

  function statCard(label, value) {
    return '<div class="usage-stat">' +
      '<div class="usage-stat-value">' + escapeHtml(value) + "</div>" +
      '<div class="usage-stat-label">' + escapeHtml(label) + "</div>" +
    "</div>";
  }

  /* ---- Trend chart (plain CSS bars, R13 — no chart library) ---- */
  function currentMetric() {
    var m = el("analyticsMetric");
    return (m && m.value) ? m.value : "tokens";
  }

  // One bucket -> one numeric value for the selected metric.
  function bucketValue(b, metric) {
    b = b || {};
    if (metric === "requests") return Number(b.requests) || 0;
    if (metric === "cost") return Number(b.cost_est) || 0;
    return (Number(b.tokens_in) || 0) + (Number(b.tokens_out) || 0);
  }

  function formatMetricValue(v, metric) {
    return metric === "cost" ? formatCost(v) : formatNumber(v);
  }

  // Render `buckets` as vertical bars scaled to the max value. X labels are
  // thinned (every Nth) so 24-30 buckets stay readable; hover title carries
  // the full "label: value".
  function renderTrendChart(buckets, metric) {
    buckets = Array.isArray(buckets) ? buckets : [];
    lastBuckets = buckets;
    var wrap = el("analyticsChart");
    if (!wrap) return;
    metric = metric || currentMetric();
    if (!buckets.length) {
      wrap.innerHTML = '<p class="empty-cell">' +
        escapeHtml(getStr("analytics.no_data")) + "</p>";
      return;
    }
    var values = buckets.map(function (b) { return bucketValue(b, metric); });
    var max = Math.max.apply(null, values);
    if (!(max > 0)) max = 1; // all-zero range -> flat chart, no div-by-zero
    var step = Math.ceil(buckets.length / CHART_MAX_LABELS);
    wrap.innerHTML = buckets.map(function (b, i) {
      b = b || {};
      var v = values[i];
      var pct = (v / max) * 100;
      var bar = v > 0
        ? '<div class="trend-bar" style="height:' + pct.toFixed(1) + '%"></div>'
        : '<div class="trend-bar trend-bar-zero"></div>';
      var label = (i % step === 0) ? String(b.label == null ? "" : b.label) : "";
      var title = escapeHtml((b.label == null ? "" : b.label) + ": " +
        formatMetricValue(v, metric));
      return '<div class="trend-col" title="' + title + '">' +
        bar +
        '<div class="trend-label">' + escapeHtml(label) + "</div>" +
      "</div>";
    }).join("");
  }

  /* ---- By-group table (key, requests, tokens, cost, savings) ---- */
  function renderByGroup(byGroup, groupBy) {
    byGroup = Array.isArray(byGroup) ? byGroup : [];
    if (groupBy) lastGroupBy = groupBy;
    var body = el("analyticsGroupBody");
    if (!body) return;
    if (!byGroup.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty-cell">' +
        escapeHtml(getStr("analytics.no_data")) + "</td></tr>";
      return;
    }
    body.innerHTML = byGroup.map(function (g) {
      g = g || {};
      return '<tr class="analytics-group-row">' +
        "<td>" + escapeHtml(g.key) + "</td>" +
        "<td>" + escapeHtml(formatNumber(g.requests)) + "</td>" +
        "<td>" + escapeHtml(formatTokens(g.tokens_in)) + "</td>" +
        "<td>" + escapeHtml(formatTokens(g.tokens_out)) + "</td>" +
        "<td>" + escapeHtml(formatCost(g.cost_est)) + "</td>" +
        "<td>" + escapeHtml(formatTokens(g.saved_tokens_est)) + "</td>" +
      "</tr>";
    }).join("");
  }

  /* ---- Totals cards + chart + table from one analytics payload ---- */
  function renderAnalytics(data) {
    data = data || {};
    if (data.group_by) lastGroupBy = data.group_by;
    var totals = data.totals || {};
    var totalsEl = el("analyticsTotals");
    if (totalsEl) {
      totalsEl.innerHTML =
        statCard(getStr("analytics.requests"), formatNumber(totals.requests)) +
        statCard(getStr("analytics.tokens_in"), formatTokens(totals.tokens_in)) +
        statCard(getStr("analytics.tokens_out"), formatTokens(totals.tokens_out)) +
        statCard(getStr("analytics.cost"), formatCost(totals.cost_est)) +
        statCard(getStr("analytics.savings"), formatTokens(totals.saved_tokens_est));
    }
    renderTrendChart(data.buckets || []);
    renderByGroup(data.by_group || [], data.group_by);
  }

  function buildAnalyticsUrl(range, groupBy) {
    return ANALYTICS_API + "?range=" + encodeURIComponent(range || "day") +
      "&group_by=" + encodeURIComponent(groupBy || "model");
  }

  // GET /api/analytics -> renderAnalytics. Args fall back to the control values.
  function loadAnalytics(range, groupBy) {
    var r = el("analyticsRange");
    var g = el("analyticsGroup");
    range = range || (r && r.value) || "day";
    groupBy = groupBy || (g && g.value) || "model";
    setMsg("analyticsMsg", "");
    return fetchJson(buildAnalyticsUrl(range, groupBy)).then(function (data) {
      renderAnalytics(data || {});
      return data;
    }).catch(function (err) {
      setMsg("analyticsMsg", err.message, "error");
      return null;
    });
  }

  /* ---- Request Log viewer (debug mode) ---- */
  function buildReqLogUrl(limit, endpointId) {
    var url = REQLOG_API + "?limit=" + encodeURIComponent(limit || REQLOG_LIMIT);
    if (endpointId != null && endpointId !== "") {
      url += "&endpoint_id=" + encodeURIComponent(endpointId);
    }
    return url;
  }

  function renderRequestLogs(list) {
    var body = el("reqlogTableBody");
    if (!body) return;
    list = Array.isArray(list) ? list : [];
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell">' +
        escapeHtml(getStr("reqlog.empty")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(function (r) {
      r = r || {};
      var req = formatPayload(r.request);
      var res = formatPayload(r.response);
      var truncNote = function (p) {
        return p.truncated
          ? '<div class="reqlog-truncated">\u26a0 ' +
            escapeHtml(getStr("reqlog.truncated")) + "</div>"
          : "";
      };
      var details = '<details class="reqlog-details"><summary>' +
        escapeHtml(getStr("reqlog.payload")) + "</summary>" +
        '<div class="reqlog-block"><div class="reqlog-block-title">' +
          escapeHtml(getStr("reqlog.request")) + "</div>" + truncNote(req) +
          "<pre>" + escapeHtml(req.text) + "</pre></div>" +
        '<div class="reqlog-block"><div class="reqlog-block-title">' +
          escapeHtml(getStr("reqlog.response")) + "</div>" + truncNote(res) +
          "<pre>" + escapeHtml(res.text) + "</pre></div>" +
        "</details>";
      return '<tr class="reqlog-row" data-id="' + escapeHtml(r.id) + '">' +
        '<td class="usage-ts">' + escapeHtml(formatTs(r.ts)) + "</td>" +
        "<td>" + escapeHtml(r.model) + "</td>" +
        "<td>" + escapeHtml(r.endpoint_id) + "</td>" +
        '<td class="reqlog-duration">' +
          escapeHtml(formatNumber(r.duration_ms) + " ms") + "</td>" +
        "<td>" + details + "</td>" +
      "</tr>";
    }).join("");
  }

  // GET /api/request-logs?limit= -> renderRequestLogs (newest first from backend).
  function loadRequestLogs(limit) {
    setMsg("reqlogMsg", "");
    return fetchJson(buildReqLogUrl(limit)).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderRequestLogs(list);
      return list;
    }).catch(function (err) {
      setMsg("reqlogMsg", err.message, "error");
      return null; // distinguish "failed to load" from "empty list"
    });
  }

  // PUT /api/settings {"key":"request_log_enabled","value":"true"|"false"}.
  // On failure: revert the checkbox + surface the error (ADR-011), never swallow.
  function setRequestLogEnabled(enabled) {
    var on = !!enabled;
    setMsg("reqlogMsg", "");
    return fetchJson(SETTINGS_API, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "request_log_enabled", value: on ? "true" : "false" })
    }).then(function () {
      // Reload the table first, THEN surface the confirmation (loadRequestLogs
      // clears the status line on entry).
      return loadRequestLogs().then(function (list) {
        // Only confirm if the reload didn't itself error (its message stays).
        if (list !== null) {
          setMsg("reqlogMsg", getStr(on ? "reqlog.enabled_ok" : "reqlog.disabled_ok"), "ok");
        }
        return on;
      });
    }).catch(function (err) {
      var cb = el("reqlogEnabled");
      if (cb) cb.checked = !on; // revert the UI to the last known state
      setMsg("reqlogMsg", err.message, "error");
      return null;
    });
  }

  // GET /api/settings -> sync the enable checkbox with the stored flag.
  function loadRequestLogSetting() {
    return fetchJson(SETTINGS_API).then(function (data) {
      var cb = el("reqlogEnabled");
      if (cb && data) cb.checked = String(data.request_log_enabled) === "true";
      return cb ? !!cb.checked : false;
    }).catch(function (err) {
      setMsg("reqlogMsg", err.message, "error");
      return false;
    });
  }

  /* ---- View lifecycle (no timers: refresh is manual + on control change) ---- */
  function onShow() {
    loadAnalytics();
    loadRequestLogSetting();
    loadRequestLogs();
  }

  function onHide() { /* nothing to stop — analytics view does not auto-poll */ }

  /* ---- Wire up ---- */
  function init() {
    var rangeSel = el("analyticsRange");
    if (rangeSel) {
      rangeSel.addEventListener("change", function () { loadAnalytics(); });
    }
    var groupSel = el("analyticsGroup");
    if (groupSel) {
      groupSel.addEventListener("change", function () { loadAnalytics(); });
    }
    var metricSel = el("analyticsMetric");
    if (metricSel) {
      // Metric is a pure re-render of the already-fetched buckets (no refetch).
      metricSel.addEventListener("change", function () {
        renderTrendChart(lastBuckets, metricSel.value);
      });
    }
    var refreshBtn = el("analyticsRefreshBtn");
    if (refreshBtn) {
      refreshBtn.addEventListener("click", function () { loadAnalytics(); });
    }
    var reqlogToggle = el("reqlogEnabled");
    if (reqlogToggle) {
      reqlogToggle.addEventListener("change", function () {
        setRequestLogEnabled(reqlogToggle.checked);
      });
    }
    var reqlogRefresh = el("reqlogRefreshBtn");
    if (reqlogRefresh) {
      reqlogRefresh.addEventListener("click", function () { loadRequestLogs(); });
    }
  }

  /* ---- Expose testable helpers on window.aigate (DoD #3) + module hook ---- */
  window.aigate = window.aigate || {};
  window.aigate.parseMaybeJson = parseMaybeJson;
  window.aigate.renderAnalytics = renderAnalytics;
  window.aigate.renderTrendChart = renderTrendChart;
  window.aigate.renderByGroup = renderByGroup;
  window.aigate.loadAnalytics = loadAnalytics;
  window.aigate.renderRequestLogs = renderRequestLogs;
  window.aigate.loadRequestLogs = loadRequestLogs;
  window.aigate.setRequestLogEnabled = setRequestLogEnabled;

  window.aigate.analytics = {
    onShow: onShow,
    onHide: onHide,
    parseMaybeJson: parseMaybeJson,
    renderAnalytics: renderAnalytics,
    renderTrendChart: renderTrendChart,
    renderByGroup: renderByGroup,
    loadAnalytics: loadAnalytics,
    renderRequestLogs: renderRequestLogs,
    loadRequestLogs: loadRequestLogs,
    loadRequestLogSetting: loadRequestLogSetting,
    setRequestLogEnabled: setRequestLogEnabled,
    buildAnalyticsUrl: buildAnalyticsUrl,
    buildReqLogUrl: buildReqLogUrl
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
