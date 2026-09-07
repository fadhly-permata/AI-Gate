/* ===== aigate Self-Heal UI (B4.1) — vanilla JS, no build ===== */
/* Spec: FSD §2.8 / PRD §2.8 Self-Heal (menu CLI-Tool).
   Pure helpers (renderSelfHealStatus, renderAgenticCheck) are importable +
   testable via vitest (no DOM). DOM logic checks the agentic CLI on load,
   pops up when none, runs the heal and renders merged / partial / error. */

(function () {
  "use strict";

  /* ---------------------------------------------------------------
   * i18n helper (mirrors app.js / clitools.js)
   * --------------------------------------------------------------- */
  function currentLoc() {
    return (typeof document !== "undefined" &&
            document.documentElement.getAttribute("data-locale")) || "en";
  }

  function t(key, loc) {
    loc = loc || currentLoc();
    var d = (window.I18N && window.I18N[loc]) || (window.I18N && window.I18N.en) || {};
    if (d[key] !== undefined) return d[key];
    var en = window.I18N && window.I18N.en;
    return en && en[key] !== undefined ? en[key] : key;
  }

  // Replace {n} / {cli} placeholders in a template string.
  function fill(tpl, vars) {
    return String(tpl).replace(/\{(\w+)\}/g, function (_, k) {
      return vars && vars[k] != null ? String(vars[k]) : "";
    });
  }

  /* ===============================================================
   * PURE HELPER — agentic CLI check (GET /api/self-heal/agentic-cli)
   * @param {object|null} result - { available:bool, cli:str|null }
   * @param {string} [loc] - locale ("en" | "id")
   * @returns {{available:boolean, cli:?string, message:string}}
   * =============================================================== */
  function renderAgenticCheck(result, loc) {
    if (!result || result.available === false) {
      return {
        available: false,
        cli: null,
        message: t("selfheal.no_cli", loc)
      };
    }
    return {
      available: true,
      cli: result.cli != null ? result.cli : null,
      message: fill(t("selfheal.cli_found", loc), { cli: result.cli != null ? result.cli : "" })
    };
  }

  /* ===============================================================
   * PURE HELPER — run result (POST /api/self-heal/run)
   * @param {object} result
   *   network failure:   { _networkError:true }
   *   no agentic CLI:    { ok:false, reason:"no_agentic_cli" }
   *   git failure:       { ok:false, reason:"git_failed", detail:str }
   *   merged:            { ok:true, merged:true, iterations:int }
   *   partial:           { ok:true, merged:false, remaining:int }
   *   unexpected 500:    { error:{ message:str, type:"internal",
   *                                code:"self_heal_failed" } }
   * @param {string} [loc] - locale
   * @returns {{kind:string, message:string}} kind: ok|warn|error|info
   * =============================================================== */
  function renderSelfHealStatus(result, loc) {
    if (!result) {
      return { kind: "error", message: t("selfheal.error_generic", loc) };
    }
    if (result._networkError) {
      return { kind: "error", message: t("selfheal.error_generic", loc) };
    }
    if (result.ok === false) {
      if (result.reason === "no_agentic_cli") {
        return { kind: "error", message: t("selfheal.no_cli", loc) };
      }
      if (result.reason === "git_failed") {
        var detail = result.detail != null ? " (" + result.detail + ")" : "";
        return { kind: "error", message: t("selfheal.git_failed", loc) + detail };
      }
      // unexpected error envelope
      var msg = (result.error && result.error.message)
        ? result.error.message
        : t("selfheal.error_generic", loc);
      return { kind: "error", message: msg };
    }
    // ok === true
    if (result.ok === true) {
      if (result.merged === true) {
        return {
          kind: "ok",
          message: fill(t("selfheal.merged", loc), {
            n: result.iterations != null ? result.iterations : "?"
          })
        };
      }
      if (result.merged === false) {
        return {
          kind: "warn",
          message: fill(t("selfheal.partial", loc), {
            n: result.remaining != null ? result.remaining : "?"
          })
        };
      }
      return { kind: "info", message: t("selfheal.merged", loc) };
    }
    // Neither ok:true nor ok:false (e.g. an unexpected 500 envelope).
    if (result.error && result.error.message) {
      return { kind: "error", message: result.error.message };
    }
    return { kind: "info", message: t("selfheal.merged", loc) };
  }

  /* Expose pure helpers on the shared namespace (testable). */
  window.aigate = window.aigate || {};
  window.aigate.renderSelfHealStatus = renderSelfHealStatus;
  window.aigate.renderAgenticCheck = renderAgenticCheck;

  /* ---------------------------------------------------------------
   * fetch JSON (mirrors app.js / clitools.js error shape)
   * --------------------------------------------------------------- */
  var SELF_HEAL_API = "/api/self-heal";

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
   * DOM refs + rendering
   * --------------------------------------------------------------- */
  function el(id) { return document.getElementById(id); }

  function setCheckMsg(text, kind) {
    var m = el("selfHealCheckMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function setResult(text, kind) {
    var r = el("selfHealResult");
    if (!r) return;
    r.textContent = text || "";
    r.className = "selfheal-result" + (kind ? " selfheal-result-" + kind : "");
  }

  function setRunEnabled(on) {
    var b = el("selfHealRunBtn");
    if (b) b.disabled = !on;
  }

  function showPopup(message) {
    var overlay = el("selfHealModal");
    var msg = el("selfHealModalMsg");
    if (!overlay || !msg) {
      // No modal in DOM — degrade to the check message + status area.
      setCheckMsg(message, "error");
      setResult(message, "error");
      return;
    }
    msg.textContent = message;
    overlay.hidden = false;
  }

  function hidePopup() {
    var overlay = el("selfHealModal");
    if (overlay) overlay.hidden = true;
  }

  var agenticCliAvailable = false;
  var agenticCliName = null;

  /* GET /api/self-heal/agentic-cli — run on view load + manual Check */
  function checkAgenticCli() {
    setCheckMsg(t("selfheal.checking"), "");
    setRunEnabled(false);
    fetchJson(SELF_HEAL_API + "/agentic-cli").then(function (data) {
      var view = renderAgenticCheck(data || {}, currentLoc());
      agenticCliAvailable = view.available;
      agenticCliName = view.cli;
      if (view.available) {
        setCheckMsg(view.message, "ok");
        setRunEnabled(true);
      } else {
        setCheckMsg(view.message, "error");
        setRunEnabled(false);
        showPopup(view.message);
      }
    }).catch(function (err) {
      agenticCliAvailable = false;
      setRunEnabled(false);
      setCheckMsg(t("selfheal.error_generic") + " (" + err.message + ")", "error");
    });
  }

  /* POST /api/self-heal/run is ASYNC: the agentic CLI runs in a live PTY
     registered under the tab key "self-heal" (watch it in the terminal view),
     while the final result lands on GET /api/self-heal/status (status.last). */
  var STATUS_POLL_MS = 5000;   // status polling cadence while a run is active
  var SELF_HEAL_TAB = "self-heal"; // backend PTY tab key for the run terminal

  /* Open (or focus) the terminal tab bound to the backend's "self-heal" PTY
     key and switch to the terminal view (clitools.js launch precedent).
     openTab may fire before the backend session exists — fine: the server
     spawns a plain shell for that key and types the CLI command into it.
     Best-effort: without the terminal manager the result area stays as-is. */
  function openSelfHealTab() {
    var tm = window.aigate && window.aigate.terminalManager;
    if (!tm || typeof tm.openTab !== "function") return;
    try { tm.openTab(SELF_HEAL_TAB); } catch (e) { return; }
    var termNav = document.querySelector('.nav-item[data-view="terminal"]');
    if (termNav) termNav.click();
  }

  /* Shared status poller. One fetch + one interval handle at a time; a new
     runSelfHeal() (e.g. the 409 path) restarts it instead of stacking. */
  var statusPollTimer = null;

  function stopStatusPolling() {
    if (statusPollTimer !== null) {
      clearInterval(statusPollTimer);
      statusPollTimer = null;
    }
  }

  function pollStatusOnce() {
    fetchJson(SELF_HEAL_API + "/status").then(function (data) {
      data = data || {};
      if (data.running === true || !data.last) return; // still running (or no result yet)
      stopStatusPolling();
      var view = renderSelfHealStatus(data.last, currentLoc());
      setResult(view.message, view.kind);
      // Keep run enabled only if a CLI is still present (partial keeps it usable).
      setRunEnabled(view.kind !== "ok");
    }).catch(function (err) {
      // A missed poll must never crash the page: surface once in the result
      // area and keep polling — the run may still finish and self-report.
      setResult(t("selfheal.status") + ": " + err.message, "warn");
    });
  }

  function startStatusPolling() {
    stopStatusPolling();
    pollStatusOnce();                    // catch a fast no_agentic_cli abort
    statusPollTimer = setInterval(pollStatusOnce, STATUS_POLL_MS);
  }

  function runSelfHeal() {
    if (!agenticCliAvailable) {
      var msg = t("selfheal.no_cli");
      setCheckMsg(msg, "error");
      showPopup(msg);
      return;
    }
    setResult(t("selfheal.running"), "info");
    setRunEnabled(false);
    fetchJson(SELF_HEAL_API + "/run", { method: "POST" }).then(function (data) {
      data = data || {};
      if (data.started === true) {
        setResult(t("selfheal.started"), "info");
        openSelfHealTab();
        startStatusPolling();
        return;                        // final result arrives via status.last
      }
      // Unexpected 2xx envelope (e.g. a legacy sync body) -> error render.
      var view = renderSelfHealStatus(data, currentLoc());
      setResult(view.message, view.kind);
      setRunEnabled(view.kind !== "ok");
    }).catch(function (err) {
      if (err && err.status === 409) {
        // already_running: fetchJson throws on non-2xx (body carries no error
        // envelope), so the reason rides on the status. Still open the tab.
        setResult(t("selfheal.already_running"), "warn");
        openSelfHealTab();
        startStatusPolling();
        return;
      }
      var view = renderSelfHealStatus({ _networkError: true }, currentLoc());
      setResult(view.message + " (" + err.message + ")", "error");
      setRunEnabled(true);
    });
  }

  function init() {
    var checkBtn = el("selfHealCheckBtn");
    if (checkBtn) checkBtn.addEventListener("click", checkAgenticCli);
    var runBtn = el("selfHealRunBtn");
    if (runBtn) runBtn.addEventListener("click", runSelfHeal);
    var okBtn = el("selfHealModalOk");
    if (okBtn) okBtn.addEventListener("click", hidePopup);
    var overlay = el("selfHealModal");
    if (overlay) overlay.addEventListener("click", function (e) {
      if (e.target === overlay) hidePopup(); // backdrop closes
    });
  }

  window.aigate.selfHeal = {
    onShow: checkAgenticCli,
    checkAgenticCli: checkAgenticCli,
    runSelfHeal: runSelfHeal,
    _test: {
      renderSelfHealStatus: renderSelfHealStatus,
      renderAgenticCheck: renderAgenticCheck,
      pollStatusOnce: pollStatusOnce,
      startStatusPolling: startStatusPolling,
      stopStatusPolling: stopStatusPolling,
      _STATUS_POLL_MS: STATUS_POLL_MS
    }
  };

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", init);
    } else {
      init();
    }
  }
})();
