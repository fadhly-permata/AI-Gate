/* ===== aigate UI shell bootstrap ===== */
/* Spec: FSD §2.7, TSD §3.4. Persist prefs in localStorage.
   Keys: aigate.theme | aigate.locale | aigate.sidebar               */

(function () {
  "use strict";

  var THEME_KEY = "aigate.theme";
  var LOCALE_KEY = "aigate.locale";
  var SIDEBAR_KEY = "aigate.sidebar";
  var DEVICE_KEY = "aigate.device";
  var DEFAULT_THEME = "light";
  var DEFAULT_LOCALE = "en";
  var DEFAULT_SIDEBAR = "expanded";
  var DEFAULT_DEVICE = "desktop";

  var ALLOWED_DEVICES = ["phone", "tablet", "desktop"];

  var SETTINGS_API = "/api/settings";

  function read(key, fallback) {
    try {
      var v = localStorage.getItem(key);
      return v === null ? fallback : v;
    } catch (e) {
      return fallback;
    }
  }

  function write(key, val) {
    try {
      localStorage.setItem(key, val);
    } catch (e) {
      /* storage unavailable — prefs simply won't persist */
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var btn = document.getElementById("themeToggle");
    if (btn) {
      var icon = btn.querySelector("i");
      // Show the icon of the theme you will switch TO.
      if (icon) icon.className = theme === "dark" ? "fa fa-sun" : "fa fa-moon";
    }
  }

  function applySidebar(state) {
    var collapsed = state === "collapsed";
    document.body.classList.toggle("sidebar-collapsed", collapsed);
  }

  /* ---- Device simulation (B4.2) ----
     Validate via the shared helper (device.js). Unknown -> desktop. */
  function deviceAttr(device) {
    if (window.aigate && typeof window.aigate.deviceAttr === "function") {
      return window.aigate.deviceAttr(device);
    }
    var v = (device == null ? "" : String(device)).trim().toLowerCase();
    return ALLOWED_DEVICES.indexOf(v) !== -1 ? v : DEFAULT_DEVICE;
  }

  function applyDevice(device) {
    var norm = deviceAttr(device);
    document.body.dataset.device = norm;
    var sel = document.getElementById("setDevice");
    if (sel) sel.value = norm;
    // Keep the bottom-nav active highlight in sync with the current view.
    var active = document.querySelector(".view.is-active");
    var view = active ? active.getAttribute("data-view") : null;
    syncBottomNav(view);
  }

  function syncBottomNav(view) {
    document.querySelectorAll(".bn-item").forEach(function (n) {
      n.classList.toggle("active", !!view && n.getAttribute("data-view") === view);
    });
  }

  function markActiveLang(locale) {
    document.querySelectorAll(".lang-btn").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-lang") === locale);
    });
  }

  // Translate a key for the active (or given) locale.
  function getStr(key, loc) {
    loc = loc || document.documentElement.getAttribute("data-locale") || DEFAULT_LOCALE;
    var d = window.I18N[loc] || window.I18N.en;
    return d[key] !== undefined ? d[key]
         : (window.I18N.en[key] !== undefined ? window.I18N.en[key] : key);
  }

  /* Expose theme helper so the Settings panel can apply theme live on save. */
  window.applyTheme = applyTheme;

  /* ---- View switching (nav-item -> matching .view) ---- */
  function showView(name) {
    var target = document.querySelector('.view[data-view="' + name + '"]');
    if (!target) target = document.querySelector('.view[data-view="welcome"]');
    document.querySelectorAll(".view").forEach(function (v) {
      v.classList.remove("is-active");
    });
    if (target) target.classList.add("is-active");
  }

  function setActiveNav(item) {
    document.querySelectorAll(".nav-item").forEach(function (n) {
      n.classList.remove("active");
    });
    if (item) item.classList.add("active");
    // Mirror the active state onto the mobile bottom-nav (same data-view).
    var view = item ? item.getAttribute("data-view") : null;
    document.querySelectorAll(".bn-item").forEach(function (n) {
      n.classList.toggle("active", !!view && n.getAttribute("data-view") === view);
    });
  }

  /* ---- Settings panel (B1.3) ---- */
  function settingsFields() {
    return {
      port: document.getElementById("setPort"),
      dev_mode: document.getElementById("setDevMode"),
      theme: document.getElementById("setTheme"),
      locale: document.getElementById("setLocale")
    };
  }

  function settingsMsgEl() {
    return document.getElementById("settingsMsg");
  }

  function setMsg(text, kind) {
    var m = settingsMsgEl();
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  // GET /api/settings -> populate fields.
  function loadSettings() {
    setMsg("", "");
    fetch(SETTINGS_API, {
      method: "GET",
      headers: { "Accept": "application/json" }
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        var f = settingsFields();
        if (f.port) f.port.value = data.port != null ? data.port : "";
        if (f.dev_mode) f.dev_mode.checked = String(data.dev_mode) === "true";
        if (f.theme) f.theme.value = data.theme || DEFAULT_THEME;
        if (f.locale) f.locale.value = data.locale || DEFAULT_LOCALE;
      })
      .catch(function (err) {
        setMsg(getStr("settings.error") + " (" + err.message + ")", "error");
      });
  }

  // Build the PUT body; ALL values stringified per API contract.
  function buildSettingsBody() {
    var f = settingsFields();
    return {
      settings: {
        port: String(f.port ? f.port.value : ""),
        dev_mode: f.dev_mode && f.dev_mode.checked ? "true" : "false",
        theme: f.theme ? f.theme.value : DEFAULT_THEME,
        locale: f.locale ? f.locale.value : DEFAULT_LOCALE
      }
    };
  }

  // PUT /api/settings with { settings: {...} } (strings).
  function saveSettings(e) {
    if (e) e.preventDefault();
    var body = buildSettingsBody();
    setMsg("", "");
    fetch(SETTINGS_API, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json"
      },
      body: JSON.stringify(body)
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function () {
        // Apply theme + locale live (source of truth now in DB).
        var f = settingsFields();
        window.applyTheme(f.theme.value);
        window.applyLocale(f.locale.value);
        // Keep localStorage in sync with the topbar toggle / lang buttons.
        write(THEME_KEY, f.theme.value);
        write(LOCALE_KEY, f.locale.value);
        markActiveLang(f.locale.value);
        setMsg(getStr("settings.saved"), "ok");
      })
      .catch(function (err) {
        setMsg(getStr("settings.error") + " (" + err.message + ")", "error");
      });
  }

  /* Test hook: lets vitest assert the PUT body stringifies values. */
  window.aigate = window.aigate || {};
  window.aigate.buildSettingsBody = buildSettingsBody;

  /* ===== Providers management (B2.2) ===== */
  var PROV_API = "/api/providers";
  var selectedProviderId = null;

  /* ---- Pure helpers (importable + testable) ---- */

  // Map a ProviderDTO to a flat table-row datum.
  function mapProviderToRow(p) {
    p = p || {};
    return {
      id: p.id,
      name: p.name,
      type: p.type,
      base_url: p.base_url,
      enabled: !!p.enabled,
      modelCount: Array.isArray(p.models) ? p.models.length : 0
    };
  }

  // Build a {key:value} dict from key/value editor rows.
  // Empty keys are skipped; values kept as-is (incl. empty string).
  function buildHeadersDict(rows) {
    var dict = {};
    (rows || []).forEach(function (r) {
      var k = (r && r.key != null ? String(r.key) : "").trim();
      var v = (r && r.value != null ? String(r.value) : "");
      if (k) dict[k] = v;
    });
    return dict;
  }

  // Inverse of buildHeadersDict: dict -> [{key, value}] rows.
  function headersToRows(dict) {
    var rows = [];
    var d = dict || {};
    Object.keys(d).forEach(function (k) {
      rows.push({ key: k, value: d[k] });
    });
    return rows;
  }

  window.aigate.mapProviderToRow = mapProviderToRow;
  window.aigate.buildHeadersDict = buildHeadersDict;
  window.aigate.headersToRows = headersToRows;

  /* ===== Terminal + Log Window (B3.1) ===== */
  /* Pure helpers (importable + testable via vitest). */

  // Map a severity to a CSS badge class. Unknown -> sev-unknown.
  function severityClass(sev) {
    switch ((sev || "").toString().toLowerCase()) {
      case "info": return "sev-info";
      case "warning": return "sev-warning";
      case "error": return "sev-error";
      default: return "sev-unknown";
    }
  }

  // Normalize a raw LogEntry into a flat row datum.
  function formatLogRow(entry) {
    entry = entry || {};
    return {
      id: entry.id,
      timestamp: entry.timestamp || "",
      severity: entry.severity || "info",
      source: entry.source || "",
      message: entry.message || "",
      stacktrace: (entry.stacktrace != null && entry.stacktrace !== "")
        ? entry.stacktrace : null
    };
  }

  // Build the querystring for GET /api/logs.
  // severity "all"/empty => omitted; limit omitted unless a positive number.
  function buildLogsQuery(severity, limit) {
    var params = [];
    if (severity && severity !== "all") {
      params.push("severity=" + encodeURIComponent(severity));
    }
    if (limit != null && limit !== "" && !isNaN(Number(limit)) && Number(limit) > 0) {
      params.push("limit=" + Number(limit));
    }
    return params.length ? "?" + params.join("&") : "";
  }

  window.aigate.severityClass = severityClass;
  window.aigate.formatLogRow = formatLogRow;
  window.aigate.buildLogsQuery = buildLogsQuery;

  /* ---- DOM helpers ---- */
  function provEl(id) { return document.getElementById(id); }

  function setProvMsg(text, kind) {
    var m = provEl("provMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function setModelMsg(text, kind) {
    var m = provEl("provModelMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // fetch + JSON + unify error shape ({error:{message}} or status text).
  function fetchJson(url, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ "Accept": "application/json" }, opts.headers || {});
    return fetch(url, opts).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (b) {
          var msg = (b && b.error && b.error.message) ? b.error.message : ("HTTP " + r.status);
          var err = new Error(msg);
          err.status = r.status;
          throw err;
        }).catch(function () { throw new Error("HTTP " + r.status); });
      }
      var ct = r.headers.get("content-type") || "";
      if (ct.indexOf("application/json") === -1) return null;
      return r.json();
    });
  }

  /* ---- List ---- */
  function loadProviders() {
    setProvMsg("");
    fetchJson(PROV_API).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderProviders(list);
    }).catch(function (err) {
      setProvMsg(err.message, "error");
    });
  }

  function renderProviders(list) {
    var body = provEl("provTableBody");
    if (!body) return;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty-cell">' +
        escapeHtml(getStr("providers.no_models")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(function (p) {
      var row = mapProviderToRow(p);
      var badge = row.enabled
        ? '<span class="badge badge-ok">' + escapeHtml(getStr("providers.enabled")) + "</span>"
        : '<span class="badge badge-off">' + escapeHtml(getStr("providers.disabled")) + "</span>";
      return '<tr class="prov-row" data-id="' + escapeHtml(row.id) + '">' +
        '<td class="prov-name">' + escapeHtml(row.name) + "</td>" +
        "<td>" + escapeHtml(row.type) + "</td>" +
        "<td>" + escapeHtml(row.base_url) + "</td>" +
        "<td>" + badge + "</td>" +
        "<td>" + row.modelCount + "</td>" +
        '<td class="row-actions">' +
          '<button type="button" class="icon-btn-small js-disc" title="' + escapeHtml(getStr("providers.discover")) + '">' +
            '<i class="fa fa-magnifying-glass"></i></button>' +
          '<button type="button" class="icon-btn-small js-del" title="' + escapeHtml(getStr("providers.delete")) + '">' +
            '<i class="fa fa-trash"></i></button>' +
        "</td>" +
      "</tr>";
    }).join("");

    Array.prototype.forEach.call(body.querySelectorAll(".prov-row"), function (tr) {
      var id = tr.getAttribute("data-id");
      // Whole row click -> edit (req: click a row to edit).
      tr.addEventListener("click", function () { openEditModal(id); });
      // Action buttons stop propagation so they don't trigger the row edit.
      tr.querySelector(".js-disc").addEventListener("click", function (e) {
        e.stopPropagation(); discoverModels(id);
      });
      tr.querySelector(".js-del").addEventListener("click", function (e) {
        e.stopPropagation(); deleteProvider(id);
      });
    });
  }

  /* ---- Modal (add / edit) ---- */
  function hideModal() {
    var m = provEl("provModal");
    if (m) m.hidden = true;
  }

  function renderHeadersEditor(rows) {
    var box = provEl("provHeaders");
    if (!box) return;
    box.innerHTML = "";
    (rows || []).forEach(function (r) { addHeaderRow(r.key, r.value); });
  }

  function addHeaderRow(key, value) {
    var box = provEl("provHeaders");
    if (!box) return;
    var row = document.createElement("div");
    row.className = "header-row";
    row.innerHTML =
      '<input class="form-input hdr-key" type="text" />' +
      '<input class="form-input hdr-val" type="text" />' +
      '<button type="button" class="icon-btn-small hdr-del" aria-label="Remove">' +
        '<i class="fa fa-xmark"></i></button>';
    row.querySelector(".hdr-key").placeholder = getStr("providers.header_key_ph");
    row.querySelector(".hdr-val").placeholder = getStr("providers.header_val_ph");
    row.querySelector(".hdr-key").value = key || "";
    row.querySelector(".hdr-val").value = value || "";
    row.querySelector(".hdr-del").addEventListener("click", function () { row.remove(); });
    box.appendChild(row);
  }

  function collectHeaders() {
    var box = provEl("provHeaders");
    if (!box) return {};
    var rows = Array.prototype.map.call(box.querySelectorAll(".header-row"), function (r) {
      return {
        key: r.querySelector(".hdr-key").value,
        value: r.querySelector(".hdr-val").value
      };
    });
    return buildHeadersDict(rows);
  }

  function openAddModal() {
    selectedProviderId = null;
    var f = provEl("provForm");
    if (f) f.reset();
    provEl("provId").value = "";
    provEl("provModalTitle").textContent = getStr("providers.add");
    renderHeadersEditor([]);
    provEl("provModal").hidden = false;
  }

  function openEditModal(id) {
    fetchJson(PROV_API + "/" + id).then(function (p) {
      selectedProviderId = id;
      provEl("provId").value = p.id;
      provEl("provName").value = p.name != null ? p.name : "";
      provEl("provType").value = p.type || "openai-compatible";
      provEl("provBaseUrl").value = p.base_url != null ? p.base_url : "";
      // ADR-007: show api_key as plaintext (no redaction).
      provEl("provApiKey").value = p.api_key != null ? p.api_key : "";
      provEl("provEnabled").checked = !!p.enabled;
      provEl("provModalTitle").textContent = getStr("providers.edit");
      renderHeadersEditor(headersToRows(p.custom_headers));
      provEl("provModal").hidden = false;
    }).catch(function (err) {
      setProvMsg(err.message, "error");
    });
  }

  function saveProvider(e) {
    if (e) e.preventDefault();
    var id = provEl("provId").value;
    var body = {
      name: provEl("provName").value,
      type: provEl("provType").value,
      base_url: provEl("provBaseUrl").value,
      api_key: provEl("provApiKey").value,
      enabled: provEl("provEnabled").checked,
      custom_headers: collectHeaders()
    };
    setProvMsg("");
    var req = id
      ? fetchJson(PROV_API + "/" + id, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        })
      : fetchJson(PROV_API, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        });
    req.then(function () {
      hideModal();
      loadProviders();
    }).catch(function (err) {
      setProvMsg(err.message, "error");
    });
  }

  /* ---- Detail + models ---- */
  function renderModels(models) {
    var body = provEl("provModelsBody");
    if (!body) return;
    models = models || [];
    if (!models.length) {
      body.innerHTML = '<tr><td colspan="2" class="empty-cell">' +
        escapeHtml(getStr("providers.no_models")) + "</td></tr>";
      return;
    }
    body.innerHTML = models.map(function (m) {
      return "<tr><td>" + escapeHtml(m.model_id) + "</td><td>" + escapeHtml(m.model_name) + "</td></tr>";
    }).join("");
  }

  function openDetail(id) {
    selectedProviderId = id;
    fetchJson(PROV_API + "/" + id).then(function (p) {
      provEl("provDetail").hidden = false;
      provEl("provDetailTitle").textContent = p.name || id;
      renderModels(p.models);
      setModelMsg("");
    }).catch(function (err) {
      setModelMsg(err.message, "error");
    });
  }

  function discoverModels(id) {
    id = id || selectedProviderId;
    if (!id) return;
    openDetail(id);
    setModelMsg(getStr("providers.discovering"), "");
    fetchJson(PROV_API + "/" + id + "/discover", {
      method: "POST", headers: { "Content-Type": "application/json" }
    }).then(function (res) {
      // Contract: {"ok":true,"models":[...]} OR {"ok":false,"error":"<msg>"}
      if (res && res.ok === false) {
        setModelMsg(res.error || getStr("providers.error"), "error");
        return;
      }
      var models = (res && res.models) ? res.models : [];
      renderModels(models);
      setModelMsg(getStr("providers.discovered") + " (" + models.length + ")", "ok");
      loadProviders(); // refresh model counts in the list
    }).catch(function (err) {
      setModelMsg(err.message, "error");
    });
  }

  function deleteProvider(id) {
    if (!window.confirm(getStr("providers.confirm_delete"))) return;
    fetchJson(PROV_API + "/" + id, { method: "DELETE" }).then(function () {
      if (selectedProviderId === id) provEl("provDetail").hidden = true;
      loadProviders();
    }).catch(function (err) {
      setProvMsg(err.message, "error");
    });
  }

  /* ===== Terminal view + Log Window (B3.1) ===== */
  var LOGS_API = "/api/logs";
  var TERM_COLLAPSE_KEY = "aigate.terminalCollapsed";
  var LOG_AUTO_REFRESH_MS = 3000;
  var logRefreshTimer = null;

  /* ---- Collapsible terminal pane ---- */
  function applyTermCollapse(collapsed) {
    var pane = document.getElementById("terminalPane");
    if (pane) pane.classList.toggle("terminal-collapsed", !!collapsed);
    var btn = document.getElementById("termCollapseBtn");
    if (btn) {
      var icon = btn.querySelector("i");
      if (icon) icon.className = collapsed ? "fa fa-chevron-down" : "fa fa-chevron-up";
      var label = getStr(collapsed ? "term.expand" : "term.collapse");
      btn.setAttribute("title", label);
      btn.setAttribute("aria-label", label);
      btn.setAttribute("aria-expanded", collapsed ? "false" : "true");
    }
  }

  function toggleTermCollapse() {
    var collapsed = !document.getElementById("terminalPane").classList.contains("terminal-collapsed");
    applyTermCollapse(collapsed);
    write(TERM_COLLAPSE_KEY, collapsed ? "collapsed" : "expanded");
  }

  /* ---- Log Window ---- */
  function logEl(id) { return document.getElementById(id); }

  function setLogMsg(text, kind) {
    var m = logEl("logMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function renderLogs(list) {
    var body = logEl("logTableBody");
    if (!body) return;
    list = list || [];
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="4" class="empty-cell">' +
        escapeHtml(getStr("term.no_logs")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(function (raw) {
      var row = formatLogRow(raw);
      var sev = severityClass(row.severity);
      var badge = '<span class="badge ' + sev + '">' + escapeHtml(row.severity) + "</span>";
      var stack = (row.stacktrace != null && row.stacktrace !== "")
        ? '<details class="log-stack"><summary>' + escapeHtml(getStr("term.stacktrace")) +
          '</summary><pre>' + escapeHtml(row.stacktrace) + "</pre></details>"
        : "";
      return "<tr>" +
        "<td class=\"log-time\">" + escapeHtml(row.timestamp) + "</td>" +
        "<td>" + badge + "</td>" +
        "<td>" + escapeHtml(row.source) + "</td>" +
        "<td>" + escapeHtml(row.message) + (stack ? "<br>" + stack : "") + "</td>" +
      "</tr>";
    }).join("");
  }

  function loadLogs() {
    var sevSel = logEl("logSeverity");
    var severity = sevSel ? sevSel.value : "all";
    var query = buildLogsQuery(severity, 200);
    fetchJson(LOGS_API + query).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderLogs(list);
      setLogMsg("");
    }).catch(function (err) {
      setLogMsg(getStr("term.logs_error") + " (" + err.message + ")", "error");
    });
  }

  function startLogAutoRefresh() {
    stopLogAutoRefresh();
    logRefreshTimer = setInterval(function () { loadLogs(); }, LOG_AUTO_REFRESH_MS);
  }

  function stopLogAutoRefresh() {
    if (logRefreshTimer !== null) {
      clearInterval(logRefreshTimer);
      logRefreshTimer = null;
    }
  }

  function initTerminalView() {
    // Restore collapse state from localStorage (mirrors sidebar persistence).
    var collapsed = read(TERM_COLLAPSE_KEY, "expanded") === "collapsed";
    applyTermCollapse(collapsed);
    loadLogs();
    startLogAutoRefresh();
  }

  function init() {
    var theme = read(THEME_KEY, DEFAULT_THEME);
    var locale = read(LOCALE_KEY, DEFAULT_LOCALE);
    var sidebar = read(SIDEBAR_KEY, DEFAULT_SIDEBAR);
    var device = read(DEVICE_KEY, DEFAULT_DEVICE);

    applyTheme(theme);
    applySidebar(sidebar);
    applyDevice(device);
    if (window.applyLocale) window.applyLocale(locale);
    markActiveLang(locale);

    // --- Theme toggle ---
    var themeBtn = document.getElementById("themeToggle");
    if (themeBtn) {
      themeBtn.addEventListener("click", function () {
        var current = document.documentElement.getAttribute("data-theme");
        var next = current === "dark" ? "light" : "dark";
        applyTheme(next);
        write(THEME_KEY, next);
      });
    }

    // --- Language switch ---
    document.querySelectorAll(".lang-btn").forEach(function (b) {
       b.addEventListener("click", function () {
        var next = b.getAttribute("data-lang");
        if (window.applyLocale) window.applyLocale(next);
        write(LOCALE_KEY, next);
        markActiveLang(next);
        // Keep terminal collapse-button label in sync with the new locale.
        var pane = document.getElementById("terminalPane");
        if (pane) applyTermCollapse(pane.classList.contains("terminal-collapsed"));
      });
    });

    // --- Sidebar toggle ---
    var sbBtn = document.getElementById("sidebarToggle");
    if (sbBtn) {
      sbBtn.addEventListener("click", function () {
        var collapsed = document.body.classList.toggle("sidebar-collapsed");
        write(SIDEBAR_KEY, collapsed ? "collapsed" : "expanded");
      });
    }

    // --- Device simulation toggle (B4.2): client-only, persisted. ---
    var devSel = document.getElementById("setDevice");
    if (devSel) {
      devSel.addEventListener("change", function () {
        var d = devSel.value;
        applyDevice(d);
        write(DEVICE_KEY, d);
      });
    }

    // --- Nav / view switching (top sidebar + mobile bottom-nav share logic) ---
    function handleNav(item) {
      var view = item.getAttribute("data-view");
      showView(view);
      setActiveNav(item);
      if (view === "settings") loadSettings();
      else if (view === "providers") loadProviders();
      else if (view === "terminal") {
        initTerminalView();
        // B3.3: open/refit the multi-tab terminal when its view is shown.
        if (window.aigate && window.aigate.terminalManager) {
          window.aigate.terminalManager.onShow();
        }
      } else if (view === "cli") {
        // B3.4: load + render the CLI Tools groups/presets.
        if (window.aigate && window.aigate.cliTools) {
          window.aigate.cliTools.onShow();
        }
        // B4.1: check the agentic CLI + arm the Self-Heal section.
        if (window.aigate && window.aigate.selfHeal) {
          window.aigate.selfHeal.onShow();
        }
      }
      // Leaving the terminal view: stop auto-refresh to avoid leaks.
      if (view !== "terminal") stopLogAutoRefresh();
    }

    document.querySelectorAll(".nav-item, .bn-item").forEach(function (item) {
      item.addEventListener("click", function (e) {
        e.preventDefault();
        handleNav(item);
      });
    });

    // --- Settings form ---
    var form = document.getElementById("settingsForm");
    if (form) form.addEventListener("submit", saveSettings);

    // --- Providers (B2.2) ---
    var provAdd = document.getElementById("provAddBtn");
    if (provAdd) provAdd.addEventListener("click", openAddModal);
    var provForm = document.getElementById("provForm");
    if (provForm) provForm.addEventListener("submit", saveProvider);
    var provCancel = document.getElementById("provCancel");
    if (provCancel) provCancel.addEventListener("click", hideModal);
    var provAddHdr = document.getElementById("provAddHeaderBtn");
    if (provAddHdr) provAddHdr.addEventListener("click", function () { addHeaderRow("", ""); });
    var provDisc = document.getElementById("provDiscoverBtn");
    if (provDisc) provDisc.addEventListener("click", function () { discoverModels(selectedProviderId); });
    var provEdit = document.getElementById("provEditBtn");
    if (provEdit) provEdit.addEventListener("click", function () { openEditModal(selectedProviderId); });
    var provDel = document.getElementById("provDeleteBtn");
    if (provDel) provDel.addEventListener("click", function () { deleteProvider(selectedProviderId); });
    var provModal = document.getElementById("provModal");
    if (provModal) provModal.addEventListener("click", function (e) {
      if (e.target === provModal) hideModal(); // click backdrop closes
    });

    // --- Terminal: collapse toggle ---
    var termCollapseBtn = document.getElementById("termCollapseBtn");
    if (termCollapseBtn) termCollapseBtn.addEventListener("click", toggleTermCollapse);

    // --- Log Window (B3.1) ---
    var logRefreshBtn = document.getElementById("logRefreshBtn");
    if (logRefreshBtn) logRefreshBtn.addEventListener("click", function () {
      loadLogs();
    });
    var logSeverity = document.getElementById("logSeverity");
    if (logSeverity) logSeverity.addEventListener("change", function () {
      loadLogs();
    });

    // Start on the welcome view.
    showView("welcome");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
