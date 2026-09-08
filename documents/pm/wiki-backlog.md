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
- [!] **W1.1** `Home.md` — peta jalan. **Rewrite v2** (user: "agak kurang menarik ya, rewrite dong"). Gaya: adegan pembuka + heading percakapan + hasil dulu.
      → naskah berubah total · 6 seksi tetap · nol "this repo" · URL absolut
      → RONDE 3 ("cerita ilustrasinya kurang asik") dan RONDE 4 (user kasih arah: "vibe coding tapi
        perangkat terbatas, lagi bepergian, minim budget beli device") → v4 = HP bekas + bus malam,
        375 kata. PM potong klaim absolut "every coding guide" → "most".
      → KOREKSI ATURAN: Self-Heal ternyata SUDAH PUBLIK di README (bikin branch, jalankan agen,
        benerin warning, merge) → larangan di wiki DICABUT. v4 tidak menyebutnya (butuh proyek +
        agen terpasang, off-theme); WAJIB dibahas di halaman 7 + risikonya.
      → owner: business-analyst · 319 kata · 0 kata terlarang · 5 tautan internal valid
      → temuan: klaim Self-Heal salah digambarkan → DICORET (lihat pertanyaan terbuka #6 di plan)
- [ ] **W1.2** `Quick-Start.md` — pasang sampai jalan, 3 platform. Perbaiki 3 bug README.
      → owner: system-analyst (verifikasi perintah) + business-analyst (nada)
- [!] **W1.3** `Interfaces.md` — daftar cara memakai aigate + link per halaman.
      → owner: system-analyst · perlu membaca route/menu frontend (read-only)
- [!] **W1.4** `Configuration-and-Keys.md` — pasang key, atur provider, ganti port.
      → owner: system-analyst · caveat: key tersimpan teks biasa
- [!] **W1.5** `CLI-Tools.md` — 24 tool + cara menyambungkan. Catatan "daftar masih berkembang".
      → owner: system-analyst (hitung preset nyata) + business-analyst (cara pakai)
- [!] **W1.6** `OpenAI-API.md` — alamat lokal + contoh request.
      → owner: be-dev (endpoint nyata) + business-analyst (penulisan awam)
- [!] **W1.7** `Terminal.md` — tab, fullscreen, paste, scroll/swipe, log, pemulihan gagal.
      → owner: fe-dev (kontrol yang muncul di UI)
- [!] **W1.8** `Providers-and-Combos.md` — model mental provider → combo → giliran pakai.
      → owner: system-analyst + business-analyst

- [!] **W1.2** `Quick-Start.md` — cara pasang. Draf siap direview (±440 kata, 6 seksi, 5 blok
      perintah, semua perintah diverifikasi PM dari kode).
      → PM menutup 4 keraguan BA dengan verifikasi: cara ambil kode (`git clone` — tidak ada jalur
        lain, tidak ada script pembungkus), cek versi Python, sintaks variabel di PowerShell/cmd.
      → ⚠️ LUBANG PRODUK Ketemu: `run.py` (46 baris) TIDAK mengecek versi Python → Python lama
        memuntahkan error yang tidak bisa dibaca orang awam. Usulan perbaikan kecil, lihat WP.1.

## Tahap 1.9 — Perbaikan produk ketemu dari penulisan wiki
- [ ] **WP.1** Tambah cek versi Python di awal `run.py`: kalau < 3.10, cetak satu pesan manusiawi
      ("aigate needs Python 3.10+ — you have X.Y") lalu keluar bersih, BUKAN traceback.
      → owner: be-dev · alasan: ini kegagalan langkah-pertama paling umum, dan dokumentasi tidak
        bisa menutupi kode yang diam saja.

DRAF 8 HALAMAN SUDAH SEMUA (user 2026-09-08: "langsung kerjain sisa file wiki"). Status per halaman:
W1.1 Home = DI-ACC · W1.2–W1.8 = draf jadi, **belum direview user**.
Hasil kerja tambahan saat menulis (jangan sampai hilang):
- **Koreksi fakta besar #1:** host/port pada endpoint **tidak** membuka port kedua (tidak ada kode
  yang memakainya untuk listen). Satu port nyata = port aplikasi. Ditulis di halaman 4, 6, 8.
- **Koreksi fakta besar #2:** koneksi terputus = **view lepas, proses tetap jalan + menampung
  output**; sesi dihapus hanya kalau ditutup sendiri atau lepas & tanpa keluaran (bawaan 60 menit).
  Lembar fakta C tadinya SALAH (PM yang salah), halaman 7 sudah dibetulkan.
- **Koreksi #3:** tidak ada combo bawaan bernama `default` → semua contoh pakai placeholder.
- Halaman 5: angka per kelompok (12/6/6) dibuang supaya tidak basi; daftar tool tetap contoh.

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

## Tahap 1.5 — Keputusan lisensi (NAIK KE PR #11)
PR: https://github.com/fadhly-permata/AI-Gate/pull/11 · branch `chore/mit-license` (9 commit,
16 file, +632/-8, mergeable=clean) · PR #10 sudah merged → 7 varian README + baris bahasa sudah di
`main` · `main` lokal disinkron. Setelah PR #11 merge: GitHub baru menampilkan label lisensi,
dan WL.2a baru boleh dikerjakan.
--- (user 2026-09-08: "kita pake MIT aja dulu")
- [x] **WL.1** Pasang `LICENSE` MIT + `THIRD_PARTY_NOTICES.md` (notis xterm.js yang wajib) + field
      lisensi `pyproject.toml`. → owner: be-dev (handover eksplisit; fullstack-dev baru ke-generate tapi belum terdaftar di runtime) · branch `chore/mit-license`
      → hasil: `LICENSE` (badan MIT **identik byte** dgn teks resmi SPDX), `THIRD_PARTY_NOTICES.md`
      (notis xterm.js upstream + Font Awesome berlisensi berlapis + daftar deps tanpa klaim bohong),
      `pyproject.toml`: `license = "MIT"` SAJA — classifier lisensi dibuang (deprecated setuptools>=77)
- [!] **WL.2** Buka larangan kata "free / open source" + tambah kalimat "this is the only official
      source" di `README.md` (root) & `documents/pm/wiki-drafts/Home.md`. → owner: business-analyst
      (varian id/ru/nl/ja/zh/zh-tw/hi TIDAK disentuh sampai master English di-ACC user)
      → README murni sisipan (+3 baris, 0 hapus) · Home.md ±337 kata · PM memperhalus 2 frasa kaku
      → KOREKSI user (R45): "this repo" AMBIGU di fork (teks ikut ter-copy) → ganti URL absolut
        `https://github.com/fadhly-permata/AI-Gate` di README & Home. UI sidebar sudah absolut ✔
      → PEKERJAAN SUSULAN: saat menyebarkan kalimat ini ke 7 varian, alamatnya TIDAK diterjemahkan
- [ ] **WL.3** REVIEW LISensi — "dulu/sementara" dari user. Pemicu review: (a) sebelum rilis publik
      pertama, (b) sebelum kontribusi orang lain masuk, (c) kalau ada yang mulai ngomersialkan klon.
      Catat: salinan MIT yang sudah tersebar tidak bisa ditarik balik.
- [ ] **WL.4** Pin versi xterm.js yang di-vendor (sekarang TIDAK tercatat di repo — provenance gap)
      dan simpan salinan teks lisensi upstream di folder vendor.
- [ ] **WL.5** ⚠️ Font Awesome dimuat dari CDN Cloudflare (`index.html:42`) padahal xterm sengaja
      di-vendor biar offline-safe → icons mati tanpa internet + ada request keluar ke pihak ketiga,
      bertentangan dengan klaim privasi di README/wiki. BUTUH KEPUTUSAN user: vendor lokal / ganti
      ikon / tetap CDN + koreksi kalimat privasi.
