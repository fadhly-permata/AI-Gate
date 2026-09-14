# Lembar Desain — Urutan Manual Anggota Kombo (ganti kolom Priority dengan ▲▼)

- Tanggal: 2026-09-13 · Penulis: ProjectManager (aturan **D6**: lembar desain + ACC user SEBELUM spawn fe-dev)
- Status: **DI-ACC — user pilih (a) ▲▼ + (b) handle geser.** (a) sudah terimplementasi di working tree (uncommitted,
  diaudit PM, gerbang hijau 26 berkas / 646 tes); (b) masih diserahkan ke fe-dev.
- Permintaan user (verbatim): "di halaman combo, ketika edit combo gua gak bisa sortir model" → lalu
  "gak usah sort berdasarkan abjad, jadi bisa di sortir up/down atau pake drag up/down. Jadikan susunan tersebut sebagai
  urutan priority, jadi kolom & field priority bisa di hide aja. Jadi gak usah set manual user-nya.. nah untuk model baru
  selalu diletakkan dibawah/terakhir aja secara default."

## 1. Fakta yang lebih dulu diluruskan (diukur, bukan dugaan)

| Klaim | Kenyataan terukur |
|---|---|
| "daftar anggota ter-sortir abjad" | **Tidak.** Server mengirim anggota urut `priority` naik (`combos_router.py:117`), lalu id naik saat nilainya sama. Dibuktikan di server uji terpisah: empat anggota ditambah berurutan (`zebra-alpha, mike9-xray, bravo-kilo, yankee-tango`, semua prioritas 0) diterima layar dalam urutan **itulah** — bukan abjad. |
| "gak bisa sortir" | **Betul, dan ini lubangnya.** Tidak ada penangan klik judul kolom (`grep comboMembersTable` di `combos.js` = 0), tidak ada tombol naik/turun, tidak ada geser. Satu-satunya cara mengatur urutan = mengetik angka di kolom Priority. |
| Yang benar-benar ter-sortir abjad | **Daftar pilihan model di dalam form tambah anggota** (`combos.js:215-223 sortModelsByName`, dipakai :311/:329/:365). Ini daftar pencarian, bukan susunan kombo. |

Jadi yang mau diubah = **susunan anggota**, dan angka prioritas cukup jadi konsekuensi dari susunan itu. Persis pola yang sudah dipakai di kartu akun penyedia (tahap-3) — user sudah menyetujui pola itu di sana.

## 2. Denah — tabel anggota di modal kombo

```
SEBELUM                                          SESUDAH
Provider | Model | Priority | Weight | ⋮         Provider | Model | Weight | ▲ ▼ | ⋮
  zeta   | gpt-4  |    0     |   1   (hapus)          zeta   | gpt-4  |   1    | ▲· ▼ | (hapus)
  zeta   | opus   |    0     |   1   (hapus)          zeta   | sonnet  |   1    | ▲  ▼ | (hapus)
  zeta   | sonnet  |    3     |   2   (hapus)          zeta   | opus   |   1    | ▲  ▼·| (hapus)
form: Provider|Model|Priority|Weight             form: Provider|Model|Weight
```

- Baris paling atas = dicoba lebih dulu. Di strategi `fallback`, urutan inilah antrean percobaan
  (`combo_routing.py:133,161`); di `load_balance` ia pemecah seri (`:236,268`); di `three_tier` tingkat
  langganan→murah→gratis tetap menang lebih dulu, urutan jadi pemecah di dalam satu tingkat (`:153-157`).
- Kolom **Priority dihapus** dari tabel (`index.html:1123`) **dan** dari form (`:1165-1168`).
- Baris atas: ▲ nonaktif; baris bawah: ▼ nonaktif (`aria-disabled` + alasan, bukan bisu) — sama seperti kartu akun.
- Judul kolom TETAP tidak bisa diklik (sengaja: kalau boleh diurut per nama/bobot, "susunan" jadi tidak bermakna lagi).

## 3. Aturan main (ini yang perlu kamu setujui)

1. **Susunan = prioritas.** Setelah pengguna memindah baris, daftar dinormalisasi jadi `0..n-1` sesuai posisi tampil,
   lalu hanya baris yang nilainya berubah yang di-`PUT /api/combos/{id}/members/{mid}` (endpoint sudah menerima `priority`,
   `combos_router.py:321-322`). PUT dijalankan **berurutan** supaya urutan di server pasti, lalu daftar dibaca ulang —
   persis `moveAccount` di penyedia (`app.js:1366-1412`).
2. **Anggota baru selalu jatuh ke paling bawah.** Yang dikirim = jumlah anggota saat ini (bukan 0). Ini juga menutup cacat
   yang sama di penyedia: dengan default 0, anggota baru menyelonong ke depan antrean.
3. **Combo lama tidak ditulis ulang diam-diam.** Selama pengguna tidak memindah apa pun, nilai `priority` lama tetap
   seperti adanya (bisa 0 semua, bisa 3/7/12 — sah, hanya aneh di layar). Klik ▲▼ pertama menormalkan seluruh daftar
   jadi `0..n-1`; perubahan itu **disimpan ke server saat itu juga** (bukan ditunda ke tombol Simpan).
4. **Mode buffer (kombo yang belum disimpan):** tidak ada API sama sekali — naik/turun cukup memindah susunan di memori,
   dan saat kombo disimpan tiap anggota dikirim dengan `priority` = posisi. Jadi membuat kombo baru dari nol tetap bisa.
5. **Bobot tetap ditampilkan dan tetap manual.** Yang dihapus hanya prioritas. (Bobot = "seberapa sering dipanggil" untuk
   `load_balance`/`latency_cost`; tidak bisa diturunkan dari urutan.)
6. **Daftar pilihan model di form TETAP urut abjad.** Ini daftar pencarian; mengurutkannya dengan cara lain cuma bikin
   sulit menemukan satu nama di ratusan model. Kalau kamu memang ingin daftar itu ikut urutan hasil `/discover` dari
   server, bilang — itu satu baris (`sortModelsByName`).

## 4. Yang TIDAK diubah

`src/backend/**` nol sentuh (API-nya sudah cukup), `combos.js` selain fungsi anggota, halaman lain, dan
mesin routing (`combo_routing.py`). Perilaku penyedia/akun/kartu kombo tidak berubah.

## 5. Drag vs tombol (satu keputusan yang butuh seleramu)

- **Saran gua: ▲▼ saja** — sudah terbukti dipakai di kartu akun, bisa dipakai papan ketik/pembaca layar, dan tidak
  berkelahi dengan gulir layar sentuh.
- **Geser-seret** di ponsel rawan: area baris kombo sempit dan satu layar dengan gulir. Kalau mau, bisa dibuat
  **handle khusus** (ikon `grip` di kiri baris, bukan seluruh baris) sebagai tambahan, bukan pengganti.
- **Keputusan user (2026-09-13): PILIH KEDUA-DUANYA — (a) ▲▼ + (b) handle geser.** (a) sudah ada di working tree
  (uncommitted, diaudit PM: `moveMember` `combos.js:475` sudah menukar→normalisasi `0..n-1`→PUT hanya berubah
  berurutan→reload; `addMember` `:639` `priority = appendPriority()` jatuh paling bawah; gerbang hijau 646 tes).
  **Sisa untuk fe-dev = (b) saja:** tambahkan **handle geser** (`grip` di kiri baris, bukan seluruh baris) yang
  memanggil kontrak yang SAMA persis dengan ▲▼ (`moveMember`/renumber/PUT-only-changed/sequential/reload) — geser
  adalah cara kedua mengubah susunan, BUKAN logika ketiga. ▲▼ tetap ada dan jalan; keduanya harus koeksis tanpa
  bentrok (drag tidak menghapus tombol, tombol tidak menabrak drag).

## 6. Cakupan tes

`combos.test.js` diperbarui + penjaga baru: kolom & field Priority hilang dari markup; ▲▼ menukar posisi dan mengirim
`PUT` hanya untuk baris yang berubah (kasus semua-0 = dua permintaan; kasus `0..n-1` rapi = dua permintaan); batas
atas/bawah `aria-disabled` + beralasan; anggota baru dapat `priority` = jumlah anggota (paling bawah); mode buffer tidak
menyentuh jaringan dan mengirim `priority` per posisi saat disimpan; gagal `PUT` → pesan inline + baca ulang dari server;
bobot masih bisa diedit. Jumlah tes boleh bertambah, nol merah, nol cakupan hilang tanpa pengganti.

## 7. Risiko / batasan jujur

1. Klik ▲▼ = langsung menulis ke server (bukan "tandai dulu, simpan nanti"). Konsisten dengan kartu akun, tapi berarti
   perpindahan tidak bisa dibatalkan kecuali dipindah balik.
2. Kombinasi `three_tier` + urutan manual bisa membingungkan: tingkat menang atas urutan. Teks bantu singkat di kolom
   atas tabel perlu dipasang supaya tidak terasa "kok urutanku tidak dituruti".
3. Uji mata tetap milik user (aturan G3 + J6): tidak ada yang bisa memastikan tampilannya sampai kamu lihat di HP.

## 8. Definition of done (sebelah sini)

Semua §2–§3 terpasang; §4 tidak tersentuh; §6 hijau penuh di gerbang PM (`node node_modules/.bin/vitest run`,
acuan sekarang 26 berkas / 625 tes); nol kunci i18n mati (kunci `combos.member.priority` dihapus dari 7 kamus kalau
memang jadi tak terpakai); nol warna hex baru; `git diff --check` bersih; `git status --short` hanya `src/frontend/**`.
