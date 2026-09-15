# Handover — B8.B6.1 Backend Chat Playground (be-dev)

Tanggal: 2026-09-16 | Owner: **be-dev** | PM: ProjectManager
Spesifikasi sumber: `documents/PRD.md` §2.9 + `documents/analysis/ERD.md` §ChatSession/ChatMessage (baris 364–384). TIDAK ada lembar desain terpisah (PM bangun langsung dari PRD+ERD, D2).

## PENTING — koreksi asumsi
Lembar desain lama yang disebut di catatan (`...desain-chat-playground-fase6.md`) TIDAK PERNAH ada. Acuan resmi = PRD §2.9 + ERD. Jangan cari file desain itu.

## Tujuan (definition of done)
Backend untuk Chat Playground: entitas + CRUD sesi/pesan + endpoint percakapan **streaming (SSE)** yang memakai pipeline gateway yang SUDAH ada (penerjemah format + token saver + kuota + usage logging jalan transparan). FE (B6.2/6.3) akan membangun di atas kontrak endpoint ini, jadi kontrak WAJIB stabil & terdokumentasi.

## Realita kode yang sudah PM verifikasi (bukan karangan)
- Models: satu file `src/backend/models.py`, `Base` + `SessionLocal` dari `backend.config.db`. Contoh gaya: `class Provider(Base)` dengan `Mapped[...]`/`mapped_column`.
- DB bootstrap: `init_db()` (`config/db.py:370`) panggil `Base.metadata.create_all(engine)` → **tabel BARU dibuat otomatis**. Fungsi `_ensure_*` HANYA untuk menambah kolom ke tabel LAMA. ChatSession/ChatMessage = tabel baru → **create_all cukup, TIDAK perlu `_ensure_`**. Pastikan `from backend import models` mendaftarkan pemetaan (sudah dilakukan init_db).
- Router: tiap router menaruh PATH LENGKAP di decorator (tanpa prefix), mis. `usage_router.py:108 @router.get("/api/usage")`. Daftar ke app di `server.py` (`app.include_router(...)` baris ~105–134).
- Gaya error: pola `_error(status, message, code, etype="invalid_request_error")` → `JSONResponse` (lihat `usage_router.py:63`). Ikuti format ini.
- Gateway streaming SUDAH ADA: `gateway/router.py:146 @router.post("/v1/chat/completions")` → `chat_completions(request)`. Untuk `stream:true` balikin `StreamingResponse` (`text/event-stream`); resolve via `gateway/resolver.py` `resolve_target` / `resolve_combo_stream_target` yang sudah paham ref model `provider:<...>` dan `combo:<...>`. Endpoint chat WAJIB pakai ulang pipeline ini, BUKAN bikin mesin LLM baru.

## Kontrak API yang harus dibuat (`/api/chat/...`)
1. `GET  /api/chat/sessions` → daftar sesi, urut `updated_at` desc. Item: `{id,title,model,provider_id,combo_id,updated_at}`.
2. `POST /api/chat/sessions` body `{title?, provider_id?, combo_id?, model?, system_prompt?, temperature?}` → buat sesi; kembalikan sesi penuh. Auto-title boleh diisi belakangan (FE), tapi terima bila dikirim.
3. `GET  /api/chat/sessions/{id}` → `{...session, messages:[{id,role,content,tokens_in,tokens_out,created_at} ...]}` kronologis asc.
4. `PUT  /api/chat/sessions/{id}` → update `{title?, system_prompt?, temperature?}` (rename + parameter). Kembalikan sesi.
5. `DELETE /api/chat/sessions/{id}` → hapus sesi + pesan terkait (cascade).
6. `POST /api/chat/sessions/{id}/complete` body `{content}` (pesan user baru) → INTI fitur:
   - Simpan `ChatMessage(role="user", content)`.
   - Rakai history: `system_prompt` sesi (bila ada, role=system) + seluruh `ChatMessage` sesi urut cron + jangan dobel user yang barusan.
   - Bangun payload OpenAI: `model=session.model`, `messages=[...]`, `temperature=session.temperature` (bila ada), `stream=true`.
   - Teruskan ke pipeline gateway → kembalikan `StreamingResponse` SSE ke klien.
   - **Persist assistant**: bungkus generator SSE — saat stream selesai, rakit `content` assistant dari delta, simpan `ChatMessage(role="assistant", content, tokens_in?, tokens_out?)`. Ambil token dari frame usage SSE terakhir bila ada, kalau tidak → `None` (jangan mengarang angka).
   - Tangani error: bila pipeline balikin non-stream (JSONResponse error), propagate dengan jujur (SSE error frame atau status sesuai), dan JANGAN simpan assistant kosong.

## Cara WAJIB pakai gateway (hindari loopback HTTP ke server jalan)
JANGAN memanggil `http://localhost:8080/v1/chat/completions` lewat HTTP (itu sentuh instance server yang lagi jalan → rawan, dan melanggar J6 spirit). Sebaiknya: **refactor minimal** `gateway/router.py` — ekstrak badan `chat_completions` jadi fungsi internal reusable, mis. `async def _run_chat(payload: dict) -> Union[dict, StreamingResponse]`, lalu route `@router.post("/v1/chat/completions")` MEMANGGIL helper itu. `chat_router` mengimpor & memanggil helper yang sama secara langsung. Kontrak eksternal `/v1/chat/completions` TIDAK boleh berubah (sudah dipakai Terminal/CLI/e2e). Kalau ekstrak helper dirasa menyentuh terlalu banyak, alternatif: panggil `resolve_target`/`provider_adapter` langsung — TAPI utamakan reuse `chat_completions` biar token saver/kuota/usage/logging ikut kewarisi persis.

## Batas berkas (STRICT)
- WRITE: `src/backend/chat_router.py` (baru), `src/backend/models.py` (tambah ChatSession+ChatMessage+relationship), `src/backend/server.py` (include_router + import), `src/backend/gateway/router.py` (HANYA refactor ekstrak helper internal, nol perubahan kontrak), `tests/backend/test_chat_router.py` (baru).
- READ: `src/backend/**`, `documents/PRD.md`, `documents/analysis/ERD.md`, `documents/pm/**`.
- DILARANG: ubah frontend, ubah kontrak `/v1/*` eksternal, menambah dependensi baru, menyentuh DB produksi user (`~/.aigate/aigate.db`), kill/restart server (J6).

## Test (pytest, DB terisolasi)
- Pakai `AIGATE_DB_PATH` ke file tmp + `TestClient` (bukan server user). 
- Cover: CRUD sesi; cascade delete; `/complete` dengan `resolve_target`/adapter/stream **di-mock** supaya tak memanggil provider sungguhan → verifikasi user msg tersimpan, SSE chunk diteruskan, assistant msg tersimpan dengan content gabungan, tokens terisi dari usage mock (dan `None` saat tak ada usage).
- Verifikasi `init_db()` membuat 2 tabel baru idempoten (run dua kali aman).
- Jalankan SUITE backend yang ada biar NOL regresi (mis. `python -m pytest tests/backend -q`); laporkan angkanya.

## Receipt yang diminta
File berubah + alasan; potongan kontrak akhir (route + skema request/response) untuk diteruskan ke fe-dev; hasil pytest; keputusan soal cara reuse gateway; open question. JANGAN commit/push (PM yang merge).
