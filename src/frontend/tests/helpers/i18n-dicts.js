/* Test-environment i18n dictionary loader.
 *
 * WHY THIS EXISTS
 * In the browser, dictionaries are separate files (static/i18n/<code>.js) that
 * <script> tags load — see the inline preloader in index.html and the on-demand
 * loader in static/i18n.js. Vitest has no page and no <head>, so nothing would
 * ever load them: `window.I18N` would stay empty and every test that asserts on
 * translated text would fail.
 *
 * This file closes that gap once per worker: it eagerly imports every locale
 * file, which self-registers into `window.I18N`, and is registered in
 * `setupFiles` (vitest.config.js) so no test file has to know about it. The
 * 20+ existing files that `import "../static/i18n.js"` keep working unchanged.
 *
 * `localeCodes()` is exported so tests/i18n.test.js can enumerate the same set
 * of files for the key-parity guard — one glob, one source of truth.
 */
const dictModules = import.meta.glob("../../static/i18n/*.js", { eager: true });

/** Locale codes derived from the file names, sorted: "en.js" -> "en", "zh-tw.js" -> "zh-tw". */
export function localeCodes() {
  return Object.keys(dictModules)
    .map((p) => p.replace(/^.*\//, "").replace(/\.js$/, ""))
    .sort();
}
