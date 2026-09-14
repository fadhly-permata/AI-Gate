# Handover — WP.1: Cek versi Python di awal `run.py`

**PM → fullstack-dev** · 2026-09-14 14:07 · branch kerja: `feat/wp1-python-check`
**Sumber tugas:** `documents/plan/wiki-backlog.md` §Tahap 1.9 item **WP.1** (antre sejak penulisan wiki).

## Kenapa ini milikmu (bukan be-dev)
`run.py` = berkas level-repo di root, **di luar** write-root `src/backend/**` milik be-dev.
Sesuai aturan batas agen (`agent-boundaries`), berkas root di luar write-root spesialis = milik fullstack-dev.
Kamu juga yang pegang register `documents/dev/CODE_CHANGES.md` untuk perubahan ini? **Tidak** — cukup lapor ke PM,
PM yang catat (hindari dua penulis di satu berkas catatan).

## Tujuan
Kalau user jalankan `python run.py` dengan Python **< 3.10**, aplikasi harus berhenti rapi dengan
**satu pesan manusiawi**, BUKAN traceback panjang dari dependensi yang gagal import/compile.
Ini kegagalan langkah-pertama paling umum (dokumentasi tidak bisa menutupi kode yang diam saja).

## Fakta yang sudah PM cek (jangan cek ulang, hemat putaran)
- `pyproject.toml:11` → `requires-python = ">=3.10"` (sumber kebenaran angka; **jangan hardkode angka lain**).
- `run.py` = 46 baris. Alur sekarang: docstring → `import importlib.util, os, subprocess, sys` →
  `sys.path.insert(0, src)` → dict `REQUIRED` (pin `fastapi>=0.95,<0.100`, `pydantic>=1.10,<2`, dst;
  `pywinpty` kalau `win32`) → `def ensure_deps()` (pip install yang hilang) →
  `if __name__ == "__main__": ensure_deps(); from backend.launcher import main; main()`.
- Bahaya nyata di Python tua: `ensure_deps()` pasang paket yang butuh 3.10 → gagal; atau
  `from backend.launcher import main` kena SyntaxError/TypeError saat import. Pesan ramah harus muncul
  **sebelum** keduanya.
- Ada interpreter 3.14 di lingkungan ini (`src/backend/__pycache__/*.cpython-314.pyc`), jadi jalur "lolos"
  juga wajib diuji.

## Batas tulis (STRIK)
- WRITE: **`run.py` saja.**
- READ: `pyproject.toml`, `documents/pm/**`, `src/backend/launcher.py` (untuk paham alur — jangan diubah).
- DILARANG tulis: `src/**`, `tests/**`, `documents/**`, `pyproject.toml`, berkas root lain, folder baru.
- Jangan sentuh logika `REQUIRED`/`ensure_deps()`/`main()` yang sudah ada — tambah gerbang, bukan rombak.

## Ketentuan isi
1. Cek versi **di titik pertama yang bisa dieksekusi** setelah `import sys` (sebelum `sys.path.insert`,
   sebelum `ensure_deps()`, sebelum import apa pun dari `backend`). Kalau perlu, pindahkan posisi cek.
2. Baca angka minimum dari **satu konstanta** `(3, 10)` dan tulis komentar rujukan ke `pyproject.toml`
   `requires-python` — supaya tidak dua sumber kebenaran. (Boleh hardkode konstanta, asal berkomentar.)
3. Pesan = satu blok teks singkat, ke `stderr`, `sys.exit(1)`. Format wajib jelas bagi orang awam, contoh:
   `aigate needs Python 3.10 or newer - you have 3.9.7` + satu baris suruhan ("pasang/install Python 3.10+
   lalu jalankan lagi"). **Bahasa Inggris**, netral budaya, tanpa path internal repo, tanpa emoji.
4. **Wajib tetap bisa dijalankan oleh Python tua** — artinya jangan pakai sintaks yang cuma ada di 3.10+
   di `run.py` (mis. `match`, union type di anotasi wajib, `except*`). Kalau perlu anotasi, pakai yang aman
   3.9. Ini poin paling sering salah: gerbang versi yang sendiri tidak bisa di-parse = percuma.
5. Nomor versi dicetak pakai `sys.version_info[:3]` (hilangkan unsur kalau cuma 2 segmen), jangan tebak.

## Gerbang selesai (kamu jalankan sendiri, laporkan hasilnya)
- [ ] `python3 -m py_compile run.py` → exit 0.
- [ ] **Jalur gagal:** `python3 -c "import sys; print(sys.version)"` catat interpreter uji, lalu paksa
      interpretasi versi rendah dengan menguji fungsi gerbang secara terisolasi (mis. ekstrak cek jadi
      `def _check_python_version(info)` lalu panggil dengan `(3,9,7)` dan `(3,12,0)`) → pesan muncul di
      stderr + `SystemExit(1)`. BUKAN pakai monkeypatch interpreter sistem.
- [ ] **Jalur lolos:** interpreter nyata 3.10+ di lingkungan ini → gerbang diam, tidak ada pesan palsu.
- [ ] `python3 run.py --help` ATAU sekali jalan cepat lalu berhenti sendiri JANGAN dilakukan kalau itu
      memicu server / instalasi paket. Cukup `py_compile` + uji gerbang terisolasi + bukti baca kode.
      Jangan start server, jangan pip install, jangan sentuh port 8080 (aturan J6: proses user haram).
- [ ] `git diff` bersih: **hanya** `run.py` yang berubah, nol file lain.
- [ ] `git status --porcelain` sebelum kirim: kalau muncul file selain `run.py` → hapus/mundurkan.

## Output yang PM minta (receipt)
1. Daftar berkas berubah (+/- baris).
2. Isi persis pesan yang akan dibaca user (tempel apa adanya).
3. Bukti tiap gerbang di atas (perintah + hasil, bukan klaim).
4. Cara kamu memastikan `run.py` masih bisa di-parse Python 3.9 (bukti, bukan asumsi).
5. JANGAN commit, JANGAN push, JANGAN buat PR (hak user).
6. Kalau ada keputusan ambigu: sebut pilihanmu + alasannya (PM sudah catat default: angka dari konstanta
   + komentar rujukan, pesan bahasa Inggris, exit code 1).
