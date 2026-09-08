# Wiki Backlog — aigate (halaman 1–8)

**Dibuat:** 2026-09-08 · **Diperbarui:** 2026-09-08
Rencana & aturan: `documents/pm/wiki-plan.md`. Aturan konten: R44. Eksekusi: **sekuensial** (R17).
Legenda: `[ ]` antre · `[~]` dikerjakan · `[!]` draft siap, **nunggu review user** · `[x]` di-ACC user

---

## Tahap 0 — Persiapan
- [x] **W0.1** Rencanakan cakupan + audit bahan yang sudah ada (`documents/`), tahan isi internal.
- [x] **W0.2** Tetapkan nada & batas konten (Inggris kasual, pembaca awam, emoji) → R44.
- [x] **W0.3** Siapkan staging `documents/pm/wiki-drafts/` + folder ini. Wiki asli **tidak disentuh**.
- [x] **W0.4** Verifikasi 3 bug README dari kode: `requirements.txt` TIDAK ada · `AIGATE_SIMULATE_DEVICE` TIDAK ada (yang ada `AIGATE_DEV`, launcher.py:26) · command `aigate` NYATA ada (`[project.scripts]`) (requirements.txt, AIGATE_DEV, `aigate`).

## Tahap 1 — Delapan halaman (satu per satu, berhenti tiap halaman untuk review)
- [!] **W1.1** `Home.md` — peta jalan. **Draft final siap direview user** (PM sudah koreksi 1 klaim salah).
      → owner: business-analyst · 319 kata · 0 kata terlarang · 5 tautan internal valid
      → temuan: klaim Self-Heal salah digambarkan → DICORET (lihat pertanyaan terbuka #6 di plan)
- [ ] **W1.2** `Quick-Start.md` — pasang sampai jalan, 3 platform. Perbaiki 3 bug README.
      → owner: system-analyst (verifikasi perintah) + business-analyst (nada)
- [ ] **W1.3** `Interfaces.md` — daftar cara memakai aigate + link per halaman.
      → owner: system-analyst · perlu membaca route/menu frontend (read-only)
- [ ] **W1.4** `Configuration-and-Keys.md` — pasang key, atur provider, ganti port.
      → owner: system-analyst · caveat: key tersimpan teks biasa
- [ ] **W1.5** `CLI-Tools.md` — 24 tool + cara menyambungkan. Catatan "daftar masih berkembang".
      → owner: system-analyst (hitung preset nyata) + business-analyst (cara pakai)
- [ ] **W1.6** `OpenAI-API.md` — alamat lokal + contoh request.
      → owner: be-dev (endpoint nyata) + business-analyst (penulisan awam)
- [ ] **W1.7** `Terminal.md` — tab, fullscreen, paste, scroll/swipe, log, pemulihan gagal.
      → owner: fe-dev (kontrol yang muncul di UI)
- [ ] **W1.8** `Providers-and-Combos.md` — model mental provider → combo → giliran pakai.
      → owner: system-analyst + business-analyst

## Tahap 2 — Setelah 8 halaman di-ACC (JANGAN dimulai sebelum itu)
- [ ] **W2.1** `_Sidebar.md` + `_Footer.md` — navigasi wiki.
- [ ] **W2.2** Putuskan: terjemahkan ke 7 bahasa atau tunggu stabil.
- [ ] **W2.3** Putuskan: halaman lanjutan (Data Model, Architecture, Testing, Roadmap) jadi atau tidak.
- [ ] **W2.4** Script publisher `.opencode/tools/docs/wiki/` — idempoten, `--dry-run` wajib,
      token dari `gh auth token`/`.env`. **Butuh izin user sebelum menulis ke wiki.**
- [ ] **W2.5** Perbaiki README root + 7 varian: tautkan halaman wiki yang sudah benar-benar ada
      (baris "Detailed documentation" sekarang menunjuk wiki yang isinya masih kosong).

## Catatan lintas halaman (jangan sampai hilang)
- Nama file wiki pakai tanda hubung (`Quick-Start.md`); tautan internal harus sama persis.
- Produk ditulis `aigate` huruf kecil. Kredit: "Made with ❤️ by Fadhly Permata".
- Jangan tulis jumlah baris/komit/file repo di materi publik — akan basi.
- Angka tool cukup disebut sekali per halaman; jangan tempel daftarnya di banyak halaman.
- DILARANG muncul: "untested/experimental/belum diverifikasi" untuk hal yang sudah dikonfirmasi
  maintainer (R42); tapi DILARANG juga melebihkan klaim yang belum dicek (R23).
