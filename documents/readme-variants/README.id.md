# aigate 🚪

aigate adalah satu pintu untuk semua provider AI yang kamu pakai,
sekaligus tempat agent AI mengerjakan koding untukmu — dan semuanya bisa
dijalankan dari HP.

Bentuknya aplikasi Python biasa: tanpa Docker, tanpa akun cloud. API key
dan riwayat pemakaian tersimpan di perangkat sendiri.

[English](../../README.md)

## Sebelum tidur ☕

Kamar sudah gelap, HP sudah di tangan, tapi tiba-tiba teringat project
yang error dari sore. Buka browser, tulis satu perintah singkat, dan
agent mulai bekerja di satu tab: error diperbaiki satu per satu, dites
ulang, sampai bersih. Hasilnya masuk ke branch utama dengan sendirinya.
Kamu tinggal menutup browser dan lanjut tidur — besok paginya kode sudah
rapi.

## Yang bikin beda ✨

- **Semua provider lewat satu pintu.** Hubungkan akun-akun provider ke
  aigate, lalu permintaan kamu diarahkan otomatis. Kalau satu provider
  sedang mati atau kuotanya habis, permintaan diteruskan ke provider
  lain.
- **24 tool AI coding, tinggal ketuk.** Asisten-asisten coding populer
  dijalankan langsung dari tab terminal bawaan aigate. Kalau salah
  satunya belum terpasang, aigate menampilkan perintah pasang yang cocok
  untuk perangkat yang dipakai.
- **Perbaikan otomatis yang terlihat.** Arahkan ke project yang error:
  aigate membuat branch, menjalankan agent di tab yang bisa kamu buka
  kapan saja, memperbaiki error satu per satu, lalu meng-merge hasil
  yang sudah beres. Sistem ini tidak pernah mengaku sukses kalau
  pengerjaannya gagal.
- **Benar-benar jalan di HP.** Di Android, aigate terpasang dan berjalan
  native di Termux — tanpa compiler, tanpa build tools.
- **Datamu tetap di perangkat.** API key dan riwayat permintaan disimpan
  lokal. Yang keluar ke internet hanya permintaan ke provider yang kamu
  pilih sendiri.
- **Nyaman di layar kecil.** Tema terang dan gelap, tujuh bahasa, dan
  tampilan yang enak dipakai dari HP maupun laptop.

## Coba 60 detik ⏱️

```bash
python run.py
```

Setelah itu buka **http://localhost:8080**. Saat pertama kali dijalankan,
aigate mengunduh sendiri paket Python yang dibutuhkan.

Kalau port 8080 sudah dipakai:

```bash
AIGATE_PORT=9090 python run.py
```

## Jalan di HP 📱

Di Android, aigate berjalan di Termux dengan cara yang sama seperti di
laptop: jalankan, lalu buka lewat browser. Yang sering bermasalah di HP
justru tool coding-nya — Android punya aturan pemasangan paket yang
berbeda dari laptop. aigate mengenali Termux, sehingga perintah pasang
yang ditampilkan adalah perintah yang benar-benar jalan di perangkat itu.

Sudah diuji di Linux, Windows, dan Android (Termux), termasuk untuk
menjalankan distro Linux penuh di dalam HP.

## Detail teknis ada di wiki 📚

Penjelasan lengkap soal API, arsitektur, pilihan pemasangan, dan
dokumentasi pengujian ada di
[wiki](https://github.com/fadhly-permata/AI-Gate/wiki). README ini cukup
gambaran besarnya saja.

## Status 📌

aigate adalah proyek personal yang terus dikembangkan dengan prinsip
semua data di perangkat sendiri, dan sudah diuji di Linux, Windows, serta
Android (Termux). Silakan dicoba, dibongkar, dan dilaporkan kalau ada
yang rusak.

---

Dibuat dengan ❤️ oleh Fadhly Permata
