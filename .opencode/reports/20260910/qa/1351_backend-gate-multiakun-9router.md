# Laporan Tugas: Gerbang Backend — Strategi Multi-Akun Provider (adopsi 9router)

## Informasi Dasar
- Tanggal: 2026-09-10
- Jenis Tugas: build + verifikasi (gerbang sebelum tahap frontend)
- Waktu Mulai: 13:36
- Eksekutor: ProjectManager (peran be-dev dijalankan in-session; tool spawn Task tidak tersedia — dicatat jujur di `documents/pm/status.md`)
- Commit hasil: `03d9b6e` (fitur) dan `f986d51` (pembersihan merah pre-existing) di branch `refactor/ui`, BELUM di-push.

## Permintaan Pengguna
"Lanjut WIP strategi multi-akun 9router. Status: backend udah ditulis tapi belum di test — review diff a237414 lalu jalanin suite backend dulu, jangan ke fe-dev sebelum hijau."
Dengan instruksi rinci: checkpoint git awal; review diff kritis terhadap kontrak PM-kunci; jalankan suite backend dengan cara yang benar (jangan asumsikan); kalau merah delegasikan perbaikan ke be-dev sampai hijau; kalau hijau formalkan kontrak tahap-1 di satu receipt lalu berhenti minta ACC user sebelum fe-dev. Mode SEKUENSIAL (jangan paralelkan fe-dev).

## Rencana Pekerjaan
1. Checkpoint git awal (branch, status, keberadaan `a237414`).
2. Review diff `a237414` per file terhadap kontrak (8 titik defect yang diinstruksikan).
3. Tentukan cara tes yang benar (pyproject, rules) lalu jalankan suite backend.
4. isolated-kan kegagalan: regresi vs pre-existing (reproduksi di baseline lewat worktree).
5. Delegasi (peran be-dev): tulis tes mesin strategi + perbaiki defect; pisahkan commit perbaikan pre-existing.
6. Formalkan kontrak tahap-1 (dokumen ini = receipt), update Memory Bank, berhenti menunggu ACC.

## Realisasi Pekerjaan

### 1. Checkpoint git — LOLOS
- Branch `refactor/ui`; `git status` bersih; `a237414` ada di posisi #2 `git log --oneline -12`; `git show --stat a237414` = 8 file `src/backend/**`, +498/−50.

### 2. Review diff `a237414` — hasil per defect yang diinstruksikan
| # | Lokasi | Temuan | Severity | Status |
|---|--------|--------|----------|--------|
| a | — | Field/kolom kontrak LENGKAP & nama persis: `models.py:66,68,120,124` vs kontrak state.md | — | sesuai |
| b | `config/db.py:218-278` | Migrasi PRAGMA-guarded, additif, pola identik `db.py:64-157`; dipanggil di `init_db` (`db.py:298`); idempotensi dibuktikan tes (2× jalan, default mendarat di baris lama) | — | sesuai |
| c | `oauth.py:336-455` | Urutan resolusi: pin (`:378-419`) > strategi (`:421-444`) > legacy `provider.api_key` (`:371-372`, `:455`); kandidat gagal-token di-skip, semua gagal → legacy (backwards compatible) | — | sesuai |
| d | `oauth.py:315-333` | Sticky LRU BENAR: streak habis setelah `sticky_round_robin_limit` SELEKSI BERTURUT-TURUT lalu maju ke `last_used_at` terlama (NULL dulu, id asc); limit dibaca dari KOLOM via `clamp_sticky_limit` (`:275`), tidak di-hardcode; dibuktikan tes limit 1/2/3 | — | sesuai |
| e | `oauth.py:298-312` | `last_used_at` ditulis pada SETIAP seleksi sukses (termasuk pin & fill-first) + commit | — | sesuai |
| f | diff penuh | TIDAK ada perubahan Combo (`combos.js` tak tersentuh; `combo_routing.py` hanya order-by retry → selaras prioritas, sesuai) / discovery / frontend; 8 file semuanya `src/backend/**` | — | sesuai |
| g | `config/db.py`, SQL | Semua SQL = ORM atau `text()` konstan (DDL migrasi); tidak ada format string input pengguna → tidak ada injeksi SQL | — | sesuai |
| h1 | `oauth.py:405-407` (lama) | Variabel `account_id` ganda tak perlu di jalur pin | rendah | DIPERBAIKI (`:419` return langsung) |
| h2 | `oauth.py` (lama) | Kontrak "skip yang unavailable" BELUM menangkap kredensial KOSONG: akun `api_key=""` lolos sebagai kredensial sah lalu diteruskan mentah ke upstream | SEDANG (defect nyata terhadap kontrak) | DIPERBAIKI + dites (kasus pin `:404-416`, kasus strategi `:442-456`) |
| i1 | `oauth.py` | Catatan desain diterima (bukan defect): counter streak in-memory (setara cursor lama; restart turunkan urutan dari `last_used_at`) — sesuai kontrak; `datetime.utcnow()` konsisten kodebase; `PUT /api/accounts/{id}` = tambahan di luar teks kontrak eksplisit tetapi diperlukan agar `priority` bisa ditulis (YAGNI lolos) | info | diterima, didokumentasikan |

### 3. Cara tes yang benar — diverifikasi, bukan diasumsikan
- `pyproject.toml:49-54`: `[tool.pytest.ini_options]` `asyncio_mode="auto"`, `testpaths=["tests"]`, `pythonpath=["src","."]`.
- `.opencode/rules/*.md`: tidak ada wrapper tes khusus → perintah = `python3 -m pytest tests/backend -q`.
- `tests/backend/conftest.py`: isolasi DB otomatis ke file temp (`AIGATE_DB_PATH`), suite hermetic.

### 4. Jalankan suite — RUNAWAI (sebelum perbaikan)
- `python3 -m pytest tests/backend -q` → **4 failed, 494 passed, 1 skipped** (40,56 s; 33 file tes).
- Isolasi regresi: worktree baseline `a237414~1` (= `c3a2241`) → KEEMPAT kegagalan TERULANG IDENTIK (2,68 s) → **pre-existing, bukan regresi WIP**. Worktree dibersihkan (`git worktree remove`).
- Rincian pre-existing: `cli_compat.py:238` except kosong (guard R12 `test_logging.py:180`) + 3 ekspektasi basi `test_cli_tools.py` milik pekerjaan anthropic-inbound/cli-compat sebelumnya (claude_flip VERIFIED tanpa builder launch in-app = gap NYATA: resolve hanya inject `OPENAI_*` yang diabaikan claude-code; kunci `compat` baru di ToolDTO; kasus param claude-unsupported basi).

### 5. Delegasi be-dev — realisasi
**Commit `03d9b6e` (fitur):**
- `src/backend/oauth.py` +20/−7: skip kredensial kosong (pin → fallback strategi; strategi → kandidat berikut); perbaikan h1; docstring diperbarui.
- `tests/backend/test_account_routing.py` BARU, 28 tes, 658 baris: mesin fill-first (urutan prioritas+tie-break id, skip raise, skip kosong, fallback legacy, string tak dikenal=fail-safe), round-robin sticky (default 3, limit dari kolom 1/2, clamp 0→1, matriks `clamp_sticky_limit`, persist `last_used_at`, urutan bertahan restart, kegagalan kandidat tidak memakan streak), pin (menang atas dua strategi; pin unknown/disabled/asing/token-gagal → fallback tanpa error; wrapper meneruskan pin), parsing header `_preferred_account_id` (absen/kosong/non-int/valid), `resolve_target` meneruskan pin s/d `ResolvedTarget.account_id`, DTO+validasi 400+clamp di jalur rute, migrasi idempoten 2× pada DB skema-lama.
- 3 bug di tes itu sendiri ditemukan & diperbaiki saat menjalankan (bocor streak antar-bagian; lupa patch SessionLocal; body 422) — hasil akhir file: 28 passed.

**Commit `f986d51` (pre-existing, dipisah dari fitur):**
- `src/backend/cli_compat.py`: `except: pass` → debug-log stdlib `logging` (modul tetap framework-free).
- `src/backend/cli_tools_router.py`: `_claude_builder` + registrasi — `ANTHROPIC_BASE_URL` = ROOT gateway (CLI menambah `/v1/messages` sendiri; form meniru `scripts/cli-tools/claude.sh:64-83` yang terbukti jalan), `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`+`--model` opsional, prefix env per-perintah (pola `_openhands_builder`, tidak persist config). Guard verified-preset kini jujur.
- `tests/backend/test_cli_tools.py`: +kunci `compat`; claude → `("verified","")`; hapus kasus param claude basi; +unit test `_claude_builder` (pembuangan `/v1`, model opsional).

### 6. Suite final — HIJAU
- `python3 -m pytest tests/backend -q` → **526 passed, 1 skipped, 0 failed** (40,63 s).
- Rekonsiliasi angka: 499 total awal + 29 tes baru − 1 kasus basi = 527 total = 526 pass + 1 skip (1 skip pre-existing, tidak berubah).

## Status Akhir
**BERHASIL — gerbang backend HIJAU.** Kontrak tahap-1 di bawah menjadi acuan tahap-2 fe-dev. Yang belum diverifikasi (jujur): (1) fitur dijalankan di aplikasi nyata (gateway live + DB nyata + claude-code spawn) — aturan "done after exercised for real" BELUM terpenuhi, baru level tes; (2) dua commit belum di-push; (3) UI strategi (modal ber-tab, pemilih strategi/sticky/priority, hapus panel discovery) belum ada — memang tahap 2.

## KONTRAK TAHAP-1 (resmi — acuan fe-dev)

### Data
- `Provider.fallback_strategy` TEXT default `'fill-first'`; enum SATU-SATUNYA: `fill-first` | `round-robin`.
- `Provider.sticky_round_robin_limit` INTEGER default `3` (efektif hanya untuk `round-robin`; di-clamp ≥ 1).
- `ProviderAccount.priority` INTEGER default `0` (ANGKA KECIL = dicoba duluan; tie-break id asc).
- `ProviderAccount.last_used_at` DATETIME NULL — milik mesin, read-only untuk API/UI.
- Migrasi self-heal idempoten `ALTER TABLE` (bukan alembic) di `config/db.py:218`.

### API
- `GET|POST /api/providers`, `PUT /api/providers/{id}`: menerima + mengembalikan `fallback_strategy`, `sticky_round_robin_limit`; strategi di luar enum → **400 `invalid_fallback_strategy`**; limit <1 → di-clamp ke 1.
- `GET /api/accounts?provider_id=` → daftar TERURUT `priority` asc, id asc; item DTO += `priority` (int), `last_used_at` (ISO-8601 | null).
- `POST /api/accounts` menerima `priority` (default 0). `PUT /api/accounts/{id}` HANYA menerima `priority` (parsial; 404 `account_not_found`).
- `GET /api/providers` DTO += dua field routing (selalu ada, ternormalisasi).
- Gateway: header **`x-connection-id: <id_akun>`** = pin satu akun untuk request itu (menang atas strategi; pin tak sah / akun tak tersedia → diabaikan + strategi jalan, request TIDAK error). Berlaku di `/v1/chat/completions`, `/v1/responses`, `/v1/messages`, dan jalur endpoint-named. **Diagnostics combo: header pin diabaikan** (kredensial anggota dipilih di dalam `combo_routing`).

### Semantik mesin (`oauth.py:336`)
1. pin > 2. strategi per provider > 3. legacy `provider.api_key`.
- `fill-first` (default): akun prioritas tertinggi yang USABLE menang terus (TIDAK berotasi); "unusable" = token gagal di-resolve ATAU kredensial kosong.
- `round-robin`: STICKY — akun yang sama dipakai `sticky_round_robin_limit` seleksi berturut-turut, lalu maju ke akun terlama tak terpakai (`last_used_at` asc, NULL terdahulu, id asc). Counter streak in-memory; restart menurunkan urutan dari `last_used_at` (tidak ada tabel baru).
- OAuth auto-refresh (ADR-013) dan attribution `UsageRecord` per akun (B5.5) tidak berubah.

### Yang TIDAK ada (keputusan terkunci user)
- TIDAK ada weighted / latency / cost / adaptive / random (di set akun-level 9router maupun di aigate).
- Combo tidak disentuh; panel discovery UI dihapus NAMUN `/discover` tetap dipanggil diam-diam (opsi a) — itu pekerjaan tahap-2 fe-dev.
