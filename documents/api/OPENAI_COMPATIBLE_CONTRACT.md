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

## Streaming
`stream: true` -> Server-Sent Events `data: {json}\n\n` selesai dengan
`data: [DONE]`.
