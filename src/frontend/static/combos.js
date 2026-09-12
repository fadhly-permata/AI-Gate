/* ===== aigate Combos management (B2.4 + members editor) — vanilla JS, no build ===== */
/* Spec: FSD §2.3, ADR-001 (no framework). Backend contract: /api/combos
   returns {object:"list", data:[ComboDTO]}. ComboDTO: {id,name,strategy,
   enabled,members:[ComboMemberDTO]}. ComboMemberDTO: {id,combo_id,
   provider_id,provider_model,priority,weight}. CRUD uses fetchJson/escapeHtml/
   getStr exposed on window.aigate by app.js (mirrors Providers, clitools).

   Members editor (9router-style, multi-provider routes):
   * Editing an existing combo (selectedId set): Add/Remove/Edit hit the member
     endpoints POST|DELETE|PUT /api/combos/{id}/members[/{mid}], then the combo
     is reloaded via GET /api/combos/{id} and the list counts refresh.
   * Creating a NEW combo (no id): members are buffered client-side
     (membersBuffer) and sent in one shot in the POST /api/combos body
     `members:[...]` on Save.
   * ORDER IS THE PRIORITY (stage-8): the table has no Priority column and the
     sub-form has no Priority field — the row position IS the queue the engine
     walks (fallback) or breaks ties with (load_balance / latency_cost). ▲▼ per
     row (moveMember) renumbers the visible list to 0..n-1 and PUTs only the
     rows that actually changed, sequentially, then re-reads the server; in
     buffer mode it only moves the array. A NEW member always joins LAST
     (priority = the current count), never at the old default of 0.
   ADR-011: every failure surfaces in #comboMemberMsg / #comboMsg — never
    swallowed.

     Model field (auto-fetch): changing #comboMemberProvider (or preselecting a
     provider in edit mode) POSTs /api/providers/{id}/discover, sorts the
     returned models by name (case-insensitive), and feeds them into the
     SEARCHABLE COMBOBOX on #comboMemberModel (combobox.js: text input +
     custom <ul> panel that filters as you type). A combobox gives BOTH a
     mobile-working dropdown (Android never pops a <datalist>) AND
     type-to-search (impossible in a <select>). Free text is native — the
     input value IS the model string — so undiscovered models and edit-mode
     values round-trip with no sentinel option or extra box.
     A loading state (combobox.setLoading: disabled input + aria-busy +
     "Loading models…" panel row, plus a disabled Add button + spinner) shows
     while fetching; on discover failure it falls back to the provider's
     cached models with a subtle note. A request-sequence token drops
     stale/out-of-order responses (race guard). */

(function () {
  "use strict";

  /* ---- Reuse shared helpers from app.js (or minimal fallbacks) ---- */
  function app() { return window.aigate || {}; }

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

  function fetchJson(url, opts) {
    var a = app();
    if (typeof a.fetchJson === "function") return a.fetchJson(url, opts);
    // Minimal fallback (kept in sync with app.js shape).
    opts = opts || {};
    opts.headers = Object.assign({ "Accept": "application/json" }, opts.headers || {});
    return fetch(url, opts).then(function (r) {
      if (!r.ok) {
        return r.json().then(function (b) {
          var msg = (b && b.error && b.error.message) ? b.error.message : ("HTTP " + r.status);
          var e = new Error(msg); e.status = r.status; throw e;
        }).catch(function () { throw new Error("HTTP " + r.status); });
      }
      return r.json();
    });
  }

  var COMBO_API = "/api/combos";
  var PROVIDERS_API = "/api/providers";
  var selectedId = null;

  /* ---- Members-editor state ---- */
  var providersCache = [];      // GET /api/providers data[]
  var currentMembers = [];      // server members of the combo being edited
  var membersBuffer = [];       // client-side buffer for a NEW combo
  var editingMemberId = null;   // server member id loaded into the sub-form
  var editingBufferIndex = null; // buffer index loaded into the sub-form
  var modelFetchSeq = 0;        // race-guard token for the model auto-fetch
  var modelLoading = false;     // true while a discover fetch is in flight
  var dragState = null;         // active grip-drag: {fromIdx, tr, pointerId}
  var pendingMovedRef = null;   // member object that just moved (drives the move flash)
  var movedFlashTimer = null;   // handle for the transient highlight cleanup

  /* ---- Pure mapping (importable + testable) ---- */
  function mapComboToRow(c) {
    c = c || {};
    return {
      id: c.id,
      name: c.name,
      strategy: c.strategy,
      enabled: !!c.enabled,
      memberCount: Array.isArray(c.members) ? c.members.length : 0
    };
  }

  /* Normalize a member to the backend ComboMemberCreate shape:
     {provider_id:int, provider_model:str, priority:int?, weight:float}.
     `priority` is carried ONLY when the caller supplies one: the sub-form has
     no priority field any more (stage-8 — position is the priority), and a
     partial PUT must leave the stored order of an edited row untouched. */
  function normalizeMember(m) {
    m = m || {};
    var prio = parseInt(m.priority, 10);
    var w = parseFloat(m.weight);
    var out = {
      provider_id: m.provider_id == null || m.provider_id === ""
        ? null : parseInt(m.provider_id, 10),
      provider_model: m.provider_model == null ? "" : String(m.provider_model).trim(),
      weight: isNaN(w) ? 1 : w
    };
    if (m.priority != null && m.priority !== "" && !isNaN(prio)) out.priority = prio;
    return out;
  }

  function providersById() {
    var map = {};
    providersCache.forEach(function (p) { map[String(p.id)] = p; });
    return map;
  }

  /* ---- DOM helpers ---- */
  function el(id) { return document.getElementById(id); }

  /* Respect users who asked for minimal motion: when true, the move flash is
      never started (see renderMembers / scheduleMovedFlash). Guarded so a
      missing or throwing matchMedia can never break the reorder path. */
  function prefersReducedMotion() {
    try {
      return !!(window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    } catch (_) {
      return false;
    }
  }

  function setMsg(text, kind) {
    var m = el("comboMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  function setMemberMsg(text, kind) {
    var m = el("comboMemberMsg");
    if (!m) { setMsg(text, kind); return; }
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  /* Human label for a strategy value; unknown values fall back to raw. */
  function strategyLabel(value) {
    var key = "combos.strategy." + value;
    var s = getStr(key);
    return s === key ? String(value == null ? "" : value) : s;
  }

  /* ---- List + render ---- */
  function loadCombos() {
    setMsg("");
    return fetchJson(COMBO_API).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderCombos(list);
    }).catch(function (err) {
      setMsg(err.message, "error");
    });
  }

  function renderCombos(list) {
    var body = el("comboTableBody");
    if (!body) return;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell">' +
        escapeHtml(getStr("combos.no_items")) + "</td></tr>";
      return;
    }
    var app0 = app();
    body.innerHTML = list.map(function (c) {
      var row = mapComboToRow(c);
      var badge = row.enabled
        ? '<span class="badge badge-ok">' + escapeHtml(getStr("combos.enabled")) + "</span>"
        : '<span class="badge badge-off">' + escapeHtml(getStr("providers.disabled")) + "</span>";
      return '<tr class="combo-row" data-id="' + escapeHtml(row.id) + '">' +
        '<td class="combo-name">' + escapeHtml(row.name) + "</td>" +
        "<td>" + escapeHtml(strategyLabel(row.strategy)) + "</td>" +
        "<td>" + badge + "</td>" +
        "<td>" + row.memberCount + "</td>" +
        (app0.rowMenuCellHtml ? app0.rowMenuCellHtml() : "") +
      "</tr>";
    }).join("");

    if (app0.wireRowMenu) {
      app0.wireRowMenu(body, function (tr) {
        var id = tr ? tr.getAttribute("data-id") : null;
        return [
          { action: "edit", label: getStr("common.edit"), icon: "fa-pen", onClick: function () { openEditModal(id); } },
          { action: "delete", label: getStr("common.delete"), icon: "fa-trash", danger: true, onClick: function () { deleteCombo(id); } }
        ];
      });
    }
  }

  /* ================================================================
   * MEMBERS EDITOR
   * ================================================================ */

  /* ---- Providers dropdown (GET /api/providers) ---- */
  function loadProviders() {
    return fetchJson(PROVIDERS_API).then(function (data) {
      providersCache = (data && data.data) ? data.data : [];
      renderProviderOptions();
      return providersCache;
    }).catch(function (err) {
      // ADR-011: surface, keep the editor usable (free-text model still works).
      setMemberMsg(err.message, "error");
      return [];
    });
  }

  function renderProviderOptions() {
    var sel = el("comboMemberProvider");
    if (!sel) return;
    var keep = sel.value;
    sel.innerHTML = '<option value="">' + escapeHtml(getStr("combos.member.provider_ph")) +
      "</option>" + providersCache.map(function (p) {
        return '<option value="' + escapeHtml(p.id) + '">' + escapeHtml(p.name) + "</option>";
      }).join("");
    sel.value = keep;
  }

  /* Sort a model list by display name, ascending, case-insensitive.
     Sort key = model_name || model_id. Returns a NEW array (never mutates). */
  function sortModelsByName(models) {
    return (Array.isArray(models) ? models : []).slice().sort(function (a, b) {
      var an = String((a && (a.model_name || a.model_id)) || "").toLowerCase();
      var bn = String((b && (b.model_name || b.model_id)) || "").toLowerCase();
      if (an < bn) return -1;
      if (an > bn) return 1;
      return 0;
    });
  }

  /* ---- Model control: searchable combobox (combobox.js) ----
     #comboMemberModel is a text <input> wired to a custom <ul> panel that
     filters as you type (window.aigate.createCombobox). This replaces the old
     <select> + "__custom__" free-text box: the combobox gives a mobile-working
     dropdown AND type-to-search, and free text is native (the input value IS
     the model string), so undiscovered models round-trip with no sentinel.
     The controller is created LAZILY (first use) and resolves its elements by
     id on every call, so it survives modal DOM rebuilds. */
  var memberModelCombo = null;

  function modelCombo() {
    if (!memberModelCombo && typeof app().createCombobox === "function") {
      memberModelCombo = app().createCombobox({
        inputId: "comboMemberModel",
        listId: "comboMemberModelList",
        formId: "comboMemberForm",
        // B: search box as first panel row + group models by prefix
        // (e.g. deepseek-v1 + deepseekv2 -> "Deepseek"). The top input keeps
        // holding the value/free text; see combobox.js.
        searchInside: true,
        groupBy: "prefix"
      });
    }
    return memberModelCombo;
  }

  /* Load a model id into the combobox (known OR custom — the input holds any
     string). Does not open the panel. */
  function setModelValue(value) {
    var c = modelCombo();
    if (c) { c.setValue(value); return; }
    var inp = el("comboMemberModel");
    if (inp) inp.value = value == null ? "" : String(value);
  }

  /* Clear the model control (provider switch / reset). */
  function clearModelSelection() {
    setModelValue("");
  }

  /* Feed an (already-sorted) model list into the combobox as {value,label}.
     The current input value is preserved (free text or a known id). */
  function renderModelOptions(models) {
    var c = modelCombo();
    if (!c) return;
    c.setOptions((models || []).map(function (m) {
      return { value: m.model_id, label: m.model_name || m.model_id };
    }));
  }

  /* Cached models for a provider id (from providersCache), UNSORTED. */
  function cachedModelsFor(providerId) {
    for (var i = 0; i < providersCache.length; i++) {
      if (String(providersCache[i].id) === String(providerId)) {
        return Array.isArray(providersCache[i].models) ? providersCache[i].models : [];
      }
    }
    return [];
  }

  /* Toggle the sub-form "loading models" state. Delegates the field half to
     combobox.setLoading (disables the input, sets aria-busy on input/list/
     form, swaps the placeholder + shows a "Loading models…" panel row); this
     also disables the Add button and shows the spinner. It never touches the
     selected model VALUE, so an edit-mode prefill survives the fetch. */
  function setModelLoading(on) {
    modelLoading = !!on;
    var c = modelCombo();
    if (c) c.setLoading(modelLoading);
    var add = el("comboMemberAddBtn");
    var form = el("comboMemberForm");
    var spinner = el("comboMemberModelSpinner");
    if (modelLoading) {
      if (add) add.disabled = true;
      if (form) form.setAttribute("aria-busy", "true");
      if (spinner) spinner.hidden = false;
    } else {
      if (add) add.disabled = false;
      if (form) form.setAttribute("aria-busy", "false");
      if (spinner) spinner.hidden = true;
    }
  }

  /* Fill the model combobox from the chosen provider's CACHED models, sorted.
     Empty list -> no options (free-text still works — the input IS the value). */
  function populateModelOptions(providerId) {
    var models = sortModelsByName(cachedModelsFor(providerId));
    renderModelOptions(models);
    return models;
  }

  /* Apply a sorted model list as the FALLBACK path (discover failed): render
     it, clear loading, and surface a subtle note. Stale requests are ignored. */
  function applyFallback(seq, models) {
    if (seq !== modelFetchSeq) return models; // a newer fetch owns the UI now
    renderModelOptions(models);
    setModelLoading(false);
    setMemberMsg(getStr("combos.member.load_failed"), "warn");
    return models;
  }

  /* Fallback chain: providersCache first; if it has no models for this
     provider, GET /api/providers/{id}; if that fails too, empty (free-text). */
  function fallbackFromCache(providerId, seq) {
    var cached = sortModelsByName(cachedModelsFor(providerId));
    if (cached.length) return applyFallback(seq, cached);
    return fetchJson(PROVIDERS_API + "/" + encodeURIComponent(providerId)).then(function (p) {
      return applyFallback(seq, sortModelsByName((p && Array.isArray(p.models)) ? p.models : []));
    }).catch(function () {
      return applyFallback(seq, []);
    });
  }

  /* Auto-fetch a provider's models on demand:
       loading -> POST /discover -> sort -> populate -> (fallback) -> clear.
     Race-guarded via modelFetchSeq: only the most-recent request may touch the
     DOM, so out-of-order responses from a fast provider switch are dropped.
     Returns a Promise<models[]>. */
  function fetchModelsForProvider(providerId) {
    // No provider selected: clear options + invalidate any in-flight fetch.
    if (providerId === "" || providerId == null) {
      modelFetchSeq++;
      renderModelOptions([]);
      setModelLoading(false);
      return Promise.resolve([]);
    }
    var seq = ++modelFetchSeq;
    setModelLoading(true);
    return fetchJson(PROVIDERS_API + "/" + encodeURIComponent(providerId) + "/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" }
    }).then(function (res) {
      if (seq !== modelFetchSeq) return []; // stale — a newer fetch won
      if (res && res.ok === true && Array.isArray(res.models)) {
        // Keep the cache fresh so a later fallback reflects this discovery.
        for (var i = 0; i < providersCache.length; i++) {
          if (String(providersCache[i].id) === String(providerId)) {
            providersCache[i].models = res.models; break;
          }
        }
        var models = sortModelsByName(res.models);
        renderModelOptions(models);
        setModelLoading(false);
        return models;
      }
      // {ok:false} (e.g. no network) -> fall back to cached models.
      return fallbackFromCache(providerId, seq);
    }).catch(function () {
      if (seq !== modelFetchSeq) return []; // stale
      return fallbackFromCache(providerId, seq); // transport error -> fallback
    });
  }

  /* Remove the transient `just-moved` highlight once it has played, so the next
      render starts clean. Uses a single timer; re-entrancy-safe via clearTimeout.
      Under reduced motion the class is never added, so this is a no-op there. */
  function scheduleMovedFlash(body) {
    var row = body ? body.querySelector("tr.member-row.just-moved") : null;
    if (!row) return;
    if (movedFlashTimer) { clearTimeout(movedFlashTimer); movedFlashTimer = null; }
    movedFlashTimer = setTimeout(function () {
      var r = body.querySelector("tr.member-row.just-moved");
      if (r) r.classList.remove("just-moved");
      movedFlashTimer = null;
    }, 650);
  }

  /* ---- Members table render ----
      There is no Priority column: the ROW ORDER is the priority (stage-8), and
      ▲▼ in the action cell is the only way to change it — the same affordance as
      the account cards on the provider page. */
  function renderMembers(members, byId) {
    var body = el("comboMembersBody");
    if (!body) return;
    members = members || [];
    byId = byId || providersById();
    // Capture the move marker for THIS render, then clear it so it can only ever
    // highlight the single row of the single move that just happened.
    var movedRef = pendingMovedRef;
    pendingMovedRef = null;
    if (!members.length) {
      body.innerHTML = '<tr><td colspan="4" class="empty-cell">' +
        escapeHtml(getStr("combos.members.none")) + "</td></tr>";
      return;
    }
    var total = members.length;
    body.innerHTML = members.map(function (m, i) {
      // Flash the row that just moved (▲▼ OR drag). Matched by object reference
      // in buffer mode, by id after a server reload (new objects from JSON).
      var movedCls = (movedRef && !prefersReducedMotion() &&
        (m === movedRef ||
         (m.id != null && movedRef.id != null &&
          String(m.id) === String(movedRef.id))))
        ? " just-moved" : "";
      var prov = byId[String(m.provider_id)];
      var pname = prov ? prov.name : ("#" + m.provider_id);
      var idAttr = m.id != null ? ' data-id="' + escapeHtml(m.id) + '"' : "";
      // Boundary buttons: aria-disabled + a title that says WHY (never a dead
      // tap that pretends nothing happened) — same contract as the account cards.
      var upOff = i === 0;
      var downOff = i === total - 1;
      var upLbl = getStr("combos.member.move_up");
      var downLbl = getStr("combos.member.move_down");
      var dragLbl = getStr("combos.member.drag");
      var upAttrs = 'aria-label="' + escapeHtml(upLbl) + '" title="' +
        escapeHtml(upOff ? getStr("combos.member.already_first") : upLbl) + '"' +
        (upOff ? ' aria-disabled="true"' : "");
      var downAttrs = 'aria-label="' + escapeHtml(downLbl) + '" title="' +
        escapeHtml(downOff ? getStr("combos.member.already_last") : downLbl) + '"' +
        (downOff ? ' aria-disabled="true"' : "");
      return '<tr class="member-row' + movedCls + '"' + idAttr + ' data-idx="' + i + '">' +
        '<td>' +
          '<button type="button" class="icon-btn-small js-mem-drag"' +
            ' aria-label="' + escapeHtml(dragLbl) + '" title="' + escapeHtml(dragLbl) + '">' +
            '<i class="fa fa-grip-vertical" aria-hidden="true"></i></button>' +
          escapeHtml(pname) +
        "</td>" +
        "<td>" + escapeHtml(m.provider_model) + "</td>" +
        "<td>" + escapeHtml(m.weight) + "</td>" +
        '<td class="row-actions">' +
          '<span class="member-move">' +
            '<button type="button" class="icon-btn-small js-mem-up"' + upAttrs + '>' +
              '<i class="fa fa-arrow-up" aria-hidden="true"></i></button>' +
            '<button type="button" class="icon-btn-small js-mem-down"' + downAttrs + '>' +
              '<i class="fa fa-arrow-down" aria-hidden="true"></i></button>' +
          "</span>" +
          '<button type="button" class="icon-btn-small js-mem-edit" title="' +
            escapeHtml(getStr("combos.member.edit")) + '"><i class="fa fa-pen"></i></button>' +
          '<button type="button" class="icon-btn-small js-mem-del" title="' +
            escapeHtml(getStr("combos.member.remove")) + '"><i class="fa fa-trash"></i></button>' +
        "</td>" +
      "</tr>";
    }).join("");

    /* ONE delegated listener per tbody — renderMembers re-writes the rows after
       every mutation but the tbody node itself survives, hence the wiring guard
       (same pattern as #accList in app.js). */
    if (body.getAttribute("data-mem-wired") !== "1") {
      body.setAttribute("data-mem-wired", "1");
      body.addEventListener("click", function (e) {
        // The grip is drag-only: a click (or its synthetic click after a drag)
        // must never be read as an arrow/edit/delete action.
        if (e.target.closest && e.target.closest(".js-mem-drag")) return;
        var tr = e.target.closest ? e.target.closest(".member-row") : null;
        if (!tr) return;
        var idx = parseInt(tr.getAttribute("data-idx"), 10);
        if (isNaN(idx)) return;
        var mid = tr.getAttribute("data-id");
        if (e.target.closest(".js-mem-edit")) { editMemberRow(mid, idx); return; }
        if (e.target.closest(".js-mem-del")) {
          if (selectedId && mid != null) removeMember(mid);
          else removeMemberLocal(idx);
          return;
        }
        var up = e.target.closest(".js-mem-up");
        var down = e.target.closest(".js-mem-down");
        // aria-disabled buttons explain themselves and never hit the network.
        if (up && up.getAttribute("aria-disabled") !== "true") moveMember(idx, -1);
        else if (down && down.getAttribute("aria-disabled") !== "true") moveMember(idx, 1);
      });
      // Drag-to-reorder (handle only, not the row) — Pointer Events so the same
      // path serves touch + mouse. startDrag guards on .js-mem-drag itself.
      body.addEventListener("pointerdown", startDrag);
    }

    // Transient highlight on the row that just moved (▲▼ OR drag). Purely
    // cosmetic — never touches the order logic or the wiring above.
    if (movedRef && !prefersReducedMotion()) scheduleMovedFlash(body);
  }

  /* ---- Priority = row order (stage-8) ----
     The SAME contract as moveAccount() on the provider page (app.js): swap i
     with i±1, normalise the visible list to priority = 0..n-1, PUT only the
     rows whose stored value actually changes, do it SEQUENTIALLY (a
     deterministic order on the server beats n requests landing in any order),
     then ALWAYS re-read the server — after a partial failure the view must
     show the truth, not the order the user tried to create.
     Buffer mode (a new, unsaved combo) is array-only: zero requests, and the
     position becomes the priority when the combo is saved (buildMembersPayload).
     An untouched combo is never renumbered: the first ▲▼ is what normalises it. */
  /* ---- Shared reorder contract (used by BOTH ▲▼ AND drag) ----
      `newOrder` is the desired final member list (full array, in display order).
      The function normalises it to priority = 0..n-1, then PUTs ONLY the rows
      whose stored number actually changed, SEQUENTIALLY, then re-reads the
      server — the one contract stage-8 mandates (same as moveAccount in app.js).
      Buffer mode (new, unsaved combo) is array-only: zero requests, and the
      edited row's index is followed so "Update member" cannot land wrong. */
  function applyOrderAndPersist(newOrder) {
    newOrder = newOrder || [];

    if (!selectedId) {
      // A sub-form edit in buffer mode is keyed by INDEX: follow the row the
      // user just moved, so "Update member" cannot land on the wrong one.
      if (editingBufferIndex != null) {
        var oldItem = membersBuffer[editingBufferIndex];
        for (var k = 0; k < newOrder.length; k++) {
          if (newOrder[k] === oldItem) { editingBufferIndex = k; break; }
        }
      }
      membersBuffer = newOrder.slice();
      renderMembers(membersBuffer, providersById());
      return Promise.resolve();
    }

    var changed = [];
    newOrder.forEach(function (m, i) {
      var cur = parseInt(m.priority, 10);
      if (isNaN(cur)) cur = 0;
      if (cur !== i) changed.push({ id: m.id, priority: i });
    });
    if (!changed.length) return reloadCombo();
    setMemberMsg("");
    var chain = Promise.resolve();
    changed.forEach(function (c) {
      chain = chain.then(function () {
        return fetchJson(COMBO_API + "/" + selectedId + "/members/" +
          encodeURIComponent(c.id), {
            method: "PUT",
            headers: { "Content-Type": "application/json", "Accept": "application/json" },
            // Partial PUT: the endpoint updates only the fields it receives.
            body: JSON.stringify({ priority: c.priority })
          });
      });
    });
    return chain.then(function () {
      return reloadCombo();
    }).catch(function (err) {
      // Re-read first, message second: the reload must never erase the reason.
      return reloadCombo().then(function () { setMemberMsg(err.message, "error"); });
    });
  }

  /* Move one row by ±1 (the ▲▼ buttons). Builds the swapped array and hands the
      whole thing to applyOrderAndPersist — no third code path for the order. */
  function moveMember(index, dir) {
    var list = selectedId ? currentMembers : membersBuffer;
    var target = index + dir;
    if (index < 0 || target < 0 || target >= list.length) return Promise.resolve();
    var order = list.slice();
    var swap = order[index];
    order[index] = order[target];
    order[target] = swap;
    pendingMovedRef = swap; // flash the row that changed position
    return applyOrderAndPersist(order);
  }

  /* Drag-to-reorder: move the row at `fromIdx` to the slot `insertIdx` (an
      insertion position in the ORIGINAL order — 0..n; `n` = the very end).
      Delegates the renumber/PUT/reload to the SAME applyOrderAndPersist used by
      ▲▼, so the two affordances can never drift apart. A no-op move (drop on the
      same row) returns cleanly with no request. */
  function reorderMembers(fromIdx, insertIdx) {
    var list = selectedId ? currentMembers : membersBuffer;
    if (fromIdx < 0 || fromIdx >= list.length) return Promise.resolve();
    if (insertIdx < 0) insertIdx = 0;
    if (insertIdx > list.length) insertIdx = list.length;
    var order = list.slice();
    var item = order.splice(fromIdx, 1)[0];
    if (insertIdx > fromIdx) insertIdx--; // removal shifts later indices left
    order.splice(insertIdx, 0, item);
    // No actual move (dropped back where it started, or past an edge that lands
    // on the same slot) = the SAME boundary no-op as an out-of-range ▲▼: zero
    // requests, no reload.
    var unchanged = order.length === list.length;
    for (var i = 0; unchanged && i < order.length; i++) {
      if (order[i] !== list[i]) unchanged = false;
    }
    if (unchanged) return Promise.resolve();
    pendingMovedRef = item; // flash the row that changed position
    return applyOrderAndPersist(order);
  }

  /* Where would a pointer at clientY drop the dragged row? Returns the insertion
      index = the first row whose vertical midpoint lies below the pointer (so the
      dragged row lands just above it); past the last row = the end. Pure of the
      DOM except getBoundingClientRect, hence unit-testable with stubbed rects. */
  function computeDropIndex(rows, clientY) {
    if (!rows || !rows.length) return null;
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i].getBoundingClientRect();
      if (clientY < (r.top || 0) + (r.height || 0) / 2) return i;
    }
    return rows.length - 1;
  }

  /* ---- Grip drag (Pointer Events: touch + mouse, ONE path) ----
      Only the .js-mem-drag handle starts a drag — the row itself stays a normal
      row (arrow buttons / edit / delete keep working). preventDefault on
      pointerdown stops the table scrolling and suppresses the trailing click so
      the grip never masquerades as an arrow/edit/delete tap. */
  function startDrag(e) {
    if (!e.target || !e.target.closest) return;
    var handle = e.target.closest(".js-mem-drag");
    if (!handle) return;
    var tr = e.target.closest(".member-row");
    if (!tr) return;
    var fromIdx = parseInt(tr.getAttribute("data-idx"), 10);
    if (isNaN(fromIdx)) return;
    e.preventDefault();
    if (typeof tr.setPointerCapture === "function" && e.pointerId != null) {
      try { tr.setPointerCapture(e.pointerId); } catch (_) {}
    }
    dragState = { fromIdx: fromIdx, tr: tr, pointerId: e.pointerId };
    if (tr) tr.classList.add("is-dragging"); // minimal in-drag feedback (token tint)
    document.addEventListener("pointermove", onGripPointerMove);
    document.addEventListener("pointerup", onGripPointerUp);
    document.addEventListener("pointercancel", onGripPointerUp);
  }

  function onGripPointerMove(e) {
    if (!dragState) return;
    // Keep the table from scrolling under a finger while a row is being dragged.
    e.preventDefault();
  }

  function onGripPointerUp(e) {
    if (!dragState) return;
    document.removeEventListener("pointermove", onGripPointerMove);
    document.removeEventListener("pointerup", onGripPointerUp);
    document.removeEventListener("pointercancel", onGripPointerUp);
    var from = dragState.fromIdx;
    var tr = dragState.tr;
    if (tr) tr.classList.remove("is-dragging");
    if (tr && typeof tr.releasePointerCapture === "function" && dragState.pointerId != null) {
      try { tr.releasePointerCapture(dragState.pointerId); } catch (_) {}
    }
    dragState = null;
    var body = el("comboMembersBody");
    var rows = body ? Array.prototype.slice.call(body.querySelectorAll("tr.member-row")) : [];
    var insertIdx = computeDropIndex(rows, e.clientY != null ? e.clientY : 0);
    if (insertIdx != null && insertIdx !== from) reorderMembers(from, insertIdx);
  }

  /* ---- Sub-form (add member / edit member) ---- */

  /* Effective model: the combobox value — a chosen option's id OR free text
     typed into the input ("" = nothing entered). No sentinel to resolve. */
  function modelFieldValue() {
    var c = modelCombo();
    if (c) return c.getValue();
    var inp = el("comboMemberModel");
    return inp ? String(inp.value || "").trim() : "";
  }

  /* What the sub-form owns: provider + model + weight. NO priority — that is
     the row's position (▲▼ / save order), never a typed number. */
  function memberFormValues() {
    return normalizeMember({
      provider_id: el("comboMemberProvider") ? el("comboMemberProvider").value : "",
      provider_model: modelFieldValue(),
      weight: el("comboMemberWeight") ? el("comboMemberWeight").value : 1
    });
  }

  /* The queue index a NEW member joins at: the END of the current list. With
     the old default (0) a new member jumped the retry queue. */
  function appendPriority() {
    return (selectedId ? currentMembers : membersBuffer).length;
  }

  function resetMemberForm() {
    editingMemberId = null;
    editingBufferIndex = null;
    modelFetchSeq++; // invalidate any in-flight model fetch (race guard)
    var p = el("comboMemberProvider"); if (p) p.value = "";
    renderModelOptions([]);   // clear the combobox option list
    clearModelSelection();    // blank the input
    var c = modelCombo(); if (c) c.close(); // never leave the panel open
    var w = el("comboMemberWeight"); if (w) w.value = "1";
    var add = el("comboMemberAddBtn");
    if (add) { add.textContent = getStr("combos.member.add"); add.disabled = false; }
    var cancel = el("comboMemberCancelEdit"); if (cancel) cancel.hidden = true;
    var form = el("comboMemberForm"); if (form) form.setAttribute("aria-busy", "false");
    var spinner = el("comboMemberModelSpinner"); if (spinner) spinner.hidden = true;
    setModelLoading(false);   // re-enable the combobox input, reset placeholder
  }

  function fillMemberForm(m) {
    m = m || {};
    var p = el("comboMemberProvider");
    if (p) p.value = m.provider_id != null ? String(m.provider_id) : "";
    // Put the member's model into the combobox. Known OR custom both work:
    // the input holds any string, so an undiscovered model round-trips.
    setModelValue(m.provider_model);
    // Edit-mode preselect: auto-fetch + sort this provider's models. The fetch
    // only repopulates the option list (the loading state never clears the
    // value set above), so the member being edited keeps its model while the
    // searchable list refreshes beneath it.
    fetchModelsForProvider(m.provider_id);
    var w = el("comboMemberWeight"); if (w) w.value = String(m.weight != null ? m.weight : 1);
    var add = el("comboMemberAddBtn");
    if (add) add.textContent = getStr("combos.member.update");
    var cancel = el("comboMemberCancelEdit"); if (cancel) cancel.hidden = false;
  }

  /* Row Edit -> load into sub-form (server mode by id, buffer mode by index). */
  function editMemberRow(mid, idx) {
    var list = selectedId ? currentMembers : membersBuffer;
    var m = null;
    for (var i = 0; i < list.length; i++) {
      if (selectedId ? String(list[i].id) === String(mid) : i === idx) { m = list[i]; break; }
    }
    if (!m) return;
    if (selectedId) editingMemberId = m.id; else editingBufferIndex = idx;
    setMemberMsg("");
    fillMemberForm(m);
  }

  /* Add/Update button: routes to the right mode. */
  function submitMemberForm() {
    var m = memberFormValues();
    if (m.provider_id == null || isNaN(m.provider_id)) {
      setMemberMsg(getStr("combos.member.provider_required"), "error");
      return Promise.resolve();
    }
    // Empty combobox (nothing picked or typed) -> no model.
    if (!m.provider_model) {
      setMemberMsg(getStr("combos.member.model_required"), "error");
      return Promise.resolve();
    }
    if (selectedId) {
      if (editingMemberId != null) {
        var eid = editingMemberId;
        return saveMember(eid, m).then(resetMemberForm);
      }
      return addMember(m);
    }
    // New-combo mode: pure client-side buffer.
    if (editingBufferIndex != null) {
      membersBuffer[editingBufferIndex] = m;
      renderMembers(membersBuffer, providersById());
    } else {
      bufferMemberLocal(m);
    }
    resetMemberForm();
    return Promise.resolve();
  }

  /* ---- Server mode (existing combo): POST|PUT|DELETE + reload ---- */
  function addMember(m) {
    m = normalizeMember(m || memberFormValues());
    if (m.provider_id == null) {
      setMemberMsg(getStr("combos.member.provider_required"), "error");
      return Promise.resolve();
    }
    if (!m.provider_model) {
      setMemberMsg(getStr("combos.member.model_required"), "error");
      return Promise.resolve();
    }
    if (!selectedId) return Promise.resolve(bufferMemberLocal(m));
    // A new member goes LAST: priority = how many members there are now.
    m.priority = appendPriority();
    setMemberMsg("");
    return fetchJson(COMBO_API + "/" + selectedId + "/members", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(m)
    }).then(function () {
      resetMemberForm();
      return reloadCombo();
    }).catch(function (err) { setMemberMsg(err.message, "error"); });
  }

  function saveMember(mid, patch) {
    if (!selectedId) return Promise.resolve();
    setMemberMsg("");
    // Partial PUT: whatever the caller did not send (notably priority, which the
    // form no longer has) keeps its stored value on the server.
    var body = normalizeMember(patch);
    return fetchJson(COMBO_API + "/" + selectedId + "/members/" + encodeURIComponent(mid), {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(body)
    }).then(function () {
      return reloadCombo();
    }).catch(function (err) { setMemberMsg(err.message, "error"); });
  }

  function removeMember(mid) {
    if (!selectedId) return Promise.resolve();
    if (!window.confirm(getStr("combos.member.confirm_delete"))) return Promise.resolve();
    setMemberMsg("");
    return fetchJson(COMBO_API + "/" + selectedId + "/members/" + encodeURIComponent(mid), {
      method: "DELETE"
    }).then(function () {
      return reloadCombo();
    }).catch(function (err) { setMemberMsg(err.message, "error"); });
  }

  /* Re-fetch the combo after a member mutation: re-render members + refresh
     the list (member counts). */
  function reloadCombo() {
    if (!selectedId) return Promise.resolve();
    return fetchJson(COMBO_API + "/" + selectedId).then(function (c) {
      currentMembers = Array.isArray(c.members) ? c.members : [];
      renderMembers(currentMembers, providersById());
      return loadCombos();
    }).catch(function (err) { setMemberMsg(err.message, "error"); });
  }

  /* ---- Buffer mode (new combo): local array ops, sent on Save ---- */
  function bufferMemberLocal(m) {
    // Same join rule as the server path: a new member goes at the END.
    var buf = normalizeMember(m);
    buf.priority = appendPriority();
    membersBuffer.push(buf);
    renderMembers(membersBuffer, providersById());
    return membersBuffer.length;
  }

  function removeMemberLocal(i) {
    if (i < 0 || i >= membersBuffer.length) return membersBuffer.length;
    membersBuffer.splice(i, 1);
    renderMembers(membersBuffer, providersById());
    return membersBuffer.length;
  }

  /* Position IS the priority for a combo being created: the payload is numbered
     0..n-1 in the order the user sees, so a buffer-mode ▲▼ move (array only,
     zero requests) is what lands on the server. */
  function buildMembersPayload() {
    return membersBuffer.map(function (m, i) {
      var v = normalizeMember(m);
      v.priority = i;
      return v;
    });
  }

  /* ---- Modal (add / edit) ---- */
  function hideModal() { var m = el("comboModal"); if (m) m.hidden = true; }

  function openAddModal() {
    selectedId = null;
    var f = el("comboForm"); if (f) f.reset();
    var idEl = el("comboId"); if (idEl) idEl.value = "";
    membersBuffer = [];
    currentMembers = [];
    resetMemberForm();
    renderMembers([], providersById());
    var t = el("comboModalTitle"); if (t) t.textContent = getStr("combos.add");
    var m = el("comboModal"); if (m) m.hidden = false;
    return loadProviders();
  }

  function openEditModal(id) {
    return fetchJson(COMBO_API + "/" + id).then(function (c) {
      selectedId = id;
      var idEl = el("comboId"); if (idEl) idEl.value = c.id;
      var n = el("comboName"); if (n) n.value = c.name != null ? c.name : "";
      var s = el("comboStrategy"); if (s) s.value = c.strategy || "fallback";
      var en = el("comboEnabled"); if (en) en.checked = !!c.enabled;
      currentMembers = Array.isArray(c.members) ? c.members : [];
      membersBuffer = [];
      resetMemberForm();
      renderMembers(currentMembers, providersById());
      var t = el("comboModalTitle"); if (t) t.textContent = getStr("combos.edit");
      var m = el("comboModal"); if (m) m.hidden = false;
      // Provider names resolve once the providers list arrives.
      return loadProviders().then(function () {
        renderMembers(currentMembers, providersById());
      });
    }).catch(function (err) { setMsg(err.message, "error"); });
  }

  function saveCombo(e) {
    if (e) e.preventDefault();
    var id = el("comboId") ? el("comboId").value : "";
    var body = {
      name: el("comboName") ? el("comboName").value : "",
      strategy: el("comboStrategy") ? el("comboStrategy").value : "fallback",
      enabled: el("comboEnabled") ? el("comboEnabled").checked : true
    };
    setMsg("");
    var req = id
      ? fetchJson(COMBO_API + "/" + id, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        })
      : fetchJson(COMBO_API, {
          method: "POST", headers: { "Content-Type": "application/json" },
          // One-shot create: combo meta + buffered members (9router-style).
          body: JSON.stringify(Object.assign({}, body, { members: buildMembersPayload() }))
        });
    req.then(function () {
      membersBuffer = [];
      hideModal(); loadCombos();
    }).catch(function (err) { setMsg(err.message, "error"); });
  }

  function deleteCombo(id) {
    if (!window.confirm(getStr("combos.confirm_delete"))) return;
    fetchJson(COMBO_API + "/" + id, { method: "DELETE" })
      .then(function () { loadCombos(); })
      .catch(function (err) { setMsg(err.message, "error"); });
  }

  /* ---- Wire up ---- */
  function init() {
    var add = el("comboAddBtn");
    if (add) add.addEventListener("click", openAddModal);
    var form = el("comboForm");
    if (form) form.addEventListener("submit", saveCombo);
    var cancel = el("comboCancel");
    if (cancel) cancel.addEventListener("click", hideModal);
    var modal = el("comboModal");
    if (modal) modal.addEventListener("click", function (e) {
      if (e.target === modal) hideModal(); // click backdrop closes
    });

    // Members sub-form wiring.
    var memAdd = el("comboMemberAddBtn");
    if (memAdd) memAdd.addEventListener("click", function (e) {
      e.preventDefault(); submitMemberForm();
    });
    var memCancel = el("comboMemberCancelEdit");
    if (memCancel) memCancel.addEventListener("click", function (e) {
      e.preventDefault(); resetMemberForm();
    });
    // NOTE: the provider-change handler AND the model Enter-to-add handler are
    // document-level delegated listeners registered at module load (see below)
    // so they survive modal DOM rebuilds.
    // Enter inside the OTHER sub-form fields adds/updates the member, never
    // saves the whole combo form. (The model combobox is handled separately,
    // delegated, because it owns Enter while its panel is open.)
    ["comboMemberProvider", "comboMemberWeight"]
      .forEach(function (id) {
        var node = el(id);
        if (!node) return;
        node.addEventListener("keydown", function (e) {
          if (e.key === "Enter") { e.preventDefault(); submitMemberForm(); }
        });
      });
    // The combobox input carries the "Search or type a model…" hint (set by
    // combobox.js on creation); no separate free-text box anymore.
    modelCombo(); // create the controller now that the DOM exists (guarded)
  }

  /* ---- Provider change -> auto-fetch + sort models (chained dropdown) ----
     Delegated on `document` and registered ONCE at module load, so it keeps
     working even when the modal DOM is rebuilt (re-renders / tests). Native
     `change` bubbles, so the select inside the modal reaches this handler. */
  document.addEventListener("change", function (e) {
    if (!e.target) return;
    if (e.target.id === "comboMemberProvider") {
      // Switching provider clears the stale model value, then fetches fresh.
      clearModelSelection();
      fetchModelsForProvider(e.target.value);
    }
  });

  /* ---- Model combobox Enter -> add/update member ONLY when the panel is
     closed. When the panel is OPEN the combobox consumes Enter to pick the
     highlighted option / accept free text (it stopPropagation()s), so this
     delegated handler must not also fire. Registered on `document` at module
     load so it survives DOM rebuilds; runs before the combobox's own listener
     (registered later, on first modelCombo() call) — hence the isOpen() guard
     reads the panel state as it was BEFORE this Enter key. */
  document.addEventListener("keydown", function (e) {
    if (!e.target || e.target.id !== "comboMemberModel") return;
    if (e.key !== "Enter") return;
    if (memberModelCombo && memberModelCombo.isOpen()) return; // combobox owns it
    e.preventDefault();
    submitMemberForm();
  });

  /* ---- Expose hook for app.js nav handler + tests ---- */
  window.aigate = window.aigate || {};
  window.aigate.combos = {
    onShow: loadCombos,
    loadCombos: loadCombos,
    renderCombos: renderCombos,
    mapComboToRow: mapComboToRow,
    // Members editor (testable helpers — callable with stubbed fetch).
    loadProviders: loadProviders,
    renderProviderOptions: renderProviderOptions,
    populateModelOptions: populateModelOptions,
    fetchModelsForProvider: fetchModelsForProvider,
    sortModelsByName: sortModelsByName,
    setModelLoading: setModelLoading,
    // Model control helpers (searchable combobox, combobox.js).
    setModelValue: setModelValue,
    modelFieldValue: modelFieldValue,
    renderModelOptions: renderModelOptions,
    getModelCombobox: modelCombo,
    renderMembers: renderMembers,
    moveMember: moveMember,
    applyOrderAndPersist: applyOrderAndPersist,
    reorderMembers: reorderMembers,
    computeDropIndex: computeDropIndex,
    memberFormValues: memberFormValues,
    fillMemberForm: fillMemberForm,
    submitMemberForm: submitMemberForm,
    resetMemberForm: resetMemberForm,
    addMember: addMember,
    saveMember: saveMember,
    removeMember: removeMember,
    reloadCombo: reloadCombo,
    bufferMemberLocal: bufferMemberLocal,
    removeMemberLocal: removeMemberLocal,
    buildMembersPayload: buildMembersPayload,
    openAddModal: openAddModal,
    openEditModal: openEditModal,
    saveCombo: saveCombo,
    normalizeMember: normalizeMember,
    providersById: providersById,
    getMembersBuffer: function () { return membersBuffer.slice(); },
    getCurrentMembers: function () { return currentMembers.slice(); },
    getSelectedId: function () { return selectedId; }
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
