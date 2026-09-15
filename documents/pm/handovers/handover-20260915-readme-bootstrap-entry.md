# Handover — README + Quick-Start: jalur "just work" jadi bootstrap

**PM → public-writer** · 2026-09-15 · branch kerja: `main` (working tree; JANGAN bikin branch).

## Tujuan
Bootstrap installer sudah ada di repo (`scripts/bootstrap.sh` + `scripts/bootstrap.ps1`, belum di-commit tapi sudah
di-review PM). Update **9 berkas publik** supaya "first run" = satu perintah **tanpa perlu Python terpasang duluan** —
sesuai klaim "Nothing installed → one command → aigate running" yang sudah tertulis di Quick-Start. Isi command berubah,
nada + struktur tetap.

## Berkas target (WRITE scope)
1. `README.md` (root, EN) — blok "Try it in 60 seconds" (baris 47-60)
2. `documents/readme-variants/README.id.md`
3. `documents/readme-variants/README.ru.md`
4. `documents/readme-variants/README.nl.md`
5. `documents/readme-variants/README.ja.md`
6. `documents/readme-variants/README.zh.md`
7. `documents/readme-variants/README.zh-tw.md`
8. `documents/readme-variants/README.hi.md`
9. `documents/pm/wiki-drafts/Quick-Start.md` — blok "What you need 🧰" + "Get it running ▶️" + contoh port/dev

**DILARANG sentuh (jangan ikut):** `documents/pm/wiki-drafts/Interfaces.md` (frasa "You ran `python run.py`" = konteks
lama yang masih valid setelah bootstrap — bukan instruksi), `documents/dev/SETUP.md` (bukan materi publik),
arsip, `documents/pm/**` lainnya.

## Fakta yang PM sudah verifikasi (jangan cek ulang)
- `scripts/bootstrap.sh` POSIX lolos `bash -n` + `dash -n` + `sh -n`; `--check-only` diverifikasi jalan nyata di Termux
  → deteksi platform + interpreter ≥3.10 + git, **nol install / nol launch**, idempoten, path-independent.
- `scripts/bootstrap.ps1` Windows: **strukturnya** lolos review PM; TIDAK dieksekusi (nggak ada `pwsh` di lingkungan ini).
  JANGAN klaim Windows "tested" LEBIH dari baseline claim repo saat ini. Perlakukan bootstrap.ps1 sebagai jalur yang
  ADA + SIAP DIPAKAI tapi BELUM DIUJI Windows real — jangan bikin kalimat seperti "we tested it on Windows just now"
  atau menambahkan klaim test baru.
- Bootstrap bukan pengganti `run.py` — dia MEMANGGIL `run.py`. Setelah `bash scripts/bootstrap.sh` selesai install
  Python, dia `exec "$PY" run.py "$@"` = pip deps + start server + arg forwarding. Env var user (`AIGATE_PORT`, `AIGATE_DEV`)
  ikut ter-forward (env inherits through exec).
- `python run.py` MASIH BEKERJA kalau user sudah punya Python ≥ 3.10. Bootstrap cuma nambah kemampuan cold-start.
  **Rekomendasi publik = bootstrap dulu**, karena README harus "just work" beneran.

## Ketentuan isi

### A. README.md (root, English) — § "Try it in 60 seconds ⏱️"
Ganti blok `python run.py` menjadi bootstrap. Struktur:

- Satu kalimat pembuka singkat yang bilang **kamu nggak perlu apa-apa lagi** (Python, pip, dsb). Nada tetap chill,
  reader-first, tanpa jargon.
- Satu blok code fenced `bash` → `bash scripts/bootstrap.sh`.
- Baris setelah blok: "Open **http://localhost:8080** ...". (kalimat existing, pertahankan nuansa)
- Sub-bagian Windows kecil: sebut command PowerShell **`pwsh scripts/bootstrap.ps1`** (Windows PowerShell 5.1:
  `powershell -File scripts\bootstrap.ps1`). SATU baris, nggak usah heboh.
- "Port busy?" tetap ada; ganti command jadi `AIGATE_PORT=9090 bash scripts/bootstrap.sh` (env var jalan karena bootstrap
  meneruskan ke run.py). Windows: `$env:AIGATE_PORT="9090"; pwsh scripts/bootstrap.ps1`.
- **JANGAN hapus** bagian "Runs on your phone 📱" — di situ sebut Termux; bootstrap.sh justru pas dipakai di sana.
  Kamu boleh tambah satu frasa ringan di situ kalau perlu (mis. "same command works there") tapi jangan panjang.
- Kalimat yang bilang "if you already have Python, `python run.py` juga oke" boleh kamu selipkan sebagai catatan kecil
  di bawah blok utama (bukan section baru). Jangan bikin sub-heading baru.

### B. 7 varian (documents/readme-variants/README.*.md)
Cerminin perubahan README.md **di bahasanya masing-masing**, NATIF (bukan translate literal). Command-nya TETAP:
`bash scripts/bootstrap.sh` (POSIX) / `pwsh scripts/bootstrap.ps1` (Windows) — command terminal jangan diterjemahkan.
Sama kayak README.md: jangan tambah sub-heading baru, jangan ubah nada tiap bahasa (mis. `ja` lebih sopan, `hi` Devanagari).
Panjang ≈ sama ±10%.

### C. Quick-Start.md (wiki draft, `documents/pm/wiki-drafts/Quick-Start.md`)
Ganti bagian yang relevan:

- § **"What you need 🧰"** — sebelumnya: "Python 3.10 or newer. That's genuinely it." **Sekarang:**
  "Nothing. That's genuinely it." ATAU "Nol. Itu beneran nol." (bahasa Inggris: "Nothing" — jangan bikin kalimat aneh).
  Sisanya (no GPU, no compiler, no Docker, no cloud) TETAP. Kalimat penutup tetap: "The only thing that might cost
  money is the AI provider account *you* use..."
- § **"Get it running ▶️"** — ganti `python run.py` → `bash scripts/bootstrap.sh` dalam blok clone/cd/run:
  ```bash
  git clone https://github.com/fadhly-permata/AI-Gate
  cd AI-Gate
  bash scripts/bootstrap.sh
  ```
  Baris follow-up "That last line grabs the Python pieces it's missing, then starts." → perlu diperbarui jadi
  sesuatu seperti "That line makes sure Python is there (installs it if it isn't), grabs the packages it needs, and
  starts the app." — nada sama, jangan lebih panjang.
  **Windows:** tambah SATU baris aja: "On Windows: `powershell -File scripts\bootstrap.ps1`". Nggak usah bikin
  subsection.
- § **"Port busy? Sharing a network? 🔌"** — ganti `python run.py` → `bash scripts/bootstrap.sh`. Kalimat
  Windows PowerShell `set AIGATE_PORT=...` TETAP valid; kamu boleh tambah `pwsh` form juga (`$env:AIGATE_PORT="9090";
  pwsh scripts/bootstrap.ps1`).
- § **"When something goes wrong 🧯"** — item pertama sekarang berubah: sebelumnya bilang "Your Python is older than
  3.10. Install a newer Python, run again." → **SEKARANG:** karena bootstrap yang install Python, pesan itu jadi lebih
  jarang muncul. Rubah jadi sesuatu seperti: "Bootstrap couldn't find a way to install Python — tell me which OS you
  were on." (reader-first, jujur). Kalimat "run with the developer window" (`AIGATE_DEV=1 python run.py` →
  `AIGATE_DEV=1 bash scripts/bootstrap.sh`).

## Batas gaya (tetap aturan lama)
- Nama aplikasi: **`aigate` huruf kecil** (bukan AI-Gate atau AIGate kecuali di URL).
- DILARANG bocorkan isi `documents/**` ke publik (nol rujukan internal path, nama file sumber, nama tabel DB, ADR-###).
  Pengecualian: nama file perintah `run.py`, `scripts/bootstrap.sh`, `scripts/bootstrap.ps1` — ini command yang user
  akan KETIK, jadi WAJIB ditulis persis.
- Nada: kasual English (README/Quick-Start) / natural per bahasa varian. Reader-first. Emoji boleh di heading,
  dilarang di alur error.
- **Jangan ubah angka "eight languages"** (line 44 README, dan padanannya di 7 varian + Quick-Start kalau ada)
  — itu bukan tugas ini. Jangan ubah "24 AI coding tools". Jangan sentah klaim lisensi MIT.
- **JANGAN klaim baru**: jangan nambah "tested on Windows" / "verified across OS" yang lebih kuat dari yang sudah ada.
  Bootstrap Windows = implemented, not yet executed at test-time.

## Gerbang selesai (kamu jalankan sendiri, laporkan hasil NYATA)
- [ ] Grep `python run.py` di 9 target file → **0 hasil**. (Arsip + Interfaces.md + SETUP.md + `documents/pm/**` boleh
      tetap punya `python run.py` — di luar scope.)
- [ ] Grep `bash scripts/bootstrap.sh` → 9 target file (1 per file, bisa >1 per file kalau blok contoh env-var juga).
- [ ] Grep `pwsh scripts/bootstrap.ps1` → 9 target file (minimal 1 per file).
- [ ] Klaim baru Windows: **0**. Diff hanya ganti/menambah perintah + satu-dua kalimat penjelasan; nggak ada kalimat
      marketing baru.
- [ ] Nada + angka kunci utuh: "eight languages", "24 AI coding tools", "http://localhost:8080", kredit "Made with ❤️
      by Fadhly Permata" baris terakhir, bahasa "aigate" kecil.
- [ ] Tiap varian tetap di bahasanya (bukan Inggris nyamar). Command terminal tetap ASCII (BUKAN transliterasi).
- [ ] `git diff --check` → 0.
- [ ] `git status --porcelain` sebelum kirim: **HANYA 9 file target** berubah (+ report-mu di `.opencode/reports/**`).
      NOL `run.py`, NOL `scripts/bootstrap.*`, NOL `src/**`, NOL `tests/**`, NOL `pyproject`, NOL file `documents/pm/**`
      selain wiki-drafts/Quick-Start.md.
- [ ] JANGAN commit, JANGAN push, JANGAN publish wiki.

## Receipt yang PM minta
1. Daftar 9 berkas + +/- baris per berkas.
2. Verbatim: 1 blok "Try it in 60 seconds" (EN), 1 blok Windows line (EN), 1 blok "What you need" (EN), 1 blok
   "Get it running" (EN), 1 blok "Port busy?" (EN). Sisanya (7 varian + sisanya Quick-Start) cukup path + ringkasan.
3. Output MENTAH tiap gerbang di atas.
4. Keputusan ambigu yang kamu ambil + alternatif.
5. Konfirmasi JANGAN commit/push/publish.

## Catatan
- Quick-Start adalah **wiki draft** di `documents/pm/wiki-drafts/`. Edit di sini BELUM update halaman wiki GitHub
  yang tayang. Publish-nya PM handle terpisah (lewat `python3 .opencode/tools/docs/wiki/publish_wiki.py`, keputusan
  user). Kamu nggak perlu mikirin publishing.
- README.md + 7 varian = materi publik yang di-serve dari repo; sudah ke-user begitu merge PR.
