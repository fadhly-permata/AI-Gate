/**
 * Guard for the e2e TOOLING itself (static checks — no browser needed).
 *
 * WHY these exist: e2e/b5_features.mjs and e2e/playwright.config.js were never
 * executed by anything in this repo. `vitest` only collects tests/**, and jsdom
 * never runs a browser, so a runner that cannot even reach its first assertion
 * stayed green for months. Four real defects are pinned here so they cannot
 * silently come back:
 *   #1 $$eval hands the callback an ARRAY (querySelectorAll result) — the old
 *      `(card) => card.querySelector(...)` threw "card.querySelector is not a
 *      function" in every browser. Needs $eval.
 *   #2 no explicit viewport -> puppeteer default 800x600, where the always-on,
 *      bottom-docked Log Window covers the row ⋮ button (measured: button
 *      294-322px vs panel top 219px) and every click lands on the panel.
 *   #3 testDir is resolved RELATIVE TO THE CONFIG FOLDER, so "e2e" meant
 *      src/frontend/e2e/e2e -> "Error: No tests found".
 *   #4 `use.executablePath` is NOT a Playwright Test option (0 hits in
 *      node_modules/playwright/types/test.d.ts) — it was ignored in silence and
 *      Playwright kept looking for its own headless_shell. Correct home:
 *      use.launchOptions.executablePath (LaunchOptions, types.d.ts:24981).
 * Plus the #6 favicon guard (browser used to auto-request /favicon.ico -> 404).
 */
import { describe, it, expect } from "vitest";
import { readFileSync, existsSync, statSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const FE_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const E2E = path.join(FE_ROOT, "e2e");
const STATIC = path.join(FE_ROOT, "static");

const read = (p) => {
  expect(existsSync(p), `berkas e2e hilang: ${p}`).toBe(true);
  return readFileSync(p, "utf8");
};
const RUNNER = read(path.join(E2E, "b5_features.mjs"));
const CONFIG = read(path.join(E2E, "playwright.config.js"));
const RUN_SH = read(path.join(E2E, "run.mjs"));

/** Source of a file with comments removed (guards must not fire on prose that
 *  merely mentions the bad pattern — both comment shapes are stripped). */
function code(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .split("\n")
    .filter((l) => !/^\s*\/\//.test(l))
    .join("\n");
}
const RUNNER_CODE = code(RUNNER);
const CONFIG_CODE = code(CONFIG);

/* ------------------------------------------------------------------ #1 */
describe("e2e guard #1 — $$eval callbacks must treat their argument as an array", () => {
  /** Every `$$eval(...)` call site, with its callback source (balanced scan). */
  function dollarDollarEvalCallbacks(src) {
    const out = [];
    const needle = "$$eval(";
    for (let i = src.indexOf(needle); i !== -1; i = src.indexOf(needle, i + 1)) {
      // walk to the matching close paren of the call
      let depth = 0;
      let j = i + needle.length - 1;
      for (; j < src.length; j++) {
        if (src[j] === "(") depth++;
        else if (src[j] === ")") { depth--; if (depth === 0) break; }
      }
      const call = src.slice(i, j + 1);
      const m = call.match(/,\s*\(\s*([A-Za-z_$][\w$]*)\s*\)\s*=>/);
      if (m) out.push({ param: m[1], body: call.slice(call.indexOf(m[0]) + m[0].length - 2) });
    }
    return out;
  }

  it("the runner really contains $$eval call sites (sanity: guard is not vacuous)", () => {
    expect(dollarDollarEvalCallbacks(RUNNER_CODE).length).toBeGreaterThanOrEqual(2);
  });

  it("no $$eval callback calls <param>.querySelector(...) — that is a TypeError", () => {
    const bad = dollarDollarEvalCallbacks(RUNNER_CODE).filter(
      ({ param, body }) => new RegExp(`\\b${param}\\.(querySelector|closest|getAttribute|classList)\\b`).test(body)
    );
    expect(bad, "$$eval mengirim ARRAY, bukan elemen -> pakai $eval untuk akses per elemen").toEqual([]);
  });

  it("the account-card probe uses $eval (single element)", () => {
    expect(RUNNER_CODE).toMatch(/\$eval\("#accList \.acc-card:first-child",\s*\(card\)\s*=>/);
  });
});

/* ------------------------------------------------------------------ #2 */
describe("e2e guard #2 — viewport must be explicit (Log Window must not eat clicks)", () => {
  it("puppeteer runner sets a viewport wider/taller than the 800x600 default", () => {
    expect(RUNNER_CODE).toMatch(/setViewport\(/);
    const m = RUNNER_CODE.match(/const VIEWPORT = \{\s*width: (\d+),\s*height: (\d+)/);
    expect(m, "VIEWPORT konstan tidak ditemukan").not.toBeNull();
    expect(Number(m[1])).toBeGreaterThanOrEqual(1280);
    expect(Number(m[2])).toBeGreaterThanOrEqual(720);
  });

  it("puppeteer runner starts with the Log Window closed (product pref, not a force-click)", () => {
    expect(RUNNER_CODE).toMatch(/aigate\.logVisible/);
    expect(RUNNER_CODE).toMatch(/evaluateOnNewDocument/);
    // force-click would hide the overlap instead of fixing it — must stay absent
    expect(RUNNER_CODE).not.toMatch(/click\([^)]*\{\s*force/);
  });

  it("playwright config pins a viewport of at least 1280x720", () => {
    const m = CONFIG_CODE.match(/viewport:\s*\{\s*width:\s*(\d+),\s*height:\s*(\d+)/);
    expect(m, "viewport eksplisit hilang dari projects[].use").not.toBeNull();
    expect(Number(m[1])).toBeGreaterThanOrEqual(1280);
    expect(Number(m[2])).toBeGreaterThanOrEqual(720);
  });
});

/* ------------------------------------------------------------------ #3/4 */
describe("e2e guard #3/#4 — playwright.config.js options that actually work", () => {
  it("testDir is an absolute path, not a name resolved against the config dir", () => {
    expect(CONFIG_CODE).toMatch(/testDir:\s*HERE/);
    expect(CONFIG_CODE).not.toMatch(/testDir:\s*["']e2e["']/);
    // and the folder it points at really holds the spec
    expect(existsSync(path.join(E2E, "smoke.spec.js"))).toBe(true);
  });

  it("executablePath lives in launchOptions (use.executablePath is not an option)", () => {
    const useBlock = CONFIG_CODE.slice(CONFIG_CODE.indexOf("use: {"), CONFIG_CODE.indexOf("webServer:"));
    expect(useBlock).toMatch(/launchOptions:\s*\{[^}]*executablePath/);
    // a bare `executablePath:` directly under use: = silently ignored
    expect(useBlock.replace(/launchOptions:\s*\{[^}]*\}/, "")).not.toMatch(/^\s*executablePath:/m);
    // proven against the shipped typings: not a UseOption, IS a LaunchOptions key
    const types = path.join(FE_ROOT, "node_modules", "playwright", "types", "test.d.ts");
    const launchTypes = path.join(FE_ROOT, "node_modules", "playwright-core", "types", "types.d.ts");
    if (existsSync(types)) expect(readFileSync(types, "utf8")).not.toMatch(/^\s*executablePath\??:/m);
    if (existsSync(launchTypes)) expect(readFileSync(launchTypes, "utf8")).toMatch(/executablePath\??: string/);
  });

  it("no-tests-found cannot come back silently: runner passes --config explicitly", () => {
    // the CLI only looks for playwright.config.* in the CWD (src/frontend),
    // so without --config this file is never read.
    expect(RUN_SH).toMatch(/--config/);
    expect(RUN_SH).toMatch(/playwright\.config\.js/);
    expect(RUN_SH).toMatch(/NODE_OPTIONS/);
    expect(RUN_SH).toMatch(/platform/);
  });

  it("no bare `npx`/global CLI call is left in the runner (npx is broken here)", () => {
    // the runner must spawn the local playwright cli.js through process.execPath
    const body = RUN_SH.replace(/^\s*\/\/.*$/gm, "");
    expect(body).not.toMatch(/\bnpx\b/);
    expect(body).toMatch(/process\.execPath/);
    expect(body).toMatch(/cli\.js/);
  });
});

/* ---------------------------------------------------------- package.json */
describe("e2e guard — npm scripts point at files that really exist", () => {
  const pkgPath = path.join(FE_ROOT, "package.json");
  const pkg = JSON.parse(readFileSync(pkgPath, "utf8"));
  const scripts = pkg.scripts || {};

  it("test:e2e runs the runner, not the bare `playwright` CLI", () => {
    // `playwright test` from src/frontend/ never loads e2e/playwright.config.js
    // (config lookup is CWD-based) and its CLI cannot even be imported on
    // Termux — see e2e/run.mjs.
    expect(scripts["test:e2e"]).toBe("node e2e/run.mjs");
    expect(scripts["test:e2e"]).not.toMatch(/^\s*playwright\b/);
    expect(scripts["test:e2e"]).not.toMatch(/\bnpx\b/);
  });

  it("every e2e script targets an existing file (read from package.json)", () => {
    const e2eScripts = Object.entries(scripts).filter(([name]) => /^test:e2e/.test(name));
    expect(e2eScripts.length).toBeGreaterThanOrEqual(3); // e2e + android + b5
    for (const [name, cmd] of e2eScripts) {
      const m = cmd.match(/node\s+(\S+)/);
      expect(m, `${name} bukan perintah "node <berkas>": ${cmd}`).not.toBeNull();
      const target = path.join(FE_ROOT, m[1]);
      expect(existsSync(target), `${name} -> ${m[1]} tidak ada`).toBe(true);
      expect(statSync(target).size).toBeGreaterThan(0);
    }
    // and each of those files exists as written above (no dead script entries)
    expect(path.basename(path.join(E2E, "run.mjs"))).toBe("run.mjs");
  });

  it("dependency list is untouched by the e2e repair (no new vendor/CDN dep)", () => {
    expect(Object.keys(pkg.devDependencies).sort()).toEqual(
      ["@playwright/test", "jsdom", "puppeteer-core", "vitest"]
    );
  });
});

/* ------------------------------------------------------------------ #6 */
describe("favicon guard — no more automatic /favicon.ico 404", () => {
  const html = readFileSync(path.join(STATIC, "index.html"), "utf8");

  it("index.html points at a local icon (SVG for modern browsers, .ico fallback)", () => {
    expect(html).toMatch(/<link[^>]+rel="icon"[^>]+href="favicon\.svg"/);
    expect(html).toMatch(/<link[^>]+rel="(?:alternate|shortcut) icon"[^>]+href="favicon\.ico"/);
  });

  it("both referenced files exist next to index.html (local asset, no CDN)", () => {
    for (const f of ["favicon.svg", "favicon.ico"]) {
      const p = path.join(STATIC, f);
      expect(existsSync(p), f + " tidak ada").toBe(true);
      expect(statSync(p).size).toBeGreaterThan(0);
    }
    // the SVG must not FETCH anything off-box: the only URL allowed inside an
    // SVG is its own xmlns namespace declaration.
    const svg = readFileSync(path.join(STATIC, "favicon.svg"), "utf8");
    expect(svg.replace(/xmlns(?::xlink)?="[^"]*"/g, "")).not.toMatch(/https?:\/\//);
    expect(svg).not.toMatch(/<image|url\(|xlink:href/i);
  });

  it("favicon.ico is a real ICO container with one 32x32 32bpp entry", () => {
    const buf = readFileSync(path.join(STATIC, "favicon.ico"));
    expect(buf.readUInt16LE(0)).toBe(0);   // reserved
    expect(buf.readUInt16LE(2)).toBe(1);   // type = icon
    expect(buf.readUInt16LE(4)).toBe(1);   // one image
    expect(buf[6]).toBe(32);               // width  (0 would mean 256)
    expect(buf[7]).toBe(32);               // height
    expect(buf.readUInt16LE(12)).toBe(32); // bit depth
    expect(buf.readUInt32LE(14)).toBe(buf.length - 22); // image size follows
  });
});
