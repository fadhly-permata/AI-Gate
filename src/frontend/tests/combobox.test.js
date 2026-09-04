import { describe, it, expect, beforeEach, afterEach } from "vitest";

// i18n.js provides window.I18N so the widget's getStr() resolves labels.
import "../static/i18n.js";
// combobox.js attaches window.aigate.createCombobox (the widget under test).
import "../static/combobox.js";

// Build a minimal input + <ul> panel and return a fresh controller. The
// combobox resolves elements BY id and delegates every listener on `document`,
// so one controller maps cleanly onto this rebuilt DOM.
function mount() {
  document.body.innerHTML =
    '<div class="aigate-combo">' +
      '<input type="text" id="cbModel" />' +
      '<ul id="cbModelList" hidden></ul>' +
    "</div>";
  return window.aigate.createCombobox({ inputId: "cbModel", listId: "cbModelList" });
}

const input = () => document.getElementById("cbModel");
const list = () => document.getElementById("cbModelList");
const optionEls = () => Array.from(list().querySelectorAll('li[role="option"]'));
const optionValues = () => optionEls().map((li) => li.getAttribute("data-value"));
const optionTexts = () => optionEls().map((li) => li.textContent);

// Type into the input (fires the delegated `input` handler -> filter + open).
function type(v) {
  input().value = v;
  input().dispatchEvent(new Event("input", { bubbles: true }));
}
function key(k) {
  input().dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true }));
}

const MODELS = [
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "llama-3.1", label: "Llama 3.1" },
  { value: "qwen-coder", label: "Qwen Coder" }
];

describe("combobox — setOptions + render", () => {
  let cb;
  beforeEach(() => { cb = mount(); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("renders one role=option row per model, label shown, value carried", () => {
    cb.setOptions(MODELS);
    cb.open();
    expect(optionValues()).toEqual(["gpt-4o", "llama-3.1", "qwen-coder"]);
    expect(optionTexts()).toEqual(["GPT-4o", "Llama 3.1", "Qwen Coder"]);
    // Unique, predictable ids for aria-activedescendant.
    optionEls().forEach((li, i) => {
      expect(li.id).toBe("cbModelList-opt-" + i);
    });
  });

  it("falls back to the value as the label when label is missing", () => {
    cb.setOptions([{ value: "bare-id" }]);
    cb.open();
    expect(optionTexts()).toEqual(["bare-id"]);
  });

  it("wires the a11y attributes onto input + list", () => {
    cb.setOptions(MODELS);
    const inp = input();
    expect(inp.getAttribute("role")).toBe("combobox");
    expect(inp.getAttribute("aria-controls")).toBe("cbModelList");
    expect(inp.getAttribute("aria-autocomplete")).toBe("list");
    expect(list().getAttribute("role")).toBe("listbox");
    expect(inp.getAttribute("aria-expanded")).toBe("false");
    cb.open();
    expect(inp.getAttribute("aria-expanded")).toBe("true");
  });
});

describe("combobox — type-to-filter", () => {
  let cb;
  beforeEach(() => { cb = mount(); cb.setOptions(MODELS); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("filters by case-insensitive substring on the LABEL", () => {
    type("llam");
    expect(optionValues()).toEqual(["llama-3.1"]);
  });

  it("filters by case-insensitive substring on the VALUE", () => {
    type("4O"); // uppercase, matches value "gpt-4o"
    expect(optionValues()).toEqual(["gpt-4o"]);
  });

  it("empty query shows ALL options", () => {
    type("zz");
    expect(optionValues()).toEqual([]);
    type("");
    expect(optionValues()).toEqual(["gpt-4o", "llama-3.1", "qwen-coder"]);
  });

  it("typing opens the panel; a no-match query shows the no_match row", () => {
    type("qwen");
    expect(list().hidden).toBe(false);
    expect(optionValues()).toEqual(["qwen-coder"]);
    type("nothing-matches-this");
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0);
    expect(list().textContent).toContain(window.I18N.en["combobox.no_match"]);
  });
});

describe("combobox — selection (click + keyboard)", () => {
  let cb;
  beforeEach(() => { cb = mount(); cb.setOptions(MODELS); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("clicking an option sets the value and closes the panel", () => {
    cb.open();
    const llama = optionEls().find((li) => li.getAttribute("data-value") === "llama-3.1");
    llama.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(cb.getValue()).toBe("llama-3.1");
    expect(list().hidden).toBe(true);
    expect(input().getAttribute("aria-expanded")).toBe("false");
  });

  it("ArrowDown moves the highlight (aria-activedescendant), Enter selects it", () => {
    cb.open();
    key("ArrowDown"); // -> index 0 (GPT-4o)
    expect(input().getAttribute("aria-activedescendant")).toBe("cbModelList-opt-0");
    expect(optionEls()[0].classList.contains("aigate-combo-active")).toBe(true);
    key("ArrowDown"); // -> index 1 (Llama 3.1)
    key("Enter");
    expect(cb.getValue()).toBe("llama-3.1");
    expect(list().hidden).toBe(true);
  });

  it("ArrowUp wraps to the last option", () => {
    cb.open();
    key("ArrowUp"); // from -1 -> last
    expect(input().getAttribute("aria-activedescendant")).toBe("cbModelList-opt-2");
    key("Enter");
    expect(cb.getValue()).toBe("qwen-coder");
  });

  it("Escape closes without changing the value", () => {
    cb.open();
    key("ArrowDown");
    key("Escape");
    expect(list().hidden).toBe(true);
    expect(cb.getValue()).toBe("");
  });
});

describe("combobox — free text is the value", () => {
  let cb;
  beforeEach(() => { cb = mount(); cb.setOptions(MODELS); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("a typed value that matches no option is still the value", () => {
    type("my-local-llama");
    expect(cb.getValue()).toBe("my-local-llama");
    // Enter on an open panel with no highlight ACCEPTS the typed text (closes).
    key("Enter");
    expect(list().hidden).toBe(true);
    expect(cb.getValue()).toBe("my-local-llama");
  });

  it("setValue() puts any string in the input (known OR custom)", () => {
    cb.setValue("undiscovered-model");
    expect(input().value).toBe("undiscovered-model");
    expect(cb.getValue()).toBe("undiscovered-model");
  });
});

describe("combobox — loading state", () => {
  let cb;
  beforeEach(() => { cb = mount(); cb.setOptions(MODELS); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("setLoading(true) shows the loading row + aria-busy + disables input", () => {
    cb.setLoading(true);
    expect(list().textContent).toContain(window.I18N.en["combobox.loading"]);
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0);
    expect(input().getAttribute("aria-busy")).toBe("true");
    expect(input().disabled).toBe(true);
  });

  it("setLoading(false) restores the options + clears aria-busy + re-enables", () => {
    cb.setLoading(true);
    cb.setLoading(false);
    expect(input().getAttribute("aria-busy")).toBe("false");
    expect(input().disabled).toBe(false);
    expect(list().textContent).not.toContain(window.I18N.en["combobox.loading"]);
    // Options come back once the panel is opened.
    cb.open();
    expect(optionValues()).toEqual(["gpt-4o", "llama-3.1", "qwen-coder"]);
  });
});
