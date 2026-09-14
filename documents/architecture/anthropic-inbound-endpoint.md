# Design: Inbound Anthropic `/v1/messages` Endpoint (aigate)

**Status:** Design only — no `src/**` written (tech-architect write scope = `documents/architecture/**`).
**Goal:** aigate serves an Anthropic‑compatible `POST /v1/messages` so `claude-code` can point
`ANTHROPIC_BASE_URL=<aigate>/v1/messages` **directly, with no litellm in the middle**. After this
ships, `scripts/cli-tools/claude.sh` is re‑wired from litellm to aigate (TODO — script untouched).

**Design principle (R10 / DRY / KISS / SOLID):** the new surface reuses the EXISTING OpenAI‑flavored
pipeline (`resolve_target` → `provider_adapter.chat_completion` → usage/logging) exactly the way
`/v1/responses` already does (`router.py:334`, `_handle_responses` at `router.py:372`). The only new
work is (a) two pure translation functions (Anthropic request ↔ OpenAI chat) in `translator.py`, and
(b) a thin route handler in `router.py` that mirrors `_handle_responses`. No new provider/auth/usage
machinery is invented.

---

## 1. Verified facts (file:line citations)

Gateway surface today (`router.py:1-41` module docstring + routes):
- `router.py:128` `POST /v1/chat/completions` — OpenAI proxy (stream + non‑stream).
- `router.py:334` `POST /v1/responses` — **Responses→chat→backend→Responses envelope**, the pattern to follow.
- `router.py:478` `GET /v1/models` — provider/combo model list.
- **No `/v1/messages` route exists** (`router.py` has none; claude would 404 — confirmed by reading the file).

Translation engine (`translator.py`):
- `translator.py:170` `_translate_request_anthropic` — OUTBOUND OpenAI→Anthropic (aigate as *client* to an anthropic upstream). Builds `url_path="/v1/messages"`, sets `anthropic-version` header (`translator.py:201-203`), injects `max_tokens` default (`translator.py:184-193`). **Does NOT currently forward `tools`/`tool_choice`** (only `model/messages/system/max_tokens/temperature/top_p/top_k/stop`).
- `translator.py:252` `_translate_response_anthropic` — INBOUND‑to‑aigate OpenAI←Anthropic response (maps `tool_use`→OpenAI `tool_calls`). Inverse of what we need on the response path.
- `translator.py:107` `_openai_to_anthropic_messages` — OpenAI messages→Anthropic `messages` (handles `tool_calls`→`tool_use`, `role:tool`→`tool_result`). Inverse direction of what we need for request messages.
- `translator.py:43-55` `FORMAT_ALIASES` — `"claude"→"anthropic"`, etc.
- `provider_adapter.py:80-86` — when `fmt=="anthropic"`, egress uses `x-api-key` + `anthropic-version` (NOT `Authorization: Bearer`).

Routing mount: `server.py:26` imports `gateway.router`; `server.py:105` `app.include_router(router)`. **Adding a route in `router.py` auto‑mounts** — no `server.py` change needed.

Streaming limitation: `provider_adapter.py:247-259` — translated formats (anthropic/gemini) **cannot** stream (per‑chunk SSE translation unimplemented; router raises `streaming_unsupported_format` 400). The Responses surface already refuses `stream:true` with `responses_streaming_unsupported` (`responses.py:227-233`).

CLI preset truth: `cli_presets.py:170` `"claude": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_ANTHROPIC_ONLY)`; `cli_presets.py:133` `REASON_ANTHROPIC_ONLY`; comment block `cli_presets.py:122-153` says gateway "exposes ONLY OpenAI endpoints … NO inbound /v1/messages". This endpoint flips claude to `LAUNCH_VERIFIED` (`cli_presets.py:128`).

litellm alignment (PM R17): `litellm` serves `POST /v1/messages` → `base_process_llm_request(route_type="anthropic_messages")`, plus `POST /v1/messages/count_tokens` and a stub `POST /api/event_logging/batch` so claude‑code telemetry does not 404. We mirror these three routes.

Rules in force: R5 (`documents/`), R10 (Pydantic **v1**), R12 (every failure logged to `LogEntry`/DB), R32 (no kill/restart — design only), R33 (no new root files), R47 (facts only).

---

## 2. API contract — `POST /v1/messages`

### 2.1 Auth (see Decision 4)
Open like `/v1/chat/completions` + `/v1/responses` — no mandatory auth in Stage 1. Accepts **either**
header as the aigate credential (so claude‑code is plug‑and‑play):
- `Authorization: Bearer <aigate-key>`, **or**
- `x-api-key: <aigate-key>` (Anthropic‑native header claude‑code sends).

Either is treated as the internal key (ADR‑007 plaintext). If access control is later enabled, the
same internal key may arrive via either header (reuse the `_endpoint_authorized` pattern at
`router.py:921-935`). The client's `x-api-key` is **never** forwarded to the upstream — aigate supplies
the resolved provider's own credential (`provider_adapter.py:60-96`). The `anthropic-version` header
from claude‑code is accepted and ignored (aigate controls egress headers).

### 2.2 Request shape (Anthropic Messages API — inbound)
```json
{
  "model": "claude-sonnet-4-5",          // bare Anthropic model id (see Decision 1)
  "messages": [
    {"role":"user","content":"hello"},
    {"role":"assistant","content":[
       {"type":"text","text":"sure"},
       {"type":"tool_use","id":"t1","name":"bash","input":{"cmd":"ls"}}
    ]},
    {"role":"user","content":[
       {"type":"tool_result","tool_use_id":"t1","content":"file1\nfile2"}
    ]}
  ],
  "system": "You are a helpful agent.",   // string OR [{type:"text",text:...}]
  "max_tokens": 8192,                      // REQUIRED by Anthropic; injected if absent
  "temperature": 0.7,
  "top_p": 1,
  "top_k": 40,
  "stop_sequences": ["\n\n"],
  "tools": [                               // Stage 1 supported (Decision 3)
    {"name":"bash","description":"run a command",
     "input_schema":{"type":"object","properties":{"cmd":{"type":"string"}}}}
  ],
  "tool_choice": {"type":"auto"}           // auto|any|none|{type:"tool",name:"x"}
}
```
Validated by a Pydantic **v1** `AnthropicMessagesRequest` model (R10, mirrors `responses.py:111`
`ResponsesRequest`): declares `model:str`, `messages`, `max_tokens`, `stream`, `extra="allow"`;
semantic (translate‑or‑refuse) validation happens in the mapper. `stream:true` is refused up‑front
(§3, Decision 2).

### 2.3 Response shape (Anthropic Messages API — outbound)
```json
{
  "id": "msg_abc123",
  "type": "message",
  "role": "assistant",
  "model": "claude-sonnet-4-5",            // echoes REQUEST model ref (as responses.py:370 does)
  "content": [
    {"type":"text","text":"Here is the result …"},
    {"type":"tool_use","id":"t2","name":"bash","input":{"cmd":"pwd"}}
  ],
  "stop_reason": "end_turn",               // end_turn|tool_use|max_tokens|stop_sequence
  "stop_sequence": null,
  "usage": {"input_tokens": 120, "output_tokens": 30}
}
```
Built by the new `openai_chat_response_to_anthropic_messages(chat_result, request_model)` (inverse of
`translator.py:252` `_translate_response_anthropic`).

### 2.4 Error shape (Anthropic envelope — deliberate per‑surface choice)
All failures render as the **Anthropic** error body (so claude‑code parses them), while keeping the
SAME internal `GatewayError` model + HTTP status + `message`/`type`/`code` semantics as the rest of
the gateway:
```json
{"type":"error","error":{"type":"invalid_request_error","message":"...","code":"model_not_found"}}
```
HTTP status mirrors the OpenAI contract (`documents/api/OPENAI_COMPATIBLE_CONTRACT.md:54-59`):
400 (bad request), 401 (auth), 502/503/504 (upstream). **Why Anthropic‑shaped here** (vs the
Responses surface which kept OpenAI‑shaped per `responses.py:26-28`): claude‑code is Anthropic‑native
and expects `{"type":"error",...}`; litellm returns Anthropic‑shaped errors on `/v1/messages`. The
internal `GatewayError` is unchanged (DRY) — only the *rendering* for this route differs. Stable
machine codes: `anthropic_missing_model`, `anthropic_invalid_request`, `anthropic_streaming_unsupported`,
`anthropic_unsupported_field`, plus reused `model_not_found`/`endpoint_not_found`/`unauthorized`.

### 2.5 Sibling routes (litellm parity, claude‑code telemetry)
- **`POST /v1/messages/count_tokens`** — translate request → OpenAI chat payload (reuse the same
  mapper), then return `{"input_tokens": <estimate>}`. Stage 1 uses a **heuristic estimate** (UTF‑8
  bytes ÷ 4, rounded; `output_tokens:0`) — no upstream call, no universal tokenizer required (KISS/YAGNI).
  Documented limitation; a real tokenizer / upstream count is a future phase.
- **`POST /api/event_logging/batch`** — stub returning `202 Accepted` + `{}`. Prevents claude‑code
  telemetry 404 noise (litellm parity).

---

## 3. Translation flow (request ↔ response)

```
claude-code ──POST /v1/messages──▶ _handle_anthropic_messages (router.py, NEW)
                                        │
       ┌────────────────────────────────┘
       ▼
anthropic_messages_request_to_openai_chat(payload)        # translator.py, NEW
   • system (str|blocks)            → leading {"role":"system"}
   • messages[].content blocks      → OpenAI messages (_anthropic_to_openai_messages, NEW)
       text              → content string
       tool_use          → assistant message w/ tool_calls (id,name,input→arguments JSON)
       tool_result       → {"role":"tool","tool_call_id","content"}
   • tools [{name,description,input_schema}]
                                  → OpenAI tools [{type:"function",function:{name,description,parameters}}]
   • tool_choice                    → OpenAI tool_choice (auto/any→required/none/{type:function,name})
   • max_tokens / temperature / top_p / top_k / stop_sequences→stop  pass through
   • stream:true                    → REFUSE (anthropic_streaming_unsupported)
                                        │
       ▼  OpenAI‑flavored chat payload (identical shape chat/responses use)
resolve_target(model)  →  ResolvedTarget  (router.py:261 / responses.py:446 reuse)
   • X-Aigate-Endpoint header?  → _route_via_endpoint (router.py:938, reuse)
   • combo_used?                → execute_combo (router.py:316/462, reuse)
   • else                       → provider_adapter.chat_completion (router.py:321/467, reuse)
                                        │  adapter internally re-translates to target.format
                                        │  (anthropic/gemini via translator.py; openai passthrough)
       ▼  OpenAI chat response dict
_record_usage_safe(result, target, …)                    # B5.5, reuse (router.py:529)
openai_chat_response_to_anthropic_messages(result, model)  # translator.py, NEW
   • choices[0].message.content   → text content block(s)
   • choices[0].message.tool_calls→ tool_use blocks (arguments JSON → input)
   • finish_reason                → stop_reason (stop/tool_calls→tool_use/length→max_tokens)
   • usage prompt/completion      → input_tokens/output_tokens
   • id / model(ref)              → msg_<base> / request model ref
                                        │
       ▼  Anthropic Messages response  ──▶ claude-code
```
**Double‑translation note (anthropic upstream):** when the resolved target is `format=="anthropic"`,
the OpenAI payload we produce is re‑translated to Anthropic by `_translate_request_anthropic` before
egress (and the response re‑translated back by `_translate_response_anthropic`). This is **identical**
to how `/v1/responses` already behaves against an anthropic combo member (`responses.py` + adapter), so
it is a proven, consistent model — not a new one. To make tools survive that round‑trip,
`_translate_request_anthropic` MUST gain OpenAI→Anthropic `tools`/`tool_choice` passthrough (§5, translator.py change #4). The two converters are designed as careful inverses.

---

## 4. Design decisions (finalized + justified)

### 4.1 Model mapping → **(a) treat as bare model id, resolved by the existing resolver**
The Anthropic `model` (e.g. `claude-sonnet-4-5`) is passed **straight to `resolve_target(model)`**,
exactly like `/v1/chat/completions` (`router.py:206-218,261`) and `/v1/responses` (`router.py:385-446`).
- **DRY/KISS:** reuses `_resolve_bare_model` (`resolver.py:212`) — no new static Anthropic→provider map
  to maintain. The Anthropic model id claude‑code sends IS the real upstream model id, which is exactly
  what a `ProviderModel.model_id` stores for an anthropic‑type provider in aigate.
- **Correct failure:** if no enabled provider advertises that `model_id` → `TargetNotFound` → 400
  `model_not_found` (same envelope as chat). The operator fixes it by registering the provider/model or
  pointing claude at a `combo:<name>`/`provider:<name>` ref — the same levers aider/opencode already use.
- **Rejected (b) static map:** would duplicate resolver knowledge, drift, and violate YAGNI. The
  `default_provider` Setting (`resolver.py:202`) already resolves bare‑model ambiguity deterministically.
- **Operator guidance (doc'd, not code):** to make `claude-sonnet-4-5` usable, register an Anthropic‑type
  provider whose `ProviderModel.model_id == "claude-sonnet-4-5"` (or a `combo:` that includes it).

### 4.2 Streaming → **Stage 1 = NON‑STREAMING only**
- `provider_adapter.py:247-259` confirms translated formats cannot stream; the Responses surface
  already refuses `stream:true` (`responses.py:227-233`). The Anthropic SSE envelope
  (`message_start` / `content_block_delta` / `message_delta` / `message_stop`) is a *different* protocol
  from OpenAI SSE and is not translated today.
- claude‑code runs fine non‑streaming (no incremental token paint). **Decision:** Stage 1 rejects
  `stream:true` with `anthropic_streaming_unsupported` (400), mirroring `responses_streaming_unsupported`.
- **Phase 2 (future):** implement Anthropic SSE translation over `provider_adapter.chat_completion_stream`
  (openai‑format targets only; translated targets stay refused until per‑chunk translation lands).

### 4.3 Tools / agentic → **Stage 1 supports tools via pass‑through translation (NOT 400)**
- claude‑code is fundamentally agentic and emits `tools` + `tool_use`/`tool_result`. Refusing tools (the
  PM's "400 terkontrol" alternative) would make claude‑code unusable — rejected.
- **Request:** Anthropic `tools`/`tool_use`/`tool_result`/`tool_choice` translate to OpenAI
  `tools`/`tool_calls`/`role:tool`/`tool_choice` (§3). The OpenAI pipeline forwards them verbatim
  (`ChatCompletionRequest` uses `extra="allow"`, `router.py:81-96`), so OpenAI‑format upstreams get them
  natively; anthropic‑format upstreams get them via the **extended** `_translate_request_anthropic`
  (§5 #4).
- **Response:** OpenAI `tool_calls` → Anthropic `tool_use` blocks + `stop_reason:"tool_use"`
  (`openai_chat_response_to_anthropic_messages`, inverse of `translator.py:252`).
- **Limitations documented for Stage 1:** extended‑thinking (`thinking`/`thinking_blocks`) is NOT
  supported (claude‑code falls back to non‑thinking; would be a future phase); `cache_control` on
  system/tools is dropped (no OpenAI equivalent in Stage 1); tools against a `gemini`‑format target are
  not translated (known limitation). These are surfaced as `anthropic_unsupported_field` 400s ONLY where
  silent dropping would corrupt an agent loop (per `responses.py:21-25` philosophy) — thinking config is
  refused loudly; `metadata`/` stream`/harmless keys are dropped silently.

### 4.4 Auth → **accept `Bearer` OR `x-api-key` (plug‑and‑play), open by default**
- claude‑code sends `x-api-key` (its API key) when `ANTHROPIC_BASE_URL` is set. Accepting it as the
  aigate credential means the re‑wire (§7) only sets `ANTHROPIC_API_KEY=<aigate-key>` and works with zero
  extra config.
- Stage 1: endpoint is open like chat/responses (no mandatory auth); both headers are tolerated. If aigate
  later enables access control, the same internal key via either header is valid (reuse
  `router.py:921-935`). The client `x-api-key` is never forwarded upstream (aigate owns egress creds).

---

## 5. Files changed (implementation plan — NOT executed here)

### 5.1 `src/backend/gateway/translator.py` (primary translation work)
1. **NEW** `AnthropicMessagesRequest` (Pydantic v1, `extra="allow"`) — shape validation mirroring
   `responses.py:111`. Declares `model`, `messages`, `max_tokens`, `stream`.
2. **NEW** `anthropic_messages_request_to_openai_chat(payload) -> dict` (pure, raises `GatewayError`):
   - refuse `stream:true` → `anthropic_streaming_unsupported`;
   - refuse `thinking` with `enabled` → `anthropic_unsupported_field` (loud, not silent);
   - `system` (str or `[{type:"text",text}]`) → leading `system` message;
   - messages via **NEW** `_anthropic_to_openai_messages(messages)` (inverse of `translator.py:107`);
   - `tools` via **NEW** `_anthropic_tools_to_openai_tools` (`[{name,description,input_schema}]` →
     `[{type:"function",function:{name,description,parameters:input_schema}}]`);
   - `tool_choice` Anthropic→OpenAI (`auto`/`none`/`any`→`required`/`{type:"tool",name}`);
   - `max_tokens` (inject `_DEFAULT_MAX_TOKENS` `translator.py:39` if absent), `temperature`, `top_p`,
     `top_k`, `stop_sequences`→`stop` pass through; `metadata`/harmless dropped.
3. **NEW** `openai_chat_response_to_anthropic_messages(chat_result, request_model) -> dict` (inverse of
   `translator.py:252`): `choices[0].message` → `content` (text + tool_calls→`tool_use`),
   `finish_reason`→`stop_reason` (`_anthropic_stop_reason` reverse map), `usage`→`input_tokens`/
   `output_tokens`, id→`msg_<base>` (`_derive_id` style), model echoes request ref.
4. **EXTEND** `_translate_request_anthropic` (`translator.py:170`) to pass OpenAI `tools`/`tool_choice`
   through to the anthropic upstream (OpenAI→Anthropic form) — required so the double‑translation
   round‑trip in §3 delivers tools to an anthropic upstream. Add `_openai_tools_to_anthropic` /
   `_openai_tool_choice_to_anthropic` helpers. **Safe, additive** — only adds fields when present;
   existing outbound behavior unchanged.
5. Add stable‑code constants `ANTHROPIC_STREAMING_UNSUPPORTED_CODE`, `ANTHROPIC_UNSUPPORTED_FIELD_CODE`,
   `ANTHROPIC_MISSING_MODEL_CODE` (mirror `responses.py:45-47`).
6. Export the new public names in `__all__` (`translator.py:402`).

### 5.2 `src/backend/gateway/router.py` (thin handler mirroring `/v1/responses`)
1. **NEW** `@router.post("/v1/messages") def messages_completions(request)` — B5.6 wrapper (timing +
   `_record_request_log_safe`, `router.py:810`) **and** Anthropic‑shaped error rendering (§2.4): catches
   `GatewayError`/`Exception`, records the debug `RequestLog` row, then returns `JSONResponse(status,
   anthropic_error_envelope)` (does NOT re‑raise to the global OpenAI handler — deliberate, documented
   per‑surface deviation). Mirror `responses_completions` (`router.py:334-369`).
2. **NEW** `async def _handle_anthropic_messages(request, ctx)` — mirror `_handle_responses`
   (`router.py:372-475`):
   - `_parse_object_body` (`router.py:164`) → validate `AnthropicMessagesRequest`;
   - `anthropic_messages_request_to_openai_chat(payload)` → `chat_payload`;
   - optional `X-Aigate-Endpoint` → `_route_via_endpoint` (`router.py:938`, reuse);
   - `resolve_target(model)` (`router.py:261` style) → `TargetNotFound`→`model_not_found`;
   - combo → `execute_combo` / else `provider_adapter.chat_completion` (`router.py:312-323` reuse);
   - `_record_usage_safe` (B5.5, `router.py:529`);
   - `openai_chat_response_to_anthropic_messages(result, model)` → return Anthropic dict.
3. **NEW** helpers: `_anthropic_error_envelope(gw_error)` (wraps `{error:{...}}`→`{type:"error",error:{...}}`),
   `_anthropic_messages_id` (msg_ derivation). Optional sibling routes: `POST /v1/messages/count_tokens`
   (heuristic estimate, §2.5) and `POST /api/event_logging/batch` (202 stub, §2.5).

### 5.3 `src/backend/cli_presets.py` (flip claude to verified)
- `cli_presets.py:170`: `"claude": LaunchSupport(LAUNCH_UNSUPPORTED, REASON_ANTHROPIC_ONLY)`
  → `"claude": LaunchSupport(LAUNCH_VERIFIED)`.
- Update the comment block `cli_presets.py:122-153` (and `:153-154`) to state aigate now serves
  `/v1/messages` inbound (the litellm chain is no longer required). Keep `REASON_ANTHROPIC_ONLY`
  constant (`cli_presets.py:133`) for other potential consumers, but claude no longer uses it.

**No `server.py` change:** `app.include_router(router)` (`server.py:105`) auto‑mounts the new routes.

---

## 6. Error handling + R12 (log to DB on success/error)

- **R12 / ADR‑011:** every failure path logs to `LogEntry` via `backend.log`. The handler mirrors
  `_handle_responses` (`router.py:372`): wraps the call in `try/except GatewayError/Exception`; on error
  calls `_record_request_log_safe(ctx, request, t0, error_envelope=…, http_status=…)` then renders the
  Anthropic error; on success calls `_record_request_log_safe(ctx, request, t0, result=result,
  http_status=200)`. `_record_request_log_safe` (`router.py:810`) is fail‑open and gated by
  `request_log_enabled` (B5.6).
- **B5.5 usage:** `_record_usage_safe(result, target, …)` (`router.py:529`) on the success path records a
  `UsageRecord` (fail‑open, never alters the client response) — `input_tokens`/`output_tokens` from the
  Anthropic usage block flow through.
- **Translation refusals** log via `log_warning` (mirroring `responses.py:238-242`) before raising the
  stable‑code `GatewayError`, so the refusal reason lands in `LogEntry`.
- **Upstream failures** propagate as `UpstreamError` from `provider_adapter` (`provider_adapter.py:29`)
  and are rendered Anthropic‑shaped by the route wrapper (§2.4). The adapter already logs (R12) its own
  connect/timeout/HTTP errors (`provider_adapter.py:108-133`).

---

## 7. Re‑wire `claude.sh` — TODO (script NOT changed by this design)

`scripts/cli-tools/claude.sh` currently chains `claude → litellm(/v1/messages) → aigate`. After this
endpoint ships, re‑wire it to point claude‑code **directly** at aigate. Plan (to be executed by be‑dev,
not here):

1. Replace the litellm env block (`claude.sh:66-90`) with aigate gateway env:
   - `AIGATE_BASE` (already from `load_gateway_config`, `claude.sh:44`) → derive
     `ANTHROPIC_BASE_URL="$AIGATE_BASE/v1"` (aigate serves `/v1/messages` under `/v1`).
   - `ANTHROPIC_API_KEY` ← aigate **internal** API key (the same value chat/responses accept; today the
     script uses `AIGATE_LITELLM_API_KEY` default `sk-aigate` — rename to the aigate key).
   - `ANTHROPIC_MODEL` optional → still forwarded as `--model`/`ANTHROPIC_MODEL`.
2. Drop the litellm reachability probe (`claude.sh:78-86`) and the `/health/liveliness` check; optionally
   probe `GET /v1/models` on aigate instead (non‑auth, `router.py:478`).
3. Keep the Termux/glibc caveat (`claude.sh:57-64`) — unchanged; that is about the claude binary, not the proxy.
4. Update the `claude.sh:19-29` header comment: aigate now exposes inbound `/v1/messages` (this design),
   so the litellm middleman is removed; chain becomes `claude-code → aigate(/v1/messages) → backend`.

---

## 8. Open questions / future phases
- **Phase 2 — Anthropic SSE streaming:** translate OpenAI SSE → Anthropic `message_start`/
  `content_block_delta`/`message_delta`/`message_stop` over `provider_adapter.chat_completion_stream`
  (openai‑format targets first; translated targets stay refused).
- **Extended thinking:** `thinking`/`thinking_blocks` round‑trip (needs thinking blocks ↔ OpenAI mapping).
- **Real `count_tokens`:** swap the heuristic estimate for an upstream/ tokenizer‑based count.
- **Gemini tool passthrough:** `_translate_request_gemini` (`translator.py:207`) currently drops tools;
  add tool translation if claude is ever routed to a gemini provider.
- **Per‑provider model aliasing:** if operators need `claude-*` to map to a specific aigate provider
  regardless of `ProviderModel.model_id`, that is a resolver concern (option (b) from Decision 4.1) and
  out of scope for Stage 1.
