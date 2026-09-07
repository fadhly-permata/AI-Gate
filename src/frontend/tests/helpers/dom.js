/* Shared, cached access to the shipped frontend fixtures.
 *
 * WHY THIS EXISTS
 * static/index.html is ~63 KB. Before this helper, 10 different test files each
 * did their own `readFileSync(index.html)` + `new JSDOM(html)`. One
 * `new JSDOM(index.html)` costs ~320 ms on this box, so the same page was
 * parsed 10 times per run — pure duplicate work, all of it in the collect phase
 * because it sat in `describe` bodies.
 *
 * With `isolate: false` (see vitest.config.js) the module registry is shared
 * across test files inside a worker, so this module-level cache is populated
 * once and reused by every file in that worker: one read, one parse.
 * (Verified: a probe counter in this file stays at 1 across two test files.)
 *
 * CONTRACT — READ-ONLY
 * `indexDocument()` hands out ONE SHARED document. JSDOM builds it without
 * `runScripts`, so it is inert: no app code ever touches it, and every consumer
 * in tests/ only queries it. DO NOT mutate the returned document (no innerHTML
 * writes, no appendChild/remove/setAttribute). A test that needs to mutate the
 * shipped markup must take its own copy into its OWN test environment instead —
 * `indexBodyHtml()` returns the cached `<body>` markup so the test can do
 * `document.body.innerHTML = indexBodyHtml()` in its own jsdom. Sharing a
 * mutable node across files would leak state between tests.
 *
 * This helper changes no test behaviour: it only removes duplicate I/O and
 * duplicate parsing.
 */
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { createRequire } from "module";

const here = dirname(fileURLToPath(import.meta.url));
const STATIC_DIR = join(here, "..", "..", "static");

/** Read (once) and return the shipped static/index.html source. */
let htmlCache = null;
export function indexHtml() {
  if (htmlCache === null) {
    htmlCache = readFileSync(join(STATIC_DIR, "index.html"), "utf8");
  }
  return htmlCache;
}

/** Read (once) a shipped static source file by name, e.g. "app.js". */
const sourceCache = new Map();
export function staticSource(name) {
  if (!sourceCache.has(name)) {
    sourceCache.set(name, readFileSync(join(STATIC_DIR, name), "utf8"));
  }
  return sourceCache.get(name);
}

/**
 * jsdom is loaded LAZILY (createRequire inside the accessor, never a
 * top-level import) on purpose: most consumers only want HTML/CSS text, and
 * pulling jsdom in eagerly would make every file that imports this helper load
 * the whole jsdom graph — costing more than the parsing it saves.
 */
let jsdomRequire = null;
function JSDOMClass() {
  if (jsdomRequire === null) {
    jsdomRequire = createRequire(import.meta.url)("jsdom");
  }
  return jsdomRequire.JSDOM;
}

/**
 * Parse index.html ONCE and return the shared, READ-ONLY document.
 * See the contract at the top of this file before mutating anything.
 */
let docCache = null;
export function indexDocument() {
  if (docCache === null) {
    const JSDOM = JSDOMClass();
    docCache = new JSDOM(indexHtml()).window.document;
  }
  return docCache;
}

/**
 * The cached markup between <body> and </body>, for tests that need the
 * shipped page inside their OWN jsdom document (i.e. anything that mutates).
 * Returns a string; assigning it to `document.body.innerHTML` parses into the
 * calling test's document, so no node is ever shared.
 */
let bodyCache = null;
export function indexBodyHtml() {
  if (bodyCache === null) {
    const html = indexHtml();
    bodyCache = html.slice(html.indexOf("<body>"), html.indexOf("</body>"));
  }
  return bodyCache;
}

/**
 * NOTE — tried and reverted: mounting the shipped page with a cached
 * `<template>` + `cloneNode(true)` instead of `innerHTML = indexBodyHtml()`.
 * Measured on this box it is 5x SLOWER (1146 ms vs 214 ms for one mount):
 * jsdom's deep clone of a ~1.5k-node tree costs far more than its HTML parser,
 * so parsing once and cloning many does not pay off here. `innerHTML` stays.
 */

/** Raw shipped styles.css, read once. */
let cssRawCache = null;
export function stylesCssRaw() {
  if (cssRawCache === null) {
    cssRawCache = readFileSync(join(STATIC_DIR, "styles.css"), "utf8");
  }
  return cssRawCache;
}

/**
 * styles.css with CSS comments stripped, computed once. Several test files
 * assert on CSS rule text; the comment-stripped source is the shared contract,
 * so an explanatory comment can never satisfy a "the old value is gone" regex.
 */
let cssCache = null;
export function stylesCss() {
  if (cssCache === null) {
    cssCache = stylesCssRaw().replace(/\/\*[\s\S]*?\*\//g, "");
  }
  return cssCache;
}
