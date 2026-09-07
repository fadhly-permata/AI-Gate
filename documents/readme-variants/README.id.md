# aigate 🚪

aigate jadi satu pintu untuk semua provider AI yang kamu pakai. Di
dalamnya ada agent AI yang nulis kode buat kamu. Semuanya bisa kamu
jalankan dari HP.

Bentuknya aplikasi Python biasa: tanpa Docker, tanpa akun cloud. aigate
menyimpan API key dan riwayat pemakaian di perangkat kamu sendiri.

[English](../../README.md)

## Sebelum tidur ☕

Kamar sudah gelap, HP sudah di tangan, tapi tiba-tiba teringat project
yang error dari sore. Buka browser, tulis satu instruksi singkat, dan
agent mulai bekerja di satu tab: dia memperbaiki error satu per satu,
mengulang tes, sampai bersih. Hasilnya masuk ke branch utama dengan
sendirinya. Kamu tinggal menutup browser dan lanjut tidur — besok
paginya kode sudah rapi.

## Yang bikin beda ✨

- **Semua provider lewat satu pintu.** Hubungkan semua akun provider ke
  aigate, lalu aigate mengarahkan request kamu secara otomatis. Kalau
  satu provider sedang bermasalah atau kuotanya habis, aigate mengirim
  request ke provider lain.
- **24 tool AI coding, tinggal ketuk.** aigate menjalankannya langsung
  di tab terminal bawaannya. Kalau salah satunya belum terpasang, aigate
  menampilkan perintah pasang yang cocok untuk perangkat itu. Daftarnya
  masih terus dikembangkan — versi berikutnya bisa menambah atau
  mengubah tool yang tersedia.
- **Perbaikan otomatis yang terlihat.** Arahkan aigate ke project kamu
  yang lagi error. Dia membuat branch, menjalankan agent di tab yang
  bisa kamu buka kapan saja, memperbaiki error satu per satu, lalu
  meng-merge hasilnya. aigate tidak pernah mengaku selesai kalau
  prosesnya gagal.
- **Benar-benar jalan di HP.** Di Android, aigate bisa dipasang dan
  jalan langsung di Termux — tanpa compiler, tanpa build tools.
- **Data kamu tetap di perangkat.** API key dan riwayat request hanya
  ada di perangkat kamu. Hanya request ke provider pilihan kamu yang
  keluar ke internet.
- **Nyaman di layar kecil.** Mode terang dan gelap, tujuh bahasa, dan
  tampilan yang enak dipakai dari HP maupun laptop.

## Coba 60 detik ⏱️

```bash
python run.py
```

Setelah itu buka **http://localhost:8080**. Saat pertama dijalankan,
aigate otomatis mengunduh paket Python yang dibutuhkan.

Kalau port 8080 sudah terpakai:

```bash
AIGATE_PORT=9090 python run.py
```

## Jalan di HP 📱

Di Android, aigate jalan di Termux, sama seperti di laptop: jalankan,
lalu buka lewat browser. Bagian yang sering bermasalah di HP justru
tool coding-nya. Android punya aturan pasang paket yang berbeda dari
laptop. aigate mengenali Termux, jadi perintah pasang yang muncul
dijamin benar-benar jalan di perangkat itu.

aigate sudah diuji di Linux, Windows, dan Android (Termux), termasuk
untuk menjalankan distro Linux penuh di dalam HP.

## Detail teknis ada di wiki 📚

Penjelasan lengkap soal API, arsitektur, cara memasang, dan cara
menjalankan tes ada di
[wiki](https://github.com/fadhly-permata/AI-Gate/wiki). README ini
cukup gambaran besarnya saja.

## Status 📌

aigate adalah proyek personal yang terus dikembangkan. Semua datanya
tetap di perangkat sendiri. aigate sudah diuji di Linux, Windows, dan
Android (Termux). Coba aja, bongkar sepuasnya, dan kamu boleh laporin
kalau ada yang rusak.

---

Dibuat dengan ❤️ oleh Fadhly Permata
