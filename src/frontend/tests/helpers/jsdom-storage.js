/* Make globalThis/window `.localStorage` + `.sessionStorage` be the jsdom
 * window's real storage again. Registered FIRST in vitest.config.js setupFiles.
 *
 * WHY THIS EXISTS
 * Node >= 22.4 (this box runs v26.4.0) defines its own `localStorage` and
 * `sessionStorage` on the JS global object. Vitest's jsdom environment copies
 * its window properties onto the global only when the name is NOT already in
 * the global (`getWindowKeys`: `if (k in global) return keysArray.includes(k)`),
 * and neither storage name is in vitest 2.1.9's KEYS allow-list (verified: the
 * string "localStorage" does not appear anywhere in its environment bundle).
 * So jsdom's working storage — vitest already creates the window with
 * `url: "http://localhost:3000"`, an opaque-origin-free URL where Storage is
 * available — is never copied, and tests see Node's stubs instead:
 *   - `globalThis.localStorage` is a getter that returns UNDEFINED unless node
 *     was started with --localstorage-file (its own storage is file-backed),
 *     so `localStorage.clear()` throws "Cannot read properties of undefined".
 *   - `globalThis.sessionStorage` happens to work, but it is Node's object,
 *     not the jsdom window's, so `window.sessionStorage` and the storage the
 *     document would see are different things.
 * This made every bare-localStorage test file order-dependent under
 * `isolate: false` (a file that stubbed storage leaked its stub to later
 * files in the same worker and masked the problem there).
 *
 * HOW THIS FIXES IT
 * Vitest exposes the live JSDOM instance as `globalThis.jsdom` (see its jsdom
 * environment setup: `global.jsdom = dom`). We re-point the two names at
 * `jsdom.window`'s storage via a delegating getter, i.e. exactly what vitest
 * itself would have installed had the key not pre-existed on the global. The
 * descriptor is kept `configurable: true` because terminal_discard.test.js
 * swaps `window.sessionStorage` (getOwnPropertyDescriptor + defineProperty +
 * restore) to simulate private mode / quota errors. The set-table override in
 * the closure mirrors vitest's own populateGlobal accessor so a plain
 * `window.localStorage = stub` assignment still works per file.
 */

const domInstance = globalThis.jsdom;

if (domInstance && domInstance.window) {
  const win = domInstance.window;
  for (const key of ["localStorage", "sessionStorage"]) {
    let overridden = false;
    let override;
    Object.defineProperty(globalThis, key, {
      configurable: true,
      enumerable: true,
      get() {
        return overridden ? override : win[key];
      },
      set(v) {
        overridden = true;
        override = v;
      }
    });
  }
}
