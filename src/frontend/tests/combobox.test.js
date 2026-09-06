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

// ---- New capabilities: searchInside + groupBy + groupOrder (B: model dropdown) ----

// Parameterized mount so we can pass the new options.
function mountOpts(opts) {
  document.body.innerHTML =
    '<div class="aigate-combo">' +
      '<input type="text" id="cbModel" />' +
      '<ul id="cbModelList" hidden></ul>' +
    "</div>";
  return window.aigate.createCombobox(
    Object.assign({ inputId: "cbModel", listId: "cbModelList" }, opts)
  );
}
const groupHeaders = () =>
  Array.from(list().querySelectorAll(".aigate-combo-group")).map((h) => h.textContent);
const subHeaders = () =>
  Array.from(list().querySelectorAll(".aigate-combo-subgroup"));
// jsdom lacks CSS.escape; match attributes directly (group/sub names are plain).
const headerByGroup = (g) =>
  Array.from(list().querySelectorAll(".aigate-combo-group"))
    .find((h) => h.getAttribute("data-group") === g);
const subHeader = (g, s) =>
  Array.from(list().querySelectorAll(".aigate-combo-subgroup"))
    .find((h) => h.getAttribute("data-group") === g && h.getAttribute("data-sub") === s);
const searchInputEl = () => document.getElementById("cbModelList-search");

describe("combobox — groupBy:'prefix'", () => {
  let cb;
  beforeEach(() => { cb = mountOpts({ searchInside: true, groupBy: "prefix" }); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("groups deepseek-v1/deepseekv2 under Deepseek and gpt-4o under Gpt", () => {
    cb.setOptions([
      { value: "deepseek-v1", label: "deepseek-v1" },
      { value: "deepseekv2", label: "deepseekv2" },
      { value: "gpt-4o", label: "gpt-4o" }
    ]);
    cb.open();
    expect(groupHeaders()).toContain("Deepseek");
    expect(groupHeaders()).toContain("Gpt");
    // Groups start COLLAPSED: clicking the Deepseek header expands it so its
    // children render, in order.
    let deepHeader = list().querySelectorAll(".aigate-combo-group")[0];
    expect(deepHeader.classList.contains("aigate-combo-group-collapsed")).toBe(true);
    deepHeader.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    deepHeader = list().querySelectorAll(".aigate-combo-group")[0]; // re-query after re-render
    expect(deepHeader.classList.contains("aigate-combo-group-collapsed")).toBe(false);
    let next = deepHeader.nextElementSibling;
    const vals = [];
    while (next && next.getAttribute("role") === "option") {
      vals.push(next.getAttribute("data-value"));
      next = next.nextElementSibling;
    }
    expect(vals).toEqual(["deepseek-v1", "deepseekv2"]);
  });
});

describe("combobox — groupBy:'group' + groupOrder", () => {
  let cb;
  beforeEach(() => {
    cb = mountOpts({ searchInside: true, groupBy: "group", groupOrder: ["Kombo/Combos"] });
  });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("honors the group field and pins Kombo/Combos first", () => {
    cb.setOptions([
      { value: "a", label: "a", group: "OpenAI" },
      { value: "b", label: "b", group: "Kombo/Combos" },
      { value: "c", label: "c", group: "Deepseek" }
    ]);
    cb.open();
    expect(groupHeaders()).toEqual(["Kombo/Combos", "Deepseek", "OpenAI"]);
  });
});

describe("combobox — searchInside in-panel search", () => {
  let cb;
  beforeEach(() => { cb = mountOpts({ searchInside: true, groupBy: "none" }); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("renders a search <li> first and filters options as you type (mirrors top input)", () => {
    cb.setOptions([
      { value: "deepseek-v1", label: "Deepseek v1" },
      { value: "gpt-4o", label: "GPT 4o" }
    ]);
    cb.open();
    const srow = list().querySelector(".aigate-combo-searchrow");
    expect(srow).toBeTruthy();
    expect(srow.getAttribute("role")).toBe("presentation");
    expect(list().firstElementChild).toBe(srow);
    const sinput = searchInputEl();
    expect(sinput).toBeTruthy();

    sinput.value = "deep";
    sinput.dispatchEvent(new Event("input", { bubbles: true }));
    expect(optionValues()).toEqual(["deepseek-v1"]);
    // top input (value holder) mirrors the search text
    expect(input().value).toBe("deep");
  });

  it("focuses the search input on open and clears it so the full list shows", () => {
    cb.setOptions([{ value: "deepseek-v1", label: "Deepseek v1" }]);
    cb.open();
    expect(document.activeElement).toBe(searchInputEl());
    expect(searchInputEl().value).toBe("");
  });
});

describe("combobox — no-match free-text (ADR-011, searchInside)", () => {
  let cb;
  beforeEach(() => { cb = mountOpts({ searchInside: true, groupBy: "none" }); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("shows a 'use custom' option on no-match and selecting it returns the raw typed value", () => {
    cb.setOptions([{ value: "deepseek-v1", label: "Deepseek v1" }]);
    cb.open();
    const sinput = searchInputEl();
    sinput.value = "zzz";
    sinput.dispatchEvent(new Event("input", { bubbles: true }));
    const custom = list().querySelector('li[role="option"][data-value="zzz"]');
    expect(custom).toBeTruthy();
    expect(custom.textContent).toContain("zzz"); // combobox.use_custom
    expect(list().querySelector(".aigate-combo-msg")).toBeTruthy(); // no_match kept

    custom.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(cb.getValue()).toBe("zzz");
  });

  it("accepts typed free text via Enter with no highlight", () => {
    cb.setOptions([{ value: "deepseek-v1", label: "Deepseek v1" }]);
    cb.open();
    const sinput = searchInputEl();
    sinput.value = "my-custom-model";
    sinput.dispatchEvent(new Event("input", { bubbles: true }));
    sinput.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(cb.getValue()).toBe("my-custom-model");
  });
});

// ---- Collapsible groups (FIX 2): collapsed by default, header toggles ----
describe("combobox — collapsible groups (collapsed by default)", () => {
  let cb;
  beforeEach(() => { cb = mountOpts({ searchInside: true, groupBy: "prefix" }); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("groups are collapsed by default: headers present, child options NOT in DOM", () => {
    cb.setOptions([
      { value: "deepseek-v1", label: "deepseek-v1" },
      { value: "gpt-4o", label: "gpt-4o" }
    ]);
    cb.open();
    expect(list().querySelectorAll(".aigate-combo-group").length).toBe(2);
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0);
    const h = list().querySelector(".aigate-combo-group");
    expect(h.getAttribute("role")).toBe("button");
    expect(h.getAttribute("aria-expanded")).toBe("false");
    expect(h.tabIndex).toBe(0);
    expect(h.classList.contains("aigate-combo-group-collapsed")).toBe(true);
  });

  it("clicking a header expands (children appear); clicking again collapses", () => {
    cb.setOptions([
      { value: "deepseek-v1", label: "deepseek-v1" },
      { value: "gpt-4o", label: "gpt-4o" }
    ]);
    cb.open();
    let h = list().querySelectorAll(".aigate-combo-group")[0];
    h.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    h = list().querySelectorAll(".aigate-combo-group")[0]; // re-query after re-render
    expect(h.getAttribute("aria-expanded")).toBe("true");
    expect(h.classList.contains("aigate-combo-group-collapsed")).toBe(false);
    expect(list().querySelectorAll('li[role="option"]').length).toBe(1); // deepseek-v1
    // collapse again
    h.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    h = list().querySelectorAll(".aigate-combo-group")[0];
    expect(h.getAttribute("aria-expanded")).toBe("false");
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0);
  });

  it("typing a query with all groups collapsed still shows matching children", () => {
    cb.setOptions([
      { value: "deepseek-v1", label: "deepseek-v1" },
      { value: "gpt-4o", label: "gpt-4o" }
    ]);
    cb.open();
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0); // collapsed
    const sinput = searchInputEl();
    sinput.value = "gpt";
    sinput.dispatchEvent(new Event("input", { bubbles: true }));
    const gptHeader = Array.from(list().querySelectorAll(".aigate-combo-group"))
      .find((x) => x.getAttribute("data-group") === "Gpt");
    expect(gptHeader.getAttribute("aria-expanded")).toBe("true");
    const gptOpt = list().querySelector('li[role="option"][data-value="gpt-4o"]');
    expect(gptOpt).toBeTruthy();
  });

  it("keyboard Enter/Space on a focused header toggles collapse", () => {
    cb.setOptions([
      { value: "deepseek-v1", label: "deepseek-v1" },
      { value: "gpt-4o", label: "gpt-4o" }
    ]);
    cb.open();
    let h = list().querySelectorAll(".aigate-combo-group")[0];
    h.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(list().querySelectorAll('li[role="option"]').length).toBe(1);
    h = list().querySelectorAll(".aigate-combo-group")[0]; // re-query after re-render
    h.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0);
  });

  it("toggle state persists across setOptions refreshes (only unseen groups added)", () => {
    cb.setOptions([{ value: "deepseek-v1", label: "deepseek-v1" }]);
    cb.open();
    let h = list().querySelector(".aigate-combo-group");
    h.dispatchEvent(new MouseEvent("click", { bubbles: true })); // expand Deepseek
    // Refresh with same + a new group; Deepseek must stay expanded, Gpt collapsed.
    cb.setOptions([
      { value: "deepseek-v1", label: "deepseek-v1" },
      { value: "gpt-4o", label: "gpt-4o" }
    ]);
    const heads = list().querySelectorAll(".aigate-combo-group");
    const deep = Array.from(heads).find((x) => x.getAttribute("data-group") === "Deepseek");
    const gpt = Array.from(heads).find((x) => x.getAttribute("data-group") === "Gpt");
    expect(deep.classList.contains("aigate-combo-group-collapsed")).toBe(false);
    expect(gpt.classList.contains("aigate-combo-group-collapsed")).toBe(true);
  });
});

// ---- Fixed positioning (FIX 3): no modal clipping, capped height ----
describe("combobox — fixed positioning (no modal clipping)", () => {
  let cb;
  beforeEach(() => { cb = mountOpts({ searchInside: false, groupBy: "none" }); });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; window.innerHeight = 768; });

  function stubRect(top, bottom, left, right, width, height) {
    const inp = input();
    inp.getBoundingClientRect = () => ({ top, bottom, left, right, width, height, x: left, y: top });
  }

  it("uses position:fixed and opens ABOVE when the field is near the bottom", () => {
    window.innerHeight = 600;
    stubRect(500, 540, 10, 210, 200, 40);
    cb.setOptions([{ value: "a", label: "a" }]);
    cb.open();
    const ul = list();
    expect(ul.style.position).toBe("fixed");
    expect(ul.classList.contains("aigate-combo-up")).toBe(true);
    expect(ul.style.bottom).toBe((600 - 500 + 4) + "px");
    expect(ul.style.top).toBe("auto");
    const maxH = parseInt(ul.style.maxHeight, 10);
    expect(maxH).toBeLessThanOrEqual(320);
    expect(maxH).toBeGreaterThanOrEqual(80);
  });

  it("opens BELOW when there is room, capping height to available space", () => {
    window.innerHeight = 600;
    stubRect(100, 140, 10, 210, 200, 40);
    cb.setOptions([{ value: "a", label: "a" }]);
    cb.open();
    const ul = list();
    expect(ul.style.position).toBe("fixed");
    expect(ul.classList.contains("aigate-combo-up")).toBe(false);
    expect(ul.style.top).toBe((140 + 4) + "px");
    expect(ul.style.bottom).toBe("auto");
    const maxH = parseInt(ul.style.maxHeight, 10);
    expect(maxH).toBeLessThanOrEqual(600 - 140 - 8); // available space below
    expect(maxH).toBeLessThanOrEqual(320);           // hard cap
  });

  it("repositions on scroll/resize while open, detaches on close", () => {
    window.innerHeight = 600;
    stubRect(100, 140, 10, 210, 200, 40);
    cb.setOptions([{ value: "a", label: "a" }]);
    cb.open();
    expect(list().style.position).toBe("fixed");
    expect(() => window.dispatchEvent(new Event("scroll"))).not.toThrow();
    expect(() => window.dispatchEvent(new Event("resize"))).not.toThrow();
    cb.close();
    expect(() => window.dispatchEvent(new Event("scroll"))).not.toThrow();
  });
});

// ---- Two-level grouping: main group = provider, sub = model-name prefix ----
// Only the CLI Tools picker uses subGroupBy. Kombo/Combos stays flat (subGroup:
// false); non-combo models get a prefix sub-group. Both levels collapsible,
// default collapsed, auto-expand while a search query is active.
describe("combobox — two-level grouping (group + subGroupBy:'prefix')", () => {
  let cb;
  const FIXTURE = [
    { value: "provider:A:deepseek-v1", label: "deepseek-v1", group: "A" },
    { value: "provider:A:deepseekv2", label: "deepseekv2", group: "A" },
    { value: "provider:A:gpt-4o", label: "gpt-4o", group: "A" },
    { value: "combo:mycombo", label: "mycombo", group: "Kombo/Combos", subGroup: false }
  ];

  beforeEach(() => {
    cb = mountOpts({
      searchInside: true,
      groupBy: "group",
      subGroupBy: "prefix",
      groupOrder: ["Kombo/Combos"]
    });
  });
  afterEach(() => { cb.destroy(); document.body.innerHTML = ""; });

  it("(3) default-collapsed: only headers visible, no role=option children", () => {
    cb.setOptions(FIXTURE);
    cb.open();
    expect(list().querySelectorAll(".aigate-combo-group").length).toBe(2); // A, Kombo/Combos
    expect(subHeaders().length).toBe(0); // subs hidden until parent expands
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0);
    // Both main headers start collapsed.
    expect(headerByGroup("A").getAttribute("aria-expanded")).toBe("false");
    expect(headerByGroup("Kombo/Combos").getAttribute("aria-expanded")).toBe("false");
  });

  it("(1) Kombo/Combos renders flat: combo item shown, no sub-header", () => {
    cb.setOptions(FIXTURE);
    cb.open();
    // Expand the Kombo/Combos main header.
    headerByGroup("Kombo/Combos").dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const kHeader = headerByGroup("Kombo/Combos");
    expect(kHeader.getAttribute("aria-expanded")).toBe("true");
    // Within Kombo/Combos there must be NO sub-header and the combo item present.
    expect(kHeader.nextElementSibling.classList.contains("aigate-combo-subgroup")).toBe(false);
    const comboOpt = list().querySelector('li[role="option"][data-value="combo:mycombo"]');
    expect(comboOpt).toBeTruthy();
    expect(comboOpt.classList.contains("aigate-combo-opt-sub")).toBe(false); // flat
    expect(comboOpt.textContent).toBe("mycombo");
  });

  it("(2)+(4) provider A splits into Deepseek + Gpt sub-headers; expand sub shows items", () => {
    cb.setOptions(FIXTURE);
    cb.open();
    // Expand provider A: two collapsed sub-headers appear.
    headerByGroup("A").dispatchEvent(new MouseEvent("click", { bubbles: true }));
    let aHeader = headerByGroup("A");
    expect(aHeader.getAttribute("aria-expanded")).toBe("true");
    const subs = subHeaders().filter((s) => s.getAttribute("data-group") === "A");
    const names = subs.map((s) => s.textContent).sort();
    expect(names).toEqual(["Deepseek", "Gpt"]);
    // Both sub-headers start collapsed (no items yet).
    subs.forEach((s) => expect(s.getAttribute("aria-expanded")).toBe("false"));

    // Expand the Deepseek sub: its two items show.
    const deepSub = subHeader("A", "Deepseek");
    deepSub.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const deepItems = Array.from(list().querySelectorAll('li[role="option"]'))
      .filter((li) => li.getAttribute("data-value").indexOf("deepseek") !== -1)
      .map((li) => li.getAttribute("data-value"));
    expect(deepItems).toEqual(["provider:A:deepseek-v1", "provider:A:deepseekv2"]);
    // Items under a sub-group get the deeper-indent class.
    expect(list()
      .querySelector('li[role="option"][data-value="provider:A:deepseek-v1"]')
      .classList.contains("aigate-combo-opt-sub")).toBe(true);

    // Gpt sub still collapsed -> its item NOT in DOM.
    expect(list().querySelector('li[role="option"][data-value="provider:A:gpt-4o"]')).toBeFalsy();
    // Expand Gpt sub now.
    subHeader("A", "Gpt").dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(list().querySelector('li[role="option"][data-value="provider:A:gpt-4o"]')).toBeTruthy();
  });

  it("(4) keyboard Enter/Space toggles a sub-header collapse", () => {
    cb.setOptions(FIXTURE);
    cb.open();
    headerByGroup("A").dispatchEvent(new MouseEvent("click", { bubbles: true }));
    const deepSub = subHeader("A", "Deepseek");
    deepSub.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    expect(list().querySelectorAll('li[role="option"]').length).toBe(2); // deepseek items
    const deepSub2 = subHeader("A", "Deepseek");
    deepSub2.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0);
  });

  it("(5) typing a query auto-expands both levels; all matches appear", () => {
    cb.setOptions(FIXTURE);
    cb.open();
    // Both levels collapsed initially.
    expect(list().querySelectorAll('li[role="option"]').length).toBe(0);
    const sinput = searchInputEl();
    sinput.value = "provider:A";
    sinput.dispatchEvent(new Event("input", { bubbles: true }));
    // All three provider models match and are now visible (auto-expanded).
    expect(optionValues().sort()).toEqual(
      ["provider:A:deepseek-v1", "provider:A:deepseekv2", "provider:A:gpt-4o"].sort()
    );
    // Headers + sub-headers are all expanded while searching.
    expect(headerByGroup("A").getAttribute("aria-expanded")).toBe("true");
    expect(subHeader("A", "Deepseek").getAttribute("aria-expanded")).toBe("true");
    expect(subHeader("A", "Gpt").getAttribute("aria-expanded")).toBe("true");
  });

  it("sub-group collapse state persists across setOptions refreshes", () => {
    cb.setOptions(FIXTURE);
    cb.open();
    headerByGroup("A").dispatchEvent(new MouseEvent("click", { bubbles: true }));
    // Expand Deepseek sub, leave Gpt collapsed.
    subHeader("A", "Deepseek").dispatchEvent(new MouseEvent("click", { bubbles: true }));
    // Refresh with the same options.
    cb.setOptions(FIXTURE);
    cb.open();
    expect(headerByGroup("A").getAttribute("aria-expanded")).toBe("true");
    expect(subHeader("A", "Deepseek").getAttribute("aria-expanded")).toBe("true");
    expect(subHeader("A", "Gpt").getAttribute("aria-expanded")).toBe("false");
  });
});
