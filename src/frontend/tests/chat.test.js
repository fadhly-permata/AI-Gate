// Chat Playground (B8.B6.2 core + B6.3 polish / PRD §2.9).
// The chat logic lives inside app.js (window.aigate.chat); this file mounts the
// shipped markup, stubs fetch, and exercises the pure helpers + the wiring.
import { describe, it, expect, vi, afterEach } from "vitest";
import { indexBodyHtml } from "./helpers/dom.js";

import "../static/i18n.js";
import "../static/combobox.js";
import "../static/app.js";

const chat = window.aigate.chat;
const T = chat._test;

function mount() {
  document.body.innerHTML = indexBodyHtml();
  window.applyLocale("en");
  window.aigate.wireChatUi();
}

function stubApi(map) {
  const calls = [];
  vi.stubGlobal("fetch", vi.fn((url, opts) => {
    const method = (opts && opts.method) || "GET";
    const u = String(url);
    calls.push({ url: u, method, body: opts && opts.body });
    const route = map[u] || map["*"];
    return Promise.resolve(route ? route(u, method, opts) : { ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve({ data: [] }) });
  }));
  return calls;
}
const jsonOk = (payload) => ({ ok: true, headers: { get: () => "application/json" }, json: () => Promise.resolve(payload) });

afterEach(() => { vi.unstubAllGlobals(); });

/* ============================================================
 * Pure helpers — describeTarget / formatTokens / parseSseLine
 * ============================================================ */
describe("describeTarget — gateway model ref -> label", () => {
  it("combo ref", () => {
    expect(T.describeTarget("combo:my-team")).toEqual({ kind: "combo", name: "my-team", model: "", label: "Combo: my-team" });
  });
  it("provider 2-seg (no model) resolves to provider name", () => {
    const r = T.describeTarget("provider:openai");
    expect(r.kind).toBe("provider");
    expect(r.name).toBe("openai");
    expect(r.model).toBe("");
  });
  it("provider 3-seg extracts model id", () => {
    const r = T.describeTarget("provider:openai:gpt-4o");
    expect(r.kind).toBe("provider");
    expect(r.name).toBe("openai");
    expect(r.model).toBe("gpt-4o");
  });
  it("empty ref -> none", () => {
    expect(T.describeTarget(null).kind).toBe("none");
    expect(T.describeTarget("").kind).toBe("none");
  });
  it("bare id still parses (resolver accepts it)", () => {
    const r = T.describeTarget("gpt-4o-mini");
    expect(r.kind).toBe("bare");
    expect(r.label).toBe("gpt-4o-mini");
  });
});

describe("formatTokens — null usage shows em dash, never 0", () => {
  it("null/undefined/NaN -> —", () => {
    expect(T.formatTokens(null)).toBe("—");
    expect(T.formatTokens(undefined)).toBe("—");
    expect(T.formatTokens(NaN)).toBe("—");
  });
  it("numbers render verbatim (incl. 0)", () => {
    expect(T.formatTokens(0)).toBe("0");
    expect(T.formatTokens(123)).toBe("123");
    expect(T.formatTokens(42.5)).toBe("42.5");
  });
});

describe("parseSseLine — one SSE line -> event", () => {
  it("delta content fragment", () => {
    const ev = T.parseSseLine('data: {"choices":[{"delta":{"content":"Hello"}}]}');
    expect(ev).toEqual({ type: "delta", content: "Hello" });
  });
  it("delta with no content is still a delta (empty)", () => {
    const ev = T.parseSseLine('data: {"choices":[{"delta":{}}]}');
    expect(ev.type).toBe("delta");
    expect(ev.content).toBe("");
  });
  it("[DONE] sentinel", () => {
    expect(T.parseSseLine("data: [DONE]").type).toBe("done");
  });
  it("blank / non-data fields are ignored", () => {
    expect(T.parseSseLine("").type).toBe("ignore");
    expect(T.parseSseLine("event: ping").type).toBe("ignore");
    expect(T.parseSseLine("data:").type).toBe("ignore");
  });
  it("upstream error frame", () => {
    const ev = T.parseSseLine('data: {"error":{"message":"bad model","code":"no_model"}}');
    expect(ev.type).toBe("error");
  });
  it("unparseable data line is an error (never crashes)", () => {
    expect(T.parseSseLine("data: {not json").type).toBe("error");
  });
});

/* ============================================================
 * Rendering — messages + session list are pure DOM builders
 * ============================================================ */
describe("renderMessages — bubbles + token display", () => {
  it("empty -> friendly empty state, no bubbles", () => {
    mount();
    T.renderMessages([]);
    const thread = document.getElementById("chatThread");
    expect(thread.querySelectorAll(".chat-msg").length).toBe(0);
    expect(thread.querySelector(".chat-empty")).not.toBeNull();
  });
  it("renders user + assistant with whitespace preserved and null tokens as —", () => {
    mount();
    T.renderMessages([
      { role: "user", content: "Hi\n there", tokens_in: null, tokens_out: null },
      { role: "assistant", content: "Hello world", tokens_in: null, tokens_out: 17 }
    ]);
    const thread = document.getElementById("chatThread");
    const msgs = thread.querySelectorAll(".chat-msg");
    expect(msgs.length).toBe(2);
    expect(msgs[0].classList.contains("chat-msg-user")).toBe(true);
    expect(msgs[1].classList.contains("chat-msg-assistant")).toBe(true);
    // whitespace preserved
    expect(msgs[0].querySelector(".chat-msg-text").textContent).toBe("Hi\n there");
    // assistant token usage: null -> —
    expect(msgs[1].querySelector(".chat-msg-tokens").textContent).toContain("—");
    expect(msgs[1].querySelector(".chat-msg-tokens").textContent).toContain("17");
  });
});

describe("renderSessionList — sidebar items", () => {
  it("empty list shows the no-sessions note", () => {
    mount();
    T.renderSessionList([]);
    expect(document.querySelectorAll("#chatSessionList .chat-session").length).toBe(0);
    expect(document.querySelector(".chat-session-empty")).not.toBeNull();
  });
  it("one item per session, labelled; clicking opens it (GET /{id})", async () => {
    const calls = stubApi({
      // click -> internal openSession fetches the full session
      "/api/chat/sessions/7": () => jsonOk({ id: 7, model: "provider:openai:gpt-4o", title: "Test chat", messages: [] })
    });
    mount();
    T.renderSessionList([
      { id: 7, title: "Test chat", model: "provider:openai:gpt-4o" }
    ]);
    const items = document.querySelectorAll("#chatSessionList .chat-session");
    expect(items.length).toBe(1);
    expect(items[0].querySelector(".chat-session-title").textContent).toBe("Test chat");
    expect(items[0].querySelector(".chat-session-target").textContent).toContain("Provider");
    items[0].click();
    await new Promise((r) => setTimeout(r, 10));
    const get = calls.find((c) => c.method === "GET" && c.url === "/api/chat/sessions/7");
    expect(get, "clicking a session GETs it").toBeTruthy();
  });
});

/* ============================================================
 * SSE read loop — split frames, accumulate deltas
 * ============================================================ */
describe("readSseStream — frame splitting + delta accumulation", () => {
  function fakeReader(chunks) {
    let i = 0;
    return {
      read() {
        if (i >= chunks.length) return Promise.resolve({ done: true });
        const v = chunks[i++];
        return Promise.resolve({ value: new TextEncoder().encode(v), done: false });
      },
      cancel() { return Promise.resolve(); }
    };
  }
  it("assembles streamed deltas across multiple frames", async () => {
    const res = { body: { getReader: () => fakeReader([
      'data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n',
      'data: {"choices":[{"delta":{"content":"lo"}}]}\n\n',
      "data: [DONE]\n\n"
    ]) } };
    const parts = [];
    await T.readSseStream(res, (c) => parts.push(c), null);
    expect(parts.join("")).toBe("Hello");
  });
  it("buffered partial frames are reassembled across chunk boundaries", async () => {
    // one chunk splits a frame in the middle of a data line
    const res = { body: { getReader: () => fakeReader([
      'data: {"choices":[{"delta":{"content":"par',
      't1"}}]}\n\ndata: {"choices":[{"delta":{"content":"part2"}}]}\n\n'
    ]) } };
    const parts = [];
    await T.readSseStream(res, (c) => parts.push(c), null);
    expect(parts.join("")).toBe("part1part2");
  });
});

/* ============================================================
 * Wiring — new-session flow ( Gemini-style: NO modal, blank draft +
 * inline model switcher -> first message creates the session ) with stubbed fetch
 * ============================================================ */
describe("new chat flow — blank draft + inline model (no modal)", () => {
  it("New chat button starts a blank draft; inline switcher ready; no modal", async () => {
    const calls = stubApi({
      "/v1/models": () => jsonOk({ data: [{ id: "provider:openai:gpt-4o", owned_by: "openai" }] })
    });
    mount();
    expect(document.getElementById("chatNewModal")).toBeNull();   // the modal is gone
    document.getElementById("chatNewBtn").click();                // -> draft, no modal
    await new Promise((r) => setTimeout(r, 10));
    // No modal element exists in the DOM and nothing threw.
    expect(document.getElementById("chatNewModal")).toBeNull();
    // Composer is ready-to-type: inline switcher present + the textarea available.
    expect(document.getElementById("chatModelSwitch")).not.toBeNull();
    expect(document.getElementById("chatInput")).not.toBeNull();
    // The model list was fetched so the inline picker is populated.
    const models = calls.find((c) => c.url === "/v1/models" && c.method === "GET");
    expect(models, "model list loaded for the inline switcher").toBeTruthy();
    // New chat alone creates NO session (only a GET for the model list).
    expect(calls.find((c) => c.method === "POST" && c.url === "/api/chat/sessions")).toBeUndefined();
  });

  it("selecting an inline model then sending creates the session and streams a reply", async () => {
    const calls = stubApi({
      "/v1/models": () => jsonOk({ data: [{ id: "provider:openai:gpt-4o", owned_by: "openai" }] }),
      "/api/chat/sessions": (u, m) => {
        if (m === "POST") return jsonOk({ id: 11, title: "New chat", model: "provider:openai:gpt-4o" });
        return jsonOk({ object: "list", data: [] });
      },
      "/api/chat/sessions/11/complete": () => jsonOk({ choices: [{ message: { content: "Echo: halo" } }] }),
      "/api/chat/sessions/11": () => jsonOk({ id: 11, model: "provider:openai:gpt-4o", title: "halo",
        system_prompt: "", temperature: null, messages: [
          { role: "user", content: "halo" },
          { role: "assistant", content: "Echo: halo", tokens_in: 3, tokens_out: 5 }
        ] })
    });
    mount();
    document.getElementById("chatNewBtn").click();   // start blank draft (no modal)
    await new Promise((r) => setTimeout(r, 10));
    expect(document.getElementById("chatNewModal")).toBeNull();

    // Pick a model inline in the composer switcher (draft: stored as pending, no PUT).
    T.commitModelSwitch("provider:openai:gpt-4o");
    expect(T.chatState.currentModel).toBe("provider:openai:gpt-4o");
    expect(T.chatState.currentId).toBeNull();   // no session until the first message

    // Send the first message.
    document.getElementById("chatInput").value = "halo";
    document.getElementById("chatSendBtn").click();
    await new Promise((r) => setTimeout(r, 40));

    const post = calls.find((c) => c.method === "POST" && c.url === "/api/chat/sessions");
    expect(post, "POST /api/chat/sessions was called").toBeTruthy();
    expect(JSON.parse(post.body).model).toBe("provider:openai:gpt-4o");
    expect(JSON.parse(post.body).title).toBeUndefined();   // auto-titled, not user-set
    // Auto-title PUT fired from the first message (no manual title prompt).
    expect(calls.find((c) => c.method === "PUT" && c.url === "/api/chat/sessions/11")).toBeTruthy();

    // No modal involved at any point.
    expect(document.getElementById("chatNewModal")).toBeNull();
    // The reply streamed into the thread.
    const thread = document.getElementById("chatThread");
    expect(thread.querySelector(".chat-msg-assistant")).not.toBeNull();
    expect(thread.querySelector(".chat-msg-assistant").textContent).toContain("Echo: halo");
    expect(document.getElementById("chatTarget").textContent).toContain("gpt-4o");
    expect(T.chatState.currentId).toBe(11);
  });
});

/* ============================================================
 * Wiring — delete confirm
 * ============================================================ */
describe("delete flow", () => {
  it("DELETE fires only after confirm; cancels do nothing", async () => {
    const calls = stubApi({
      "/api/chat/sessions": () => jsonOk({ object: "list", data: [] }),
      "/api/chat/sessions/3": (u, m) => (m === "DELETE"
        ? jsonOk({ object: "chat.session.deleted", id: 3, deleted: true })
        : jsonOk({ id: 3, model: "combo:team", title: "x" }))
    });
    mount();
    await window.aigate.chat.onShow();          // loads the (empty) session list
    await window.aigate.chat.openSession(3);    // sets currentId = 3 + renders
    document.getElementById("chatDeleteBtn").click();
    expect(document.getElementById("chatDeleteModal").hidden).toBe(false);
    // cancel path: no DELETE issued, modal closes
    document.getElementById("chatDeleteCancel").click();
    expect(document.getElementById("chatDeleteModal").hidden).toBe(true);
    expect(calls.find((c) => c.method === "DELETE")).toBeUndefined();
    // confirm path: DELETE issued
    document.getElementById("chatDeleteBtn").click();
    document.getElementById("chatDeleteConfirm").click();
    await new Promise((r) => setTimeout(r, 10));
    expect(calls.find((c) => c.method === "DELETE" && c.url === "/api/chat/sessions/3")).toBeTruthy();
  });
});

/* ============================================================
 * BUG-260916-1 p.2 — system prompt + temperature moved to a dialog
 * ============================================================ */
describe("settings dialog (BUG-260916-1 p.2)", () => {
  it("no always-visible settings block remains; the gear opens the dialog", async () => {
    stubApi({
      "/api/chat/sessions/5": () => jsonOk({ id: 5, model: "provider:openai:gpt-4o", title: "T",
        system_prompt: "Be terse", temperature: 0.3, messages: [] })
    });
    mount();
    await window.aigate.chat.openSession(5);
    expect(document.getElementById("chatSettings")).toBeNull();       // inline block gone
    document.getElementById("chatSettingsBtn").click();
    expect(document.getElementById("chatSettingsModal").hidden).toBe(false);
    // the dialog carries the session values
    expect(document.getElementById("chatSystemPrompt").value).toBe("Be terse");
    expect(document.getElementById("chatTemperature").value).toBe("0.3");
  });

  it("gear with no open session warns instead of opening", async () => {
    stubApi({});
    mount();
    window.aigate.chat._test.chatState.currentId = null;
    document.getElementById("chatSettingsBtn").click();
    expect(document.getElementById("chatSettingsModal").hidden).toBe(true);
    expect(document.getElementById("chatMsg").textContent).toBe("Choose a conversation or start a new one.");
  });

  it("Save PUTs system_prompt + temperature", async () => {
    const calls = stubApi({
      "/api/chat/sessions/5": () => jsonOk({ id: 5, model: "provider:openai:gpt-4o", title: "T",
        system_prompt: "", temperature: null, messages: [] })
    });
    mount();
    await window.aigate.chat.openSession(5);
    document.getElementById("chatSettingsBtn").click();
    document.getElementById("chatSystemPrompt").value = "Only Spanish";
    document.getElementById("chatTemperature").value = "1.2";
    document.getElementById("chatSettingsSave").click();
    await new Promise((r) => setTimeout(r, 10));
    const put = calls.find((c) => c.method === "PUT" && c.url === "/api/chat/sessions/5");
    expect(put, "PUT /api/chat/sessions/5 was called").toBeTruthy();
    const body = JSON.parse(put.body);
    expect(body.system_prompt).toBe("Only Spanish");
    expect(body.temperature).toBe(1.2);
    expect(document.getElementById("chatSettingsMsg").textContent).toBe("Saved.");
  });

  it("Escape dismisses the dialog (keyboard-accessible)", async () => {
    stubApi({
      "/api/chat/sessions/5": () => jsonOk({ id: 5, model: "combo:x", title: "T", messages: [] })
    });
    mount();
    await window.aigate.chat.openSession(5);
    document.getElementById("chatSettingsBtn").click();
    expect(document.getElementById("chatSettingsModal").hidden).toBe(false);
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    expect(document.getElementById("chatSettingsModal").hidden).toBe(true);
  });
});

/* ============================================================
 * BUG-260916-1 p.3 — switch the model of the CURRENT session in place
 * ============================================================ */
describe("in-chat model switcher (BUG-260916-1 p.3)", () => {
  function session5Map() {
    return {
      "/api/chat/sessions/5": (u, m) => (m === "PUT"
        ? jsonOk({ id: 5, model: "combo:team", title: "T", messages: [] })
        : jsonOk({ id: 5, model: "provider:openai:gpt-4o", title: "T", messages: [] })),
      "/api/chat/sessions": () => jsonOk({ object: "list", data: [] })
    };
  }

  it("commitModelSwitch PUTs {model} and updates chatState + #chatTarget", async () => {
    const calls = stubApi(session5Map());
    mount();
    await window.aigate.chat.openSession(5);
    expect(document.getElementById("chatTarget").textContent).toContain("gpt-4o");
    T.commitModelSwitch("combo:team");
    await new Promise((r) => setTimeout(r, 10));
    const put = calls.find((c) => c.method === "PUT" && c.url === "/api/chat/sessions/5");
    expect(put, "PUT persists the chosen ref").toBeTruthy();
    expect(JSON.parse(put.body)).toEqual({ model: "combo:team" });
    expect(T.chatState.currentModel).toBe("combo:team");
    expect(document.getElementById("chatTarget").textContent).toContain("team");
  });

  it("choosing the current model is a no-op (no PUT)", async () => {
    const calls = stubApi(session5Map());
    mount();
    await window.aigate.chat.openSession(5);
    T.commitModelSwitch("provider:openai:gpt-4o");
    await new Promise((r) => setTimeout(r, 10));
    expect(calls.find((c) => c.method === "PUT")).toBeUndefined();
  });

  it("clicking an option in the switcher listbox commits (delegated wiring)", async () => {
    const calls = stubApi(session5Map());
    mount();
    await window.aigate.chat.openSession(5);
    const ul = document.getElementById("chatModelSwitchList");
    ul.hidden = false;
    const li = document.createElement("li");
    li.setAttribute("role", "option");
    li.setAttribute("data-value", "combo:team");
    li.textContent = "team";
    ul.appendChild(li);
    li.click();
    await new Promise((r) => setTimeout(r, 10));
    const put = calls.find((c) => c.method === "PUT" && c.url === "/api/chat/sessions/5");
    expect(put, "option click PUTs the new model").toBeTruthy();
    expect(JSON.parse(put.body).model).toBe("combo:team");
  });
});

/* ============================================================
 * BUG-260916-1 p.4 — auto title from the first user message
 * ============================================================ */
describe("auto title (BUG-260916-1 p.4)", () => {
  it("deriveAutoTitle collapses whitespace and caps at 40 chars", () => {
    expect(T.deriveAutoTitle("  Halo   dunia\napa\t kabar  ")).toBe("Halo dunia apa kabar");
    const long = "Hello world, this is the first user message in the session";
    expect(T.deriveAutoTitle(long)).toBe("Hello world, this is the first user mess");
    expect(T.deriveAutoTitle(long).length).toBeLessThanOrEqual(40);
    expect(T.deriveAutoTitle("   ")).toBe("");
    expect(T.deriveAutoTitle(null)).toBe("");
  });

  it("first derivation PUTs the title once, then never overwrites", async () => {
    const calls = stubApi({
      "/api/chat/sessions/9": (u, m) => (m === "PUT"
        ? jsonOk({ id: 9, model: "combo:team", title: "Buatkan ringkasan laporan penjualan", messages: [] })
        : jsonOk({ id: 9, model: "combo:team", title: "", messages: [] })),
      "/api/chat/sessions": () => jsonOk({ object: "list", data: [] })
    });
    mount();
    await window.aigate.chat.openSession(9);
    expect(T.chatState.titleAuto).toBe(true);
    const msg = "Buatkan ringkasan laporan penjualan bulan ini untuk tim manajemen";
    expect(T.autoTitleIfNeeded(msg), "first send derives").toBe(true);
    await new Promise((r) => setTimeout(r, 10));
    const put = calls.find((c) => c.method === "PUT" && c.url === "/api/chat/sessions/9");
    expect(put, "PUT persists the derived title").toBeTruthy();
    expect(JSON.parse(put.body).title).toBe("Buatkan ringkasan laporan penjualan bula");
    expect(T.chatState.titleAuto).toBe(false);
    // a second derivation attempt is refused (flag already cleared)
    const before = calls.length;
    expect(T.autoTitleIfNeeded("pesan kedua sama sekali berbeda")).toBe(false);
    expect(calls.length).toBe(before);
  });

  it("manual rename wins: titleAuto off, no auto-overwrite afterwards", async () => {
    const calls = stubApi({
      "/api/chat/sessions/9": (u, m) => (m === "PUT"
        ? jsonOk({ id: 9, model: "combo:team", title: "Rencana Q3", messages: [] })
        : jsonOk({ id: 9, model: "combo:team", title: "", messages: [] })),
      "/api/chat/sessions": () => jsonOk({ object: "list", data: [] })
    });
    mount();
    await window.aigate.chat.openSession(9);
    expect(T.chatState.titleAuto).toBe(true);
    document.getElementById("chatRenameBtn").click();
    expect(document.getElementById("chatRenameModal").hidden).toBe(false);
    document.getElementById("chatRenameInput").value = "Rencana Q3";
    document.getElementById("chatRenameSave").click();
    await new Promise((r) => setTimeout(r, 10));
    expect(document.getElementById("chatTitleInput").value).toBe("Rencana Q3");
    expect(T.chatState.titleAuto).toBe(false);
    const before = calls.length;
    expect(T.autoTitleIfNeeded("pesan berikutnya")).toBe(false);
    expect(calls.length).toBe(before);
  });

  it("a session that already has a real title is not an auto-candidate", async () => {
    stubApi({
      "/api/chat/sessions/4": () => jsonOk({ id: 4, model: "combo:team", title: "Laporan penjualan", messages: [] })
    });
    mount();
    await window.aigate.chat.openSession(4);
    expect(T.chatState.titleAuto).toBe(false);
    expect(T.isAutoTitleCandidate("")).toBe(true);
    expect(T.isAutoTitleCandidate(null)).toBe(true);
    expect(T.isAutoTitleCandidate("New chat")).toBe(true);   // placeholder still auto-able
    expect(T.isAutoTitleCandidate("Laporan")).toBe(false);
  });
});

/* ============================================================
 * BUG-260916-1 p.5 — session panel expand/collapse + persistence
 * ============================================================ */
describe("session sidebar collapse (BUG-260916-1 p.5)", () => {
  it("toggle collapses/expands and persists to localStorage", async () => {
    stubApi({});
    localStorage.removeItem("aigate.chat.sidebarCollapsed");
    mount();
    const layout = document.getElementById("chatLayout");
    const btn = document.getElementById("chatSidebarToggle");
    expect(layout.classList.contains("is-collapsed")).toBe(false);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    btn.click();
    expect(layout.classList.contains("is-collapsed")).toBe(true);
    expect(btn.getAttribute("aria-expanded")).toBe("false");
    expect(localStorage.getItem("aigate.chat.sidebarCollapsed")).toBe("1");
    btn.click();
    expect(layout.classList.contains("is-collapsed")).toBe(false);
    expect(btn.getAttribute("aria-expanded")).toBe("true");
    expect(localStorage.getItem("aigate.chat.sidebarCollapsed")).toBe("0");
  });

  it("collapsed state survives a reload (restored on view show)", async () => {
    stubApi({});
    localStorage.setItem("aigate.chat.sidebarCollapsed", "1");
    mount();
    expect(document.getElementById("chatLayout").classList.contains("is-collapsed")).toBe(false);
    await window.aigate.chat.onShow();   // loadChat -> applies the stored state
    expect(document.getElementById("chatLayout").classList.contains("is-collapsed")).toBe(true);
    expect(document.getElementById("chatSidebarToggle").getAttribute("aria-expanded")).toBe("false");
    localStorage.removeItem("aigate.chat.sidebarCollapsed");
  });
});

/* ============================================================
 * Gemini-like redesign — the NEW structure the visual overhaul ships.
 * jsdom has no layout engine, so these assert the MARKUP SHAPE the redesign
 * depends on (pill wraps the reused combobox, composer is one surface holding
 * input + send/stop, settings has a Cancel affordance, thread renders a minimal
 * user bubble + plain assistant text, a friendly non-error empty state). They
 * complement (never replace) the 13 BUG-260916-1 assertions above.
 * ============================================================ */
describe("Gemini-like structure — top bar / rail / composer / thread", () => {
  it("model switcher lives inline in the composer (Gemini-style), reusing createCombobox", () => {
    stubApi({});
    mount();
    const composer = document.querySelector(".chat-composer");
    const composerModel = document.querySelector(".chat-composer-model");
    const pill = document.querySelector(".chat-model-pill");
    const input = document.getElementById("chatModelSwitch");
    expect(composer, ".chat-composer surface present").not.toBeNull();
    expect(composerModel, ".chat-composer-model wrapper present").not.toBeNull();
    expect(pill, "model pill present").not.toBeNull();
    expect(input, "#chatModelSwitch present").not.toBeNull();
    expect(pill.contains(input), "pill wraps the switcher input").toBe(true);
    // It sits INSIDE the composer surface (the Gemini-style placement), wrapped by
    // .chat-composer-model, not boxed in the top bar.
    expect(composer.contains(input), "switcher is inside the composer").toBe(true);
    expect(composerModel.contains(input), "switcher is inside .chat-composer-model").toBe(true);
    const bar = document.querySelector(".chat-bar");
    expect(bar, ".chat-bar present").not.toBeNull();
    expect(bar.contains(input), "switcher is no longer in the bar").toBe(false);
    // It is a real combobox (role + a linked listbox the widget renders into).
    expect(input.getAttribute("role")).toBe("combobox");
    expect(input.getAttribute("aria-controls")).toBe("chatModelSwitchList");
    expect(document.getElementById("chatModelSwitchList")).not.toBeNull();
  });

  it("gear / rename / delete are ghost buttons in the bar (clean, one row)", () => {
    stubApi({});
    mount();
    const bar = document.querySelector(".chat-bar");
    const actions = document.querySelector(".chat-bar-actions");
    expect(actions, "actions cluster present").not.toBeNull();
    expect(bar.contains(actions), "actions live in the bar").toBe(true);
    ["chatSettingsBtn", "chatRenameBtn", "chatDeleteBtn"].forEach((id) => {
      const b = document.getElementById(id);
      expect(b, "#" + id + " present").not.toBeNull();
      expect(actions.contains(b), "#" + id + " in the actions cluster").toBe(true);
      expect(b.classList.contains("chat-ghost-btn"), "#" + id + " is a ghost button").toBe(true);
    });
  });

  it("composer is a single rounded surface holding input + send + stop", () => {
    stubApi({});
    mount();
    const composer = document.querySelector(".chat-composer");
    expect(composer, ".chat-composer surface present").not.toBeNull();
    const input = document.getElementById("chatInput");
    const send = document.getElementById("chatSendBtn");
    const stop = document.getElementById("chatStopBtn");
    expect(composer.contains(input), "input inside the composer surface").toBe(true);
    expect(composer.contains(send), "send inside the composer surface").toBe(true);
    expect(composer.contains(stop), "stop inside the composer surface").toBe(true);
    expect(stop.hasAttribute("hidden"), "stop hidden until streaming").toBe(true);
    // Status line sits under the surface (composer wrap), not boxed inside it.
    const wrap = document.querySelector(".chat-composer-wrap");
    expect(wrap, ".chat-composer-wrap present").not.toBeNull();
    expect(wrap.contains(composer) && wrap.contains(document.getElementById("chatMsg")),
      "wrap holds the surface + status").toBe(true);
    // The composer is NOT inside the scrollable thread (it stays pinned below).
    expect(document.getElementById("chatThread").contains(composer),
      "composer is not inside the thread").toBe(false);
  });

  it("title is a borderless read-only heading above the thread", () => {
    stubApi({});
    mount();
    const title = document.getElementById("chatTitleInput");
    expect(title, "#chatTitleInput present").not.toBeNull();
    expect(title.getAttribute("readonly"), "read-only until renamed").not.toBeNull();
    expect(title.classList.contains("chat-title-input"), "carries the title class").toBe(true);
    // It is out of the bar, in its own title block above the thread.
    const bar = document.querySelector(".chat-bar");
    expect(bar.contains(title), "title is not boxed in the bar").toBe(false);
    const wrap = document.querySelector(".chat-title-wrap");
    expect(wrap && wrap.contains(title), "title lives in .chat-title-wrap").toBe(true);
  });

  it("user turn = a minimal bubble, assistant turn = plain text block", () => {
    stubApi({});
    mount();
    T.renderMessages([
      { role: "user", content: "Hi", tokens_in: null, tokens_out: null },
      { role: "assistant", content: "Hello there", tokens_in: 3, tokens_out: 5 }
    ]);
    const thread = document.getElementById("chatThread");
    const user = thread.querySelector(".chat-msg-user");
    const assistant = thread.querySelector(".chat-msg-assistant");
    expect(user, "user message present").not.toBeNull();
    expect(assistant, "assistant message present").not.toBeNull();
    // Both are text-bearing message nodes (the bubble vs plain text is pure CSS).
    expect(user.querySelector(".chat-msg-text").textContent).toBe("Hi");
    expect(assistant.querySelector(".chat-msg-text").textContent).toBe("Hello there");
    // Token meta is on the assistant turn only (small + muted in CSS).
    expect(assistant.querySelector(".chat-msg-tokens")).not.toBeNull();
    expect(user.querySelector(".chat-msg-tokens"), "user has no token line").toBeNull();
  });

  it("empty thread renders a friendly placeholder, not an error state", () => {
    stubApi({});
    mount();
    T.renderMessages([]);
    const thread = document.getElementById("chatThread");
    const empty = thread.querySelector(".chat-empty");
    expect(empty, "friendly empty placeholder present").not.toBeNull();
    expect(empty.textContent.trim().length, "has hint copy").toBeGreaterThan(0);
    // No message bubbles and no error styling on the empty state.
    expect(thread.querySelectorAll(".chat-msg").length).toBe(0);
    expect(empty.className).not.toMatch(/error/);
  });

  it("settings dialog has a Cancel button that closes it (besides Escape/overlay)", async () => {
    stubApi({
      "/api/chat/sessions/5": () => jsonOk({ id: 5, model: "combo:team", title: "T", messages: [] })
    });
    mount();
    await window.aigate.chat.openSession(5);
    document.getElementById("chatSettingsBtn").click();
    expect(document.getElementById("chatSettingsModal").hidden).toBe(false);
    const cancel = document.getElementById("chatSettingsCancel");
    expect(cancel, "#chatSettingsCancel present").not.toBeNull();
    cancel.click();
    expect(document.getElementById("chatSettingsModal").hidden).toBe(true);
  });
});

/* ============================================================
 * Waiting-for-response loader — pelangi border + cycling phrase.
 * It must appear the instant streaming starts (before the first token) and be
 * gone the moment the first SSE chunk lands. A controllable SSE reader lets us
 * observe the "before any token" window deterministically.
 * ============================================================ */
describe("streaming loader — rainbow border + cycling phrase (clears on first token)", () => {
  /** A fetch-Response-shaped SSE stream the test can feed frame-by-frame. */
  function sseStream() {
    const encoder = new TextEncoder();
    const queue = [];
    let pending = null;   // resolver for the currently-held read()
    let closed = false;
    const reader = {
      read() {
        if (queue.length) return Promise.resolve({ value: encoder.encode(queue.shift()), done: false });
        if (closed) return Promise.resolve({ done: true });
        return new Promise((res) => {
          pending = () => {
            pending = null;
            if (queue.length) res({ value: encoder.encode(queue.shift()), done: false });
            else res({ done: true });
          };
        });
      },
      cancel() { closed = true; if (pending) pending(); return Promise.resolve(); }
    };
    return {
      res: { ok: true, headers: { get: () => "text/event-stream" }, body: { getReader: () => reader } },
      push(frame) { queue.push(frame); if (pending) pending(); },
      close() { closed = true; if (pending) pending(); }
    };
  }

  /** Stub the routes, mount, set an existing session, and click Send. */
  function beginSend(sse) {
    stubApi({
      "/api/chat/sessions/21/complete": () => sse.res,
      "/api/chat/sessions/21": () => jsonOk({ id: 21, model: "combo:team", title: "T", messages: [] }),
      "/api/chat/sessions": () => jsonOk({ object: "list", data: [] })
    });
    mount();
    T.chatState.currentId = 21;
    T.chatState.currentModel = "combo:team";
    T.chatState.titleAuto = false;          // no auto-title PUT noise in this flow
    document.getElementById("chatInput").value = "hi";
    document.getElementById("chatSendBtn").click();   // -> sendChatMessage -> streamChat (sync startLoader)
  }

  afterEach(() => {
    const b = document.querySelector(".chat-msg-loading");
    if (b) T.stopLoader(b);                 // clear any leftover interval
    T.chatState.streaming = false;
    T.chatState.controller = null;
    T.chatState.currentId = null;
    T.chatState.currentModel = null;
  });

  it("before the first token the assistant bubble shows the rainbow loader + a cycling phrase", () => {
    const sse = sseStream();
    beginSend(sse);                          // loader is added synchronously in streamChat
    const bubble = document.querySelector(".chat-msg-assistant");
    expect(bubble, "live assistant bubble exists").not.toBeNull();
    expect(bubble.classList.contains("chat-msg-loading")).toBe(true);
    const text = bubble.querySelector(".chat-loader-text");
    expect(text, ".chat-loader-text present").not.toBeNull();
    expect(T.LoaderPhrases).toContain(text.textContent);   // phrase came from the pool
    expect(bubble.querySelector(".chat-loader-rainbow"), "rainbow border element present").not.toBeNull();
    // Deliberately do NOT close(): leave the reader pending so finishStream never
    // fires and re-renders the thread under the next test (isolate:false).
  });

  it("the first SSE chunk clears the loader and the real content shows in its place", async () => {
    const sse = sseStream();
    beginSend(sse);
    sse.push('data: {"choices":[{"delta":{"content":"Hel"}}]}\n\n');
    await new Promise((r) => setTimeout(r, 20));
    const bubble = document.querySelector(".chat-msg-assistant");
    expect(bubble.classList.contains("chat-msg-loading"), "loading class gone").toBe(false);
    expect(bubble.querySelector(".chat-loader-text"), "loader text gone").toBeNull();
    expect(bubble.querySelector(".chat-loader-rainbow"), "rainbow gone").toBeNull();
    expect(bubble.querySelector(".chat-msg-text").textContent).toBe("Hel");   // real streamed content
    sse.close();
    await new Promise((r) => setTimeout(r, 10));
  });

  it("exposes a loader phrase pool of >= 32 distinct phrases", () => {
    expect(T.LoaderPhrases.length, "pool size").toBeGreaterThanOrEqual(32);
    expect(new Set(T.LoaderPhrases).size, "all distinct").toBe(T.LoaderPhrases.length);
  });
});
