/* ===== aigate client-side i18n: registry + loader + helpers ===== */
/* Spec: FSD §2.7, TSD §3.4 — data-i18n keys resolved by applyLocale().

   TRANSLATION STRINGS DO NOT LIVE HERE. One file per language sits in
   static/i18n/<code>.js and self-registers into window.I18N:

     window.I18N = window.I18N || {};
     window.I18N.ru = { "app.title": "aigate", ... };

   That keeps every locale file owned by exactly one language (no shared file
   to merge between languages) and lets this file stay small and stable.
   Adding a language = drop i18n/<code>.js + add one row to window.LANGS.
   tests/i18n.test.js enforces that all locale files carry the SAME key set. */

(function () {
  "use strict";

  /* Namespace first, never clobber: a dictionary file may execute before or
     after this one — both orders are valid (see the self-register snippet). */
  window.I18N = window.I18N || {};

  /* ---- Registry: single source of truth for every language picker ----
     `code` doubles as the dictionary filename (i18n/<code>.js) and the
     localStorage value in `aigate.locale`. Names are endonyms (each language
     written in itself) so the labels never need re-translating.
     zh = Simplified Chinese, zh-tw = Traditional Chinese — do not invent
     other codes for them. */
  window.LANGS = [
    { code: "en", flag: "🇺🇸", nameKey: "lang.en" },
    { code: "id", flag: "🇮🇩", nameKey: "lang.id" },
    { code: "ru", flag: "🇷🇺", nameKey: "lang.ru" },
    { code: "nl", flag: "🇳🇱", nameKey: "lang.nl" },
    { code: "ja", flag: "🇯🇵", nameKey: "lang.ja" },
    { code: "zh", flag: "🇨🇳", nameKey: "lang.zh" },
    { code: "zh-tw", flag: "🇹🇼", nameKey: "lang.zh-tw" }
  ];

  var FALLBACK_LOCALE = "en";
  var DICT_DIR = "i18n/";

  /* Cache-buster for injected dictionary URLs. The inline preloader in
     index.html owns the number (it is also the one writing the <script> tags);
     this file only reads it, so the version lives in exactly one place. */
  function dictUrl(code) {
    var v = window.I18N_VER;
    return DICT_DIR + code + ".js" + (v ? "?v=" + v : "");
  }

  /** Is the dictionary for `loc` present in this page? */
  function hasLocale(loc) {
    return !!(window.I18N && loc && window.I18N[loc]);
  }

  /**
   * Resolve one key: locale dictionary -> English dictionary -> the key itself.
   * Never throws, even when no dictionary has loaded at all — that is the
   * contract that keeps the UI alive while a language file is missing.
   */
  function translate(key, loc) {
    var d = window.I18N && loc && window.I18N[loc];
    if (d && d[key] !== undefined) return d[key];
    var en = window.I18N && window.I18N[FALLBACK_LOCALE];
    if (en && en[key] !== undefined) return en[key];
    return key;
  }

  /**
   * Replace text of every element carrying [data-i18n] / [data-i18n-aria] with
   * the translation for `loc`, falling back to English, then to the raw key.
   * Pure render: it never fetches anything (see setLocale for that).
   * @param {string} loc - locale code from window.LANGS
   */
  function applyLocale(loc) {
    loc = loc || FALLBACK_LOCALE;
    document.querySelectorAll("[data-i18n]").forEach(function (el) {
      el.textContent = translate(el.getAttribute("data-i18n"), loc);
    });
    // aria-label bindings (accessibility, not visible text)
    document.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      el.setAttribute("aria-label", translate(el.getAttribute("data-i18n-aria"), loc));
    });
    document.documentElement.setAttribute("lang", loc);
    document.documentElement.setAttribute("data-locale", loc);
    // Browser tab title (visible copy) — resolved through the dictionary.
    try {
      document.title = translate("app.title", loc);
    } catch (e) { /* document.title unavailable — ignore */ }
  }

  /* ---- On-demand dictionary loading -------------------------------
     The page loads only the ACTIVE language up front (inline preloader in
     index.html <head>, synchronous, before app.js). Switching to a language
     that is not loaded yet fetches its file here.
     `inFlight` / `absent` make sure a language whose file does not exist yet
     is probed once per page view instead of on every click. */
  var inFlight = {};
  var absent = {};

  /**
   * Make sure `loc`'s dictionary is loaded, then run `onReady(loaded)`.
   * Calls `onReady` synchronously with true when the dictionary is already
   * present, and synchronously with false when it can never be fetched
   * (no DOM, already in flight, or already known to be absent).
   */
  function ensureLocale(loc, onReady) {
    var done = typeof onReady === "function" ? onReady : function () {};
    if (hasLocale(loc)) { done(true); return; }
    if (!loc || inFlight[loc] || absent[loc]) { done(false); return; }
    // The <head> preloader already fetched this file — its tags block the
    // parser, so they are finished by now. No dictionary means that fetch
    // failed: do not ask the server a second time in the same page view.
    if ((window.I18N_PRELOAD || []).indexOf(loc) >= 0) { absent[loc] = true; done(false); return; }
    if (typeof document === "undefined" || !document.createElement) { done(false); return; }

    inFlight[loc] = true;
    var script = document.createElement("script");
    script.src = dictUrl(loc);
    script.async = true;
    script.onload = function () {
      delete inFlight[loc];
      // A captive portal / SPA fallback answers 200 with HTML: still no dict.
      if (hasLocale(loc)) { done(true); }
      else { absent[loc] = true; done(false); }
    };
    script.onerror = function () {
      delete inFlight[loc];
      absent[loc] = true;
      done(false);
    };
    (document.head || document.documentElement).appendChild(script);
  }

  /**
   * Switch the UI to `loc`: render immediately with whatever is loaded (English
   * stands in for a missing dictionary, so there is never a raw-key flash), then
   * re-render as soon as the language's own file arrives.
   */
  function setLocale(loc) {
    applyLocale(loc);
    if (hasLocale(loc)) return; // already loaded: nothing to fetch, nothing to re-render
    ensureLocale(loc, function (loaded) {
      // Guard against a slow answer for a language the user has left meanwhile.
      if (loaded && document.documentElement.getAttribute("data-locale") === loc) {
        applyLocale(loc);
      }
    });
  }

  window.applyLocale = applyLocale;
  window.setLocale = setLocale;
  window.translate = translate;
  window.hasLocale = hasLocale;
  window.ensureLocale = ensureLocale;
})();
