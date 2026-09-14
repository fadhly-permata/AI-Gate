# Wiki Backlog — aigate (halaman 1–8)

**Dibuat:** 2026-09-08 · **Diperbarui:** 2026-09-14
Rencana & aturan: `documents/plan/wiki-plan.md`. Aturan konten: R44. Eksekusi: **sekuensial** (R17).
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
       → KOREKSI 2026-09-14 (user): jumlah bahasa aplikasi 7→8 (Hindi `hi` masuk registry
         `window.LANGS` `i18n.js:28-37` + `hi.js`, 2026-09-13). `Home.md:11` "seven languages"
         → "eight languages". Terverifikasi dari kode (8 entri LANGS + 8 file kamus).
       → SPREAD 2026-09-14: angka yang sama basi di 8 README — semua dibetulin 7→8 dalam bahasa
         masing-masing: `README.md:44` eight · `id:46` delapan · `zh:43` 8 · `zh-tw:40` 8 ·
         `ja:42` 8 · `ru:48` восемь · `nl:44` acht · `hi:43` आठ. Verifikasi grep: 0 sisa "7",
         9 baris baru (8 README + Home) = 8. (Catatan: `семь`=7 adalah sub-string dari
         `восемь`=8 → jangan grep mentah "семь", bikin false positive.)
- [x] **W1.2** `Quick-Start.md` — pasang sampai jalan, 3 platform. Perbaiki 3 bug README.
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
       → **DI-ACC user 2026-09-14** (review sekuensial, tanpa revisi). Langsung commit + publish ke
         GitHub wiki (perintah user: "push dan commit dulu, pastikan tampil di halaman wiki").
         Pembatasan publish (PM ambil default, dicatat): HANYA 2 halaman yang SUDAH DI-ACC = `Home.md`
         + `Quick-Start.md`; 6 halaman lain (Interfaces cs) TETAP di staging sampai lu review.

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
- [ ] **W2.6** **GitHub Pages DITUNDA** (keputusan user 2026-09-14): opsi bikin situs docs aigate
       lewat GitHub Pages (website statis) BARU dikerjain SETELAH ke-8 halaman wiki ACC + terbit.
       Bukan sekarang. Catatan: Pages ≠ Wiki (beda layanan). Tangguhkan sampai wiki rampung.

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
- [~] **WL.4** Pin versi xterm.js yang di-vendor (sekarang TIDAK tercatat di repo — provenance gap)
      dan simpan salinan teks lisensi upstream di folder vendor.
      PERLUAS 2026-09-11: berlaku juga untuk Font Awesome 6.5.1 — nomor versi HANYA dari string header CSS internal,
      belum diverifikasi terhadap artefak rilis upstream (diakui jujur di `THIRD_PARTY_NOTICES.md` §2, commit `15862bf`).
      **SEBAGIAN BESAR SELESAI 2026-09-11 (keputusan user: "boleh" untuk telusuri sumber resmi):**
      versi xterm.js + Font Awesome kini **terverifikasi terhadap artefak rilis** — pencocokan sha256 per berkas
      ke tarball resmi npm, bukan lagi tebakan dari string internal:
      `xterm@5.3.0` (`lib/xterm.js` 283.404 B, `css/xterm.css` 5.383 B), `xterm-addon-fit@0.8.0` (1.503 B),
      `@fortawesome/fontawesome-free@6.5.1` (5/5 berkas identik; tarball 4.951.025 B, sha512+sha1 registry cocok).
      Semua tercatat + bertanggal di `THIRD_PARTY_NOTICES.md` §1–§2.
      SISA (tetap terbuka, makanya `[~]`): (a) teks lisensi upstream xterm BELUM disimpan sebagai berkas di
      `static/vendor/xterm/` (baru Font Awesome yang punya `LICENSE.txt`) dan belum di-diff per-baris vs isi tarball;
      (b) usulan manifest `PROVENANCE.txt` per folder vendor supaya bukti nempel ke artefaknya, bukan cuma ke dokumen root.
- [x] **WL.5** ⚠️ Font Awesome dimuat dari CDN Cloudflare (`index.html:42`) padahal xterm sengaja
      di-vendor biar offline-safe → icons mati tanpa internet + ada request keluar ke pihak ketiga,
      bertentangan dengan klaim privasi di README/wiki. BUTUH KEPUTUSAN user: vendor lokal / ganti
      ikon / tetap CDN + koreksi kalimat privasi.
      **SELESAI 2026-09-11 (keputusan user: "localin aja semua aset font atau icon")** — vendor lokal di
      `src/frontend/static/vendor/font-awesome/` (5 berkas, 409.388 B, blob identik branch `docs/wiki`),
      `index.html:43` path relatif, grep CDN di `static/**` = 0, penjaga otomatis `tests/vendor_assets.test.js` (7 tes),
      legal §2 ditulis ulang + ADR-015 di TSD + FSD 321 dikoreksi. commit `19df593` `15862bf` `b256064` `bb759e4`.
      SISA: uji mata offline nyata (matikan jaringan → ikon tetap muncul) belum dilakukan — butuh user/QA.

---

## Tahap 1.7 — REWRITE 6 halaman oleh SPESIALIS `public-writer` (2026-09-14)
**Perintah user:** "tulis ulang dokumen wiki dengan menggunakan spesialis agent yang baru" → mode: **SEKUENSIAL**
(pilihan user "sekuen"). **Cakupan (default PM, dicatat):** hanya W1.3–W1.8; `Home.md` + `Quick-Start.md`
TIDAK disentuh (sudah ACC + sudah tayang). Owner baru = **public-writer** (agent + skill commit `1f4120b`) —
sebelumnya halaman 3–8 ditulis analyst/engineer, sekarang dirombak total oleh penulis materi publik.
Handover: `documents/pm/handovers/handover-20260914-wiki-rewrite-{1..6}-*.md` · Laporan:
`.opencode/reports/20260914/docs/1201_wiki-rewrite-public-writer.md` · Sesi: `ses_f61faa11fffeobPweNZWiz8zm5`.

Status per halaman (hasil + gerbang):
- [!] **W1.3** `Interfaces.md` — rewrite selesai · 296 kata prosa · gerbang PASS.
- [!] **W1.4** `Configuration-and-Keys.md` — rewrite selesai · 447 kata · gerbang PASS.
- [!] **W1.5** `CLI-Tools.md` — rewrite selesai · 393 kata · gerbang PASS · **Self-Heal pertama kali didokumentasikan**
      di halaman ini (kartunya memang di layar alat coding, `index.html:866-880`) + risikonya ditulis jujur.
- [!] **W1.6** `OpenAI-API.md` — rewrite selesai · 395 kata · gerbang PASS.
- [!] **W1.7** `Terminal.md` — rewrite selesai · 394 kata · gerbang PASS.
- [!] **W1.8** `Providers-and-Combos.md` — rewrite selesai · 477 kata · gerbang PASS.

⚠️ **Lembar fakta A/B/C (2026-09-08) SEBAGIAN BASI — jangan dipakai lagi tanpa audit ulang.**
Fakta baru yang terbukti dari kode hari ini (9 koreksi; rinci di laporan `1201`):
1. **Tidak ada "split view / pecah layar" di terminal** — toolbar nyata: new-tab, Paste + Paste as Code Block,
   Settings (TUI Passthrough, Keep Screen On), Full Page vs Fullscreen, cluster mengambang
   (`index.html:775-835`). Kelas `term-split` = tombol caret, BUKAN layar terpisah. **Salah ini sudah sempat
   masuk draf halaman 3 + 7 → dibuang.**
2. **3 pilihan teknis TIDAK muncul di layar setelan** (logging detail per request, umur simpan log, batas sesi
   terminal) — layar cuma Port/dev-mode/tema/bahasa (`index.html:195-290`). Halaman 4 dulu menjanjikannya → dibetulkan.
3. **Anthropic inbound HIDUP**: `POST /v1/messages` (`gateway/router.py:528`, non-streaming Stage 1) +
   `/v1/messages/count_tokens` (:688); `claude` kini `verified` (`cli_presets.py:174`). Draf lama halaman 6
   bahkan menulis "there are no other endpoints" → SALAH, sudah dibetulkan.
4. **Strategi combo = 5**: `fallback` (bawaan) / `load_balance` / `latency_cost` / `three_tier` / `round_robin`
   (`index.html:1102-1106`; mesin `combo_routing.py:275-305`, docstring `:3-13`). Draf lama cuma tahu sebagian.
5. **Model nama polos ≠ "penyedia aktif"** — resolver cari semua penyedia aktif yang menawarkan model itu; kalau
   >1 → pakai penyedia yang ditandai dipakai (`gateway/resolver.py:218-270`).
6. Port 11434 (Ollama) cuma nongol di docstring contoh (`cli_tools_router.py:606`) = pengetahuan eksternal →
   disebutannya di halaman 8 digeneralisasi.
7–9. Tiga klaim dilemaskan (redaksi): "stutter never reaches you" (klien tetap nunggu saat retry),
   "working offline stays possible" → terlalu tegas, dan "60 menit adjustable in settings" → tidak diekspos layar.
- Koreksi lama #1 (endpoint bukan port kedua) · #2 (putus koneksi ≠ proses mati) · #3 (tidak ada combo `default`)
  TETAP BERLAKU dan justru diperkuat di naskah baru.
- **GATE user sekarang:** review 6 halaman hasil rewrite. **UPDATE 2026-09-14:** perintah user
  "commit, push, dan publish ke halaman wiki" landed → commit `e5a376c`+`806b4cb` (docs/wiki di-push),
  ke-6 halaman DIPUBLIKASIKAN ke wiki GitHub (`ae55c46`, gerbang konten 6/6 PASS di-run ulang sebelum
  tayang, diverifikasi live). Review user kini OPSIONAL (halaman sudah tayang); WP.1 tetap antre;
  Tahap 2 masih ditahan sampai user perintahkan.

