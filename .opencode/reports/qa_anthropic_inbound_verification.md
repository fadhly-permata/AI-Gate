# QA Report — Verifikasi Inbound Anthropic `/v1/messages` (Stage 1)

- **Tanggal:** 2026-09-09
- **Verifikator:** qa-engineer (independen; read-only ke `src/**`, `tests/**`, `documents/**`)
- **Target impl be-dev:** `src/backend/gateway/translator.py`, `src/backend/gateway/router.py`, `src/backend/cli_presets.py`, `tests/backend/test_anthropic_messages.py`
- **Referensi:** `documents/architecture/anthropic-inbound-endpoint.md`, `OPERATING_RULES.md` (R12/R14/R20/R23/R25/R47), `.opencode/rules/code-quality-principles.md`
- **Batas sandbox:** sesuai R14/R20 — `py_compile` + `pytest` jalan di sandbox; env user gak bisa install dep. Full e2e run-time **belum** diverifikasi di sini (lihat §6).

---

## 1. py_compile (semua file yang diubah be-dev)

```
python -m py_compile \
  src/backend/gateway/translator.py \
  src/backend/gateway/router.py \
  src/backend/cli_presets.py \
  tests/backend/test_anthropic_messages.py
→ PY_COMPILE_OK_ALL  (bersih, 0 error)
```

Runtime import check tambahan (`PYTHONPATH=src:.`):
- `backend.gateway.translator`, `backend.gateway.router`, `backend.cli_presets` import **bersih** (py_compile cuma cek syntax; ini cek missing-symbol/circular-import).
- Export baru hadir: `AnthropicMessagesRequest`, `anthropic_messages_request_to_openai_chat`, `openai_chat_response_to_anthropic_messages`.
- `cli_presets.LAUNCH_SUPPORT["claude"]` = `LaunchSupport(mode='verified', ...)` → konfirmasi flip claude ke `LAUNCH_VERIFIED`.

---

## 2. pytest — hasil NYATA

### 2a. `tests/backend/test_anthropic_messages.py -v`
- **11 pure-function tests PASSED** (translator: basic / system-string+blocks / tool_use blocks / tool_result blocks / tools+tool_choice forward / stream-refused / thinking-refused / max_tokens-default / response-basic / response-tool_use / outbound-tools-forward-to-anthropic-upstream).
- **9 route-level tests FAILED** — SEMUA dengan error IDENTIK:
  `TypeError: Client.__init__() got an unexpected keyword argument 'app'`
  di `starlette.testclient.TestClient(app=...)`. Penyebab: mismatch dep `httpx 0.28.1` vs `starlette 0.27.0` (FastAPI 0.99.1). `TestClient(app)` gagal saat **konstruksi**, sebelum logic route dieksekusi → test gak nge-touch logic be-dev sama sekali.

### 2b. `tests/backend/test_translator.py -v` (regresi)
- **17 passed, 0 failed** — 0 regression di modul translator (termasuk `_translate_request_anthropic` yang di-extend).

### 2c. Konfirmasi env-issue vs regression
```
pytest tests/backend/test_gateway.py::test_unknown_model_returns_model_not_found
→ FAILED, error SAMA PERSIS:
  TypeError: Client.__init__() got an unexpected keyword argument 'app'
```
Test ini **pre-existing** (bukan punya be-dev) → membuktikan failure murni env/dependency, **BUKAN regression** dari kode be-dev.
**Kesimpulan:** klaim be-dev terkonfirmasi = env issue pre-existing.

---

## 3. Principle Review (R25 — DRY/KISS/SOLID/YAGNI)

Baca diff `translator.py` (+445) + `router.py` (+230):

- **DRY ✅** — `_handle_anthropic_messages` reuse 1:1 `resolve_target`, `execute_combo`, `provider_adapter.chat_completion`, `_record_usage_safe`, `_record_request_log_safe`, `_route_via_endpoint`, `_apply_token_saver_for_endpoint` (gak ada duplikasi pipeline). Translator inbound = inverse pair dari outbound yg sudah ada. `_record_request_log_safe` dipakai bareng chat/responses.
- **KISS ✅** — mapping eksplisit & jelas; `count_tokens` pakai heuristic `len(utf8)//4` (no tokenizer, sesuai design §2.5/YAGNI).
- **SOLID ✅** — SRP: translator=translate, router=route; handler tipis. Open/Closed: perubahan additif (route baru + extend `_translate_request_anthropic` **additively** forward tools bila ada; behavior lama gak berubah).
- **YAGNI ✅** — gak ada fitur spekulatif. Streaming / extended-thinking / gemini-tools **ditolak / di-doc** sebagai future phase, gak dibangun.

**Observasi minor (BUKAN pelanggaran, gak blocking):** dua statement `import` ditaruh tengah-file di `translator.py` — `import uuid as _uuid` (sebelum `_derive_anthropic_id`) dan `from pydantic import BaseModel as _BaseModel` (sebelum `class AnthropicMessagesRequest`), pakai `# noqa: E402`. Secara fungsional aman (Python izinkan import di module level posisi mana pun), tapi agak tak-lazim vs konvensi import di atas file. Saran: pindah ke blok import atas bila ada kesempatan. **Tidak dilaporkan sebagai bug** (R25 butuh pelanggaran nyata; ini cuma gaya).

**Tidak ada `/log-bug` diperlukan** — 0 pelanggaran DRY/KISS/SOLID/YAGNI.

---

## 4. R12 — Logging ke DB (LogEntry)

Jalur error/success di `messages_completions` (B5.6 wrapper) + `_handle_anthropic_messages`:
- **Error path:** `_record_request_log_safe(ctx, request, t0, error_envelope=exc.envelope, http_status=exc.status_code)` (GatewayError) dan `error_envelope=None, http_status=500, exc=exc` (Exception).
- **Success path:** `_record_request_log_safe(ctx, request, t0, result=result, http_status=200)`.
- **Translator** `log_warning`: stream refused, thinking refused, max_tokens-default injected.
- **Router** `log_warning`: missing model, invalid request (ValidationError), model not found (TargetNotFound); `log_info`: success + success-via-endpoint.
- Grep `except: pass` / `except ...: pass` di file baru → **0 ditemukan** (match cuma di docstring/comment). `_record_request_log_safe` fail-open + log ke `LogEntry` via `log_error_exc`.

**Status R12: LULUS.**

---

## 5. Smoke Logika (alur Anthropic → OpenAI → backend → Anthropic)

Verifikasi dari diff + 11 unit tests passed:

1. **model bare-resolve ✅** — `target = resolve_target(model)` (string payload dilewat apa adanya, mirip chat/responses); `TargetNotFound` → 400 `model_not_found`.
2. **non-streaming 400 ✅** — `anthropic_messages_request_to_openai_chat` raise `GatewayError(400, …, ANTHROPIC_STREAMING_UNSUPPORTED_CODE)` kalau `stream:true`.
3. **tools passthrough ✅** — `_anthropic_tools_to_openai_tools` → `[{type:"function",function:{name,description,parameters:input_schema}}]`; `_anthropic_tool_choice_to_openai` (auto→auto, none→none, any→required, tool→function). Outbound `_translate_request_anthropic` kini forward tools/tool_choice ke upstream anthropic (double-translation round-trip, §3).
4. **auth Bearer/x-api-key ✅ (by design)** — handler terbuka spt chat/responses (Decision 4.4); dua-duanya ditolerir, gak di-enforce. Header client `x-api-key` **gak** diteruskan ke upstream (aigate punya egress cred sendiri). Test `test_messages_authorization_bearer_also_accepted` + `test_messages_non_streaming_success` validasi keduanya → 200.
5. **response envelope ✅** — `openai_chat_response_to_anthropic_messages` → `{type:"message", role, model(echo request ref), content[text|tool_use], stop_reason, usage{input_tokens,output_tokens}}`. Unit test basic + tool_use passed.
6. **sibling routes ✅** — `/v1/messages/count_tokens` (heuristic, "hello world"=11 byte//4=2 token) + `/api/event_logging/batch` (202 stub). Logic sederhana & benar.
7. **double-translation anthropic upstream** — test `test_messages_real_adapter_anthropic_upstream` (respx) memvalidasi upstream dipanggil di `/v1/messages` dgn wire format Anthropic; logic benar, gak jalan gara2 env.

---

## 6. Kesimpulan

**LULUS** untuk implementasi Stage 1 inbound Anthropic `/v1/messages` di level:
- syntax (`py_compile` bersih + runtime import OK),
- principled design (DRY/KISS/SOLID/YAGNI — R25),
- R12 logging (semua jalur error/success → DB; gak ada `except: pass`),
- logika alur (diverifikasi via code-review + 11 unit tests passed + reuse pola `/v1/responses` yg sudah terbukti).

**BUG: 0.** Tidak ada pelanggaran prinsip, tidak ada regresi translator (17/17 passed).

⚠️ **Batas verifikasi (R20) — PENTING:**
- 9 route-level integration tests (`TestClient`) **GAGAL DIEKSEKUSI** di sandbox ini murni gara2 mismatch dependency pre-existing (`httpx 0.28.1` vs `starlette 0.27.0` / FastAPI 0.99.1) — **bukan** bug kode be-dev (terkonfirmasi sama persis di `test_gateway.py` pre-existing).
- Artinya: **saya TIDAK klaim "endpoint jalan end-to-end / aplikasi jalan"** cuma dari unit test. Jalur runtime route handler (HTTP envelope, B5.6 logging benar-benar nulis `RequestLog`, endpoint routing, adapter anthropic sungguhan) baru ter-cover penuh kalau env dependency diselaraskan, lalu test route-level dijalankan di env user.
- **Rekomendasi PM:** (a) selaraskan `httpx` di `pyproject.toml` ke versi kompatibel `starlette 0.27.0` (mis. `httpx<0.28`) agar seluruh suite gateway (lama+baru) bisa jalan — ini fix env, bukan kode fitur; (b) jalankan `pytest tests/backend/test_anthropic_messages.py tests/backend/test_translator.py` di env user yg dep-aligned; (c) opsional smoke `claude.sh` re-wire (design §7, TODO) untuk bukti e2e nyata per R20 sebelum tandai "aplikasi jalan".

---
*Laporan ini ditulis di `.opencode/reports/` (R23). Tidak ada file `src/**` atau `tests/backend/**` yang ditulis/diubah oleh QA.*
