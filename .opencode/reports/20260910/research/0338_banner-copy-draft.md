# Laporan Tugas: Banner Tujuan Halaman — Fase 2 Draf Copy Berbasis Bukti

## Informasi Dasar
- Tanggal: 2026-09-10
- Jenis Tugas: research (draf copy; TIDAK ada implementasi, TIDAK ada sub-agent)
- Waktu Mulai: 03:38

## Permintaan Pengguna
Fase 1 (lihat `.opencode/reports/20260910/research/0324_banner-halaman-inventarisasi-proposal.md`):
user minta banner tujuan halaman, kecuali home dan terminal. Balasan user atas daftar isian:
"ya justru itu, buatin dong teksnya" — teks dikerjakan oleh tim, bukan oleh user.
Fase 2: draf 8 teks banner Indonesia (≤140 karakter, satu kalimat, tanpa emoji/gaya iklan),
setiap klaim tujuan wajib berbukti `file:line`; contoh baris lintas 7 locale; rekomendasi
urutan kerja; konfirmasi rencana kunci i18n terhadap parity guard.

## Catatan Penting di Awal (fakta, bukan asumsi)
- Skill `.opencode/skills/aigatedoc-copywriting-skill/SKILL.md` yang dirujuk instruksi
  Phase 2 TIDAK ADA. Bukti: `ls .opencode/skills/` menghasilkan 8 direktori
  (be-dev, business-analyst, fe-dev, fullstack-dev, pm-orchestration, qa, system-analyst,
  tech-architect) tanpa nama itu; pencarian `aigatedoc` (case-insensitive) di `documents/`,
  `.opencode/`, `README.md` = 0 hasil.
- Sebagai pengganti gaya suara yang berbukti: `.opencode/rules/language.md` (baris 1–7)
  dan mikrocopy UI Indonesia yang sudah hidup di `src/frontend/static/i18n/id.js`
  (mis. "Tambah Penyedia" :41, "Belum ada penyedia." :57) — netral, singkat, tanpa emoji.
  Istilah baku yang dipakai banner mengikuti id.js: Penyedia (:19), Kombo (:20),
  Pool Proxy (:21), Endpoint (:22), Pengaturan (:25), Pemakaian & Kuota (:321),
  Analitik (:350), Alat CLI (:24).

## Rencana Pekerjaan
1. Baca penuh 8 section halaman di `src/frontend/static/index.html` + modul JS-nya.
2. Petakan tiap halaman ke endpoint dan model backend aslinya (bukti baris doktrin model).
3. Draf 8 teks Indonesia ≤140 karakter dengan maksimum 2 pointer bukti tiap item.
4. Buat contoh baris `page_desc.settings` untuk 7 locale + rekomendasi urutan A/B.
5. Tulis laporan, perbarui dokumen PM; berhenti sebelum implementasi.

## Realisasi Pekerjaan
- [03:38] langkah 1–2 selesai (baca: index.html:174–272, 274–404, 406–486, 488–674,
  756–860; clitools.js, selfheal.js, models.py, usage_router.py, selfheal.py;
  daftar endpoint per modul via pencarian pola `api/…` di tiap file)
- [03:38] langkah 3–5 selesai; panjang teks diukur dengan Python (semua ≤140)

## Peta Bukti per Halaman (fakta terverifikasi)

| Halaman | Fungsi terverifikasi | Endpoint backend (bukti frontend) |
|---|---|---|
| Pengaturan | port, mode pengembang, tema, bahasa, simulasi perangkat + cadangan/pulihkan JSON lokal | `api/settings`, `api/settings/export`, `api/settings/import` (app.js; tautan ekspor index.html:245) |
| Penyedia | daftar/tambah penyedia (openai-compatible, anthropic, ollama, openrouter, litellm, other), Discover Models, akun API key/OAuth, ringkasan pemakaian per penyedia | `api/providers`, `api/accounts`, `api/oauth/` (app.js; modal index.html:807–830) |
| Kombo | grup routing `fallback / load_balance / latency_cost` dengan anggota + prioritas + bobot | `api/combos`, `api/providers` (combos.js; model models.py:162–199) |
| Pool Proxy | kumpulan node proxy + strategi rotasi (`round_robin` default), dipakai egress per endpoint | `api/proxy-pools` (proxies.js; models.py:125–129, :216–218; proxy_selector.py:54) |
| Endpoint | alamat gerbang OpenAI-compatible lokal: listen host/port, kunci akses, binding ke Penyedia ATAU Kombo, pool proxy, mode penghemat token | `api/endpoints` (endpoints.js; models.py:201–246) |
| Pemakaian & Kuota | "Remaining quota + reset countdown per provider" + ringkasan hari/minggu/bulan per provider/model + baris pemakaian terakhir | `api/quota`, `api/usage`, `api/usage/summary` (usage.js; usage_router.py:189–191) |
| Analitik | dasbor tren (range, group by model/provider, metrik token/permintaan/biaya, ekspor CSV, estimasi penghematan) + penampil log permintaan debug | `api/analytics`, `api/analytics/export`, `api/request-logs` (analytics.js; index.html:580–674) |
| Alat CLI + Self-Heal | peluncur alat CLI AI ke TAB TERMINAL BARU (B3.3/B3.4) + badge kompatibilitas per platform; Self-Heal = orkestrator cabang git + agentic CLI + loop fix/test yang tampil di tab hidup | `api/cli-tools`, `api/cli-tools/resolve`, `api/self-heal*` (clitools.js:1–5; selfheal.py:1–20) |

## a) Delapan Draf Banner (format: teks — jumlah karakter — bukti)

1. **Pengaturan** — "Atur port, tema, bahasa, mode pengembang, dan tampilan perangkat;
   lalu cadangkan atau pulihkan semua pengaturan dari satu berkas." — 129 —
   `index.html:180-224` (lima baris formulir), `index.html:236-246` (kartu Backup &
   Restore, ekspor `/api/settings/export` di :245).
2. **Penyedia** — "Daftarkan layanan AI sumber model Anda, isi kunci API atau OAuth,
   temukan daftarnya, dan pantau pemakaian tiap penyedia." — 120 —
   `index.html:277-280` (tambah penyedia), `index.html:306-308` + `:332-360`
   (Discover Models; akun API key/OAuth), `index.html:379-400` (usage summary per penyedia).
3. **Kombo** — "Gabungkan beberapa Penyedia dan model jadi satu alamat dengan aturan
   cadangan otomatis atau pembagian beban; atur prioritas dan bobotnya." — 137 —
   `models.py:163` ("Routing group (fallback / load_balance / latency_cost)"),
   `models.py:190-191` (kolom `priority`, `weight` pada ComboMember).
4. **Pool Proxy** — "Kelompokkan beberapa proxy dan tentukan cara pemakaiannya diputar,
   supaya panggilan keluar tidak menumpuk pada satu jalur." — 122 —
   `models.py:126-132` ("A pool of proxy nodes with a rotation strategy", default
   `round_robin`), `models.py:216-218` (ADR-008: endpoint → pool = "per-endpoint egress proxy").
5. **Endpoint** — "Atur alamat gerbang lokal tempat aplikasi memanggil model: port,
   kunci akses, tujuan Penyedia/Kombo, proxy keluar, dan hemat token." — 131 —
   `models.py:202-203` ("Local OpenAI-compatible gateway endpoint") + `:209-228`
   (field listen/access key/pool/token_saver), `models.py:236-241` (binding provider ATAU combo).
6. **Pemakaian & Kuota** — "Pantau sisa kuota dan hitungan mundur reset tiap Penyedia,
   serta ringkas pemakaian permintaan, token, dan biaya dari harian sampai bulanan." — 139 —
   `usage_router.py:190-191` ("Remaining quota + reset countdown per provider"),
   `index.html:495-503` + `:520-527` (kolom tabel kuota; pemilih rentang day/week/month).
7. **Analitik** — "Lihat tren pemakaian, total dan rincian biaya per model atau Penyedia,
   ekspor CSV, serta log permintaan mentah untuk keperluan perbaikan." — 137 —
   `index.html:586-605` (kontrol range/group by/metric/Refresh/Export CSV),
   `index.html:637-647` (kartu Request Log debug + toggle enable).
8. **Alat CLI** — "Jalankan alat CLI AI lewat tab terminal dari halaman ini, cek catatan
   kompatibilitasnya, dan gunakan Self-Heal untuk perbaikan." — 127 —
   `clitools.js:1-5` ("launcher … launch into a NEW terminal tab"), `selfheal.py:1-6`
   (orkestrator branch + agentic CLI + fix/test loop).

Catahan keandalan: jumlah preset CLI (24) SENGAJA tidak disebut di banner agar teks tidak
basi saat daftar bertambah (kebijakan "Daftarnya masih terus dikembangkan", memory bank).

## b) Contoh Baris `page_desc.settings` (7 locale — draf terjemahan, belum ditinjau penutur asli)

- en: "Configure how aigate runs — port, theme, language, developer mode, device view — then back up or restore every setting from one file."
- id: "Atur port, tema, bahasa, mode pengembang, dan tampilan perangkat; lalu cadangkan atau pulihkan semua pengaturan dari satu berkas."
- ru: "Настройте работу aigate: порт, тему, язык, режим разработчика, вид устройства; затем сохраните или восстановите все настройки одним файлом."
- nl: "Stel in hoe aigate werkt — poort, thema, taal, ontwikkelaarsmodus, apparaatweergave — en maak een back-up van alle instellingen of herstel ze."
- ja: "aigate の動作（ポート、テーマ、言語、開発者モード、端末表示）を設定し、全設定のバックアップと復元もここで行えます。"
- zh: "在这里调整 aigate 的运行设置——端口、主题、语言、开发者模式、设备预览——并可用单个文件备份或恢复全部设置。"
- zh-tw: "在這裡調整 aigate 的執行設定——連接埠、主題、語言、開發者模式、裝置預覽——並可用單一檔案備份或復原全部設定。"

## c) Urunan Kerja — Rekomendasi: OPSI A
**A. Setujui draf Indonesia dulu (8 kalimat) → baru terjemahkan 6 bahasa lain → fe-dev
kerjakan sekali jadi.** Alasan satu baris: koreksi wording paling murah dilakukan sebelum
berlipat tujuh; opsi B membuat ulang 42 entri terjemahan kalau teks Indonesia berubah.

## d) Kunci i18n dan Parity Guard
Kunci baru (8): `page_desc.settings`, `page_desc.providers`, `page_desc.combos`,
`page_desc.proxies`, `page_desc.endpoints`, `page_desc.usage`, `page_desc.analytics`,
`page_desc.cli`. Parity guard (src/frontend/tests/i18n.test.js:81–88) memaksa SETIAP berkas
kamus punya set kunci yang sama; rencana ini menambahkan 8 kunci yang sama ke KETUJUH berkas
(`static/i18n/{en,id,ru,nl,ja,zh,zh-tw}.js`) sekaligus dalam satu commit fe-dev — guard lolos
karena tidak ada bahasa yang tertinggal. Ini menepati default Fase 1 butir e.1 (isi nilai nyata
per bahasa, bukan teks mentah satu bahasa yang membuat locale lain jatuh ke raw key).

## Status Akhir
Sebagian (sesuai desain) — Fase 2 SELESAI: 8 draf teks Indonesia berbukti + contoh 7 locale +
rekomendasi urutan. Implementasi MASIH DITAHAN: menunggu (i) persetujuan/penyuntingan 8 draf
oleh user, (ii) persetujuan opsi A, (iii) ACC turun fe-dev (scope `src/frontend/**`).
Belum ada berkas src/** yang berubah; belum ada sub-agent yang diturunkan.
