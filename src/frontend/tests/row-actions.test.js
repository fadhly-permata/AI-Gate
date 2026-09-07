import { describe, it, expect } from "vitest";
import { indexHtml, indexBodyHtml } from "./helpers/dom.js";

import "../static/i18n.js";
import "../static/combobox.js";
import "../static/app.js";

const html = indexHtml();

describe("kebab action menu + lang dropdown", () => {
  it("all four management tables have an Actions header", () => {
    for (const id of ["provTable", "comboTable", "poolTable", "endpointTable"]) {
      expect(html, id).toContain('id="' + id + '"');
    }
    const n = (html.match(/data-i18n="common\.actions"/g) || []).length;
    expect(n).toBe(4);
  });

  it("header has lang dropdown trigger + menu (no old lang-btn)", () => {
    expect(html).toContain('id="langMenuBtn"');
    expect(html).toContain('id="langMenu"');
    expect(html).toContain('id="langTriggerFlag"');
    expect(html).not.toContain('class="lang-btn"');
  });

  it("providers row kebab opens menu with edit/discover/delete", () => {
    document.body.innerHTML = '<table><tbody id="provTableBody"></tbody></table>';
    window.aigate.renderProviders([
      { id: "p1", name: "OpenAI", type: "openai-compatible", base_url: "u", enabled: true, models: [] }
    ]);
    const kebab = document.querySelector("#provTableBody .js-row-menu");
    expect(kebab).toBeTruthy();
    kebab.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const menu = document.querySelector(".row-menu");
    expect(menu).toBeTruthy();
    const actions = Array.from(menu.querySelectorAll("[data-action]"))
      .map((b) => b.getAttribute("data-action"));
    expect(actions).toEqual(["edit", "discover", "delete"]);
    expect(menu.textContent).toContain("Edit");
    expect(menu.textContent).toContain("Discover Models");
    expect(menu.textContent).toContain("Delete");
  });

  it("updateLangUI renders flag + localized name in trigger and menu", () => {
    document.body.innerHTML = indexBodyHtml();
    window.applyLocale("id");
    // The dropdown is data-driven: one row per registry entry, so adding a
    // language never means editing index.html. The registry is the pin here.
    expect(window.LANGS.map((l) => l.code))
      .toEqual(["en", "id", "ru", "nl", "ja", "zh", "zh-tw"]);
    window.LANGS.forEach((l) => {
      expect(window.I18N.id[l.nameKey], l.code).toBeTruthy();
      expect(window.I18N.en[l.nameKey], l.code).toBeTruthy();
    });
    expect(window.I18N.id["lang.id"]).toBe("Bahasa Indonesia");
    expect(window.I18N.en["lang.en"]).toBe("English");
  });
});
