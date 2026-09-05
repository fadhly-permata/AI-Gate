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

  // JSON close control frame. This is the ONLY thing that tells the backend to
  // KILL the PTY. Sent on a DELIBERATE tab close (the X button), never on a
  // transient WS drop — so a minimized/backgrounded tab keeps its shell running.
  function buildCloseFrame() {
    return JSON.stringify({ type: "close" });
  }

  // JSON pong control frame. Sent back over the SAME socket in reply to a
  // server heartbeat {"type":"ping"} so the backend knows the client is alive.
  function buildPongFrame() {
    return JSON.stringify({ type: "pong" });
  }

  /* Classify an incoming WS TEXT frame as PTY output vs. a JSON control frame.
     Cheap + guarded: we only attempt JSON.parse when the frame starts with "{"
     AND contains the substring `"type"` — so ordinary PTY output (even output
     that happens to begin with "{") is never parsed, and a malformed JSON-ish
     chunk falls through as PTY output rather than being swallowed.
     Returns { kind: "pty" } or { kind: "control", type }. Pure: no DOM/xterm. */
  function classifyIncoming(data) {
    if (typeof data === "string" && data.charAt(0) === "{" && data.indexOf('"type"') !== -1) {
      var obj;
      try { obj = JSON.parse(data); } catch (e) { return { kind: "pty" }; }
      if (obj && typeof obj === "object" && typeof obj.type === "string") {
        return { kind: "control", type: obj.type };
      }
      return { kind: "pty" };
    }
    return { kind: "pty" };
  }

  /* Exponential backoff delay (ms) for reconnect attempt N (0-indexed).
     0.5s, 1s, 2s, 4s, 8s, then capped at ~15s. Pure + testable. */
  function computeBackoffDelay(attempt, opts) {
    opts = opts || {};
    var base = opts.base != null ? opts.base : 500;
    var factor = opts.factor != null ? opts.factor : 2;
    var cap = opts.cap != null ? opts.cap : 15000;
    var n = Number(attempt) || 0;
    if (n < 0) n = 0;
    var d = base * Math.pow(factor, n);
    if (d > cap) d = cap;
    return d;
  }

  /* Map a touch-drag delta (CSS px, finger DOWN is positive) to the `deltaY`
     of the wheel event we synthesise for xterm.
       - sign is INVERTED: dragging a finger up reveals newer content, the same
         convention xterm's own touch/wheel handling uses (native mobile scroll)
       - 1:1 pixel tracking (no velocity curve) so the buffer sticks to the
         finger; velocity only matters for the release momentum
       - clamped per event: a stalled frame (huge dt) must not launch the buffer
      Pure: no DOM, no xterm. */
  function swipeWheelDelta(dy, opts) {
    opts = opts || {};
    var sens = Number(opts.sensitivity) || 1;
    var cap = opts.maxStep != null ? opts.maxStep : 120;
    var v = -(Number(dy) || 0) * sens;
    if (!isFinite(v)) return 0;
    if (v > cap) v = cap;
    else if (v < -cap) v = -cap;
    return Math.round(v) || 0; // `|| 0` also normalises -0
  }

  /* Exponential moving average of the finger velocity (px/ms). Raw per-frame
     velocity is noisy on mobile (jittery dt), so blend: new = prev*(1-w)+raw*w.
     Pure + testable. */
  function blendVelocity(prev, raw, weight) {
    var w = weight != null ? Number(weight) : 0.35;
    return (Number(prev) || 0) * (1 - w) + (Number(raw) || 0) * w;
  }

  /* One inertia frame: friction-decay a velocity (px/ms). `friction` is the
     retention factor per 16ms, so the decay is frame-rate independent. Returns
     0 once the gesture is slow enough to stop. Pure + testable. */
  function decayVelocity(vy, dt, opts) {
    opts = opts || {};
    var friction = opts.friction != null ? Number(opts.friction) : 0.9;
    var min = opts.min != null ? Number(opts.min) : 0.03;
    var v = Number(vy) || 0;
    if (Math.abs(v) < min) return 0;
    var frames = (Number(dt) || 0) / 16;
    if (frames <= 0) return v;
    v *= Math.pow(friction, frames);
    return Math.abs(v) < min ? 0 : v;
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
  var emptyEl = null;        // centered hint shown while no tab exists
  var emptyNewTabBtn = null; // the hint's own "New Tab" affordance
  var stageResizeObs = null; // BUG2: ResizeObserver on the shared .term-stage
  var debouncedRefit = null;  // BUG2: debounced refitActive() for resize storms

  function activeTab() { return activeId ? tabs.get(activeId) : null; }

  /* Empty state (redesign): the panel shows a centered hint instead of a blank
     surface whenever no tab exists (i.e. before the first session opens). Pure
     DOM toggle, guarded so it is a no-op in test fixtures without the element. */
  function updateEmptyState() {
    if (!emptyEl) return;
    emptyEl.hidden = tabs.size > 0;
  }

  // Is the active terminal scroll position at a buffer edge? (inertia damping)
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

  // Monotonic-ish clock for gesture timing (performance.now when available).
  function nowMs() {
    return (typeof performance !== "undefined" && performance.now)
      ? performance.now() : Date.now();
  }

  /* Alternate buffer == a full-screen app is running (TUI: vim, htop, less,
     opencode...). That buffer has NO scrollback, so term.scrollLines() is a
     no-op there — the gesture has to be translated instead (see emitWheel). */
  function isAltScreen(tab) {
    try {
      return !!(tab && tab.term && tab.term.buffer && tab.term.buffer.active &&
        tab.term.buffer.active.type === "alternate");
    } catch (e) { return false; }
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

  /* ---- Reconnect / reattach (backend PTY now survives WS drops) ----
   * A tab's WebSocket may close because Chrome froze a minimized/backgrounded
   * tab. The backend keeps the PTY alive + buffers output, so we reconnect to
   * the SAME tab_id (reattach + replay) with exponential backoff. We only send
   * the {"type":"close"} kill frame when the user DELIBERATELY closes a tab. */

  // Write a dim status line into the terminal (ADR-011 surface status/errors).
  function writeStatus(tab, text) {
    if (!tab || !tab.term) return;
    try { tab.term.write("\r\n\x1b[2m" + text + "\x1b[0m\r\n"); } catch (e) {}
  }

  // Schedule a reconnect for a tab (unless it was deliberately closed).
  function scheduleReconnect(tab, immediate) {
    if (!tab || tab.userClosed) return;
    if (tab.reconnectTimer) { clearTimeout(tab.reconnectTimer); tab.reconnectTimer = null; }

    var delay;
    if (immediate) {
      delay = 0;                 // visibilitychange fast-path: skip backoff
      tab.reconnectAttempt = 0;  // a fresh, user-driven attempt
    } else {
      delay = computeBackoffDelay(tab.reconnectAttempt);
      tab.reconnectAttempt = (tab.reconnectAttempt || 0) + 1;
    }

    // Only show "Reconnecting…" once per drop episode (don't spam on retries).
    if (!tab.reconnectShown) {
      tab.reconnectShown = true;
      writeStatus(tab, t("term.reconnecting"));
    }

    tab.reconnectTimer = setTimeout(function () {
      tab.reconnectTimer = null;
      if (tab.userClosed) return;
      connectSocket(tab);
    }, delay);
  }

  /* ---- Heartbeat liveness (client side of the server ping/pong) ----
   * While attached, the backend sends a TEXT frame {"type":"ping","t":<sec>}
   * every ~15s. We answer with {"type":"pong"} (never render the ping) and
   * stamp tab.lastPingAt. A half-open socket (Chrome froze a backgrounded tab,
   * or a silent network drop) stops delivering pings long before the browser
   * fires onclose — so we arm a ONE-SHOT watchdog per tab (reused, not a heavy
   * polling interval): each ping/open clears + re-arms a single setTimeout that
   * fires LIVENESS_MS later. If it fires while the tab is ACTIVE + visible and
   * no ping has arrived in that window, we force a reconnect to the SAME tab_id.
   * Backgrounded tabs are left alone — the visibilitychange fast-path resumes
   * them, and the server keeps buffering their PTY output. */
  var LIVENESS_MS = 45000; // ~3 missed 15s pings before we treat the socket as dead

  function armLiveness(tab) {
    if (!tab || tab.userClosed) return;
    if (tab.livenessTimer) clearTimeout(tab.livenessTimer);
    tab.livenessTimer = setTimeout(function () {
      tab.livenessTimer = null;
      checkLiveness(tab);
    }, LIVENESS_MS);
  }

  // Force a reconnect for a tab whose socket looks OPEN but has gone quiet.
  function checkLiveness(tab) {
    if (!tab || tab.userClosed) return;
    if (tab.id !== activeId) return;                 // only the active pane
    if (typeof document !== "undefined" && document.visibilityState !== "visible") return;
    if (tab.reconnectTimer) return;                  // a reconnect is already pending
    if (!tab.ws || tab.ws.readyState !== WebSocket.OPEN) return; // half-open only; else onclose handles it
    if (!tab.lastPingAt) return;                     // never connected/pinged
    if (Date.now() - tab.lastPingAt < LIVENESS_MS) { armLiveness(tab); return; } // fired early — keep watching

    // Stale + half-open: close the dead socket and reattach to the SAME tab_id.
    // _forceReconnectNow tells the onclose handler to reconnect immediately
    // (skip backoff) instead of double-scheduling.
    tab._forceReconnectNow = true;
    try { tab.ws.close(); } catch (e) {}
  }

  /* Handle one incoming TEXT frame: PTY output → render; control frame → act.
     A ping is answered with a pong over the SAME ws and is NEVER written to the
     terminal. Any other control frame is dropped (not rendered). Everything
     else (including malformed JSON-ish chunks) is written as PTY output. */
  function handleWsMessage(tab, ws, data) {
    var info = classifyIncoming(data);
    if (info.kind === "control") {
      if (info.type === "ping") {
        tab.lastPingAt = Date.now();
        armLiveness(tab);
        try {
          if (ws && ws.readyState === WebSocket.OPEN) ws.send(buildPongFrame());
        } catch (e) { /* socket raced closed — the next ping/reconnect covers it */ }
      }
      return; // control frames must never appear in the terminal
    }
    tab.term.write(data);
  }

  /* Wire a socket's handlers. Shared by the FIRST connection (openTab) and every
     reattach (connectSocket) so ping/pong + liveness behave identically across
     reconnects. */
  function wireSocket(tab, ws) {
    ws.onopen = function () {
      tab.reconnectAttempt = 0;
      if (tab.reconnectShown) {
        tab.reconnectShown = false;
        writeStatus(tab, t("term.reconnected"));
      }
      tab.lastPingAt = Date.now();   // fresh socket: start the liveness clock
      armLiveness(tab);
      sendResize(tab);
    };
    ws.onmessage = function (ev) { handleWsMessage(tab, ws, ev.data); };
    ws.onclose = function () {
      if (tab.userClosed) return;                    // deliberate close → final
      if (tab._forceReconnectNow) {                  // liveness-triggered close
        tab._forceReconnectNow = false;
        scheduleReconnect(tab, true);                // immediate, same tab_id
        return;
      }
      scheduleReconnect(tab, false);                 // transient drop → backoff
    };
    ws.onerror = function () { /* surfaced via onclose */ };
  }

  /* (Re)open the WebSocket for an EXISTING tab, reusing its tab_id so the
     backend reattaches to the still-running PTY and replays buffered output. */
  function connectSocket(tab) {
    if (!tab || tab.userClosed) return;
    var ws = new WebSocket(buildTerminalWsUrl(tab.id));
    tab.ws = ws;
    wireSocket(tab, ws);
  }

  function createTabButton(tab) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "term-tab";
    btn.setAttribute("role", "tab");
    btn.setAttribute("aria-selected", "false");
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
    // Tabs are appended to the scrolling strip. The "+" button lives OUTSIDE the
    // strip (pinned in the toolbar) so it stays reachable when the tabs overflow;
    // insertBefore is kept only for the case where it is still inside the strip.
    if (newTabBtn && newTabBtn.parentNode === tabBarEl) {
      tabBarEl.insertBefore(btn, newTabBtn);
    } else {
      tabBarEl.appendChild(btn);
    }
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
    var tab = {
      id: id, term: term, fit: fit, ws: ws, container: container, tuiMode: false,
      userClosed: false,          // true only when the user closes the tab
      reconnectTimer: null,       // pending reconnect setTimeout handle
      reconnectAttempt: 0,        // backoff step counter (reset on open)
      reconnectShown: false,      // "Reconnecting…" shown for this episode
      lastPingAt: 0,              // ms stamp of the last heartbeat ping received
      livenessTimer: null,        // one-shot watchdog setTimeout handle (re-armed per ping)
      _forceReconnectNow: false   // set when a liveness close should skip backoff
    };
    tabs.set(id, tab);

    term.write("\x1b[2m" + t("term.connecting") + "\x1b[0m\r\n");

    // Keystrokes always go to the tab's CURRENT socket (tab.ws), so input keeps
    // working after a reconnect swaps in a new WebSocket.
    term.onData(function (d) {
      var s = tab.ws;
      if (s && s.readyState === WebSocket.OPEN) s.send(d);
    });
    wireSocket(tab, ws);

    createTabButton(tab);
    updateEmptyState();
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
    stopInertia(); // a fling must not carry over onto the tab being switched to
    activeId = id;
    tabs.forEach(function (tab) {
      var show = tab.id === id;
      if (tab.container) tab.container.style.display = show ? "block" : "none";
      if (tab.button) {
        tab.button.classList.toggle("active", show);
        // ARIA tab semantics + keep the active tab visible in a scrolling strip.
        try { tab.button.setAttribute("aria-selected", show ? "true" : "false"); } catch (e) {}
        if (show && tab.button.scrollIntoView) {
          try { tab.button.scrollIntoView({ block: "nearest", inline: "nearest" }); } catch (e) {}
        }
      }
    });
    refitActive();
    observeActiveStage();
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

  /* BUG2: re-target the single ResizeObserver at the ACTIVE tab's container so
     FitAddon recomputes rows whenever THAT box actually changes size — covering
     the mobile URL-bar collapse, orientation change, and fullscreen enter/exit
     (none of which reliably fire a window resize). disconnect() first clears the
     previous tab's target. No-op when ResizeObserver is unavailable (jsdom). */
  function observeActiveStage() {
    if (!stageResizeObs) return;
    var tab = activeTab();
    try { stageResizeObs.disconnect(); } catch (e) {}
    if (tab && tab.container) {
      try { stageResizeObs.observe(tab.container); } catch (e) {}
    }
  }

  function closeTab(id) {
    var tab = tabs.get(id);
    if (!tab) return;

    // DELIBERATE close: stop reconnecting, tell the backend to KILL the PTY,
    // then drop the socket. This is the ONLY path that sends {"type":"close"}.
    tab.userClosed = true;
    if (inertia.tab === tab) stopInertia();
    if (tab.reconnectTimer) { clearTimeout(tab.reconnectTimer); tab.reconnectTimer = null; }
    if (tab.livenessTimer) { clearTimeout(tab.livenessTimer); tab.livenessTimer = null; }
    try {
      if (tab.ws && tab.ws.readyState === WebSocket.OPEN) tab.ws.send(buildCloseFrame());
    } catch (e) {}
    try { tab.ws.close(); } catch (e) {}
    try { tab.term.dispose(); } catch (e) {}
    // BUG2: stop observing the closed tab's stage box (the observer only ever
    // watches the active container, so this is a targeted cleanup; reactivation
    // below re-targets it at the surviving tab via observeActiveStage()).
    if (stageResizeObs && tab.container) {
      try { stageResizeObs.unobserve(tab.container); } catch (e) {}
    }
    if (tab.button && tab.button.remove) tab.button.remove();
    if (tab.container && tab.container.remove) tab.container.remove();
    tabs.delete(id);

    if (activeId === id) {
      var it = tabs.keys().next();
      if (!it.done) activate(it.value);
      else { activeId = null; openTab(); } // keep at least one tab alive
    }
    updateEmptyState();
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
    stopInertia(); // a fling must not keep scrolling into a just-enabled passthrough
    var btn = document.getElementById("termTui");
    if (btn) {
      btn.setAttribute("aria-pressed", tab.tuiMode ? "true" : "false");
      btn.title = t(tab.tuiMode ? "term.tui_on" : "term.tui_off");
      btn.setAttribute("aria-label", btn.title);
    }
  }

  /* ---- Scroll & swipe (FSD §2.5.1) ----
   * A touch swipe is turned into the SAME signal a mouse wheel produces: we
   * dispatch a synthetic `wheel` event on xterm's root element and let xterm
   * decide what the gesture means for whatever is running in the tab:
   *   - normal buffer (shell / logs / man): viewport pixel scroll -> 1:1 finger
   *     tracking, and xterm's own edge bubbling gives the soft stop at the ends.
   *   - alternate buffer (TUI): there is no scrollback to move, so xterm emits
   *     the app's own scroll input — Up/Down cursor keys, or mouse-wheel
   *     reports when the app asked for wheel tracking. THIS is the TUI fix:
   *     calling term.scrollLines() there silently did nothing, so swiping a TUI
   *     felt dead.
   * Release momentum (rAF + friction) is layered on top of the 1:1 drag.
   * The manual TUI toggle stays as an explicit PASSTHROUGH for apps that want
   * the raw touch (drag-select, tap-and-hold) — see swipeIsOurs().
   */
  var SWIPE_THRESHOLD = 10;        // px before a gesture is treated as a swipe
  var VELOCITY_WEIGHT = 0.35;      // EMA factor for the release velocity
  var INERTIA_MIN_VY = 0.05;       // px/ms below which we skip the momentum
  var ptr = {
    active: false, type: "", lastX: 0, lastY: 0, lastT: 0, x: 0, y: 0,
    vy: 0, moved: 0, isSwipe: false
  };
  var inertia = { raf: 0, vy: 0, lastT: 0, tab: null };

  /* A swipe is "ours" to own only when: a non-mouse gesture is in flight, it has
     crossed the movement threshold, and the active tab is NOT in TUI passthrough.
     Shared by the pointermove scroller and the touchmove suppression guard. */
  function swipeIsOurs(tab) {
    return ptr.active && ptr.type !== "mouse" && ptr.isSwipe && !!tab && !tab.tuiMode;
  }

  /* Feed a pixel delta to xterm as a wheel gesture at the finger position.
     No-op when the terminal is not attached (no element) or the platform has no
     WheelEvent — a swipe must never fall back to a bogus scrollLines(). */
  function emitWheel(tab, deltaY, clientX, clientY) {
    if (!deltaY || !tab || !tab.term || !tab.term.element) return;
    if (typeof WheelEvent !== "function") return;
    var ev = new WheelEvent("wheel", {
      deltaY: deltaY,
      deltaMode: 0, // DOM_DELTA_PIXEL -> 1:1 with the finger
      clientX: clientX || 0,
      clientY: clientY || 0,
      bubbles: true,
      cancelable: true
    });
    tab.term.element.dispatchEvent(ev);
  }

  function stopInertia() {
    if (inertia.raf && typeof cancelAnimationFrame === "function") {
      cancelAnimationFrame(inertia.raf);
    }
    inertia.raf = 0; inertia.vy = 0; inertia.tab = null;
  }

  function inertiaFrame() {
    var tab = inertia.tab;
    if (!tab || !inertia.vy) { stopInertia(); return; }
    var t = nowMs();
    var dt = t - inertia.lastT;
    inertia.lastT = t;
    if (!(dt > 0) || dt > 100) dt = 16; // stalled / backgrounded frame
    // Momentum dies at a buffer edge (soft stop). Not applicable to a TUI: its
    // "scroll" is the app's own state, so let the app decide when to stop.
    if (!isAltScreen(tab) && atEdge(tab.term)) { stopInertia(); return; }
    emitWheel(tab, swipeWheelDelta(inertia.vy * dt), ptr.x, ptr.y);
    inertia.vy = decayVelocity(inertia.vy, dt);
    if (!inertia.vy) { stopInertia(); return; }
    if (typeof requestAnimationFrame === "function") {
      inertia.raf = requestAnimationFrame(inertiaFrame);
    } else {
      stopInertia();
    }
  }

  function startInertia(tab, vy) {
    stopInertia();
    inertia.tab = tab; inertia.vy = vy; inertia.lastT = nowMs();
    if (typeof requestAnimationFrame === "function") {
      inertia.raf = requestAnimationFrame(inertiaFrame);
    }
  }

  function setupSwipe() {
    var target = stageEl || bodyEl;
    if (!target) return;

    // CAPTURE + non-passive so the arm reliably fires even for touches that land
    // on the xterm layers mounted inside the stage (the stage is their ancestor,
    // so capture sees the pointerdown before any child can consume it). We skip
    // the `mouse` pointerType: mouse text-selection is xterm's job (mousedown),
    // and mouse wheel is a separate `wheel` event — neither should be hijacked.
    target.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") { ptr.active = false; return; }
      stopInertia();                   // a new touch interrupts a running fling
      ptr.active = true;
      ptr.type = e.pointerType || "touch";
      ptr.lastX = e.clientX; ptr.lastY = e.clientY;
      ptr.x = e.clientX; ptr.y = e.clientY;
      ptr.lastT = nowMs();
      ptr.vy = 0; ptr.moved = 0; ptr.isSwipe = false;
    }, { capture: true, passive: false });

    // Listen on window so we keep tracking outside the element bounds.
    window.addEventListener("pointermove", function (e) {
      if (!ptr.active) return;
      var tab = activeTab();
      if (!tab) return;
      var t = nowMs();
      var dt = t - ptr.lastT;
      if (dt <= 0) return;
      var dy = e.clientY - ptr.lastY;
      ptr.moved += Math.abs(dy) + Math.abs(e.clientX - ptr.lastX);
      ptr.vy = blendVelocity(ptr.vy, dy / dt, VELOCITY_WEIGHT);
      ptr.lastX = e.clientX; ptr.lastY = e.clientY; ptr.lastT = t;
      ptr.x = e.clientX; ptr.y = e.clientY;

      if (!ptr.isSwipe && ptr.moved > SWIPE_THRESHOLD) ptr.isSwipe = true;

      // Passthrough (TUI toggle ON) => the app keeps its own raw gesture.
      if (swipeIsOurs(tab)) {
        e.preventDefault();
        e.stopPropagation();
        emitWheel(tab, swipeWheelDelta(dy), e.clientX, e.clientY);
      }
    }, { passive: false });

    // xterm binds its OWN non-passive `touchmove` on `.xterm-screen` that scrolls
    // the viewport via scrollTop. With touch-action:none the browser no longer
    // steals the gesture, so BOTH that handler and our pointermove would fire —
    // double-scrolling. In CAPTURE on the stage we stop the touchmove from ever
    // reaching xterm, but ONLY while we own the swipe (and never in passthrough
    // mode, so the app keeps its raw touch). preventDefault here also blocks the
    // compat mouse events xterm would otherwise derive from the touch.
    target.addEventListener("touchmove", function (e) {
      if (swipeIsOurs(activeTab())) {
        e.preventDefault();
        e.stopPropagation();
      }
    }, { capture: true, passive: false });

    // If the browser ever reclaims the gesture (pointercancel), drop the arm so
    // a stale pointermove can't scroll after the finger is gone.
    window.addEventListener("pointercancel", function () {
      ptr.active = false; ptr.isSwipe = false; ptr.vy = 0;
      stopInertia();
    });

    window.addEventListener("pointerup", function (e) {
      if (!ptr.active) return;
      var tab = activeTab();
      // Decide ownership BEFORE clearing ptr.active (swipeIsOurs depends on it).
      var ours = swipeIsOurs(tab);
      ptr.active = false;
      ptr.x = e.clientX || ptr.x; ptr.y = e.clientY || ptr.y;
      if (ours && Math.abs(ptr.vy) > INERTIA_MIN_VY) startInertia(tab, ptr.vy);
      ptr.isSwipe = false;
      ptr.vy = 0;
    });
  }

  function init() {
    tabBarEl = document.getElementById("termTabBar");
    containersEl = document.getElementById("termContainers");
    stageEl = document.getElementById("termStage");
    bodyEl = document.getElementById("terminalBody");
    newTabBtn = document.getElementById("termNewTab");
    emptyEl = document.getElementById("termEmpty");
    emptyNewTabBtn = document.getElementById("termEmptyNewTab");
    if (!tabBarEl || !containersEl) return; // not on this page / test env

    if (newTabBtn) newTabBtn.addEventListener("click", openTab);
    if (emptyNewTabBtn) emptyNewTabBtn.addEventListener("click", openTab);
    var fs = document.getElementById("termFullscreen");
    if (fs) fs.addEventListener("click", toggleFullscreen);
    var pst = document.getElementById("termPaste");
    if (pst) pst.addEventListener("click", pasteActive);
    var tui = document.getElementById("termTui");
    if (tui) tui.addEventListener("click", toggleTui);

    setupSwipe();
    updateEmptyState();
    window.addEventListener("resize", debounce(refitActive, 120));

    // BUG2: refit xterm whenever the ACTIVE stage box actually changes size —
    // covers the mobile URL-bar collapse, orientation change, and fullscreen
    // enter/exit, none of which reliably fire a window resize. Re-targeted at
    // the active tab's container in observeActiveStage(); disconnected on close.
    if (typeof ResizeObserver !== "undefined") {
      debouncedRefit = debounce(refitActive, 100);
      stageResizeObs = new ResizeObserver(function () {
        if (debouncedRefit) debouncedRefit();
      });
      observeActiveStage();
    }

    // Fast-path: when the page becomes visible again (e.g. restored from a
    // minimized tab), if the ACTIVE tab's socket is down, reconnect NOW instead
    // of waiting out the backoff — so the session resumes immediately.
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState !== "visible") return;
      var tab = activeTab();
      if (!tab || tab.userClosed) return;
      var down = !tab.ws ||
        (tab.ws.readyState !== WebSocket.OPEN && tab.ws.readyState !== WebSocket.CONNECTING);
      if (down) { scheduleReconnect(tab, true); return; }
      // Socket still looks OPEN after a freeze — but it may be half-open (no
      // heartbeat). If it's gone quiet, force a fresh reattach on return.
      checkLiveness(tab);
    });

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
    swipeWheelDelta: swipeWheelDelta,
    blendVelocity: blendVelocity,
    decayVelocity: decayVelocity,
    buildTerminalWsUrl: buildTerminalWsUrl,
    tabTitle: tabTitle,
    buildResizeFrame: buildResizeFrame,
    buildCloseFrame: buildCloseFrame,
    buildPongFrame: buildPongFrame,
    classifyIncoming: classifyIncoming,
    computeBackoffDelay: computeBackoffDelay,
    // manager hooks (used by app.js nav handler):
    onShow: function () {
      if (!activeId) openTab();
      else refitActive();
    },
    openTab: openTab,
    closeTab: closeTab,
    activate: activate,
    refitActive: refitActive,
    launchInNewTab: launchInNewTab,
    // test/introspection hooks (reconnect logic):
    _tabs: tabs,
    _scheduleReconnect: scheduleReconnect,
    _connectSocket: connectSocket,
    _checkLiveness: checkLiveness,
    _LIVENESS_MS: LIVENESS_MS
  };
  // Convenience alias for app.js.
  window.aigate.terminalManager = window.aigate.terminal;

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
