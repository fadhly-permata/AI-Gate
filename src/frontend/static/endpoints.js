/* ===== aigate Endpoints management (B2.5) — vanilla JS, no build ===== */
/* Spec: FSD §2.4, ADR-001 / ADR-008. Backend contract: /api/endpoints
   returns {object:"list", data:[EndpointDTO]}. EndpointDTO: {id,name,
   listen_host,listen_port,access_control_enabled,internal_api_key,
   proxy_pool_id,binding}. CRUD wired; binding is optional
   (bind_type "provider"|"combo" + bind_id). Reuses window.aigate helpers. */

(function () {
  "use strict";

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

  var EP_API = "/api/endpoints";
  var selectedId = null;

  /* ---- Pure mapping (testable) ---- */
  function mapEndpointToRow(e) {
    e = e || {};
    var binding = e.binding || null;
    var bindText = "—";
    if (binding && binding.bind_type && binding.bind_id != null) {
      bindText = binding.bind_type + ":" + binding.bind_id;
    }
    return {
      id: e.id,
      name: e.name,
      listen: (e.listen_host || "127.0.0.1") + ":" + (e.listen_port != null ? e.listen_port : "8000"),
      enabled: !!e.access_control_enabled,
      proxy_pool_id: (e.proxy_pool_id != null) ? e.proxy_pool_id : null,
      binding_text: bindText
    };
  }

  function el(id) { return document.getElementById(id); }

  function setMsg(text, kind) {
    var m = el("endpointMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  /* ---- List + render ---- */
  function loadEndpoints() {
    setMsg("");
    return fetchJson(EP_API).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderEndpoints(list);
    }).catch(function (err) {
      setMsg(err.message, "error");
    });
  }

  function renderEndpoints(list) {
    var body = el("endpointTableBody");
    if (!body) return;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="6" class="empty-cell">' +
        escapeHtml(getStr("endpoints.no_items")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(function (e) {
      var row = mapEndpointToRow(e);
      var ac = row.enabled
        ? '<span class="badge badge-ok">' + escapeHtml(getStr("endpoints.enabled")) + "</span>"
        : '<span class="badge badge-off">' + escapeHtml(getStr("providers.disabled")) + "</span>";
      var pool = (row.proxy_pool_id != null)
        ? escapeHtml(String(row.proxy_pool_id))
        : '<span class="muted">—</span>';
      var bind = (row.binding_text !== "—")
        ? escapeHtml(row.binding_text)
        : '<span class="muted">' + escapeHtml(getStr("endpoints.none")) + "</span>";
      return '<tr class="endpoint-row" data-id="' + escapeHtml(row.id) + '">' +
        '<td class="endpoint-name">' + escapeHtml(row.name) + "</td>" +
        "<td>" + escapeHtml(row.listen) + "</td>" +
        "<td>" + ac + "</td>" +
        "<td>" + pool + "</td>" +
        "<td>" + bind + "</td>" +
        '<td class="row-actions">' +
          '<button type="button" class="icon-btn-small js-edit" title="' + escapeHtml(getStr("endpoints.edit")) + '">' +
            '<i class="fa fa-pen"></i></button>' +
          '<button type="button" class="icon-btn-small js-del" title="' + escapeHtml(getStr("endpoints.delete")) + '">' +
            '<i class="fa fa-trash"></i></button>' +
        "</td>" +
      "</tr>";
    }).join("");

    Array.prototype.forEach.call(body.querySelectorAll(".endpoint-row"), function (tr) {
      var id = tr.getAttribute("data-id");
      tr.querySelector(".js-edit").addEventListener("click", function (e) {
        e.stopPropagation(); openEditModal(id);
      });
      tr.querySelector(".js-del").addEventListener("click", function (e) {
        e.stopPropagation(); deleteEndpoint(id);
      });
    });
  }

  /* ---- Modal (add / edit) ---- */
  function hideModal() { var m = el("endpointModal"); if (m) m.hidden = true; }

  function toggleBindId() {
    var bt = el("endpointBindType");
    var row = el("endpointBindIdRow");
    if (row && bt) row.style.display = (bt.value === "none") ? "none" : "";
  }

  function openAddModal() {
    selectedId = null;
    var f = el("endpointForm"); if (f) f.reset();
    var idEl = el("endpointId"); if (idEl) idEl.value = "";
    var bt = el("endpointBindType"); if (bt) bt.value = "none";
    toggleBindId();
    var t = el("endpointModalTitle"); if (t) t.textContent = getStr("endpoints.add");
    var m = el("endpointModal"); if (m) m.hidden = false;
  }

  function openEditModal(id) {
    fetchJson(EP_API + "/" + id).then(function (e) {
      selectedId = id;
      var idEl = el("endpointId"); if (idEl) idEl.value = e.id;
      var n = el("endpointName"); if (n) n.value = e.name != null ? e.name : "";
      var h = el("endpointHost"); if (h) h.value = e.listen_host || "";
      var p = el("endpointPort"); if (p) p.value = (e.listen_port != null) ? e.listen_port : "";
      var ac = el("endpointAccessControl"); if (ac) ac.checked = !!e.access_control_enabled;
      var pp = el("endpointProxyPool"); if (pp) pp.value = (e.proxy_pool_id != null) ? e.proxy_pool_id : "";
      var bt = el("endpointBindType");
      var bind = e.binding || null;
      if (bt) bt.value = (bind && bind.bind_type) ? bind.bind_type : "none";
      var bid = el("endpointBindId"); if (bid) bid.value = (bind && bind.bind_id != null) ? bind.bind_id : "";
      var t = el("endpointModalTitle"); if (t) t.textContent = getStr("endpoints.edit");
      toggleBindId();
      var m = el("endpointModal"); if (m) m.hidden = false;
    }).catch(function (err) { setMsg(err.message, "error"); });
  }

  function saveEndpoint(e) {
    if (e) e.preventDefault();
    var id = el("endpointId") ? el("endpointId").value : "";
    var bt = el("endpointBindType") ? el("endpointBindType").value : "none";
    var bindIdRaw = el("endpointBindId") ? el("endpointBindId").value : "";
    var bindId = parseInt(bindIdRaw, 10);
    var ppRaw = el("endpointProxyPool") ? el("endpointProxyPool").value : "";
    var body = {
      name: el("endpointName") ? el("endpointName").value : "",
      listen_host: el("endpointHost") ? el("endpointHost").value : "",
      listen_port: el("endpointPort") ? (parseInt(el("endpointPort").value, 10) || null) : null,
      access_control_enabled: el("endpointAccessControl")
        ? !!el("endpointAccessControl").checked : false,
      proxy_pool_id: el("endpointProxyPool") ? (parseInt(ppRaw, 10) || null) : null
    };
    if (bt !== "none" && !isNaN(bindId)) {
      body.binding = { bind_type: bt, bind_id: bindId };
    }
    setMsg("");
    var req = id
      ? fetchJson(EP_API + "/" + id, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        })
      : fetchJson(EP_API, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        });
    req.then(function () { hideModal(); loadEndpoints(); })
       .catch(function (err) { setMsg(err.message, "error"); });
  }

  function deleteEndpoint(id) {
    if (!window.confirm(getStr("endpoints.confirm_delete"))) return;
    fetchJson(EP_API + "/" + id, { method: "DELETE" })
      .then(function () { loadEndpoints(); })
      .catch(function (err) { setMsg(err.message, "error"); });
  }

  /* ---- Wire up ---- */
  function init() {
    var add = el("endpointAddBtn");
    if (add) add.addEventListener("click", openAddModal);
    var form = el("endpointForm");
    if (form) form.addEventListener("submit", saveEndpoint);
    var cancel = el("endpointCancel");
    if (cancel) cancel.addEventListener("click", hideModal);
    var bt = el("endpointBindType");
    if (bt) bt.addEventListener("change", toggleBindId);
    var modal = el("endpointModal");
    if (modal) modal.addEventListener("click", function (e) {
      if (e.target === modal) hideModal();
    });
  }

  window.aigate = window.aigate || {};
  window.aigate.endpoints = {
    onShow: loadEndpoints,
    loadEndpoints: loadEndpoints,
    renderEndpoints: renderEndpoints,
    mapEndpointToRow: mapEndpointToRow
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
