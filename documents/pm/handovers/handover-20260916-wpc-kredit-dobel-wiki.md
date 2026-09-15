# Handover — WP-C: hapus "kredit dobel" di naskah wiki (public-writer)

Tanggal: 2026-09-16 | Owner: **public-writer** | PM: ProjectManager
Batas tulis: `documents/pm/wiki-drafts/**` HANYA berkas naskah konten (lihat daftar). DILARANG ubah berkas lain.

## Masalah (kredit dobel)
Baris kredit `Made with ❤️ by Fadhly Permata` saat ini ada di DUA tempat:
1. Inline di bagian bawah 8 naskah konten wiki.
2. Di `_Footer.md` (baris 1).

Wiki GitHub me-render `_Footer.md` otomatis di BAWAH SETIAP halaman. Begitu `_Footer.md` diterbitkan, pembaca akan melihat kredit **dua kali** per halaman (sekali inline, sekali dari footer otomatis).

## Putusan PM (default, sudah dicatat di memory-bank)
Kredit cukup **SATU** tempat = `_Footer.md`. Maka: **hapus baris inline dari 8 naskah konten**, JANGAN sentuh `_Footer.md`/`_Sidebar.md`.

## Tugas (edit kecil & deterministik)
Dari 8 berkas berikut, HAPUS baris yang persisnya berisi `Made with ❤️ by Fadhly Permata` (baris berdiri sendiri, biasanya dekat akhir berkas):
1. `documents/pm/wiki-drafts/Home.md` (baris ±34)
2. `documents/pm/wiki-drafts/Quick-Start.md` (baris ±83)
3. `documents/pm/wiki-drafts/Interfaces.md` (baris ±30)
4. `documents/pm/wiki-drafts/Configuration-and-Keys.md` (baris ±31)
5. `documents/pm/wiki-drafts/Providers-and-Combos.md` (baris ±41)
6. `documents/pm/wiki-drafts/Terminal.md` (baris ±33)
7. `documents/pm/wiki-drafts/CLI-Tools.md` (baris ±33)
8. `documents/pm/wiki-drafts/OpenAI-API.md` (baris ±51)

## Larangan
- JANGAN ubah `_Footer.md` (kredit di situ TETAP, itu satu-satunya).
- JANGAN ubah `_Sidebar.md`.
- JANGAN menulis ulang prosa/paragraf lain; HANYA buang baris kredit itu (+ rapikan sisa newline agar tidak ada 2 baris kosong menggantung di akhir).
- JANGAN ubah rujukan `github.com/fadhly-permata/AI-Gate` di dalam prosa (mis. Home.md baris ±7) — itu bukan baris kredit, biarkan.

## Definition-of-done
- `grep -rn "Made with" documents/pm/wiki-drafts/` menghasilkan HANYA 1 kejadian: `.../\_Footer.md:1`.
- Diff = murni penghapusan baris kredit di 8 berkas, tanpa perubahan konten lain.
- Tiap berkas tetap Markdown valid (heading/tautan utuh).

## Receipt yang diharapkan
Daftar 8 berkas + jumlah baris dihapus per berkas; konfirmasi grep; open question (kalau ada).
