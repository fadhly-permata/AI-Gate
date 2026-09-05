/* ===== aigate Proxy Pools management (B2.3) — vanilla JS, no build ===== */
/* Spec: FSD §2.2, ADR-001. Backend contract: /api/proxy-pools returns
   {object:"list", data:[ProxyPoolDTO]}. ProxyPoolDTO: {id,name,
   rotation_strategy,enabled,last_used_index,nodes:[NodeDTO]}. CRUD + a
   per-pool health-check (POST /api/proxy-pools/{id}/health-check) are wired.
   Reuses window.aigate.fetchJson/escapeHtml/getStr from app.js. */

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

  var POOL_API = "/api/proxy-pools";
  var selectedId = null;

  /* ---- Pure mapping (testable) ---- */
  function mapPoolToRow(p) {
    p = p || {};
    return {
      id: p.id,
      name: p.name,
      strategy: p.rotation_strategy,
      enabled: !!p.enabled,
      nodeCount: Array.isArray(p.nodes) ? p.nodes.length : 0
    };
  }

  function el(id) { return document.getElementById(id); }

  function setMsg(text, kind) {
    var m = el("poolMsg");
    if (!m) return;
    m.textContent = text || "";
    m.className = "settings-msg" + (kind ? " settings-msg-" + kind : "");
  }

  /* ---- List + render ---- */
  function loadPools() {
    setMsg("");
    return fetchJson(POOL_API).then(function (data) {
      var list = (data && data.data) ? data.data : [];
      renderPools(list);
    }).catch(function (err) {
      setMsg(err.message, "error");
    });
  }

  function renderPools(list) {
    var body = el("poolTableBody");
    if (!body) return;
    if (!list.length) {
      body.innerHTML = '<tr><td colspan="5" class="empty-cell">' +
        escapeHtml(getStr("proxies.no_items")) + "</td></tr>";
      return;
    }
    body.innerHTML = list.map(function (p) {
      var row = mapPoolToRow(p);
      var badge = row.enabled
        ? '<span class="badge badge-ok">' + escapeHtml(getStr("proxies.enabled")) + "</span>"
        : '<span class="badge badge-off">' + escapeHtml(getStr("providers.disabled")) + "</span>";
      return '<tr class="pool-row" data-id="' + escapeHtml(row.id) + '">' +
        '<td class="pool-name">' + escapeHtml(row.name) + "</td>" +
        "<td>" + escapeHtml(row.strategy) + "</td>" +
        "<td>" + badge + "</td>" +
        "<td>" + row.nodeCount + "</td>" +
        '<td class="row-actions">' +
          '<button type="button" class="icon-btn-small js-check" title="' + escapeHtml(getStr("proxies.health")) + '">' +
            '<i class="fa fa-stethoscope"></i></button>' +
          '<button type="button" class="icon-btn-small js-edit" title="' + escapeHtml(getStr("proxies.edit")) + '">' +
            '<i class="fa fa-pen"></i></button>' +
          '<button type="button" class="icon-btn-small js-del" title="' + escapeHtml(getStr("proxies.delete")) + '">' +
            '<i class="fa fa-trash"></i></button>' +
        "</td>" +
      "</tr>";
    }).join("");

    Array.prototype.forEach.call(body.querySelectorAll(".pool-row"), function (tr) {
      var id = tr.getAttribute("data-id");
      tr.querySelector(".js-edit").addEventListener("click", function (e) {
        e.stopPropagation(); openEditModal(id);
      });
      tr.querySelector(".js-del").addEventListener("click", function (e) {
        e.stopPropagation(); deletePool(id);
      });
      tr.querySelector(".js-check").addEventListener("click", function (e) {
        e.stopPropagation(); healthCheck(id);
      });
    });
  }

  /* ---- Modal (add / edit) ---- */
  function hideModal() { var m = el("poolModal"); if (m) m.hidden = true; }

  function openAddModal() {
    selectedId = null;
    var f = el("poolForm"); if (f) f.reset();
    var idEl = el("poolId"); if (idEl) idEl.value = "";
    var t = el("poolModalTitle"); if (t) t.textContent = getStr("proxies.add");
    var m = el("poolModal"); if (m) m.hidden = false;
  }

  function openEditModal(id) {
    fetchJson(POOL_API + "/" + id).then(function (p) {
      selectedId = id;
      var idEl = el("poolId"); if (idEl) idEl.value = p.id;
      var n = el("poolName"); if (n) n.value = p.name != null ? p.name : "";
      var s = el("poolStrategy"); if (s) s.value = p.rotation_strategy || "round_robin";
      var en = el("poolEnabled"); if (en) en.checked = !!p.enabled;
      var t = el("poolModalTitle"); if (t) t.textContent = getStr("proxies.edit");
      var m = el("poolModal"); if (m) m.hidden = false;
    }).catch(function (err) { setMsg(err.message, "error"); });
  }

  function savePool(e) {
    if (e) e.preventDefault();
    var id = el("poolId") ? el("poolId").value : "";
    var body = {
      name: el("poolName") ? el("poolName").value : "",
      rotation_strategy: el("poolStrategy") ? el("poolStrategy").value : "round_robin",
      enabled: el("poolEnabled") ? el("poolEnabled").checked : true
    };
    setMsg("");
    var req = id
      ? fetchJson(POOL_API + "/" + id, {
          method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        })
      : fetchJson(POOL_API, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body)
        });
    req.then(function () { hideModal(); loadPools(); })
       .catch(function (err) { setMsg(err.message, "error"); });
  }

  function deletePool(id) {
    if (!window.confirm(getStr("proxies.confirm_delete"))) return;
    fetchJson(POOL_API + "/" + id, { method: "DELETE" })
      .then(function () { loadPools(); })
      .catch(function (err) { setMsg(err.message, "error"); });
  }

  /* ---- Health check (POST /api/proxy-pools/{id}/health-check) ---- */
  function healthCheck(id) {
    setMsg(getStr("proxies.health") + "…", "");
    return fetchJson(POOL_API + "/" + id + "/health-check", {
      method: "POST", headers: { "Content-Type": "application/json" }
    }).then(function (res) {
      var results = (res && res.results) ? res.results : [];
      var healthy = results.filter(function (r) { return r.status === "healthy"; }).length;
      // Reload the list first, then surface the summary (loadPools clears the
      // status line, so we set it afterwards).
      return loadPools().then(function () {
        setMsg(getStr("proxies.health_done") + " (" + healthy + "/" + results.length + ")", "ok");
      });
    }).catch(function (err) {
      setMsg(err.message, "error");
    });
  }

  /* ---- Wire up ---- */
  function init() {
    var add = el("poolAddBtn");
    if (add) add.addEventListener("click", openAddModal);
    var form = el("poolForm");
    if (form) form.addEventListener("submit", savePool);
    var cancel = el("poolCancel");
    if (cancel) cancel.addEventListener("click", hideModal);
    var modal = el("poolModal");
    if (modal) modal.addEventListener("click", function (e) {
      if (e.target === modal) hideModal();
    });
  }

  window.aigate = window.aigate || {};
  window.aigate.proxies = {
    onShow: loadPools,
    loadPools: loadPools,
    renderPools: renderPools,
    mapPoolToRow: mapPoolToRow,
    healthCheck: healthCheck
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
