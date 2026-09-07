/* ===== aigate searchable combobox (model pickers) — vanilla JS, no build ===== */
/* window.aigate.createCombobox({inputId, listId, formId?, searchInside?,
    groupBy?, groupOrder?}) -> controller.

    A text <input> + a custom-rendered <ul role="listbox"> panel that FILTERS
    as you type. One widget fixes both mobile bugs:
      * <datalist> never pops a dropdown on Android  -> this panel is plain DOM.
      * <select> cannot be typed into to search      -> this is a text input.
    Free text is native: the input value IS the model string, so undiscovered
    / custom models need no sentinel option and no extra box.

    API:
      setOptions(models)  models = [{value,label,group?}] ALREADY sorted by the
                          caller (group-less sorting); rebuilds the option list
                          (current filter re-applied). `group` is only used when
                          groupBy === "group".
      setValue(v)         put v into the input (programmatic selection).
      getValue()          the chosen-or-typed model string (trimmed).
      setLoading(bool)    "Loading models…" row in the panel + aria-busy on
                          input/list/form + input disabled; false restores.
      focus()             passthrough focus on the input.
      open() / close() / isOpen()   panel control + state.
      destroy()           detach the document-level listeners.

    New capabilities:
      searchInside (bool, default false)
        Render a search <input> as the FIRST <li> of the panel (role=
        presentation). The top <input> stays the selected-value holder/trigger
        (editable for free text + shows the chosen value); the inner search
        input is the live filter. The two are kept in sync (mirror both ways).
        On open the inner search is focused (and cleared so the full list shows);
        the selected value is preserved and restored on cancel.
      groupBy ("none"|"prefix"|"group", default "none")
        "prefix": derive a group from each option value via familyOf() (e.g.
                  deepseek-v1 + deepseekv2 -> Deepseek; gpt-4o -> Gpt).
        "group":   use each option's supplied `group` (caller-supplied; falls
                  back to "Other").
        "none":    flat (default, legacy behavior).
      groupOrder (array of strings, optional)
        Pinned group order; listed groups come first, remaining groups sorted
        alphabetically (case-insensitive) afterwards.

    Robustness / a11y notes (unchanged contracts):
    * Elements are resolved BY ID on every operation and every listener is
      delegated on `document`, so ONE controller survives modal DOM rebuilds
      (tests replace body.innerHTML between cases). Open/loading state is
      derived from the DOM (ul[hidden], input[aria-busy]) — never from a cached
      flag.
    * Group headers are <li role="presentation"> (not focusable, not options);
      only <li role="option"> participate in keyboard nav (indexed by `visible`).
    * Keyboard: ArrowDown/ArrowUp move the highlight (wrapping), Enter selects
      the highlighted option — or, with no highlight, accepts the typed
      free-text value (ADR-011) — and closes; Escape closes. Enter on a CLOSED
      panel is NOT consumed, so outer form wiring still runs.
    * Close on outside click, and on blur with a small delay so option clicks
      register (mousedown on the panel also cancels the pending close). */

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

  /* Derive a model "family" group from an option value (groupBy:"prefix").
     Take the leading token before the first "-"; if that token still ends in a
     version suffix matching /[vV]?\d.*$/ strip it; title-case the first letter.
       deepseek-v1 -> deepseek -> Deepseek
       deepseekv2  -> deepseek -> Deepseek
       gpt-4o      -> gpt      -> Gpt
       claude-3-opus -> claude -> Claude */
  function familyOf(id) {
    id = String(id == null ? "" : id);
    var token = id.split("-")[0];
    if (!token) return "";
    var m = token.match(/[vV]?\d.*$/);
    if (m && m.index > 0) token = token.slice(0, m.index);
    return token.charAt(0).toUpperCase() + token.slice(1);
  }

  /* Blur-close grace period: long enough for a tap/click on an option to
     fire before the panel disappears, short enough to feel instant. */
  var CLOSE_DELAY_MS = 150;
  var FALLBACK_GROUP = "Other";

  window.aigate = window.aigate || {};

  window.aigate.createCombobox = function (opts) {
    opts = opts || {};
    var inputId = String(opts.inputId || "");
    var listId = String(opts.listId || "");
    var formId = opts.formId ? String(opts.formId) : null;
    var searchInside = !!opts.searchInside;
    var groupBy = opts.groupBy === "prefix" || opts.groupBy === "group"
      ? opts.groupBy : "none";
    var groupOrder = Array.isArray(opts.groupOrder) ? opts.groupOrder.slice() : [];
    // Two-level grouping: only the caller that wants it passes subGroupBy.
    // "prefix" derives a sub from the label via familyOf(); "group" uses an
    // explicit option.subGroup string. A caller may opt ONE option out with
    // subGroup:false (e.g. combo items stay flat). null = no sub-grouping.
    var subGroupBy = opts.subGroupBy === "prefix" || opts.subGroupBy === "group"
      ? opts.subGroupBy : null;
    // startExpanded (bool, default false): when true, groups are NOT collapsed
    // on first appearance (the legacy default collapses new groups). Toggling
    // a group still works either way. Used by the Self-Heal model picker, which
    // wants its family groups visible without a click.
    var startExpanded = !!opts.startExpanded;

    var options = [];   // [{value,label,_group}] as supplied
    var visible = [];   // options after the current filter (selectable only)
    var visibleIndex = null; // Map<option, index-into-visible>
    var active = -1;    // highlighted index into `visible`
    var collapsed = (typeof Set === "function") ? new Set() : null; // group names collapsed
    var tracked = (typeof Set === "function") ? new Set() : null;   // groups already assigned a state
    var collapsedSub = (typeof Set === "function") ? new Set() : null; // composite "group\u0001sub" collapsed
    var trackedSub = (typeof Set === "function") ? new Set() : null;   // sub keys already assigned a state
    var closeTimer = null;
    var onScroll = function () { position(); };   // reposition fixed panel (capture: catches modal scroll)
    var onResize = function () { position(); };
    var posBound = false;                          // scroll/resize listeners attached?
    function addPosListeners() {
      if (posBound) return;
      posBound = true;
      window.addEventListener("scroll", onScroll, true);
      window.addEventListener("resize", onResize);
    }
    function removePosListeners() {
      if (!posBound) return;
      posBound = false;
      window.removeEventListener("scroll", onScroll, true);
      window.removeEventListener("resize", onResize);
    }
    var bound = false;  // document listeners attached once per controller
    var origPlaceholder = null; // remembered before the first loading swap
    var committedValue = "";    // last selected/known value (searchInside cancel-restore)
    var lastNoMatch = false;    // searchInside no-match (custom entry) active

    /* ---- lazy element lookup (rebuild-safe) ---- */
    function input() { return document.getElementById(inputId); }
    function list() { return document.getElementById(listId); }
    function form() { return formId ? document.getElementById(formId) : null; }
    function searchInput() { return document.getElementById(listId + "-search"); }
    function topValue() { var i = input(); return i ? String(i.value || "") : ""; }
    function searchValue() { var s = searchInput(); return s ? String(s.value || "") : ""; }
    /* Filter source: the inner search input when searchInside, else the top
       input (legacy behavior). The two are mirrored so they stay equal during
       typing; search is cleared on open so the full list shows. */
    function query() { return searchInside ? searchValue() : topValue(); }

    /* ---- derived state: read from the DOM, never cached ---- */
    function isOpen() { var ul = list(); return !!ul && !ul.hidden; }
    function isLoading() { var i = input(); return !!i && i.getAttribute("aria-busy") === "true"; }

    /* ---- filtering: case-insensitive substring on label OR value ----
       Empty query shows everything. When searchInside + non-empty query + no
       match, a synthetic "use custom" option is appended to `visible`. */
    function queryNonEmpty() { return query().trim() !== ""; }
    function computeVisible() {
      var qRaw = query();
      var q = qRaw.trim().toLowerCase();
      var qEmpty = qRaw.trim() === "";
      var matched = !q ? options.slice() : options.filter(function (o) {
        var label = String(o.label == null ? o.value : o.label).toLowerCase();
        var value = String(o.value == null ? "" : o.value).toLowerCase();
        return label.indexOf(q) !== -1 || value.indexOf(q) !== -1;
      });
      lastNoMatch = searchInside && q !== "" && matched.length === 0;
      if (lastNoMatch) {
        visible = [{ value: qRaw, label: useCustomLabel(qRaw), _group: null, _custom: true }];
      } else {
        // Drop options belonging to a COLLAPSED group — but ONLY when the query
        // is empty. While searching (query non-empty) every group is treated as
        // expanded so matches are always visible regardless of collapse state
        // (the spec's "queryEmpty ||" is the negation: show-all while searching).
        // Same rule applies to the second-level sub-groups (composite key).
        visible = matched.filter(function (o) {
          if (!qEmpty) return true; // searching -> show all (auto-expand)
          if (collapsed && o._group != null && collapsed.has(o._group)) return false; // main collapsed
          if (subGroupBy && collapsedSub && o._sub != null &&
              collapsedSub.has(o._group + "\u0001" + o._sub)) return false; // sub collapsed
          return true;
        });
      }
      visibleIndex = new Map();
      visible.forEach(function (o, i) { visibleIndex.set(o, i); });
      // NOTE: do NOT reset `active` here — move() calls computeVisible() then
      // increments active; callers that want a reset do it themselves.
    }

    function useCustomLabel(raw) {
      var tpl = getStr("combobox.use_custom");
      return tpl.replace("%s", raw);
    }

    /* ---- render ---- */
    function optionId(i) { return listId + "-opt-" + i; }

    function optionHtml(o) {
      var i = visibleIndex ? visibleIndex.get(o) : -1;
      return '<li role="option" id="' + escapeHtml(optionId(i)) + '"' +
        ' data-value="' + escapeHtml(o.value) + '"' +
        ' class="aigate-combo-opt' + (o._sub != null ? " aigate-combo-opt-sub" : "") +
        (i === active ? " aigate-combo-active" : "") + '"' +
        ' aria-selected="' + (i === active ? "true" : "false") + '">' +
        escapeHtml(o.label == null ? o.value : o.label) + "</li>";
    }

    /* Ordered group names derived from ALL options (not just visible), honoring
       groupOrder pins then alpha. Used so a collapsed group's HEADER still
       renders (we never want to hide a header just because its children are
       collapsed). */
    function orderedGroupNames() {
      var seen = {};
      var names = [];
      options.forEach(function (o) {
        var g = o._group == null ? "" : String(o._group);
        if (g === "") return; // null groups are flat-rendered, not as a header
        if (!seen[g]) { seen[g] = true; names.push(g); }
      });
      var rest = names.filter(function (n) { return groupOrder.indexOf(n) === -1; })
        .sort(function (a, b) {
          var al = a.toLowerCase(), bl = b.toLowerCase();
          return al < bl ? -1 : al > bl ? 1 : 0;
        });
      return groupOrder.concat(rest);
    }

    /* Sub-group names for ONE main group. Derived from `options` (NOT `visible`)
        so a collapsed sub-group's HEADER still renders — we never hide a header
        just because its children are dropped by the collapse filter. While
        SEARCHING we switch the pool to `visible` so only sub-groups that actually
        have matches are shown (auto-expanded, no empty headers). Alpha-sorted,
        case-insensitive. Combo/flat items (_sub == null) are excluded here; they
        render directly under the main header. */
    function orderedSubGroupNames(name, searching) {
      var seen = {};
      var names = [];
      var pool = searching ? visible : options;
      pool.forEach(function (o) {
        if (o._sub == null) return;
        if ((o._group == null ? "" : String(o._group)) !== name) return;
        if (!seen[o._sub]) { seen[o._sub] = true; names.push(o._sub); }
      });
      names.sort(function (a, b) {
        var al = a.toLowerCase(), bl = b.toLowerCase();
        return al < bl ? -1 : al > bl ? 1 : 0;
      });
      return names;
    }

    function renderOptionsHtml() {
      if (lastNoMatch || groupBy === "none") return visible.map(optionHtml).join("");
      var searching = queryNonEmpty();
      // Group-less options (e.g. a "" default option) have no _group, so they
      // can't ride a group header — render them flat at the top before any
      // grouped section. No other picker emits group-less options, so this is
      // additive for the existing prefix/group callers.
      var groupless = visible.filter(function (o) { return o._group == null || o._group === ""; });
      var groupHtml = orderedGroupNames().map(function (name) {
        // Header shows only if the group has at least one option at all.
        var hasAny = options.some(function (o) {
          return (o._group == null ? "" : String(o._group)) === name;
        });
        if (!hasAny) return "";
        var expanded = searching || !collapsed || !collapsed.has(name);
        var head = '<li class="aigate-combo-group' +
          (expanded ? "" : " aigate-combo-group-collapsed") + '"' +
          ' role="button" tabindex="0" aria-expanded="' + (expanded ? "true" : "false") + '"' +
          ' data-group="' + escapeHtml(name) + '">' + escapeHtml(name) + "</li>";
        if (!expanded) return head; // collapsed: header only, children hidden
        var items = visible.filter(function (o) {
          return (o._group == null ? "" : String(o._group)) === name;
        });
        if (!subGroupBy) {
          // Single-level: render the group's visible children flat.
          return head + items.map(optionHtml).join("");
        }
        // Two-level: combo/flat items (no _sub) render directly under the main
        // header; remaining items are bucketed into sub-groups by _sub.
        var html = head;
        items.filter(function (o) { return o._sub == null; })
          .forEach(function (o) { html += optionHtml(o); });
        orderedSubGroupNames(name, searching).forEach(function (sub) {
          var sKey = name + "\u0001" + sub;
          var subExpanded = searching || !collapsedSub || !collapsedSub.has(sKey);
          var subHead = '<li class="aigate-combo-subgroup' +
            (subExpanded ? "" : " aigate-combo-subgroup-collapsed") + '"' +
            ' role="button" tabindex="0" aria-expanded="' + (subExpanded ? "true" : "false") + '"' +
            ' data-group="' + escapeHtml(name) + '" data-sub="' + escapeHtml(sub) + '">' +
            escapeHtml(sub) + "</li>";
          if (!subExpanded) { html += subHead; return; } // collapsed: sub-header only
          var subItems = items.filter(function (o) {
            return o._sub != null && o._sub === sub;
          });
          html += subHead + subItems.map(optionHtml).join("");
        });
        return html;
      }).join("");
      return groupless.map(optionHtml).join("") + groupHtml;
    }

    function createSearchLi() {
      var li = document.createElement("li");
      li.className = "aigate-combo-searchrow";
      li.setAttribute("role", "presentation");
      li.id = listId + "-search-li";
      var inp = document.createElement("input");
      inp.type = "text";
      inp.className = "aigate-combo-search";
      inp.id = listId + "-search";
      inp.autocomplete = "off";
      try {
        inp.setAttribute("placeholder", getStr("combobox.search_ph"));
        inp.setAttribute("aria-label", getStr("combobox.search_ph"));
      } catch (e) { /* ignore */ }
      li.appendChild(inp);
      return li;
    }

    function render() {
      var ul = list();
      var inp = input();
      var open = isOpen();
      var loading = isLoading();
      if (ul) {
        var bodyHtml;
        if (loading) {
          bodyHtml = '<li class="aigate-combo-msg" role="presentation">' +
            escapeHtml(getStr("combobox.loading")) + "</li>";
        } else if (lastNoMatch) {
          bodyHtml = '<li class="aigate-combo-msg" role="presentation">' +
            escapeHtml(getStr("combobox.no_match")) + "</li>" + renderOptionsHtml();
        } else if (!visible.length && query().trim() !== "") {
          bodyHtml = '<li class="aigate-combo-msg" role="presentation">' +
            escapeHtml(getStr("combobox.no_match")) + "</li>";
        } else {
          bodyHtml = renderOptionsHtml();
        }

        if (!searchInside) {
          ul.innerHTML = bodyHtml;
        } else {
          // Preserve the search <li> node (else focus/caret is lost on every
          // keystroke) — only rebuild the option/group nodes after it.
          var sLi = ul.querySelector(".aigate-combo-searchrow");
          if (!sLi) sLi = createSearchLi();
          if (ul.firstChild !== sLi) ul.insertBefore(sLi, ul.firstChild);
          while (sLi.nextSibling) ul.removeChild(sLi.nextSibling);
          if (bodyHtml) {
            var tmp = document.createElement("div");
            tmp.innerHTML = bodyHtml;
            while (tmp.firstChild) ul.appendChild(tmp.firstChild);
          }
        }
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

    /* ---- fixed, viewport-anchored positioning ----
       The panel is position:fixed (set inline) anchored to the input's viewport
       rect, so it is NOT clipped by an ancestor overflow (e.g. .modal). It flips
       above the input when there is more room above, and its max-height is capped
       to the available space so it never overflows the viewport. No-ops where
       layout metrics are unavailable (jsdom). */
    var MAX_PANEL = 320; // px hard cap
    function position() {
      var ul = list();
      var inp = input();
      if (!ul || !inp) return;
      ul.classList.remove("aigate-combo-up");
      try {
        var rect = inp.getBoundingClientRect();
        var vh = window.innerHeight || (document.documentElement && document.documentElement.clientHeight) || 0;
        var margin = 8, gap = 4, minShow = 120;
        var spaceBelow = vh - rect.bottom - margin;
        var spaceAbove = rect.top - margin;
        var below;
        if (spaceBelow >= minShow && spaceBelow >= spaceAbove) below = true;
        else if (spaceAbove > spaceBelow) below = false;
        else below = true; // fallback when neither fits well
        var avail = below ? spaceBelow : spaceAbove;
        var maxH = Math.max(80, Math.min(MAX_PANEL, avail));
        ul.style.position = "fixed";
        ul.style.left = rect.left + "px";
        ul.style.width = rect.width + "px";
        ul.style.right = "auto";
        ul.style.maxHeight = maxH + "px";
        if (below) {
          ul.style.top = (rect.bottom + gap) + "px";
          ul.style.bottom = "auto";
        } else {
          ul.style.bottom = (vh - rect.top + gap) + "px";
          ul.style.top = "auto";
          ul.classList.add("aigate-combo-up");
        }
      } catch (e) { /* no layout info (jsdom) */ }
    }

    /* ---- open / close ---- */
    function open() {
      var ul = list();
      if (!ul) return;
      if (searchInside) {
        committedValue = topValue();
        var s = searchInput();
        if (s) s.value = ""; // fresh filter -> show everything
      }
      active = -1;
      computeVisible();
      ul.hidden = false;
      render();
      position();
      addPosListeners();
      if (searchInside) {
        var s2 = searchInput();
        if (s2 && typeof s2.focus === "function") s2.focus();
      }
    }

    function close(optsArg) {
      var opts = optsArg || {};
      var ul = list();
      active = -1;
      if (ul) ul.hidden = true;
      removePosListeners();
      if (searchInside && opts.keepValue !== true) {
        // Cancel / Escape / outside-click: revert the shown value to what was
        // committed before this open (the typed-free-text is discarded).
        var inp = input();
        if (inp) inp.value = committedValue;
        var s = searchInput();
        if (s) s.value = "";
      }
      render();
    }

    function cancelClose() {
      if (closeTimer) { clearTimeout(closeTimer); closeTimer = null; }
    }
    function scheduleClose() {
      cancelClose();
      closeTimer = setTimeout(function () { close(); }, CLOSE_DELAY_MS);
    }

    /* ---- selection ---- */
    function selectValue(v) {
      var inp = input();
      if (inp) inp.value = v == null ? "" : String(v);
      if (searchInside) {
        committedValue = inp ? inp.value : "";
        var s = searchInput();
        if (s) { s.value = ""; if (typeof s.blur === "function") s.blur(); }
      }
      close({ keepValue: true });
    }

    /* Toggle a group's collapsed state; re-render keeping the panel open and
       the search input focused. The header lives inside `ul`, so the existing
       mousedown cancel-close logic already keeps the panel from closing.
       Recompute `visible` so the (de)collapsed group's children enter/leave. */
    function toggleGroup(name) {
      if (!collapsed) return;
      if (collapsed.has(name)) collapsed.delete(name);
      else collapsed.add(name);
      computeVisible();
      render();
      if (searchInside) {
        var s = searchInput();
        if (s && typeof s.focus === "function") s.focus();
      }
    }

    /* Toggle a sub-group's collapsed state (two-level grouping). Composite key
        keeps each (group, sub) pair independent. Re-render keeping the panel
        open and the search input focused. */
    function toggleSub(group, sub) {
      if (!collapsedSub) return;
      var key = group + "\u0001" + sub;
      if (collapsedSub.has(key)) collapsedSub.delete(key);
      else collapsedSub.add(key);
      computeVisible();
      render();
      if (searchInside) {
        var s = searchInput();
        if (s && typeof s.focus === "function") s.focus();
      }
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
    function ownsSearch(e) { return e && e.target && e.target.id === listId + "-search"; }

    function onDocInput(e) {
      if (!owns(e) && !ownsSearch(e)) return;
      cancelClose();
      // Mirror the two inputs so they always hold the same filter text.
      if (ownsSearch(e)) {
        var s = searchInput(), i = input();
        if (i && s) i.value = s.value;
      } else {
        var i2 = input(), s2 = searchInput();
        if (s2 && i2) s2.value = i2.value;
      }
      computeVisible();
      active = -1;
      var ul = list();
      if (ul && ul.hidden) { ul.hidden = false; render(); position(); }
      else render();
    }

    function onDocFocusIn(e) {
      if (!owns(e) && !ownsSearch(e)) return;
      cancelClose();
      open();
    }

    function onDocFocusOut(e) {
      if (!owns(e) && !ownsSearch(e)) return;
      scheduleClose();
    }

    function onDocKeydown(e) {
      // Sub-group header (role=button, tabindex=0) reached via Tab: Enter/Space
      // toggles that sub-group's collapse. Check BEFORE the main-group handler.
      if (e.target && e.target.classList && e.target.classList.contains("aigate-combo-subgroup")) {
        var sk = e.key;
        if (sk === "Enter" || sk === " " || sk === "Spacebar") {
          e.preventDefault();
          toggleSub(e.target.getAttribute("data-group"), e.target.getAttribute("data-sub"));
        }
        return;
      }
      // Group header (role=button, tabindex=0) reached via Tab: Enter/Space toggles.
      if (e.target && e.target.classList && e.target.classList.contains("aigate-combo-group")) {
        var gk = e.key;
        if (gk === "Enter" || gk === " " || gk === "Spacebar") {
          e.preventDefault();
          toggleGroup(e.target.getAttribute("data-group"));
        }
        return;
      }
      if (!owns(e) && !ownsSearch(e)) return;
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
        else selectValue(query()); // accept typed free-text value (ADR-011)
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
      // Sub-group header click toggles its collapse (keeps panel open, no close).
      // Check BEFORE the main-group header so a click on a sub-header is not
      // swallowed by the ancestor group's own closest() match.
      var sub = (e.target && typeof e.target.closest === "function")
        ? e.target.closest(".aigate-combo-subgroup") : null;
      if (sub && ul.contains(sub)) {
        e.preventDefault();
        toggleSub(sub.getAttribute("data-group"), sub.getAttribute("data-sub"));
        return;
      }
      // Group header click toggles collapse (keeps panel open, no close).
      var grp = (e.target && typeof e.target.closest === "function")
        ? e.target.closest(".aigate-combo-group") : null;
      if (grp && ul.contains(grp)) {
        e.preventDefault();
        toggleGroup(grp.getAttribute("data-group"));
        return;
      }
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
      removePosListeners();
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
          var label = m.label == null || m.label === "" ? v : String(m.label);
          var grp = null;
          if (groupBy === "prefix") grp = familyOf(v);
          else if (groupBy === "group") grp = (m.group != null) ? String(m.group) : FALLBACK_GROUP;
          // Sub-group derivation (two-level). null when subGroupBy is null, or
          // when the caller explicitly opts this option out via subGroup:false.
          var sub = null;
          if (subGroupBy === "prefix") {
            sub = (m.subGroup === false) ? null : familyOf(label != null ? label : v);
          } else if (subGroupBy === "group") {
            sub = (m.subGroup != null && m.subGroup !== false) ? String(m.subGroup) : null;
          }
          return { value: v, label: label, _group: grp, _sub: sub };
        });
        // Seed collapse state: every group present in the new options that is
        // NOT already TRACKED defaults to collapsed. Previously toggled state is
        // preserved across refreshes (we only ADD unseen groups, never reset).
        // `tracked` is separate from `collapsed` so an expanded (removed-from-
        // collapsed) group is still remembered and not re-collapsed on refresh.
        if (groupBy !== "none" && collapsed && tracked) {
          // Legacy behavior: new groups start collapsed (the user expands them).
          // When startExpanded, leave them expanded so options are visible at once.
          if (!startExpanded) {
            options.forEach(function (o) {
              var g = o._group == null ? "" : String(o._group);
              if (g !== "" && !tracked.has(g)) { tracked.add(g); collapsed.add(g); }
            });
          }
        }
        // Seed sub-group collapse state — mirror of the main-group seeding, keyed
        // by the composite "group\u0001sub" so each (provider, family) pair is
        // independently collapsible and persists across refreshes.
        if (subGroupBy && collapsedSub && trackedSub) {
          options.forEach(function (o) {
            if (o._group == null || o._sub == null) return;
            var key = o._group + "\u0001" + o._sub;
            if (!trackedSub.has(key)) { trackedSub.add(key); collapsedSub.add(key); }
          });
        }
        active = -1;
        computeVisible();
        render();
        if (isOpen()) position();
      },
      setValue: function (v) {
        var inp = input();
        if (inp) inp.value = v == null ? "" : String(v);
        if (searchInside) committedValue = inp ? inp.value : "";
        active = -1;
        computeVisible();
        render();
      },
      /* Re-pin the group order at runtime. Callers that localize a group name
         (e.g. the CLI model picker's combo group) must refresh the pin after a
         locale switch, otherwise the translated group no longer matches the
         creation-time groupOrder and loses its top position. */
      setGroupOrder: function (names) {
        groupOrder = Array.isArray(names) ? names.slice() : [];
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
