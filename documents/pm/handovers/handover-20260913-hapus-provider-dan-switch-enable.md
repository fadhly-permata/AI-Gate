# Lembar Desain — Hapus nama provider di daftar anggota + switch enable/disable per model kombo

- Tanggal: 2026-09-13 · Penulis: ProjectManager (aturan **D6**: lembar desain + ACC user sebelum spawn).
- Status: **DI-ACC — user perintah eksplisit** ("hapus nama providernya di list model... redundan" + "butuh switch
  enable/disable model... yang di-disable tidak dipakai untuk fallback/round-robin/dll").
- Dasar: fitur urutan manual kombo (▲▼ + drag + animasi) & strategi `round_robin` sudah di-commit
  (`4c5d3fa` kode + `4fc0641` docs). Ini dua penambahan di atasnya.

## A. Hapus nama provider di tabel anggota kombo (frontend ONLY — fe-dev)

### Fakta yang diukur
- `renderMembers` (`combos.js:422`): kolom ke-1 = grip `js-mem-drag` + `pname` (nama provider, `:462-467`);
  ke-2 = `provider_model`; ke-3 = `weight`; ke-4 = `row-actions` (▲▼/edit/hapus). Jadi 4 kolom:
  `[grip+provider] [model] [weight] [aksi]`.
- Header tabel anggota kombo ada di `index.html` (modal edit kombo) — cari `<th>` bertulis Provider/Model/Weight.
- Baris kosong pakai `colspan="4"` (`combos.js:432`).

### Desain (default PM, user boleh veto)
- Hapus TEKS `pname` dari kolom ke-1 (grip tetap di situ). Hapus/relabel `<th>` Provider di header agar cocok.
- JUMLAH kolOM TETAP 4 (grip tetap menempati kolom ke-1) → `colspan="4"` baris kosong TIDAK berubah.
- **Asumsi PM:** yang dimaksud "list model" = tabel anggota kombo (bukan dropdown pilih model saat tambah
  anggota). Kalau maksudmu dropdown pemilih model, bilang — gua arahkan ke sana.

### DoD (fe-dev)
- `node node_modules/.bin/vitest run` tetap HIJAU; header & tiap baris sinkron (kolom sejajar); nol hex baru;
  `git status --short` hanya `src/frontend/**`.

## B. Switch enable/disable per model (backend be-dev + frontend fe-dev)

### Fakta yang diukur (PENTING — beda dari enabled level kombo)
- `ComboMember` model (`models.py:206-218`): `id, combo_id, provider_id, provider_model, priority, weight`.
  **BELUM punya `enabled`.**
- Yang SUDAH ada: `enabled` level **KOMBO UTUH** (`combos_router.py:53` di `ComboCreate`, `:122` di DTO load,
  `:238-239` di update) — itu on/off SELURUH kombo (tampil di tabel kombo `index.html:501`). Bukan per-model.
- `ComboMemberCreate` (`:40`), `ComboMemberUpdate` (`:69`), `ComboMemberDTO` (`:79`) — **BELUM bawa
  `enabled` member**.
- `build_candidates` (`combo_routing.py:150`): `session.query(ComboMember).filter_by(combo_id=combo.id).all()`
  TANPA filter enabled.

### Desain (default PM)
1. **Model:** tambah `ComboMember.enabled` (`Boolean, default=True`) + **migrasi idempoten** (cek PRAGMA dulu,
   ADD COLUMN; mirip `_ensure_combo_last_used_index_column` yang barusan dibuat be-dev di `config/db.py:280`,
   dipanggil di `init_db` `:331`).
2. **Routing:** `build_candidates` filter `enabled=True` (di query `:150`) → member dinonaktifkan di-skip di
   **SEMUA** strategi (fallback / load_balance / latency_cost / three_tier / round_robin). Persis maksud user:
   "tidak dipakai untuk fallback/round-robin/dan lain sebagainya".
3. **API:** `ComboMemberDTO` tambah `enabled`; `ComboMemberCreate` + `ComboMemberUpdate` tambah `enabled`
   (Optional, default True); load (`:110`) isi `enabled=bool(member.enabled)`; `create_member` (`:275`) set;
   update member (cari di `combos_router.py` / endpoint `combo_routing.py:~321`) TERIMA `enabled` via partial
   PUT (`exclude_unset` sudah ada di backend akun — pakai pola sama).
4. **Frontend (fe-dev):** toggle enable/disable per baris. Member tersimpan → `PUT {enabled}`; member buffer →
   lokal. Baris dinonaktifkan tampil **greyed** tapi TETAP ada (bisa di-enable lagi). `weight` / ▲▼ tetap jalan.
   Toggle butuh `aria-label` — pakai/tambah kunci i18n `combos.member.enabled` (EN "Enabled") di 7 kamus bila perlu.

### DoD (backend be-dev)
- Tes backend baru: member `enabled=False` di-skip di semua strategi; `enabled` default True untuk member lama/baru;
  update `enabled` tersimpan & kebaca di DTO; migrasi idempoten (2x jalan aman). `pytest tests/backend` HIJAU
  (baseline 547 passed/1 skip).
- `git diff --check` bersih; scope `src/backend/**` + `tests/backend/**`.

### DoD (frontend fe-dev)
- Toggle muncul tiap baris; `PUT {enabled}` jalan; baris disabled greyed; vitest HIJAU; parity i18n (bila tambah
  kunci); `git status --short` hanya `src/frontend/**`.

## C. Yang TIDAK diubah
- `enabled` level kombo utuh tetap ada & jalan. Strategi kombo tetap. ▲▼ / drag / animasi tetap.
- Logika reorder tidak dirombak.

## D. Risiko jujur
1. Kalau satu kombo berisi provider BEDA dengan model sama, hapus nama provider bikin baris jadi ambigu.
   Asumsi user: redundan = aman (kombo biasanya 1 provider / model sudah cukup jelas). Kalau tidak, bilang.
2. Toggle WAJIB persist ke server (backend), bukan cuma CSS/disabled sementara — supaya routing benar-benar skip.
3. Uji mata HP tetap milik user (G3 + J6).
