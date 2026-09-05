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
      renderGroups(list);
      setCliMsg("");
    }).catch(function (err) {
      setCliMsg(getStr("cli.load_error") + " (" + err.message + ")", "error");
    });
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

  function renderGroups(groups) {
    var wrap = el("cliGroups");
    if (!wrap) return;
    if (!groups.length) {
      wrap.innerHTML = '<p class="empty-cell">' + escapeHtml(getStr("cli.no_tools")) + "</p>";
      return;
    }
    wrap.innerHTML = "";
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
        grid.appendChild(card);
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
      sel.innerHTML = list.map(function (m) {
        var id = m.id != null ? m.id : "";
        return '<option value="' + escapeHtml(id) + '">' + escapeHtml(id) + "</option>";
      }).join("");
      if (!list.length) {
        sel.innerHTML = '<option value="">' + escapeHtml(getStr("cli.no_models")) + "</option>";
      }
      return list;
    }).catch(function () {
      sel.innerHTML = '<option value="">' + escapeHtml(getStr("cli.no_models")) + "</option>";
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
    _test: { renderGroups: renderGroups }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
