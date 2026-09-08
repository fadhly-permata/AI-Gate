# Lembar fakta C — halaman 7 `Terminal.md` & halaman 8 `Providers-and-Combos.md`
**PM → business-analyst · 2026-09-08.** Sumber fakta = file INI SAJA (R44). Branch `docs/wiki`.
Tulis 2 file: `documents/pm/wiki-drafts/Terminal.md` dan
`documents/pm/wiki-drafts/Providers-and-Combos.md`.
Baca dulu `Home.md` + `Quick-Start.md` di `documents/pm/wiki-drafts/` buat nyamain suara.

# HALAMAN 7 — `Terminal.md`
Fungsi: terminal di dalam browser itu fitur paling bikin orang kagok ("bisa gitu?"). Jual geraknya:
dulu butuh SSH/aplikasi terpisah, sekarang satu tab.

## Fakta yang nyata ada (jangan lebih)
- Terminal **sungguhan** (bukan gambar terminal): banyak tab, tiap tab = sesi nyata di perangkat itu.
- Kontrol yang tersedia di layar: **layar penuh**, **pecah layar** (sisi-sebelah), **tahan-nyala**
  (layar HP gak tidur sementara kerja), **tombol mengambang** di pojok area terminal, dan menu
  kecil buat pilihan yang jarang dipake.
- **Tempel**: isi clipboard disuntikkan ke sesi yang aktif, dan fokus **balik otomatis** ke terminal
  sehingga user bisa langsung lanjut ngetik.
- **Gulir & usap**: roda mouse dan gestur usap trackpad/jari jalan. Pada aplikasi TUI (layar penuh
  model editor di terminal), usap diterjemahkan jadi input gulir aplikasi itu, arah natural
  (jari ke atas = konten terbaru), lepas jari mengikuti 1:1. Riwayat gulir ±5000 baris.
- Alat coding yang diluncurin dari dalam aplikasi **buka di tab baru** — itu jalur kerjanya halaman
  [CLI Tools](CLI-Tools).
- Jendela kerja developer (`AIGATE_DEV=1`) menambahkan **jendela log** dan alat bantu. Sekali kalimat,
  jangan jadiin fokus halaman.
- **Self-Heal — boleh dan harus dijelaskan apa adanya** (user sudah publishes ini di README):
  arahkan aplikasi ke error proyeknya → dia **bikin branch**, **menjalankan agen coding di tab
  yang hidup** (kelihatan, bukan proses tersembunyi), memperbaiki peringatan/error satu-satu
  dengan mengulang pengecekan, menghapus catatan yang sudah beres, lalu **menggabungkan ke cabang
  utama kalau semuanya lulus**. Dia **tidak pernah** mengaku sukses kalau jalannya gagal; kalau
  perintahnya keluar dengan galat, itu ditandai gagal. Butuh: agen coding yang sudah terpasang
  (bisa dipilih) + proyek. **Tulis risikonya**: dia benar-benar menulis kode dan menggabungkan
  branch, jadi pake itu di proyek yang bisa kamu periksa sendiri. Jangan tulis angka keberhasilan
  atau janji.
- Batas yang jujur: terminalnya butuh sesi di perangkat tempat aigate jalan; kalau perangkatnya
  tidur/layar mati, sesi bisa putus → itu sebabnya ada tahan-nyala. Jangan ngarang perilaku lain.

Panjang 380–480 kata.

# HALAMAN 8 — `Providers-and-Combos.md`
Fungsi: ini halaman konsep. Kalau pembaca cuma baca 1 halaman selain Quick Start, harusnya ini.
Jelasin **mental model**-nya pakai bahasa dapur, bukan arsitektur.

## Rantainya (urut, ini yang harus kebaca)
1. **Penyedia** = akun/alamat yang menjawab (kunci + alamat dasar). Alamat dasar boleh menunjuk
   **perangkat sendiri** (mis. layanan model lokal yang melayani format OpenAI di port 11434) →
   di sinilah skenario "jalan tanpa internet sama sekali" jadi nyata. Tulis sebagai kemungkinan,
   bukan fitur khusus yang kita klaim punya.
2. **Kombinasi (combo)** = sekelompok penyedia yang ditata bareng, masing-masing punya **prioritas**
   dan **bobot**, plus satu **strategi**.
3. **Titik layanan (endpoint)** = alamat lokal yang diberikan kombinasi itu ke alat/aplikasi lain;
   bisa dikasih kunci akses sendiri, host/port sendiri, dan (opsional) **proxy keluar** sendiri.

## Tiga strategi (nama di layar: fallback / load_balance / latency_cost — jelaskan tanpa kode)
- **Cadangan berurutan**: coba yang prioritas teratas; kalau penyedia ngambek/limit/mati, lanjut ke
  berikutnya; kalau SEMUA gagal, pesan gagal terakhir yang keluar (gak nyembunyiin error).
  Saat penyedia lagi kena limit/kuota/masalah akses, alat ini juga **coba akun lain dari penyedia
  yang sama** dulu sebelum pindah penyedia.
- **Bagi rata berbobot**: dipilih acak sesuai bobot → buat nyebar beban ke beberapa akun.
- **Pilih yang paling hemat**: bobot dipakai sebagai taksiran mahal/murah, diambil yang paling ringan,
  **satu kali percobaan** tanpa ulang → kalau yang murah itu mati, dia gak otomatis pindah
  (perbedaan penting! jangan disamarkan).
- Catatan kuota: tiap penyedia bisa diberi **batas kuota + jangkaunya**; pemakaian kerekam dan bisa
  dilihat (halaman analisis). Jangan klaim pemblokiran otomatis kalau itu belum jelas — cukup
  "kelihatan, dan dipakai buat milih".
- Catatan penting buat awam: **ganti penyedia/model itu satu tempat**, dan semua alat yang udah
  disambung ke alamat aigate ikut pindah — itu intinya.

Panjang 400–520 kata (halaman konsep, boleh agak panjang, tapi tetap satu ide per kalimat).

## Batas dua halaman (berlaku semua)
Inggris kasual, awam, emoji di heading; heading `#` lalu `##`; produk `aigate` kecil.
DILARANG: path `src/**`/`documents/**`, nama fungsi/modul/tabel/kolom/variabel internal selain
`AIGATE_DEV`/`AIGATE_PORT` yang memang diketik user, nomor internal/ADR, kata "MIT", "this repo"
(R45), "untested/experimental" (R42), nama tabel basis data, jumlah baris/commit.
Jangan menyebut nama penyedia model lokal tertentu sebagai rekomendasi; cukup "layanan model lokal
yang berbicara bahasa OpenAI".
Tautan internal hanya ke: Home, Quick-Start, Interfaces, Configuration-and-Keys, CLI-Tools,
OpenAI-API, Terminal, Providers-and-Combos. Kredit terakhir: "Made with ❤️ by Fadhly Permata".
JANGAN git commit/push.
