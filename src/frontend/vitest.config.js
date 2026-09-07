import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.js"],
    // Speed: reuse one jsdom + module registry across files instead of
    // rebuilding the environment per file. Measured ~2x faster wall time
    // (environment cost dominated: 84.9s -> 25.4s on 23 files). Safe because
    // terminal.js caches DOM refs in its IIFE init(); a file that asserts on a
    // cached-ref side effect must be self-contained via vi.resetModules()+
    // re-import (see terminal_exit.test.js). Files asserting via live
    // getElementById + shared T()._tabs are fine as-is. RAISE isolate back to
    // true if a test needs pristine module/global state it cannot reset itself.
    isolate: false,
    // Stops app.js/usage.js background pollers after every test. Needed with
    // `isolate: false`: they start once per worker at import time and would
    // otherwise leak fetch calls into later files in the same worker.
    // See tests/helpers/quiet.js.
    setupFiles: ["./tests/helpers/quiet.js"],
    // Cap the worker count. Termux reports `os.cpus().length === 0`, so vitest
    // falls back to availableParallelism() = 8 forks and oversubscribes a
    // throttled phone CPU: each fork rebuilds the jsdom environment and the
    // ~250 KB module graph, so phase sums blow up (collect 20.5s, environment
    // 24.8s) while wall time stays flat. Measured wall, same box, 484 tests green:
    //   1 -> 12.6s  2 -> 8.3s  3 -> 10.5s  4 -> 10.4s  6 -> 12.6s  8 (default) -> 12.2s
    // Tuned for THIS box; on an unthrottled multi-core host a higher cap wins.
    pool: "forks",
    poolOptions: { forks: { maxForks: 2, minForks: 1 } }
  }
});
