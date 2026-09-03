/* ===== aigate UI shell bootstrap ===== */
/* Spec: FSD §2.7, TSD §3.4. Persist prefs in localStorage.
   Keys: aigate.theme | aigate.locale | aigate.sidebar               */

(function () {
  "use strict";

  var THEME_KEY = "aigate.theme";
  var LOCALE_KEY = "aigate.locale";
  var SIDEBAR_KEY = "aigate.sidebar";
  var DEFAULT_THEME = "light";
  var DEFAULT_LOCALE = "en";
  var DEFAULT_SIDEBAR = "expanded";

  function read(key, fallback) {
    try {
      var v = localStorage.getItem(key);
      return v === null ? fallback : v;
    } catch (e) {
      return fallback;
    }
  }

  function write(key, val) {
    try {
      localStorage.setItem(key, val);
    } catch (e) {
      /* storage unavailable — prefs simply won't persist */
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    var btn = document.getElementById("themeToggle");
    if (btn) {
      var icon = btn.querySelector("i");
      // Show the icon of the theme you will switch TO.
      if (icon) icon.className = theme === "dark" ? "fa fa-sun" : "fa fa-moon";
    }
  }

  function applySidebar(state) {
    var collapsed = state === "collapsed";
    document.body.classList.toggle("sidebar-collapsed", collapsed);
  }

  function markActiveLang(locale) {
    document.querySelectorAll(".lang-btn").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-lang") === locale);
    });
  }

  function init() {
    var theme = read(THEME_KEY, DEFAULT_THEME);
    var locale = read(LOCALE_KEY, DEFAULT_LOCALE);
    var sidebar = read(SIDEBAR_KEY, DEFAULT_SIDEBAR);

    applyTheme(theme);
    applySidebar(sidebar);
    if (window.applyLocale) window.applyLocale(locale);
    markActiveLang(locale);

    // --- Theme toggle ---
    var themeBtn = document.getElementById("themeToggle");
    if (themeBtn) {
      themeBtn.addEventListener("click", function () {
        var current = document.documentElement.getAttribute("data-theme");
        var next = current === "dark" ? "light" : "dark";
        applyTheme(next);
        write(THEME_KEY, next);
      });
    }

    // --- Language switch ---
    document.querySelectorAll(".lang-btn").forEach(function (b) {
      b.addEventListener("click", function () {
        var next = b.getAttribute("data-lang");
        if (window.applyLocale) window.applyLocale(next);
        write(LOCALE_KEY, next);
        markActiveLang(next);
      });
    });

    // --- Sidebar toggle ---
    var sbBtn = document.getElementById("sidebarToggle");
    if (sbBtn) {
      sbBtn.addEventListener("click", function () {
        var collapsed = document.body.classList.toggle("sidebar-collapsed");
        write(SIDEBAR_KEY, collapsed ? "collapsed" : "expanded");
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
