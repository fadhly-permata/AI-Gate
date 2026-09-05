/* ===== aigate Device Simulation helper (B4.2) — vanilla JS, no build ===== */
/* Pure validation of a device token. Loaded as a classic <script> in the
   browser (attaches window.aigate.deviceAttr) and importable in vitest for
   its side effect (same file works in both: it only touches window). */

(function () {
  "use strict";

  var ALLOWED = ["phone", "tablet", "desktop"];
  var DEFAULT_DEVICE = "desktop";

  /* Validate + normalize a device string.
     @param {*} device - any input (string expected).
     @returns {"phone"|"tablet"|"desktop"} canonical lowercase token,
              or "desktop" for any unknown / empty / falsy input. */
  function deviceAttr(device) {
    var v = (device == null ? "" : String(device)).trim().toLowerCase();
    return ALLOWED.indexOf(v) !== -1 ? v : DEFAULT_DEVICE;
  }

  // Expose for app.js + tests.
  window.aigate = window.aigate || {};
  window.aigate.deviceAttr = deviceAttr;
})();
