/* ===== aigate client-side i18n dictionary (EN / ID) ===== */
/* Spec: FSD §2.7, TSD §3.4 — data-i18n keys resolved by applyLocale(). */

window.I18N = {
  en: {
    "app.title": "aigate",
    "app.subtitle": "AI Proxy Gateway",
    "nav.providers": "Providers",
    "nav.combos": "Combos",
    "nav.proxies": "Proxy Pools",
    "nav.endpoints": "Endpoints",
    "nav.terminal": "Terminal",
    "nav.cli": "CLI Tools",
    "btn.theme": "Theme",
    "btn.lang": "Language",
    "btn.menu": "Toggle sidebar",
    "ws.welcome": "Welcome to aigate",
    "ws.placeholder": "The management console and terminal will appear here."
  },
  id: {
    "app.title": "aigate",
    "app.subtitle": "Gateway Proxy AI",
    "nav.providers": "Penyedia",
    "nav.combos": "Kombo",
    "nav.proxies": "Pool Proxy",
    "nav.endpoints": "Endpoint",
    "nav.terminal": "Terminal",
    "nav.cli": "Alat CLI",
    "btn.theme": "Tema",
    "btn.lang": "Bahasa",
    "btn.menu": "Alihkan bilah sisi",
    "ws.welcome": "Selamat datang di aigate",
    "ws.placeholder": "Konsol manajemen dan terminal akan muncul di sini."
  }
};

/**
 * Replace text of every element carrying [data-i18n] with the
 * translation from I18N[loc]. Falls back to English for missing keys.
 * @param {string} loc - locale code ("en" | "id")
 */
function applyLocale(loc) {
  var dict = window.I18N[loc] || window.I18N.en;
  var fb = window.I18N.en;
  document.querySelectorAll("[data-i18n]").forEach(function (el) {
    var key = el.getAttribute("data-i18n");
    el.textContent = dict[key] !== undefined ? dict[key] : (fb[key] !== undefined ? fb[key] : key);
  });
  // aria-label bindings (accessibility, not visible text)
  document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
    var key = el.getAttribute("data-i18n-aria");
    el.setAttribute("aria-label", dict[key] !== undefined ? dict[key] : (fb[key] || key));
  });
  document.documentElement.setAttribute("lang", loc);
}

window.applyLocale = applyLocale;
