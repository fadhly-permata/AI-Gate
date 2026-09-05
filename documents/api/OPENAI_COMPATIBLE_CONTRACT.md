# API Contract — OpenAI-Compatible Gateway (aigate)

Base URL: `http://localhost:8080/v1` (dapat diubah di config).
Kontrak mengikuti format OpenAI agar tool eksternal (CLI agentic) bisa pakai
langsung. Merujuk PRD §2.4, FSD §2.4, TSD (gateway design), dan ADR-008
(proxy binding di level Endpoint, Endpoint -> Combo).

## Authentication
- Opsional access control via internal API key.
- Header: `Authorization: Bearer <INTERNAL_API_KEY>` (key disimpan di file
  biasa tanpa enkripsi — ADR-007).
- Jika tidak di-set, gateway tetap melayani (mode lokal terbuka).

## POST /v1/chat/completions
Request (OpenAI-compatible):
```json
{
  "model": "combo:default | provider:model",
  "messages": [{"role": "user", "content": "halo"}],
  "stream": false,
  "temperature": 0.7,
  "max_tokens": 1024
}
```
Response:
```json
{
  "id": "chatcmpl-xxx",
  "object": "chat.completion",
  "model": "combo:default",
  "choices": [{"index": 0, "message": {"role": "assistant", "content": "..."},
               "finish_reason": "stop"}],
  "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
}
```
- `model` menunjuk ke Combo atau Provider/Model. Routing mengikuti strategi
  Combo (fallback / load-balance / latency-cost).
- Bila di-bound ke Endpoint dengan proxy pool (ADR-008), request keluar lewat
  proxy tersebut.

## GET /v1/models
Response:
```json
{
  "object": "list",
  "data": [
    {"id": "combo:default", "object": "model", "owned_by": "aigate"},
    {"id": "openai:gpt-4o", "object": "model", "owned_by": "openai"}
  ]
}
```
Daftar diambil dari Provider yang mendukung auto-discovery (`/models`) + Combo.

## Error format
```json
{"error": {"message": "proxy pool unreachable", "type": "upstream_error",
           "code": "proxy_503"}}
```
HTTP status: 400 (bad request), 401 (auth), 502/503 (upstream/proxy).

## GET /api/logs
Mengambil log operasional dari tabel `LogEntry` (mode developer / observabilitas).
- Query: `?severity=info,warning,error` (filter, default semua), `?limit=100`, `?since=<iso8601>`.
- Response:
```json
{ "object": "list", "data": [
  {"id": 1, "timestamp": "2026-09-03T06:00:00", "severity": "error",
   "source": "backend.gateway", "message": "upstream 502", "stacktrace": "..."}
] }
```
- `POST /api/logs` (frontend → backend): body
  `{"severity":"error","source":"frontend:app","message":"...","stacktrace":"..."}`
  → simpan ke `LogEntry`.
- Akses log diutamakan saat `AIGATE_DEV=1`; di luar dev mode dapat dibatasi.

## Streaming
`stream: true` -> Server-Sent Events `data: {json}\n\n` selesai dengan
`data: [DONE]`.

## Management Endpoints (adopsi 9router)

> Penerjemah format (PRD §2.4) bersifat **internal/transparan** — tidak ada
> endpoint baru; client tetap kirim/terima format OpenAI, aigate menerjemahkan
> ke provider target di belakang layar.

### Multi-Account & OAuth (PRD §2.1)
- `GET /api/accounts?provider_id=` — daftar akun per provider.
- `POST /api/accounts` — tambah akun (api_key / oauth token). Body:
  `{"provider_id": 1, "label": "acc-1", "auth_type": "api_key|oauth", "api_key": "..."}`.
- `POST /api/oauth/<provider>/start` — mulai flow OAuth; kembalikan URL authorize.
- `GET /api/oauth/<provider>/callback` — tukar code → simpan token + `expires_at`;
  refresh otomatis sebelum kedaluwarsa (lihat TSD ADR-013).
- `DELETE /api/accounts/<id>` — hapus akun.

### Quota & Usage (PRD §2.4.2 / §2.4.3)
- `GET /api/usage?provider_id=&range=day` — ringkasan token in/out, estimasi
  biaya, tren. `GET /api/quota` — sisa kuota & reset countdown per provider
  berlangganan.

### Export / Import Setting (PRD §2.4.4 — lokal, tanpa cloud)
- `GET /api/settings/export` — kembalikan seluruh setting (provider, combo,
  akun, proxy, endpoint, preferensi) sebagai JSON.
- `POST /api/settings/import` — body = JSON dari export; pulihkan setting.
  Rute ini lokal; tidak ada pengiriman ke pihak ketiga.

### Token Saver toggle (PRD §2.4.1)
- Field `token_saver` (enum: `off | rtk | caveman | ponytail`) di config
  Endpoint — diterapkan sebagai pre-translate hook (lihat TSD ADR-013).

### Chat Playground (PRD §2.9 — reuse gateway, ADR-014)
- `GET /api/chat/sessions` — daftar sesi. `POST /api/chat/sessions`
  body `{title?, provider_id?, combo_id?, model, system_prompt?, temperature?}` → sesi.
- `GET /api/chat/sessions/{id}` · `PUT /api/chat/sessions/{id}` (title/system_prompt/
  temperature/model) · `DELETE /api/chat/sessions/{id}`.
- `GET /api/chat/sessions/{id}/messages` — riwayat pesan (`{role, content, created_at}`).
- `POST /api/chat/sessions/{id}/complete` — body `{content}` (pesan user baru).
  Server simpan pesan user, rakit `messages` (system + riwayat + baru), teruskan ke
  gateway `/v1/chat/completions` ke provider/combo sesi, **stream balik SSE**; saat
  selesai simpan `ChatMessage(role=assistant)`. Client tetap format OpenAI.
