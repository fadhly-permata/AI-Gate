# Handover — WL.2a: sebarkan 1 kalimat lisensi ke 7 varian README

**Dari:** PM · **Untuk:** business-analyst · **Tanggal:** 2026-09-08
**Lisensi resmi sudah masuk `main` (MIT, PR #11 merged `785845a`)** → kalimat "free and open source"
sekarang BOLEH dan HARUS ada di semua varian, biar isinya gak beda-beda antar bahasa.

## WRITE SCOPE — hanya 7 file ini
`documents/readme-variants/README.{id,ru,nl,ja,zh,zh-tw,hi}.md`
JANGAN sentuh `README.md` (Inggris sudah beres & sudah merged). JANGAN sentuh file lain.

## Yang harus disampaikan (FAKTA — sama persis di semua bahasa)
1. aigate itu gratis dan sumber kodenya terbuka, **tidak ada paket berbayar / fitur yang dikunci**.
2. Di bawah lisensi ini **siapa pun bebas menyalin** kodenya.
3. Makanya **satu-satunya rumah resmi aigate** adalah alamat ini:
   `https://github.com/fadhly-permata/AI-Gate`

## Versi Inggris yang sudah di-ACC (jadi acuan MAKNA, BUKAN acuan kalimat)
> It's free and open source — no paid tier, and nothing locked behind a plan.
> Anyone may copy this code, so the one true home of aigate is
> [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate).

## RUMUSAN TIAP BAHASA — baca dulu bagian "PEMBETULAN WAJIB"
Kalimat di bawah ini DRAF PM. Beberapa di antaranya baru gue koreksi; sisanya tetap **tugas lu**
buat bikin kedengeran natural buat penutur asli, bukan hasil terjemahan. Struktur dan urutan informasi
yang wajib sama: **gratis+terbuka → tidak ada jebakan biaya → bebas disalin → makanya cuma satu
yang resmi**.

- **id:** "Kode aigate gratis dan terbuka — tidak ada paket berbayar, tidak ada fitur yang dikunci.
  Siapa pun bebas menyalin kode ini, jadi satu-satunya rumah resmi aigate cuma di
  [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate)."
- **ru:** "aigate бесплатен, код открыт — платных тарифов нет и ничего не спрятано за подпиской.
  Этот код может скопировать кто угодно, поэтому единственный официальный дом aigate —
  [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate)."
- **nl:** ⚠️ **JANGAN pakai kata "thuis" (rumah) secara kiasan** — dalam Belanda itu terasa aneh
  untuk alamat web. Pakai "de officiële plek"/"hier". Draf: "aigate is gratis en open source — er is
  geen betaald abonnement en niets zit achter een betaalmuur. Wie dat wil mag deze code kopiëren, dus de enige
  officiële plek voor aigate is
  [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate)."
  (kata ganti objek "m't" sudah dibuang — jangan kembalikan)
- **ja:** ⚠️ "自由なライセンス" itu **tidak netral** — itu klaim soal jenis lisensi. Ganti jadi
  "自由にコピーできます". Draf: "aigate は無料で、ソースも公開されています。有料プランや、課金しないと
  使えない機能はありません。ライセンス上誰でもコードをコピーできるため、aigate の公式な配布先は
  [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate) のひとつだけです。"
- **zh (sederhana):** "aigate 免费且开源——没有付费套餐，也没有功能被锁在订阅后面。任何人都可以复制这份
  代码，所以 aigate 唯一的官方来源就是
  [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate)。"
- **zh-tw:** WAJIB bentuk tradisional (cek: 免費/複製/來源/官網), jangan lolos satu pun karakter
  sederhana dari draf zh di atas.
- **hi:** "aigate मुफ़्त है और इसका कोड सबके लिए खुला है — कोई पैड टारिफ़ नहीं, कोई सुविधा लॉक नहीं।
  यह कोड कोई भी कॉपी कर सकता है, इसलिए aigate का एकमात्र आधिकारिक पता यही है:
  [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate)।"

## ⚠️ PEMBETULAN WAJIB (kesalahan yang sudah gue tangkap di draf atas, jangan diulang)
1. **Jangan menulis "salinannya harus tetap terbuka / wajib buka kode hasil turunan".** MIT itu
   lisensi permisif: orang **boleh** menutup kode turunannya. Yang benar cuma: "siapa pun bebas
   menyalin". Kalau draf lu menyiratkan copyleft → itu SALAH secara hukum.
2. **URL tidak diterjemahkan, tidak dipendekkan, tidak diubah kapitalisasinya.** Teks tampilan dan
   tujuan tautan keduanya `github.com/fadhly-permata/AI-Gate` /
   `https://github.com/fadhly-permata/AI-Gate`.
3. **DILARANG menyebut nama lisensi (MIT) atau nomor hukum** di README varian. Cukup "gratis dan
   sumbernya terbuka". (GitHub sudah menampilkan label "MIT" sendiri.)
4. `aigate` huruf kecil; jangan "Aigate"/"AI-Gate" di teks (kecuali di dalam URL).
5. **Jangan menulis "repo ini" / "ini rumahnya"** — kalimat ikut ter-fork jadi ambigu (R45).
   Selalu sertakan alamatnya.
6. Letak: sisip 2–3 baris **setelah paragraf pembuka masing-masing varian** (yang ngomong Python
   lokal/kunci tetap di alat user), sebelum baris bahasa 🌐. Paragraf yang sudah ada **jangan diubah
   satu karakter pun** — murni penyisipan, biar bisa diverifikasi dengan `git diff`.
7. Nada tiap bahasa tetap seperti file-nya sekarang (id: kamu, kasual-hangat; ru: вы; nl: je/jij;
   ja: です・ます; zh/zh-tw: netral-ringan; hi: आप). Jangan campur register.

## Definisi selesai
- [ ] 7 file berubah, **murni penyisipan** (diff tidak menghapus baris lama).
- [ ] Tiap bahasa terbaca asli, bukan calque Inggris (R43).
- [ ] Tidak ada klaim copyleft yang salah (poin 1).
- [ ] URL identik byte di 7 file.
- [ ] Kembaliin struk: kalimat final tiap bahasa + bagian yang lu rasa masih kurang natural.
