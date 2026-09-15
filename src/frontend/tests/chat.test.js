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
 * Wiring — new-session flow (modal -> POST -> open) with stubbed fetch
 * ============================================================ */
describe("new chat flow — picker + create", () => {
  it("New chat button opens the target-picker modal after the model list loads", async () => {
    stubApi({ "/v1/models": () => jsonOk({ data: [] }) });
    mount();
    document.getElementById("chatNewBtn").click();
    await new Promise((r) => setTimeout(r, 10));
    expect(document.getElementById("chatNewModal").hidden).toBe(false);
  });

  it("submits the chosen model and opens the new session", async () => {
    const calls = stubApi({
      "/v1/models": () => jsonOk({ data: [{ id: "provider:openai:gpt-4o", owned_by: "openai" }] }),
      "/api/chat/sessions": (u, m) => {
        if (m === "POST") return jsonOk({ id: 11, title: "New chat", model: "provider:openai:gpt-4o" });
        return jsonOk({ object: "list", data: [] });
      },
      "/api/chat/sessions/11": () => jsonOk({ id: 11, model: "provider:openai:gpt-4o", title: "New chat",
        system_prompt: "", temperature: null, messages: [{ role: "assistant", content: "hi", tokens_in: null, tokens_out: 5 }] })
    });
    mount();
    document.getElementById("chatNewBtn").click();   // opens modal + fetches models
    await new Promise((r) => setTimeout(r, 10));

    // Target value is read straight from the picker input (combobox fallback).
    document.getElementById("chatNewModel").value = "provider:openai:gpt-4o";
    document.getElementById("chatNewTitleInput").value = "My chat";
    document.getElementById("chatNewCreate").click();

    await new Promise((r) => setTimeout(r, 20)); // let create + open resolve

    const post = calls.find((c) => c.method === "POST" && c.url === "/api/chat/sessions");
    expect(post, "POST /api/chat/sessions was called").toBeTruthy();
    expect(JSON.parse(post.body).model).toBe("provider:openai:gpt-4o");
    expect(JSON.parse(post.body).title).toBe("My chat");

    // modal closed + thread shows the persisted assistant message
    expect(document.getElementById("chatNewModal").hidden).toBe(true);
    const thread = document.getElementById("chatThread");
    expect(thread.querySelector(".chat-msg-assistant")).not.toBeNull();
    expect(document.getElementById("chatTarget").textContent).toContain("gpt-4o");
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
