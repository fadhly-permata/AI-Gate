/* Device-view simulation modal (Opsi A — moved OUT of the Settings form).
 *
 * Contract under test (handover §2.5): a trigger (sidebar-footer on desktop,
 * .bn-device in the bottom-nav on phone) opens #deviceModal; selecting a mode is
 * scoped to the iframe ONLY — the live page (outer body[data-device]) and
 * localStorage are never touched; the dialog is accessible — focus moves
 * in on open, Tab is trapped inside, ESC closes and restores focus to the
 * trigger, and clicking the backdrop (outside the dialog) closes it.
 *
 * app.js runs its boot init() against an empty jsdom body at import time, so
 * the modal wiring is re-bound here with window.aigate.setupDeviceModal() after
 * the shipped markup is mounted (same pattern as provider_detail.test.js). */
import { describe, it, expect, beforeEach } from "vitest";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { join, dirname } from "path";
import { indexBodyHtml } from "./helpers/dom.js";

// Static guard against the device-preview left/right clip regression
// (handover-20260913-device-preview-clip-lr). jsdom does not lay out, so the
// geometry bug can't be caught by a DOM/behavior test; instead we assert the CSS
// itself no longer centers an overflowing flex child and no longer lets the
// modal box scroll. See §2.1–§2.4.
const STATIC_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "static");
const CSS = readFileSync(join(STATIC_DIR, "styles.css"), "utf8");

// Returns the body (between the first matching { and its matching }) of the
// FIRST occurrence of `selector { ... }` in `source`. Returns "" if absent.
function cssRuleBody(source, selector) {
  const start = source.indexOf(selector + " {");
  if (start === -1) return "";
  let i = source.indexOf("{", start);
  let depth = 0;
  for (; i < source.length; i++) {
    const ch = source[i];
    if (ch === "{") depth++;
    else if (ch === "}") {
      depth--;
      if (depth === 0) return source.slice(source.indexOf("{", start) + 1, i);
    }
  }
  return "";
}

import "../static/i18n.js";
import "../static/device.js";
import "../static/app.js";

function key(name, opts) {
  return new KeyboardEvent("keydown", Object.assign({ key: name, bubbles: true, cancelable: true }, opts || {}));
}

function mount() {
  document.body.innerHTML = indexBodyHtml();
  window.aigate.setupDeviceModal();
}

describe("device-sim control placement", () => {
  it("control lives ABOVE the Repo link in both shells, as a dialog trigger", () => {
    mount();
    // Desktop: sticky sidebar-footer, before the repo <a>.
    const desktop = document.getElementById("deviceTriggerDesktop");
    expect(desktop, "desktop trigger present").not.toBeNull();
    const repoFooter = document.querySelector('.sidebar-footer a[href*="github"]');
    expect(repoFooter.compareDocumentPosition(desktop) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();

    // Mobile: bottom-nav, directly before the repo .bn-item.
    const mobile = document.getElementById("deviceTriggerMobile");
    expect(mobile, "mobile trigger present").not.toBeNull();
    expect(mobile.classList.contains("bn-item"), "not a .bn-item (keeps nav parity)").toBe(false);
    const repoBn = document.querySelector('.bottom-nav a.bn-item[href*="github"]');
    expect(repoBn.compareDocumentPosition(mobile) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();

    // Both carry the dialog affordances.
    [desktop, mobile].forEach(function (t) {
      expect(t.getAttribute("aria-haspopup")).toBe("dialog");
      expect(t.getAttribute("aria-controls")).toBe("deviceModal");
    });
  });

  it("the #setDevice <select> is gone from the Settings form", () => {
    mount();
    expect(document.getElementById("setDevice")).toBeNull();
    expect(document.querySelector('.settings-form select[name="device"]')).toBeNull();
  });
});

describe("device-sim modal behaviour", () => {
  let modal, trigger, first, last;

  beforeEach(() => {
    localStorage.removeItem("aigate.device");
    // Precondition for the isolation test: the live page is on "desktop". Selecting
    // a mode in the modal must NOT change this (proof the outer body is untouched).
    document.body.dataset.device = "desktop";
    mount();
    modal = document.getElementById("deviceModal");
    trigger = document.getElementById("deviceTriggerMobile");
    const modes = modal.querySelectorAll("[data-device-mode]");
    first = modes[0]; // phone
    last = document.getElementById("deviceModalClose");
  });

  it("opens on trigger click, moves focus inside, dialog is labelled", () => {
    expect(modal.hidden).toBe(true);
    const dialog = modal.querySelector(".modal");
    expect(dialog.getAttribute("role")).toBe("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(dialog.getAttribute("aria-labelledby")).toBe("deviceModalTitle");
    trigger.focus();
    trigger.click();
    expect(modal.hidden).toBe(false);
    expect(document.activeElement).toBe(first); // focus the first control
  });

  it("selecting a mode previews in the iframe WITHOUT touching the live page", () => {
    trigger.click();
    first.click(); // phone
    // The live page must be untouched: the outer body keeps its pre-test value
    // (set in beforeEach) and the modal must never persist a device to localStorage.
    expect(document.body.dataset.device, "outer body unchanged").toBe("desktop");
    expect(localStorage.getItem("aigate.device"), "no localStorage write").toBeNull();
    // The preview IS sized to the device — the --dev-w/--dev-h vars that the
    // iframe + box read are set to the phone dims, and the button is marked.
    expect(modal.style.getPropertyValue("--dev-w")).toBe("375px");
    expect(modal.style.getPropertyValue("--dev-h")).toBe("667px");
    expect(first.classList.contains("is-active")).toBe(true);
    expect(first.getAttribute("aria-pressed")).toBe("true");
  });

  it("Tab on the last control wraps focus to the first (focus trap)", () => {
    trigger.click();
    last.focus();
    modal.dispatchEvent(key("Tab"));
    expect(document.activeElement).toBe(first);
  });

  it("Shift+Tab on the first control wraps to the last (focus trap)", () => {
    trigger.click();
    first.focus();
    modal.dispatchEvent(key("Tab", { shiftKey: true }));
    expect(document.activeElement).toBe(last);
  });

  it("ESC closes the dialog and restores focus to the trigger", () => {
    trigger.focus();
    trigger.click();
    expect(modal.hidden).toBe(false);
    modal.dispatchEvent(key("Escape"));
    expect(modal.hidden).toBe(true);
    expect(document.activeElement).toBe(trigger);
  });

  it("clicking the backdrop (outside the dialog) closes it", () => {
    trigger.focus();
    trigger.click();
    expect(modal.hidden).toBe(false);
    modal.dispatchEvent(new MouseEvent("click", { bubbles: true })); // target === overlay
    expect(modal.hidden).toBe(true);
    expect(document.activeElement).toBe(trigger);
  });

  it("clicking the dialog body (not the backdrop) does NOT close it", () => {
    trigger.click();
    expect(modal.hidden).toBe(false);
    const inner = modal.querySelector(".modal");
    inner.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(modal.hidden, "inner click is not a backdrop close").toBe(false);
  });
});

// Static regression guard (handover-20260913-device-preview-clip-lr §5). The
// clip was caused purely by CSS geometry, not JS, so it is pinned here at the
// stylesheet level: the two properties that caused it must never come back.
describe("device-preview clip-lr CSS guard", () => {
  const preview = cssRuleBody(CSS, ".device-preview");
  const box = cssRuleBody(CSS, ".modal.device-modal");

  it("found both rule blocks in styles.css", () => {
    expect(preview.length, ".device-preview block present").toBeGreaterThan(0);
    expect(box.length, ".modal.device-modal block present").toBeGreaterThan(0);
  });

  it(".device-preview no longer centers an overflowing flex child", () => {
    // justify-content:center split the overflow symmetrically; scrollLeft can't
    // go negative, so the LEFT edge became permanently unreachable.
    expect(preview, "no justify-content:center in .device-preview")
      .not.toMatch(/justify-content\s*:\s*center/);
    expect(preview).toMatch(/justify-content\s*:\s*flex-start/);
    // min-height:0 is required so the preview scrolls internally instead of
    // pushing the Close button out of a short viewport.
    expect(preview).toMatch(/min-height\s*:\s*0/);
  });

  it(".modal.device-modal hugs the device and does NOT scroll itself", () => {
    expect(box, "box hugs device").toMatch(/width\s*:\s*fit-content/);
    expect(box, "modal itself must not scroll")
      .not.toMatch(/overflow\s*:\s*auto/);
    expect(box).toMatch(/overflow\s*:\s*hidden/);
  });

  it(".device-frame-wrap safe-centers (flex:0 0 auto + margin-inline:auto)", () => {
    const wrap = cssRuleBody(CSS, ".device-frame-wrap");
    expect(wrap.length, ".device-frame-wrap block present").toBeGreaterThan(0);
    expect(wrap).toMatch(/margin-inline\s*:\s*auto/);
    expect(wrap).toMatch(/flex\s*:\s*0 0 auto/);
  });
});
