/* Per-worker test hygiene: silence the app's background pollers.
 *
 * WHY THIS EXISTS
 * `static/app.js` init() starts a 3s log poller (`startLogAutoRefresh`) and
 * `static/usage.js` init() starts a usage poller, both guarded by
 * `typeof fetch === "function"`. Node ships a global fetch, so in jsdom those
 * guards pass and the intervals are really created.
 *
 * With `isolate: false` the module registry is shared across test files inside
 * one worker, so a poller started by the first file that imports app.js keeps
 * running while *later* files in the same worker are executing. Two concrete
 * failures follow from that, and both are timing/worker-distribution dependent
 * (they appear or vanish when the fork count changes):
 *   - a poller callback lands inside a test that has just installed its own
 *     fetch spy, so the spy records a request the test never made
 *     (e.g. logwindow "cancel -> dialog closes, no request" sees 1 call, not 0);
 *   - a callback fires after `vi.unstubAllGlobals()` removed the stub, so the
 *     real `loadLogs()` runs with no fetch at all -> "ReferenceError: fetch is
 *     not defined" as an unhandled error.
 *
 * The production code is correct (a real page reload clears the interval), and
 * it is out of scope for tests, so the leak is closed here instead: both
 * pollers already expose stop functions on `window.aigate`, and stopping them
 * after every test keeps each test's network view to itself.
 *
 * Registered as `setupFiles` in vitest.config.js so it applies to every test
 * file from one place instead of being copy-pasted into each afterEach.
 */
import { afterEach } from "vitest";

afterEach(() => {
  const api = typeof window !== "undefined" ? window.aigate : null;
  if (!api) return;
  // Optional-call: files that never import app.js/usage.js have no such method.
  api.stopLogAutoRefresh?.();
  api.stopUsageAutoRefresh?.();
});
