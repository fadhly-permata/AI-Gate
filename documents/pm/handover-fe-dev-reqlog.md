# Handover PM → fe-dev: render Request Log — nama endpoint + fallback kolom kosong

## Goal
Tabel Request Log (halaman Logging) menampilkan kolom **Model** dan **Endpoint**
yang informatif untuk SEMUA baris: endpoint = nama (bukan id mentah), dan baris
lama/edge case tidak lagi tampak sel kosong.

## Context — kontrak baru dari be-dev (SUDAH diimplement + tested, jangan diubah)
`GET /api/request-logs` DTO sekarang:
```json
{"id":1,"endpoint_id":12,"endpoint_name":"ep-api","model":"gpt-4o",
 "ts":"...","duration_ms":1234,"request":"...","response":"..."}
```
- `endpoint_name` = `Endpoint.name` bila baris dirouting via endpoint; **`null`**
  untuk request model-based (by-design — tidak ada endpoint yang terlibat).
- `model` untuk entri BARU selalu terisi (member upstream / combo ref).
  Entri LAMA di DB masih bisa `model: ""` (data retroaktif, tidak di-backfill).

## Tempat kerja (root cause tampilan)
- `src/frontend/static/analytics.js:300-337` `renderRequestLogs()`:
  - Kolom Endpoint sekarang render `escapeHtml(r.endpoint_id)` mentah
    (null → kosong; terisi → angka id, bukan nama).
  - Kolom Model render `escapeHtml(r.model)` (baris lama `""` → kosong).
- Fix yang diminta:
  1. Endpoint: tampilkan `r.endpoint_name`, fallback `r.endpoint_id` (kalau nama
     null tapi id ada — jaga kompatibilitas respons lama), fallback terakhir
     tanda strip "—" untuk null (jangan biarkan sel kosong).
  2. Model: fallback "—" bila `r.model` kosong/undefined.
  3. Tetap pakai `escapeHtml` di SEMUA value (jangan introduce XSS).
- Test: `src/frontend/tests/analytics.test.js` — fixture payload
  (`REQLOG_PAYLOAD`) harus ikut bentuk DTO baru (ada `endpoint_name`), + test:
  nama endpoint tampil, fallback ke id, "—" saat null, "—" saat model kosong.
- i18n: cek dulu apakah "—" cukup literal (ya, karakter netral) — TIDAK perlu
  key baru kecuali memang sudah ada pola placeholder di `i18n.js`; ikuti pola
  file lokal yang ada. JANGAN pakai string gabungan bilingual (R: i18n policy).

## Scope (STRICT)
- WRITE: `src/frontend/**` saja (utamanya `analytics.js` + `tests/analytics.test.js`).
- READ: `documents/**`, `src/backend/analytics_router.py` (kontrak), `src/shared/**`.
- DILARANG: menyentuh `src/backend/**`, `tests/backend/**`, `documents/pm/**`,
  kill/restart proses aigate (R32).

## Definition of done
1. `renderRequestLogs` menampilkan endpoint NAME bila ada; id bila nama absen;
   "—" bila keduanya absen; "—" untuk model kosong.
2. Vitest hijau: `node node_modules/.bin/vitest run src/frontend/tests/analytics.test.js`
   (shebang vitest rusak di Termux — WAJIB lewat `node node_modules/.bin/vitest`).
3. Suite frontend penuh hijau tanpa regresi (baseline 442 passed / 23 files).
4. Tidak ada perubahan di luar `src/frontend/**`.

## Receipt yang diharapkan
File berubah, ringkasan test (angka), keputusan, open questions.
