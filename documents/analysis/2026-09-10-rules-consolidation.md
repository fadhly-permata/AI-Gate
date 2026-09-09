# Usulan Konsolidasi Rule Operasional (langkah b perapian governance)

- Tanggal: 2026-09-10 · Penulis: system-analyst (spesialis) · Status: **USULAN** — bukan eksekusi.
- Sasaran: `documents/pm/OPERATING_RULES.md` dari 52 seksi rule → ≤10 tema, teks lama diarsipkan utuh.
- Metode sensus: baca berkas nyata, tiap angka di bawah punya `file:line`. Tidak ada angka kira-kira.

## 0. Koreksi sensus (bukan menyanggah fakta — hasil ukur hari ini)

| Item | Angka di handover/laporan | Angka terukur sekarang | Cara ukur |
|---|---|---|---|
| rule `^## R<n>` | 51 | **52** (R1–R52, tanpa celah, tanpa duplikat ID) | `grep -nE "^##+ R[0-9]+"` |
| baris | 772 | **788** | `wc -l` |
| byte | 51.493 | **52.698** | `wc -c` |
| `documents/pm/` | 19 berkas / 427 KB | **19 berkas / 403.321 byte (394 KiB)** | `find … -printf '%s'` dijumlah |
| `status.md` | 195 KB | **199.976 byte / 2.450 baris** | `wc -lc` |

Delta 51→52 = R52 ditulis setelah sensus (mtime `OPERATING_RULES.md` 01:37, laporan `0120` dibuat 01:20).
Peta di bawah memetakan **52** ID; syarat "tidak ada rule hilang" tetap terpenuhi (52 ⊇ 51).
Angka 427 KB kemungkinan `du` (blok), bukan ukuran isi; dipakai 403.321 byte sebagai acuan.

Bukti rujukan kode ke `documents/{analysis,api,config}/**` (tidak boleh dipindah tanpa betulkan rujukan):
`src/backend/models.py:4` → `documents/analysis/ERD.md`; `src/backend/gateway/errors.py:8` →
`documents/api/OPENAI_COMPATIBLE_CONTRACT.md`; `src/backend/cli_presets.py:3` →
`documents/config/CLI_CONFIG_SCHEMA.md`. Rujukan kode ke `documents/pm/**`: **0** (grep di `src/`, `tests/`, `run.py`).

---

## 1. Peta old → new (52 baris)

Tema: **A** routing/delegasi · **B** penempatan & higienitas berkas · **C** command & tool ·
**D** tanya-vs-perintah & wewenang user · **E** mode eksekusi & kecepatan proses ·
**F** fakta, sumber, provenance · **G** verifikasi & quality gate · **H** git, catatan, PR ·
**I** materi publik (README/wiki/lokal) · **J** kontrak produk, kredensial & keselamatan host.

| Old ID | Judul lama (ringkas) | Baris lama | → Tema | → Rule baru |
|---|---|---|---|---|
| R1 | sub-agent hanya saat dibutuhkan | 5–8 | A | A5 (pointer saja) |
| R2 | skill dibuat bersamaan agen | 10–13 | A | A5 (pointer saja) |
| R3 | batasan akses file per agen | 15–17 | A | A3 (pointer saja) |
| R4 | setelah generate minta restart | 19–25 | A | A5 (pointer saja) |
| R5 | dokumen di `documents/` | 27–33 | B | B1 |
| R6 | artefak selalu di folder proyek | 35–39 | B | B2 |
| R7 | command low-friction | 41–49 | C | C1 |
| R8 | no-junk (scratch dihapus) | 51–55 | B | B5 |
| R9 | implementasi tanpa konfirmasi | 57–76 | D | D2 |
| R10 | stack Pydantic v1 / no Rust | 78–83 | J | J1 |
| R11 | secret plaintext di DB (ADR-007/010) | 85–89 | J | J3 |
| R12 | logging wajib ke DB (ADR-011) | 91–94 | J | J4 |
| R13 | FE vanilla JS no-build (ADR-001) | 96–99 | J | J2 |
| R14 | verifikasi sub-agent (batas sandbox) | 101–105 | G | G2 |
| R15 | jangan interupsi mid-run | 107–110 | E | E3 |
| R16 | tanya paralel/sekuensial | 112–127 | E | E1 (pointer saja) |
| R17 | referensi eksternal harus nyata | 129–142 | F | F1 |
| R18 | pertahankan rujukan inline | 144–150 | F | F2 |
| R19 | checkpoint git + commit per subtask | 152–172 | H | H1 |
| R20 | verifikasi end-to-end lingkungan nyata | 174–192 | G | G3 |
| R21 | PM tidak implementasi, delegasi | 194–215 | A | A2 |
| R22 | perubahan kode dicatat per-file | 217–231 | H | H3 |
| R23 | laporan di `.opencode/reports/` | 233–236 | B | B3 (pointer saja) |
| R24 | cek artefak markup di HTML akhir | 238–242 | G | G4 |
| R25 | DRY/KISS/SOLID/YAGNI | 244–252 | G | G1 (pointer saja) |
| R26 | "install+init" tool existing | 254–262 | C | C2 |
| R27 | tool dirujuk via repo → pastikan identitas | 264–271 | C | C3 |
| R28 | baca kode lewat codegraph | 273–286 | C | C4 (**mati**; lihat §3 K4) |
| R29 | semua request lewat PM | 288–318 | A | A1 |
| R30 | "terminal" = fitur aigate | 320–345 | D | D3 |
| R31 | jangan blokir panggilan panjang | 347–363 | E | E2 |
| R32 | dilarang kill/restart proses | 365–381 | J | J6 |
| R33 | dilarang file/folder baru di root | 383–400 | B | B4 |
| R34 | self-heal: subcommand + gate exit code | 402–422 | G | G5 |
| R35 | verifikasi hemat (tes tertarget) | 424–443 | E | E4 |
| R36 | commit per fitur, split hunk | 445–453 | H | H2 |
| R37 | jalur tiap-shell bebas blocking | 455–475 | E | E5 |
| R38 | right-size handover task kecil | 477–487 | A | A4 |
| R39 | "gak kecampur" = branch, bukan repo | 489–518 | D | D4 |
| R40 | rencana daftar halaman sebelum wiki | 520–530 | I | I1 |
| R41 | README untuk awam, tanpa path | 532–549 | I | I2 |
| R42 | kultur netral + status tes milik maintainer | 551–569 | I | I3 |
| R43 | varian bahasa = tulisan asli | 571–609 | I | I4 |
| R44 | wiki jangan bocorkan `documents/` | 611–634 | I | I5 |
| R45 | jangan "repo ini" → URL absolut | 636–654 | I | I6 |
| R46 | koreksi typo user | 656–668 | D | D5 |
| R47 | dilarang asumsi/halusinasi | 670–689 | F | F3 |
| R48 | script wajib >1 sumber independen | 691–704 | F | F3 |
| R49 | tiap PR ≥1 label tipe | 706–721 | H | H4 |
| R50 | pertanyaan ≠ perintah | 723–741 | D | D1 |
| R51 | kredensial satu sumber `.env` | 743–772 | J | J5 |
| R52 | caveman ultra cuma untuk `.md` | 774–788 | I | I7 (pointer saja) |

Addendum lama ikut terpetakan (bukan ID baru): R29 addendum (310–318) → A1; R39 addendum
(513–518) → D4; R43 addendum (593–609) → I4.

Tanda **(pointer saja)** = isi rule itu sudah hidup di `.opencode/rules/*` (kanonik) sehingga di file
v2 hanya jadi satu baris rujukan; daftar lengkapnya di §2.1. R28 → C4 bukan salinan: C4 **menggantikan**
R28 yang mati (kanal graf belum ada), bukan memindahkan teksnya.

**Pemeriksaan kelengkapan (terukur).** Rule baru di draf §2.2 = **49**, ID unik, 0 ganda:
A=5, B=5, C=4, D=5, E=5, F=3, G=5, H=4, I=7, J=6 (skrip pemindaian blok: 49 baris rule, ID unik semua).
Rule lama terpetakan = **52** (R1…R52, rentang numerik penuh: 0 hilang, 0 ganda — lihat §0).
Rasio: 52 lama → 49 baru; penghematan utama bukan di jumlah rule, tapi di panjang tiap rule
(1 baris perintah + 1 klausa alasan, bukan 8–20 baris narasi + "Pelajaran").

---

## 2. Struktur target (isi baru `OPERATING_RULES.md`)

Kebijakan rumah: **nama berkas tidak berubah** (`documents/pm/OPERATING_RULES.md`) supaya 8 berkas
hidup yang menunjuknya tidak patah (`AGENTS.md:21`, `AGENTS.md:27`, `.opencode/agents/ProjectManager.md:29`,
`.opencode/skills/pm-orchestration/SKILL.md:15`, `documents/plan/BACKLOG.md`, `documents/dev/CODE_CHANGES.md`).
Teks v1 dipindah utuh ke `documents/pm/archive/OPERATING_RULES-v1-52rules.md` (`git mv` + tulis ulang file aktif;
history ke-jejak, pola sama dengan R33 `documents/pm/memory-bank.md:42-49`).
Header baru wajib menunjuk arsip + pelajaran tiap rule dibaca dari arsip, bukan disalin ulang.

### 2.1 Rule mana yang DUPLIKAT dengan `.opencode/rules/*` (satu aturan satu rumah)

| Rule lama | Berkas kanonik yang sudah memuat | Putusan | Rumah tunggal |
|---|---|---|---|
| R1 | `.opencode/rules/agent-generation.md:12-17` | **hapus teks**, sisakan pointer | agent-generation.md |
| R2 | `agent-generation.md:19-23` | **hapus teks**, pointer | agent-generation.md |
| R4 | `agent-generation.md:25-30` | **hapus teks**, pointer | agent-generation.md |
| R3 | `.opencode/rules/agent-boundaries.md:29-34` | **hapus teks**, pointer | agent-boundaries.md |
| R16 | `.opencode/rules/parallel-sequential.md:10-50` | **hapus teks**, pointer (key state dipindah ke E1) | parallel-sequential.md |
| R25 | `.opencode/rules/code-quality-principles.md:6-38` | **hapus teks**, pointer | code-quality-principles.md |
| R23 | `.opencode/rules/task-report.md:2-5` | **hapus teks**; larangan `reports/**` root + format folder digabung ke task-report.md | task-report.md |
| R52 | `.opencode/rules/language.md:2-4` | **hapus teks**; amandemen "semua `.md` caveman ultra" + "format wajib rule lain tidak dipangkas" masuk language.md | language.md |
| R47 | `.opencode/rules/no-hallucination.md:1-6` | **sebagian**: ayat "wajib sertakan `file:line`/URL" masuk no-hallucination.md; sisanya tetap di F3 | no-hallucination.md + F3 |
| R51 | `.opencode/rules/secrets.md:1-2` | **sebagian**: "token di `.env`, jangan hardcode, jangan commit" sudah ada; ayat "cek rules+.env sebelum ngaku gak bisa" + inline credential helper tetap di J5 | secrets.md + J5 |
| R7 | `.opencode/rules/commands.md:2-4` | **sebagian**: low-friction (arg otomatis, auto-probe) belum ada → tambah 1 baris ke commands.md | commands.md |

Total 8 rule hilang total dari OPERATING_RULES (R1,R2,R3,R4,R16,R23,R25,R52) + 3 rule terbagi
(R7,R47,R51). Penghematan bagian ini ± 5,1 KB: 219+252+193+511+1104+278+609+1194+553 = **4.913 byte**
(ukuran blok terukur §0 sensus) belum termasuk ayat tersisa R47/R51 yang tetap tinggal.

**Syarat yang belum bisa dieksekusi PM:** tidak ada satu pun agen yang diberi WRITE scope
`.opencode/rules/**` (lihat roster `agent-boundaries.md:17-27`; PM hanya `documents/pm/**` +
generate agen/skill). Menghapus duplikat = **wajib** mengedit berkas kanonik dulu, dan itu
**butuh keputusan user** (siapa yang boleh menulis `.opencode/rules/`). Tanpa itu, usulan ini mandul.

### 2.2 Draf teks rule baru (49 rule, ≤4 baris per rule)

Blok di bawah adalah **isi usulan** file baru; ukurannya terukur (lihat §5). Rujukan `[R#]` = ID lama
(barisnya ada di arsip v1). Format ini yang dipakai skrip pemeriksa §7.

<!-- BEGIN:NEW-RULES -->
```markdown
# PM Operating Rules v2 (konsolidasi 10 tema)
Teks v1 (R1–R52, 52.698 byte) diarsipkan utuh: `documents/pm/archive/OPERATING_RULES-v1-52rules.md`.
Rule kanonik agen ada di `.opencode/rules/*.md` — tidak diulang di sini (DRY).
Tambah rule baru = 1 baris perintah + 1 baris alasan; pelajaran panjang masuk arsip.

## A — Routing, delegasi, siklus agen
A1 Semua input user masuk PM dulu; main thread dilarang sentuh `src/**`|`tests/**`|`documents/**`. Alasan: eksekusi tanpa rute = tanpa boundary/receipt. [R29] → `AGENTS.md:3-18`, `.opencode/rules/request-routing.md`.
A2 PM tidak menulis kode/test. Butuh keahlian → spawn spesialis + handover (goal, `file:line`, scope, DoD). Verifikasi & integrasi tetap milik PM. [R21]
A3 Tiap agen hanya tulis di scope-nya; lintas scope = receipt ditolak. Detail roster: `.opencode/rules/agent-boundaries.md`. [R3]
A4 Handover = ≤25 baris untuk task ≤5 file; peta `file:line` wajib; jangan minta file laporan `.md` untuk task kecil; jangan bikin FILE baru untuk mencatat (append baris boleh). [R38]
A5 Sub-agent + skill dibuat berbarengan saat dibutuhkan, tidak pernah dihapus. Setelah generate: WAJIB minta user restart opencode; dilarang diam-diam fallback ke agen `general`. [R1,R2,R4] → `.opencode/rules/agent-generation.md`.

## B — Penempatan & higienitas berkas
B1 Semua dokumen proyek di `documents/**`, bukan `docs/**`. [R5]
B2 Artefak opencode (command/rule/skill/agent) di `.opencode/**` proyek; global hanya bila user menyebut "global". [R6]
B3 Laporan tugas di `.opencode/reports/[yyyymmdd]/[jenis]/[hhmm]_[slug].md`; root `reports/**` dilarang. [R23] → `.opencode/rules/task-report.md`.
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
```
<!-- END:NEW-RULES -->

---

## 3. Tabel konflik (wajib diputuskan, bukan diasumsikan)

"Menang/kalah" = aturan yang berlaku bila keduanya dibaca. Semua rujukan terukur.

| # | Konflik | Bukti | Putusan usulan | Menang / Kalah |
|---|---|---|---|---|
| K1 | **R50 (nanya ≠ perintah) vs instruksi "jangan tanya, langsung jalan"** | Teks "mulai kerja segera, jangan tanya" TIDAK ada di `.opencode/skills/pm-orchestration/SKILL.md` (55 baris, sudah dibaca penuh — justru `:45-50` menyuruh STOP & tanya). Yang benar: `.opencode/commands/test-cli-compat.md:5` "do NOT ask the user to re-explain; just execute" dan `.opencode/commands/run-impl.md:28` "Eksekusi task aktif sesuai R9 (TANPA konfirmasi)" | Kalimat penengah: **"Jangan tanya" hanya berlaku DI DALAM tugas yang sudah diperintah dan konteksnya sudah lengkap. Pertanyaan user, perintah ambigu, atau aksi yang membuat resource eksternal = tetap tanya/jawab dulu (D1, D2, D4).** | R50 **menang** sebagai gerbang awal; R9/test-cli-compat **menang** di dalam run yang sudah berjalan |
| K2 | **R21 (PM dilarang implementasi) vs PM wajib menulis laporan** | `agent-boundaries.md:25` memberi `.opencode/reports/**` hanya ke **qa-engineer**; `task-report.md:2-5` mewajibkan **pelaksana** menulis laporannya sendiri; R21 (baris 206-208) membatasi PM ke `documents/pm/**` + `documents/**` | Kalimat penengah: **laporan tugas adalah dokumen kerja, bukan implementasi produk. Siapa pun pelaksana tugas menulis laporan sendiri; scope tulis `.opencode/reports/**` dibuka untuk SEMUA agen (PM + spesialis) khusus berkas `[yyyymmdd]/[jenis]/…`. Kode produksi tetap milik spesialis.** Perbaikan konkret: tambah baris laporan ke roster `agent-boundaries.md`. | R21 **kalah sebagian** (PM tetap boleh menulis laporan); larangan "PM tidak implementasi" tetap menang untuk `src/**`/`tests/**` |
| K3 | **R38 (jangan bikin dokumen tambahan untuk task kecil) vs kewajiban catat handover/state/status** | `pm-orchestration/SKILL.md:20-28` handover = isi **prompt spawn**, bukan berkas (jadi tidak bertabrakan); yang bertabrakan: `parallel-sequential.md:43,50` (`pm/state.md`, `pm/status.md`) dan `ProjectManager.md:160` ("Log the spawn in `documents/pm/status.md`") — wajib tulis berkas tiap spawn | Kalimat penengah: **R38 melarang FILE/BERKAS baru untuk task kecil; penulisan append-baris ke `status.md`/`state.md`/`memory-bank.md` selalu wajib dan dihitung ≤3 baris per peristiwa. Jangan bikin `handovers/<task>.md` kecuali handover >25 baris (task besar/audit).** | R38 **menang** untuk berkas baru; kewajiban state/status **menang** untuk append |
| K4 | **R28 (wajib codegraph) vs tool tidak ada** | Terukur: `codegraph` tidak di PATH, tidak ada server MCP (fakta handover; tidak diselidiki ulang). User sudah putuskan: diganti **Graphify**, instalasi **belum** terjadi | Kalimat penengah: **rule ditulis sebagai kondisi: "bila kanal graf terpasang, ia langkah pertama; bila belum, baca terarah dari `file:line` yang diketahui + catat sebagai utang tooling." Rule hanya hidup setelah instalasi diverifikasi (`graphify --help` jalan) — sesuai putusan user "jangan tulis rule yang belum benar" (`memory-bank.md:12-13`).** | R28 lama **mati/hapus**; C4 **menang**; jangan klaim Graphify aktif |
| K5 | **`.opencode/rules/secrets.md` vs R11 (secret produk plaintext)** | `secrets.md:2` "Store in `.env`. Never hardcode… Never commit" vs `OPERATING_RULES.md:86-89` plaintext DB + UI tanpa masking. Agen yang membaca salah satu bisa "membersihkan" yang lain | Kalimat penengah: **dua domain berbeda: `secrets.md` = kredensial yang dipakai AGEN; J3 = data milik PENGGUNA yang disimpan aplikasi. J3 eksplisit menyatakan dirinya pengecualian dari secrets.md.** | Keduanya **menang** di domainnya; tanpa kalimat penengah = konflik (usulan sudah dipasang di J3/J5) |
| K6 | **Tidak ada pemilik WRITE `.opencode/rules/**`** | Roster `agent-boundaries.md:12-27`: PM = `documents/pm/**` + generate agen/skill; tidak ada agen untuk `.opencode/rules/` | Putusan usulan: **PM atau agen yang ditunjuk user memegang WRITE `.opencode/rules/**` khusus langkah perapian ini, atau user mengedit sendiri.** Ini prasyarat K1–K5 bisa dieksekusi | Keputusan **user** |
| K7 | **Ruang lingkup style: bahasa & gaya** | `language.md:2` "`.opencode` files: English caveman ultra" vs R52 "berkas `.md` (termasuk `documents/**`) caveman ultra" — `language.md` tidak pernah menyebut `documents/**` | Kalimat penengah: **`language.md` diperluas: `.opencode/**` = Inggris caveman ultra; `documents/**` = Indonesia caveman ultra (kecuali laporan `.opencode/reports/**` Indonesia formal, dan dokumen yang diminta bahasa lain).** | R52 **menang**, `language.md` **diamandemen** |
| K8 | **Rujukan basi pasca-R33 (`pm/**` → `documents/pm/**`)** | 17 rujukan masih `pm/...` di 6 berkas hidup: `parallel-sequential.md:43,50`; `run-impl.md:11,19,21,29,37,46`; `log-bug.md:16,26,30`; `revise-docs.md:15,19,20,33`; `qa-engineer.md:13`; `qa-skill/SKILL.md:12` — ditambah `system-analyst.md:9` (`READ only: pm/`) | Putusan: **satu langkah bersih-bersih rujukan (search-replace terkontrol) dijalankan SEBELUM rule lama dihapus**, atau agen akan terus menulis ke path yang sudah tidak ada | R33 **menang**; rujukan lama **kalah/harus diperbaiki** |
| K9 | **Rujukan skill mati di definisi PM** | `ProjectManager.md:30` merujuk skill `pm-postmortem` (TIDAK ada di `.opencode/skills/`); `ProjectManager.md:76` skill `fullstack-skill` padahal direktori nyata `fullstack-dev-skill`; `ProjectManager.md:85,93,110` + `pm-orchestration/SKILL.md:36,37,40` menulis write root `docs/analysis|business|architecture/**` yang **bertentangan** dengan `agent-boundaries.md:23-27` (`documents/...`) dan R5 | Putusan: **perbaiki pointer + write root di kedua berkas itu sebelum consolidation dianggap selesai.** R5 **menang** atas `docs/` |
| K10 | **Format folder laporan tidak seragam** | `.opencode/reports/` berisi `2026-09-03/` DAN `20260903/` (dua format) + 1 berkas di root (`qa_anthropic_inbound_verification.md`); `task-report.md:3` mewajibkan `[yyyymmdd]`; total 29 berkas | Kalimat penengah: **`[yyyymmdd]` tunggal; isi folder lama dinormalisasi (rename + perbaiki rujukan); berkas di root `.opencode/reports/` dipindah ke `[yyyymmdd]/[jenis]/`.** | `task-report.md` **menang** |

---

## 4. Shortlist `AGENTS.md` (kanal auto-inject; ≤12 aturan)

Fakta: hanya `AGENTS.md` yang terbukti ter-inject ke agen (`AGENTS.md:21-24`;
`memory-bank.md:14-16` → plugin opencode DITUNDA). Usulan: 12 baris aturan + rujukan.
Bahasa Inggris caveman ultra. Baris "Language" yang sudah ada (`AGENTS.md:31-32`) diperluas, bukan ditambah.

1. `Route ALL user input to @ProjectManager first. Main thread never implements. [AGENTS.md:3-18 · RULES A1]`
2. `Question != command. Asked -> answer only. No edit, commit, PR, label, spawn until told. [RULES D1]`
3. `Commanded task -> run without asking. Ambiguity -> pick default, log it. Stop only for irreversible/unsafe. [RULES D2]`
4. `PM never writes src/ or tests/. Delegate to specialist: goal, file:line map, scope, done-def. [RULES A2]`
5. `Each agent writes only its scope. Roster: .opencode/rules/agent-boundaries.md. [RULES A3]`
6. `No new file/folder at repo root. Docs -> documents/. Artifacts -> .opencode/. Reports -> .opencode/reports/[yyyymmdd]/[type]/[hhmm]_[slug].md. [RULES B1-B5]`
7. `Every technical claim needs proof: file:line, URL, or ask. External facts need 2 independent sources. [RULES F3 · no-hallucination.md]`
8. `Find code location via graph channel first if installed; else targeted read. Never broad repo grep. [RULES C4]`
9. `Never kill/restart aigate, uvicorn, or parent process. Compare ps lstart vs file mtime, report; user decides. [RULES J6]`
10. `Agent credentials: .env only. Never print values, never new credential store, never commit. Product plaintext-in-DB secrets are intentional (J3) — do not "fix". [RULES J5/J3]`
11. `Git: checkpoint at task start; commit per feature, never git add -A across features; log code changes per-file in documents/dev/CODE_CHANGES.md. [RULES H1-H3]`
12. `Done only after feature exercised end-to-end for real. Green tests != usable app. Vendor assets local, no CDN. [RULES G3 · OPERATING_RULES R20]`

Bukan rule (tetap di kanal kanonik, cukup dirujuk): rincian paralel/sekuensial, DRY/KISS/SOLID/YAGNI,
gaya bahasa, self-heal, label PR, README/wiki. Semua punya pointer `RULES <ID>` di baris 1–12.

---

## 5. Angka biaya (terukur, bukan kira-kira)

Rumus dipakai: **token ≈ byte / 3,6** (heuristik untuk markdown Latin; Indonesian/English campur).
Angka byte = `wc -c` nyata. Token = estimasi, diberi label estimasi, bukan hasil tokenizer opencode.
Kalau mau presisi: jalankan tokenizer model target pada tiap berkas (di luar kemampuan langkah ini —
TIDAK DIKETAHUI jumlah token sebenarnya).

| Kanal | Sekarang (byte, terukur) | Setelah usulan (byte) | Estimasi token (byte/3,6) | Cara hitung |
|---|---|---|---|---|
| `AGENTS.md` (auto-inject **setiap sesi, semua agen**) | 1.866 | ≈ **2.600** (12 baris rule §4 + header + Language) | 518 → ±722 | `wc -c AGENTS.md`; 12 baris × ±60 B + 1.150 B struktur lama yang dipertahankan |
| `documents/pm/OPERATING_RULES.md` (dibaca hanya saat digali) | **52.698** | **10.533** (blok §2.2 terukur; 49 baris rule) | 14.638 → **2.926** | `wc -c`; blok 2.2 diekstrak (marker BEGIN/END) lalu di-`wc -c` = 10.533 |
| `documents/pm/archive/OPERATING_RULES-v1-52rules.md` (baru, read-rare) | 0 | **52.698** (salin utuh) | ±14.638 (hanya saat dibuka) | `cp` + `wc -c`; tidak pernah auto-inject |
| `.opencode/rules/` (11 berkas) | **9.929 / 229 baris** | ±**10.600** (4 berkas tema + amandemen K1–K5,K7) | 2.758 → ±2.944 | `wc -c .opencode/rules/*.md`; penggabungan tidak menambah teks, amandemen +±670 B |
| `.opencode/skills/pm-orchestration/SKILL.md` | 2.586 | ±2.200 (buang baris duplikat rule → pointer) | ±611 | `wc -c` |
| `documents/pm/` total | 403.321 (19 berkas) | ±415.000 (naik karena arsip v1 +±53 KB; turun dari pemangkasan `status.md`) | — | `find … -printf '%s'` |

Poin yang membuat dokumen ini layak: **beban konteks per sesi tidak naik** (yang auto-inject cuma
`AGENTS.md`, ±2,6 KB), sementara bahan yang harus dibaca agen untuk "tahu aturan" turun dari
**52.698 → 10.533 byte (−80,0%)**. Rasio lama/baris juga turun: 52 rule (±1.013 B/rule) → 49 rule
(±215 B/rule), tiap rule ≤4 baris, bukan 8–20 baris. Pelajaran panjang tetap ada, cuma pindah ke arsip
(dibaca atas kebutuhan, tidak pernah auto-inject). Selisih 42.165 byte = yang tidak lagi dibayar tiap
kali agen menggali aturan.


---

## 6. Rencana pemindahan berkas `documents/pm/**` (19 berkas; USULAN — eksekusi PM + user)

Rujukan hidup yang ditemukan (jangan dipindah sebelum rujukannya dibetulkan):
`ProjectManager.md:28-32,160` · `pm-orchestration/SKILL.md:13-17` · `business-analyst.md:11`
(`documents/pm/handovers/`, `documents/pm/wiki-plan.md`) · `BACKLOG.md:101` (`documents/pm/status.md`) ·
`CODE_CHANGES.md:139` (`documents/pm/cli-tools-compatibility.md`).

| Berkas (ukur) | Nasib usulan | Catatan |
|---|---|---|
| `OPERATING_RULES.md` 52.698 B / 788 L | **tetap di tempat**, isi diganti v2 (§2.2); teks lama → `documents/pm/archive/OPERATING_RULES-v1-52rules.md` | Nama dijaga: 8 berkas hidup di luar `documents/pm/` menunjuk file ini (terukur `grep -rl`) |
| `status.md` 199.976 B / 2.450 L | pangkas ke 30 hari terakhir; riwayat → `documents/pm/archive/status-2026Q3.md` | `BACKLOG.md:101` menunjuk file ini → nama jangan berubah |
| `memory-bank.md` 49.893 B / 414 L | brief + 10 keputusan terakhir + open risks tetap; progress lama → `archive/memory-bank-log.md` | Ada duplikat heading `## Decisions` (baris 6 dan 9) → rapikan |
| `state.md` 7.096 B / 14 L | **tidak dipindah** (runtime PM; `multiagent_mode` per `parallel-sequential.md:43`) | format ditegaskan: 1 checkpoint aktif |
| `bugs.md` 4.019 B | tetap di `documents/pm/bugs.md` DAN `/log-bug` dibetulkan ke path itu | pindah ke `.opencode/reports/` butuh edit `log-bug.md` (di luar scope PM) → keputusan user |
| `cli-tools-install-backlog.md` 26.794 B | → `documents/plan/cli-tools-install-backlog.md` | 0 rujukan kode; cek ulang `update-backlog.md` hanya menunjuk `BACKLOG.md` (`:7,12,15`) → aman |
| `cli-tools-compatibility.md` 4.644 B | → `documents/config/cli-tools-compatibility.md` | sumber kebenaran nyata = `src/backend/cli_compat.py` (`test-cli-compat.md:14`); berkas ini mirror → betulkan rujukan `CODE_CHANGES.md:139` |
| `wiki-plan.md` 7.095 B · `wiki-backlog.md` 6.099 B | → `documents/plan/` | WAJIB perbarui `business-analyst.md:11` (read scope) di commit yang sama |
| `wiki-drafts/Home.md` 2.338 B | **JANGAN DISENTUH** | staging wajib R44 ayat 8 (`OPERATING_RULES.md:632-633`); pindah = melanggar rule yang masih hidup |
| `handover-20260907-logs-be.md`, `handover-20260907-logs-fe.md`, `handover-be-dev-reqlog.md`, `handover-fe-dev-reqlog.md` (4 berkas, 20.188 B) | → `documents/pm/handovers/` (satu rumah); yang task-nya selesai → `documents/pm/handovers/archive/` | `business-analyst.md:11` sudah menunjuk `handovers/` → aman |
| `handovers/*` (5 berkas, 25.515 B) | 4 selesai → `handovers/archive/`; `2026-09-08-wiki-home-facts.md` + `wl2a-license-variants.md` = bukti provenance → archive, jangan hapus | R18 melarang mencabut provenance |

**Yang tidak boleh disentuh siapa pun:** `AGENTS.md` (kanal auto-inject; R29 addendum: kalau hilang →
rule kehilangan gigi), `documents/{analysis,architecture,api,config}/**` (dirujuk kode, baris §0),
`.opencode/rules/*` (kanonik; pemilik write-nya belum ada → K6), `.opencode/agents/specialists/*`
(reuse, jangan hapus per A5/R1).

Urutan aman (sekuensial, sesuai putusan user #4): ① betulkan rujukan basi K8+K9 → ② sepakati pemilik
`.opencode/rules/**` (K6) → ③ tulis arsip v1 → ④ ganti isi `OPERATING_RULES.md` dengan §2.2 →
⑤ jalankan skrip §7 (gate) → ⑥ pindahkan berkas §6 → ⑦ update `AGENTS.md` §4 → ⑧ normalisasi laporan K10.
Satu langkah = satu review user; jangan digabung (R31).

---

## 7. Spesifikasi skrip pemeriksa (tidak ditulis di sini)

- Path usulan: **`.opencode/tools/governance/rules-index.py`** (rumus rumah: `.opencode/tools/[kind]/[filename]`,
  `.opencode/rules/tools-scripts.md:2`; kind baru `governance` — preseden nyata `.opencode/tools/tests/`).
  Alternatif satu berkas saja: `.opencode/tools/governance/rules-check.py` kalau indeks tidak dipisah.
- Konsumsi: arg posisi 1 = path rule (baku `documents/pm/OPERATING_RULES.md`), arg 2 = path arsip v1,
  flag `--json`, `--max-bytes 20480`, `--themes 10`.
- Dependensi: **stdlib Python saja** (aturan portabilitas J1/R10 — jangan tambah dependency proyek).
  Catatan jujur: Python lokal 3.14.6 (fakta handover) — skrip tidak boleh memakai API yang baru.
- Perilaku yang diperiksa (exit 0 = semua lolos; exit 1 = daftar kegagalan dicetak; TIDAK menulis file):
  1. **Indeks**: hasilkan tabel `ID | judul | baris_awal | baris_akhir | byte | tema` dari `^##+ [A-J]\d+|^## R\d+`.
  2. **Cakupan lama→baru**: baca peta §1 (marker `| R<n> |`) → setiap ID lama muncul tepat **1x**;
     gagal kalau hilang/ganda. Output: `mapped=52 unique=52 missing=[] dup=[]`.
  3. **Rentang numerik**: ID `R1..R<n>` tanpa celah; deteksi tabrakan nomor (preseden nyata:
     R23 routing vs R23 reports, tercatat `memory-bank.md:36-41`).
  4. **Ukuran**: byte rule aktif ≤ `--max-bytes`; jumlah tema ≤ `--themes`; tiap rule ≤4 baris.
  5. **Arsip**: arsip v1 harus memuat teks tiap rule lama (bandingkan judul + byte blok;
     gagal kalau arsip lebih kecil dari total blok v1 = 52.121 byte, terukur §0).
  6. **Rujukan hidup**: setiap path yang disebut di rule/arsip dicek benar-benar ada
     (`documents/pm/state.md`, `documents/dev/CODE_CHANGES.md`, dst) dan tidak ada lagi stale
     `pm/...` pasca langkah ① (pola regex `(^|[^./\w-])pm/[a-z]`).
  7. **Konsistensi laporan**: daftar `.opencode/reports/*` yang tidak sesuai `[yyyymmdd]/[jenis]/[hhmm]_*.md`
     → cetak sebagai utang (K10).
  8. `--json` untuk dipakai PM/mesin: `{rules:[…], themes:[…], totals:{bytes,rules}, checks:[{name,pass,detail}]}`.
- Pemicu jalan: setelah setiap edit rule (gate langkah ⑤ §6) + bisa dipakai `/revise-docs`.
- Bukan-tanggung-jawab skrip ini: menilai isi rule benar/salah (butuh keputusan user).

---

## 8. Yang butuh keputusan PM + user (tidak bisa diputuskan di sini)

1. **Pemilik WRITE `.opencode/rules/**`** (K6) — tanpa ini, 8 rule duplikat tidak bisa dihapus dan DRY gagal.
2. **Putusan K1** (gerbang tanya-vs-jalan), **K2** (laporan milik siapa), **K3** (batas "berkas baru" vs append) — kalimat penengah sudah diusulkan, butuh ACC.
3. **Graf channel**: instal Graphify dulu (butuh `uv`; Python 3.14 vs diminta 3.12) atau terima C4 sebagai rule berkondisi? R28 lama tetap mati sampai instalasi nyata.
4. Setuju **nama file `OPERATING_RULES.md` dipertahankan** + arsip v1 di `documents/pm/archive/` (vs nama baru)?
5. Setuju **52 rule dilebur jadi 49 rule tema → `documents/pm/` tetap bertambah 1 folder arsip** meski user melarang perluasan `documents/pm/`? (Net: −42.165 byte rule aktif, +52.698 byte arsip, +1 folder.)
6. `bugs.md`: tetap di `documents/pm/` atau ikut `/log-bug` ke `.opencode/reports/` (butuh edit command → scope user).
7. Shortlist `AGENTS.md` §4: 12 aturan final mana yang masuk; sisanya harus tetap bisa ditemukan lewat pointer.
8. Normalisasi folder laporan (K10) — rename folder `.opencode/reports/2026-09-03/` → `20260903/`? Berisiko memutus rujukan lama; boleh juga dibekukan sebagai legacy.
