import { describe, it, expect, beforeEach, afterEach } from "vitest";

// i18n.js is a side-effect module: it attaches window.I18N (empty namespace),
// the language registry and the helpers, and uses document inside applyLocale.
// jsdom (configured in vitest.config.js) provides window/document, so we just
// import for the side effect. The dictionaries themselves are loaded into
// window.I18N by tests/helpers/i18n-dicts.js (setupFiles) — in the browser that
// job is done by <script> tags. The same helper enumerates the locale files for
// the parity guard below, so the set of languages is discovered, never listed.
import "../static/i18n.js";
import { localeCodes } from "./helpers/i18n-dicts.js";
import { indexHtml } from "./helpers/dom.js";

/** Keys of a locale dictionary, sorted — the unit the parity guard compares. */
function keysOf(code) {
  const dict = window.I18N[code];
  expect(dict, `dictionary window.I18N.${code} is registered`).toBeTruthy();
  return Object.keys(dict).sort();
}

describe("i18n.applyLocale", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div data-i18n="app.title"></div>
      <nav data-i18n="nav.providers"></nav>
      <button data-i18n-aria="btn.menu"></button>
    `;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("applies Indonesian translations from window.I18N", async () => {
    window.applyLocale("id");
    const title = document.querySelector('[data-i18n="app.title"]');
    const providers = document.querySelector('[data-i18n="nav.providers"]');
    expect(title.textContent).toBe(window.I18N.id["app.title"]);
    expect(providers.textContent).toBe(window.I18N.id["nav.providers"]);
    // nav.providers differs EN/ID — meaningful language switch assertion
    expect(providers.textContent).toBe("Penyedia");
    expect(document.documentElement.getAttribute("lang")).toBe("id");
    expect(document.documentElement.getAttribute("data-locale")).toBe("id");
  });

  it("reverts to English on applyLocale('en')", async () => {
    window.applyLocale("id");
    window.applyLocale("en");
    const providers = document.querySelector('[data-i18n="nav.providers"]');
    expect(providers.textContent).toBe(window.I18N.en["nav.providers"]);
    expect(providers.textContent).toBe("Providers");
    expect(document.documentElement.getAttribute("lang")).toBe("en");
  });

  it("sets aria-label from data-i18n-aria", async () => {
    window.applyLocale("id");
    const btn = document.querySelector("[data-i18n-aria]");
    expect(btn.getAttribute("aria-label")).toBe(window.I18N.id["btn.menu"]);
  });

  it("renders English for a registered language whose file is not loaded", () => {
    // The transition state between shipping the registry and shipping a
    // language file. Simulated by hiding a real dictionary, so this stays
    // valid after every locale file exists.
    const code = "id";
    const saved = window.I18N[code];
    try {
      delete window.I18N[code];
      expect(window.hasLocale(code)).toBe(false);
      window.applyLocale(code);
      expect(document.querySelector('[data-i18n="nav.providers"]').textContent)
        .toBe(window.I18N.en["nav.providers"]);
      // The chosen language is still remembered as active.
      expect(document.documentElement.getAttribute("data-locale")).toBe(code);
    } finally {
      window.I18N[code] = saved;
    }
  });
});

/* ===== Key-parity guard: one rule for EVERY locale file =====
   Discovers static/i18n/*.js at run time, so a new language is held to the
   exact same contract as English the moment its file appears: same keys, none
   missing, none extra. Nothing here is hardcoded to a language pair, and
   adding a locale never means editing this file. */
const codes = localeCodes();

describe("i18n locale files — key parity with English", () => {
  it("ships at least the English dictionary", () => {
    expect(codes).toContain("en");
  });

  it.each(codes.filter((c) => c !== "en"))("%s has EXACTLY the English key set", (code) => {
    expect(keysOf(code)).toEqual(keysOf("en"));
  });

  it("every locale file is listed in the registry (no orphan dictionary)", () => {
    const registered = (window.LANGS || []).map((l) => l.code);
    expect(codes.filter((c) => !registered.includes(c))).toEqual([]);
  });
});

/* ===== Registry: the contract the language pickers render from ===== */
describe("i18n registry (window.LANGS)", () => {
  const EXPECTED = [
    ["en", "🇺🇸"], ["id", "🇮🇩"], ["ru", "🇷🇺"], ["nl", "🇳🇱"],
    ["ja", "🇯🇵"], ["zh", "🇨🇳"], ["zh-tw", "🇹🇼"]
  ];

  it("lists all seven locales, in order, with their flags", () => {
    expect(window.LANGS.map((l) => [l.code, l.flag])).toEqual(EXPECTED);
  });

  it("uses lang.<code> as the name key for every locale", () => {
    window.LANGS.forEach((l) => expect(l.nameKey).toBe("lang." + l.code));
  });

  it("resolves every language name in English (picker never shows a raw key)", () => {
    window.LANGS.forEach((l) => {
      const name = window.translate(l.nameKey, "en");
      expect(name, l.code).not.toBe(l.nameKey);
      expect(name.trim().length).toBeGreaterThan(0);
    });
    // Endonyms: a language is always written in itself.
    expect(window.translate("lang.ja", "en")).toBe("日本語");
    expect(window.translate("lang.zh", "en")).toBe("简体中文");
    expect(window.translate("lang.zh-tw", "en")).toBe("繁體中文");
  });

  it("keeps zh = Simplified and zh-tw = Traditional, no other Chinese codes", () => {
    const zh = window.LANGS.filter((l) => l.code.startsWith("zh"));
    expect(zh.map((l) => l.code).sort()).toEqual(["zh", "zh-tw"]);
  });
});

/* ===== Fallback contract: no dictionary, no crash, no raw-key flash =====
   These are the "safe when a language file is missing" guarantees: every entry
   point the UI uses must survive an empty or partial window.I18N.
   `NOT_A_LOCALE` is a code no language file will ever ship under, so these
   assertions keep their meaning after all seven locales land. */
const NOT_A_LOCALE = "zz";

describe("i18n fallback safety", () => {
  it("translate() prefers the locale, then English, then the key itself", () => {
    expect(window.translate("nav.providers", "id")).toBe("Penyedia");
    expect(window.translate("nav.providers", NOT_A_LOCALE)).toBe("Providers");
    expect(window.translate("no.such.key", "id")).toBe("no.such.key");
  });

  it("translate() survives an empty dictionary namespace", () => {
    const saved = window.I18N;
    try {
      window.I18N = {};
      expect(window.translate("app.title", "id")).toBe("app.title");
      expect(() => window.applyLocale("id")).not.toThrow();
      expect(() => window.setLocale("id")).not.toThrow();
    } finally {
      window.I18N = saved;
    }
  });

  it("hasLocale() reports what is actually loaded", () => {
    expect(window.hasLocale("en")).toBe(true);
    expect(window.hasLocale(NOT_A_LOCALE)).toBe(false);
    expect(window.hasLocale(undefined)).toBe(false);
  });

  it("setLocale() renders at once from English and never blocks on the file", () => {
    document.body.innerHTML = '<nav data-i18n="nav.providers"></nav>';
    expect(() => window.setLocale(NOT_A_LOCALE)).not.toThrow();
    // Instant visible result (English stands in) — no raw key, no blank label.
    expect(document.querySelector("nav").textContent).toBe("Providers");
    document.body.innerHTML = "";
    // Do not leak the injected probe into other files (shared jsdom worker).
    document.querySelectorAll(`script[src^='i18n/${NOT_A_LOCALE}.js']`)
      .forEach((s) => s.remove());
  });

  it("does not re-fetch a dictionary that is already loaded", () => {
    const before = document.querySelectorAll("script[src^='i18n/']").length;
    window.ensureLocale("en", () => {});
    window.ensureLocale("id", () => {});
    expect(document.querySelectorAll("script[src^='i18n/']").length).toBe(before);
  });

  it("does not re-probe a file the <head> preloader already fetched", () => {
    // The preloader's tags block the parser, so by the time app.js runs a
    // missing dictionary there is a confirmed 404 — asking twice is pure noise.
    const code = "preloaded";
    window.I18N_PRELOAD = ["en", code];
    let result = null;
    window.ensureLocale(code, (ok) => { result = ok; });
    expect(result).toBe(false);
    expect(document.querySelector(`script[src^='i18n/${code}.js']`)).toBeNull();
    delete window.I18N_PRELOAD;
  });

  it("builds on-demand URLs with the cache-buster the preloader published", () => {
    // Own code: the probes above already left "zz" in flight.
    const probe = "probe";
    window.I18N_VER = "9999";
    window.ensureLocale(probe, () => {});
    const el = document.querySelector(`script[src^='i18n/${probe}.js']`);
    expect(el, "a missing dictionary is probed once").toBeTruthy();
    expect(el.getAttribute("src")).toBe(`i18n/${probe}.js?v=9999`);
    delete window.I18N_VER;
    // The probe is remembered (in flight, then known-absent): no request storm
    // when the user switches to a language that has no file yet.
    window.ensureLocale(probe, () => {});
    expect(document.querySelectorAll(`script[src^='i18n/${probe}.js']`).length).toBe(1);
    el.remove();
  });
});

/* ===== Moved strings must be untouched ===== */
describe("i18n dictionary content", () => {
  it("nav.repo stays the product name 'aigate Repo' in both shipped locales", () => {
    expect(window.I18N.en["nav.repo"]).toBe("aigate Repo");
    expect(window.I18N.id["nav.repo"]).toBe("aigate Repo");
  });

  it("every dictionary value is a non-empty string", () => {
    codes.forEach((code) => {
      Object.entries(window.I18N[code]).forEach(([k, v]) => {
        expect(typeof v, `${code}:${k}`).toBe("string");
        expect(v.length, `${code}:${k}`).toBeGreaterThan(0);
      });
    });
  });
});

/* ===== The <head> preloader: why there is no flash and no race =====
   index.html injects the active dictionary with document.write() while the
   parser is still in <head>. A parser-blocking script written there is
   guaranteed to finish before ANY deferred script runs — that is what makes
   `getStr()` safe on the very first call in app.js init(). These tests execute
   the shipped snippet against a stubbed document/localStorage, so the ordering
   guarantee and the URL it builds are both pinned. */
describe("index.html i18n preloader", () => {
  const html = indexHtml();

  /** The inline snippet, taken verbatim from the shipped page. */
  function preloaderSource() {
    const blocks = Array.from(html.matchAll(/<script>([\s\S]*?)<\/script>/g), (m) => m[1]);
    const src = blocks.find((b) => b.includes("window.I18N_VER"));
    expect(src, "inline i18n preloader exists in index.html").toBeTruthy();
    return src;
  }

  /** Run the snippet with a fake storage + a document.write spy. */
  function run(stored) {
    const writes = [];
    const win = {};
    const fn = new Function("window", "localStorage", "document", preloaderSource());
    fn(win, { getItem: () => stored }, { write: (s) => writes.push(s) });
    return { win, writes: writes.join("") };
  }

  it("lives in <head>, before i18n.js and app.js", () => {
    const head = html.slice(0, html.indexOf("</head>"));
    expect(head.length, "index.html has a <head>").toBeGreaterThan(0);
    expect(head).toContain("window.I18N_VER");
    // Parser order is execution order for the blocking preloader and the
    // deferred scripts: preloader -> i18n.js (registry) -> app.js (consumer).
    expect(html.indexOf("window.I18N_VER")).toBeLessThan(html.indexOf('src="i18n.js'));
    expect(html.indexOf('src="i18n.js')).toBeLessThan(html.indexOf('src="app.js'));
  });

  it("loads English only, when no preference is stored", () => {
    const { writes } = run(null);
    expect(writes).toContain("i18n/en.js?v=");
    expect(writes.match(/<script src=/g)).toHaveLength(1);
  });

  it("loads English plus the stored language, in that order", () => {
    const { writes } = run("id");
    expect(writes).toContain("i18n/en.js?v=");
    expect(writes.indexOf("i18n/en.js")).toBeLessThan(writes.indexOf("i18n/id.js"));
  });

  it("reads the same storage key app.js writes", () => {
    expect(preloaderSource()).toContain('localStorage.getItem("aigate.locale")');
  });

  it("rejects anything that is not a locale code (no URL injection)", () => {
    ["../../etc/passwd", "</script><script>alert(1)</script>", "EN", "a", "toolongcode!!"]
      .forEach((stored) => {
        const { writes } = run(stored);
        expect(writes, `stored=${JSON.stringify(stored)}`).not.toContain(stored);
        expect(writes.match(/<script src=/g)).toHaveLength(1); // English only
      });
  });

  it("treats an empty or 'en' stored value as English", () => {
    ["", "en"].forEach((stored) => {
      const { writes } = run(stored);
      expect(writes.match(/<script src=/g)).toHaveLength(1);
      expect(writes).toContain("i18n/en.js?v=");
    });
  });

  it("accepts the hyphenated zh-tw code", () => {
    const { writes } = run("zh-tw");
    expect(writes).toContain("i18n/zh-tw.js?v=");
  });

  it("publishes the same cache-buster it injects, and i18n.js reuses it", () => {
    const { win, writes } = run("id");
    const ver = win.I18N_VER;
    expect(ver).toMatch(/^\d{8}$/);
    expect(writes).toContain(`i18n/id.js?v=${ver}`);
    // The registry tag must carry the same version, or a stale i18n.js would
    // build on-demand URLs the browser has cached away.
    expect(html).toContain(`src="i18n.js?v=${ver}"`);
    expect(html).toContain(`src="app.js?v=${ver}"`);
  });

  it("publishes what it injected, so i18n.js never re-probes it", () => {
    expect(run(null).win.I18N_PRELOAD).toEqual(["en"]);
    expect(run("id").win.I18N_PRELOAD).toEqual(["en", "id"]);
    expect(run("zh-tw").win.I18N_PRELOAD).toEqual(["en", "zh-tw"]);
  });

  it("survives blocked storage", () => {
    const writes = [];
    const fn = new Function("window", "localStorage", "document", preloaderSource());
    expect(() => fn({}, {
      getItem() { throw new Error("SecurityError"); },
    }, { write: (s) => writes.push(s) })).not.toThrow();
    expect(writes.join("")).toContain("i18n/en.js?v=");
  });
});
