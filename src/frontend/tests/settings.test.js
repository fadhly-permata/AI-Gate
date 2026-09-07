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

/* ===== Settings locale select is built from the registry =====
   One file per language means index.html can no longer list the languages by
   hand: app.js renders the <select> from window.LANGS. These guards pin that
   down, including the failure mode a 7-locale registry would otherwise create
   (a stored locale with no <option> -> empty select -> saving wipes the pref). */
describe("Settings locale select (registry-driven)", () => {
  let savedLocale;

  beforeEach(() => {
    document.body.innerHTML = `
      <form id="settingsForm">
        <select id="setTheme"><option value="light" selected>Light</option></select>
        <select id="setLocale">
          <option value="en" selected>English</option>
          <option value="id">Indonesian</option>
        </select>
      </form>
    `;
    // <html data-locale> is shared state under isolate:false — snapshot it so
    // these tests cannot leak a fake locale into later files.
    savedLocale = document.documentElement.getAttribute("data-locale");
    localStorage.removeItem("aigate.locale");
  });

  afterEach(() => {
    document.body.innerHTML = "";
    localStorage.removeItem("aigate.locale");
    if (savedLocale === null) document.documentElement.removeAttribute("data-locale");
    else document.documentElement.setAttribute("data-locale", savedLocale);
  });

  it("offers every registered language, so a new locale needs no HTML edit", () => {
    window.aigate.populateLocaleOptions();
    const sel = document.getElementById("setLocale");
    expect(Array.from(sel.options).map((o) => o.value)).toEqual(window.LANGS.map((l) => l.code));
    const zhTw = sel.querySelector('option[value="zh-tw"]');
    expect(zhTw.textContent).toContain("繁體中文");
    expect(zhTw.textContent).toContain("🇹🇼");
  });

  it("keeps the active locale selected", () => {
    document.documentElement.setAttribute("data-locale", "id");
    window.aigate.populateLocaleOptions();
    expect(document.getElementById("setLocale").value).toBe("id");
  });

  it("falls back to the stored preference when no locale is active yet", () => {
    document.documentElement.removeAttribute("data-locale");
    localStorage.setItem("aigate.locale", "id");
    window.aigate.populateLocaleOptions();
    expect(document.getElementById("setLocale").value).toBe("id");
  });

  it("never leaves the select empty for an unknown stored locale", () => {
    document.documentElement.setAttribute("data-locale", "klingon");
    window.aigate.populateLocaleOptions();
    const sel = document.getElementById("setLocale");
    expect(sel.value).not.toBe("");
    expect(window.aigate.buildSettingsBody().settings.locale).not.toBe("");
  });
});
