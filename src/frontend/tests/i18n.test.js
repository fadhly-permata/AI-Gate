import { describe, it, expect, beforeEach, afterEach } from "vitest";

// i18n.js is a side-effect module: it attaches window.I18N + window.applyLocale
// and uses document inside applyLocale. jsdom (configured in vitest.config.js)
// provides window/document, so we just import for the side effect.
import "../static/i18n.js";

describe("i18n.applyLocale", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div data-i18n="app.title"></div>
      <nav data-i18n="nav.providers"></nav>
      <button data-i18n-aria="btn.menu"></button>
    `;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("applies Indonesian translations from window.I18N", async () => {
    window.applyLocale("id");
    const title = document.querySelector('[data-i18n="app.title"]');
    const providers = document.querySelector('[data-i18n="nav.providers"]');
    expect(title.textContent).toBe(window.I18N.id["app.title"]);
    expect(providers.textContent).toBe(window.I18N.id["nav.providers"]);
    // nav.providers differs EN/ID — meaningful language switch assertion
    expect(providers.textContent).toBe("Penyedia");
    expect(document.documentElement.getAttribute("lang")).toBe("id");
    expect(document.documentElement.getAttribute("data-locale")).toBe("id");
  });

  it("reverts to English on applyLocale('en')", async () => {
    window.applyLocale("id");
    window.applyLocale("en");
    const providers = document.querySelector('[data-i18n="nav.providers"]');
    expect(providers.textContent).toBe(window.I18N.en["nav.providers"]);
    expect(providers.textContent).toBe("Providers");
    expect(document.documentElement.getAttribute("lang")).toBe("en");
  });

  it("sets aria-label from data-i18n-aria", async () => {
    window.applyLocale("id");
    const btn = document.querySelector("[data-i18n-aria]");
    expect(btn.getAttribute("aria-label")).toBe(window.I18N.id["btn.menu"]);
  });

  it("every English key has an Indonesian translation (no drift)", () => {
    const en = Object.keys(window.I18N.en).sort();
    const id = Object.keys(window.I18N.id).sort();
    expect(id).toEqual(en);
  });
});
