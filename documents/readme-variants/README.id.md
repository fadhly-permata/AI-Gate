# aigate 🚪

Satu pintu buat semua penyedia AI yang lu pakai. Satu tempat main di mana
agent AI yang ngetik kode buat lu. Dan semuanya bisa lu jalanin dari HP.

Nggak pakai Docker, nggak pakai akun cloud — aigate itu aplikasi Python
biasa yang hidup di komputer atau HP Android lu sendiri. API key dan
riwayat pemakaian nyimpen lokal, di perangkat lu juga.

[English](../../README.md)

## Bayangin gini ☕

Lu lagi di KRL pulang kerja, HP di tangan, browser kebuka. Side project
lu terus-terusan error. Lu ketik satu kalimat ke agent lu, gas — sebuah
tab hidup dan mulai benerin error satu per satu: jalanin test, baca
gagalannya, tambal, ulang. Lu tinggal ngeliatin dari kursi sambil lampu
kota lewat di jendela. Pas error terakhir beres, semua fix masuk ke
branch utama dan branch kerjanya hilang sendiri. Semuanya dari HP, di
tab browser.

## Yang bikin beda ✨

- **Satu pintu buat semua penyedia AI.** Sambungkan akun penyedia lu
  sekali, aigate yang ngatur jalur request-nya — kalau salah satu mati
  atau kuotanya habis, request tetep kejawab, nggak gagal begitu aja.
- **24 tool AI coding, sekali ketuk.** Jalankan asisten coding AI
  populer langsung ke tab terminal bawaan aigate. Belum kepasang? Dia
  ngusulin perintah install yang beneran jalan di perangkat lu.
- **Loop self-heal yang bisa lu tonton.** Arahin ke error project lu:
  dia bikin branch, jalanin agent di tab yang keliatan, benerin warning
  satu per satu, lalu merge balik pas udah lolos. Nggak ada yang
  disembunyiin — dan dia nggak pernah pura-pura sukses kalau aslinya
  gagal.
- **Beneran jalan di HP.** aigate terpasang dan jalan native di Termux
  Android — tanpa compiler, tanpa build tools, nggak ada yang cuma bisa
  di desktop.
- **Privat secara default.** API key dan riwayat lu itu data lokal di
  perangkat lu. Nggak ada yang ngobrol ke cloud kecuali penyedia AI yang
  lu pilih sendiri.
- **Nyaman dipakai.** Tema terang dan gelap, 7 bahasa, dan UI yang tetap
  enak di layar kecil.

## Coba 60 detik ⏱️

```bash
python run.py
```

Buka **http://localhost:8080** — jalan pertama ngambil beberapa paket
Python yang dibutuhin, langsung nyala.

Port-nya lagi kepake? Pindah aja:

```bash
AIGATE_PORT=9090 python run.py
```

## Jalan di HP 📱

Pasang Termux di Android, taruh aigate di dalamnya, dan jalankan sama
kayak di laptop. Yang agak tricky di HP itu masang *tool coding*-nya —
Android ngeresolve paket beda dari desktop — makanya aigate tahu kapan
dia lagi di Termux dan ngusulin perintah install yang beneran jalan di
sana, misalnya paket sistem, bukan versi desktop.

aigate sudah dites di Linux, Windows, dan Android (Termux) — dan bisa
pake distro Linux penuh di dalam HP lu, kalau lu suka trik begitu.

## Detail teknisnya di mana? 📚

Semua soal API, arsitektur, opsi setup, dan dokumentasi testing ada di
[wiki](https://github.com/fadhly-permata/AI-Gate/wiki) — README ini tetap
santai, wiki yang ngomongin detailnya.

## Status 📌

aigate adalah tool personal yang lokal-dulu dan masih aktif dikembangin,
sudah dites di Linux, Windows, dan Android (Termux). Coba aja, oprek
sepuasnya — kalau ada yang nyangkut, bilang gue di mana encernya.

---

Dibuat dengan ❤️ oleh Fadhly Permata
