/**
 * Guard: every shipped asset must be LOCAL (OPERATING_RULES G3 — vendor lokal,
 * tanpa CDN). This is the regression net that makes "the CDN came back" fail
 * loudly, offline icon death included.
 *
 * WHAT IS FLAGGED (each construct makes the browser fetch a resource itself,
 * so an absolute URL here = a network request off the phone):
 *   - <link  ... href="http(s)://host/...">   (stylesheets, preloads, icons)
 *   - <link  ... href="//host/...">           (protocol-relative — same thing)
 *   - <script ... src="http(s)://host/...">   / <script ... src="//host/...">
 *   - <img|source|iframe|embed|object|video|audio|track ... (src|srcset|poster|data)
 *                                              ="http(s)://host/...">
 *   - CSS  @import url("http(s)://host/...")  and  url("http(s)://host/...")
 *   - a <style> block or an inline style="...url(http...)"
 *
 * WHAT IS DELIBERATELY ALLOWED (and WHY — this is a STRUCTURE test, not a URL
 * denylist, so a new CDN host can never slip through just because it is not on
 * a list, and a legit link never trips it just because it looks like github):
 *   - <a href="https://github.com/fadhly-permata/AI-Gate"> — the sidebar/bottom
 *     "Repo" button. An ANCHOR does not auto-fetch: the browser loads nothing
 *     until the user clicks and navigates. It is a navigation link, not an
 *     asset, so it is not matched by the resource-tag patterns below.
 *   - http(s) URLs that live in COMMENTS or in dictionary/help STRING values
 *     (terminal.js secure-context notes, base_url examples). None of the
 *     patterns below match text that is not a tag attribute or a CSS url(), so
 *     comments are inherently excluded — no comment-stripping, no host list.
 *   - RELATIVE asset refs (styles.css?v=, vendor/xterm/xterm.css,
 *     vendor/font-awesome/css/all.min.css, ../webfonts/*.woff2): served by the
 *     same local FastAPI origin, no egress — exactly what G3 wants.
 *
 * The scan covers the real files, not a hand-kept list: it walks static/** so a
 * new html/css/js is picked up automatically. Binary font/woff2 payloads are
 * skipped for the text scan (they cannot hold a <link>); they get their own
 * existence check below instead.
 */
import { describe, it, expect } from "vitest";
import { readFileSync, readdirSync, statSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join, relative } from "path";

const STATIC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "static");

/** All files under static/, recursively. */
function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

const ALL_FILES = walk(STATIC_DIR);
const TEXT_EXT = /\.(?:html?|css|js|mjs)$/i;
const TEXT_FILES = ALL_FILES.filter((f) => TEXT_EXT.test(f));

// One regex per fetch-triggering shape. `//` after an optional scheme is the
// protocol-relative form; it is matched in the same breath as http(s)://.
const PATTERNS = [
  { what: '<link href="<absolute>"', re: /<link\b[^>]*?\bhref\s*=\s*["']?\s*(?:https?:)?\/\//gi },
  { what: '<script src="<absolute>"', re: /<script\b[^>]*?\bsrc\s*=\s*["']?\s*(?:https?:)?\/\//gi },
  {
    what: '<img|source|iframe|embed|object|video|audio|track src|srcset|poster|data="<absolute>"',
    re: /<(?:img|source|iframe|embed|object|video|audio|track)\b[^>]*?\b(?:src|srcset|poster|data)\s*=\s*["']?\s*(?:https?:)?\/\//gi,
  },
  { what: 'CSS @import url("<absolute>")', re: /@import\b[^;]*?url\(\s*["']?\s*(?:https?:)?\/\//gi },
  { what: 'CSS url("<absolute>")', re: /\burl\(\s*["']?\s*(?:https?:)?\/\//gi },
];

/** Every absolute-asset hit, as "file:pattern" strings (empty === pass). */
function externalAssetHits(files) {
  const hits = [];
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    for (const { what, re } of PATTERNS) {
      re.lastIndex = 0;
      if (re.test(text)) hits.push(`${relative(STATIC_DIR, file)} -> ${what}`);
    }
  }
  return hits;
}

describe("G3 asset guard — no CDN / no external asset fetch", () => {
  it("scans the whole static tree (sanity: the guard is actually wired up)", () => {
    // If this ever drops to ~0 the walk() broke and the test is vacuous.
    expect(TEXT_FILES.length).toBeGreaterThan(15);
    expect(TEXT_FILES.map((f) => relative(STATIC_DIR, f))).toContain("index.html");
  });

  it("index.html loads Font Awesome from the vendored copy, not a CDN", () => {
    const html = readFileSync(join(STATIC_DIR, "index.html"), "utf8");
    expect(html).toContain('href="vendor/font-awesome/css/all.min.css');
    // The exact CDN that broke offline rendering must be gone, not just masked.
    expect(html).not.toMatch(/cdnjs\.cloudflare\.com/i);
  });

  it("no <link>/<script>/media tag or CSS url() points at an absolute host", () => {
    expect(externalAssetHits(TEXT_FILES)).toEqual([]);
  });

  it("the github 'Repo' link stays a plain <a> (proves the allow-reason holds)", () => {
    // The only absolute http(s) URLs left in the shipped html must be <a> nav
    // links. If someone turns the repo link into an asset (preload/iframe/img),
    // the rule above catches it; this pins the exclusion's justification.
    const html = readFileSync(join(STATIC_DIR, "index.html"), "utf8");
    const nonA = html.split("\n").filter((line) => /https?:\/\//.test(line) && !/<a\b/.test(line) && !/^\s*(\/\/|<!--|\*)/.test(line));
    expect(nonA).toEqual([]);
  });
});

describe("G3 asset guard — vendored Font Awesome woff2 exist on disk", () => {
  const CSS = join(STATIC_DIR, "vendor/font-awesome/css/all.min.css");
  const css = () => readFileSync(CSS, "utf8");

  it("all.min.css itself references no external host", () => {
    expect(css()).not.toMatch(/url\(\s*["']?\s*(?:https?:)?\/\//i);
  });

  // Every @font-face whose woff2 the app can actually request must resolve to a
  // real file. The app's classes (.fa/.fa-solid/.fa-regular/.fas/.far ->
  // "Font Awesome 6 Free"; .fa-brands/.fab -> "Font Awesome 6 Brands") only ever
  // pull those two families, and BOTH faces carry no unicode-range, so they cover
  // every glyph the markup renders. The FA v4-compat faces (family "FontAwesome",
  // incl. fa-v4compatibility.woff2) are only fetched when some selector applies
  // the legacy family — audited: all.min.css contains ZERO non-@font-face rules
  // with font-family:"FontAwesome" (those live in v4-shims.css, not vendored),
  // and no app file does either. The .ttf entries are never requested either:
  // woff2 is first in every src chain and all target browsers support it.
  // Vendoring the ttf fallbacks + v4compat would add dead weight, so requiring
  // them here would fail the test over files that are never fetched.
  it("every @font-face woff2 the app loads resolves to a real file", () => {
    const cssDir = dirname(CSS);
    const faces = [...css().matchAll(/@font-face\s*\{[^}]*\}/gi)].map((m) => m[0]);
    const wanted = faces
      .filter((b) => /font-family:\s*["']?Font Awesome 6 (?:Free|Brands)/i.test(b))
      .flatMap((b) => [...b.matchAll(/url\(([^)]+?\.woff2)\)/gi)].map((m) => m[1]));
    expect(wanted.length).toBeGreaterThan(0); // guard is not vacuous
    const resolved = new Set(wanted.map((r) => join(cssDir, r.replace(/^["']|["']$/g, ""))));
    for (const file of resolved) {
      // The guard's whole point: a missing webfont = a dead icon offline.
      expect(existsSafe(file), `missing referenced woff2: ${relative(STATIC_DIR, file)}`).toBe(true);
    }
  });

  it("the three FA6 faces the markup loads (solid/regular/brands) are present", () => {
    const webfonts = join(STATIC_DIR, "vendor/font-awesome/webfonts");
    for (const f of ["fa-solid-900.woff2", "fa-regular-400.woff2", "fa-brands-400.woff2"]) {
      expect(existsSafe(join(webfonts, f)), f).toBe(true);
    }
  });
});

function existsSafe(p) {
  try {
    return statSync(p).isFile();
  } catch {
    return false;
  }
}
