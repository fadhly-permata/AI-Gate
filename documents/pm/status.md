# PM Status

> Log aktif 30 hari terakhir. Entri 2026-09-03 s/d 09-08 → `documents/pm/archive/status-2026-09-03_sampai_2026-09-08.md` (dipindah, tidak dihapus).

## 2026-09-10 04:35 — CHECKPOINT WIP pindah perangkat (HP -> TABLET): backend be-dev belum diverifikasi (ProjectManager)
- be-dev tahap1 DIINTERUPSI user sebelum balik receipt, TAPI sempat nulis perubahan: 506 baris / 8 file `src/backend/**` (accounts_router, combo_routing, config/db, gateway/resolver, gateway/router, models, oauth, providers_router).
- JUJUR: KOREKSI pernyataan PM sebelumnya "kode tidak berubah" = SALAH — backend KE-ubah. Yang terverifikasi BARU `py_compile` 8 file (sintaks OK). BELUM: pytest, diff review, kontrak final.
- KEPUTUSAN: user mau pindah tablet + minta commit&push -> simpan state sbg WIP checkpoint (BUKAN klaim selesai) supaya tablet bisa pull.
- NEXT di tablet: review diff be-dev -> jalankan pytest suite (mesin strategi + migrasi idempoten) -> hijau? -> PM terbitkan kontrak -> baru tahap2 fe-dev.

## 2026-09-10 04:20 — Fitur baru: Provider multi-account strategy (adopsi 9router) — rencana diACC, tahap1 be-dev jalan (ProjectManager)
- User minta: rotasi/fallback multi-akun DI DALAM jendela Tambah/Edit Provider (tab "Akun"), hapus panel Discover Models.
- Riset otoritatif source 9router (decolua/9router @eb712ca) via sub-agent general: akun-level = fill-first + round-robin(sticky) + pin x-connection-id SAJA (bukan weighted/random). Dilaporkan jujur ke user (skala adopsi kecil; nilai riil = bisa DIPILIH + sticky + pin + backoff).
- Keputusan user: adopsi strategi 9router apa adanya; discovery opsi (a) hapus UI tetap panggil diam-diam; Combo utuh; eksekusi SEKUENSIAL.
- Kontrak PM-kunci ditulis di state.md checkpoint. Tahap1 = be-dev (DB migration idempoten + mesin select + DTO), hasilkan kontrak di receipt. Tahap2 = fe-dev (modal ber-tab + hapus panel + wire) SETELAH kontrak PM tayang.

## 2026-09-10 04:07 — Banner halaman Fase 3: fe-dev spawned + diterima, fitur di-COMMIT (ProjectManager)
- ACC user: "oke kerjain" = 8 draf ID + opsi A + bentuk Opsi B. Delegasi: fe-dev (sudah ter-generate, reuse)
  via `opencode run --agent fe-dev` — ONE spawn, handover file di luar repo (scope: index.html, styles.css,
  7 kamus; 56 entri kamus sudah ditulis PM di handover; DILARANG sentuh JS/tests/git).
- Receipt fe-dev: 9 berkas, 8 blok anak pertama, CSS `--accent` card tokens, self-check parity 35 tes hijau.
- AUDIT PM (bukan terima buta): git diff per berkas = sesuai spesifikasi; verifikasi independen —
  (1) regex per-section: 8 view banner=True first_child=True, welcome+terminal banner=False;
  (2) `rg -c page_desc.` = 8 di TIAP 7 kamus (400 kunci/kamus); (3) vitest PENUH 23 berkas/523 tes LULUS
  (10,21 s, = baseline → 0 regresi); (4) render-check jsdom (applyLocale + kamus ASLI): 7/7 locale 8/8
  banner terisi teks kamus, welcome+terminal nihil → LULUS; (5) glyph fa-circle-info terbukti ada di
  FA 6.5.1 yang dimuat index.html:42. Skrip scratch dihapus (B5). Gate rules-index LOLOS.
- TIDAK TERBUKTI: browser nyata (playwright crash di Termux, tanpa biner browser) → user WAJIB lihat
  sendiri (G3/R20). Deviasi: nol. Catatan fe-dev diteruskan: banner full-width vs kartu settings 540px.
- COMMIT: `a9c7f3b` feat(ui) 9 berkas (+146/−7), explicit staging (no -A). TIDAK di-push (workflow butuh
  perintah user; PR #17 masih terbuka). Laporan: `.opencode/reports/20260910/implementation/0405_banner-halaman-implementasi.md`
  + receipt fe-dev `.opencode/reports/20260910/dev/0357_banner-halaman-fe-receipt.md`.

## 2026-09-10 03:40 — Banner halaman Fase 2: draf copy 8 halaman selesai, tunggu ACC user (ProjectManager)
- User: teksnya dibikinin tim ("ya justru itu, buatin dong teksnya") → asumsi Fase 1 (teks dari user) DICABUT user.
- PM baca penuh 8 section + modul JS + model backend (models.py, usage_router.py, selfheal.py, proxy_selector.py) → 8 draf ID ≤140 char, semua klaim berbukti file:line.
- TEMUAN: skill `aigatedoc-copywriting-skill` yang dirujuk instruksi TIDAK ADA (ls .opencode/skills = 8 direktori, grep "aigatedoc" repo = 0). Gaya suara diambil dari language.md + mikrocopy id.js yang hidup. Dilaporkan ke user, tidak pura-pura baca.
- Kunci baru: 8× `page_desc.<view>` di 7 kamus sekaligus (parity guard i18n.test.js:81 aman). Rekom urut: opsi A (ACC ID dulu → translate 6 bahasa → fe-dev sekali jalan).
- Laporan: `.opencode/reports/20260910/research/0338_banner-copy-draft.md`. Nol perubahan src, nol sub-agent. NEXT: ACC/edit 8 draf + ACC opsi A → turun fe-dev.

## 2026-09-10 03:30 — Banner tujuan halaman: Fase 0+1 selesai, tunggu user (ProjectManager)
- User minta banner "tujuan halaman" di semua halaman kecuali home + terminal; teks dikasih user per halaman (belum dikasih).
- PM kerjakan read-only sendiri (inventarisasi, bukan implementasi — boleh, A2 cuma larang PM nulis src/tests). Cek poin: 10 view di satu `index.html` (SPA, tanpa route URL), home=`welcome` (:164), terminal (:676), target 8: settings/providers/combos/proxies/endpoints/usage/analytics/cli.
- Proposal: Opsi B (elemen `.page-banner` anak pertama tiap section + kunci i18n `page_desc.<view>` di 7 kamus, parity guard jaganya) DIREKOMENDASIKAN; Opsi A (banner tunggal + hook showView) ditolak (nyentuh app.js sentral + risiko flex terminal).
- Sub-agent TIDAK diturunkan (perintah user: tunggu teks + ACC). Laporan: `.opencode/reports/20260910/research/0324_banner-halaman-inventarisasi-proposal.md`. Checkpoint awal: `refactor/ui` @ e8ce6ae bersih.
- Hasil: menanti jawaban user atas daftar isian 1–8 + persetujuan opsi.

## 2026-09-10 01:35 — PM decided wrong → user correction recorded (R51 + R52) (ProjectManager)

### Violation
- Rule broken: `.opencode/rules/language.md:2` ("English caveman ultra") + R46 (typo user wajib
  dikoreksi) + `task-report.md` (laporan wajib ditulis di awal) + R51 (kredensial dari `.env`).
- What PM did: jawab user dengan tabel/uraian panjang berkali-kali, nggak koreksi typo
  ("operation_rule.md", "kitq"), nawarin nyimpen kredensial di luar `.env`, dan sempat
  ngaku "nggak bisa push" tanpa cek `.env`/rules.

### Correction
- Durable rule captured: **R52** — caveman ultra HANYA untuk penulisan berkas `.md`; komunikasi
  & konfirmasi ke user tetap bahasa Indonesia casual normal, jelas, non-IT, tanpa singkatan.
  (Amandemen `language.md` dieksekusi di langkah (d).)
- User juga mutusin: **R28 diganti Graphify** (bukan codegraph), **lebur 51 rule boleh** (teks
  lama diarsip, nggak dihapus), **(c) diserahkan ke PM** → keputusan PM: kanal wajib-baca =
  `AGENTS.md` (nol kode, terbukti ke-load), plugin `chat.system.transform` DITUNDA (YAGNI/R38).

### Prevention
- Mechanism: (1) PM wajib baca `.opencode/rules/*.md` + indeks rule SEBELUM aksi apa pun
  (dilakukan di langkah (a) dan langsung nangkep 4 pelanggaran); (2) langkah (b) merampingkan
  51 rule → kelompok tema + indeks auto-generate; (3) langkah (c) mindahin subset wajib ke
  `AGENTS.md` supaya ke-inject tanpa perlu inisiatif baca.
- Verification: jumlah rule lama (51) harus nongol semua di peta old→new hasil (b); `git diff`
  nggak boleh nghapus teks rule mana pun (cuma pindah ke `archive/`).

## Merge `origin/main` + PR #17 — 2026-09-10 (PM)
**Perintah:** user "ok" (setelah ditanya boleh sinkron + bikin PR). **Hasil: PR #17 TERBUKA, mergeable=clean.**
- 4 berkas bentrok diselesaiin: v2 + arsip aktif menang, salinan versi main dipindah ke
  `archive/memory-bank-progress-lama.md` (+59 baris) dan `archive/state-sebelum-v2.md` (+6 baris).
  Verifikasi nol-kehilangan: tiap baris versi `main` dicocokkan ke (berkas aktif ∪ arsip) → **0 ilang**.
- Bonus: header ganda di `OPERATING_RULES.md` v2 (akibat sisipan saya sendiri) dibetulkan → 11.319 B.
- Handover FE dari main (`handover-20260909-fe-test-env.md`) langsung masuk rumah barunya `documents/pm/handovers/`.
- Gate `python3 .opencode/tools/governance/rules-index.py` → LOLOS (11 checks). Suite FE dijalankan sekali
  sebelum commit merge: `node node_modules/.bin/vitest run` di `src/frontend` → **23 berkas / 523 tes lulus**, 11,53 s.
- Commit merge `b5e5886` di-push. PR: https://github.com/fadhly-permata/AI-Gate/pull/17
  (label `documentation` + `enhancement` sesuai H4; isi = sensus, rule v2, kanal wajib-baca, pembersihan
  rujukan hantu, penataan berkas, normalisasi laporan, gerbang pemeriksa, + catatan Graphify yang mentok).

## Langkah (e) — Graphify dipasang sungguh-sungguh lalu DIBLOKIR environment — 2026-09-10 (PM)
**Perintah:** "ganti pake graphify aja" + "3 dan 2 kerjain dulu". **Hasil: BLOCKED, bukan DONE.**
`pkg install -y python-numpy tree-sitter` (numpy 2.4.4 + CLI tree-sitter 0.26.13 OK) → venv luar-repo →
`pip install tree-sitter networkx rapidfuzz` + `--no-deps graphifyy` (0.9.57) → `graphify --help` exit 0.
Tapi uji nyata di fixture 1 file `.py`: `graphify update` = exit 0 dengan
`warning: 1 .py file(s) contributed nothing to the graph ... tree_sitter_python not installed (#1745)`
→ **0 node / 0 edge**. Sebab: `ImportError: dlopen failed: cannot locate symbol
"tree_sitter_python_external_scanner_create"` (binding grammar Python tidak jalan di Android/Termux;
sudah dicoba versi lepas 0.25.0 dan pin `<0.26` force-reinstall → sama). Termux cuma punya grammar
level-C, bukan binding Python-nya.
**Keputusan:** C4 `OPERATING_RULES.md` TETAP berkondisi (nol klaim palsu — F3/no-hallucination);
venv + fixture dihapus (B5, 43 MB); repo nol perubahan kode/venv.
**Sumber identitas (F3, 2 sumber):** PyPI `graphifyy` 0.9.57 requires-python >=3.10 (situs tulis "3.12+uv");
GitHub API `Graphify-Labs/graphify` = **Apache-2.0**, branch default `v8` — situs tulis **MIT** dan
"3.7k+ stars" (API: 116.361). Selisih lisensi STAR jika jadi dipakai → cek sebelum `THIRD_PARTY_NOTICES.md`.
**Opsi buat user:** (i) generate `graph.json` di mesin Linux, query tetap lokal di HP
(`graphify path/explain --graph <file>` tidak butuh LLM); (ii) tetap tanpa kanal graf;
(iii) deep-dive build binding (tidak dijamin berhasil). Detail teknis: `documents/dev/CODE_CHANGES.md`.

## Langkah ⑥+⑧ — pindah berkas `documents/pm/**` + normalisasi laporan — 2026-09-10 (PM)
**Perintah user:** "3 dan 2 kerjain dulu" (= sisa pekerjaan ⑥⑧(e) lalu push).
**⑥ pindah (git mv, nol isi berubah):** `cli-tools-install-backlog` + `wiki-plan` + `wiki-backlog` → `documents/plan/`;
`cli-tools-compatibility` → `documents/config/`; 4 handover root → `documents/pm/handovers/` (total 9 di satu folder);
`status.md` 202.175 B → 11.018 B aktif + `archive/status-2026-09-03_sampai_2026-09-08.md` 191.477 B;
`memory-bank.md` 51.882 B → 21.896 B + `archive/memory-bank-progress-lama.md` 25.740 B +
`archive/memory-bank-decisions-lama.md` 4.660 B (heading `## Decisions` dobel 3x → 1 aktif + 1 penunjuk).
`wiki-drafts/` TIDAK disentuh (R44 ayat 8). Rujukan hidup dibetulkan: `business-analyst.md:11`,
`documents/plan/wiki-{plan,backlog}.md`, `memory-bank.md`, `state.md`. Histori (`CODE_CHANGES.md:139`,
entri `status.md` lama) sengaja tidak ditulis ulang → tidak ada rujukan yang dipalsukan.
**⑧ laporan:** folder `2026-09-03/` → `20260903/` (11 berkas `git mv`); 2 berkas tanpa jam →
`0627_revise_native_run.md` + `20260909/qa/0718_qa_anthropic_inbound_verification.md` (waktu = add-commit git,
karena dokumen tidak memuat jam — sumber dicatat); 1 duplikat byte-identik dihapus
(`2026-09-03_b4_3_qa.md` == `1350_b4_3_qa.md`). Klausul `task-report.md` "folder lama dibekukan"
diperbaiki jadi "dinormalisasi via git mv" (aturan harus mencerminkan kenyataan, bukan sisa usulan).
**Verifikasi:** byte terpelihara (202.495 vs 202.175 = +320 header arsip; 52.296 vs 51.882 = +414);
`git ls-files .opencode/reports` = 28; `grep` sitatan path laporan lama = 0 putus;
gate `rules-index.py` LOLOS, **utang format laporan 0** (sebelumnya 14).
**Sisa:** (e) Graphify belum dipasang (prasyarat `uv` tidak ada; Python 3.14.6 vs diminta 3.12) →
C4 tetap berkondisi; push ke `origin/refactor/ui` = langkah berikutnya.

## 2026-09-10 02:35 — PM decided wrong → user correction recorded (rule v2 + kanal wajib-baca + gate) (ProjectManager)

### Violation
- Rule broken: `AGENTS.md` A1 ayat 4 / `.opencode/rules/request-routing.md` (gua sempat nganggap
  "rule" = sesuatu yang gua inget, bukan berkas yang harus dibaca); `no-hallucination.md` + F3
  (klaim sensus "427 KB" dan "27 laporan" tanpa cek alat — `du -k` membulatkan blok, angka nyata
  403.321 B); R46 (typo user "operation_rule.md" / "kitq" nggak dikoreksi); `language.md`
  (balasan user panjang-polin; harusnya caveman cuma untuk tulis berkas → R52).
- What PM did: jawab pakai angka hasil `du` sebagai byte, tawarin solusi kredensial di luar `.env`,
  dan ngejalanin aksi sebelum baca `.opencode/rules/*.md`.

### Correction
- Durable rule captured: R51 (kredensial → J5), R52 (ruang lingkup caveman → I7 + `language.md`),
  **F4 baru** (klaim ukuran wajib sebut alat + satuan).
- Decision: user nyerahin kepemilikan tulis `.opencode/rules/**` ke PM + nyerahin putusan (c) ke PM.

### Prevention
- Mechanism: (1) `documents/pm/OPERATING_RULES.md` v2 = 50 rule / 10 tema / 11.463 B (v1 52 rule /
  52.698 B diarsipkan utuh) → rule jadi muat dibaca; (2) kanal wajib-baca `AGENTS.md` (12 aturan
  always-on) + `opencode.json` `"instructions": [documents/pm/OPERATING_RULES.md]` → rule ke-inject
  tanpa mengandalkan inisiatif; (3) gerbang `python3 .opencode/tools/governance/rules-index.py`
  (11 pemeriksaan; LOLOS exit 0) nangkep rujukan hantu, ID dobel, rule kepanjangan, path mati;
  (4) 39 baris rujukan hantu (`pm/`, `docs/`, skill `pm-postmortem`, `fullstack-skill`) dibersihin
  di 15 berkas config — sumber salah baca paling sering; (5) `.opencode/skills/pm-orchestration/SKILL.md`
  §6 Record Protocol ditulis beneran (sebelumnya pointer ke skill yang nggak ada).
- Verification: gate exit 0; `grep` rujukan `pm/` basi = 0 di berkas hidup; `wc -c` per kanal
  (AGENTS.md 3.896 B; rules v2 11.463 B; `.opencode/rules/` 12.669 B); `py_compile` + `json.tool`
  bersih; `git diff --check` bersih; `src/**` & `tests/**` nol berubah.
- **User WAJIB restart opencode** supaya AGENTS.md / opencode.json / agent / skill yang baru kebaca.

## Perapian governance — langkah (a) sensus + peta target — 2026-09-10 (PM, mode SEKUENSIAL)
**Perintah user:** "intinya rapihin semua, tapi pastikan lu gak akan pernah nabrak rule lagi" →
pilih **sekuensial** (R16, dicatat di `state.md:multiagent_mode`) → "lanjut" buat langkah (a).
**Yang gua bedain dari sesi-sesi sebelumnya:** sebelum ngapa-ngapain gua **baca penuh**
`.opencode/rules/*.md` (11 berkas, 229 baris) + indeks 51 rule. Ini yang bikin ketahuan:
- **`task-report.md` wajib laporan ditulis DI AWAL** → dibuat:
  `.opencode/reports/20260910/docs/0120_perapian-governance-pm.md` (Indonesia formal, sesuai
  pengecualian `language.md:3`). Ini satu-satunya berkas baru yang gua bikin di langkah (a).
- **`language.md:2` udah nyuruh "English caveman ultra"** buat berkas `.opencode` → jawaban gua
  yang panjang-polin itu pelanggaran, dan "caveman" bukan fitur yang perlu dipasang: rule-nya ada.
- **R46 (koreksi typo user itu wajib)** — juga gua lewatin barusan: user nulis
  "operation_rule.md" (nama asli `OPERATING_RULES.md`) dan "kitq" → harusnya gua koreksi dijawab,
  bukan ikut-ikutan. Dicatat di sini biar nggak keulang.
- **R28 MATI:** "baca kode WAJIB lewat codegraph dulu" (`OPERATING_RULES.md:273`) tapi
  `codegraph` tidak ada di PATH, tidak ada blok `mcp` di `opencode.json`/config global, tidak ada
  skill/command-nya → rule ini pasti dilanggar tiap sesi sejak 2026-09-06. Butuh keputusan user:
  pasang codegraph / ganti pakai Graphify / hapus rule-nya.
**Angka hasil sensus (bukti, bukan kesan):** `documents/pm/` = 19 berkas / **427 KB** = 53% semua
isi `documents/`; `status.md` **195 KB**; `OPERATING_RULES.md` 51 rule / 51 KB; `memory-bank.md`
49 KB. `.opencode/reports/` = 27 laporan, **dua format folder** (`2026-09-03` vs `20260903`) padahal
`task-report.md` minta `[yyyymmdd]`. Kode asli repo: 136 berkas / 51.402 baris (di luar vendor).
**Peta target (usul, belum dieksekusi):** status.md 195 KB → 30 hari + `archive/`; 51 rule → dikelompok
per tema + indeks auto-generate; `cli-tools-*`/`wiki-*` keluar dari `documents/pm/` (bukan wewenang PM);
handover jadi satu folder; `.opencode/rules/` 11 → 4 berkas tema. **Yang TIDAK boleh digeser:**
`documents/{analysis,architecture,api,config}/**` — dirujuk kode (`src/backend/models.py:5`,
`src/backend/gateway/errors.py:8`) → R18/R22.
**Jawaban soal plugin:** bukan plugin luar; 1 berkas lokal `.opencode/plugins/` pakai hook
`experimental.chat.system.transform` (ditegaskan ada di biner opencode 1.17.9). Tapi sesuai **YAGNI
(`code-quality-principles.md`) + R38**, kanal wajib-baca yang udah terbukti = `AGENTS.md` → plugin
ditunda, jadi opsi di langkah (c).
**Jawaban soal Graphify (graphify.net, MIT, Tree-sitter+NetworkX+Leiden):** belum perlu — penyakitnya
dokumen, bukan keterbacaan kode; repo 51 ribu baris masih murah di-grep; prasyarat **Python 3.12 +
uv** tidak tersedia (di sini Python 3.14.6, `uv` tidak ada). Masuk akal hanya kalau sekalian mau
dipakai **menggantikan codegraph di R28** → itu keputusan user, bukan asumsi gua.
**Status:** langkah (a) selesai (sensus + peta target + laporan awal). (b)(c)(d) MENUNGGU ACC user
karena memangkas/menggabung/memindah dokumen governance.

## R51 — kredensial cuma dari `.env` (user koreksi: "dari tadi lu nabrak rule melulu") — 2026-09-10 (PM)
**Pelanggaran gua:** `.opencode/rules/secrets.md` udah bilang "API key / JWT / PAT / token →
store in `.env`; never hardcode; never commit". Tapi pas `git push --delete` gagal (git nggak
manggil `.env`, dan sesi ini nggak punya TTY), gua: (a) nyimpulkan user harus nyediain kredensial,
(b) malah nawarin nyimpen token polos di `~/.git-credentials` / pindah SSH — dua-duanya nabrak
spirit rule. Faktanya **`.env` di root UDAH ADA**: 1 variabel `GITHUB_TOKEN`, classic PAT 40 char,
scope `repo, workflow, write:packages`, permission repo `admin`+`push` (cek lewat header API),
identik dengan `$GITHUB_TOKEN` env (dibuktikan pakai hash pendek, nilai nggak dicetak), dan
`.env` udah ke-gitignore + belum pernah ke-track.
**Verifikasi kemampuan:** `git -c credential.helper='!f(){echo username=x-access-token; echo password=$GITHUB_TOKEN; };f' ls-remote origin HEAD`
→ sukses (bukti `git push` bisa jalan tanpa nyimpen kredensial ke disk).
**Aturan baru R51** (OPERATING_RULES.md): 1) ambil kredensial dari `.env`; 2) sebelum ngaku
"nggak bisa/nggak punya akses" WAJIB cek `.opencode/rules/*.md` + `.env` dulu; 3) DILARANG bikin
penyimpanan kredensial baru tanpa user minta — pakai helper sekali-pakai inline; 4) nilai
kredensial nggak pernah dicetak; 5) `.env` nggak pernah di-commit; 6) token ditolak → lapor fakta +
minta keputusan user.
**Aksi (perintah user: "kerjain nomor 2 lalu nomor 1"):** tulis R51 + mirror ke memory-bank &
state.md (`rules_ref` → R1–R51, `mode: refactor-ui`) → commit → push `refactor/ui` pakai token
dari `.env` (helper inline, nol penulisan ke disk).

## Branch hygiene 2026-09-10 — hapus `fix/fe-test-env` (lokal + GitHub), kerja pindah ke `refactor/ui` (PM)
User: "hapus branch ini dari local dan github, kita pindah ke branch refactor ui".
**Temuan sebelum eksekusi:** branch itu punya 2 commit yang BELUM ada di `main` maupun
`refactor/ui` = aturan **R49** + **R50** dan catatannya (`e87ad53`, `2c5b70b`). Kode perbaikan
tes FE (`95d46e4`) sudah aman di `origin/main` lewat PR #15. Working tree bersih, tidak ada stash.
**Keputusan user (opsi 1 = aman):** selamatkan doc dulu, baru hapus.
- `git checkout refactor/ui` → `git cherry-pick e87ad53 2c5b70b`. Konflik di `state.md` +
  `status.md` (checkpoint/heading lama vs baru) → PM resolv **union, buang checkpoint lama yang
  sudah disuperseded** ("PR #14 open / scroll UNVERIFIED" → fakta baru: merged + sudah dites HP).
  Hasil: `7665074` (R49) + `c5fc038` (R50). `git diff fix/fe-test-env refactor/ui -- OPERATING_RULES.md`
  = **kosong** → isi rules identik, tidak ada yang hilang.
- Lokal: `git branch -D fix/fe-test-env` (butuh `-D`: setelah cherry-pick SHA-nya beda, `-d` nolak).
- Remote: `git push --delete` GAGAL (tidak ada TTY/credential helper; `gh` tidak terpasang) →
  hapus via GitHub API pakai `$GITHUB_TOKEN` → **HTTP 204**; `git remote prune origin` beres.
- Status sekarang: aktif di `refactor/ui`, **ahead 2** dari `origin/refactor/ui` (2 commit doc itu
  BELUM di-push — butuh ACC user). Sisa branch: main, refactor/ui, setup/cli-tools,
  feat/anthropic-inbound (lokal saja), docs/wiki, docs/readme-main, feat/i18n-locales (remote saja).

## Preferensi: setiap PR berlabel tipe (R49) — 2026-09-10 (PM)
User minta PR SELALU pakai label (contoh `bug`). Jadi aturan **R49**: PM auto-klassif
`bug`/`enhancement`/`documentation` (pakai label yang udah ada di repo; label baru butuh ACC user).
Aksi: PR #15 di-tag **`bug`** via API. PR #14 (sudah merged) TIDAK di-retro-tag (user "2 aja").
PR #15 di-MERGE ke main (merge commit; label `bug` ikut ke log). Catatan governance R49 di-
COMMIT ke branch `fix/fe-test-env` supaya ikut ke-main lewat merge PR ini (sebelumnya PR #15
tanpa label — pelajaran).
