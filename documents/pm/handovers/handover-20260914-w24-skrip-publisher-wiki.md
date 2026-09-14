# Handover — W2.4: skrip publisher wiki (idempoten + dry-run)

**PM → fullstack-dev** · 2026-09-14 14:07 · branch: `feat/wp1-python-check` (jangan pindah branch tanpa izin PM)
**Sumber tugas:** `documents/plan/wiki-backlog.md` §Tahap 2 item **W2.4**.

## Kenapa kamu
Skrip tooling di `.opencode/tools/**` = berkas level-repo di luar write-root spesialis lain → milik
fullstack-dev (roster: "repo-level files that fall outside other specialists' write roots").

## Tujuan
Sekarang penerbitan halaman wiki dikerjakan manual (clone `AI-Gate.wiki.git` ke tmp → salin `.md` → push).
Itu bisa salah/tempel-kurung. Butuh satu skrip yang mengulang proses itu secara **idempoten** dan
**berhenti sendiri** kalau tidak sengaja dipanggil.

## Fakta yang sudah PM cek (jangan cek ulang)
- Konten sumber = `documents/pm/wiki-drafts/*.md` (8 berkas: CLI-Tools, Configuration-and-Keys, Home,
  Interfaces, OpenAI-API, Providers-and-Combos, Quick-Start, Terminal). Nama file pakai tanda hubung;
  nama itulah nama halaman wiki.
- Wiki repo publik = `https://github.com/fadhly-permata/AI-Gate/wiki` → git-nya
  `https://github.com/fadhly-permata/AI-Gate.wiki.git`. Ronde publish sebelumnya (commit wiki `ae55c46`)
  berhasil lewat clone tmp + salin + push.
- Kredensial: HANYA dari `.env` (`GITHUB_TOKEN` ada di situ) atau `gh auth token`. **DILARANG** cetak nilai
  token, **DILARANG** commit `.env`, **DILARANG** bikin tempat kredensial baru. Repo utama `origin` harus
  tetap **tanpa** token di URL-nya (sudah dibersihkan ronde lalu — jangan dikotori lagi).
- Aturan B1: tidak bikin folder/baru di root repo; artefak tool = `.opencode/tools/...`.

## Batas tulis (STRIK)
- WRITE: `.opencode/tools/docs/wiki/**` (folder baru di bawah `.opencode/tools/` = sah, ini memang
  lokasi yang ditunjuk backlog).
- READ: `documents/pm/wiki-drafts/**`, `documents/plan/wiki-backlog.md`, `.opencode/rules/**`.
- DILARANG tulis: `src/**`, `tests/**`, `README.md`, `documents/readme-variants/**` (lagi dipegang
  public-writer ronde ini), `documents/pm/**` (milik PM), root repo.

## Ketentuan skrip
1. Bahasa: Python 3 (standar repo), jalan tanpa dependensi baru di luar yang sudah ada di
   `pyproject.toml`. Nol npm, nol install.
2. Panggilan: `python3 .opencode/tools/docs/wiki/publish_wiki.py [--source DIR] [--pages a.md,b.md] [--dry-run|--publish]`.
3. **Default = DRY-RUN.** Menerbit nyata **wajib** tombol eksplisit `--publish`. Kalau tidak ada keduanya,
   skrip harus memperlakukan sebagai dry-run, bukan publish. (Ini pagar anti-klik-salah.)
4. Mode dry-run: clone/fetch ke direktori sementara DI LUAR repo (pakai `tempfile`), bandingkan isi per
   berkas (sha256), cetak tabel "akan tulis / tidak berubah / sumber hilang". NOL push, NOL tulis ke wiki.
5. Mode publish: sama, lalu commit + push **hanya** berkas yang benar-benar berubah. Pesan commit otomatis
   singkat + daftar halaman. Idempoten: dipanggil dua kali beruntun = perubahan nol di panggilan kedua.
6. Bersih: direktori sementara selalu dihapus (`try/finally`), termasuk saat gagal.
7. Kredensial: ambil dari env var `GITHUB_TOKEN`, kalau tidak ada coba `gh auth token`; kalau dua-duanya
   tiada → pesan jelas lalu keluar nonzero (jangan traceback, jangan minta input interaktif).
   Jangan pernah mencetak token; kalau perlu menampilkan URL, tutupi (`https://x-access-token:***@...`).
8. JANGAN pernah menyentuh repo utama (tidak `git add`, tidak `git commit`, tidak ubah remote/URL).
   Skrip ini cuma ngurus repo wiki hasil klon sementara.
9. Nama produk di teks/output: `aigate` huruf kecil.

## Gerbang selesai (kamu jalankan sendiri)
- [ ] `python3 -m py_compile .opencode/tools/docs/wiki/publish_wiki.py` → exit 0.
- [ ] `--help` jalan, keluar 0, tanpa sentuh jaringan? (boleh sentuh jaringan kalau dry-run; kalau iya,
      catat.)
- [ ] **Kering tanpa kredensial:** panggil dry-run dengan `GITHUB_TOKEN` dikosongkan + `gh` dianggap tiada →
      harus keluar rapi dengan pesan jelas, **nol traceback**, exit != 0.
- [ ] **Uji logika inti tanpa jaringan:** fungsi bandinkannya (mis. `plan_publish(source_files, wiki_files)`)
      diuji terisolasi dengan data palsu → kasuskan: berkas baru, berkas berubah, berkas identik (harus
      "tidak berubah"), berkas di sumber hilang (tidak boleh hapus halaman wiki tanpa perintah eksplisit).
      Tulis sebagai tes cepat yang bisa dijalankan orang lain (perintah tunggal), taruh juga di
      `.opencode/tools/docs/wiki/` (mis. `selftest.py`) — BUKAN di `tests/**` (itu wilayah be-dev/qa).
- [ ] JALANKAN DRY-RUN NYATA kalau kredensial tersedia: laporkan tabelnya. **JANGAN `--publish`.**
      Menerbit nyata = hak user, dan lagi ada tugas paralel yang masih mengubah sumber draft wiki.
- [ ] `git status --porcelain` sebelum kirim: hanya berkas di `.opencode/tools/docs/wiki/**` yang boleh muncul.

## Output yang PM minta (receipt)
1. Berkas dibuat (+ baris) + cara pakai singkat.
2. Hasil tiap gerbang di atas: perintah + keluaran asli (token tersamar).
3. Tabel dry-run nyata: halaman mana "berubah" vs "tidak berubah" (kalau jalan).
4. Cara kamu memastikan idempoten (bukti, bukan klaim).
5. Keputusan ambigu yang kamu ambil + alasannya.
6. JANGAN commit / push / publish.
