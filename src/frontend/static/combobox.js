/* ===== aigate searchable combobox (model pickers) — vanilla JS, no build ===== */
/* window.aigate.createCombobox({inputId, listId, formId?}) -> controller.

   A text <input> + a custom-rendered <ul role="listbox"> panel that FILTERS
   as you type. One widget fixes both mobile bugs:
     * <datalist> never pops a dropdown on Android  -> this panel is plain DOM.
     * <select> cannot be typed into to search      -> this is a text input.
   Free text is native: the input value IS the model string, so undiscovered
   / custom models need no sentinel option and no extra box.

   API:
     setOptions(models)  models = [{value,label}] ALREADY sorted by the caller;
                         rebuilds the option list (current filter re-applied).
     setValue(v)         put v into the input (programmatic selection).
     getValue()          the chosen-or-typed model string (trimmed).
     setLoading(bool)    "Loading models…" row in the panel + aria-busy on
                         input/list/form + input disabled; false restores.
     focus()             passthrough focus on the input.
     open() / close() / isOpen()   panel control + state.
     destroy()           detach the document-level listeners.

   Robustness notes:
   * Elements are resolved BY ID on every operation and every listener is
     delegated on `document`, so ONE controller survives modal DOM rebuilds
     (tests replace body.innerHTML between cases). Open/loading state is
     derived from the DOM (ul[hidden], input[aria-busy]) — never from a cached
     flag — so a rebuilt DOM can never desync the widget.
   * Panel: absolutely positioned under the input (the .aigate-combo wrapper
     is position:relative), scrollable max-height, >=40px touch rows; flips
     above the input (.aigate-combo-up) when it would overflow the viewport
     bottom (short screens / mobile keyboard).
   * a11y: input role=combobox + aria-expanded / aria-controls /
     aria-autocomplete="list" / aria-activedescendant; list role=listbox;
     options role=option with unique ids ("<listId>-opt-<n>").
   * Keyboard: ArrowDown/ArrowUp move the highlight (wrapping), Enter selects
     the highlighted option — or, with no highlight, accepts the typed
     free-text value — and closes; Escape closes. Enter on a CLOSED panel is
     NOT consumed, so outer form wiring (e.g. add-member submit) still runs.
   * Close on outside click, and on blur with a small delay so option clicks
     register (mousedown on the panel also cancels the pending close).
   * ADR-011: this widget never swallows errors; fetch failures stay the
     caller's responsibility (it only renders what it is given). */

(function () {
  "use strict";

  /* Same resolution order as combos.js/app.js getStr (window.aigate.getStr
     when app.js is loaded, raw window.I18N fallback otherwise). */
  function getStr(key) {
    var a = window.aigate || {};
    if (typeof a.getStr === "function") return a.getStr(key);
    var loc = (typeof document !== "undefined" && document.documentElement)
      ? document.documentElement.getAttribute("data-locale") : "en";
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

  /* Blur-close grace period: long enough for a tap/click on an option to
     fire before the panel disappears, short enough to feel instant. */
  var CLOSE_DELAY_MS = 150;

  window.aigate = window.aigate || {};

  window.aigate.createCombobox = function (opts) {
    opts = opts || {};
    var inputId = String(opts.inputId || "");
    var listId = String(opts.listId || "");
    var formId = opts.formId ? String(opts.formId) : null;

    var options = [];   // [{value,label}] as supplied (caller keeps them sorted)
    var visible = [];   // options after the current filter
    var active = -1;    // highlighted index into `visible`
    var closeTimer = null;
    var bound = false;  // document listeners attached once per controller
    var origPlaceholder = null; // remembered before the first loading swap

    /* ---- lazy element lookup (rebuild-safe) ---- */
    function input() { return document.getElementById(inputId); }
    function list() { return document.getElementById(listId); }
    function form() { return formId ? document.getElementById(formId) : null; }
    function query() { var i = input(); return i ? String(i.value || "") : ""; }

    /* ---- derived state: read from the DOM, never cached ---- */
    function isOpen() { var ul = list(); return !!ul && !ul.hidden; }
    function isLoading() { var i = input(); return !!i && i.getAttribute("aria-busy") === "true"; }

    /* ---- filtering: case-insensitive substring on label OR value ----
       Empty query shows everything. */
    function computeVisible() {
      var q = query().trim().toLowerCase();
      if (!q) { visible = options.slice(); return; }
      visible = options.filter(function (o) {
        var label = String(o.label == null ? o.value : o.label).toLowerCase();
        var value = String(o.value == null ? "" : o.value).toLowerCase();
        return label.indexOf(q) !== -1 || value.indexOf(q) !== -1;
      });
    }

    /* ---- render ---- */
    function optionId(i) { return listId + "-opt-" + i; }

    function render() {
      var ul = list();
      var inp = input();
      var open = isOpen();
      var loading = isLoading();
      if (ul) {
        var html = "";
        if (loading) {
          html = '<li class="aigate-combo-msg" role="presentation">' +
            escapeHtml(getStr("combobox.loading")) + "</li>";
        } else if (!visible.length && query().trim() !== "") {
          html = '<li class="aigate-combo-msg" role="presentation">' +
            escapeHtml(getStr("combobox.no_match")) + "</li>";
        } else {
          html = visible.map(function (o, i) {
            return '<li role="option" id="' + escapeHtml(optionId(i)) + '"' +
              ' data-value="' + escapeHtml(o.value) + '"' +
              ' class="aigate-combo-opt' + (i === active ? " aigate-combo-active" : "") + '"' +
              ' aria-selected="' + (i === active ? "true" : "false") + '">' +
              escapeHtml(o.label == null ? o.value : o.label) + "</li>";
          }).join("");
        }
        ul.innerHTML = html;
        ul.setAttribute("role", "listbox");
        if (loading) ul.setAttribute("aria-busy", "true");
        else ul.removeAttribute("aria-busy");
      }
      if (inp) {
        inp.setAttribute("role", "combobox");
        inp.setAttribute("aria-controls", listId);
        inp.setAttribute("aria-autocomplete", "list");
        inp.setAttribute("aria-expanded", open ? "true" : "false");
        if (open && active >= 0 && visible[active]) {
          inp.setAttribute("aria-activedescendant", optionId(active));
        } else {
          inp.removeAttribute("aria-activedescendant");
        }
      }
    }

    /* ---- mobile-safe positioning ----
       Flip the panel above the input when it would overflow the viewport
       bottom AND there is more room above. No-ops where layout metrics are
       unavailable (jsdom). */
    function position() {
      var ul = list();
      var inp = input();
      if (!ul || !inp) return;
      ul.classList.remove("aigate-combo-up");
      try {
        var rect = inp.getBoundingClientRect();
        var vh = window.innerHeight ||
          (document.documentElement && document.documentElement.clientHeight) || 0;
        var ph = ul.offsetHeight || 0;
        if (rect.bottom + ph > vh && rect.top - ph > 0) ul.classList.add("aigate-combo-up");
      } catch (e) { /* no layout info — keep the default (below) */ }
    }

    /* ---- open / close ---- */
    function open() {
      var ul = list();
      if (!ul) return;
      active = -1;
      computeVisible();
      ul.hidden = false;
      render();
      position();
    }

    function close() {
      var ul = list();
      active = -1;
      if (ul) ul.hidden = true;
      render();
    }

    function cancelClose() {
      if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
    }
    function scheduleClose() {
      cancelClose();
      closeTimer = setTimeout(close, CLOSE_DELAY_MS);
    }

    /* ---- selection ---- */
    function selectValue(v) {
      var inp = input();
      if (inp) inp.value = v == null ? "" : String(v);
      close();
    }

    /* Move the highlight (wrapping) over the CURRENT filtered list. */
    function move(delta) {
      if (isLoading()) return;
      computeVisible();
      if (!visible.length) { render(); return; }
      active += delta;
      if (active < 0) active = visible.length - 1;
      if (active >= visible.length) active = 0;
      render();
      var ul = list();
      var li = ul ? ul.querySelector('li[role="option"][id="' + optionId(active) + '"]') : null;
      if (li && typeof li.scrollIntoView === "function") {
        try { li.scrollIntoView({ block: "nearest" }); } catch (e) { /* jsdom */ }
      }
    }

    /* ---- delegated event handlers (document-level, id-guarded) ---- */
    function owns(e) { return e && e.target && e.target.id === inputId; }

    function onDocInput(e) {
      if (!owns(e)) return;
      cancelClose();
      computeVisible();
      active = -1;
      var ul = list();
      if (ul && ul.hidden) { ul.hidden = false; render(); position(); }
      else render();
    }

    function onDocFocusIn(e) {
      if (!owns(e)) return;
      cancelClose();
      open();
    }

    function onDocFocusOut(e) {
      if (!owns(e)) return;
      scheduleClose();
    }

    function onDocKeydown(e) {
      if (!owns(e)) return;
      var key = e.key;
      if (key === "ArrowDown" || key === "ArrowUp") {
        e.preventDefault();
        if (!isOpen()) open();
        move(key === "ArrowDown" ? 1 : -1);
      } else if (key === "Enter") {
        if (!isOpen()) return; // closed: let it bubble (outer form wiring)
        e.preventDefault();
        e.stopPropagation();
        if (isLoading()) return;
        if (active >= 0 && visible[active]) selectValue(visible[active].value);
        else close(); // accept the typed free-text value (input IS the value)
      } else if (key === "Escape") {
        if (isOpen()) { e.preventDefault(); e.stopPropagation(); cancelClose(); close(); }
      }
    }

    function onDocMousedown(e) {
      var ul = list();
      if (ul && ul.contains(e.target)) {
        e.preventDefault(); // keep focus on the input (no blur-close)
        cancelClose();
      }
    }

    function onDocClick(e) {
      var ul = list();
      var inp = input();
      if (!ul || !inp) return;
      var li = (e.target && typeof e.target.closest === "function")
        ? e.target.closest('li[role="option"]') : null;
      if (li && ul.contains(li)) {
        e.preventDefault();
        selectValue(li.getAttribute("data-value"));
        return;
      }
      if (isOpen() && e.target !== inp && !inp.contains(e.target) && !ul.contains(e.target)) {
        close();
      }
    }

    function bind() {
      if (bound) return;
      bound = true;
      document.addEventListener("input", onDocInput);
      document.addEventListener("focusin", onDocFocusIn);
      document.addEventListener("focusout", onDocFocusOut);
      document.addEventListener("keydown", onDocKeydown);
      document.addEventListener("mousedown", onDocMousedown);
      document.addEventListener("click", onDocClick);
    }

    function unbind() {
      if (!bound) return;
      bound = false;
      cancelClose();
      document.removeEventListener("input", onDocInput);
      document.removeEventListener("focusin", onDocFocusIn);
      document.removeEventListener("focusout", onDocFocusOut);
      document.removeEventListener("keydown", onDocKeydown);
      document.removeEventListener("mousedown", onDocMousedown);
      document.removeEventListener("click", onDocClick);
    }

    /* ---- public controller ---- */
    var api = {
      setOptions: function (models) {
        options = (Array.isArray(models) ? models : []).map(function (m) {
          m = m || {};
          var v = m.value == null ? "" : String(m.value);
          return { value: v, label: m.label == null || m.label === "" ? v : String(m.label) };
        });
        active = -1;
        computeVisible();
        render();
        if (isOpen()) position();
      },
      setValue: function (v) {
        var inp = input();
        if (inp) inp.value = v == null ? "" : String(v);
        active = -1;
        computeVisible();
        render();
      },
      getValue: function () {
        var inp = input();
        return inp ? String(inp.value || "").trim() : "";
      },
      setLoading: function (on) {
        on = !!on;
        var inp = input();
        var f = form();
        if (inp) {
          if (on) {
            if (origPlaceholder === null) origPlaceholder = inp.getAttribute("placeholder");
            inp.setAttribute("placeholder", getStr("combobox.loading"));
          } else if (origPlaceholder !== null) {
            inp.setAttribute("placeholder", origPlaceholder);
          }
          inp.setAttribute("aria-busy", on ? "true" : "false");
          inp.disabled = on;
        }
        if (f) f.setAttribute("aria-busy", on ? "true" : "false");
        active = -1;
        render();
      },
      focus: function () {
        var inp = input();
        if (inp && typeof inp.focus === "function") inp.focus();
      },
      open: open,
      close: close,
      isOpen: isOpen,
      getVisible: function () { return visible.slice(); },
      destroy: unbind
    };

    bind();
    // Seed the a11y attributes + placeholder when the DOM already exists.
    var inp0 = input();
    if (inp0 && !inp0.getAttribute("placeholder")) {
      inp0.setAttribute("placeholder", getStr("combobox.search_ph"));
    }
    render();
    return api;
  };
})();
