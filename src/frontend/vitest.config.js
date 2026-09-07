import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    globals: true,
    include: ["tests/**/*.test.js"],
    // Speed: reuse one jsdom + module registry across files instead of
    // rebuilding the environment per file. Measured ~2x faster wall time
    // (environment cost dominated: 84.9s -> 25.4s on 23 files). Safe because
    // terminal.js caches DOM refs in its IIFE init(); the only file that
    // asserts on a cached-ref side effect (terminal_exit's #termEmpty.hidden)
    // is now self-contained via vi.resetModules()+re-import (see that file).
    // The other terminal files (reconnect/layout/swipe/toolbar) import once and
    // pass because they assert via live getElementById + shared T()._tabs, not
    // via cached refs. If forks are ever raised above 1 (os.cpus()=0 here keeps
    // it sequential) or a new test reads a cached-DOM side effect, give it the
    // same resetModules treatment. RAISE isolate back to true if a test needs
    // pristine module/global state it cannot reset itself.
    isolate: false
  }
});
