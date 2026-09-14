# Desain: Anthropic Inbound Streaming — `POST /v1/messages` (Tahap 2 / B7)

**Status:** Design only. Tidak ada `src/**`/`tests/**` ditulis (write scope = `documents/architecture/**`).
**Tujuan:** aigate stream Anthropic Messages API (`stream:true`) — translate Anthropic SSE <-> OpenAI/aigate SSE, reuse translator + stage-1 non-streaming route. claude-code dapet token paint real-time padahal backend bisa OpenAI/combo.

**Prinsip (R10 / DRY / KISS / SOLID):** representasi internal stream = **OpenAI chat-completion chunk dicts** (sama yg `_streaming_response` pakai hari ini). Edge `/v1/messages` decode upstream OpenAI SSE -> encode ke Anthropic SSE. Tidak bikin mesin streaming baru; reuse `anthropic_messages_request_to_openai_chat`, `_derive_anthropic_id`, `_openai_finish_to_anthropic`, `_streaming_response` priming + usage-after-stream.

---

## 0. KOREKSI FAKTA PM (re-check di source, bukan memory)

- PM memory: `cli_presets.py:170` claude `LAUNCH_UNSUPPORTED` (REASON_ANTHROPIC_ONLY). **SALAH hari ini** — stage-1 sudah ship & flip: `cli_presets.py:174` `"claude": LaunchSupport(LAUNCH_VERIFIED)`. `REASON_ANTHROPIC_ONLY` (`cli_presets.py:133`) jadi unused buat claude. => B7 streaming BUKAN unblock claude (sudah VERIFIED), tapi UX upgrade (token paint). Catat di state.md kalau perlu.
- PM memory line drift (karena kode nambah): handler chat `router.py:139` (bukan 128), responses `router.py:369` (bukan 334), stage-1 messages `router.py:528` (benar), `_translate_request_anthropic` `translator.py:183` (bukan 170), `_translate_response_anthropic` `translator.py:318` (bukan 252). Semua diverifikasi hari ini.

---

## 1. Fakta terverifikasi (file:line)

Gateway surface (`router.py`):
- `router.py:139` `POST /v1/chat/completions` — OpenAI proxy (stream + non-stream).
- `router.py:369` `POST /v1/responses` — Responses->chat.
- `router.py:528` `POST /v1/messages` — **stage-1 non-streaming** handler `messages_completions`.
- `router.py:578` `_handle_anthropic_messages` — logic stage-1.
- `router.py:674` `_anthropic_error_body`, `router.py:679` `_anthropic_error_response` — render Anthropic envelope.
- `router.py:688` `messages_count_tokens` (sibling route).
- `router.py:902` `_streaming_response` — SSE OpenAI **pass-through**; `router.py:968` `StreamingResponse(media_type="text/event-stream", headers{Cache-Control:no-cache, X-Accel-Buffering:no})`.
- `router.py:845` `_extract_usage_from_sse` (parse usage dari byte SSE), `router.py:874` `_record_stream_usage_safe` (usage setelah stream kelar).
- `router.py:837` `_streaming_unsupported_error()`, `router.py:831` `STREAMING_UNSUPPORTED_MSG`.
- `router.py:316-342` branch streaming di chat (combo -> `resolve_combo_stream_target`, lalu `_streaming_response`).
- `router.py:1305-1348` branch streaming di `_route_via_endpoint` (provider openai + combo member openai).
- `router.py:160-172` wrapper pattern (B5.6: `_record_request_log_safe`).

Translator (`translator.py`):
- `translator.py:45-48` stable codes: `ANTHROPIC_STREAMING_UNSUPPORTED_CODE` dll.
- `translator.py:183` `_translate_request_anthropic` (OUTBOUND anthropic).
- `translator.py:318` `_translate_response_anthropic` (INBOUND openai<-anthropic, non-stream).
- `translator.py:630` `anthropic_messages_request_to_openai_chat` — **refuse `stream:true` di :645** (stage-1 non-stream).
- `translator.py:718` `openai_chat_response_to_anthropic_messages` (non-stream inverse).
- `translator.py:453` `_derive_anthropic_id(chat_id, prefix)` — derive `msg_` dari `chatcmpl-`.
- `translator.py:619` `_openai_finish_to_anthropic` (stop_reason map). `translator.py:375` `_anthropic_stop_reason` (inverse).
- `translator.py:828` `AnthropicMessagesRequest` (Pydantic v1, `extra="allow"`).
- `translator.py:676` `translate_error(format, status, raw)` — map error upstream -> OpenAI envelope (aman, hanya message/type/code).

Adapter (`provider_adapter.py`):
- `provider_adapter.py:43` `_STREAM_TIMEOUT = httpx.Timeout(30, connect=10, read=300, write=30, pool=10)`.
- `provider_adapter.py:214` `chat_completion_stream` — **OpenAI pass-through bytes only**; `provider_adapter.py:247-259` TOLAK format != openai (raise `UpstreamError 400 streaming_unsupported_format`).
- `provider_adapter.py:267-272` url/headers (`Accept:text/event-stream`, `Authorization:Bearer`).
- `provider_adapter.py:282` `client.stream("POST", ...)`.
- `provider_adapter.py:284-330` status map: 401->502 `upstream_401`, 5xx->502 `upstream_5xx`, 4xx->`upstream_{code}` (status dipertahankan).
- `provider_adapter.py:332-354` mid-stream transport failure -> `UpstreamError 502 upstream_stream_interrupted` (setelah byte keluar).
- `provider_adapter.py:355-367` timeout -> 504 `upstream_timeout`. `provider_adapter.py:368-380` connect -> 503 `proxy_503`.
- `provider_adapter.py:80-89` egress anthropic pakai `x-api-key` (kredensial provider, bukan client).

Mount: `server.py:26` import `gateway.router`; `server.py:105` `app.include_router(router)`. Tambah route = auto-mount.

Combo stream resolver: `combo_routing.py:525` `resolve_combo_stream_target`.

Test harness existing: `tests/backend/test_gateway_stream.py` (respx + `StaticPool` sqlite in-memory, `_patch_db`, `_client`), `tests/backend/test_anthropic_messages.py`, `tests/backend/conftest.py` (DB isolation via `AIGATE_DB_PATH` sebelum import `backend`).

---

## 2. Endpoint spec — streaming `POST /v1/messages`

- **Request:** `Content-Type: application/json`, body Anthropic Messages + `"stream": true`.
- **Auth (reuse stage-1 §2.1):** terima `Authorization: Bearer <key>` ATAU `x-api-key: <key>` (both = aigate internal key). Header `anthropic-version` di-ignore (aigate kontrol egress). Client `x-api-key` TIDAK pernah di-forward (adapter supply kredensial provider — `provider_adapter.py:80-89`).
- **Response:** `Content-Type: text/event-stream`; header `Cache-Control: no-cache`, `X-Accel-Buffering: no` (mirror `router.py:971`). Body = SSE Anthropic (`event:` + `data:` + `\n\n` per event, lihat §4).
- **Accept header:** claude-code kirim `Accept: text/event-stream` — kita echo/set di response.
- **Non-stream preserved:** `stream:false`/absent -> stage-1 path utuh (tidak ada breaking change).

---

## 3. Request translation mapping (Anthropic -> OpenAI/aigate)

Reuse `anthropic_messages_request_to_openai_chat` dg param baru `allow_stream: bool = False` (default False = behavior stage-1 utuh, refuse `stream:true` di `:645`). Saat `allow_stream=True`: skip refusal, set `chat["stream"]=True` + `chat["stream_options"]={"include_usage": true}` (wajib biar dapet chunk usage buat `message_delta`).

| Anthropic field | OpenAI/aigate field | Catatan |
|---|---|---|
| `model` | `model` | di-resolve verbatim (`resolve_target`), sama spt stage-1 (`router.py:583`, `:642`). |
| `system` (str\|blocks) | leading `{"role":"system"}` | `_anthropic_system_to_text` (`translator.py:561`) -> insert index 0. |
| `messages[].content` blocks | OpenAI messages | `_anthropic_to_openai_messages` (`translator.py:469`): text->content, tool_use->tool_calls, tool_result->role:tool. |
| `max_tokens` | `max_tokens` | inject `_DEFAULT_MAX_TOKENS` (`translator.py:40,692`) kalau absen. |
| `temperature` | `temperature` | pass-through (`translator.py:701`). |
| `top_p` | `top_p` | pass-through. |
| `top_k` | `top_k` | pass-through (OpenAI-native upstream ignore; aman). |
| `stop_sequences` | `stop` | remap key (`translator.py:703`). |
| `tools` | `tools` | `_anthropic_tools_to_openai_tools` (`translator.py:576`). |
| `tool_choice` | `tool_choice` | `_anthropic_tool_choice_to_openai` (`translator.py:597`). |
| `stream:true` | `stream:true` + `stream_options.include_usage` | **baru** saat allow_stream. |
| `metadata` | — | DROP (stateless gateway, spt stage-1). |
| `cache_control` | — | DROP (no OpenAI equiv Tahap 2). |
| `thinking` | — | REFUSE loudly (`anthropic_unsupported_field`) — stage-1 sudah di `:661`; pertahankan di stream. |
| `anthropic-version` header | — | di-ignore (egress adapter). |
| client `x-api-key`/`Authorization` | — | TIDAK forward (adapter supply kredensial provider). |

**No-mapping fields yang disadari:** `metadata`, `cache_control`, `thinking` (refuse), `anthropic-version` header — semua di atas.

---

## 4. SSE event mapping (both directions)

Representasi internal = OpenAI chunk dict (di-parse dari upstream OpenAI SSE). Karena Tahap 2 HANYA stream upstream **openai-format** (lihat §7 keputusan), arah utama = **OpenAI chunk -> Anthropic SSE**.

### 4.1 OpenAI chunk -> Anthropic SSE (INBOUND client anthropic, upstream openai)

NEW pure `openai_chunk_stream_to_anthropic_events(chunks, request_model) -> Iterator[str]` di `translator.py` (peer `_translate_response_anthropic`). State: `msg_id` (dari chunk pertama `id` via `_derive_anthropic_id(_, "msg_")`, `translator.py:453`), `block_open`, `finish`, `usage`.

| OpenAI chunk | Anthropic SSE event(s) |
|---|---|
| pertama (ada `delta.role=="assistant"` / delta pertama) | `message_start` (`id=msg_.., type:message, role:assistant, model:request_model, content:[], stop_reason:null, usage:{input_tokens:0, output_tokens:0}`) LALU `content_block_start` (`index:0, content_block:{type:text, text:""}`). |
| `delta.content: "..."` | `content_block_delta` (`index:0, delta:{type:text_delta, text:...}`). |
| `delta.tool_calls:[{index,id,name,function.arguments}]` | `content_block_start` (`index:1, content_block:{type:tool_use, id, name, input:{}}`) LALU tiap partial `function.arguments` -> `content_block_delta` (`index:1, delta:{type:input_json_delta, partial_json:...}`) LALU `content_block_stop` (`index:1`). (Buffering partial_json spt Anthropic spec.) |
| `finish_reason != null` (usage belum) | simpan finish; **jangan** emit message_stop dulu. |
| chunk `usage` (biasanya `choices:[]` + `usage`) | `message_delta` (`delta:{stop_reason:_openai_finish_to_anthropic(finish), stop_sequence:null}, usage:{input_tokens:prompt_tokens, output_tokens:completion_tokens}`) LALU `message_stop`. |
| `data: [DONE]` | ignore (Anthropic pakai `message_stop`). |
| upstream `ping` | tidak ada di OpenAI; kita TIDAK emit ping (optional future). |

**Chunking/flush:** tiap Anthropic event di-format jadi 1 SSE block (`event: X\ndata: {json}\n\n`) dan langsung `yield` (flush per chunk = low latency). Preserve `stop_reason` via `_openai_finish_to_anthropic` (`translator.py:619`); preserve `usage` dari chunk usage terakhir.

**Limitasi input_tokens di message_start = 0:** OpenAI stream tidak kirim prompt usage di awal (cuma di chunk usage akhir). `message_start.usage.input_tokens` = 0; nilai final ada di `message_delta.usage` (Anthropic bilang count cumulative — acceptable). Open question §7-R1.

### 4.2 Anthropic SSE -> OpenAI chunk (reverse; FUTURE, bukan Tahap 2)

Dokumentasi utk kalau kelak stream upstream **anthropic-format** (hari ini di-tolak `provider_adapter.py:247`):
- `message_start` -> chunk pertama `delta:{role:assistant}`.
- `content_block_delta` `text_delta` -> `delta.content`.
- `content_block_delta` `input_json_delta` -> `delta.tool_calls` (+ buffering partial_json -> arguments).
- `message_delta.stop_reason` -> `finish_reason` (`_anthropic_stop_reason`, `translator.py:375`).
- `message_stop` -> `data: [DONE]`.

Tahap 2 TIDAK implement reverse ini (upstream anthropic streaming = deferred, §7-R3).

---

## 5. Error mapping (Anthropic `error` event / envelope)

### 5.1 Pre-first-byte (priming) — clean JSON
Sama spt `_streaming_response` (`router.py:933`), kita **prime** generator sebelum commit SSE. Kalau priming raise `UpstreamError`/`GatewayError` -> `messages_completions` wrapper catch -> `_anthropic_error_response` (`router.py:679`) -> `{"type":"error","error":{...}}` JSON (bukan SSE). Mapping (dari `provider_adapter.py`):

| Penyebab | HTTP | Anthropic `error.type` / `code` |
|---|---|---|
| `ConnectError` / unreachable | 503 | `upstream_error` / `proxy_503` (`provider_adapter.py:368-380`) |
| `TimeoutException` (read/connect) | 504 | `upstream_error` / `upstream_timeout` (`provider_adapter.py:355-367`) |
| HTTP 401 | 502 | `upstream_error` / `upstream_401` (`provider_adapter.py:284-292`) |
| HTTP 429 | 429 | `upstream_error` / `upstream_429` (`provider_adapter.py:302-330`) |
| HTTP 5xx | 502 | `upstream_error` / `upstream_5xx` |
| HTTP 4xx lain | status asli | `upstream_error` / `upstream_{code}` |
| `stream:true` ke upstream format != openai | 400 | `invalid_request_error` / `streaming_unsupported_format` (`_streaming_unsupported_error`, `router.py:837`) |

### 5.2 Mid-stream (setelah message_start keluar)
Upstream raise `UpstreamError` mid-stream (`provider_adapter.py:336-354`) -> status sudah 200. **Keputusan:** emit 1 frame `event: error\ndata: {"type":"error","error":{type,message,code}}\n\n` (Anthropic-shaped, pakai `msg_id` correlation) LALU close generator. Lebih spec-aligned drpd truncate diam (lihat §7-R6 utk konfirmasi user). Correlation id = `msg_` id (dari `_derive_anthropic_id`) biar log terikat.

### 5.3 No secret leak
`UpstreamError` envelope hanya bawa `message/type/code` (`provider_adapter._error`); `translate_error` (`translator.py:676`) juga hanya itu. Client `x-api-key`/`Authorization` TIDAK di-forward; provider key cuma di egress (`provider_adapter.py:80-89`). `_anthropic_error_body` (`router.py:674`) cuma wrap `error` dict — tidak dump request/header.

---

## 6. Route mounting (reuse server.py, no breaking change)

- **Tidak ubah `server.py`** — `app.include_router(router)` (`server.py:105`) auto-mount.
- Di `messages_completions` (`router.py:528`): setelah parse+validate+translate (`anthropic_messages_request_to_openai_chat(payload, allow_stream=True)`), branch:
  - `stream` true -> `return await _handle_anthropic_messages_stream(...)` (return `StreamingResponse` ATAU Anthropic JSON error bila priming gagal).
  - else -> stage-1 logic utuh (`_handle_anthropic_messages`, `router.py:578`).
- NEW `_handle_anthropic_messages_stream(request, ctx)` ditempel di samping `_handle_anthropic_messages` (`router.py:578`):
  - endpoint header? (`router.py:616`) -> branch stream mirip `_route_via_endpoint` openai-provider (`router.py:1305`) + combo (`router.py:1325`) tapi stream lewat encoder Anthropic (bukan `_streaming_response` mentah).
  - else `resolve_target` (`router.py:642`); combo -> `resolve_combo_stream_target` (`combo_routing.py:525`) -> member pertama openai; else provider.
  - upstream format != openai -> `_streaming_unsupported_error()` (Anthropic envelope).
  - panggil NEW `_anthropic_stream_response(target, chat_payload, ctx, endpoint_id, request_model)`.
- NEW `_anthropic_stream_response(...)` — mirror `_streaming_response` (`router.py:902`) TAPI: force `stream:true`+`include_usage`; prime `provider_adapter.chat_completion_stream` (`provider_adapter.py:214`); parse bytes->OpenAI chunk dicts (NEW `_iter_openai_sse_chunks`); encode via `openai_chunk_stream_to_anthropic_events`; `finally` -> `agen.aclose()` + `_record_stream_usage_safe` (`router.py:874`) setelah kelar.
- **B5.6 request-log:** wrapper panggil `_record_request_log_safe(ctx, request, t0, ...)` — untuk stream, `result` bisa `StreamingResponse` (bukan dict); panggil dgn `result=None, http_status=200` (mirror chat). Usage lewat `_record_stream_usage_safe`.

---

## 7. Testing plan

### 7.1 Unit (translator streaming) — `tests/backend/test_anthropic_messages_stream.py` (NEW)
- Pure function `openai_chunk_stream_to_anthropic_events`: feed list OpenAI chunk dicts (copy `SSE_BODY` shape dari `test_gateway_stream.py:50`) -> assert urutan event: `message_start`, `content_block_start`, `content_block_delta` xN, `message_delta` (`stop_reason` + `usage`), `message_stop`. Assert `stop_reason` map benar via `_openai_finish_to_anthropic`.
- Error mapping unit: `UpstreamError(429, ..., "upstream_429")` -> `anthropic_error_response` body `{"type":"error","error":{"type":"upstream_error","code":"upstream_429"}}`.
- Refuse: `anthropic_messages_request_to_openai_chat(payload, allow_stream=False)` masih raise `anthropic_streaming_unsupported` (stage-1 intact); `allow_stream=True` set `stream:true` + `stream_options.include_usage`.

### 7.2 G3 isolated gateway boot (no :8080)
Reuse pola `test_gateway_stream.py`: `StaticPool` sqlite in-memory + `monkeypatch.setattr(db_mod/resolver/router/..., "SessionLocal", sf)` (`_patch_db`), `respx.mock` POST `http://provider.test/v1/chat/completions` return `SSE_BODY` (`text/event-stream`). `TestClient(app).post("/v1/messages", json={model:"provider:test:gpt-4o", messages:[...], stream:true})`. Assert:
- `resp.status_code==200`, `content-type` startswith `text/event-stream`, `cache-control:no-cache`.
- Parse SSE -> assert event sequence Anthropic lengkap + `stop_reason` benar + `usage` ada di `message_delta`.
- Assert upstream receive `stream:true` + model rewritten ke `gpt-4o` (spt `test_gateway_stream.py:171`).
- **Isolasi:** `TestClient` in-process = TIDAK bind port (paling aman, prefer). Kalau butuh real-process boot: set `AIGATE_DB_PATH` ke temp sqlite SEBELUM import `backend` (pola `conftest.py`), lalu uvicorn bind **:8099** (bukan :8080 user). Tear down: stop proc + hapus temp DB. **JANGAN sentuh :8080.**

### 7.3 Regression
- `test_anthropic_messages.py` stage-1 non-stream tetap hijau (no breaking change).
- `test_gateway_stream.py` OpenAI pass-through tetap hijau.

---

## 8. Risks / Open questions / DECISIONS NEEDED

**Keputusan sudah diambil (recommended):**
- D-A: Tahap 2 stream HANYA upstream **openai-format** (provider openai, combo member openai, endpoint-bound openai). Upstream anthropic/gemini -> 400 `streaming_unsupported_format` (konsisten `provider_adapter.py:247`). Alasan: produk inti = kasih claude-code akses ke provider NON-anthropic; anthropic-asli claude-code langsung ke Anthropic.
- D-B: Prime generator sblm commit SSE (mirror `router.py:933`) -> error pre-first-byte jadi JSON Anthropic bersih.
- D-C: Reuse `anthropic_messages_request_to_openai_chat(payload, allow_stream=True)` — 1 sumber mapping request, stage-1 behavior identik (default False).

**Risks / open questions:**
- **R1 (low):** `message_start.usage.input_tokens = 0` (OpenAI stream tdk kirim prompt usage awal). Final di `message_delta`. Acceptable? (recommended: ya.)
- **R2 (medium):** `tool_use` streaming (`input_json_delta`) — Tahap 2 map basic (content_block_start tool_use + delta input_json_delta + stop), tapi buffering partial_json = riskiest. Opsi: **defer tool_use streaming ke future phase** (Tahap 2 text-only + kalau stream bawa tool_calls, buffer jd 1 tool_use block di akhir). Perlu pilihan user.
- **R3 (future):** upstream **anthropic-format** streaming (double-translate anthropic->openai->anthropic). Hari ini di-tolak adapter. Deferred.
- **R4 (kept):** `thinking` streaming di-refuse (stage-1 sudah refuse `thinking.enabled`).
- **R5 (low):** request-log utk stream — pastikan `_record_request_log_safe` dipanggil dgn `result=None` bila StreamingResponse; usage lewat `_record_stream_usage_safe`.
- **R6 (need user):** mid-stream failure -> emit `event: error` frame (recommended, spec-aligned) vs silent truncate (spt OpenAI surface hari ini `router.py:233-235`)?

**DECISIONS NEEDED dari user:**
1. **Scope Tahap 2:** openai-format upstream ONLY (recommended, D-A) — setuju?
2. **Tool-use streaming:** include basic mapping (R2) atau defer ke future phase (text-only Tahap 2)?
3. **Mid-stream error:** emit `event: error` frame (recommended) atau silent truncate (R6)?

---

## 9. File:line reference index (semua klaim)

- `router.py:139,369,528,578,674,679,688,902,968,845,874,837,831,316,342,1305,1348,160,971,642,616,105(server.py)`
- `translator.py:45,48,183,318,630,645,718,453,619,375,561,576,597,469,40,692,701,703,676,828`
- `provider_adapter.py:43,214,247,259,267,272,282,284,330,332,354,355,367,368,380,80,89`
- `server.py:26,105`
- `combo_routing.py:525`
- `cli_presets.py:174,133`
- `tests/backend/test_gateway_stream.py:50,148,171,298,315,377,399`; `tests/backend/conftest.py` (DB isolation)
- `documents/architecture/anthropic-inbound-endpoint.md` (stage-1 design, §2.1 auth, §4 decisions)
