import { describe, it, expect, beforeEach, afterEach } from "vitest";

// i18n.js attaches window.I18N + window.applyLocale (jsdom provides DOM).
import "../static/i18n.js";
// app.js wires the Settings panel and exposes window.aigate.buildSettingsBody.
import "../static/app.js";

describe("i18n.applyLocale (B1.3 keys)", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div data-i18n="nav.settings"></div>
      <span data-i18n="settings.port"></span>
      <span data-i18n="settings.dev_mode"></span>
      <span data-i18n="settings.theme"></span>
      <span data-i18n="settings.locale"></span>
      <button data-i18n="settings.save"></button>
    `;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("translates the new Settings labels to Indonesian", () => {
    window.applyLocale("id");
    const q = (k) => document.querySelector('[data-i18n="' + k + '"]').textContent;
    expect(q("nav.settings")).toBe("Pengaturan");
    expect(q("settings.port")).toBe("Port");
    expect(q("settings.dev_mode")).toBe("Mode Pengembang");
    expect(q("settings.theme")).toBe("Tema");
    expect(q("settings.locale")).toBe("Bahasa");
    expect(q("settings.save")).toBe("Simpan");
  });

  it("translates the new Settings labels to English", () => {
    window.applyLocale("en");
    const q = (k) => document.querySelector('[data-i18n="' + k + '"]').textContent;
    expect(q("nav.settings")).toBe("Settings");
    expect(q("settings.dev_mode")).toBe("Developer Mode");
    expect(q("settings.save")).toBe("Save");
  });
});

describe("settings PUT body builder", () => {
  beforeEach(() => {
    // Mirror the real settings form so buildSettingsBody reads real DOM.
    document.body.innerHTML = `
      <form id="settingsForm">
        <input type="number" id="setPort" value="8080" />
        <input type="checkbox" id="setDevMode" checked />
        <select id="setTheme"><option value="dark" selected>Dark</option></select>
        <select id="setLocale"><option value="id" selected>ID</option></select>
      </form>
    `;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("stringifies every value (numbers, booleans) into the {settings:{...}} shape", () => {
    const body = window.aigate.buildSettingsBody();
    expect(body).toHaveProperty("settings");
    const s = body.settings;
    // All values must be strings per the API contract.
    expect(typeof s.port).toBe("string");
    expect(s.port).toBe("8080");
    expect(typeof s.dev_mode).toBe("string");
    expect(s.dev_mode).toBe("true");
    expect(s.theme).toBe("dark");
    expect(s.locale).toBe("id");
  });

  it("serializes an unchecked dev_mode as the string 'false'", () => {
    document.getElementById("setDevMode").checked = false;
    const s = window.aigate.buildSettingsBody().settings;
    expect(s.dev_mode).toBe("false");
  });
});
