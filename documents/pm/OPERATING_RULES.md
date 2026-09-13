# PM Operating Rules v2 (konsolidasi 10 tema)
Dihasilkan 2026-09-10 dari 52 rule v1 (52.698 byte) — teks lama utuh: `documents/pm/archive/OPERATING_RULES-v1-52rules.md`.
Desain + peta lama->baru + tabel konflik: `documents/analysis/2026-09-10-rules-consolidation.md`.
Rule kanonik agen ada di `.opencode/rules/*.md` — tidak diulang di sini (DRY).
Tambah rule baru = 1 baris perintah + 1 baris alasan; pelajaran panjang masuk arsip.
Sitatan `[R#]` = ID lama: teks lengkapnya di arsip v1; peta lama->baru di `documents/analysis/2026-09-10-rules-consolidation.md` §1.

## A — Routing, delegasi, siklus agen
A1 Semua input user masuk PM dulu; main thread dilarang sentuh `src/**`|`tests/**`|`documents/**`. Alasan: eksekusi tanpa rute = tanpa boundary/receipt. [R29] → `AGENTS.md:3-18`, `.opencode/rules/request-routing.md`.
A2 PM tidak menulis kode/test. Butuh keahlian → spawn spesialis + handover (goal, `file:line`, scope, DoD). Verifikasi & integrasi tetap milik PM. [R21]
A3 Tiap agen hanya tulis di scope-nya; lintas scope = receipt ditolak. Detail roster: `.opencode/rules/agent-boundaries.md`. [R3]
A4 Handover = ≤25 baris untuk task ≤5 file; peta `file:line` wajib; jangan minta file laporan `.md` untuk task kecil; jangan bikin FILE baru untuk mencatat (append baris boleh). [R38]
A5 Sub-agent + skill dibuat berbarengan saat dibutuhkan, tidak pernah dihapus. Setelah generate: WAJIB minta user restart opencode; dilarang diam-diam fallback ke agen `general`. [R1,R2,R4] → `.opencode/rules/agent-generation.md`.
A11 `documents/pm/**` = memo kerja PM (rekaman titik-waktu, append-only): blok/entri lama jangan ditulis-ulang, jangan dihapus,
   jangan "dirapikan" isinya; koreksi = entri/blok BARIS yang menyebut yang lama. Boleh diedit hanya baris `mode:` `state.md`
   + typo; isi catatan/status/keputusan lama haram. Detail: `.opencode/skills/pm-orchestration/SKILL.md` §6 + `task-report.md`
   (laporan diisi maju, tidak dirombak).
A12 Fakta dunia luar (status PR/branch/isu/merge) = rekaman titik-waktu: boleh dikutip sebagai "per tanggal X", TAPI sebelum
   jadi dasar kerja WAJIB dicek ulang ke sumbernya (API / `git fetch`) pada sesi itu; kedaluwarsa → tulis koreksi + perbarui
   baris `updated:` `state.md`, jangan diulang diam-diam sebagai kebenaran aktif. → `.opencode/rules/no-hallucination.md`.

## B — Penempatan & higienitas berkas
B1 Semua dokumen proyek di `documents/**`, bukan `docs/**`. [R5]
B2 Artefak opencode (command/rule/skill/agent) di `.opencode/**` proyek; global hanya bila user menyebut "global". [R6]
B3 Laporan tugas di `.opencode/reports/[yyyymmdd]/[jenis]/[hhmm]_[slug].md`; root `reports/**` dilarang.
   HANYA PM yang menulis berkas laporan — sub-agent mengembalikan receipt di sesi, bukan file laporan.
   [R23] → `.opencode/rules/task-report.md`.
B4 Dilarang file/folder baru di root repo; artefak masuk rumah yang sudah ada; belum ada tempat → tanya user. [R33]
B5 File scratch/temp/one-off wajib dihapus setelah dipakai; produk (`src/**`, `documents/**`, `.opencode/reports/**`) dikecualikan. [R8]

## C — Command & tool
C1 Command hemat usaha user: parameter yang bisa dideteksi otomatis jangan ditanya; field auto (ID, tanggal, severity) jangan diketik. [R7] → `.opencode/rules/commands.md`.
C2 "install X" untuk tool yang SUDAH ada = pastikan callable, bukan menambah dependency/config proyek. "init X" = jalankan tool-nya pada proyek ini. [R26]
C3 User menunjuk tool via URL repo → verifikasi identitas + cara install dari repo itu sebelum bertindak; package se-nama bukan jawaban. [R27]
C4 Cari lokasi kode lewat kanal graf dulu, baru baca file spesifik; dilarang broad grep/glob seluruh repo.
   STATUS: Graphify **belum terpasang** (prasyarat `uv` belum ada; Python lokal 3.14 vs diminta 3.12).
   Sampai instalasi terverifikasi: pembacaan terarah (`file:line` dari rujukan nyata) = kanal sah, bukan pelanggaran.
   Rule hidup hanya setelah `graphify --help` benar-benar jalan. [R28 → mati; lihat §3 K4]

## D — Tanya-vs-perintah & wewenang user
D1 Pesan berupa pertanyaan → jawab saja, nol aksi (tanpa edit/commit/PR/label/spawn) sampai user menyuruh eksplisit. Ragu → tanya balik "mau dikerjakan?". [R50]
D2 Setelah ada perintah: jalan tanpa konfirmasi; ambiguitas → ambil default + catat di `status.md`/memory-bank; berhenti hanya untuk aksi ireversibel, peringatan keamanan, atau user tidak jelas. [R9]
D3 Istilah yang bisa dua level ("terminal" = fitur aigate, bukan terminal OS) → cek repo dulu atau klarifikasi 1 kalimat; jangan jawab di level salah. [R30]
D4 Niat "pemisahan" default = branch, bukan repo. Resource eksternal (repo/registry/domain/akun/webhook) wajib disebut bentuknya + tunggu jawaban. Terlanjur salah bikin → lapor, jangan hapus sendiri. [R39]
D5 Typo user wajib dikoreksi ke bentuk benar; jangan diikuti; ragu → tanya 1 kalimat. [R46]
D6 Fitur UI baru: PM WAJIB tayangkan 1 lembar desain (denah blok + alternatif + alasan) dan dapat ACC user
   SEBELUM spawn fe-dev. Kontrak data/API bukan pengganti persetujuan interaksi; tes hijau bukan ACC desain.
   Desain ditolak user → desain ulang + ACC lagi, jangan tambal-sulam di kode.

## E — Mode eksekusi & kecepatan proses
E1 Sebelum kerja multi-agen/panjang: tawarkan paralel vs sekuensial; pilihan berlaku satu sesi, sesi baru tanya lagi; scope overlap → paksa sekuensial. Detail: `.opencode/rules/parallel-sequential.md`; state = `documents/pm/state.md` key `multiagent_mode`. [R16]
E2 Satu panggilan = satu tujuan; reuse `file:line` yang sudah dibaca; spawn cepat dengan handover ketat; verifikasi = cek kontrak + tes terkait, bukan investigasi ulang. [R31]
E3 Jangan kirim pekerjaan baru di tengah `/run-impl`; tahan perubahan spec sampai run selesai atau batch di awal. [R15]
E4 Saat iterasi hanya jalankan tes relevan; suite penuh sekali sebagai gate commit; perubahan yang tak tertes (markup/komentar/dokumen) tanpa suite; klaim kecepatan wajib angka `time`/`--durations`. [R35]
E5 Jalur yang dijalankan tiap shell (`~/.bashrc`, `PROMPT_COMMAND`, hook) wajib bebas perintah blocking; kebutuhan hidup → cache state + background. Ukur dulu (`time bash -ic true`) sebelum dan sesudah. [R37]

## F — Fakta, sumber, provenance
F1 Mengadopsi fitur dari sumber eksternal: fetch isinya dulu, sitat (nama + URL) di dokumen, align ke isi asli, lalu verifikasi sitat benar-benar ada. [R17]
F2 Tag provenance inline (mis. "adopsi 9router") jangan dicabut demi kerapian — itu memori lintas sesi. [R18]
F3 Klaim teknis wajib bukti: `file:line`, URL, atau konfirmasi user. Fakta eksternal (paket/binary/platform) minimal 2 sumber independen yang di-cross-check; konflik → selidiki sampai konsisten. [R47,R48] → `.opencode/rules/no-hallucination.md`.
F4 Klaim ukuran/kuantitas wajib menyebut alat + satuan aslinya (`wc -c`=byte, `du -k`=KiB blok terbulatkan, `wc -l`=baris). Angka beda alat tidak boleh dicampur tanpa label; sebut rentang, bukan satu angka palsu-presisi. [baru]

## G — Verifikasi & quality gate
G1 Kode produksi mengikuti DRY/KISS/SOLID/YAGNI; gate QA + PM menolak receipt copy-paste/over-engineer. Detail: `.opencode/rules/code-quality-principles.md`. [R25]
G2 Sub-agent: `py_compile` semua `.py` yang ditulis. Full `pytest`/`npm test` di env user. Jangan klaim "terverifikasi runtime" kalau cuma syntax; catat batasnya di receipt. [R14]
G3 Aset yang dipakai fitur di-vendor lokal (bukan CDN); dependensi runtime masuk `pyproject` + diverifikasi terpasang. Klaim "fitur X jalan" hanya setelah fitur itu di-exercise end-to-end di lingkungan nyata; e2e menyentuh tiap fitur inti; "test hijau" ≠ "aplikasi kepake". [R20]
G4 Setelah perubahan FE: periksa HTML final dari artefak markup/tool-call (`tsoassistant`, `recipient_name`, `functions.*`). `git diff --check` + unit test tidak cukup. [R24]
G5 Perintah yang dibangkitkan orchestrator (self-heal): pakai subcommand non-interaktif yang dicek dari `--help`; marker `.done` hanya bila exit 0, `.failed` bila tidak; model id dikualifikasi ke `provider/model`; uji live, bukan assertion string. [R34]

## H — Git, catatan, PR
H1 Awal task: checkpoint commit (`git add -A && git commit -m "checkpoint: <task> start"`). Tiap subtask selesai & terverifikasi: commit langsung. Conventional Commits; hormati `.gitignore` (`.env`, DB di `~/.aigate`); cek `git status` sebelum commit. [R19]
H2 Commit dipecah per FITUR, bukan per lapisan; file yang dipakai dua fitur di-split per hunk; urutan commit = penyedia API/kolom dulu, pemakai belakang. Dilarang `git add -A` untuk kerjaan beda fitur. [R36]
H3 Tiap perubahan kode yang sudah diverifikasi dicatat per-file di `documents/dev/CODE_CHANGES.md` (tanggal, task, fungsi/marker, baris bila relevan; kerja belum kelar = PENDING; lingkungan luar repo di subseksi khusus). [R22]
H4 Tiap PR yang PM buka membawa ≥1 label tipe dari label yang sudah ada (`bug`/`enhancement`/`documentation`/…); label baru butuh ACC user (API menolak nama baru); tag dipasang saat membuat PR, bukan menyusul. [R49]

## I — Materi publik (README, wiki, varian bahasa)
I1 Pekerjaan banyak halaman (wiki/docs site/API ref): sajikan dulu daftar halaman + ringkas + sumber + yang TIDAK dipublikasi + bahasa + titik publikasi; ACC user baru jalan; satu halaman → review → berikutnya. [R40]
I2 README = bahasa manfaat untuk orang awam; dilarang menyebut path/nama file; nama produk `aigate` huruf kecil; nilai jual di 3–5 baris pertama + ilustrasi adegan; poin ini masuk handover SEBELUM ditulis. [R41]
I3 Materi publik pakai kultur netral (tanpa idiom/contoh khas satu negara). Status "sudah dites" adalah wewenang maintainer: jangan pasang atau hapus caveat atas dugaan; ragu → tanya maintainer 1 kalimat, lalu catat konfirmasinya. [R42]
I4 Varian bahasa = tulisan ASLI di bahasa target, bukan calque; fakta identik (jumlah, nama produk, perintah, URL, kredit), kalimat/idiom/adegan bebas; satu kalimat satu makna. Hindari pasif kaku, subjek hilang, reduplikasi palsu, nominalisasi kaku, redundansi. [R43]
I5 Wiki TIDAK boleh membocorkan `documents/**` (path, struktur, nomor ADR, nama tabel, path `src/...`); sumber fakta = kode/perilaku nyata; tidak terbukti → `TODO-VERIFY`. Draft di staging `documents/pm/wiki-drafts/`; wiki asli tidak ditulis/di-push sampai user membuka larangan. [R44]
I6 Dilarang referensi relatif-ke-diri ("repo ini", "this repo", "link di atas") di materi publik → URL absolut; tautan antar-file repo sendiri boleh relatif. [R45]
I7 Berkas `.md` ditulis caveman ultra (pendek, padat); balasan ke user bahasa Indonesia casual normal, utuh, tanpa singkatan. Gaya ringkas tidak boleh memangkas format wajib rule lain. [R52] → `.opencode/rules/language.md`.

I8 Bicara ke user: istilah teknis dipakai APA ADANYA (PR, commit, merge, branch, tes). Jangan ganti dengan padanan Indonesia yang tidak dipakai user (contoh nyata: "usulan" untuk PR). Kalau user tidak paham → jelaskan artinya sekali, lalu tetap pakai istilah itu. "non-IT jelas" = tambah penjelasan, bukan ganti istilah. [I7] → `.opencode/rules/language.md`.


## J — Kontrak produk, kredensial, keselamatan host
J1 FastAPI `>=0.95,<0.100` + Pydantic `>=1.10,<2` (v1, pure Python). Semua dependency pure-Python (Termux/Windows/Linux/macOS); tanpa Rust/`pydantic-core`. [R10]
J2 UI = HTML/CSS/JS vanilla (tanpa React/Vue/Expo/bundler); state global di `app.js`; tidak ada langkah compile. [R13]
J3 Secret PRODUK disimpan plaintext di DB (`api_key`, `internal_api_key`, `password`) dan UI tidak me-mask; seluruh config aplikasi di tabel `Setting`, bukan file. Ini keputusan maintainer (ADR-007/010) — JANGAN "dibersihkan" jadi enkripsi/masking. Beda dengan J5 (kredensial agen). [R11]
J4 Semua error/warning masuk tabel `LogEntry` (severity + stacktrace + context). `except: pass` / catch kosong dilarang. [R12]
J5 Kredensial AGEN hanya dari `.env` root. Sebelum menyimpulkan "gak bisa / gak punya akses": cek
   `.opencode/rules/*.md` + `.env` dulu. Dilarang bikin penyimpanan kredensial baru (credential.helper store,
   `~/.git-credentials`, SSH, config) tanpa user minta — git butuh auth → helper sekali-pakai inline dari
   `.env`, tidak ditulis ke disk; nilai tidak dicetak (nama + panjang + hash pendek); token ditolak → lapor + tanya. [R51] → `.opencode/rules/secrets.md`.
J6 DILARANG kill/pkill/killall/restart proses aigate, uvicorn, atau proses induk (sesi opencode hidup di dalamnya). Sub-agent hanya boleh mematikan PID miliknya sendiri di port acak. Bukti "kode lama masih aktif" = bandingkan `ps -o lstart` vs `stat -c %y file`, lalu lapor; **user yang memutuskan restart**. [R32]
## Cara nambah rule (v2)
1 baris perintah + 1 baris alasan. Pelajaran panjang -> arsip, bukan file ini.
ID baru = huruf tema + nomor_next (A1..J6 terisi; lanjutan J7, dst). Rujukan `[R#]` = ID lama di arsip.
Gate wajib setelah edit: `python3 .opencode/tools/governance/rules-index.py` (exit 0 = lolos).
