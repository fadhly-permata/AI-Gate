#!/usr/bin/env node
/**
 * i18n parity checker (PM-owned tool, fast path for locale authors).
 *
 * usage:  node .opencode/tools/tests/i18n-parity-check.mjs <locale-code> [<locale-code> ...]
 * example: node .opencode/tools/tests/i18n-parity-check.mjs ru zh-tw
 *
 * Loads src/frontend/static/i18n/en.js as the reference and each target dictionary
 * in a bare VM context (they self-register onto `window.I18N`), then compares the
 * KEY SETS. Exit 0 = every target has exactly the EN key set; exit 1 = differences.
 *
 * Why this exists: the real gate is `src/frontend/tests/i18n.test.js` (vitest, globs
 * the i18n dir). Running the whole suite per locale on a throttled phone is wasteful
 * (rule R35), so locale authors use this 0.1s check and the PM runs vitest once.
 */
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const I18N_DIR = resolve(here, "../../../src/frontend/static/i18n");

function load(code) {
  const file = join(I18N_DIR, `${code}.js`);
  let src;
  try {
    src = readFileSync(file, "utf8");
  } catch {
    return { error: `tidak bisa baca ${code}.js (path: ${file})` };
  }
  const ctx = createContext({ window: {} });
  try {
    runInContext(src, ctx, { filename: `${code}.js` });
  } catch (e) {
    return { error: `file ${code}.js error saat dijalankan: ${e.message}` };
  }
  const dict = ctx.window.I18N && ctx.window.I18N[code];
  if (!dict) {
    return {
      error:
        `${code}.js harus self-register: window.I18N = window.I18N || {}; ` +
        `window.I18N.${code} = { ... }`,
    };
  }
  return { dict };
}

const ref = load("en");
if (ref.error) {
  console.error("rujukan EN rusak:", ref.error);
  process.exit(1);
}
const refKeys = Object.keys(ref.dict);
const codes = process.argv.slice(2);
if (!codes.length) {
  console.error("usage: i18n-parity-check.mjs <locale-code> [...]");
  process.exit(2);
}

let bad = 0;
for (const code of codes) {
  const t = load(code);
  if (t.error) {
    console.log(`FAIL ${code}: ${t.error}`);
    bad++;
    continue;
  }
  const keys = Object.keys(t.dict);
  const set = new Set(keys);
  const missing = refKeys.filter((k) => !set.has(k));
  const extra = keys.filter((k) => !refKeys.includes(k));
  const empty = keys.filter(
    (k) => typeof t.dict[k] !== "string" || t.dict[k].trim() === ""
  );
  const untranslated = keys.filter(
    (k) => t.dict[k] === ref.dict[k] && !/^[^A-Za-z]*$/.test(t.dict[k])
  );
  const ok = !missing.length && !extra.length && !empty.length;
  console.log(
    `${ok ? "OK  " : "FAIL"} ${code}: ${keys.length} kunci (rujukan ${refKeys.length})` +
      ` | hilang ${missing.length} | thừa ${extra.length} | kosong ${empty.length}` +
      ` | masih-sama-EN ${untranslated.length}`
  );
  if (missing.length) console.log("     hilang:", missing.slice(0, 40).join(", "));
  if (extra.length) console.log("     thừa:", extra.slice(0, 40).join(", "));
  if (empty.length) console.log("     kosong:", empty.slice(0, 40).join(", "));
  if (untranslated.length)
    console.log(
      "     catatan (boleh jadi memang tidak diterjemahkan, mis. nama produk/istilah):",
      untranslated.slice(0, 25).join(", ")
    );
  if (!ok) bad++;
}
process.exit(bad ? 1 : 0);
