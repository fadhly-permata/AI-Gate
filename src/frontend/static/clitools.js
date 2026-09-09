/* ===== aigate CLI Tools launcher (B3.4) — vanilla JS, no build ===== */
/* Spec: FSD §2.6 / §2.6.1 / UX §3, PRD §2.6, CLI_CONFIG_SCHEMA.md.
   Grouping UI (A/B/C) + model picker modal + resolve via backend +
   launch into a NEW terminal tab (reuses B3.3 terminal manager).
   The PTY WebSocket backend (B3.2) and terminal manager (B3.3) are owned
   here too. xterm refs only inside methods so this file is testable. */

(function () {
  "use strict";

  /* ---------------------------------------------------------------
   * PURE HELPER (importable + testable via vitest)
   *
   * Build a PTY-side, SELF-DECIDING shell command to launch a CLI tool.
   *
   * WHY self-deciding: `binary_found` in the DTO is computed by the SERVER
   * process's PATH, which may not include where the user actually installed
   * the tool (~/.local/bin, pipx, npm global, a venv, Termux prefix...). The
   * interactive PTY has the user's real login PATH, so `command -v` THERE is
   * authoritative. We therefore never trust `binary_found` to pick install vs
   * run — the emitted command checks the binary itself and only installs when
   * genuinely absent:
   *
   *   export OPENAI_API_BASE='<base>'
   *   export OPENAI_API_KEY='<key>'
   *   if command -v <binary_name> >/dev/null 2>&1; then
   *     <run_command>
   *   else
   *     <install_command>
   *   fi
   *
   * @param {object} dto - resolve DTO from POST /api/cli-tools/resolve
   *   { binary_found:bool (HINT only, ignored here), binary_name:str,
   *     install_command:str (may be ""), run_command:str,
   *     env:{OPENAI_API_BASE, OPENAI_API_KEY}, model }
   * @returns {string} command to send into the terminal.
   * --------------------------------------------------------------- */

  /* POSIX single-quote wrapping: wrap in '...' and escape any embedded '
   * via the '\'' idiom (close-quote, escaped-quote, reopen-quote). Safe for
   * arbitrary base/key values, incl. spaces and single quotes. */
  function shSingleQuote(s) {
    s = s == null ? "" : String(s);
    return "'" + s.replace(/'/g, "'\\''") + "'";
  }

  function buildLaunchCommand(dto) {
    dto = dto || {};
    var env = dto.env || {};
    var base = env.OPENAI_API_BASE != null ? env.OPENAI_API_BASE : "";
    var key = env.OPENAI_API_KEY != null ? env.OPENAI_API_KEY : "";
    var run = dto.run_command != null ? String(dto.run_command) : "";
    var install = dto.install_command != null ? String(dto.install_command) : "";

    // Binary to probe: prefer dto.binary_name; fall back (defensively) to the
    // first token of run_command when it is missing/blank.
    var binary = dto.binary_name != null ? String(dto.binary_name).trim() : "";
    if (!binary) {
      var toks = run.trim().split(/\s+/);
      binary = toks[0] || "";
    }

    // `then` body: run_command, or a `:` no-op if empty (empty body is a
    // shell syntax error). `else` body: install_command, or a clear message
    // when no install command is configured.
    var thenBody = run.trim() !== "" ? run : ":";
    var elseBody = install.trim() !== ""
      ? install
      : 'echo "aigate: \'' + binary + "' not installed and no install command configured\"";

    // ADR-007: plaintext OPENAI_API_KEY injected into the local shell is fine.
    // Env exports kept for generic tools that read OPENAI_API_BASE/KEY.
    return "export OPENAI_API_BASE=" + shSingleQuote(base) + "\n" +
           "export OPENAI_API_KEY=" + shSingleQuote(key) + "\n" +
           "if command -v " + binary + " >/dev/null 2>&1; then\n" +
           "  " + thenBody + "\n" +
           "else\n" +
           "  " + elseBody + "\n" +
           "fi\n";
  }

  window.aigate = window.aigate || {};
  window.aigate.buildLaunchCommand = buildLaunchCommand;

  /* ---------------------------------------------------------------
   * i18n helper (mirrors app.js / terminal.js)
   * --------------------------------------------------------------- */
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

  /* ---------------------------------------------------------------
   * State + DOM refs
   * --------------------------------------------------------------- */
  var CLI_API = "/api/cli-tools";
  var MODELS_API = "/v1/models";
  var currentTool = null;

  function el(id) { return document.getElementById(id); }

  /* ---- Model picker: searchable combobox (combobox.js) ----
     Replaces the old native <select id="cliModel">. #cliModel is now a text
     <input> wired to a custom <ul id="cliModelList"> panel. The controller is
     created LAZILY (first use) and resolves its elements by id, so it survives
     DOM rebuilds. searchInside=true gives an in-panel search box; groupBy="group"
     groups options by provider (option.group), with the combo group pinned to the
     top via groupOrder. The combo group LABEL is localized through
     `combobox.group_combos` ("Combos" in EN, "Kombo" in ID) — never a hardcoded
     literal — and re-pinned on every fetch so a locale switch keeps it on top.
     The option VALUE stays the full gateway id (provider:... / combo:...) so
     launch() can POST it verbatim; only the LABEL is the human model portion. */
  function comboGroupName() {
    return getStr("combobox.group_combos");
  }

  var cliModelCombo = null;
  function cliModelCtl() {
    if (!cliModelCombo && typeof window.aigate !== "undefined" &&
        typeof window.aigate.createCombobox === "function") {
      cliModelCombo = window.aigate.createCombobox({
        inputId: "cliModel",
        listId: "cliModelList",
        searchInside: true,
        groupBy: "group",
        groupOrder: [comboGroupName()],
        subGroupBy: "prefix" // two-level: provider (main) -> model-name prefix (sub)
      });
    }
    return cliModelCombo;
  }

  function setCliMsg(text, kind) {
    var m = el("cliLoadMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function showModal(id) { var m = el(id); if (m) m.hidden = false; }
  function hideModal(id) { var m = el(id); if (m) m.hidden = true; }

  /* ---------------------------------------------------------------
   * fetch JSON (mirrors app.js fetchJson error shape)
   * --------------------------------------------------------------- */
  function fetchJson(url, opts) {
    opts = opts || {};
    opts.headers = Object.assign({ "Accept": "application/json" }, opts.headers || {});
    return fetch(url, opts).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (b) {
          var msg = (b && b.error && b.error.message) ? b.error.message : ("HTTP " + r.status);
          var err = new Error(msg); err.status = r.status; throw err;
        }).catch(function () { var e = new Error("HTTP " + r.status); e.status = r.status; throw e; });
      }
      var ct = r.headers.get("content-type") || "";
      if (ct.indexOf("application/json") === -1) return null;
      return r.json();
    });
  }

  /* ---------------------------------------------------------------
   * Load + render groups (A/B/C) from GET /api/cli-tools
   * --------------------------------------------------------------- */
  function loadCliTools() {
    setCliMsg(getStr("cli.loading"), "");
    fetchJson(CLI_API).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      var cur = (data && data.current_platform) ? data.current_platform : "unknown";
      renderGroups(list, cur);
      setCliMsg("");
    }).catch(function (err) {
      setCliMsg(getStr("cli.load_error") + " (" + err.message + ")", "error");
    });
  }

  /* Platform order shown as compatibility badges (must match backend PLATFORMS). */
  var COMPAT_PLATFORMS = ["termux", "linux", "windows", "macos"];
  /* Statuses that warrant a visible warning on the CURRENT platform. */
  var COMPAT_WARN = { broken: 1, no_install: 1, not_a_cli: 1, not_wired: 1 };

  function platformLabel(code) {
    return getStr("cli.platform." + code);
  }

  function statusLabel(status) {
    return getStr("cli.status." + (status || "unknown"));
  }

  /* One badge per platform, colored by status; the current platform is outlined. */
  function renderCompatStrip(tool, currentPlatform) {
    var compat = tool.compat || {};
    var strip = document.createElement("div");
    strip.className = "cli-compat";
    COMPAT_PLATFORMS.forEach(function (p) {
      var info = compat[p] || { status: "unknown", note: "", source: "unknown" };
      var status = info.status || "unknown";
      var chip = document.createElement("span");
      chip.className = "cli-compat-chip cli-status-" + status +
        (p === currentPlatform ? " cli-compat-current" : "");
      chip.textContent = platformLabel(p);
      chip.title = platformLabel(p) + ": " + statusLabel(status) +
        (info.note ? " — " + info.note : "");
      strip.appendChild(chip);
    });
    return strip;
  }

  /* Red warning line when the tool is not usable on the current platform. */
  function renderCompatWarn(tool, currentPlatform) {
    var compat = tool.compat || {};
    var info = compat[currentPlatform] || { status: "unknown", note: "" };
    var status = info.status || "unknown";
    if (!COMPAT_WARN[status]) return null;
    var warn = document.createElement("div");
    warn.className = "cli-compat-warn";
    warn.textContent = "⚠ " + getStr("cli.compat.warn_label") + " " + (info.note || statusLabel(status));
    return warn;
  }

  /* Legend shown once above the groups (mirrors the per-tool badge styling). */
  function renderCompatLegend(currentPlatform) {
    var legend = document.createElement("div");
    legend.className = "cli-compat-legend";
    var txt = document.createElement("span");
    txt.textContent = getStr("cli.compat.legend") + " ";
    legend.appendChild(txt);
    COMPAT_PLATFORMS.forEach(function (p) {
      var chip = document.createElement("span");
      chip.className = "cli-compat-chip" + (p === currentPlatform ? " cli-compat-current" : "");
      chip.textContent = platformLabel(p);
      legend.appendChild(chip);
    });
    return legend;
  }

  /* Human explanation for a struck-through tool. The server sends a stable
     reason CODE (tool.launch_reason); the text is translated here so the same
     payload serves both locales. Unknown/absent code -> the generic note. */
  function unsupportedNote(tool) {
    var mode = tool.launch_mode || "pending";
    if (mode !== "unsupported") return getStr("cli.reason.pending");
    var key = "cli.reason." + (tool.launch_reason || "");
    var note = getStr(key);
    return note === key ? getStr("cli.unsupported") : note;
  }

  function renderGroups(groups, currentPlatform) {
    var wrap = el("cliGroups");
    if (!wrap) return;
    if (!groups.length) {
      wrap.innerHTML = '<p class="empty-cell">' + escapeHtml(getStr("cli.no_tools")) + "</p>";
      return;
    }
    wrap.innerHTML = "";
    // Legend explaining the per-platform badges (once, above all groups).
    if (currentPlatform && currentPlatform !== "unknown") {
      wrap.appendChild(renderCompatLegend(currentPlatform));
    }
    groups.forEach(function (g) {
      var section = document.createElement("div");
      section.className = "cli-group";

      var h = document.createElement("h3");
      h.className = "cli-group-title";
      h.textContent = g.name || g.code || "Group"; // server `name` is the label
      section.appendChild(h);

      var grid = document.createElement("div");
      grid.className = "cli-tools";

      (g.tools || []).forEach(function (tool) {
        // Cell = launch button + compatibility badges + optional warning.
        var cell = document.createElement("div");
        cell.className = "cli-tool-cell";

        var card = document.createElement("button");
        card.type = "button";
        card.className = "btn cli-tool";
        card.textContent = tool.name;
        if (tool.enabled === false) card.classList.add("cli-tool-disabled");
        // Struck through = NOT launchable yet: either no verified launch command
        // (pending) or a wire format the gateway does not serve (unsupported).
        // The strike is deliberate — the tool stays visible as the to-do list —
        // but the card never opens the modal, so no guessed command is run.
        // Fail CLOSED on a missing mode (an old server that never sends the
        // field must not be treated as "everything is verified").
        var launchable = tool.launch_mode === "verified";
        if (!launchable) {
          card.classList.add("cli-tool-unsupported");
          card.setAttribute("aria-disabled", "true");
        }
        card.title = launchable
          ? (tool.binary_name || tool.name)
          : unsupportedNote(tool);
        card.addEventListener("click", function () {
          if (!launchable) { setCliMsg(unsupportedNote(tool), "warn"); return; }
          openLaunchModal(g, tool);
        });
        cell.appendChild(card);

        // Per-platform compatibility badges (current platform highlighted).
        cell.appendChild(renderCompatStrip(tool, currentPlatform));

        // Red warning when the tool is not usable on the current platform.
        var warn = renderCompatWarn(tool, currentPlatform);
        if (warn) cell.appendChild(warn);

        grid.appendChild(cell);
      });

      section.appendChild(grid);
      wrap.appendChild(section);
    });
  }

  /* ---------------------------------------------------------------
   * Launch modal: model picker + Launch/Cancel
   * --------------------------------------------------------------- */
  function fetchModels() {
    var sel = el("cliModel");
    if (!sel) return Promise.resolve([]);
    return fetchJson(MODELS_API).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      var c = cliModelCtl();
      var comboCombo = comboGroupName(); // localized: "Combos" (EN) / "Kombo" (ID)
      if (c && typeof c.setGroupOrder === "function") c.setGroupOrder([comboCombo]);
      var opts = list.map(function (m) {
        var id = m.id != null ? m.id : "";
        if (id.indexOf("combo:") === 0) {
          // Combo models stay FLAT under the combo group: explicitly opt out of
          // sub-grouping so they render directly under the main header.
          return { value: id, label: id.slice("combo:".length), group: comboCombo, subGroup: false };
        }
        // provider entry: value = full id (e.g. provider:deepseek:deepseek-v1),
        // label = human model portion after the last ":". The sub-group (_sub)
        // is auto-derived from the label prefix by the combobox (subGroupBy:"prefix").
        return { value: id, label: id.split(":").pop(), group: m.owned_by || "unknown" };
      });
      // Sort by label (case-insensitive) before handing to the combobox.
      opts.sort(function (a, b) {
        var al = a.label.toLowerCase(), bl = b.label.toLowerCase();
        return al < bl ? -1 : al > bl ? 1 : 0;
      });
      if (c) c.setOptions(opts);
      // Preselect the first model so launch() always has a default (mirrors the
      // old <select>'s first-option behavior); value is the full id.
      if (c && opts.length) c.setValue(opts[0].value);
      if (!list.length) {
        setCliModalMsg(getStr("cli.no_models"), "warn");
      } else {
        setCliModalMsg("");
      }
      return list;
    }).catch(function () {
      var c = cliModelCtl();
      if (c) c.setOptions([]); // combobox shows its own no_match row
      setCliModalMsg(getStr("cli.no_models"), "error");
      return [];
    });
  }

  function openLaunchModal(group, tool) {
    currentTool = tool;
    var hint = el("cliHint");
    if (hint) hint.hidden = true;
    setCliModalMsg("");
    fetchModels().then(function () {
      showModal("cliLaunchModal");
    });
  }

  function setCliModalMsg(text, kind) {
    var m = el("cliMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function launch() {
    if (!currentTool) return;
    var modelSel = el("cliModel");
    var model = modelSel ? modelSel.value : null;

    setCliModalMsg(getStr("cli.launching"), "");
    fetchJson(CLI_API + "/resolve", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ tool: currentTool.name, model: model || undefined })
    }).then(function (dto) {
      // The emitted command self-decides (PTY-side `command -v`), so we must
      // NOT claim "installing" — the tool may already be installed and simply
      // launch. Neutral hint; `binary_found` is only a server-side PATH hint.
      var hint = el("cliHint");
      if (hint) {
        hint.hidden = false;
        hint.textContent = getStr("cli.launching_or_installing");
      }
      var command = window.aigate.buildLaunchCommand(dto);
      // Reuse B3.3 terminal manager: open a NEW tab and run the command.
      if (window.aigate && window.aigate.terminalManager &&
          typeof window.aigate.terminalManager.launchInNewTab === "function") {
        window.aigate.terminalManager.launchInNewTab(command);
        // Bring the user to the terminal view so the new tab is visible.
        var termNav = document.querySelector('.nav-item[data-view="terminal"]');
        if (termNav) termNav.click();
      } else {
        setCliModalMsg(getStr("cli.term_unavailable"), "error");
      }
      hideModal("cliLaunchModal");
    }).catch(function (err) {
      // 404 (tool_not_found) or other -> graceful error in the modal.
      setCliModalMsg(err.message || getStr("cli.error"), "error");
    });
  }

  function cancelLaunch() {
    currentTool = null;
    hideModal("cliLaunchModal");
  }

  /* ---------------------------------------------------------------
   * Wire up modal + expose hook for app.js nav handler
   * --------------------------------------------------------------- */
  function init() {
    var launchBtn = el("cliLaunchBtn");
    if (launchBtn) launchBtn.addEventListener("click", launch);
    var cancelBtn = el("cliCancelBtn");
    if (cancelBtn) cancelBtn.addEventListener("click", cancelLaunch);
    var modal = el("cliLaunchModal");
    if (modal) modal.addEventListener("click", function (e) {
      if (e.target === modal) cancelLaunch(); // backdrop closes
    });
  }

  window.aigate.cliTools = {
    onShow: loadCliTools,
    buildLaunchCommand: buildLaunchCommand,
    loadCliTools: loadCliTools,
    _test: { renderGroups: renderGroups, comboGroupName: comboGroupName }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
