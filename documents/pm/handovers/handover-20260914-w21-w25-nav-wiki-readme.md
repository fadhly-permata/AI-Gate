# Handover — W2.1 + W2.5: navigasi wiki + tautan README ke halaman nyata

**PM → public-writer** · 2026-09-14 14:07 · branch: `feat/wp1-python-check` (jangan pindah branch)
**Sumber tugas:** `documents/plan/wiki-backlog.md` §Tahap 2 item **W2.1** dan **W2.5**.
Dua item kecil, satu pemilik, satu berkas bisa bertabrakan → dikerjakan bareng dalam satu kali jalan.

## Bagian 1 — W2.1: navigasi wiki (`_Sidebar.md` + `_Footer.md`)

### Konteks nyata (sudah PM cek, jangan cek ulang)
Wiki publik sudah TAYANG 8 halaman (rilis `ae55c46`): `Home`, `Quick-Start`, `Providers-and-Combos`,
`Interfaces`, `Terminal`, `CLI-Tools`, `Configuration-and-Keys`, `OpenAI-API`. Sumber naskah ada di
`documents/pm/wiki-drafts/` dengan nama berkas persis sama (`.md`, tanda hubung).
Sekarang wiki **tidak punya navigasi samping maupun footer** — orang mendarat di satu halaman lalu buntu.

### Yang harus dibuat
- `documents/pm/wiki-drafts/_Sidebar.md` — daftar tautan ke 8 halaman di atas, urutan membaca masuk akal
  (mulai dari Home → Quick-Start → dst.). Judul kelompok singkat, boleh emoji secukupnya.
- `documents/pm/wiki-drafts/_Footer.md` — satu-dua baris: kredit "Made with ❤️ by Fadhly Permata" (persis,
  sudah di-ACC user) + tautan balik ke Home + tautan ke halaman kontribusi/beranda repo bila perlu.
- Tautan internal wiki pakai **nama halaman persis** (mis. `[Quick Start](Quick-Start)`), bukan path folder,
  bukan URL absolut ke `documents/**`. Jangan menulis jumlah baris/commit/file repo (basi).
- Nama produk: `aigate` huruf kecil. Nada: Inggris kasual, pembaca awam, netral budaya.
- DILARANG menulis apa pun ke wiki asli / push — kamu hanya menyiapkan naskah di folder draf.

## Bagian 2 — W2.5: README + varian bahasa

### Masalah nyata (bukti)
`README.md:75-77` sekarang menulis "The API, architecture, setup options, and testing docs all live in the
[wiki](https://github.com/fadhly-permata/AI-Gate/wiki)". Kalimat itu menunjuk wiki **yang kini sudah berisi**,
tapi tidak menyebut ada berapa dan apa saja, dan menyebut "architecture"/"testing" yang **tidak** ada
halamannya (halaman lanjutan baru diputuskan user → item W2.3, masih terbuka). Jadi kalimat itu sekarang
melebihkan klaim.

### Yang harus dibuat
1. `README.md`: perbaiki blok itu jadi singkat + jujur: tunjuk **halaman wiki yang benar-benar sudah ada**
   (8 halaman di atas), boleh daftar mini atau 1 kalimat + 3–4 tautan paling berguna (Quick Start,
   Providers & Combos, Terminal, CLI Tools). Jangan menyebut arsitektur/testing kalau halamannya belum ada.
   Jangan tempel jumlah baris/commit. Kalimat penutup yang sudah di-ACC user **jangan diubah**
   ("Try it, break it, and tell me where it hurts." + baris kredit terakhir).
2. `documents/readme-variants/*.md` (7 varian: id, ja, nl, ru, zh, zh-tw, hi): terapkan perubahan yang sama,
   **ditulis ulang dalam bahasa target**, bukan diterjemahkan kata per kata. Alamat URL tetap seperti adanya.
   Nama produk `aigate` kecil. Cek tiap varian punya blok padanan di tempat yang wajar.
3. Konsistensi: nama halaman yang ditaut sama persis dengan nama halaman wiki; URL wiki absolut.

## Batas tulis (STRIK)
- WRITE: `documents/pm/wiki-drafts/**`, `README.md`, `documents/readme-variants/**`.
- READ: `documents/plan/wiki-backlog.md`, `documents/plan/wiki-plan.md`, `documents/pm/memory-bank.md`
  (bagian fakta wiki + konfirmasi maintainer), isi halaman wiki hasil rewrite di `wiki-drafts/` (biar nada
  dan istilah nyambung).
- DILARANG tulis: `src/**`, `tests/**`, `documents/pm/*.{md}` (catatan PM), `.opencode/**`
  (skrip publisher sedang dikerjakan agen lain ronde ini), berkas lain di root.

## Gerbang selesai (kamu jalankan sendiri)
- [ ] `_Sidebar.md` memuat 8 halaman, tidak ada tautan ke halaman yang belum ada. Verifikasi: cocokkan
      daftarmu vs isi folder `wiki-drafts/` (8 file `.md`) — tampilkan hasilnya.
- [ ] Tiap tautan internal: nama hedef = nama berkas nyata (bedanya kapital/tanda hubung = tautan mati).
- [ ] `README.md` + 7 varian: tidak ada lagi klaim halaman yang belum ada; tidak ada path internal
      (`documents/`, `src/`) yang bocor ke materi publik.
- [ ] Semua varian tetap punya struktur yang sama (judul, blok instalasi, penutup) — jangan ada varian
      yang kehilangan bagian karena diedit.
- [ ] Sebutkan jumlah kata tiap berkas baru, biar PM bisa bandingkan batas gaya.
- [ ] `git status --porcelain` sebelum kirim: hanya berkas dalam write-rootmu yang boleh berubah.

## Output yang PM minta (receipt)
1. Berkas dibuat/diubah + apa berubah di tiap berkas (baris sebelum → sesudah untuk README).
2. Isi persis `_Sidebar.md` dan `_Footer.md` (tempel penuh, biar PM baca tanpa buka berkas).
3. Bukti gerbang di atas (perintah + hasil).
4. Daftar istilah/keputusan bahasa yang kamu ambil di tiap varian (mis. "terminal" dipinjam atau tidak).
5. Kalau ada klaim yang kamu tidak yakin benar: TANDA TANGAN `MERAGU` + alasan, jangan dikarang.
6. JANGAN commit / push / publish ke wiki.
