# Handover PM → be-dev: fix RequestLog kolom Model kosong (combo path) + endpoint_name di DTO

## Goal
Entri baru di tabel Request Log halaman Logging harus punya kolom **Model terisi**
(buat SEMUA jalur: provider ref, combo ref, endpoint, streaming), dan API
`GET /api/request-logs` harus menyertakan **endpoint_name** supaya FE bisa
menampilkan nama endpoint, bukan id mentah.

## Root cause (sudah diverifikasi PM — evidence)
1. **Model kosong untuk request combo:**
   - `src/backend/gateway/resolver.py:172-178` — untuk ref `combo:<name>` resolver
     balikin `ResolvedTarget(upstream_model="", combo_used=True)` (marker; member
     asli baru diputuskan di dalam `execute_combo`).
   - `src/backend/gateway/router.py:272` (chat) & `:449` (responses): UNCONDITIONAL
     `ctx["model"] = target.upstream_model` → nimpa model ref asli dengan `""`.
   - Bukti DB (`~/.aigate/aigate.db`, tabel `request_logs`): baris ts 21:28–21:29
     punya `model=''`, padahal body request-nya `"model": "combo:B.AI"`.
     Provider-path (model ref `glm-5.3-flash`) terisi normal.
   - Situs ketiga: `router.py:1017` `ctx["model"] = target.upstream_model` di
     `_route_via_endpoint` (provider binding) — cek juga jalur endpoint yang bind
     combo (sekitar line 1040–1067, `execute_combo` di 1067) dan jalur streaming
     combo (`router.py:280-302`, member di-resolve via
     `combo_routing.resolve_combo_stream_target` → punya `upstream_model` real).
2. **Endpoint kosong** = by-design (model-based path tanpa header
   `X-Aigate-Endpoint` → `endpoint_id=NULL`; lihat komentar `models.py:313-315`).
   Bukan bug BE. Tugas BE cuma: DTO harus ikut bawa **nama** endpoint saat ada.

## Kontrak yang PM tetapkan (source of truth — FE akan dibangun di atas ini)
- `RequestLog.model` (kolom & DTO) untuk entri baru:
  - Provider ref / bare model: **upstream_model** (perilaku sekarang, jangan ubah —
    test `test_request_log.py` line 129 mengunci ini).
  - Combo ref non-streaming sukses: prefer **model member yang benar-benar melayani**
    (ambil dari envelope upstream `result.get("model")` bila non-empty str), fallback
    ke model ref combo (mis. `combo:B.AI`) bila envelope tak punya field `model`.
  - Combo ref streaming: **upstream_model member** yang di-resolve
    (`resolve_combo_stream_target`).
  - Error path apa pun (GatewayError sebelum resolve sukses): model ref yang diminta
    klien (jangan sampai `""`).
- `RequestLogDTO` (`src/backend/analytics_router.py`): tambah field
  **`endpoint_name: Optional[str]`** — dari relasi `row.endpoint.name` saat
  `endpoint_id` terisi, `None` kalau tidak. Populate di dalam session yang sama
  (`_row_to_dto` dipanggil di dalam `with SessionLocal()` — aman lazy-load).
- DTO contract doc di docstring module `analytics_router.py` ikut di-update.

## Scope (STRICT)
- WRITE: `src/backend/**`, `tests/backend/**` saja.
- READ: `documents/**`, `tests/**`, `src/frontend/**` (baca saja, JANGAN ubah).
- DILARANG: menulis `documents/pm/**` (PM yang update), file FE, kill/restart
  proses aigate (R32 — sesi opencode hidup di dalamnya), edit `~/.aigate/aigate.db`.

## Definition of done
1. Semua situs overwrite `ctx["model"]` (272, 449, 1017 + jalur combo-bound endpoint
   & streaming combo) tidak lagi menghasilkan `""` — ikuti kontrak di atas.
2. `RequestLogDTO` + `GET /api/request-logs` mengembalikan `endpoint_name`.
3. Test baru di `tests/backend/test_request_log.py`:
   - combo request (member sukses) → `RequestLog.model` terisi (bukan `''`);
   - combo streaming path → model terisi;
   - request via `X-Aigate-Endpoint` → `endpoint_name` benar di response API;
   - regresi provider path tetap `upstream_model`.
4. `python -m pytest tests/backend` HIJAU semua (baseline sekarang: 65 passed /
   1 skipped — skip itu test native PTY, bukan regksi).
5. Pydantic **v1** saja (R10); tanpa dependency baru.

## Receipt yang diharapkan
Daftar file berubah + alasan per situs, hasil pytest (angka), keputusan teknis,
open questions.
