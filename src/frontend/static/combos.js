/* ===== aigate Combos management (B2.4) — vanilla JS, no build ===== */
/* Spec: FSD §2.3, ADR-001 (no framework). Backend contract: /api/combos
   returns {object:"list", data:[ComboDTO]}. ComboDTO: {id,name,strategy,
   enabled,members:[ComboMemberDTO]}. CRUD uses fetchJson/escapeHtml/getStr
   exposed on window.aigate by app.js (mirrors Providers, clitools). */

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
  var selectedId = null;

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

  /* ---- DOM helpers ---- */
  function el(id) { return document.getElementById(id); }

  function setMsg(text, kind) {
    var m = el("comboMsg");
    if (!m) return;
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

  /* ---- Modal (add / edit) ---- */
  function hideModal() { var m = el("comboModal"); if (m) m.hidden = true; }

  function openAddModal() {
    selectedId = null;
    var f = el("comboForm"); if (f) f.reset();
    var idEl = el("comboId"); if (idEl) idEl.value = "";
    var t = el("comboModalTitle"); if (t) t.textContent = getStr("combos.add");
    var m = el("comboModal"); if (m) m.hidden = false;
  }

  function openEditModal(id) {
    fetchJson(COMBO_API + "/" + id).then(function (c) {
      selectedId = id;
      var idEl = el("comboId"); if (idEl) idEl.value = c.id;
      var n = el("comboName"); if (n) n.value = c.name != null ? c.name : "";
      var s = el("comboStrategy"); if (s) s.value = c.strategy || "fallback";
      var en = el("comboEnabled"); if (en) en.checked = !!c.enabled;
      var t = el("comboModalTitle"); if (t) t.textContent = getStr("combos.edit");
      var m = el("comboModal"); if (m) m.hidden = false;
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
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        });
    req.then(function () { hideModal(); loadCombos(); })
       .catch(function (err) { setMsg(err.message, "error"); });
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
  }

  /* ---- Expose hook for app.js nav handler + tests ---- */
  window.aigate = window.aigate || {};
  window.aigate.combos = {
    onShow: loadCombos,
    loadCombos: loadCombos,
    renderCombos: renderCombos,
    mapComboToRow: mapComboToRow
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
