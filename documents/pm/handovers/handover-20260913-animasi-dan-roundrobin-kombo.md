# Lembar Desain — Animasi Reorder + Strategi Round-Robin Kombo

- Tanggal: 2026-09-13 · Penulis: ProjectManager (aturan **D6**: lembar desain + ACC user sebelum spawn).
- Status: **DI-ACC — user minta dua-duanya** ("kasih animasinya buat perpindahan naik turunnya" + "tambahin fitur round robin").
- Dasar: fitur urutan manual kombo sudah jadi & di-commit (`00e2d08`) — tombol ▲▼ + handle drag, kolom Priority dihapus,
  posisi baris = priority. Lembar ini menambah (A) animasi pada perpindahan, dan (B) strategi `round_robin` baru.

## A. Animasi perpindahan naik/turun (frontend ONLY — fe-dev)

### Fakta
- `renderMembers` (`combos.js:393`) menulis ulang `comboMembersBody.innerHTML` setiap mutasi → baris diganti,
  bukan dipindah. Maka transisi CSS biasa pada posisi TIDAK otomatis jalan; butuh teknik eksplisit.
- Dua jalur yang memindah baris: `moveMember` (▲▼, `combos.js:475`) dan `reorderMembers` (drag, `:558`).

### Desain (default PM, user boleh veto)
- Tambahkan animasi RINGAN saat satu baris pindah: setelah `moveMember`/`reorderMembers` memindah, beri baris yang
  berpindah efek transisi singkat (mis. `transform` slide / `opacity` / highlight warna seketika lalu pudar).
  Teknik bebas (FLIP atau kelas transien) asal: (1) nol layout-thrash berat, (2) nol ganggu logika reorder,
  (3) **hormati `prefers-reduced-motion`** (matikan animasi kalau user minta gerak minimal).
- Handle drag juga dapat umpan balik visual minimal (sudah ada `cursor:grabbing` di `.js-mem-drag`).
- Nol warna hex baru; pakai token existing. Nol sentuh `src/backend/**`.

### DoD (fe-dev)
- `node node_modules/.bin/vitest run` tetap HIJAU (baseline 26 berkas / 656 tes + tes animasi bila perlu, nol merah).
- Animasi terlihat saat ▲▼ DAN saat drag-drop (verifikasi mata user tetap milik user / G3).
- `git diff --check` bersih; scope murni `src/frontend/**`.

## B. Strategi round-robin kombo (backend be-dev + frontend fe-dev)

### Fakta yang diukur
- Kombo strategi sekarang (`combo_routing.py:151` + `index.html:1104-1107`): `fallback | load_balance | latency_cost | three_tier`.
  `round_robin` BELUM ada di kombo. `select_member` (`combo_routing.py:225`) hanya tangani `load_balance` (weighted random)
  + `latency_cost` (lowest weight); sisanya jatuh ke `candidates[0]` (`:270-272`).
- Round-robin SUDAH ada di tempat lain & pakai **penunjuk urutan tersimpan**: `ProxyPool.last_used_index`
  (`models.py:158`, `rotation_strategy` `:154`); akun provider pakai `last_used_at` LRU (`models.py:98-124`, `oauth.py:315`).
- `Combo` model (`models.py:186-193`) PUNYA `strategy` tapi BELUM punya kolom penunjuk urutan.
- `ComboMember` (`models.py:206-218`): `priority` (default 0) + `weight` (default 1.0).

### Desain (default PM — log ini, user boleh veto)
1. **Semantik:** `round_robin` = bagikan request SATU-PER-SATU ke anggota menurut **urutan baris (priority naik)**,
   berputar (wrap-around). **Bagi rata** — `weight` DIABAIKAN untuk pemilihan (beda dari `load_balance` yang weighted-random).
2. **State penunjuk:** tambah kolom `last_used_index` (Integer, default 0) ke tabel kombo, MIRIP `ProxyPool.last_used_index`.
   Via migrasi **idempoten** (cek dulu ada/tidak, jangan drop tabel). be-dev baca pola migrasi repo yang sudah ada.
3. **Seleksi:** di `combo_routing.py`, tambah cabang `round_robin` — pilih `candidates[cursor]`, lalu
   `cursor = (cursor+1) % n` dan simpan ke `combo.last_used_index` (flush lewat session yang sudah ada).
   Kandidat tetap diurut priority naik (pakai `build_candidates` sama seperti `fallback`); round-robin cuma
   mengganti CARA memilih, bukan susunan.
4. **Error:** **satu percobaan, tanpa retry dalam request yang sama** — konsisten dengan kontrak `load_balance`/
   `latency_cost` ("Single attempt, no retry", `combo_routing.py:237,296`). Cursor TETAP maju walau gagal, supaya
   request berikutnya tidak mengulang anggota yang barusan error. (Bukan fallback berantai.)
5. **Validasi:** terima `round_robin` di router kombo (tempat `strategy` divalidasi); unknown strategy tetap
   fallback aman.

### UI (fe-dev, SETELAH backend beres)
- Tambah `<option value="round_robin" data-i18n="combos.strategy.round_robin">` ke `#comboStrategy`
  (`index.html:1103-1107`).
- Kunci i18n `combos.strategy.round_robin` ke 7 kamus (EN "Round robin"; ID ikut "Round robin" — jangan terjemahkan
  istilah, aturan I8). `strategyLabel` (`combos.js:146`) sudah fallback ke raw value kalau kunci kurang.
- Nol hex baru; scope murni `src/frontend/**`.

### DoD (backend be-dev)
- Tes backend: distribusi round-robin berputar rata menurut priority, cursor tersimpan & maju tiap request,
  weight diabaikan, single-attempt (no retry), unknown strategy → fallback. Jalur yang sama (`pytest tests/backend`).
- Migrasi idempoten; `python -m pytest tests/backend -q` tetap HIJAU (baseline 526 passed/1 skip).

### DoD (frontend fe-dev)
- Opsi `round_robin` muncul di selector + 7 kamus parity LOJONG (`i18n.test.js`); vitest tetap HIJAU.
- `git status --short` hanya `src/frontend/**`.

## C. Yang TIDAK diubah
- `fallback / load_balance / latency_cost / three_tier` tetap jalan seperti sekarang.
- Akun provider / proxy pool tidak disentuh (sudah punya round-robin sendiri).
- Logika reorder ▲▼/drag tidak dirombak, hanya ditambah animasi.

## D. Risiko jujur
1. Animasi bisa bentrok dengan render ulang `innerHTML` → fe-dev wajib uji tidak ada flicker/duplikat baris.
2. Round-robin butuh tulis ke DB tiap request (cursor) → be-dev cek apakah session flush per-request aman
   (mirip ProxyPool). Kalau ada race antar-request, catat, jangan sembunyikan.
3. Uji mata HP tetap milik user (G3 + J6) — PM tidak bisa pastikan tampilan animasi sebelum user lihat.
