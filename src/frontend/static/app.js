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

  // Rows with an expanded <details class="log-stack"> — preserved across the 3s
  // re-render so an open stacktrace does not auto-collapse (Task 1). Declared up
  // here so the test hook on window.aigate (assigned before this block executes)
  // shares the same Set instance.
  var openStackIds = new Set();

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
    // Keep the bottom-nav active highlight in sync with the current view.
    var active = document.querySelector(".view.is-active");
    var view = active ? active.getAttribute("data-view") : null;
    syncBottomNav(view);
  }

  // Which nav item lights up for a given view. Normally 1:1 — except the
  // provider-detail page (stage-3), which has NO entry of its own and belongs
  // to "providers". Kept in one place so setActiveNav and the device-simulation
  // re-sync can never disagree about it.
  function navViewFor(view) {
    return view === "provider-detail" ? "providers" : view;
  }

  function syncBottomNav(view) {
    var target = navViewFor(view);
    document.querySelectorAll(".bn-item").forEach(function (n) {
      n.classList.toggle("active", !!target && n.getAttribute("data-view") === target);
    });
  }

  /* ---- Device-simulation modal (Opsi A — moved out of the Settings form) ----
     A small device-sim control (sidebar-footer on desktop, bottom-nav on mobile)
     opens an accessible dialog that previews THIS app in an iframe at the chosen
     device size. The preview is scoped to the iframe only — selecting a mode
     applies the device INSIDE the frame (contentWindow.aigate.applyDevice), so
     the live page (the outer document) is never touched. The focus-trap / ESC /
     click-outside / restore-focus behaviour lives here, scoped to this dialog. */
  var DEVICE_SIZES = { phone: [375, 667], tablet: [768, 1024], desktop: [1280, 800] };

  var deviceModal = null;
  var deviceFrame = null;
  var deviceLastTrigger = null;
  var deviceKeyHandler = null;
  // Session-local preview mode. NOT localStorage, NOT the outer body — the modal
  // never reads or writes the live page's device view (see deviceSelectMode).
  var devicePreviewMode = null;

  function deviceFocusables() {
    if (!deviceModal) return [];
    // Everything inside this dialog is always visible (no conditionally-hidden
    // controls), so a plain focusable selector is enough — and it stays correct
    // under jsdom, where offsetParent is always null (no layout engine).
    return Array.prototype.slice.call(
      deviceModal.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    );
  }

  /* Size the device box to the chosen device's REAL pixels. The box is clamped
     to the viewer in CSS (max-width:92vw / max-height:80vh) and scrolls
     internally — the content is NEVER scaled down. --dev-w / --dev-h are set per
     mode on .device-modal and cascade into the box + iframe, so the frame keeps
     its exact device px and the iframe's own media queries + body[data-device]
     rules fire INSIDE the frame. Returns the dims so callers (and tests) can read
     what was applied. */
  function deviceRenderPreview(mode) {
    if (!deviceModal) return null;
    var dims = DEVICE_SIZES[mode] || DEVICE_SIZES.desktop;
    deviceModal.style.setProperty("--dev-w", dims[0] + "px");
    deviceModal.style.setProperty("--dev-h", dims[1] + "px");
    return dims;
  }

  /* Apply the device mode INSIDE the iframe only. The frame loads the app
     itself, so its contentWindow exposes aigate.applyDevice; calling it there
     writes body[data-device] on the FRAME's document, never the outer one. */
  function deviceApplyInFrame(mode) {
    if (!deviceFrame || !deviceFrame.contentWindow) return;
    try {
      var w = deviceFrame.contentWindow;
      if (w.aigate && typeof w.aigate.applyDevice === "function") {
        w.aigate.applyDevice(mode);
      }
    } catch (e) {
      /* not loaded yet / inaccessible — nothing to apply */
    }
  }

  function deviceSetActiveMode(mode) {
    if (!deviceModal) return;
    Array.prototype.forEach.call(
      deviceModal.querySelectorAll("[data-device-mode]"),
      function (btn) {
        var on = btn.getAttribute("data-device-mode") === mode;
        btn.classList.toggle("is-active", on);
        btn.setAttribute("aria-pressed", on ? "true" : "false");
      }
    );
  }

  /* Set + persist the device-view preference (B4.2, client-only) on the LIVE
     page. Entry point for the boot re-apply and the test-facing
     window.aigate.setDevice hook; returns the canonical token. NOTE: the
     device-sim modal no longer calls this — its preview is scoped to the iframe
     (deviceApplyInFrame), so it never mutates the outer page or localStorage. */
  function setDevicePreference(mode) {
    var norm = deviceAttr(mode);
    applyDevice(norm);
    write(DEVICE_KEY, norm);
    return norm;
  }

  /* Preview-only mode switch. Marks the active button, sizes the device box, and
     applies the device INSIDE the iframe. It never calls setDevicePreference, so
     the outer page is never mutated and localStorage is never written here. */
  function deviceSelectMode(mode) {
    var norm = deviceAttr(mode);
    devicePreviewMode = norm;
    deviceSetActiveMode(norm);
    deviceRenderPreview(norm);
    deviceApplyInFrame(norm);
  }

  function openDeviceModal(trigger) {
    if (!deviceModal) return;
    deviceLastTrigger = trigger || null;
    deviceModal.hidden = false;
    // Default to the last previewed mode this session — NOT the outer page's
    // body[data-device] and NOT localStorage (the modal never reads the live view).
    var cur = devicePreviewMode || DEFAULT_DEVICE;
    deviceSetActiveMode(cur);
    deviceRenderPreview(cur);
    // Load the preview once (same origin -> the app itself). Skip in non-DOM
    // test envs where the frame has no real layout.
    if (deviceFrame && !deviceFrame.getAttribute("src")) {
      deviceFrame.setAttribute("src", location.pathname || "/");
    }
    var f = deviceFocusables();
    if (f.length) f[0].focus();
    deviceKeyHandler = function (e) {
      if (e.key === "Escape") {
        e.preventDefault();
        closeDeviceModal();
        return;
      }
      if (e.key !== "Tab") return;
      var list = deviceFocusables();
      if (!list.length) return;
      var first = list[0], last = list[list.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first || !deviceModal.contains(document.activeElement)) {
          e.preventDefault(); last.focus();
        }
      } else {
        if (document.activeElement === last || !deviceModal.contains(document.activeElement)) {
          e.preventDefault(); first.focus();
        }
      }
    };
    document.addEventListener("keydown", deviceKeyHandler, true);
  }

  function closeDeviceModal() {
    if (!deviceModal || deviceModal.hidden) return;
    deviceModal.hidden = true;
    if (deviceKeyHandler) {
      document.removeEventListener("keydown", deviceKeyHandler, true);
      deviceKeyHandler = null;
    }
    if (deviceLastTrigger && typeof deviceLastTrigger.focus === "function") {
      deviceLastTrigger.focus(); // restore focus to the trigger
    }
    deviceLastTrigger = null;
  }

  function setupDeviceModal() {
    deviceModal = document.getElementById("deviceModal");
    if (!deviceModal) return;
    deviceFrame = document.getElementById("deviceFrame");
    // Triggers (desktop sidebar-footer + mobile bottom-nav share the attribute).
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-device-trigger]"),
      function (t) {
        t.addEventListener("click", function () { openDeviceModal(t); });
      }
    );
    // Mode buttons (delegated — they exist at load, but keep it cheap).
    deviceModal.addEventListener("click", function (e) {
      if (e.target === deviceModal) { closeDeviceModal(); return; } // click backdrop
      var btn = e.target.closest ? e.target.closest("[data-device-mode]") : null;
      if (btn) { deviceSelectMode(btn.getAttribute("data-device-mode")); return; }
      if (e.target.closest && e.target.closest("#deviceModalClose")) closeDeviceModal();
    });
    // Once the iframe loads the app, apply the current preview mode INSIDE it.
    if (deviceFrame) {
      deviceFrame.addEventListener("load", function () {
        deviceApplyInFrame(devicePreviewMode || DEFAULT_DEVICE);
      });
    }
    // Refit the open modal when the viewport changes / rotates. CSS clamps (92vw /
    // 80vh) already size the box; re-rendering keeps the per-mode vars current.
    window.addEventListener("resize", function () {
      if (deviceModal && !deviceModal.hidden) {
        deviceRenderPreview(devicePreviewMode || DEFAULT_DEVICE);
      }
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
    // Mirror the active state onto the mobile bottom-nav (same data-view,
    // mapped through navViewFor so a sub-page like provider-detail still
    // highlights its parent).
    var view = item ? navViewFor(item.getAttribute("data-view")) : null;
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
        // Developer Mode gate: reflects the persisted value on body and starts/
        // stops the log poll accordingly (Task 3). Single source of truth.
        applyDevMode(String(data.dev_mode) === "true");
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
        // Live Developer Mode gate: toggling the switch shows/hides the dev-only
        // surfaces + starts/stops the log poll without a reload (Task 3).
        applyDevMode(!!(f.dev_mode && f.dev_mode.checked));
        setMsg(getStr("settings.saved"), "ok");
      })
      .catch(function (err) {
        setMsg(getStr("settings.error") + " (" + err.message + ")", "error");
      });
  }

  /* Developer Mode switch: apply + persist the moment it toggles, so the gated
     surfaces appear/disappear without a "Save" click (real-Chromium UX fix).
     saveSettings() already PUTs the whole settings object (dev_mode included)
     and calls applyDevMode() on success, so this reuses that single path —
     no duplicated persist logic. It is idempotent with the Save button: the
     submit handler still calls saveSettings on an explicit click, and the
     Port/theme/locale fields are NOT wired here (no save-per-keystroke).
     `change` fires only when the checkbox value settles, not per keypress. */
  function wireDevModeToggle() {
    var dm = document.getElementById("setDevMode");
    if (dm) dm.addEventListener("change", function () { saveSettings(); });
  }

  /* Test hook: lets vitest assert the PUT body stringifies values. */
  window.aigate = window.aigate || {};
  window.aigate.buildSettingsBody = buildSettingsBody;
  // Device-view simulation (Opsi A): exposed so tests drive the same entry point
  // the modal's mode buttons use; the shipped control is the modal trigger.
  window.aigate.setDevice = setDevicePreference;
  window.aigate.applyDevice = applyDevice;
  // Wiring the device-sim modal is exposed like wireProviderUi so a test that
  // re-mounts the shipped body can bind the triggers + focus trap in isolation.
  window.aigate.setupDeviceModal = setupDeviceModal;

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
  window.aigate.loadProviders = loadProviders;
  window.aigate.buildHeadersDict = buildHeadersDict;
  window.aigate.headersToRows = headersToRows;
  window.aigate.saveProvider = saveProvider;
  window.aigate.openAddModal = openAddModal;
  window.aigate.openEditModal = openEditModal;
  window.aigate.discoverModels = discoverModels;
  window.aigate.populateModelCombobox = populateModelCombobox;
  // Provider-detail page (stage-3, Opsi A): only what a test or another module
  // actually calls is exported — the rest stays private to this IIFE.
  window.aigate.openDetail = openDetail;
  window.aigate.backToProviders = backToProviders;
  window.aigate.saveStrategy = saveStrategy;

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
  /* Task 1: expanded-stacktrace ids are exposed so a test can seed/presence-
     check the set that survives the 3s re-render. Task 3: applyDevMode is the
     single gate for the dev-only surfaces + log poll. */
  window.aigate.openStackIds = openStackIds;
  window.aigate.applyDevMode = applyDevMode;
  // Re-attach the tbody delegates (init ran on an empty body in jsdom tests).
  window.aigate.wireLogTable = wireLogTable;
  // Re-attach the instant Developer Mode toggle (same jsdom re-wiring need).
  window.aigate.wireDevModeToggle = wireDevModeToggle;
  // DEV-RESTART: expose the handler + re-wiring so the vitest sim can drive the
  // same entry point the shipped button uses (init runs on an empty jsdom body).
  window.aigate.devRestart = devRestart;
  window.aigate.wireDevRestart = wireDevRestart;
  window.aigate.pollHealthThenReload = pollHealthThenReload;

  /* ---- DOM helpers ---- */
  function provEl(id) { return document.getElementById(id); }

  /* ---- Shared status-line writer (DRY: every message slot behaves the same) ---- */
  function setMsgIn(id, text, kind, base) {
    var m = provEl(id);
    if (!m) return;
    m.textContent = text || "";
    m.className = (base || "settings-msg") + (kind ? " settings-msg-" + kind : "");
  }

  function setProvMsg(text, kind) { setMsgIn("provMsg", text, kind); }
  function setProvModalMsg(text, kind) { setMsgIn("provModalMsg", text, kind); }

  // Discovery speaks through ONE small text line, shown in BOTH places it is
  // relevant: under the model combobox in the profile modal and inside Kartu A
  // of the detail page. (stage-3: the old #provModelMsg + model table are gone;
  // a status line never needs a table and never blocks the form.)
  function setModelMsg(text, kind) {
    setMsgIn("provModalModelStatus", text, kind, "pd-status");
    setMsgIn("pdModelStatus", text, kind, "pd-status");
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
      // The name is plain text (stage-4): the detail page (Opsi A) is reached
      // through the kebab's top item, like every other row action. The cell
      // matches the plain name cells of the combos/pools/endpoints tables.
      var modelsHint = escapeHtml(getStr("providers.models_hint"));
      return '<tr class="prov-row" data-id="' + escapeHtml(row.id) + '">' +
        '<td class="prov-name">' + escapeHtml(row.name) + "</td>" +
        "<td>" + escapeHtml(row.type) + "</td>" +
        "<td>" + escapeHtml(row.base_url) + "</td>" +
        "<td>" + badge + "</td>" +
        // The count is a machine result (silent /discover), so say where it
        // comes from instead of letting the number look authoritative.
        '<td class="prov-models" title="' + modelsHint + '" aria-label="' + modelsHint + '">' +
          escapeHtml(row.modelCount) + "</td>" +
        rowMenuCellHtml() +
      "</tr>";
    }).join("");

    // Consistent with the other tables: actions live in the kebab menu only.
    // The detail page is one of them ("Kelola akun" = providers.accounts_menu,
    // stage-4), so the name cell carries no click behavior at all.
    wireRowMenu(body, function (tr) {
      var id = tr ? tr.getAttribute("data-id") : null;
      return [
        { action: "accounts", label: getStr("providers.accounts_menu"), icon: "fa-users",
          onClick: function () { openDetail(id); } },
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

  /* ---- Rotation strategy (Kartu B of the provider-detail page) ----
     sticky_round_robin_limit is only meaningful while strategy=round-robin: for
     fill-first the row is hidden AND the input disabled, so saveStrategy can skip
     the field instead of pretending a dead value was sent. The strategy select
     lives ONLY here — the profile modal no longer carries it, so the two
     surfaces cannot overwrite each other (stage-3, Opsi A). */
  function strategyIsRoundRobin() {
    var sel = provEl("pdStrategy");
    return !!sel && sel.value === "round-robin";
  }

  function syncStickyLimitRow() {
    var rr = strategyIsRoundRobin();
    var row = provEl("pdStickyRow");
    var inp = provEl("pdStickyLimit");
    if (row) row.hidden = !rr;
    if (inp) inp.disabled = !rr;
  }

  // Master<->sub switch linkage for the Token Saver block. The three sub
  // switches are only meaningful while the master is ON; master OFF disables
  // them (and saveProvider() then forces the three booleans false).
  var TS_SUB_IDS = ["provTsRtk", "provTsCaveman", "provTsPonytail"];

  function syncTokenSaverUI() {
    var master = provEl("provTokenSaver");
    var on = !!master && master.checked;
    TS_SUB_IDS.forEach(function (id) {
      var el = provEl(id);
      if (el) el.disabled = !on;
    });
  }

  function openAddModal() {
    selectedProviderId = null;
    var f = provEl("provForm");
    if (f) f.reset();
    provEl("provId").value = "";
    provEl("provModalTitle").textContent = getStr("providers.add");
    // Fresh provider: master + subs start OFF and disabled.
    var tsMaster = provEl("provTokenSaver");
    if (tsMaster) tsMaster.checked = false;
    syncTokenSaverUI();
    renderHeadersEditor([]);
    // Fresh provider: clear any stale discovered options + value from a prior
    // edit (free text still works with an empty option list).
    var c = provModelCtl();
    if (c) { c.setOptions([]); c.setValue(""); c.close(); }
    setModelMsg("", "");
    provEl("provModal").hidden = false;
  }

  // EDIT mode: the profile fields come from the DTO, then the modal opens. The
  // rotation strategy is deliberately NOT loaded here — it belongs to Kartu B
  // (renderStrategyCard), and the profile PUT must not carry it back.
  function openEditModal(id) {
    fetchJson(PROV_API + "/" + id).then(function (p) {
      selectedProviderId = id;
      provEl("provId").value = p.id != null ? p.id : "";
      provEl("provName").value = p.name != null ? p.name : "";
      provEl("provType").value = p.type || "openai-compatible";
      provEl("provBaseUrl").value = p.base_url != null ? p.base_url : "";
      // ADR-007: show api_key as plaintext (no redaction).
      provEl("provApiKey").value = p.api_key != null ? p.api_key : "";
      provEl("provEnabled").checked = !!p.enabled;
      // Token Saver (D6/ACC): master is ON if any sub is stored true; each sub
      // reads its own boolean. syncTokenSaverUI then enables/disables the subs.
      var tsMaster = provEl("provTokenSaver");
      if (tsMaster) {
        tsMaster.checked = !!(p.token_saver_rtk || p.token_saver_caveman || p.token_saver_ponytail);
      }
      var tsInputs = {
        provTsRtk: p.token_saver_rtk,
        provTsCaveman: p.token_saver_caveman,
        provTsPonytail: p.token_saver_ponytail
      };
      TS_SUB_IDS.forEach(function (id) {
        var el = provEl(id);
        if (el) el.checked = !!tsInputs[id];
      });
      syncTokenSaverUI();
      // Default model: seed the combobox with this provider's known models
      // (sorted) and set the stored value. A custom (undiscovered) value is
      // still shown because the input holds any string.
      var mc = provModelCtl();
      if (mc) { mc.setOptions(modelOptions(p.models)); mc.setValue(p.default_model); }
      else if (provEl("provModel")) provEl("provModel").value = p.default_model != null ? p.default_model : "";
      provEl("provModalTitle").textContent = getStr("providers.edit");
      renderHeadersEditor(headersToRows(p.custom_headers));
      setModelMsg("", "");
      provEl("provModal").hidden = false;
      // Background model refresh (stage-2 decision kept): the POST still runs
      // quietly; stage-3 adds ONE status line so the wait is not mute.
      discoverModels(id, { quiet: true });
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
    // Stage-3 (Opsi A): PROFILE fields only. fallback_strategy /
    // sticky_round_robin_limit deliberately are NOT sent — they belong to
    // Kartu B (saveStrategy), so saving the profile can never silently
    // overwrite the rotation the user just stored there.
    var body = {
      name: provEl("provName").value,
      type: provEl("provType").value,
      base_url: provEl("provBaseUrl").value,
      api_key: provEl("provApiKey").value,
      default_model: provModelValue(),
      enabled: provEl("provEnabled").checked,
      custom_headers: collectHeaders(),
      // Token Saver (D6/ACC): never send the removed string field. When the
      // master is OFF every sub is forced false; when ON each toggles freely.
      token_saver_rtk: !!provEl("provTokenSaver").checked && !!provEl("provTsRtk").checked,
      token_saver_caveman: !!provEl("provTokenSaver").checked && !!provEl("provTsCaveman").checked,
      token_saver_ponytail: !!provEl("provTokenSaver").checked && !!provEl("provTsPonytail").checked
    };
    setProvMsg("");
    var req = id
      ? fetchJson(PROV_API + "/" + id, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        })
      : fetchJson(PROV_API, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        });
    req.then(function (saved) {
      hideModal();
      loadProviders();
      // Editing from the detail page: refresh what the user is looking at, with
      // the id the SERVER answered (a POST has no id yet).
      var savedId = (saved && saved.id != null) ? saved.id : id;
      if (savedId != null && savedId !== "" && selectedProviderId === savedId &&
          isProviderDetailActive()) {
        loadProviderDetail(savedId);
      }
    }).catch(function (err) {
      setProvMsg(err.message, "error");
    });
  }

  /* ===== Provider-detail page (stage-3, Opsi A) =====
     One page owns everything about ONE provider: head (back / name / badge /
     Ubah / Hapus), Kartu A profile (read-only), Kartu B rotation strategy,
     Kartu C accounts, Kartu D usage (B5.5, moved from the old detail card).
     It has NO nav entry of its own: the "providers" item stays highlighted so
     the nav <-> view parity contract keeps holding. */

  // Is the detail page the one currently on screen?
  function isProviderDetailActive() {
    var v = document.querySelector('.view[data-view="provider-detail"]');
    return !!v && v.classList.contains("is-active");
  }

  // Load discovered models into the #provModel combobox panel (sorted by name).
  // Replaces the old populateModelDatalist(): a <datalist> never pops on
  // Android, so the searchable combobox renders its own <ul> instead.
  function populateModelCombobox(models) {
    var c = provModelCtl();
    if (c) c.setOptions(modelOptions(models));
  }

  /* skipDiscover: the legacy non-quiet discoverModels() opens the page itself
     and then runs its OWN visible discovery — no duplicate POST. */
  function openDetail(id, skipDiscover) {
    selectedProviderId = id;
    showView("provider-detail");
    // Same item as the list: the sidebar/bottom-nav keep pointing at "Penyedia".
    setActiveNav(document.querySelector('.nav-item[data-view="providers"]'));
    stopOAuthPoll();
    loadProviderDetail(id);
    if (!skipDiscover) discoverModels(id, { quiet: true });
  }

  // GET everything the page shows for ONE provider (profile + accounts + usage).
  function loadProviderDetail(id) {
    if (id == null) id = selectedProviderId;
    if (id == null) return Promise.resolve();
    setProvMsg("");
    return fetchJson(PROV_API + "/" + id).then(function (p) {
      renderProfileCard(p);
      renderStrategyCard(p);
      loadAccounts(id);
      // B5.5 usage (Kartu D) — usage.js owns the rendering, we only point it.
      if (window.aigate && window.aigate.usage &&
          typeof window.aigate.usage.loadProviderUsage === "function") {
        window.aigate.usage.loadProviderUsage(id);
      }
    }).catch(function (err) {
      // Nothing can be rendered without the provider: go back to the list and
      // put the reason where the user can actually see it (#provMsg is there).
      if (isProviderDetailActive()) {
        showView("providers");
        setActiveNav(document.querySelector('.nav-item[data-view="providers"]'));
      }
      setProvMsg(err.message, "error");
    });
  }

  // "← Kembali ke Penyedia": back to the list, and the list is re-read so the
  // model counts / badges are fresh after anything changed on the detail page.
  function backToProviders() {
    stopOAuthPoll();
    selectedProviderId = null;
    showView("providers");
    setActiveNav(document.querySelector('.nav-item[data-view="providers"]'));
    loadProviders();
  }

  // Kartu A — read-only profile. Values go in as text (never HTML), long ones
  // are cut by CSS and ride along in `title` so nothing is lost.
  function renderProfileCard(p) {
    p = p || {};
    var title = provEl("provDetailTitle");
    if (title) title.textContent = p.name != null ? p.name : "";
    var badge = provEl("provDetailBadge");
    if (badge) {
      badge.hidden = false;
      badge.textContent = getStr(p.enabled ? "providers.enabled" : "providers.disabled");
      badge.className = "pd-badge badge " + (p.enabled ? "badge-ok" : "badge-off");
    }
    setProfileText("pdType", p.type || "");
    setProfileText("pdBaseUrl", p.base_url || "");
    setProfileText("pdDefaultModel", p.default_model || "");
    // ADR-007 / J3: the key is plaintext on screen by design, never masked.
    setProfileText("pdApiKey", p.api_key || "");
    var headers = headersToRows(p.custom_headers);
    setProfileText("pdHeaders", headers.length
      ? headers.map(function (h) { return h.key + ": " + h.value; }).join("  ·  ")
      : getStr("provider_detail.none"));
    var models = Array.isArray(p.models) ? p.models : [];
    setModelCount(models.length);
  }

  // One <dd>: text only + a title carrying the full value (ellipsised by CSS).
  function setProfileText(id, value) {
    var el = provEl(id);
    if (!el) return;
    el.textContent = value;
    el.setAttribute("title", value);
  }

  // The known-model count in Kartu A (DTO count on load, discovery count when a
  // background /discover lands).
  function setModelCount(n) {
    var el = provEl("pdModels");
    if (!el) return;
    var text = String(n);
    el.textContent = text;
    el.setAttribute("title", text);
  }

  // Kartu B — strategy + sticky limit. Enum guard from the stage-1 contract:
  // anything unexpected shows the default instead of echoing a value the
  // backend would later reject with 400.
  function renderStrategyCard(p) {
    p = p || {};
    var sel = provEl("pdStrategy");
    if (sel) sel.value = p.fallback_strategy === "round-robin" ? "round-robin" : "fill-first";
    var lim = provEl("pdStickyLimit");
    if (lim) {
      var n = parseInt(p.sticky_round_robin_limit, 10);
      lim.value = isNaN(n) ? 3 : n;
    }
    syncStickyLimitRow();
    setStrategyMsg("", "");
  }

  function setStrategyMsg(text, kind) { setMsgIn("pdStrategyMsg", text, kind); }

  // PUT ONLY the two routing fields (stage-1 contract). A rejected strategy
  // (400 invalid_fallback_strategy) shows inline; nothing else is touched.
  function saveStrategy() {
    var id = selectedProviderId;
    if (id == null) {
      setStrategyMsg(getStr("provider_detail.save_blocked"), "error");
      return Promise.resolve();
    }
    var body = {
      fallback_strategy: strategyIsRoundRobin() ? "round-robin" : "fill-first"
    };
    if (strategyIsRoundRobin()) {
      var limEl = provEl("pdStickyLimit");
      var lim = limEl ? parseInt(limEl.value, 10) : NaN;
      body.sticky_round_robin_limit = isNaN(lim) ? 3 : Math.max(1, lim);
    }
    setStrategyMsg("");
    return fetchJson(PROV_API + "/" + id, {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body)
    }).then(function (saved) {
      if (saved && saved.id != null) renderStrategyCard(saved);
      else syncStickyLimitRow();
      setStrategyMsg(getStr("provider_detail.strategy_saved"), "ok");
    }).catch(function (err) {
      // The 400 (invalid_fallback_strategy) belongs to THIS card, not the list.
      setStrategyMsg(err.message, "error");
    });
  }

  /* ---- Model discovery: silent POST, but not mute (stage-3, gap no.5) ----
     discoverSeq: if the user moved on to another provider while a response was
     in flight, the stale answer must never overwrite the current one — and it
     must never rewrite the status line either. */
  var discoverSeq = 0;

  function discoverModels(id, opts) {
    opts = opts || {};
    id = id || selectedProviderId;
    if (!id) return;
    var quiet = !!opts.quiet;
    var seq = ++discoverSeq;
    var mc = provModelCtl();
    // The line is shown on BOTH paths: a silent background POST may be quiet
    // about blocking, it must not be mute about what it is doing (stage-3).
    setModelMsg(getStr("providers.discovering"), "");
    if (!quiet) {
      // Legacy visible path (window.aigate.discoverModels — kept for tests and
      // any internal caller): opens the page and locks the field while loading.
      openDetail(id, true);
      if (mc) mc.setLoading(true); // disable field + "Loading models…" row
    }
    fetchJson(PROV_API + "/" + id + "/discover", {
      method: "POST", headers: { "Content-Type": "application/json" }
    }).then(function (res) {
      if (seq !== discoverSeq) return; // a newer discovery superseded this one
      if (!quiet && mc) mc.setLoading(false);
      // Contract: {"ok":true,"models":[...]} OR {"ok":false,"error":"<msg>"}
      if (res && res.ok === false) {
        reportDiscoveryFailure(res.error || getStr("providers.error"), quiet);
        return;
      }
      var models = (res && res.models) ? res.models : [];
      populateModelCombobox(models);
      setModelMsg(getStr("providers.discovered") + " (" + models.length + ")", "ok");
      // Kartu A shows the same number the list is about to show, so the page
      // never displays a count older than the discovery that just landed.
      setModelCount(models.length);
      loadProviders(); // refresh model counts in the list
    }).catch(function (err) {
      if (seq !== discoverSeq) return;
      if (!quiet && mc) mc.setLoading(false);
      reportDiscoveryFailure(err.message, quiet);
    });
  }

  // One text line + console.warn. A dead model list NEVER blocks a form: the
  // model combobox stays free-text (R12: the reason goes to the console).
  function reportDiscoveryFailure(message, quiet) {
    setModelMsg(getStr("providers.models_failed"), "error");
    if (typeof console !== "undefined" && console.warn) {
      console.warn("aigate: model discovery failed" + (quiet ? " (silent)" : "") + ":", message);
    }
  }

  function deleteProvider(id) {
    if (!window.confirm(getStr("providers.confirm_delete"))) return;
    fetchJson(PROV_API + "/" + id, { method: "DELETE" }).then(function () {
      // Deleting the provider whose detail page is open: fall back to the list.
      if (selectedProviderId === id && isProviderDetailActive()) {
        selectedProviderId = null;
        showView("providers");
        setActiveNav(document.querySelector('.nav-item[data-view="providers"]'));
      }
      loadProviders();
    }).catch(function (err) {
      setProvMsg(err.message, "error");
    });
  }

  /* ===== Provider Accounts (B5.1): multi-account per provider + OAuth =====
     stage-3 (Opsi A): the accounts of ONE provider are rendered as a vertical
     list of CARDS on the provider-detail page (Kartu C) — the old 6-column
     table is gone, so nothing has to scroll sideways on a phone. Creating an
     account goes through its own small modal (#accModal). */
  var ACC_API = "/api/accounts";
  var oauthPollTimer = null;
  var OAUTH_POLL_MS = 2000;
  var OAUTH_POLL_MAX = 15;
  // The list exactly as the server last returned it (already sorted
  // priority asc, id asc) — the ▲▼ buttons operate on THIS order.
  var accountRows = [];

  function setAccountsMsg(text, kind) { setMsgIn("accountsMsg", text, kind); }
  function setAccModalMsg(text, kind) { setMsgIn("accModalMsg", text, kind); }

  // One account = one card. Position is 1..n (a human rank), never the raw DB
  // integer; the credential is PLAINTEXT (J3 / ADR-007: this product stores and
  // shows its own local secrets on purpose) and is cut by CSS with the full
  // value kept in `title`.
  function accountCardHtml(a, i, total) {
    var position = i + 1;
    var posTitle = escapeHtml(getStr("provider_detail.position") + " " + position + " / " + total);
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
      // ADR-007: show api_key plaintext, no masking. An account without a key
      // says so instead of leaving a blank that looks like data.
      var key = a.api_key != null ? String(a.api_key) : "";
      credential = '<span class="acc-key" title="' + escapeHtml(key) + '">' +
        escapeHtml(key || getStr("provider_detail.none")) + "</span>";
    }
    // Last used: machine-owned ISO timestamp, or the i18n "never" marker —
    // never a blank cell pretending to be data.
    var lastUsed = escapeHtml(getStr("provider_detail.last_used")) + ": " +
      (a.last_used_at ? escapeHtml(a.last_used_at)
        : escapeHtml(getStr("provider_detail.never_used")));
    // Boundary buttons: aria-disabled + a title that says WHY (never a dead
    // tap that pretends nothing happened).
    var upOff = i === 0;
    var downOff = i === total - 1;
    var upAttrs = 'aria-label="' + escapeHtml(getStr("provider_detail.move_up")) + '"' +
      (upOff ? ' aria-disabled="true" title="' + escapeHtml(getStr("provider_detail.already_first")) + '"' : "");
    var downAttrs = 'aria-label="' + escapeHtml(getStr("provider_detail.move_down")) + '"' +
      (downOff ? ' aria-disabled="true" title="' + escapeHtml(getStr("provider_detail.already_last")) + '"' : "");
    return '<article class="acc-card" data-id="' + escapeHtml(a.id) + '" data-index="' + i + '">' +
      '<div class="acc-card-top">' +
        '<span class="acc-pos" title="' + posTitle + '">' + position + "</span>" +
        '<span class="acc-label">' + escapeHtml(a.label) + "</span>" +
        '<span class="acc-type">' + escapeHtml(a.auth_type) + "</span>" +
      "</div>" +
      '<div class="acc-cred"><span class="acc-cred-label">' +
        escapeHtml(getStr("accounts.credential")) + ":</span> " + credential + "</div>" +
      '<div class="acc-card-foot">' +
        '<span class="acc-move">' +
          '<button type="button" class="icon-btn-small acc-up"' + upAttrs + ">" +
            '<i class="fa fa-arrow-up" aria-hidden="true"></i></button>' +
          '<button type="button" class="icon-btn-small acc-down"' + downAttrs + ">" +
            '<i class="fa fa-arrow-down" aria-hidden="true"></i></button>' +
        "</span>" +
        '<span class="acc-last">' + lastUsed + "</span>" +
        '<button type="button" class="btn acc-edit" ' +
          'aria-label="' + escapeHtml(getStr("provider_detail.edit_account")) + '" ' +
          'title="' + escapeHtml(getStr("provider_detail.edit_account")) + '">' +
          '<i class="fa fa-pen" aria-hidden="true"></i> ' +
          escapeHtml(getStr("provider_detail.edit_account")) + "</button>" +
        '<button type="button" class="btn btn-danger acc-del">' +
          '<i class="fa fa-trash" aria-hidden="true"></i> ' +
          escapeHtml(getStr("accounts.delete")) + "</button>" +
      "</div>" +
    "</article>";
  }

  // Render a GET /api/accounts payload into the account card list (Kartu C).
  // The stage-1 contract order is trusted as-is: the server sorts
  // priority asc, id asc, so card position == routing position.
  function renderAccounts(list) {
    var box = provEl("accList");
    if (!box) return;
    list = list || [];
    accountRows = list.slice();
    if (!list.length) {
      box.innerHTML = '<p class="acc-empty" data-i18n="provider_detail.no_accounts">' +
        escapeHtml(getStr("provider_detail.no_accounts")) + "</p>";
      return;
    }
    var total = list.length;
    box.innerHTML = list.map(function (a, i) {
      return accountCardHtml(a, i, total);
    }).join("");

    // One delegated listener survives innerHTML re-renders (the guard mirrors
    // the provider tbody wiring: a test that rebuilds the node re-attaches).
    if (box.getAttribute("data-acc-wired") !== "1") {
      box.setAttribute("data-acc-wired", "1");
      box.addEventListener("click", function (e) {
        var card = e.target.closest ? e.target.closest(".acc-card") : null;
        if (!card) return;
        var idx = parseInt(card.getAttribute("data-index"), 10);
        if (isNaN(idx)) return;
        if (e.target.closest(".acc-del")) {
          deleteAccount(card.getAttribute("data-id"));
          return;
        }
        if (e.target.closest(".acc-edit")) {
          openAccountEditModal(card.getAttribute("data-id"));
          return;
        }
        var up = e.target.closest(".acc-up");
        var down = e.target.closest(".acc-down");
        // aria-disabled buttons explain themselves and never hit the network.
        if (up && up.getAttribute("aria-disabled") !== "true") moveAccount(idx, -1);
        else if (down && down.getAttribute("aria-disabled") !== "true") moveAccount(idx, 1);
      });
    }
  }

  /* ---- Priority = swap + renumber (stage-3, replaces the bare number input) ----
     ▲/▼ exchange position i with i+1, the list is then normalised to
     priority = 0..n-1, and ONLY the rows whose stored value actually changes are
     PUT. With the all-zero default that is 2 requests, not n. */
  function moveAccount(index, dir) {
    var target = index + dir;
    if (index < 0 || target < 0 || target >= accountRows.length) {
      return Promise.resolve();
    }
    var order = accountRows.slice();
    var swap = order[index];
    order[index] = order[target];
    order[target] = swap;
    var changed = [];
    order.forEach(function (a, i) {
      var cur = parseInt(a.priority, 10);
      if (isNaN(cur)) cur = 0;
      if (cur !== i) changed.push({ id: a.id, priority: i });
    });
    if (!changed.length) return loadAccounts(selectedProviderId);
    setAccountsMsg("");
    // Sequential PUTs: a deterministic order on the server beats firing n
    // requests that may land in any order (risk 2 of the design sheet).
    var chain = Promise.resolve();
    changed.forEach(function (c) {
      chain = chain.then(function () {
        return fetchJson(ACC_API + "/" + encodeURIComponent(c.id), {
          method: "PUT",
          headers: { "Content-Type": "application/json", "Accept": "application/json" },
          body: JSON.stringify({ priority: c.priority })
        });
      });
    });
    // Always re-read from the server — after a partial failure the view must
    // show the truth, not the order the user tried to create. The message is
    // set AFTER the reload: loadAccounts() clears the status line first.
    return chain.then(function () {
      return loadAccounts(selectedProviderId);
    }).catch(function (err) {
      return loadAccounts(selectedProviderId).then(function () {
        setAccountsMsg(err.message, "error");
      });
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

  /* ---- Account modal (stage-3 add, stage-5 add + edit): ONE surface ----
      The provider id is already known here (the detail page owns it). The same
      modal now serves two modes, chosen by accModalMode:
        "add"  -> POST /api/accounts   (label, auth_type, api_key?, priority)
        "edit" -> PUT  /api/accounts/{id}  (label, enabled, api_key?)  — only
                  the fields the mode actually shows, never auth_type, priority
                  or last_used_at.
      Which rows show, what the title/submit say, and whether auth_type is
      interactive all live in setAccountModalChrome(), so the two modes can never
      drift out of sync with the request bodies they produce. */
  var accModalMode = "add";
  var accEditingId = null;

  function openAccountModal() {
    accModalMode = "add";
    accEditingId = null;
    var f = provEl("accForm");
    if (f) f.reset();
    // Seed the add defaults EXPLICITLY (not only via form.reset, which needs a
    // <form> wrapper): an edit that filled these fields must never leave a value
    // behind when the next open is an add. auth_type returns to the default.
    setFieldOrEmpty("accLabel", "");
    setFieldOrEmpty("accApiKey", "");
    var sel = provEl("accAuthType");
    if (sel) sel.value = "api_key";
    // A fresh account joins at the END of the queue (priority = current count);
    // the note under the field explains that a smaller number is tried first.
    var pr = provEl("accPriority");
    if (pr) pr.value = String(accountRows.length);
    // add mode never shows/POSTs `enabled` (a new account is created live), so
    // its default is irrelevant to the body — set it for a clean, honest control.
    var en = provEl("accEnabled");
    if (en) en.checked = true;
    setAccountModalChrome();
    syncAccountKeyRow();
    setAccModalMsg("", "");
    var m = provEl("accModal");
    if (m) m.hidden = false;
  }

  // Edit mode is seeded from `accountRows` (the last server read), NOT a refetch:
  // the card the user just tapped is already in memory with the same DTO.
  function openAccountEditModal(id) {
    var a = null;
    for (var i = 0; i < accountRows.length; i++) {
      if (String(accountRows[i].id) === String(id)) { a = accountRows[i]; break; }
    }
    if (!a) {
      // The row vanished between render and tap (a reload landed): never open an
      // edit modal on nothing. Re-read FIRST, then put the reason on the list —
      // loadAccounts clears the status line, so the message must come AFTER it
      // (same ordering rule moveAccount follows), or it would be wiped.
      return loadAccounts(selectedProviderId).then(function () {
        setAccountsMsg(getStr("provider_detail.edit_missing"), "error");
      });
    }
    accModalMode = "edit";
    accEditingId = a.id;
    var f = provEl("accForm");
    if (f) f.reset(); // clear stale add-typing BEFORE filling from the row
    setFieldOrEmpty("accLabel", a.label);
    setFieldOrEmpty("accApiKey", a.api_key);
    var sel = provEl("accAuthType");
    if (sel) sel.value = (a.auth_type === "oauth") ? "oauth" : "api_key";
    var en = provEl("accEnabled");
    if (en) en.checked = a.enabled !== false; // DTO owns truth
    setAccountModalChrome();
    syncAccountKeyRow();
    setAccModalMsg("", "");
    var m = provEl("accModal");
    if (m) m.hidden = false;
  }

  // Small input helper: null/undefined becomes "", so a blank never prints
  // "undefined" (an empty label/api_key are legitimate, distinct values).
  function setFieldOrEmpty(id, val) {
    var el = provEl(id);
    if (el) el.value = val != null ? val : "";
  }

  // Everything that differs between the two modes, in ONE place.
  function setAccountModalChrome() {
    var edit = accModalMode === "edit";
    var title = provEl("accModalTitle");
    if (title) title.textContent =
      getStr(edit ? "provider_detail.edit_title" : "provider_detail.account_modal_title");
    var submit = provEl("accAddBtn");
    if (submit) submit.textContent =
      getStr(edit ? "provider_detail.save_changes" : "accounts.add");
    // Priority belongs to adding; an existing account is ordered by ▲▼ only.
    var pr = provEl("accPriorityRow");
    if (pr) pr.hidden = edit;
    var pn = provEl("accPriorityNote");
    if (pn) pn.hidden = edit;
    // Enabled belongs to editing (a new account is always created live).
    var er = provEl("accEnabledRow");
    if (er) er.hidden = !edit;
    // auth_type is fixed once an account exists (a change is ignored anyway).
    var sel = provEl("accAuthType");
    if (sel) sel.disabled = edit;
  }

  // Close and hand the modal back in ADD mode: every value filled from a row is
  // reset and the chrome is restored, so no half-typed edit leaks into the next
  // "Add account" open.
  function closeAccountModal() {
    var m = provEl("accModal");
    if (m) m.hidden = true;
    accModalMode = "add";
    accEditingId = null;
    var f = provEl("accForm");
    if (f) f.reset();
    setAccountModalChrome();
  }

  // Auth type drives the API-key row: an OAuth account has no key to type, so we
  // hide the input and explain instead — the PUT/POST of a key to an oauth
  // account is a 400 oauth_account_key_readonly, and a form must not walk the
  // user into a rejection the backend has to hand back.
  function syncAccountKeyRow() {
    var sel = provEl("accAuthType");
    var isOauth = !!sel && sel.value !== "api_key";
    var row = provEl("accApiKeyRow");
    if (row) row.hidden = isOauth;
    var note = provEl("accOauthNote");
    if (note) note.hidden = !isOauth;
  }

  // Modal submit routes by mode. The modal closes ONLY when the write landed, so
  // a 400/404 keeps the user's typing on screen.
  function submitAccountForm(e) {
    if (e) e.preventDefault();
    var run = accModalMode === "edit" ? saveAccountEdit() : addAccount();
    return Promise.resolve(run).then(function (res) {
      if (res && res.ok) closeAccountModal();
      return res;
    });
  }

  // PUT /api/accounts/{id} — the stage-5 partial update. Body carries ONLY what
  // this mode shows: label + enabled, plus api_key for an api_key account. Never
  // auth_type (backend ignores it), never priority (▲▼ own it), never
  // last_used_at (machine-owned). A "" for label/api_key is a deliberate clear.
  function saveAccountEdit() {
    var id = accEditingId;
    if (id == null) {
      setAccModalMsg(getStr("provider_detail.edit_missing"), "error");
      return Promise.resolve({ ok: false });
    }
    var sel = provEl("accAuthType");
    var isOauth = !!sel && sel.value === "oauth";
    var body = {
      label: provEl("accLabel") ? provEl("accLabel").value : "",
      enabled: provEl("accEnabled") ? !!provEl("accEnabled").checked : true
    };
    if (!isOauth) {
      body.api_key = provEl("accApiKey") ? provEl("accApiKey").value : "";
    }
    setAccModalMsg("");
    return fetchJson(ACC_API + "/" + encodeURIComponent(id), {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body)
    }).then(function () {
      // Success: re-read from the server (moveAccount's pattern) so the card
      // shows the stored truth in the server's order — then submitAccountForm
      // closes the modal.
      return loadAccounts(selectedProviderId).then(function () { return { ok: true }; });
    }).catch(function (err) {
      if (err && err.status === 404) {
        // The row is gone server-side (another tab deleted it). Keep the modal
        // open on the message AND re-read the list so the stale card behind it
        // disappears — the id no longer exists to retry against.
        setAccModalMsg(getStr("provider_detail.edit_missing"), "error");
        return loadAccounts(selectedProviderId).then(function () { return { ok: false }; });
      }
      // Any other failure (e.g. a 400) leaves the modal open with the reason,
      // so the typing is not lost.
      setAccModalMsg(getStr("provider_detail.edit_error") + " (" + err.message + ")", "error");
      return { ok: false };
    });
  }

  // POST /api/accounts. opts may carry {provider_id,label,auth_type,api_key,
  // priority} to bypass the form (used by tests); otherwise reads the modal
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
      setAccModalMsg(getStr("accounts.provider_required"), "error");
      return Promise.resolve({ ok: false });
    }
    var body = {
      provider_id: providerId, label: label,
      auth_type: auth_type, priority: priority
    };
    if (auth_type === "api_key") body.api_key = api_key;
    setAccountsMsg("");
    setAccModalMsg("");
    return fetchJson(ACC_API, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body)
    }).then(function () {
      return loadAccounts(providerId).then(function () { return { ok: true }; });
    }).catch(function (err) {
      setAccModalMsg(getStr("accounts.add_error") + " (" + err.message + ")", "error");
      return { ok: false };
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

  /* ---- Wiring for the whole provider surface (list + detail + modals) ----
     Kept as ONE named function: init() calls it once, and a test that mounts
     the shipped page into its own jsdom calls the SAME code, so the wiring
     under test can never drift from the wiring that ships. */
  function wireProviderUi() {
    var provAdd = document.getElementById("provAddBtn");
    if (provAdd) provAdd.addEventListener("click", openAddModal);
    var provForm = document.getElementById("provForm");
    if (provForm) provForm.addEventListener("submit", saveProvider);
    // Token Saver master: toggling it enables/disables the three sub-switches.
    var provTsMaster = document.getElementById("provTokenSaver");
    if (provTsMaster) provTsMaster.addEventListener("change", syncTokenSaverUI);
    var provTest = document.getElementById("provTestBtn");
    if (provTest) provTest.addEventListener("click", testProviderConnection);
    var provCancel = document.getElementById("provCancel");
    if (provCancel) provCancel.addEventListener("click", hideModal);
    var provAddHdr = document.getElementById("provAddHeaderBtn");
    if (provAddHdr) provAddHdr.addEventListener("click", function () { addHeaderRow("", ""); });
    // The Discover button is gone (stage-2): /discover runs in the background
    // from openDetail / openEditModal and only speaks through one text line.
    // What is wired here instead: the strategy row of Kartu B + its own save.
    var pdStrategy = document.getElementById("pdStrategy");
    if (pdStrategy) pdStrategy.addEventListener("change", syncStickyLimitRow);
    var pdStrategySave = document.getElementById("pdStrategySaveBtn");
    if (pdStrategySave) pdStrategySave.addEventListener("click", saveStrategy);
    var pdBack = document.getElementById("provDetailBackBtn");
    if (pdBack) pdBack.addEventListener("click", backToProviders);
    var provEdit = document.getElementById("provEditBtn");
    if (provEdit) provEdit.addEventListener("click", function () { openEditModal(selectedProviderId); });
    var provDel = document.getElementById("provDeleteBtn");
    if (provDel) provDel.addEventListener("click", function () { deleteProvider(selectedProviderId); });
    // --- Accounts (Kartu C + its own modal) ---
    var pdAccAdd = document.getElementById("pdAccAddBtn");
    if (pdAccAdd) pdAccAdd.addEventListener("click", openAccountModal);
    var pdAccReload = document.getElementById("pdAccReloadBtn");
    if (pdAccReload) pdAccReload.addEventListener("click", function () {
      loadAccounts(selectedProviderId);
    });
    var accOAuth = document.getElementById("provConnectOAuthBtn");
    if (accOAuth) accOAuth.addEventListener("click", function () {
      connectOAuth(selectedProviderId);
    });
    var accForm = document.getElementById("accForm");
    if (accForm) accForm.addEventListener("submit", submitAccountForm);
    var accCancel = document.getElementById("accCancelBtn");
    if (accCancel) accCancel.addEventListener("click", closeAccountModal);
    var accAuthType = document.getElementById("accAuthType");
    if (accAuthType) accAuthType.addEventListener("change", syncAccountKeyRow);
    var provModal = document.getElementById("provModal");
    if (provModal) provModal.addEventListener("click", function (e) {
      if (e.target === provModal) hideModal(); // click backdrop closes
    });
    var accModal = document.getElementById("accModal");
    if (accModal) accModal.addEventListener("click", function (e) {
      if (e.target === accModal) closeAccountModal(); // click backdrop closes
    });
  }

  window.aigate.wireProviderUi = wireProviderUi;
  window.aigate.renderAccounts = renderAccounts;
  window.aigate.loadAccounts = loadAccounts;
  window.aigate.addAccount = addAccount;
  window.aigate.deleteAccount = deleteAccount;
  window.aigate.connectOAuth = connectOAuth;
  // Account modal submit + the last-read order: what the tests drive directly.
  // (The ▲▼ buttons, the open/close taps and the auth-type toggle are wired by
  // wireProviderUi / the delegated card listener, so they stay private.)
  window.aigate.submitAccountForm = submitAccountForm;
  // Edit mode is driven through the card's .acc-edit button in the shipped page;
  // these are exposed so tests can enter edit mode and read the PUT body.
  window.aigate.openAccountEditModal = openAccountEditModal;
  window.aigate.openAccountModal = openAccountModal;
  window.aigate.saveAccountEdit = saveAccountEdit;
  window.aigate.getAccountModalMode = function () {
    return { mode: accModalMode, id: accEditingId };
  };
  window.aigate.getAccountRows = function () { return accountRows.slice(); };

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

  /* ---- Developer Mode gate (Task 3) ----
     dev_mode false => hide the 3 dev-only surfaces (Log Window, Device
     Simulation, Self Heal) via CSS `body[data-devmode="off"]` and do NOT run
     the 3s /api/logs poll. true => show them + start the poll. Called from
     loadSettings()/saveSettings() once the real value is known; body ships
     data-devmode="off" so a fresh install flashes nothing before this runs. */
  function applyDevMode(on) {
    if (document.body) document.body.dataset.devmode = on ? "on" : "off";
    if (typeof fetch !== "function") return; // headless: attribute only
    if (on) {
      loadLogs();            // fill the (now visible) panel immediately
      startLogAutoRefresh();
    } else {
      stopLogAutoRefresh();
    }
  }

  /* ---- DEV-RESTART (dev-only surface) ----
     POST /api/dev/restart is fail-closed on the server (403 unless dev_mode is
     ON), and the card that holds this button is hidden by the SAME
     body[data-devmode="off"] CSS gate as the Log Window / Device Sim / Self-Heal
     surfaces — applyDevMode() already drives it, so no separate JS gate here.
     On 2xx the server restarts itself in-process (os.execv), so the client is
     the only thing left standing: we poll GET /api/health (any 2xx = back up)
     every RESTART_POLL_MS up to RESTART_POLL_MAX times, then location.reload()
     to hand control back to the freshly-booted app. */
  var RESTART_API = "/api/dev/restart";
  var HEALTH_API = "/api/health";
  var RESTART_POLL_MS = 500;
  var RESTART_POLL_MAX = 30;

  function setRestartMsg(text, kind) { setMsgIn("devRestartMsg", text, kind); }

  function pollHealthThenReload(attempt) {
    if (attempt >= RESTART_POLL_MAX) {
      // Server never answered within the window — leave the honest status.
      setRestartMsg(getStr("settings.restarting"), "error");
      return;
    }
    fetch(HEALTH_API, {
      method: "GET",
      headers: { "Accept": "application/json" },
      cache: "no-store"
    })
      .then(function (r) {
        if (r.ok) { window.location.reload(); return; }
        setTimeout(function () { pollHealthThenReload(attempt + 1); }, RESTART_POLL_MS);
      })
      .catch(function () {
        setTimeout(function () { pollHealthThenReload(attempt + 1); }, RESTART_POLL_MS);
      });
  }

  function devRestart() {
    if (!window.confirm(getStr("settings.dev_restart_confirm"))) return;
    setRestartMsg("", "");
    fetch(RESTART_API, {
      method: "POST",
      headers: { "Accept": "application/json" }
    })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        setRestartMsg(getStr("settings.restarting"));
        pollHealthThenReload(0);
      })
      .catch(function (err) {
        // 403 dev_mode_required is unexpected (the button hides when off) — but
        // surface it instead of spinning. fetchJson's error shape is reused.
        setRestartMsg(getStr("settings.error") + " (" + err.message + ")", "error");
      });
  }

  // Re-attach the click handler so a test that re-mounts the shipped body can
  // bind the button in isolation (same reason wireDevModeToggle is exported).
  function wireDevRestart() {
    var btn = document.getElementById("devRestartBtn");
    if (btn) btn.addEventListener("click", devRestart);
  }


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
  // NOTE: openStackIds (expanded stacktrace ids, Task 1) is declared at the top
  // of this IIFE so window.aigate.openStackIds shares the same instance.

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
        ? '<details class="log-stack"' +
          ' data-logid="' + escapeHtml(row.id) + '"' +
          // Id is normalized to a string on BOTH sides: the delegate stores what
          // getAttribute returns (always a string, even when the API sends a
          // number like {"id":4}), and here we compare String(row.id) so a
          // numeric id (4) matches the stored "4". Without this, a numeric id
          // collapses on every 3s poll (type mismatch, jsdom-string tests hid it).
          (openStackIds.has(String(row.id)) ? ' open' : '') +
          '><summary>' + escapeHtml(getStr("term.stacktrace")) +
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

  /* Delegated listeners on the (stable) #logTableBody. Extracted so a jsdom
     test that creates the tbody AFTER init() can re-attach them (init ran
     against an empty document body). One click delegate for per-row resolve,
     one capture-phase `toggle` delegate to remember expanded stacktraces so
     renderLogs re-applies `open` across the 3s poll instead of collapsing
     them (Task 1). `toggle` does not bubble, so it is captured on the tbody. */
  function wireLogTable() {
    var logTableBody = document.getElementById("logTableBody");
    if (!logTableBody) return;
    logTableBody.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest(".log-resolve-btn") : null;
      if (btn && btn.getAttribute("data-id")) resolveLog(btn.getAttribute("data-id"));
    });
    logTableBody.addEventListener("toggle", function (e) {
      var d = e.target;
      if (!d || !d.classList || !d.classList.contains("log-stack")) return;
      var id = d.getAttribute("data-logid");
      if (id == null) return;
      // Store the normalized string key so it always matches String(row.id) in
      // renderLogs. The API sends numeric ids but the attribute round-trips as a
      // string; keying on the string form for both keeps number-vs-string safe.
      id = String(id);
      if (d.open) openStackIds.add(id);
      else openStackIds.delete(id);
    }, true);
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

    // --- Device simulation (B4.2, Opsi A): the control moved OUT of the Settings
    //     form into a small trigger above the Repo link (sidebar-footer on desktop,
    //     .bn-device in the bottom-nav on phone). Clicking it opens an accessible
    //     modal with a live iframe preview. The preview is scoped to the iframe
    //     only — selecting a mode never touches the live page. The #setDevice
    //     <select> + its change listener are gone.
    setupDeviceModal();

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
      } else if (view === "chat") {
        // B8.B6.2/B6.3: load the session list; streaming + picker wired at boot.
        if (window.aigate && window.aigate.chat) window.aigate.chat.onShow();
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
    // Developer Mode switch applies + persists instantly on toggle (no Save click).
    wireDevModeToggle();
    // DEV-RESTART: bind the dev-only restart button (hidden via the dev gate when off).
    wireDevRestart();

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

    // --- Providers (B2.2) + provider-detail page (stage-3, Opsi A) ---
    // One named wiring function (window.aigate.wireProviderUi) instead of inline
    // code here: the shipped page has to be re-mounted by tests, and duplicating
    // the wiring there would drift from production the first time it changed.
    wireProviderUi();

    // --- Chat Playground (B8.B6.2/B6.3) — wired here so the view works from
    // boot; its onShow hook (window.aigate.chat) is invoked by handleNav. ---
    wireChatUi();

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
    // Rows re-render often -> delegate resolve clicks + stacktrace toggles on the
    // (stable) tbody, so the listeners survive every innerHTML rebuild.
    wireLogTable();

    // --- Global Log Window: restore show/hide + gate the log poll on dev_mode ---
    var logVisible = read(LOG_VISIBLE_KEY, "1") !== "0";
    applyLogVisible(logVisible);
    applyShowResolved();
    observeLogWindow();
    // Read the real dev_mode and let applyDevMode() decide whether to start the
    // 3s /api/logs poll. body ships data-devmode="off" (index.html), so a fresh
    // install shows nothing until the value lands. Guarded so headless test envs
    // without fetch() don't error on import.
    if (typeof fetch === "function") {
      loadSettings();
    }

    // Start on the welcome view.
    showView("welcome");
  }

  /* ===== Chat Playground (B8.B6.2 core + B6.3 polish / PRD §2.9) =====
     A thin conversation UI on top of the gateway: sessions CRUD + an SSE
     streaming composer + per-session system_prompt/temperature/rename/stop.
     It is part of the SPA shell (no new <script>), so it shares window.aigate
     helpers (getStr/escapeHtml/fetchJson), the nav wiring, and the i18n keys.
     Backend contract (chat_router.py, verified): model ref is
     `provider:<name>[:<model_id>]` or `combo:<name>` — the SAME strings the
     gateway /v1/models advertises, so the picker reads that endpoint (never
     guessing a ref). After a /complete stream the assistant turn is only in the
     DB, so we ALWAYS re-GET the session (authoritative history). */
  var CHAT_API = "/api/chat/sessions";
  var CHAT_MODELS_API = "/v1/models";
  var chatState = { currentId: null, currentModel: null, streaming: false, controller: null };
  var chatDialogs = {};

  function chatEl(id) { return document.getElementById(id); }
  function chatMsg(id, text, kind) {
    var m = chatEl(id);
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }
  function setChatMsg(t, k) { chatMsg("chatMsg", t, k); }
  function setChatListMsg(t, k) { chatMsg("chatListMsg", t, k); }
  function setChatSettingsMsg(t, k) { chatMsg("chatSettingsMsg", t, k); }
  function setChatNewMsg(t, k) { chatMsg("chatNewMsg", t, k); }

  /* ---- Pure helpers (no DOM/fetch; exported for tests) ---- */

  // Map a gateway model ref to a human label + its kind. Never invents a ref.
  function describeTarget(modelRef) {
    var ref = modelRef == null ? "" : String(modelRef);
    if (!ref) return { kind: "none", name: "", model: "", label: "" };
    if (ref.indexOf("combo:") === 0) {
      var cname = ref.slice("combo:".length);
      return { kind: "combo", name: cname, model: "", label: getStr("chat.target_combo") + ": " + cname };
    }
    if (ref.indexOf("provider:") === 0) {
      var rest = ref.slice("provider:".length);
      var i = rest.indexOf(":");
      var pname = i === -1 ? rest : rest.slice(0, i);
      var pmodel = i === -1 ? "" : rest.slice(i + 1);
      return { kind: "provider", name: pname, model: pmodel,
        label: getStr("chat.target_provider") + ": " + pname + (pmodel ? " · " + pmodel : "") };
    }
    return { kind: "bare", name: "", model: ref, label: ref }; // bare id (resolver accepts it too)
  }

  // tokens_in/out may be null (usage unavailable) -> "—", never a fake 0.
  function formatTokens(v) {
    return (v === null || v === undefined || v !== v) ? "—" : String(v);
  }

  // One SSE line -> {type, content?}. Only `data:` field lines carry payloads;
  // other fields (event:/id:/retry:) and blanks are ignored, per the SSE spec.
  //   delta   -> a content fragment to append
  //   done    -> the [DONE] sentinel
  //   error   -> an upstream/JSON error frame or unparseable data line
  //   ignore  -> blank / non-data field line
  function parseSseLine(line) {
    if (line == null) return { type: "ignore" };
    var s = String(line).replace(/\r$/, "");
    if (s.indexOf("data:") !== 0) return { type: "ignore" };
    s = s.slice(5).trim();
    if (s === "") return { type: "ignore" };
    if (s === "[DONE]") return { type: "done" };
    var obj;
    try { obj = JSON.parse(s); } catch (e) { return { type: "error", raw: s }; }
    if (obj && obj.error) return { type: "error", raw: s };
    var choices = (obj && Array.isArray(obj.choices)) ? obj.choices : [];
    var c0 = choices[0] || {};
    var content = "";
    if (typeof c0.delta === "object" && c0.delta && typeof c0.delta.content === "string") {
      content = c0.delta.content;
    } else if (typeof c0.message === "object" && c0.message && typeof c0.message.content === "string") {
      content = c0.message.content;
    }
    return { type: "delta", content: content };
  }

  /* ---- Rendering ---- */
  function roleLabel(role) {
    if (role === "assistant") return getStr("chat.role_assistant");
    if (role === "system") return getStr("chat.role_system");
    return getStr("chat.role_you");
  }

  function createMessageEl(msg) {
    msg = msg || {};
    var wrap = document.createElement("div");
    wrap.className = "chat-msg chat-msg-" + (msg.role || "user");
    var meta = document.createElement("div");
    meta.className = "chat-msg-meta";
    meta.textContent = roleLabel(msg.role);
    var text = document.createElement("div");
    text.className = "chat-msg-text";
    text.textContent = msg.content == null ? "" : String(msg.content);
    wrap.appendChild(meta);
    wrap.appendChild(text);
    if (msg.role === "assistant") {
      var tok = document.createElement("div");
      tok.className = "chat-msg-tokens";
      tok.textContent = getStr("chat.tokens") + ": " +
        formatTokens(msg.tokens_in) + " / " + formatTokens(msg.tokens_out);
      wrap.appendChild(tok);
    }
    return wrap;
  }

  function scrollThreadToEnd() {
    var thread = chatEl("chatThread");
    if (thread) thread.scrollTop = thread.scrollHeight;
  }

  function renderMessages(messages) {
    var thread = chatEl("chatThread");
    if (!thread) return;
    thread.innerHTML = "";
    if (!messages || !messages.length) {
      var empty = document.createElement("div");
      empty.className = "chat-empty";
      empty.textContent = getStr("chat.empty");
      thread.appendChild(empty);
      return;
    }
    for (var i = 0; i < messages.length; i++) thread.appendChild(createMessageEl(messages[i]));
    scrollThreadToEnd();
  }

  function markActiveSession(id) {
    var ul = chatEl("chatSessionList");
    if (!ul) return;
    Array.prototype.forEach.call(ul.querySelectorAll(".chat-session"), function (li) {
      li.classList.toggle("is-active", li.getAttribute("data-id") === String(id));
    });
  }

  function renderSessionList(list) {
    var ul = chatEl("chatSessionList");
    if (!ul) return;
    ul.innerHTML = "";
    if (!list || !list.length) {
      var li = document.createElement("li");
      li.className = "chat-session-empty";
      li.textContent = getStr("chat.no_sessions");
      ul.appendChild(li);
      return;
    }
    list.forEach(function (s) {
      var item = document.createElement("li");
      item.className = "chat-session" + (s.id === chatState.currentId ? " is-active" : "");
      item.setAttribute("data-id", s.id);
      var title = document.createElement("div");
      title.className = "chat-session-title";
      title.textContent = s.title || getStr("chat.new");
      var t = describeTarget(s.model);
      var sub = document.createElement("div");
      sub.className = "chat-session-target";
      sub.textContent = t.kind === "none" ? getStr("chat.no_target") : t.label;
      item.appendChild(title);
      item.appendChild(sub);
      item.addEventListener("click", function () { openSession(s.id); });
      ul.appendChild(item);
    });
  }

  function renderSession(session) {
    if (!session) return;
    chatState.currentId = session.id;
    chatState.currentModel = session.model || null;
    var title = chatEl("chatTitleInput");
    if (title) title.value = session.title || "";
    var target = chatEl("chatTarget");
    if (target) {
      var t = describeTarget(session.model);
      target.textContent = t.kind === "none" ? getStr("chat.no_target") : t.label;
      target.className = "chat-target" + (t.kind === "none" ? " chat-target-none" : "");
    }
    var sys = chatEl("chatSystemPrompt");
    if (sys) sys.value = session.system_prompt || "";
    var temp = chatEl("chatTemperature");
    if (temp) temp.value = session.temperature == null ? "" : String(session.temperature);
    renderMessages(session.messages || []);
    markActiveSession(session.id);
  }

  /* ---- Loaders / actions ---- */
  function loadChatSessions() {
    return fetchJson(CHAT_API).then(function (data) {
      renderSessionList((data && data.data) ? data.data : []);
    }).catch(function (err) {
      setChatListMsg(getStr("chat.load_error") + " (" + err.message + ")", "error");
    });
  }

  function openSession(id) {
    return fetchJson(CHAT_API + "/" + id).then(function (session) {
      renderSession(session);
    }).catch(function () {
      setChatMsg(getStr("chat.error"), "error");
    });
  }

  function loadChat() {
    setChatMsg("", "");
    setChatSettingsMsg("", "");
    return loadChatSessions();
  }

  /* ---- Model/combo picker (combobox.js, same pattern as the CLI launcher) ---- */
  var chatModelCombo = null;
  function chatModelCtl() {
    if (!chatModelCombo && typeof window.aigate !== "undefined" &&
        typeof window.aigate.createCombobox === "function") {
      chatModelCombo = window.aigate.createCombobox({
        inputId: "chatNewModel",
        listId: "chatNewModelList",
        searchInside: true,
        groupBy: "group",
        groupOrder: [getStr("combobox.group_combos")],
        subGroupBy: "prefix"
      });
    }
    return chatModelCombo;
  }

  function fetchChatModels() {
    return fetchJson(CHAT_MODELS_API).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      var c = chatModelCtl();
      var comboGroup = getStr("combobox.group_combos");
      if (c && typeof c.setGroupOrder === "function") c.setGroupOrder([comboGroup]);
      var opts = list.map(function (m) {
        var id = m.id != null ? m.id : "";
        if (id.indexOf("combo:") === 0) {
          return { value: id, label: id.slice("combo:".length), group: comboGroup, subGroup: false };
        }
        return { value: id, label: id.split(":").pop(), group: m.owned_by || "unknown" };
      });
      opts.sort(function (a, b) {
        var al = a.label.toLowerCase(), bl = b.label.toLowerCase();
        return al < bl ? -1 : al > bl ? 1 : 0;
      });
      if (c) c.setOptions(opts);
      if (c && opts.length) c.setValue(opts[0].value);
      if (!list.length) setChatNewMsg(getStr("chat.picker_none"), "warn");
      return list;
    });
  }

  function readComboValue() {
    var c = chatModelCombo;
    if (c && typeof c.getValue === "function") return c.getValue();
    var inp = chatEl("chatNewModel");
    return inp ? String(inp.value || "").trim() : "";
  }

  /* ---- New-session modal ---- */
  function openNewChatModal(trigger) {
    var title = chatEl("chatNewTitleInput");
    if (title) title.value = "";
    setChatNewMsg("", "");
    fetchChatModels().catch(function () {}).then(function () {
      openChatDialog("chatNewModal", trigger);
    });
  }

  function createChatSession() {
    var model = readComboValue();
    if (!model) { setChatNewMsg(getStr("chat.model_required"), "error"); return; }
    var titleEl = chatEl("chatNewTitleInput");
    var title = titleEl ? String(titleEl.value || "").trim() : "";
    var body = { model: model };
    if (title) body.title = title;
    fetchJson(CHAT_API, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (session) {
      closeChatDialog("chatNewModal");
      chatState.currentId = session.id;
      return loadChatSessions().then(function () { openSession(session.id); });
    }).catch(function (err) {
      setChatNewMsg(err.message || getStr("chat.error"), "error");
    });
  }

  /* ---- Rename / delete / settings (all via PUT/DELETE) ---- */
  function openRenameModal(trigger) {
    if (!chatState.currentId) { setChatMsg(getStr("chat.empty"), "warn"); return; }
    var cur = chatEl("chatTitleInput");
    var input = chatEl("chatRenameInput");
    if (input) input.value = cur ? cur.value : "";
    openChatDialog("chatRenameModal", trigger);
  }
  function saveRename() {
    if (!chatState.currentId) return;
    var input = chatEl("chatRenameInput");
    var title = input ? String(input.value || "").trim() : "";
    fetchJson(CHAT_API + "/" + chatState.currentId, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title })
    }).then(function (session) {
      closeChatDialog("chatRenameModal");
      var t = chatEl("chatTitleInput");
      if (t) t.value = session.title || "";
      loadChatSessions();
    }).catch(function () { setChatMsg(getStr("chat.rename_error"), "error"); });
  }

  function openDeleteModal(trigger) {
    if (!chatState.currentId) { setChatMsg(getStr("chat.empty"), "warn"); return; }
    openChatDialog("chatDeleteModal", trigger);
  }
  function confirmDeleteSession() {
    if (!chatState.currentId) return;
    fetchJson(CHAT_API + "/" + chatState.currentId, { method: "DELETE" }).then(function () {
      closeChatDialog("chatDeleteModal");
      chatState.currentId = null;
      chatState.currentModel = null;
      var thread = chatEl("chatThread"); if (thread) thread.innerHTML = "";
      var title = chatEl("chatTitleInput"); if (title) title.value = "";
      var target = chatEl("chatTarget"); if (target) { target.textContent = ""; target.className = "chat-target"; }
      loadChatSessions();
    }).catch(function () { setChatMsg(getStr("chat.delete_error"), "error"); });
  }

  function saveChatSettings() {
    if (!chatState.currentId) { setChatSettingsMsg(getStr("chat.empty"), "warn"); return; }
    var sys = chatEl("chatSystemPrompt");
    var temp = chatEl("chatTemperature");
    var body = {};
    if (sys) body.system_prompt = sys.value;
    if (temp && String(temp.value).trim() !== "") {
      var v = parseFloat(temp.value);
      if (!isNaN(v)) body.temperature = v;
    }
    fetchJson(CHAT_API + "/" + chatState.currentId, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (session) {
      chatState.currentModel = session.model || null;
      setChatSettingsMsg(getStr("chat.saved"), "ok");
    }).catch(function () { setChatSettingsMsg(getStr("chat.save_error"), "error"); });
  }

  /* ---- Streaming (SSE via fetch + ReadableStream; Stop via AbortController) ---- */
  function setStreamingUI(on) {
    var sendBtn = chatEl("chatSendBtn");
    var stopBtn = chatEl("chatStopBtn");
    if (sendBtn) sendBtn.disabled = !!on;
    if (stopBtn) stopBtn.hidden = !on;
  }

  // Read an SSE body to completion, invoking onDelta(content) per fragment.
  function readSseStream(res, onDelta, signal) {
    var reader = res.body.getReader();
    var decoder = new TextDecoder("utf-8");
    var buffer = "";
    function step() {
      if (signal && signal.aborted) return Promise.resolve();
      return reader.read().then(function (result) {
        if (result.done) return;
        buffer += decoder.decode(result.value, { stream: true });
        var frames = buffer.split("\n\n");
        buffer = frames.pop() || "";
        for (var f = 0; f < frames.length; f++) {
          var lines = frames[f].split("\n");
          for (var j = 0; j < lines.length; j++) {
            var ev = parseSseLine(lines[j]);
            if (ev.type === "delta") onDelta(ev.content);
            else if (ev.type === "error") { reader.cancel(); return Promise.reject(new Error("stream_error")); }
          }
        }
        return step();
      });
    }
    return step();
  }

  function finishStream(sessionId) {
    chatState.streaming = false;
    chatState.controller = null;
    setStreamingUI(false);
    // Authoritative re-read: the persisted assistant turn only exists in the DB.
    return openSession(sessionId).then(function () { loadChatSessions(); });
  }

  function streamChat(sessionId, content) {
    if (chatState.streaming) return;
    var controller = new AbortController();
    chatState.controller = controller;
    chatState.streaming = true;
    setStreamingUI(true);
    setChatMsg("", "");

    var thread = chatEl("chatThread");
    // Optimistic: show the user turn + a live assistant bubble while it streams.
    if (thread && thread.querySelector(".chat-empty")) thread.innerHTML = "";
    if (thread) thread.appendChild(createMessageEl({ role: "user", content: content }));
    var assistantEl = createMessageEl({ role: "assistant", content: "" });
    if (thread) thread.appendChild(assistantEl);
    scrollThreadToEnd();
    var textNode = assistantEl.querySelector(".chat-msg-text");

    fetch(CHAT_API + "/" + sessionId + "/complete", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "text/event-stream" },
      body: JSON.stringify({ content: content }),
      signal: controller.signal
    }).then(function (res) {
      if (!res.ok) {
        return res.json().catch(function () { return {}; }).then(function (b) {
          var m = (b && b.error && b.error.message) ? b.error.message : ("HTTP " + res.status);
          throw new Error(m);
        });
      }
      var ct = res.headers.get("content-type") || "";
      if (ct.indexOf("text/event-stream") !== -1) {
        return readSseStream(res, function (chunk) {
          if (textNode) textNode.textContent += chunk;
          scrollThreadToEnd();
        }, controller.signal);
      }
      // Non-stream fallback (some translated formats answer as JSON).
      return res.json().then(function (data) {
        var c = (data && data.choices && data.choices[0] && data.choices[0].message &&
          data.choices[0].message.content) || "";
        if (textNode) textNode.textContent += c;
        scrollThreadToEnd();
      });
    }).then(function () {
      return finishStream(sessionId);
    }).catch(function (err) {
      if (err && err.name === "AbortError") {
        setChatMsg(getStr("chat.stop"), "warn");
      } else {
        setChatMsg(getStr("chat.send_error") + (err && err.message ? " (" + err.message + ")" : ""), "error");
      }
      return finishStream(sessionId);
    });
  }

  function sendChatMessage() {
    var input = chatEl("chatInput");
    if (!input) return;
    var content = String(input.value || "").trim();
    if (!content) return;
    if (!chatState.currentId) { setChatMsg(getStr("chat.empty"), "warn"); return; }
    if (!chatState.currentModel) { setChatMsg(getStr("chat.no_target"), "error"); return; }
    input.value = "";
    streamChat(chatState.currentId, content);
  }

  function stopChatGeneration() {
    if (chatState.controller) {
      try { chatState.controller.abort(); } catch (e) { /* already done */ }
    }
  }

  /* ---- Accessible dialogs (focus-trap + ESC + restore focus; mirrors the
         device-sim modal pattern already in this file). Backdrop click closes. ---- */
  function chatFocusables(modal) {
    return Array.prototype.slice.call(modal.querySelectorAll(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), ' +
      'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ));
  }
  function openChatDialog(id, trigger) {
    var m = chatEl(id);
    if (!m) return;
    chatDialogs[id] = { trigger: trigger || null };
    m.hidden = false;
    var f = chatFocusables(m);
    if (f.length) f[0].focus();
    var handler = function (e) {
      if (e.key === "Escape") { e.preventDefault(); closeChatDialog(id); return; }
      if (e.key !== "Tab") return;
      var list = chatFocusables(m);
      if (!list.length) return;
      var first = list[0], last = list[list.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first || !m.contains(document.activeElement)) { e.preventDefault(); last.focus(); }
      } else if (document.activeElement === last || !m.contains(document.activeElement)) {
        e.preventDefault(); first.focus();
      }
    };
    m.__chatKey = handler;
    document.addEventListener("keydown", handler, true);
  }
  function closeChatDialog(id) {
    var m = chatEl(id);
    if (!m || m.hidden) return;
    m.hidden = true;
    if (m.__chatKey) { document.removeEventListener("keydown", m.__chatKey, true); m.__chatKey = null; }
    var trigger = chatDialogs[id] ? chatDialogs[id].trigger : null;
    delete chatDialogs[id];
    if (trigger && typeof trigger.focus === "function") trigger.focus();
  }

  function wireChatUi() {
    var b;
    b = chatEl("chatNewBtn"); if (b) b.addEventListener("click", function () { openNewChatModal(b); });
    b = chatEl("chatNewCreate"); if (b) b.addEventListener("click", createChatSession);
    b = chatEl("chatNewCancel"); if (b) b.addEventListener("click", function () { closeChatDialog("chatNewModal"); });
    b = chatEl("chatRenameBtn"); if (b) b.addEventListener("click", function () { openRenameModal(b); });
    b = chatEl("chatRenameSave"); if (b) b.addEventListener("click", saveRename);
    b = chatEl("chatRenameCancel"); if (b) b.addEventListener("click", function () { closeChatDialog("chatRenameModal"); });
    b = chatEl("chatDeleteBtn"); if (b) b.addEventListener("click", function () { openDeleteModal(b); });
    b = chatEl("chatDeleteConfirm"); if (b) b.addEventListener("click", confirmDeleteSession);
    b = chatEl("chatDeleteCancel"); if (b) b.addEventListener("click", function () { closeChatDialog("chatDeleteModal"); });
    b = chatEl("chatSendBtn"); if (b) b.addEventListener("click", sendChatMessage);
    b = chatEl("chatStopBtn"); if (b) b.addEventListener("click", stopChatGeneration);
    b = chatEl("chatSettingsSave"); if (b) b.addEventListener("click", saveChatSettings);

    var input = chatEl("chatInput");
    if (input) {
      input.setAttribute("placeholder", getStr("chat.input_ph"));
      input.addEventListener("keydown", function (e) {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
      });
    }
    var modelInput = chatEl("chatNewModel");
    if (modelInput) modelInput.setAttribute("placeholder", getStr("combobox.search_ph"));

    // backdrop click closes any open chat dialog
    ["chatNewModal", "chatRenameModal", "chatDeleteModal"].forEach(function (id) {
      var m = chatEl(id);
      if (m) m.addEventListener("click", function (e) { if (e.target === m) closeChatDialog(id); });
    });
  }
  window.aigate.wireChatUi = wireChatUi;

  window.aigate.chat = {
    onShow: loadChat,
    loadChat: loadChat,
    openSession: openSession,
    send: sendChatMessage,
    stop: stopChatGeneration,
    _test: {
      describeTarget: describeTarget,
      formatTokens: formatTokens,
      parseSseLine: parseSseLine,
      createMessageEl: createMessageEl,
      renderMessages: renderMessages,
      renderSessionList: renderSessionList,
      readSseStream: readSseStream
    }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
