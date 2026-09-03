/* ===== aigate Terminal (B3.3) — vanilla JS, no build ===== */
/* Spec: FSD §2.5 / §2.5.0 / §2.5.1, PRD §2.5/§2.5.1.
   Integrates the PTY WebSocket backend (B3.2). xterm.js + FitAddon are loaded
   via CDN <script> tags (see index.html), exposed as window.Terminal /
   window.FitAddon. This file references them ONLY inside methods, so importing
   it in a jsdom test env (no xterm) is safe — pure helpers stay testable. */

(function () {
  "use strict";

  /* ---------------------------------------------------------------
   * PURE HELPERS (importable + testable via vitest)
   * --------------------------------------------------------------- */

  // Build the PTY WebSocket URL for a given tab id.
  // Scheme follows the page (wss on https, ws otherwise); same origin.
  function buildTerminalWsUrl(tabId) {
    var proto = location.protocol === "https:" ? "wss" : "ws";
    return proto + "://" + location.host + "/ws/terminal/" + encodeURIComponent(tabId);
  }

  // Short display title for a tab from its (uuid) id.
  function tabTitle(id) {
    if (!id) return "term";
    return String(id).slice(0, 8);
  }

  // JSON resize control frame (sent to backend, NOT written to the terminal).
  function buildResizeFrame(cols, rows) {
    return JSON.stringify({ type: "resize", cols: cols, rows: rows });
  }

  /* Map a swipe velocity (px/ms, vertical; negative = upward) to a terminal
     scroll delta in lines.
       - sign is preserved (up swipe -> negative lines -> scroll toward top)
       - small swipes still move >= minLines (line-by-line feel)
       - large swipes get a soft-saturating (tanh) gain so extra speed yields
         diminishing extra lines -> natural easing / damping
       - atEdge multiplies magnitude down (extra damping near buffer ends)
     Pure: no DOM, no xterm. */
  function swipeToScrollDelta(velocityY, opts) {
    opts = opts || {};
    var gain = opts.gain != null ? opts.gain : 1.4;          // lines per (px/ms)
    var minLines = opts.minLines != null ? opts.minLines : 1;
    var maxLines = opts.maxLines != null ? opts.maxLines : 60;
    var knee = opts.knee != null ? opts.knee : 4;            // soft-saturation knee
    var edgeDamp = opts.edgeDamp != null ? opts.edgeDamp : 0.35;
    var atEdge = !!opts.atEdge;

    var v = Number(velocityY) || 0;
    if (v === 0) return 0;

    var av = Math.abs(v);
    // Soft-saturating magnitude: grows linearly then compresses (easing).
    var mag = gain * (knee * Math.tanh(av / knee));
    if (mag < minLines) mag = minLines;
    if (mag > maxLines) mag = maxLines;
    if (atEdge) mag *= edgeDamp;

    return Math.round((v < 0 ? -1 : 1) * mag);
  }

  /* ---------------------------------------------------------------
   * i18n helper (mirrors app.js getStr)
   * --------------------------------------------------------------- */
  function t(key) {
    var loc = document.documentElement.getAttribute("data-locale") || "en";
    var dict = (window.I18N && window.I18N[loc]) || (window.I18N && window.I18N.en) || {};
    if (dict[key] !== undefined) return dict[key];
    if (window.I18N && window.I18N.en && window.I18N.en[key] !== undefined) return window.I18N.en[key];
    return key;
  }

  function debounce(fn, ms) {
    var timer = null;
    return function () {
      var ctx = this, args = arguments;
      if (timer) clearTimeout(timer);
      timer = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  // xterm color theme (terminal is always dark; fg follows app theme).
  function currentXtermTheme() {
    var dark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      background: "#1e1e1e",
      foreground: dark ? "#e4e6eb" : "#f4f6f9",
      cursor: dark ? "#e4e6eb" : "#f4f6f9",
      selectionBackground: "#375a7f",
      black: "#1e1e1e", white: "#d4d4d4", brightBlack: "#666"
    };
  }

  /* ---------------------------------------------------------------
   * Terminal manager (multi-tab)
   * --------------------------------------------------------------- */
  var tabs = new Map();      // id -> { id, term, fit, ws, container, button, tuiMode }
  var activeId = null;
  var tabBarEl, containersEl, stageEl, bodyEl, newTabBtn;

  function activeTab() { return activeId ? tabs.get(activeId) : null; }

  // Is the active terminal scroll position at a buffer edge? (for damping)
  function atEdge(term) {
    try {
      var buf = term.buffer.active;
      var vY = buf.viewportY;
      var rows = term.rows;
      var len = buf.length;
      if (vY <= 0) return true;
      if (vY + rows >= len) return true;
    } catch (e) { /* ignore */ }
    return false;
  }

  function sendResize(tab) {
    if (!tab || !tab.term || !tab.ws) return;
    var frame = buildResizeFrame(tab.term.cols, tab.term.rows);
    if (tab.ws.readyState === WebSocket.OPEN) {
      tab.ws.send(frame);
    } else {
      tab.ws.addEventListener("open", function () {
        if (tab.ws.readyState === WebSocket.OPEN) tab.ws.send(frame);
      }, { once: true });
    }
  }

  function createTabButton(tab) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "term-tab";
    btn.setAttribute("role", "tab");
    btn.dataset.tabId = tab.id;

    var label = document.createElement("span");
    label.className = "term-tab-label";
    label.textContent = tabTitle(tab.id);

    var close = document.createElement("span");
    close.className = "term-tab-close";
    close.innerHTML = "&times;";
    close.title = t("term.close_tab");

    btn.appendChild(label);
    btn.appendChild(close);

    btn.addEventListener("click", function (e) {
      if (e.target === close) return;
      activate(tab.id);
    });
    close.addEventListener("click", function (e) {
      e.stopPropagation();
      closeTab(tab.id);
    });

    tab.button = btn;
    tabBarEl.insertBefore(btn, newTabBtn);
  }

  function openTab() {
    if (!tabBarEl || !containersEl) return null;

    var id = (window.crypto && crypto.randomUUID)
      ? crypto.randomUUID()
      : "tab-" + Math.random().toString(36).slice(2);

    var container = document.createElement("div");
    container.className = "term-tab-container";
    container.dataset.tabId = id;
    containersEl.appendChild(container);

    var term = new window.Terminal({
      fontFamily: 'Menlo, Consolas, "DejaVu Sans Mono", monospace',
      fontSize: 13,
      theme: currentXtermTheme(),
      cursorBlink: true,
      scrollback: 5000
    });
    var fit = new window.FitAddon.FitAddon();
    term.loadAddon(fit);
    term.open(container);
    fit.fit();

    var ws = new WebSocket(buildTerminalWsUrl(id));
    var tab = { id: id, term: term, fit: fit, ws: ws, container: container, tuiMode: false };
    tabs.set(id, tab);

    term.write("\x1b[2m" + t("term.connecting") + "\x1b[0m\r\n");

    term.onData(function (d) {
      if (ws.readyState === WebSocket.OPEN) ws.send(d);
    });
    ws.onmessage = function (ev) {
      // TEXT frame = terminal output (or JSON resize ack — backend only sends
      // raw output here; we still guard against accidentally echoing control).
      if (typeof ev.data === "string" && ev.data.charAt(0) === "{") return;
      term.write(ev.data);
    };
    ws.onopen = function () { sendResize(tab); };
    ws.onclose = function () {
      term.write("\r\n\x1b[33m" + t("term.disconnected") + "\x1b[0m\r\n");
    };
    ws.onerror = function () { /* surface via onclose */ };

    createTabButton(tab);
    activate(id);
    return tab;
  }

  /* Launch a command into a NEW terminal tab (B3.4 CLI launcher).
     Creates a tab (reuses openTab), then sends `command` to the shell once
     the WebSocket is open, and brings focus to that tab. Returns the tab id. */
  function launchInNewTab(command) {
    if (!tabBarEl || !containersEl) return null;
    var tab = openTab();
    if (!tab) return null;
    var ws = tab.ws;
    var send = function () {
      try {
        // Simulate typing + Enter so the shell executes the command.
        // Multi-line command (env exports) has embedded \n -> line breaks.
        ws.send(String(command) + "\n");
      } catch (e) { /* ws not ready — ignore */ }
    };
    if (ws && ws.readyState === WebSocket.OPEN) send();
    else if (ws) ws.addEventListener("open", function () { send(); }, { once: true });
    activate(tab.id);
    return tab.id;
  }

  function activate(id) {
    if (!tabs.has(id)) return;
    activeId = id;
    tabs.forEach(function (tab) {
      var show = tab.id === id;
      if (tab.container) tab.container.style.display = show ? "block" : "none";
      if (tab.button) tab.button.classList.toggle("active", show);
    });
    refitActive();
    var tab = tabs.get(id);
    if (tab) { try { tab.term.focus(); } catch (e) {} }
  }

  function refitActive() {
    var tab = activeTab();
    if (!tab) return;
    try {
      tab.fit.fit();
      sendResize(tab);
      tab.term.focus();
    } catch (e) { /* xterm not laid out yet */ }
  }

  function closeTab(id) {
    var tab = tabs.get(id);
    if (!tab) return;
    try { tab.ws.close(); } catch (e) {}
    try { tab.term.dispose(); } catch (e) {}
    if (tab.button && tab.button.remove) tab.button.remove();
    if (tab.container && tab.container.remove) tab.container.remove();
    tabs.delete(id);

    if (activeId === id) {
      var it = tabs.keys().next();
      if (!it.done) activate(it.value);
      else { activeId = null; openTab(); } // keep at least one tab alive
    }
  }

  /* ---- Floating control ---- */
  function toggleFullscreen() {
    if (!bodyEl) return;
    var on = bodyEl.classList.toggle("terminal-fullscreen");
    var btn = document.getElementById("termFullscreen");
    if (btn) {
      var icon = btn.querySelector("i");
      if (icon) icon.className = on ? "fa fa-compress" : "fa fa-expand";
      btn.title = t(on ? "term.exit_fullscreen" : "term.fullscreen");
      btn.setAttribute("aria-label", btn.title);
    }
    // Refit after the layout change settles.
    requestAnimationFrame(function () { refitActive(); });
  }

  function pasteActive() {
    var tab = activeTab();
    if (!tab) return;
    if (navigator.clipboard && navigator.clipboard.readText) {
      navigator.clipboard.readText().then(function (text) {
        if (text) tab.term.paste(text);
        tab.term.focus(); // PRD §2.5: return focus to the active terminal
      }).catch(function () { tab.term.focus(); });
    } else {
      tab.term.focus();
    }
  }

  function toggleTui() {
    var tab = activeTab();
    if (!tab) return;
    tab.tuiMode = !tab.tuiMode;
    var btn = document.getElementById("termTui");
    if (btn) {
      btn.setAttribute("aria-pressed", tab.tuiMode ? "true" : "false");
      btn.title = t(tab.tuiMode ? "term.tui_on" : "term.tui_off");
      btn.setAttribute("aria-label", btn.title);
    }
  }

  /* ---- Scroll & swipe (FSD §2.5.1) ---- */
  var SWIPE_THRESHOLD = 10; // px before a gesture is treated as a swipe
  var ptr = { active: false, lastX: 0, lastY: 0, lastT: 0, vy: 0, moved: 0, isSwipe: false };

  function setupSwipe() {
    var target = stageEl || bodyEl;
    if (!target) return;

    target.addEventListener("pointerdown", function (e) {
      ptr.active = true;
      ptr.lastX = e.clientX; ptr.lastY = e.clientY;
      ptr.lastT = (typeof performance !== "undefined" ? performance.now() : Date.now());
      ptr.vy = 0; ptr.moved = 0; ptr.isSwipe = false;
    });

    // Listen on window so we keep tracking outside the element bounds.
    window.addEventListener("pointermove", function (e) {
      if (!ptr.active) return;
      var tab = activeTab();
      if (!tab) return;
      var now = (typeof performance !== "undefined" ? performance.now() : Date.now());
      var dt = now - ptr.lastT;
      if (dt <= 0) return;
      var dy = e.clientY - ptr.lastY;
      ptr.moved += Math.abs(dy) + Math.abs(e.clientX - ptr.lastX);
      ptr.vy = dy / dt;

      if (!ptr.isSwipe && ptr.moved > SWIPE_THRESHOLD) ptr.isSwipe = true;

      // TUI mode ON => let the app handle its own gestures (whitelist stand-in).
      if (ptr.isSwipe && !tab.tuiMode) {
        e.preventDefault();
        e.stopPropagation();
        var delta = swipeToScrollDelta(ptr.vy, { atEdge: atEdge(tab.term) });
        if (delta) tab.term.scrollLines(delta);
      }
      ptr.lastX = e.clientX; ptr.lastY = e.clientY; ptr.lastT = now;
    });

    window.addEventListener("pointerup", function () {
      if (!ptr.active) return;
      var tab = activeTab();
      ptr.active = false;
      if (ptr.isSwipe && tab && !tab.tuiMode && Math.abs(ptr.vy) > 0.05) {
        // Momentum: one last scroll from the release velocity.
        var delta = swipeToScrollDelta(ptr.vy, { atEdge: atEdge(tab.term) });
        if (delta) tab.term.scrollLines(delta);
      }
      ptr.isSwipe = false;
    });
  }

  function init() {
    tabBarEl = document.getElementById("termTabBar");
    containersEl = document.getElementById("termContainers");
    stageEl = document.getElementById("termStage");
    bodyEl = document.getElementById("terminalBody");
    newTabBtn = document.getElementById("termNewTab");
    if (!tabBarEl || !containersEl) return; // not on this page / test env

    if (newTabBtn) newTabBtn.addEventListener("click", openTab);
    var fs = document.getElementById("termFullscreen");
    if (fs) fs.addEventListener("click", toggleFullscreen);
    var pst = document.getElementById("termPaste");
    if (pst) pst.addEventListener("click", pasteActive);
    var tui = document.getElementById("termTui");
    if (tui) tui.addEventListener("click", toggleTui);

    setupSwipe();
    window.addEventListener("resize", debounce(refitActive, 120));

    // Keep xterm themes in sync with the global theme toggle.
    if (typeof MutationObserver !== "undefined") {
      var obs = new MutationObserver(function (muts) {
        muts.forEach(function (m) {
          if (m.attributeName === "data-theme") {
            var th = currentXtermTheme();
            tabs.forEach(function (tab) {
              try { tab.term.options.theme = th; } catch (e) {}
            });
          }
        });
      });
      obs.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    }
  }

  /* Expose pure helpers + a manager hook for app.js / tests. */
  window.aigate = window.aigate || {};
  window.aigate.terminal = {
    swipeToScrollDelta: swipeToScrollDelta,
    buildTerminalWsUrl: buildTerminalWsUrl,
    tabTitle: tabTitle,
    buildResizeFrame: buildResizeFrame,
    // manager hooks (used by app.js nav handler):
    onShow: function () {
      if (!activeId) openTab();
      else refitActive();
    },
    openTab: openTab,
    closeTab: closeTab,
    activate: activate,
    refitActive: refitActive,
    launchInNewTab: launchInNewTab
  };
  // Convenience alias for app.js.
  window.aigate.terminalManager = window.aigate.terminal;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
