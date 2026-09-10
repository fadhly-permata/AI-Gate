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

  /* ---- Language dropdown (header) ----
     Trigger shows "[flag] [lang name]" of the ACTIVE locale; the menu lists
     every language as "[flag] [lang name]" too. Names resolve through the
     dictionary, so the dropdown follows the active language. */
  function langName(l) { return getStr(l.nameKey); }

  function updateLangUI(locale) {
    var langs = window.LANGS || [];
    var active = null;
    langs.forEach(function (l) { if (l.code === locale) active = l; });
    if (!active) active = langs[0];
    var trigFlag = document.getElementById("langTriggerFlag");
    var trigName = document.getElementById("langTriggerName");
    if (trigFlag && active) trigFlag.textContent = active.flag;
    if (trigName && active) trigName.textContent = langName(active);
    var menu = document.getElementById("langMenu");
    if (menu) {
      menu.innerHTML = langs.map(function (l) {
        return '<button type="button" class="lang-menu-item' +
          (active && l.code === active.code ? " active" : "") +
          '" data-lang="' + escapeHtml(l.code) + '" role="menuitem">' +
          '<span class="lang-flag">' + escapeHtml(l.flag) + "</span>" +
          '<span class="lang-name">' + escapeHtml(langName(l)) + "</span></button>";
      }).join("");
    }
  }

  function closeLangMenu() {
    var menu = document.getElementById("langMenu");
    var btn = document.getElementById("langMenuBtn");
    if (menu) menu.hidden = true;
    if (btn) btn.setAttribute("aria-expanded", "false");
  }

  function toggleLangMenu() {
    var menu = document.getElementById("langMenu");
    var btn = document.getElementById("langMenuBtn");
    if (!menu || !btn) return;
    var open = menu.hidden;
    menu.hidden = !open;
    btn.setAttribute("aria-expanded", open ? "true" : "false");
  }

  // Translate a key for the active (or given) locale. Key resolution and the
  // English fallback live in i18n.js (window.translate) — one implementation
  // for every caller. The bare-key return below only covers a page where
  // i18n.js never loaded.
  function getStr(key, loc) {
    loc = loc || document.documentElement.getAttribute("data-locale") || DEFAULT_LOCALE;
    if (typeof window.translate === "function") return window.translate(key, loc);
    return key;
  }

  // Switch the UI to a locale. i18n.js renders it at once (English stands in
  // while a language file is missing) and re-renders when that file arrives.
  function switchLocale(loc) {
    if (typeof window.setLocale === "function") window.setLocale(loc);
    else if (typeof window.applyLocale === "function") window.applyLocale(loc);
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

  /* ---- Locale options for the Settings select ----
     Built from the registry (window.LANGS) so adding a language never means
     editing index.html. Labels are endonyms ("日本語"), the same in every
     dictionary, so they never need re-rendering when the locale changes. */
  function populateLocaleOptions() {
    var sel = document.getElementById("setLocale");
    var langs = window.LANGS || [];
    if (!sel || !langs.length) return; // no registry -> keep the shipped markup
    // Priority: the locale the UI is actually showing (applyLocale sets
    // data-locale right before this runs at boot), then the stored preference.
    // The markup value is never authoritative — it is only the no-JS default.
    var current = document.documentElement.getAttribute("data-locale") ||
      read(LOCALE_KEY, DEFAULT_LOCALE);
    sel.innerHTML = langs.map(function (l) {
      return '<option value="' + escapeHtml(l.code) + '">' +
        escapeHtml(l.flag + " " + getStr(l.nameKey)) + "</option>";
    }).join("");
    sel.value = current;
    // Unknown stored value -> first option, so a save can never send "".
    if (sel.selectedIndex === -1) sel.selectedIndex = 0;
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
        switchLocale(f.locale.value);
        // Keep localStorage in sync with the topbar toggle / lang buttons.
        write(THEME_KEY, f.theme.value);
        write(LOCALE_KEY, f.locale.value);
        updateLangUI(f.locale.value);
        setMsg(getStr("settings.saved"), "ok");
      })
      .catch(function (err) {
        setMsg(getStr("settings.error") + " (" + err.message + ")", "error");
      });
  }

  /* Test hook: lets vitest assert the PUT body stringifies values. */
  window.aigate = window.aigate || {};
  window.aigate.buildSettingsBody = buildSettingsBody;

  /* ===== Backup & Restore (B5.7, PRD §2.4.4) ===== */
  /* Export/import the whole local config as one JSON file (no cloud). The export
     file carries secrets in plaintext by design (R11 / ADR-007). Errors are
     surfaced in the status line + console (ADR-011). */
  var EXPORT_URL = "/api/settings/export";
  var IMPORT_API = "/api/settings/import";

  function backupMsgEl() { return document.getElementById("backupMsg"); }

  function setBackupMsg(text, kind) {
    var m = backupMsgEl();
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
    if (kind === "error") {
      try { console.error("[backup] " + (text || "")); } catch (e) { /* no console */ }
    }
  }

  // Read the mode selector; anything but an explicit "merge" is "replace".
  function currentImportMode() {
    var sel = document.getElementById("importMode");
    var v = sel ? String(sel.value || "").toLowerCase() : "";
    return v === "merge" ? "merge" : "replace";
  }

  // Trigger the file download. The server sets the filename via
  // Content-Disposition, so the download attribute is left empty.
  function exportSettings() {
    var a = document.createElement("a");
    a.setAttribute("href", EXPORT_URL);
    a.setAttribute("download", "");
    a.rel = "noopener";
    a.style.display = "none";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setBackupMsg(getStr("settings.export.ok"), "ok");
    return EXPORT_URL;
  }

  // FileReader -> text, as a promise.
  function readFileText(file) {
    return new Promise(function (resolve, reject) {
      var reader = new FileReader();
      reader.onload = function () { resolve(reader.result); };
      reader.onerror = function () {
        reject(reader.error || new Error("read_error"));
      };
      reader.readAsText(file);
    });
  }

  // Pure-ish: format the per-table imported counts into a status string.
  function renderImportResult(result) {
    if (!result || result.ok !== true || !result.imported) {
      return getStr("settings.import.error");
    }
    var imported = result.imported;
    var parts = [];
    Object.keys(imported).forEach(function (k) {
      var n = imported[k];
      if (n == null) return;
      parts.push(k + ": " + n);
    });
    var base = getStr("settings.import.done");
    return parts.length ? (base + " " + parts.join(", ")) : base;
  }

  // After a successful import, refresh the views so the restored config shows.
  function reloadAfterImport() {
    try { loadSettings(); } catch (e) { /* ignore */ }
    try { loadProviders(); } catch (e) { /* ignore */ }
    ["combos", "proxies", "endpoints", "usage", "analytics"].forEach(function (m) {
      try {
        if (window.aigate && window.aigate[m] &&
            typeof window.aigate[m].onShow === "function") {
          window.aigate[m].onShow();
        }
      } catch (e) { /* module not loaded — ignore */ }
    });
  }

  // Read + parse + confirm + POST. Returns a promise resolving to the outcome.
  // The confirm + fetch live here so tests can drive them directly.
  function importSettingsFromFile(fileObj) {
    var mode = currentImportMode();
    return readFileText(fileObj).then(function (text) {
      var doc;
      try {
        doc = JSON.parse(text);
      } catch (e) {
        setBackupMsg(getStr("settings.import.invalid"), "error");
        return { ok: false, error: "invalid_json" };
      }
      var confirmKey = mode === "merge"
        ? "settings.import.confirm.merge" : "settings.import.confirm";
      if (!window.confirm(getStr(confirmKey))) {
        setBackupMsg(getStr("settings.import.cancelled"), "");
        return { ok: false, cancelled: true };
      }
      var url = IMPORT_API + "?mode=" + encodeURIComponent(mode);
      return fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(doc)
      }).then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (res) {
          res = res || {};
          if (r.ok && res.ok === true) {
            setBackupMsg(renderImportResult(res), "ok");
            reloadAfterImport();
            return res;
          }
          if (r.status === 400) {
            setBackupMsg(getStr("settings.import.invalid"), "error");
            return { ok: false, error: res.error || "invalid_format" };
          }
          var reason = res.error ? String(res.error) : ("HTTP " + r.status);
          setBackupMsg(getStr("settings.import.error") + " " + reason, "error");
          return { ok: false, error: reason, status: r.status };
        });
      }).catch(function (err) {
        setBackupMsg(getStr("settings.import.error") + " " + err.message, "error");
        return { ok: false, error: err.message };
      });
    }, function (err) {
      var reason = (err && err.message) ? err.message : "read_error";
      setBackupMsg(getStr("settings.import.error") + " " + reason, "error");
      return { ok: false, error: reason };
    });
  }

  window.aigate.exportSettings = exportSettings;
  window.aigate.importSettingsFromFile = importSettingsFromFile;
  window.aigate.renderImportResult = renderImportResult;
  window.aigate.setBackupMsg = setBackupMsg;
  window.aigate.currentImportMode = currentImportMode;

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
  window.aigate.renderProviders = renderProviders;
  window.aigate.buildHeadersDict = buildHeadersDict;
  window.aigate.headersToRows = headersToRows;
  window.aigate.saveProvider = saveProvider;
  window.aigate.openAddModal = openAddModal;
  window.aigate.openEditModal = openEditModal;
  window.aigate.discoverModels = discoverModels;
  window.aigate.populateModelCombobox = populateModelCombobox;
  // Modal tab wiring — exposed so tests can exercise the exact init() wiring.
  window.aigate.wireProvTabs = wireProvTabs;
  window.aigate.selectProvTab = selectProvTab;
  window.aigate.syncStickyLimitRow = syncStickyLimitRow;

  /* Shared helpers — exposed so the Combos / Proxy Pools / Endpoints modules
     (and tests) reuse the exact same fetch/escape/i18n behavior. */
  window.aigate.fetchJson = fetchJson;
  window.aigate.escapeHtml = escapeHtml;
  window.aigate.getStr = getStr;
  window.aigate.switchLocale = switchLocale;
  window.aigate.populateLocaleOptions = populateLocaleOptions;

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
        ? entry.stacktrace : null,
      resolved: entry.resolved === true
    };
  }

  // Build the querystring for GET /api/logs.
  // severity "all"/empty => omitted; limit omitted unless a positive number;
  // showResolved=true => resolved rows are included too (backend default false).
  function buildLogsQuery(severity, limit, showResolved) {
    var params = [];
    if (severity && severity !== "all") {
      params.push("severity=" + encodeURIComponent(severity));
    }
    if (limit != null && limit !== "" && !isNaN(Number(limit)) && Number(limit) > 0) {
      params.push("limit=" + Number(limit));
    }
    if (showResolved === true) {
      params.push("show_resolved=true");
    }
    return params.length ? "?" + params.join("&") : "";
  }

  // Build the querystring for DELETE /api/logs (T2 log cleanup).
  // The clear-dialog scope maps directly: "all" => wipe-all, which requires
  // the explicit confirm=all param; anything else (e.g. "warning,error") is
  // sent as the severity filter. Same encoding style as above.
  function buildClearLogsQuery(severity) {
    if (!severity || severity === "all") return "?confirm=all";
    return "?severity=" + encodeURIComponent(severity);
  }

  window.aigate.severityClass = severityClass;
  window.aigate.formatLogRow = formatLogRow;
  window.aigate.buildLogsQuery = buildLogsQuery;
  window.aigate.buildClearLogsQuery = buildClearLogsQuery;

  /* Log Window (global) helpers — exposed for tests + external control. */
  window.aigate.applyLogVisible = applyLogVisible;
  window.aigate.toggleLogVisible = toggleLogVisible;
  window.aigate.isLogVisible = isLogVisible;
  window.aigate.measureLogHeight = measureLogHeight;
  window.aigate.loadLogs = loadLogs;
  window.aigate.renderLogs = renderLogs;
  window.aigate.clearLogs = clearLogs;
  window.aigate.confirmClearLogs = confirmClearLogs;
  window.aigate.cancelClearLogs = cancelClearLogs;
  window.aigate.resolveLog = resolveLog;
  window.aigate.resolveAllLogs = resolveAllLogs;
  window.aigate.applyShowResolved = applyShowResolved;
  window.aigate.toggleShowResolved = toggleShowResolved;
  window.aigate.isShowResolved = readShowResolved;
  window.aigate.startLogAutoRefresh = startLogAutoRefresh;
  window.aigate.stopLogAutoRefresh = stopLogAutoRefresh;

  /* ---- DOM helpers ---- */
  function provEl(id) { return document.getElementById(id); }

  function setProvMsg(text, kind) {
    var m = provEl("provMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function setProvModalMsg(text, kind) {
    var m = provEl("provModalMsg");
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

  /* ---- Provider default-model: searchable combobox (combobox.js) ----
     #provModel is a text input + a custom <ul> panel (#provModelList) that
     filters as you type. This replaces the old <input list> + <datalist>,
     which never pops a dropdown on Android. The controller is created LAZILY
     and resolves its elements by id on every call, so it survives DOM
     rebuilds (tests). If combobox.js is somehow absent, the plain input still
     works (free text is the value either way). */
  var provModelCombo = null;

  function provModelCtl() {
    if (!provModelCombo && window.aigate &&
        typeof window.aigate.createCombobox === "function") {
      provModelCombo = window.aigate.createCombobox({
        inputId: "provModel",
        listId: "provModelList"
      });
    }
    return provModelCombo;
  }

  // The current default-model string (combobox value == input value).
  function provModelValue() {
    var c = provModelCtl();
    if (c) return c.getValue();
    var i = provEl("provModel");
    return i ? String(i.value || "") : "";
  }

  // Sort a model list by display name, ascending, case-insensitive.
  // Sort key = model_name || model_id. Returns a NEW array (never mutates).
  function sortModelsByName(models) {
    return (Array.isArray(models) ? models : []).slice().sort(function (a, b) {
      var an = String((a && (a.model_name || a.model_id)) || "").toLowerCase();
      var bn = String((b && (b.model_name || b.model_id)) || "").toLowerCase();
      if (an < bn) return -1;
      if (an > bn) return 1;
      return 0;
    });
  }

  // Map a raw ModelDTO list -> combobox {value,label} options (sorted by name).
  function modelOptions(models) {
    return sortModelsByName(models).map(function (m) {
      return { value: m.model_id, label: m.model_name || m.model_id };
    });
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
        // NOTE: pass onRejected as the 2nd arg of .then so it only catches a
        // failed r.json() parse — NOT the intentional throw above (which carries
        // the backend's real error message). Swallowing it would violate ADR-011.
        return r.json().then(function (b) {
          var msg = (b && b.error && b.error.message) ? b.error.message : ("HTTP " + r.status);
          var err = new Error(msg);
          err.status = r.status;
          throw err;
        }, function () { throw new Error("HTTP " + r.status); });
      }
      var ct = r.headers.get("content-type") || "";
      if (ct.indexOf("application/json") === -1) return null;
      return r.json();
    });
  }

  /* ---- Shared row action menu (kebab) ----
     ONE consistent pattern for every management table (Providers, Combos,
     Proxy Pools, Endpoints): an "Actions" column with a kebab button that
     opens a dropdown of row actions (Edit / Delete / …). The menu is a
     singleton appended to <body> (fixed positioning) so it never clips
     inside table overflow. Modules build the button via rowMenuCellHtml()
     and open it via rowMenu.open(btn, actions). */
  var rowMenuEl = null;
  var rowMenuBtn = null;

  function closeRowMenu() {
    if (!rowMenuEl) return;
    rowMenuEl.remove();
    rowMenuEl = null;
    if (rowMenuBtn) rowMenuBtn.setAttribute("aria-expanded", "false");
    rowMenuBtn = null;
  }

  function positionRowMenu(btn, menu) {
    var rect = btn.getBoundingClientRect();
    var w = menu.offsetWidth;
    var h = menu.offsetHeight;
    var left = Math.max(8, Math.min(rect.right - w, window.innerWidth - w - 8));
    var top = rect.bottom + 4;
    if (top + h > window.innerHeight - 8) top = Math.max(8, rect.top - h - 4);
    menu.style.left = left + "px";
    menu.style.top = top + "px";
  }

  function openRowMenu(btn, actions) {
    var reopen = rowMenuBtn === btn;
    closeRowMenu();
    if (reopen) return; // second click toggles closed
    var menu = document.createElement("div");
    menu.className = "row-menu";
    menu.setAttribute("role", "menu");
    (actions || []).forEach(function (a) {
      a = a || {};
      if (!a.label) return;
      var item = document.createElement("button");
      item.type = "button";
      item.className = "row-menu-item" + (a.danger ? " is-danger" : "");
      item.setAttribute("role", "menuitem");
      if (a.action) item.setAttribute("data-action", a.action);
      item.innerHTML = '<i class="fa ' + escapeHtml(a.icon || "fa-ellipsis") +
        '" aria-hidden="true"></i><span>' + escapeHtml(a.label) + "</span>";
      item.addEventListener("click", function () {
        closeRowMenu();
        if (typeof a.onClick === "function") a.onClick();
      });
      menu.appendChild(item);
    });
    document.body.appendChild(menu);
    positionRowMenu(btn, menu);
    menu.dataset.state = "open";
    btn.setAttribute("aria-expanded", "true");
    rowMenuEl = menu;
    rowMenuBtn = btn;
  }

  // Kebab cell markup for a table row. `actions` are resolved lazily by
  // rowMenu.open on click, so labels follow the active locale.
  function rowMenuCellHtml() {
    return '<td class="row-actions">' +
      '<button type="button" class="icon-btn-small js-row-menu" aria-haspopup="true" ' +
      'aria-expanded="false" title="' + escapeHtml(getStr("common.actions")) + '" ' +
      'aria-label="' + escapeHtml(getStr("common.actions")) + '">' +
      '<i class="fa fa-ellipsis-vertical"></i></button></td>';
  }

  function wireRowMenu(scope, getActions) {
    Array.prototype.forEach.call(
      (scope || document).querySelectorAll(".js-row-menu"), function (btn) {
        btn.addEventListener("click", function (e) {
          e.stopPropagation();
          var tr = btn.closest("tr");
          openRowMenu(btn, typeof getActions === "function" ? getActions(tr) : []);
        });
      });
  }

  function initRowMenuGlobal() {
    document.addEventListener("click", function (e) {
      if (rowMenuEl && !e.target.closest(".row-menu") && !e.target.closest(".js-row-menu")) {
        closeRowMenu();
      }
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeRowMenu();
    });
    window.addEventListener("resize", closeRowMenu);
    window.addEventListener("scroll", closeRowMenu, true);
  }

  window.aigate = window.aigate || {};
  window.aigate.rowMenu = { open: openRowMenu, close: closeRowMenu };
  window.aigate.rowMenuCellHtml = rowMenuCellHtml;
  window.aigate.wireRowMenu = wireRowMenu;

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
        escapeHtml(getStr("providers.no_items")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(function (p) {
      var row = mapProviderToRow(p);
      var badge = row.enabled
        ? '<span class="badge badge-ok">' + escapeHtml(getStr("providers.enabled")) + "</span>"
        : '<span class="badge badge-off">' + escapeHtml(getStr("providers.disabled")) + "</span>";
      // The name is the entry point to the detail card (usage + Edit/Delete):
      // the old way in was the kebab "Discover Models" action, but discovery
      // now runs silently and that action became redundant (stage-2).
      return '<tr class="prov-row" data-id="' + escapeHtml(row.id) + '">' +
        '<td class="prov-name"><button type="button" class="prov-name-btn js-prov-detail" data-id="' +
          escapeHtml(row.id) + '">' + escapeHtml(row.name) + "</button></td>" +
        "<td>" + escapeHtml(row.type) + "</td>" +
        "<td>" + escapeHtml(row.base_url) + "</td>" +
        "<td>" + badge + "</td>" +
        "<td>" + row.modelCount + "</td>" +
        rowMenuCellHtml() +
      "</tr>";
    }).join("");

    // Name button -> openDetail. One delegated listener on the tbody (the node
    // survives innerHTML re-renders; the flag stops per-call listener buildup
    // when a test rebuilds the tbody it re-attaches on the fresh node).
    if (body.getAttribute("data-detail-wired") !== "1") {
      body.setAttribute("data-detail-wired", "1");
      body.addEventListener("click", function (e) {
        var btn = e.target.closest ? e.target.closest(".js-prov-detail") : null;
        if (!btn) return;
        var id = btn.getAttribute("data-id");
        if (id != null) openDetail(id);
      });
    }

    // Consistent with the other tables: actions live in the kebab menu only.
    wireRowMenu(body, function (tr) {
      var id = tr ? tr.getAttribute("data-id") : null;
      return [
        { action: "edit", label: getStr("common.edit"), icon: "fa-pen", onClick: function () { openEditModal(id); } },
        { action: "delete", label: getStr("common.delete"), icon: "fa-trash", danger: true, onClick: function () { deleteProvider(id); } }
      ];
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
      '<button type="button" class="icon-btn-small hdr-del" aria-label="' +
        escapeHtml(getStr("common.remove")) + '">' +
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

  /* ---- Modal tabs: [Provider] | [Accounts] (stage-2) ----
     One WAI-ARIA tablist with a roving tabindex; panels toggle `hidden`.
     In ADD mode the Accounts tab is aria-disabled (no provider id to attach
     accounts to) and #provTabHint explains — never silently dead controls. */
  function provTabButtons() {
    return [provEl("provTabProvider"), provEl("provTabAccounts")];
  }

  function provPanels() {
    return [provEl("provPanelProvider"), provEl("provPanelAccounts")];
  }

  function accountsTabEnabled() {
    var t = provEl("provTabAccounts");
    return !!t && t.getAttribute("aria-disabled") !== "true";
  }

  function setAccountsTabEnabled(on) {
    var t = provEl("provTabAccounts");
    var hint = provEl("provTabHint");
    if (hint) hint.hidden = !!on;
    if (!t) return;
    if (on) {
      t.removeAttribute("aria-disabled");
    } else {
      t.setAttribute("aria-disabled", "true");
      t.tabIndex = -1;
      if (t.getAttribute("aria-selected") === "true") selectProvTab(0);
    }
  }

  // Activate panel `idx` (0 Provider, 1 Accounts). A disabled Accounts tab
  // falls back to Provider. moveFocus = keyboard interaction (arrow keys).
  function selectProvTab(idx, moveFocus) {
    var tabs = provTabButtons();
    var panels = provPanels();
    if (!tabs[idx]) return;
    if (idx === 1 && !accountsTabEnabled()) idx = 0;
    tabs.forEach(function (t, i) {
      if (!t) return;
      var on = i === idx;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      t.classList.toggle("is-active", on);
    });
    panels.forEach(function (p, i) {
      if (p) p.hidden = i !== idx;
    });
    if (moveFocus && tabs[idx] && typeof tabs[idx].focus === "function") {
      tabs[idx].focus();
    }
  }

  // Left/Right move (wrapping), Home/End jump — across ENABLED tabs only.
  function provTabKeydown(e) {
    var tabs = provTabButtons();
    var current = tabs.indexOf(document.activeElement);
    if (current === -1) return;
    var enabled = [0, 1].filter(function (i) {
      return i === 0 || accountsTabEnabled();
    });
    var pos = enabled.indexOf(current);
    if (pos === -1) return;
    var next = null;
    if (e.key === "ArrowRight") next = enabled[(pos + 1) % enabled.length];
    else if (e.key === "ArrowLeft") next = enabled[(pos - 1 + enabled.length) % enabled.length];
    else if (e.key === "Home") next = enabled[0];
    else if (e.key === "End") next = enabled[enabled.length - 1];
    if (next === null) return;
    e.preventDefault();
    selectProvTab(next, true);
  }

  function wireProvTabs() {
    var tabs = provTabButtons();
    tabs.forEach(function (t, i) {
      if (!t) return;
      t.addEventListener("click", function () { selectProvTab(i); });
    });
    var list = provEl("provTabList");
    if (list) list.addEventListener("keydown", provTabKeydown);
  }

  /* ---- Strategy controls (stage-2, adopsi 9router) ----
     sticky_round_robin_limit is only meaningful while strategy=round-robin:
     for fill-first the row is hidden AND the input disabled, so saveProvider
     can skip the field instead of pretending a dead value was sent. */
  function strategyIsRoundRobin() {
    var sel = provEl("provStrategy");
    return !!sel && sel.value === "round-robin";
  }

  function syncStickyLimitRow() {
    var rr = strategyIsRoundRobin();
    var row = provEl("provStickyRow");
    var inp = provEl("provStickyLimit");
    if (row) row.hidden = !rr;
    if (inp) inp.disabled = !rr;
  }

  function openAddModal() {
    selectedProviderId = null;
    var f = provEl("provForm");
    if (f) f.reset();
    provEl("provId").value = "";
    provEl("provModalTitle").textContent = getStr("providers.add");
    renderHeadersEditor([]);
    // Fresh provider: clear any stale discovered options + value from a prior
    // edit (free text still works with an empty option list).
    var c = provModelCtl();
    if (c) { c.setOptions([]); c.setValue(""); c.close(); }
    // Strategy defaults: fill-first + limit 3 (the HTML form defaults).
    syncStickyLimitRow();
    // No id yet -> the Accounts tab cannot attach anything; hint explains.
    setAccountsTabEnabled(false);
    selectProvTab(0);
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
      // Rotation strategy (stage-1 contract): enum is exactly fill-first |
      // round-robin; anything unexpected falls back to the default instead of
      // echoing a value the backend would reject with 400 later.
      var sel = provEl("provStrategy");
      if (sel) {
        sel.value = p.fallback_strategy === "round-robin" ? "round-robin" : "fill-first";
      }
      var lim = provEl("provStickyLimit");
      if (lim) {
        var n = parseInt(p.sticky_round_robin_limit, 10);
        lim.value = isNaN(n) ? 3 : n;
      }
      syncStickyLimitRow();
      // Default model: seed the combobox with this provider's known models
      // (sorted) and set the stored value. A custom (undiscovered) value is
      // still shown because the input holds any string.
      var mc = provModelCtl();
      if (mc) { mc.setOptions(modelOptions(p.models)); mc.setValue(p.default_model); }
      else provEl("provModel").value = p.default_model != null ? p.default_model : "";
      provEl("provModalTitle").textContent = getStr("providers.edit");
      renderHeadersEditor(headersToRows(p.custom_headers));
      // Accounts live in this modal now (tab 2): enable the tab + load list.
      setAccountsTabEnabled(true);
      selectProvTab(0);
      loadAccounts(id);
      // Silent model refresh: no status message, no table — feeds only the
      // combobox options + list counts once it lands (stage-2 decision).
      discoverModels(id, { quiet: true });
      provEl("provModal").hidden = false;
    }).catch(function (err) {
      setProvMsg(err.message, "error");
    });
  }

  /* ---- Test Connection (uses current form values, no save needed) ---- */
  function testProviderConnection() {
    var btn = provEl("provTestBtn");
    var previousLabel = btn ? btn.textContent : "";
    if (btn) {
      btn.disabled = true;
      btn.textContent = "...";
    }
    setProvModalMsg("");
    var payload = {
      type: provEl("provType").value,
      base_url: provEl("provBaseUrl").value,
      api_key: provEl("provApiKey").value,
      model: provModelValue()
    };
    fetch("/api/providers/test", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(payload)
    })
      .then(function (r) { return r.json(); })
      .then(function (res) {
        if (res && res.ok === true) {
          setProvModalMsg(getStr("providers.test_ok"), "ok");
        } else {
          var err = (res && res.error) ? res.error : getStr("providers.error");
          setProvModalMsg(getStr("providers.test_fail") + err, "error");
        }
      })
      .catch(function (err) {
        setProvModalMsg(getStr("providers.test_fail") + err.message, "error");
      })
      .then(function () {
        if (btn) {
          btn.disabled = false;
          btn.textContent = previousLabel;
        }
      });
  }

  window.aigate.testProviderConnection = testProviderConnection;

  function saveProvider(e) {
    if (e) e.preventDefault();
    var id = provEl("provId").value;
    var body = {
      name: provEl("provName").value,
      type: provEl("provType").value,
      base_url: provEl("provBaseUrl").value,
      api_key: provEl("provApiKey").value,
      default_model: provModelValue(),
      enabled: provEl("provEnabled").checked,
      custom_headers: collectHeaders(),
      // Stage-1 contract: strategy is always sent (enum select cannot emit
      // anything else); the sticky limit goes along ONLY when round-robin —
      // hidden+disabled-for-fill-first must not masquerade as a live value.
      fallback_strategy: provEl("provStrategy") ? provEl("provStrategy").value : "fill-first"
    };
    if (strategyIsRoundRobin()) {
      var limEl = provEl("provStickyLimit");
      var lim = limEl ? parseInt(limEl.value, 10) : NaN;
      body.sticky_round_robin_limit = isNaN(lim) ? 3 : Math.max(1, lim);
    }
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

  /* ---- Detail card (stage-2 tidy) ----
     The discovered-models TABLE is gone (it cluttered the card); /discover
     now runs quietly from openDetail/openEditModal and feeds only the
     #provModel combobox + the "Models" count column. renderModels() died with
     its table. */

  // Load discovered models into the #provModel combobox panel (sorted by name).
  // Replaces the old populateModelDatalist(): a <datalist> never pops on
  // Android, so the searchable combobox renders its own <ul> instead.
  function populateModelCombobox(models) {
    var c = provModelCtl();
    if (c) c.setOptions(modelOptions(models));
  }

  // skipDiscover: the legacy non-quiet discoverModels() opens the detail card
  // itself and then runs its OWN (visible) discovery — no duplicate POST.
  function openDetail(id, skipDiscover) {
    selectedProviderId = id;
    fetchJson(PROV_API + "/" + id).then(function (p) {
      provEl("provDetail").hidden = false;
      provEl("provDetailTitle").textContent = p.name || id;
      // B5.5: refresh the per-provider Usage subsection (day summary).
      if (window.aigate && window.aigate.usage &&
          typeof window.aigate.usage.loadProviderUsage === "function") {
        window.aigate.usage.loadProviderUsage(id);
      }
      if (!skipDiscover) discoverModels(id, { quiet: true });
    }).catch(function (err) {
      setProvMsg(err.message, "error");
    });
  }

  // Discovery runs quietly (stage-2): modal/detail opens trigger it without
  // any status chatter; the only UI effect is fresh combobox options.
  // discoverSeq: if the user moved on to another provider while a response
  // was in flight, the stale list must never overwrite the current one.
  var discoverSeq = 0;

  function discoverModels(id, opts) {
    opts = opts || {};
    id = id || selectedProviderId;
    if (!id) return;
    var quiet = !!opts.quiet;
    var seq = ++discoverSeq;
    var mc = provModelCtl();
    if (!quiet) {
      // Legacy visible path (window.aigate.discoverModels — kept for tests
      // and any internal caller): status text + loading state on the field.
      openDetail(id, true);
      setModelMsg(getStr("providers.discovering"), "");
      if (mc) mc.setLoading(true); // disable field + "Loading models…" row
    }
    fetchJson(PROV_API + "/" + id + "/discover", {
      method: "POST", headers: { "Content-Type": "application/json" }
    }).then(function (res) {
      if (seq !== discoverSeq) return; // a newer discovery superseded this one
      if (!quiet && mc) mc.setLoading(false);
      // Contract: {"ok":true,"models":[...]} OR {"ok":false,"error":"<msg>"}
      if (res && res.ok === false) {
        if (!quiet) setModelMsg(res.error || getStr("providers.error"), "error");
        return;
      }
      var models = (res && res.models) ? res.models : [];
      populateModelCombobox(models);
      if (!quiet) {
        setModelMsg(getStr("providers.discovered") + " (" + models.length + ")", "ok");
      }
      loadProviders(); // refresh model counts in the list
    }).catch(function (err) {
      if (seq !== discoverSeq) return;
      if (!quiet) {
        if (mc) mc.setLoading(false);
        setModelMsg(err.message, "error");
        return;
      }
      // Quiet mode never blocks the form with an error, but the failure is
      // not swallowed either — leave it in the console (R12).
      if (typeof console !== "undefined" && console.warn) {
        console.warn("aigate: silent model discovery failed:", err.message);
      }
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

  /* ===== Provider Accounts (B5.1): multi-account per provider + OAuth ===== */
  var ACC_API = "/api/accounts";
  var oauthPollTimer = null;
  var OAUTH_POLL_MS = 2000;
  var OAUTH_POLL_MAX = 15;

  function setAccountsMsg(text, kind) {
    var m = provEl("accountsMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  // Render a GET /api/accounts payload into #accountsBody (modal Accounts tab).
  // Column order mirrors the stage-1 contract: list arrives sorted by
  // priority asc, id asc; last_used_at belongs to the ENGINE (read-only —
  // never sent back, PUT only accepts {priority}).
  function renderAccounts(list) {
    var body = provEl("accountsBody");
    if (!body) return;
    list = list || [];
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty-cell">' +
        escapeHtml(getStr("accounts.none")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(function (a) {
      var credential;
      if (a.auth_type === "oauth") {
        credential = '<span class="badge badge-ok">' +
          escapeHtml(getStr("accounts.oauth_badge")) + " ✓</span>";
        if (a.expires_at) {
          credential += ' <span class="acc-expires">' +
            escapeHtml(getStr("accounts.expires")) + ": " +
            escapeHtml(a.expires_at) + "</span>";
        }
      } else {
        // ADR-007: show api_key plaintext, no masking.
        credential = a.api_key != null ? escapeHtml(a.api_key) : "";
      }
      // Priority: small number tried first; malformed/missing -> 0 (default).
      var pr = parseInt(a.priority, 10);
      pr = isNaN(pr) ? 0 : pr;
      // Last used: machine-owned ISO timestamp, or the i18n "never" marker —
      // never a blank cell pretending to be data.
      var lastUsed = a.last_used_at
        ? escapeHtml(a.last_used_at)
        : '<span class="acc-never">' + escapeHtml(getStr("accounts.never_used")) + "</span>";
      return '<tr class="acc-row" data-id="' + escapeHtml(a.id) + '">' +
        "<td>" + escapeHtml(a.label) + "</td>" +
        "<td>" + escapeHtml(a.auth_type) + "</td>" +
        "<td>" + credential + "</td>" +
        '<td><input type="number" class="form-input acc-priority" min="0" step="1" ' +
          'value="' + escapeHtml(pr) + '" data-priority="' + escapeHtml(pr) + '" ' +
          'aria-label="' + escapeHtml(getStr("accounts.priority")) + '" /></td>' +
        '<td class="acc-last-used">' + lastUsed + "</td>" +
        '<td class="row-actions">' +
          '<button type="button" class="icon-btn-small js-acc-del" title="' +
            escapeHtml(getStr("accounts.delete")) + '">' +
            '<i class="fa fa-trash"></i></button>' +
        "</td>" +
      "</tr>";
    }).join("");

    Array.prototype.forEach.call(body.querySelectorAll(".js-acc-del"), function (btn) {
      btn.addEventListener("click", function () {
        var tr = btn.closest(".acc-row");
        var id = tr ? tr.getAttribute("data-id") : null;
        if (id != null) deleteAccount(id);
      });
    });

    // Priority is committed on `change` (not per keystroke): blur/Enter sends
    // one PUT {priority} and reloads the list in the new order.
    Array.prototype.forEach.call(body.querySelectorAll(".acc-priority"), function (inp) {
      inp.addEventListener("change", function () {
        var tr = inp.closest(".acc-row");
        var id = tr ? tr.getAttribute("data-id") : null;
        if (id == null) return;
        var next = parseInt(inp.value, 10);
        if (isNaN(next) || next < 0) next = 0;
        inp.value = String(next);
        if (String(next) === inp.getAttribute("data-priority")) return; // no-op edit
        updateAccountPriority(id, next);
      });
    });
  }

  // PUT /api/accounts/<id> with ONLY {priority} (contract: no other field is
  // accepted — last_used_at stays machine-owned).
  function updateAccountPriority(id, priority) {
    setAccountsMsg("");
    return fetchJson(ACC_API + "/" + encodeURIComponent(id), {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ priority: priority })
    }).then(function () {
      return loadAccounts(selectedProviderId);
    }).catch(function (err) {
      setAccountsMsg(err.message, "error");
    });
  }

  // GET /api/accounts?provider_id=<id> then render.
  function loadAccounts(providerId) {
    providerId = providerId != null ? providerId : selectedProviderId;
    if (providerId == null) {
      renderAccounts([]);
      return Promise.resolve([]);
    }
    setAccountsMsg("");
    return fetchJson(ACC_API + "?provider_id=" + encodeURIComponent(providerId))
      .then(function (data) {
        var list = (data && data.data) ? data.data : [];
        renderAccounts(list);
        return list;
      })
      .catch(function (err) {
        setAccountsMsg(err.message, "error");
        return [];
      });
  }

  // POST /api/accounts. opts may carry {provider_id,label,auth_type,api_key,
  // priority} to bypass the form (used by tests); otherwise reads the form
  // fields. priority defaults to 0 (contract: small number tried first).
  function addAccount(opts) {
    opts = opts || {};
    var providerId = opts.provider_id != null ? opts.provider_id
      : (selectedProviderId != null ? selectedProviderId : null);
    var label = opts.label != null ? opts.label
      : (provEl("accLabel") ? provEl("accLabel").value : "");
    var auth_type = opts.auth_type != null ? opts.auth_type
      : (provEl("accAuthType") ? provEl("accAuthType").value : "api_key");
    var api_key = opts.api_key != null ? opts.api_key
      : (provEl("accApiKey") ? provEl("accApiKey").value : "");
    var priority = opts.priority != null ? parseInt(opts.priority, 10)
      : (provEl("accPriority") ? parseInt(provEl("accPriority").value, 10) : 0);
    if (isNaN(priority) || priority < 0) priority = 0;
    if (providerId == null) {
      setAccountsMsg(getStr("accounts.provider_required"), "error");
      return Promise.resolve();
    }
    var body = {
      provider_id: providerId, label: label,
      auth_type: auth_type, priority: priority
    };
    if (auth_type === "api_key") body.api_key = api_key;
    setAccountsMsg("");
    return fetchJson(ACC_API, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body)
    }).then(function () {
      if (provEl("accLabel")) provEl("accLabel").value = "";
      if (provEl("accApiKey")) provEl("accApiKey").value = "";
      if (provEl("accPriority")) provEl("accPriority").value = "0";
      return loadAccounts(providerId);
    }).catch(function (err) {
      setAccountsMsg(getStr("accounts.add_error") + " (" + err.message + ")", "error");
    });
  }

  // DELETE /api/accounts/<id>, then re-render the list.
  function deleteAccount(id) {
    if (!window.confirm(getStr("accounts.delete_confirm"))) return Promise.resolve();
    setAccountsMsg("");
    return fetchJson(ACC_API + "/" + encodeURIComponent(id), { method: "DELETE" })
      .then(function () { return loadAccounts(selectedProviderId); })
      .catch(function (err) { setAccountsMsg(err.message, "error"); });
  }

  // Raw POST to /api/oauth/<id>/start; surfaces the error code for detection.
  function startOAuth(providerId) {
    return fetch("/api/oauth/" + encodeURIComponent(providerId) + "/start", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" }
    }).then(function (r) {
      if (!r.ok) {
        // Use .then(onFulfilled, onRejected) so onRejected only catches a failed
        // r.json() parse — NOT the intentional throw that carries {code,message}.
        return r.json().then(function (b) {
          var code = (b && b.error) ? b.error : null;
          var msg = (b && b.message) ? b.message : ("HTTP " + r.status);
          var err = new Error(msg);
          err.code = code;
          err.status = r.status;
          throw err;
        }, function () {
          var e = new Error("HTTP " + r.status);
          e.code = null;
          throw e;
        });
      }
      return r.json();
    });
  }

  function startOAuthPoll(providerId) {
    stopOAuthPoll();
    var tries = 0;
    oauthPollTimer = setInterval(function () {
      tries++;
      fetchJson(ACC_API + "?provider_id=" + encodeURIComponent(providerId))
        .then(function (data) {
          var list = (data && data.data) ? data.data : [];
          var found = list.some(function (a) { return a.auth_type === "oauth"; });
          if (found || tries >= OAUTH_POLL_MAX) {
            stopOAuthPoll();
            renderAccounts(list);
            if (found) setAccountsMsg(getStr("accounts.oauth_ok"), "ok");
            else setAccountsMsg(getStr("accounts.oauth_timeout"), "error");
          }
        })
        .catch(function (err) {
          if (tries >= OAUTH_POLL_MAX) {
            stopOAuthPoll();
            setAccountsMsg(err.message, "error");
          }
        });
    }, OAUTH_POLL_MS);
  }

  function stopOAuthPoll() {
    if (oauthPollTimer !== null) {
      clearInterval(oauthPollTimer);
      oauthPollTimer = null;
    }
  }

  // Kick off OAuth: start -> open authorize_url -> poll for the new account.
  function connectOAuth(providerId) {
    providerId = providerId != null ? providerId : selectedProviderId;
    if (providerId == null) {
      setAccountsMsg(getStr("accounts.provider_required"), "error");
      return;
    }
    setAccountsMsg(getStr("accounts.oauth_waiting"), "");
    startOAuth(providerId).then(function (res) {
      if (res && res.authorize_url) {
        if (typeof window.open === "function") window.open(res.authorize_url, "_blank");
        startOAuthPoll(providerId);
      } else {
        setAccountsMsg(getStr("accounts.oauth_not_configured"), "error");
      }
    }).catch(function (err) {
      if (err && err.code === "oauth_not_configured") {
        setAccountsMsg(getStr("accounts.oauth_not_configured"), "error");
      } else {
        setAccountsMsg(err.message, "error");
      }
    });
  }

  window.aigate.renderAccounts = renderAccounts;
  window.aigate.loadAccounts = loadAccounts;
  window.aigate.addAccount = addAccount;
  window.aigate.deleteAccount = deleteAccount;
  window.aigate.connectOAuth = connectOAuth;

  /* ===== Terminal view + Log Window (B3.1) ===== */
  var LOGS_API = "/api/logs";
  var LOG_VISIBLE_KEY = "aigate.logVisible";
  var LOG_AUTO_REFRESH_MS = 3000;
  var logRefreshTimer = null;
  var logResizeObserver = null;

  /* ---- Global Log Window: show/hide (NOT expand/collapse) ----
     The whole #logWindow panel is toggled via the topbar icon. When visible we
     reserve its height at the bottom of the workspace (--log-h) so the fixed,
     bottom-docked panel never overlaps the terminal / view content. */
  function setLogHeightVar(px) {
    var h = px > 0 ? px : 0;
    document.documentElement.style.setProperty("--log-h", h + "px");
  }

  /* Measure the docked panel and publish --log-h. jsdom returns 0 (no layout),
     which is fine — the class/attr logic is what the tests assert. */
  function measureLogHeight() {
    var lw = document.getElementById("logWindow");
    if (!lw || lw.hidden) { setLogHeightVar(0); return; }
    var h = 0;
    if (typeof lw.getBoundingClientRect === "function") {
      h = lw.getBoundingClientRect().height || 0;
    }
    if (!h && lw.offsetHeight) h = lw.offsetHeight;
    setLogHeightVar(h);
  }

  function applyLogVisible(visible) {
    visible = !!visible;
    var lw = document.getElementById("logWindow");
    if (lw) lw.hidden = !visible;
    document.body.classList.toggle("log-visible", visible);
    var btn = document.getElementById("logWindowToggle");
    if (btn) {
      btn.setAttribute("aria-pressed", visible ? "true" : "false");
      var label = getStr(visible ? "log.hide" : "log.show");
      btn.setAttribute("title", label);
      btn.setAttribute("aria-label", label);
    }
    // Reserve space only while shown; collapse the reservation when hidden.
    if (visible) measureLogHeight();
    else setLogHeightVar(0);
  }

  function toggleLogVisible() {
    var next = !isLogVisible();
    applyLogVisible(next);
    write(LOG_VISIBLE_KEY, next ? "1" : "0");
  }

  function isLogVisible() {
    var lw = document.getElementById("logWindow");
    return !!(lw && !lw.hidden);
  }

  /* Keep --log-h in sync when the panel resizes (logs grow, sidebar toggles).
     Guarded: ResizeObserver is absent in headless test envs. */
  function observeLogWindow() {
    if (typeof ResizeObserver !== "function") return;
    var lw = document.getElementById("logWindow");
    if (!lw) return;
    if (logResizeObserver) { try { logResizeObserver.disconnect(); } catch (e) {} }
    logResizeObserver = new ResizeObserver(function () { measureLogHeight(); });
    logResizeObserver.observe(lw);
  }

  /* ---- Log Window ---- */
  function logEl(id) { return document.getElementById(id); }

  function setLogMsg(text, kind) {
    var m = logEl("logMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  /* ---- T2 log cleanup state ---- */
  var LOG_SHOW_RESOLVED_KEY = "aigate.logShowResolved";
  // Last rendered (normalized) rows — resolve-all operates on these.
  var lastLogRows = [];

  function isResolvableSeverity(sev) {
    var s = (sev || "").toString().toLowerCase();
    return s === "warning" || s === "error";
  }

  function readShowResolved() {
    return read(LOG_SHOW_RESOLVED_KEY, "0") === "1";
  }

  // Sync the toggle button state (aria-pressed + label) from localStorage.
  function applyShowResolved() {
    var on = readShowResolved();
    var btn = logEl("logShowResolvedBtn");
    if (btn) {
      btn.setAttribute("aria-pressed", on ? "true" : "false");
      var label = getStr("log.show_resolved");
      btn.setAttribute("title", label);
      btn.setAttribute("aria-label", label);
    }
    return on;
  }

  function toggleShowResolved() {
    write(LOG_SHOW_RESOLVED_KEY, readShowResolved() ? "0" : "1");
    applyShowResolved();
  }

  function renderLogs(list) {
    var body = logEl("logTableBody");
    if (!body) return;
    list = list || [];
    lastLogRows = list.map(function (raw) { return formatLogRow(raw); });
    if (!lastLogRows.length) {
      body.innerHTML = '<tr><td colspan="4" class="empty-cell">' +
        escapeHtml(getStr("term.no_logs")) + "</td></tr>";
      return;
    }
    body.innerHTML = lastLogRows.map(function (row) {
      var sev = severityClass(row.severity);
      var badge = '<span class="badge ' + sev + '">' + escapeHtml(row.severity) + "</span>";
      if (row.resolved) {
        badge += '<span class="badge sev-info log-resolved-badge">' +
          escapeHtml(getStr("log.resolved")) + "</span>";
      }
      var stack = (row.stacktrace != null && row.stacktrace !== "")
        ? '<details class="log-stack"><summary>' + escapeHtml(getStr("term.stacktrace")) +
          '</summary><pre>' + escapeHtml(row.stacktrace) + "</pre></details>"
        : "";
      // Per-row resolve: only for unresolved warning|error rows.
      var resolveBtn = (!row.resolved && isResolvableSeverity(row.severity))
        ? '<button type="button" class="log-resolve-btn" data-id="' +
          escapeHtml(row.id) + '" title="' + escapeHtml(getStr("log.resolve")) +
          '" aria-label="' + escapeHtml(getStr("log.resolve")) + '">' +
          '<i class="fa fa-check"></i></button>'
        : "";
      return "<tr" + (row.resolved ? ' class="log-row-resolved"' : "") + ">" +
        '<td class="log-time">' + escapeHtml(row.timestamp) + "</td>" +
        "<td>" + badge + "</td>" +
        "<td>" + escapeHtml(row.source) + "</td>" +
        "<td>" + escapeHtml(row.message) + (stack ? "<br>" + stack : "") + resolveBtn + "</td>" +
      "</tr>";
    }).join("");
  }

  // Optional (msg, kind): status shown after the reload lands — lets action
  // handlers (clear/resolve) keep their success message visible post-refresh.
  function loadLogs(successMsg, successKind) {
    var sevSel = logEl("logSeverity");
    var severity = sevSel ? sevSel.value : "all";
    var query = buildLogsQuery(severity, 200, readShowResolved());
    fetchJson(LOGS_API + query).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderLogs(list);
      setLogMsg(successMsg || "", successKind);
    }).catch(function (err) {
      setLogMsg(getStr("term.logs_error") + " (" + err.message + ")", "error");
    });
  }

  /* ---- T2 log cleanup ---- */

  var LOG_CLEAR_MODAL = "logClearModal";
  var LOG_CLEAR_SCOPE = "logClearScope";

  // Irreversible delete -> ALWAYS confirm via the dialog first. The scope
  // (severity choice) lives in the dialog, NOT the filter select: default is
  // "Warnings + Errors" (?severity=warning,error); "All logs" wipes every
  // entry and therefore sends the backend's explicit ?confirm=all.
  // Cancel / backdrop => no request.
  function clearLogs() {
    var modal = logEl(LOG_CLEAR_MODAL);
    if (!modal) return;
    var scope = logEl(LOG_CLEAR_SCOPE);
    if (scope) scope.value = "warning,error"; // safe default, every open
    modal.hidden = false;
  }

  function cancelClearLogs() {
    var modal = logEl(LOG_CLEAR_MODAL);
    if (modal) modal.hidden = true;
  }

  function confirmClearLogs() {
    cancelClearLogs(); // close first; the request fires right after either way
    var scope = logEl(LOG_CLEAR_SCOPE);
    var value = scope ? scope.value : "warning,error";
    var query = buildClearLogsQuery(value);
    fetchJson(LOGS_API + query, { method: "DELETE" }).then(function (data) {
      var deleted = (data && data.deleted != null) ? data.deleted : 0;
      loadLogs(getStr("log.cleared").replace("{n}", String(deleted)), "ok");
    }).catch(function (err) {
      setLogMsg(getStr("term.logs_error") + " (" + err.message + ")", "error");
    });
  }

  // Resolve a single row: POST /api/logs/{id}/resolve -> {"resolved": N}.
  function resolveLog(id) {
    fetchJson(LOGS_API + "/" + encodeURIComponent(id) + "/resolve", { method: "POST" })
      .then(function (data) {
        var n = (data && data.resolved != null) ? data.resolved : 1;
        lastLogRows.forEach(function (r) { if (r.id === id) r.resolved = true; });
        loadLogs(getStr("log.resolved_n").replace("{n}", String(n)), "ok");
      }).catch(function (err) {
        setLogMsg(getStr("term.logs_error") + " (" + err.message + ")", "error");
      });
  }

  // Resolve every currently rendered unresolved warning|error row (non-destructive,
  // no confirm). POST /api/logs/resolve {"ids":[...]} -> {"resolved": N}.
  function resolveAllLogs() {
    var ids = lastLogRows
      .filter(function (r) { return !r.resolved && isResolvableSeverity(r.severity); })
      .map(function (r) { return r.id; });
    if (!ids.length) return;
    fetchJson(LOGS_API + "/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ids: ids })
    }).then(function (data) {
      var n = (data && data.resolved != null) ? data.resolved : ids.length;
      loadLogs(getStr("log.resolved_n").replace("{n}", String(n)), "ok");
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

  /* Shared accessible popovers for controls whose visible content is only an
     icon. Delegation covers buttons rendered later by view modules. Native
     title remains intact as a browser fallback; aria-label is preferred so
     locale updates are reflected immediately. */
  var iconPopover = null;
  var iconPopoverTarget = null;
  var iconPopoverTimer = null;

  function clearIconPopoverTimer() {
    if (iconPopoverTimer !== null) {
      clearTimeout(iconPopoverTimer);
      iconPopoverTimer = null;
    }
  }

  function iconOnlyControl(node) {
    if (!node || !node.matches || !node.matches("button, a")) return false;
    if (node.matches(".js-row-menu, .lang-menu-btn")) return false;
    if (node.disabled || node.getAttribute("aria-disabled") === "true") return false;
    var clone = node.cloneNode(true);
    clone.querySelectorAll("i, svg, img, .fa, [aria-hidden=\"true\"]").forEach(function (el) { el.remove(); });
    var navIconOnly = (node.classList.contains("bn-item") ||
      (node.classList.contains("nav-item") && document.body.classList.contains("sidebar-collapsed")));
    return (navIconOnly || !clone.textContent.trim()) &&
      !!(node.getAttribute("aria-label") || node.getAttribute("title"));
  }

  function closeIconPopover() {
    clearIconPopoverTimer();
    if (iconPopover) iconPopover.remove();
    iconPopover = null;
    iconPopoverTarget = null;
  }

  function positionIconPopover(control, pop) {
    var rect = control.getBoundingClientRect();
    var gap = 10;
    var width = pop.offsetWidth;
    var height = pop.offsetHeight;
    var placements = [
      { name: "top", space: rect.top }, { name: "bottom", space: window.innerHeight - rect.bottom },
      { name: "right", space: window.innerWidth - rect.right }, { name: "left", space: rect.left }
    ];
    var placement = placements[0];
    for (var i = 0; i < placements.length; i++) {
      var needed = (placements[i].name === "top" || placements[i].name === "bottom") ? height + gap : width + gap;
      if (placements[i].space >= needed) { placement = placements[i]; break; }
      if (placements[i].space > placement.space) placement = placements[i];
    }
    var left = rect.left + (rect.width - width) / 2;
    var top = rect.top - height - gap;
    if (placement.name === "bottom") top = rect.bottom + gap;
    if (placement.name === "left") { left = rect.left - width - gap; top = rect.top + (rect.height - height) / 2; }
    if (placement.name === "right") { left = rect.right + gap; top = rect.top + (rect.height - height) / 2; }
    left = Math.max(8, Math.min(left, window.innerWidth - width - 8));
    top = Math.max(8, Math.min(top, window.innerHeight - height - 8));
    pop.dataset.placement = placement.name;
    pop.style.left = left + "px";
    pop.style.top = top + "px";
  }

  function showIconPopover(control, transient) {
    if (!iconOnlyControl(control)) return;
    var label = control.getAttribute("aria-label") || control.getAttribute("title");
    if (!label || !label.trim()) return;
    if (iconPopoverTarget !== control || !iconPopover) {
      closeIconPopover();
      var pop = document.createElement("div");
      pop.className = "icon-popover";
      pop.setAttribute("role", "tooltip");
      pop.dataset.state = "hidden";
      pop.textContent = label.trim();
      document.body.appendChild(pop);
      iconPopover = pop;
      iconPopoverTarget = control;
      positionIconPopover(control, pop);
      requestAnimationFrame(function () {
        if (iconPopover === pop) pop.dataset.state = "visible";
      });
    } else {
      positionIconPopover(control, iconPopover);
    }
    if (transient) {
      clearIconPopoverTimer();
      iconPopoverTimer = setTimeout(closeIconPopover, 2000);
    }
  }

  function initIconPopovers() {
    document.addEventListener("pointerover", function (e) {
      var control = e.target.closest && e.target.closest("button, a");
      if (control && (!e.relatedTarget || !control.contains(e.relatedTarget))) showIconPopover(control);
    });
    document.addEventListener("pointerout", function (e) {
      var control = e.target.closest && e.target.closest("button, a");
      if (control && iconPopoverTarget === control && (!e.relatedTarget || !control.contains(e.relatedTarget)) && document.activeElement !== control) closeIconPopover();
    });
    document.addEventListener("focusin", function (e) { showIconPopover(e.target.closest && e.target.closest("button, a")); });
    document.addEventListener("focusout", function (e) {
      var control = e.target.closest && e.target.closest("button, a");
      if (control && iconPopoverTarget === control && (!e.relatedTarget || !control.contains(e.relatedTarget))) closeIconPopover();
    });
    document.addEventListener("click", function (e) {
      var control = e.target.closest && e.target.closest("button, a");
      if (control && iconOnlyControl(control)) { showIconPopover(control, true); return; }
      if (!e.target.closest || !e.target.closest(".icon-popover")) closeIconPopover();
    });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeIconPopover(); });
    window.addEventListener("resize", closeIconPopover);
    window.addEventListener("scroll", closeIconPopover, true);
  }

  function init() {
    initIconPopovers();
    var theme = read(THEME_KEY, DEFAULT_THEME);
    var locale = read(LOCALE_KEY, DEFAULT_LOCALE);
    var sidebar = read(SIDEBAR_KEY, DEFAULT_SIDEBAR);
    var device = read(DEVICE_KEY, DEFAULT_DEVICE);

    applyTheme(theme);
    applySidebar(sidebar);
    applyDevice(device);
    // Same entry point as the picker: renders now, and if the <head> preloader
    // could not run (blocked storage, CSP) it fetches the dictionary and
    // re-renders when it lands. Normally the file is already there -> no-op.
    switchLocale(locale);
    populateLocaleOptions();
    updateLangUI(locale);
    initRowMenuGlobal();

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

    // --- Language dropdown switch ---
    var langBtn = document.getElementById("langMenuBtn");
    if (langBtn) {
      langBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        toggleLangMenu();
      });
    }
    var langMenu = document.getElementById("langMenu");
    if (langMenu) {
      langMenu.addEventListener("click", function (e) {
        var item = e.target.closest("[data-lang]");
        if (!item) return;
        var next = item.getAttribute("data-lang");
        switchLocale(next);
        write(LOCALE_KEY, next);
        updateLangUI(next);
        closeLangMenu();
        // Keep the Log Window toggle's aria/title label in sync with the locale.
        applyLogVisible(isLogVisible());
      });
    }
    document.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest(".lang-switch")) return;
      closeLangMenu();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeLangMenu();
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
      // B5.5: stop the usage auto-refresh whenever we navigate (the usage
      // module restarts it via onShow when its view is entered). Guarded so
      // the shell works even if usage.js is absent.
      if (view !== "usage" && window.aigate && window.aigate.usage &&
          typeof window.aigate.usage.onHide === "function") {
        window.aigate.usage.onHide();
      }
      showView(view);
      setActiveNav(item);
      if (view === "settings") loadSettings();
      else if (view === "providers") loadProviders();
      else if (view === "combos") {
        if (window.aigate && window.aigate.combos) window.aigate.combos.onShow();
      } else if (view === "proxies") {
        if (window.aigate && window.aigate.proxies) window.aigate.proxies.onShow();
      } else if (view === "endpoints") {
        if (window.aigate && window.aigate.endpoints) window.aigate.endpoints.onShow();
      } else if (view === "usage") {
        // B5.5: load quota + summary + recent and start the auto-refresh.
        if (window.aigate && window.aigate.usage) window.aigate.usage.onShow();
      } else if (view === "analytics") {
        // B5.6: load the analytics dashboard + request-log viewer (manual refresh
        // only — no auto-poll timers to stop on onHide).
        if (window.aigate && window.aigate.analytics) {
          window.aigate.analytics.onShow();
        }
      } else if (view === "terminal") {
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
    }

    document.querySelectorAll(".nav-item, .bn-item").forEach(function (item) {
      // Only in-app views are driven by data-view. Items without it are plain
      // links (the sidebar Repository link to GitHub) — registering the handler
      // there would preventDefault() and kill the navigation.
      if (!item.hasAttribute("data-view")) return;
      item.addEventListener("click", function (e) {
        e.preventDefault();
        handleNav(item);
      });
    });

    // --- Settings form ---
    var form = document.getElementById("settingsForm");
    if (form) form.addEventListener("submit", saveSettings);

    // --- Backup & Restore (B5.7) ---
    // Export: intercept the anchor so we surface the "Export started" status and
    // drive the download through exportSettings() (single, controlled trigger).
    var exportBtn = document.getElementById("exportBtn");
    if (exportBtn) {
      exportBtn.addEventListener("click", function (e) {
        e.preventDefault();
        exportSettings();
      });
    }
    // Import: read the chosen file, then run the confirm + POST flow.
    var importBtn = document.getElementById("importBtn");
    if (importBtn) {
      importBtn.addEventListener("click", function () {
        var input = document.getElementById("importFile");
        var file = input && input.files && input.files[0];
        if (!file) {
          setBackupMsg(getStr("settings.import.no_file"), "error");
          return;
        }
        importSettingsFromFile(file);
      });
    }

    // --- Providers (B2.2) ---
    var provAdd = document.getElementById("provAddBtn");
    if (provAdd) provAdd.addEventListener("click", openAddModal);
    var provForm = document.getElementById("provForm");
    if (provForm) provForm.addEventListener("submit", saveProvider);
    var provTest = document.getElementById("provTestBtn");
    if (provTest) provTest.addEventListener("click", testProviderConnection);
    var provCancel = document.getElementById("provCancel");
    if (provCancel) provCancel.addEventListener("click", hideModal);
    var provAddHdr = document.getElementById("provAddHeaderBtn");
    if (provAddHdr) provAddHdr.addEventListener("click", function () { addHeaderRow("", ""); });
    // The Discover button is gone (stage-2): discovery runs silently from
    // openEditModal/openDetail. What is wired here instead: the strategy
    // select drives the sticky-limit row, and the modal tablist behaves.
    var provStrategy = document.getElementById("provStrategy");
    if (provStrategy) provStrategy.addEventListener("change", syncStickyLimitRow);
    wireProvTabs();
    var provEdit = document.getElementById("provEditBtn");
    if (provEdit) provEdit.addEventListener("click", function () { openEditModal(selectedProviderId); });
    var provDel = document.getElementById("provDeleteBtn");
    if (provDel) provDel.addEventListener("click", function () { deleteProvider(selectedProviderId); });
    var accAdd = document.getElementById("accAddBtn");
    if (accAdd) accAdd.addEventListener("click", function () { addAccount(); });
    var accOAuth = document.getElementById("provConnectOAuthBtn");
    if (accOAuth) accOAuth.addEventListener("click", function () { connectOAuth(selectedProviderId); });
    var accAuthType = document.getElementById("accAuthType");
    if (accAuthType) accAuthType.addEventListener("change", function () {
      var row = document.getElementById("accApiKeyRow");
      if (row) row.hidden = accAuthType.value !== "api_key";
    });
    var provModal = document.getElementById("provModal");
    if (provModal) provModal.addEventListener("click", function (e) {
      if (e.target === provModal) hideModal(); // click backdrop closes
    });

    // --- Log Window (B3.1) — GLOBAL, shown on every view, toggled from topbar ---
    var logRefreshBtn = document.getElementById("logRefreshBtn");
    if (logRefreshBtn) logRefreshBtn.addEventListener("click", function () {
      loadLogs();
    });
    var logSeverity = document.getElementById("logSeverity");
    if (logSeverity) logSeverity.addEventListener("change", function () {
      loadLogs();
    });
    var logWindowToggle = document.getElementById("logWindowToggle");
    if (logWindowToggle) logWindowToggle.addEventListener("click", toggleLogVisible);

    // --- T2 log cleanup: clear (confirm-first), show-resolved toggle, resolve-all ---
    var logClearBtn = document.getElementById("logClearBtn");
    if (logClearBtn) logClearBtn.addEventListener("click", clearLogs);
    var logClearConfirmBtn = document.getElementById("logClearConfirmBtn");
    if (logClearConfirmBtn) logClearConfirmBtn.addEventListener("click", confirmClearLogs);
    var logClearCancelBtn = document.getElementById("logClearCancelBtn");
    if (logClearCancelBtn) logClearCancelBtn.addEventListener("click", cancelClearLogs);
    var logClearModal = document.getElementById("logClearModal");
    if (logClearModal) logClearModal.addEventListener("click", function (e) {
      if (e.target === logClearModal) cancelClearLogs(); // click backdrop closes
    });
    var logShowResolvedBtn = document.getElementById("logShowResolvedBtn");
    if (logShowResolvedBtn) {
      logShowResolvedBtn.addEventListener("click", function () {
        toggleShowResolved();
        loadLogs();
      });
    }
    var logResolveAllBtn = document.getElementById("logResolveAllBtn");
    if (logResolveAllBtn) logResolveAllBtn.addEventListener("click", resolveAllLogs);
    // Rows re-render often -> delegate resolve clicks on the tbody.
    var logTableBody = document.getElementById("logTableBody");
    if (logTableBody) logTableBody.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".log-resolve-btn") : null;
      if (btn && btn.getAttribute("data-id")) resolveLog(btn.getAttribute("data-id"));
    });

    // --- Global Log Window: restore show/hide + start auto-refresh once ---
    var logVisible = read(LOG_VISIBLE_KEY, "1") !== "0";
    applyLogVisible(logVisible);
    applyShowResolved();
    observeLogWindow();
    // Start auto-refresh globally (runs across all view switches). Guarded so
    // headless test envs without fetch() don't error on import.
    if (typeof fetch === "function") {
      loadLogs();
      startLogAutoRefresh();
    }

    // Start on the welcome view.
    showView("welcome");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
