# Lembar Desain — `round_robin` diabaikan di jalur streaming (bug)

- Tanggal: 2026-09-13 · Penulis: ProjectManager (diagnosis) · Eksekusi: be-dev (backend-only).
- Laporan user: combo "B.AI" pakai strategi `round_robin`, 4 anggota (2 disabled → 2 enabled),
  tapi di "usage & quota" cuma model **Hy3** yang kepakai. Tes lewat UI (streaming).
- Status: bug, user minta benerin. (Bug fix, bukan fitur baru — pakai spec ini sebagai kontrak.)

## Akar masalah (terbukti dari kode)
- Jalur NON-streaming (`execute_combo` → `select_member`, `combo_routing.py:286-305`) memang muter
  via cursor `combo.last_used_index` + `session.commit()`. Benar.
- Jalur STREAMING (`gateway/router.py:316-341`): bila `payload["stream"] is True` dan target kombo,
  panggil `resolve_combo_stream_target(combo_name)` (`combo_routing.py:525`).
- `resolve_combo_stream_target` mengembalikan **kandidat OpenAI-format PERTAMA** dan **mengabaikan
  cursor round_robin sama sekali** (loop `for target in candidates: if openai: return target`).
  Maka streaming SELALU pakai `candidates[0]` = Hy3 (priority 0). UI ngobrol pakai SSE streaming →
  makanya cuma Hy3 yang muncul di usage/quota.
- Kolom `last_used_index` valid (`models.py:198`, migrasi `config/db.py:280`), jadi non-streaming jalan.

## Desain perbaikan (backend-only — be-dev)
File: `src/backend/combo_routing.py`, fungsi `resolve_combo_stream_target` (~525).

Restrukturisasi agar cursor round_robin dipakai JUGA di streaming. Kunci: pemilihan harus
BERADA di dalam `with SessionLocal() as session:` karena `select_member` perlu commit cursor.

```python
def resolve_combo_stream_target(combo_ref):
    with SessionLocal() as session:
        # ... load combo (sudah ada) ...
        candidates = build_candidates(combo, session)
        if not candidates:
            raise UpstreamError(502, {...combo_no_members...})
        strategy = (combo.strategy or "fallback").lower()
        openai_candidates = [c for c in candidates
                             if (c.format or "openai").lower() == "openai"]
        if not openai_candidates:
            return None  # caller angkat 400 (tetap sama)
        if strategy == "round_robin":
            # putar antar anggota streamable; select_member advances + commit cursor
            return select_member("round_robin", openai_candidates, session, combo=combo)
        # fallback / three_tier / lainnya: kandidat OpenAI pertama (perilaku lama)
        return openai_candidates[0]
```
- `select_member` SUDAH diimpor di `combo_routing.py`; tidak perlu import baru.
- Pemilihan dilakukan di dalam `with session` (biar cursor ke-commit). Objek `ResolvedTarget`
  dikembalikan setelah itu — aman (bukan terikat DB).
- Untuk kombo yang semua anggotanya OpenAI (kasus user), rotasi streaming == rotasi non-streaming.
- Catatan batas: kombo campuran format (OpenAI + Anthropic) → streaming round_robin cuma muter
  anggota OpenAI; cursor dipakai bersama jalur non-streaming (list penuh) sehingga bisa desync di
  kasus langka itu. DITERIMA (batasan diketahui); kombo user semua OpenAI → benar.

## Yang tidak diubah
- Skema DB tidak berubah (pakai `last_used_index` yang ada). Frontend tidak disentuh.
- Jalur non-streaming (`execute_combo`) tetap benar — jangan ubah.

## Tes (be-dev)
Tambah/perluas di `tests/backend/` (mis. `test_combo_tiers.py` atau file kombo routing):
- Kombo `round_robin` dengan 2 anggota enabled berformat OpenAI: dua pemanggilan berturut-turut
  `resolve_combo_stream_target` mengembalikan `upstream_model` BEDA (rotasi), dan
  `combo.last_used_index` naik (0→1→0).
- Kombo `fallback`/`three_tier` tetap mengembalikan kandidat OpenAI pertama (regresi tidak lolos).
- Jalankan `python -m pytest tests/backend -q` → HIJAU (baseline ~553 passed / 1 skipped).

## DoD (be-dev)
- `python -m pytest tests/backend -q` HIJAU; tes rotasi streaming ada & lolos.
- `git diff --check` bersih; `git status --short` hanya `src/backend/**` (+ test).
- nol perubahan skema; nol file frontend; perilaku non-streaming tidak berubah.
