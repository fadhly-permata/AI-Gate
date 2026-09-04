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
   ADR-011: every failure surfaces in #comboMemberMsg / #comboMsg — never
    swallowed.

    Model field (auto-fetch): changing #comboMemberProvider (or preselecting a
    provider in edit mode) POSTs /api/providers/{id}/discover, sorts the
    returned models by name (case-insensitive), and repopulates the datalist.
    A loading state (disabled field + Add, aria-busy, spinner, "Loading
    models…" placeholder) shows while fetching; on discover failure it falls
    back to the provider's cached models with a subtle note. A request-sequence
    token drops stale/out-of-order responses (race guard). */

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
     {provider_id:int, provider_model:str, priority:int, weight:float}. */
  function normalizeMember(m) {
    m = m || {};
    var prio = parseInt(m.priority, 10);
    var w = parseFloat(m.weight);
    return {
      provider_id: m.provider_id == null || m.provider_id === ""
        ? null : parseInt(m.provider_id, 10),
      provider_model: m.provider_model == null ? "" : String(m.provider_model).trim(),
      priority: isNaN(prio) ? 0 : prio,
      weight: isNaN(w) ? 1 : w
    };
  }

  function providersById() {
    var map = {};
    providersCache.forEach(function (p) { map[String(p.id)] = p; });
    return map;
  }

  /* ---- DOM helpers ---- */
  function el(id) { return document.getElementById(id); }

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
    body.innerHTML = list.map(function (c) {
      var row = mapComboToRow(c);
      var badge = row.enabled
        ? '<span class="badge badge-ok">' + escapeHtml(getStr("combos.enabled")) + "</span>"
        : '<span class="badge badge-off">' + escapeHtml(getStr("providers.disabled")) + "</span>";
      return '<tr class="combo-row" data-id="' + escapeHtml(row.id) + '">' +
        '<td class="combo-name">' + escapeHtml(row.name) + "</td>" +
        "<td>" + escapeHtml(row.strategy) + "</td>" +
        "<td>" + badge + "</td>" +
        "<td>" + row.memberCount + "</td>" +
        '<td class="row-actions">' +
          '<button type="button" class="icon-btn-small js-edit" title="' + escapeHtml(getStr("combos.edit")) + '">' +
            '<i class="fa fa-pen"></i></button>' +
          '<button type="button" class="icon-btn-small js-del" title="' + escapeHtml(getStr("combos.delete")) + '">' +
            '<i class="fa fa-trash"></i></button>' +
        "</td>" +
      "</tr>";
    }).join("");

    Array.prototype.forEach.call(body.querySelectorAll(".combo-row"), function (tr) {
      var id = tr.getAttribute("data-id");
      tr.querySelector(".js-edit").addEventListener("click", function (e) {
        e.stopPropagation(); openEditModal(id);
      });
      tr.querySelector(".js-del").addEventListener("click", function (e) {
        e.stopPropagation(); deleteCombo(id);
      });
    });
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

  /* Render a (already-sorted) model list into the #comboMemberModelList
     datalist. Empty list -> no options (free-text input still works). */
  function renderModelOptions(models) {
    var dl = el("comboMemberModelList");
    if (!dl) return;
    dl.innerHTML = (models || []).map(function (m) {
      return '<option value="' + escapeHtml(m.model_id) + '">' +
        escapeHtml(m.model_name || m.model_id) + "</option>";
    }).join("");
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

  /* Toggle the sub-form "loading models" state. Deliberately does NOT touch
     the model input's VALUE (so an edit-mode prefill survives); it only
     disables the field + Add button, swaps the placeholder to the loading
     text, shows the spinner, sets aria-busy on the sub-form, and clears the
     datalist options. */
  function setModelLoading(on) {
    var mo = el("comboMemberModel");
    var add = el("comboMemberAddBtn");
    var form = el("comboMemberForm");
    var spinner = el("comboMemberModelSpinner");
    var dl = el("comboMemberModelList");
    if (on) {
      if (mo) { mo.disabled = true; mo.placeholder = getStr("combos.member.loading"); }
      if (add) add.disabled = true;
      if (form) form.setAttribute("aria-busy", "true");
      if (spinner) spinner.hidden = false;
      if (dl) dl.innerHTML = "";
    } else {
      if (mo) { mo.disabled = false; mo.placeholder = getStr("combos.member.model_ph"); }
      if (add) add.disabled = false;
      if (form) form.setAttribute("aria-busy", "false");
      if (spinner) spinner.hidden = true;
    }
  }

  /* Fill the model datalist from the chosen provider's CACHED models, sorted.
     Empty list -> free-text input still works (no options rendered). */
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

  /* ---- Members table render ---- */
  function renderMembers(members, byId) {
    var body = el("comboMembersBody");
    if (!body) return;
    members = members || [];
    byId = byId || providersById();
    if (!members.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell">' +
        escapeHtml(getStr("combos.members.none")) + "</td></tr>";
      return;
    }
    body.innerHTML = members.map(function (m, i) {
      var prov = byId[String(m.provider_id)];
      var pname = prov ? prov.name : ("#" + m.provider_id);
      var idAttr = m.id != null ? ' data-id="' + escapeHtml(m.id) + '"' : "";
      return '<tr class="member-row"' + idAttr + ' data-idx="' + i + '">' +
        "<td>" + escapeHtml(pname) + "</td>" +
        "<td>" + escapeHtml(m.provider_model) + "</td>" +
        "<td>" + escapeHtml(m.priority) + "</td>" +
        "<td>" + escapeHtml(m.weight) + "</td>" +
        '<td class="row-actions">' +
          '<button type="button" class="icon-btn-small js-mem-edit" title="' +
            escapeHtml(getStr("combos.member.edit")) + '"><i class="fa fa-pen"></i></button>' +
          '<button type="button" class="icon-btn-small js-mem-del" title="' +
            escapeHtml(getStr("combos.member.remove")) + '"><i class="fa fa-trash"></i></button>' +
        "</td>" +
      "</tr>";
    }).join("");

    Array.prototype.forEach.call(body.querySelectorAll(".member-row"), function (tr) {
      var idx = parseInt(tr.getAttribute("data-idx"), 10);
      var mid = tr.getAttribute("data-id");
      tr.querySelector(".js-mem-edit").addEventListener("click", function (e) {
        e.stopPropagation(); editMemberRow(mid, idx);
      });
      tr.querySelector(".js-mem-del").addEventListener("click", function (e) {
        e.stopPropagation();
        if (selectedId && mid != null) removeMember(mid);
        else removeMemberLocal(idx);
      });
    });
  }

  /* ---- Sub-form (add member / edit member) ---- */
  function memberFormValues() {
    return normalizeMember({
      provider_id: el("comboMemberProvider") ? el("comboMemberProvider").value : "",
      provider_model: el("comboMemberModel") ? el("comboMemberModel").value : "",
      priority: el("comboMemberPriority") ? el("comboMemberPriority").value : 0,
      weight: el("comboMemberWeight") ? el("comboMemberWeight").value : 1
    });
  }

  function resetMemberForm() {
    editingMemberId = null;
    editingBufferIndex = null;
    modelFetchSeq++; // invalidate any in-flight model fetch (race guard)
    var p = el("comboMemberProvider"); if (p) p.value = "";
    var mo = el("comboMemberModel");
    if (mo) { mo.value = ""; mo.disabled = false; mo.placeholder = getStr("combos.member.model_ph"); }
    var pr = el("comboMemberPriority"); if (pr) pr.value = "0";
    var w = el("comboMemberWeight"); if (w) w.value = "1";
    var dl = el("comboMemberModelList"); if (dl) dl.innerHTML = "";
    var add = el("comboMemberAddBtn");
    if (add) { add.textContent = getStr("combos.member.add"); add.disabled = false; }
    var cancel = el("comboMemberCancelEdit"); if (cancel) cancel.hidden = true;
    var form = el("comboMemberForm"); if (form) form.setAttribute("aria-busy", "false");
    var spinner = el("comboMemberModelSpinner"); if (spinner) spinner.hidden = true;
  }

  function fillMemberForm(m) {
    var p = el("comboMemberProvider");
    if (p) p.value = m.provider_id != null ? String(m.provider_id) : "";
    var mo = el("comboMemberModel"); if (mo) mo.value = m.provider_model || "";
    // Edit-mode preselect: auto-fetch + sort this provider's models. The fetch
    // only repopulates the datalist (loading state never clears the value set
    // above), so the member being edited keeps its model while options refresh.
    fetchModelsForProvider(m.provider_id);
    var pr = el("comboMemberPriority"); if (pr) pr.value = String(m.priority != null ? m.priority : 0);
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
    m = m || memberFormValues();
    m = normalizeMember(m);
    if (m.provider_id == null) {
      setMemberMsg(getStr("combos.member.provider_required"), "error");
      return Promise.resolve();
    }
    if (!selectedId) return Promise.resolve(bufferMemberLocal(m));
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
    return fetchJson(COMBO_API + "/" + selectedId + "/members/" + encodeURIComponent(mid), {
      method: "PUT",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify(normalizeMember(patch))
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
    membersBuffer.push(normalizeMember(m));
    renderMembers(membersBuffer, providersById());
    return membersBuffer.length;
  }

  function removeMemberLocal(i) {
    if (i < 0 || i >= membersBuffer.length) return membersBuffer.length;
    membersBuffer.splice(i, 1);
    renderMembers(membersBuffer, providersById());
    return membersBuffer.length;
  }

  function buildMembersPayload() {
    return membersBuffer.map(normalizeMember);
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
    // NOTE: the provider-change handler is a document-level delegated listener
    // registered at module load (see below) so it survives modal DOM rebuilds.
    // Enter inside the members sub-form adds/updates the member, never saves
    // the whole combo form.
    ["comboMemberProvider", "comboMemberModel", "comboMemberPriority", "comboMemberWeight"]
      .forEach(function (id) {
        var node = el(id);
        if (!node) return;
        node.addEventListener("keydown", function (e) {
          if (e.key === "Enter") { e.preventDefault(); submitMemberForm(); }
        });
      });
    var mo = el("comboMemberModel");
    if (mo) mo.placeholder = getStr("combos.member.model_ph");
  }

  /* ---- Provider change -> auto-fetch + sort models (chained dropdown) ----
     Delegated on `document` and registered ONCE at module load, so it keeps
     working even when the modal DOM is rebuilt (re-renders / tests). Native
     `change` bubbles, so the select inside the modal reaches this handler. */
  document.addEventListener("change", function (e) {
    if (!e.target || e.target.id !== "comboMemberProvider") return;
    // Switching provider clears the stale model value, then fetches fresh.
    var mo = el("comboMemberModel"); if (mo) mo.value = "";
    fetchModelsForProvider(e.target.value);
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
    renderMembers: renderMembers,
    memberFormValues: memberFormValues,
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
