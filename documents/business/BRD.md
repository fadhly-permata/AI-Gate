# Business Requirements Document (BRD): aigate

**Versi:** 1.0
**Tanggal:** 2026-09-03
**Penulis:** Business Analyst (stand-in)
**Sumber rujukan utama:** `documents/PRD.md` (PRD aigate), `pm/memory-bank.md`, `pm/status.md`

---

## 1. Ringkasan Eksekutif (Overview)

**aigate** adalah aplikasi desktop berbasis Python (multiplatform: Windows, macOS, Linux) yang berfungsi sebagai **AI Proxy Gateway & Management Tool**. Produk ini menyatukan pengelolaan *AI Providers*, *Proxy Pools*, *Combos* (logika routing/load-balancing), dan penyediaan *custom OpenAI-compatible endpoints* dalam satu antarmuka. Selain itu, aigate menyertakan Terminal terintegrasi berbasis `xterm.js` (multi-tab) dengan kontrol mengambang (fullscreen & paste) serta dukungan scroll/swipe ala trackpad, dan integrasi instan untuk *CLI tools* (dikelompokkan per kategori) yang secara otomatis mengonfigurasi dan memilih model dari provider atau combos yang aktif.

Tujuan bisnis utama aigate adalah **menurunkan friction** bagi pengembang dan praktisi ML dalam menjalankan agen AI berbasis CLI: tidak perlu lagi mengatur API key, base URL, rotasi proxy, dan failover secara manual di setiap tool. Semua dikelola sekali di aigate, lalu disuntikkan otomatis ke CLI tool pilihan.

## 2. Tujuan Bisnis (Business Objectives)

1. **Konsolidasi pengelolaan AI:** Satu titik kontrol untuk provider, proxy, routing, dan endpoint.
2. **Akselerasi adopsi CLI agentic:** Pengguna dapat menjalankan `claude`, `opencode`, `codex`, `aider`, dan lainnya dalam hitungan detik tanpa setup manual.
3. **Ketahanan (resilience):** Failover otomatis antar provider melalui Combo mengurangi downtime saat satu provider error atau rate-limited.
4. **Efisiensi biaya & latensi:** Strategi routing *lowest latency / cost optimization* menekan biaya inferensi.
5. **Pengalaman terminal natural:** Scroll/swipe velocity-based dan kontrol mengambang membuat aigate nyaman dipakai sebagai workspace utama.

## 3. Stakeholders & User Personas

| Persona | Peran | Kebutuhan utama | Nilai yang diharapkan |
| :--- | :--- | :--- | :--- |
| **Developer / CLI-Agent User** | Engineer yang menjalankan agen coding (`claude`, `opencode`, `aider`, dsb.) | Launcher instan + auto-config model/provider; terminal multi-tab nyaman | Hemat waktu setup; fokus ke coding, bukan konfigurasi |
| **ML Ops / Platform Engineer** | Mengelola banyak provider, proxy, quota | Proxy pools, health check, routing cerdas, access control endpoint | Uptime tinggi, observabilitas, kontrol biaya |
| **Researcher / Autonomous-Agent Builder** | Menjalankan agen otonom (`autogpt`, `crewai`, `openhands`) | Grouping tool, auto-inject env, multi-tab | Eksperimen cepat tanpa boilerplate |
| **Casual Power User** | Pakai chat/shell assistant (`llm`, `sgpt`, `mods`) | Grup C rapi, paste/fullscreen mudah | Pengalaman CLI sehari-hari lebih mulus |
| **Product Owner / BA (internal)** | Menentukan prioritas fitur | Dokumen kebutuhan jelas & teruji | Roadmap terukur |

**Stakeholder eksternal:** Pengguna akhir aigate (individu/ tim kecil praktisi AI). Tidak ada pihak ketiga selain provider AI eksternal.

## 4. Value Proposition & ROI Framing

- **Penghematan waktu (Time-to-First-Token):** Tanpa aigate, setiap CLI tool memerlukan setup env manual (~5–15 menit/tool). Dengan launcher auto-config, turun ke <30 detik. Untuk tim 5 orang × 10 tool = ~12,5 jam/orang/bulan dihemat.
- **Pengurangan kegagalan konfigurasi:** Auto-injection menekan error *wrong API base/key* mendekati nol.
- **Resilience tanpa biaya ops:** Failover Combo mencegah interupsi kerja saat provider down; ROI berupa kontinuitas produktivitas.
- **Native Python run (tanpa deployment & tanpa packaging):** Berjalan langsung sebagai aplikasi Python cross-platform sehingga beban onboarding & dukungan IT rendah.

## 5. User Stories & Acceptance Criteria

Prioritas: **Must-have** (M), **Should-have** (S), **Nice-to-have** (N).
Setiap story merujuk nomor section PRD terkait.

### 5.1 Providers Management (rujukan PRD §2.1)

**US-2.1.1 — CRUD Provider** *(Must-have)*
Sebagai Developer, saya ingin menambah/mengedit/melihat/menghapus AI Provider (OpenAI, Anthropic, OpenRouter, Ollama, LiteLLM, dsb.) agar semua kredensial terpusat.
- *Acceptance:* (1) UI menyediakan form tambah/edit/hapus provider. (2) Daftar provider terlihat lengkap. (3) Hapus provider meminta konfirmasi dan menghapus data terkait.

**US-2.1.2 — Credential Storage Aman** *(Must-have)*
Sebagai ML Ops, saya ingin menyimpan API Key, Base URL, dan custom headers per provider secara aman agar tidak tersebar di env shell.
- *Acceptance:* (1) Field API Key tampil apa adanya (tanpa masking per ADR-007). (2) Data tersimpan plaintext di DB lokal (SQLite) sesuai ADR-007/ADR-010, tanpa enkripsi. (3) Custom headers dapat ditambah sebagai pasangan key-value.

**US-2.1.3 — Model Auto-Discovery** *(Should-have)*
Sebagai Developer, saya ingin aigate mengambil daftar model otomatis dari provider yang mendukung `/models`.
- *Acceptance:* (1) Saat provider ditambah, aigate memanggil endpoint `/models` bila didukung. (2) Daftar model tampil dan bisa dipilih. (3) Bila tidak didukung, user dapat input model manual.

**US-2.1.4 — Multi-Akun per Provider** *(Must-have)*
Sebagai ML Ops, saya ingin menambah beberapa akun per provider agar beban/limit dibagi atau jadi cadangan otomatis.
- *Acceptance:* (1) Satu provider bisa punya ≥1 akun. (2) Routing bisa pilih akun (round-robin) atau pakai sebagai cadangan. (3) Tiap akun punya kredensial sendiri.

**US-2.1.5 — Login OAuth + Token Diperbarui Otomatis** *(Must-have)*
Sebagai Developer, saya ingin login provider resmi (Claude Code, Codex, Cursor, Antigravity, GitHub Copilot, dll) via OAuth tanpa modal token manual, dan token diperbarui otomatis.
- *Acceptance:* (1) Tombol "Connect" memicu OAuth. (2) Token disimpan & diperbarui otomatis sebelum kedaluwarsa (tanpa login ulang). (3) Bila refresh gagal, user diberi tahu.

### 5.2 Proxy Pools (rujukan PRD §2.2)

**US-2.2.1 — Proxy Configuration Multi-Protokol** *(Must-have)*
Sebagai ML Ops, saya ingin mendaftarkan proxy HTTP/HTTPS/SOCKS5 agar traffic ke provider dapat di-routing.
- *Acceptance:* (1) UI menerima input host:port dan tipe protokol. (2) Validasi format address. (3) Proxy tersimpan dan dapat dipilih oleh routing.

**US-2.2.2 — Rotation Strategy** *(Should-have)*
Sebagai ML Ops, saya ingin memilih strategi rotasi (Round Robin / Random / Failover).
- *Acceptance:* (1) Dropdown strategi tersedia. (2) Behavior rotasi sesuai pilihan saat request keluar.

**US-2.2.3 — Health Check** *(Should-have)*
Sebagai ML Ops, saya ingin proxy di-check latensi & uptime berkala agar proxy mati otomatis dilewati.
- *Acceptance:* (1) Status proxy (healthy/dead) tampil. (2) Proxy dead tidak dipakai rotasi. (3) Check berjalan di background.

### 5.3 Combos — Smart Routing & Fallback (rujukan PRD §2.3)

**US-2.3.1 — Custom Pipeline** *(Must-have)*
Sebagai ML Ops, saya ingin menggabungkan beberapa provider/model ke dalam satu Combo agar dipakai sebagai satu tujuan.
- *Acceptance:* (1) UI membuat Combo dari ≥2 anggota provider/model. (2) Combo muncul di daftar & dapat dipilih endpoint/CLI.

**US-2.3.2 — Fallback Strategy** *(Must-have)*
Sebagai Developer, saya ingin request dialihkan ke provider B bila A error/rate-limited.
- *Acceptance:* (1) Bila A gagal (5xx/429), request otomatis ke B. (2) User tidak perlu restart.

**US-2.3.3 — Load Balancing & Cost/Latency Optimization** *(Should-have)*
Sebagai ML Ops, saya ingin strategi load-balancing berbobot dan *lowest latency / cost optimization*.
- *Acceptance:* (1) Bobot tiap anggota dapat diatur. (2) Strategi arahkan ke model tercepat/termurah berfungsi.

**US-2.3.4 — Fallback 3 Tingkat (Langganan→Murah→Gratis)** *(Must-have)*
Sebagai Developer, saya ingin Combo otomatis pindah: langganan → murah → gratis bila kuota habis/error, agar coding tak berhenti.
- *Acceptance:* (1) Tier diurutkan. (2) Bila tier atas habis/error → lanjut tier bawah otomatis. (3) Tidak perlu restart.

**US-2.3.5 — Cadangan Antar-Akun + Sadar Kuota** *(Must-have)*
Sebagai ML Ops, saya ingin Combo memakai akun lain di provider sama bila satu akun kena limit, dan mempertimbangkan sisa kuota saat routing.
- *Acceptance:* (1) Satu anggota Combo bisa punya beberapa akun; bila satu limit → pakai akun lain. (2) Routing preferensi ke langganan yang masih punya kuota.

### 5.4 Endpoints (rujukan PRD §2.4)

**US-2.4.1 — OpenAI-Compatible Gateway** *(Must-have)*
Sebagai Developer, saya ingin server lokal `http://localhost:8080/v1` kompatibel OpenAI (`/v1/chat/completions`, `/v1/models`).
- *Acceptance:* (1) Server jalan otomatis saat aigate aktif. (2) Request format OpenAI dijawab benar. (3) `/v1/models` mengembalikan model terdaftar.

**US-2.4.2 — Endpoint Binding** *(Must-have)*
Sebagai ML Ops, saya ingin memetakan endpoint ke Provider/Combo tertentu.
- *Acceptance:* (1) Setiap endpoint terikat ke satu sumber (provider/combo). (2) Perubahan binding langsung berlaku.

**US-2.4.3 — Access Control** *(Should-have)*
Sebagai ML Ops, saya ingin API key internal opsional mengamankan akses lokal.
- *Acceptance:* (1) Bila diaktifkan, request tanpa key ditolak. (2) Key dapat digenerate & direset.

**US-2.4.4 — Penerjemah Format Antar-Alat** *(Must-have)*
Sebagai Developer, saya ingin aigate menerjemahkan permintaan & jawaban antar format (OpenAI↔Claude↔Gemini↔Cursor↔Kiro↔Vertex↔Antigravity↔Ollama) secara otomatis.
- *Acceptance:* (1) Alat CLI berformat OpenAI bisa dipakai dengan provider mana pun. (2) Terjemahan transparan (client tak perlu tahu). (3) Tidak merusak streaming.

**US-2.4.5 — Penghemat Token (RTK / Caveman / Ponytail)** *(Should-have)*
Sebagai Developer, saya ingin opsi penghemat token: RTK memadatkan hasil alat, mode Caveman menjawab singkat, Ponytail menyuruh AI tulis kode minimal — tiap endpoint bisa nyala/mati.
- *Acceptance:* (1) Toggle per endpoint. (2) RTK kurangi token input 20–40%. (3) Bila gagal, request tetap jalan normal (fail-open).

**US-2.4.6 — Pelacak Kuota & Pemakaian Real-Time** *(Should-have)*
Sebagai ML Ops, saya ingin melihat sisa kuota & hitung mundur reset per provider berlangganan, plus estimasi biaya.
- *Acceptance:* (1) Dashboard tampilkan sisa token & reset countdown. (2) Estimasi biaya tier berbayar. (3) Dipakai routing sadar kuota.

**US-2.4.7 — Log Permintaan (Debug) + Usage Analytics** *(Should-have)*
Sebagai ML Ops, saya ingin mode debug mencatat tiap permintaan/jawaban, plus laporan pemakaian token & tren.
- *Acceptance:* (1) Debug log mencatat header/isi (opsional). (2) Laporan pemakaian per provider/model. (3) Terpisah dari wajib-logging DB (§2.8).

**US-2.4.8 — Export/Import Setting Lokal** *(Should-have, request user)*
Sebagai User, saya ingin export semua setting ke satu file lalu import di device lain, tanpa cloud.
- *Acceptance:* (1) Menu export → file JSON. (2) Import di device lain → setting pulih. (3) Lokal sepenuhnya.

### 5.5 Integrated Multi-Tab Terminal (rujukan PRD §2.5, §2.5.1)

**US-2.5.1 — Web/UI Terminal Multi-Tab** *(Must-have)*
Sebagai Developer, saya ingin terminal `xterm.js` multi-tab via WebSocket PTY di dalam aigate.
- *Acceptance:* (1) Buka ≥1 tab independen. (2) Shell terdeteksi (Bash/Zsh/PowerShell/CMD). (3) Input/output real-time.

**US-2.5.2 — Floating Control: Toggle Fullscreen** *(Must-have)*
Sebagai Developer, saya ingin ikon mengambang untuk memperbesar terminal menutupi seluruh area kerja lalu kembali normal.
- *Acceptance:* (1) Ikon mengambang tampil di area terminal. (2) Klik toggle → fullscreen; klik lagi → normal. (3) State tidak merusak tab lain.

**US-2.5.3 — Floating Control: Paste + Auto Return Focus** *(Must-have)*
Sebagai Developer, saya ingin tombol paste menyuntikkan clipboard ke PTY aktif, lalu fokus input otomatis kembali ke terminal aktif tanpa klik ulang.
- *Acceptance:* (1) Klik paste → isi clipboard masuk ke PTY. (2) Setelah paste, kursor/fokus berada di terminal aktif. (3) Tidak bergantung shortcut OS.

**US-2.5.4 — Scroll Mouse & Trackpad** *(Should-have)*
Sebagai Developer, saya ingin scroll vertikal (dan horizontal bila ada) via roda mouse/trackpad.
- *Acceptance:* (1) Roda mouse scroll buffer. (2) Gesture trackpad horizontal berfungsi bila didukung hardware.

**US-2.5.5 — Swipe → Scroll (bukan navigasi TUI)** *(Must-have)*
Sebagai Developer, saya ingin gesture swipe diubah menjadi scroll buffer (bukan memicu navigasi/escape TUI yang merusak tampilan).
- *Acceptance:* (1) Swipe di area terminal = scroll. (2) Tidak memicu escape/navigasi TUI. (3) Aplikasi TUI yang butuh swipe khusus dapat dikecualikan per-aplikasi.

**US-2.5.6 — Velocity-based Scroll & Damping** *(Should-have)*
Sebagai Developer, saya ingin kecepatan swipe menentukan kecepatan scroll, dengan easing & damping agar natural.
- *Acceptance:* (1) Swipe cepat → scroll cepat (bisa lompat layar). (2) Swipe lambat → halus baris-per-baris. (3) Easing/damping halus di ujung buffer.

### 5.6 CLI Tools Auto-Launcher & Auto-Configuration (rujukan PRD §2.6, §2.6.1)

**US-2.6.1 — CLI Tool Presets & Auto-Install** *(Must-have)*
Sebagai Developer, saya ingin klik tool CLI (mis. `aider`, `llm`) lalu aigate cek `which/where`; bila belum ada, install otomatis di tab terminal.
- *Acceptance:* (1) Klik tool → cek ketersediaan binary. (2) Bila tiada → jalankan `pip install`/`uv` di tab baru. (3) Bila ada → lanjut ke picker.

**US-2.6.2 — Interactive Model & Provider Picker** *(Must-have)*
Sebagai Developer, saya ingin modal berisi daftar Provider/Combo & Model aktif sebelum tool dijalankan.
- *Acceptance:* (1) Modal tampil sebelum eksekusi. (2) Pilihan terbatas pada provider/combo/model aktif. (3) Pilihan disimpan untuk sesi.

**US-2.6.3 — Auto-Injection Envs/Flags** *(Must-have)*
Sebagai Developer, saya ingin aigate menyet `OPENAI_API_BASE`, `OPENAI_API_KEY` (atau flag) ke tab terminal lalu menjalankan CLI tool.
- *Acceptance:* (1) Env disuntikkan sebelum command. (2) Tool berjalan terhadap gateway lokal aigate. (3) Key tidak tertulis plaintext di history shell yang mudah terbaca (best-effort).

**US-2.6.4 — Grouping Tool CLI (Grup A/B/C)** *(Must-have)*
Sebagai Developer, saya ingin tool CLI dikelompokkan: Grup A (Agentic Coding: `claude`, `opencode`, `codex`, `gemini`, `antigravity`, `phi`, `aider`, `goose`, `amp`, `qwen`, `cline`, `kilo`), Grup B (Autonomous Agents: `openhands`, `swe-agent`, `open-interpreter`, `autogpt`, `gpt-researcher`, `crewai`), Grup C (Chat/Shell: `llm`, `sgpt`, `mods`, `oterm`, `gptme`, `aichat`).
- *Acceptance:* (1) UI membagi minimal 3 grup, masing-masing ≥5 preset. (2) Grup A (agentic) ditonjolkan/diutamakan. (3) Daftar dapat diperluas via YAML/JSON (rujukan Roadmap §6).

### 5.7 Antarmuka Web / Admin Console (rujukan PRD §2.7)

**US-2.7.1 — Collapsible Sidebar (ikon saat collapse)** *(Must-have)*
Sebagai Developer, saya ingin sidebar konsol dapat di-collapse/expand; saat collapse tetap menampilkan ikon tanpa teks judul agar navigasi cepat.
- *Acceptance:* (1) Ada tombol toggle collapse/expand. (2) Saat collapse, menu hanya menampilkan ikon (judul tersembunyi). (3) State collapse tersimpan di sisi klien (localStorage) antar sesi.

**US-2.7.2 — Dark / Light Theme Switcher** *(Must-have)*
Sebagai Developer, saya ingin tombol pengalih tema gelap/terang pada UI.
- *Acceptance:* (1) Tersedia pengalih tema di header. (2) Beralih mengubah seluruh tampilan (sidebar + area kerja + terminal). (3) Pilihan tema tersimpan di sisi klien (localStorage).

**US-2.7.3 — Multi-Bahasa (EN/ID)** *(Must-have)*
Sebagai Pengguna, saya ingin UI dapat ditampilkan dalam Bahasa Inggris atau Indonesia.
- *Acceptance:* (1) Pengalih bahasa di header dengan opsi EN & ID (minimal). (2) Mengganti bahasa memperbarui seluruh string UI (menu, label, tombol). (3) Pilihan bahasa tersimpan di sisi klien (localStorage).

### 5.8 Mode Developer, Logging & Self-Heal (rujukan PRD §2.8)

**US-2.8.1 — Custom Port & Developer Mode** *(Must-have)*
Sebagai Developer, saya ingin menjalankan aigate di port pilihan dan mengaktifkan mode developer.
- *Acceptance:* (1) Arg/env `--port` mengubah port listen. (2) Env `AIGATE_DEV=1` mengaktifkan fitur developer di UI.

**US-2.8.2 — UI Responsif + Simulasi Perangkat** *(Must-have)*
Sebagai Developer, saya ingin UI responsif (phone/tablet/desktop) dan di mode developer bisa mensimulasikan perangkat; di layar phone layout bukan AdminLTE.
- *Acceptance:* (1) Layout menyesuaikan breakpoint phone/tablet/desktop. (2) Tombol simulasi phone/tablet/desktop mengubah lebar viewport. (3) Di phone, nav menyederhana (bukan AdminLTE).

**US-2.8.3 — Log Window (dev mode)** *(Must-have)*
Sebagai Developer, saya ingin panel log info/warning/error di UI mode developer.
- *Acceptance:* (1) Panel log tampil di mode developer. (2) Menampilkan log dari database (auto-refresh). (3) Dapat filter severity.

**US-2.8.4 — Mandatory Logging (severity + stacktrace + DB)** *(Must-have)*
Sebagai Developer, saya ingin SETIAP method (frontend & backend) menulis log severity; warning/error menyertakan stacktrace; log di DB; tidak ada try/catch kosong.
- *Acceptance:* (1) Semua method log minimal info. (2) Warning/error menyertakan stacktrace/inner exception. (3) Log tersimpan di DB (`LogEntry`). (4) Tidak ada blok try/catch tanpa penanganan.

**US-2.8.5 — Self-Heal (menu CLI-Tool)** *(Must-have)*
Sebagai Developer, saya ingin fitur Self-Heal di menu CLI-Tool yang membuat branch, menjalankan agentic CLI terinstall, lalu fix/test loop dari log warning/error.
- *Acceptance:* (1) Klik Self-Heal → `git init` bila belum ada repo, buat branch `aigate/self-heal-*`. (2) Bila tidak ada agentic CLI terinstall → popup "Self-Heal tidak bisa jalan: tidak ada agentic CLI terinstall". (3) Ambil log warning+error, jalankan agentic CLI di tab terminal, loop fix→test sampai sehat atau batas iterasi. (4) Setelah issue selesai dikerjakan, baris `LogEntry` terkait dihapus agar tidak di-fix ulang. (5) Setelah seluruh issue terbukti pass, lakukan merge branch
  self-heal ke `main`, pindah ke `main`, dan hapus branch fixing — run berikutnya
  pakai versi latest.

**US-2.8.6 — Konfigurasi di Database** *(Must-have)*
Sebagai Developer, saya ingin seluruh konfigurasi aplikasi tersimpan di SQLite, bukan file terpisah.
- *Acceptance:* (1) Setting (port, mode, toggle, preset CLI) dibaca/ditulis via DB. (2) Tidak ada file config terpisah yang jadi sumber kebenaran.

### 5.9 Chat Playground (rujukan PRD §2.9)

**US-2.9.1 — Percakapan streaming** *(Must-have)*
Sebagai User, saya ingin mengobrol dengan model AI lewat aigate dan melihat jawaban muncul bertahap (streaming), seperti ChatGPT/Gemini.
- *Acceptance:* (1) Kirim pesan → jawaban di-stream (SSE) & dirender bertahap. (2) Jawaban memakai provider/combo terpilih via gateway (format translator + token saver berlaku). (3) Bisa stop generation.

**US-2.9.2 — Multi-sesi + riwayat di DB** *(Must-have)*
Sebagai User, saya ingin banyak sesi chat yang tersimpan & bisa dilanjutkan setelah reload.
- *Acceptance:* (1) Sidebar daftar sesi (buat/ganti nama/hapus). (2) Riwayat pesan disimpan di DB (`ChatSession`/`ChatMessage`). (3) Buka sesi → pesan lama muncul.

**US-2.9.3 — Pilih provider/model/combo** *(Must-have)*
Sebagai User, saya ingin memilih tujuan chat: satu provider+model atau satu combo.
- *Acceptance:* (1) Picker model auto-fetch + search (combobox). (2) Bisa pilih combo untuk routing. (3) Pilihan tersimpan per sesi.

**US-2.9.4 — System prompt & parameter** *(Should-have)*
Sebagai User, saya ingin mengatur system prompt & temperature per sesi.
- *Acceptance:* (1) System prompt diterapkan ke request. (2) Temperature bisa diset.

## 6. Prioritas & Matrix Dampak

| Fitur | Prioritas | Dampak bisnis | Alasan |
| :--- | :--- | :--- | :--- |
| 2.4 Gateway + 2.6 Launcher/Auto-config | Must | Tinggi | Inti value proposition (zero-setup agentic) |
| 2.1 Providers, 2.3 Combos | Must | Tinggi | Fondasi routing & resilience |
| 2.5 Terminal + floating control + swipe/scroll | Must | Sedang-Tinggi | Workspace utama & UX differentiation |
| 2.7 Admin Console UI (sidebar collapse, tema, i18n) | Must | Sedang | Konsol nyaman & akses cepat |
| 2.8 Dev Mode, Logging & Self-Heal | Must | Sedang-Tinggi | Operabilitas & observabilitas |
| 2.2 Proxy Pools | Should | Sedang | Penting untuk region/anti-rate-limit |
| 2.1.3 Auto-discovery, 2.4.3 Access Control | Should | Sedang | Keamanan & kenyamanan |
| 2.5.4/2.5.6 velocity scroll/damping | Should | Sedang | Polesan UX |
| 2.1.4 Multi-akun, 2.1.5 OAuth+refresh | Must | Tinggi | Resilience & kemudahan kredensial |
| 2.3.4 / 2.3.5 3-tier + akun + kuota | Must | Tinggi | Zero-downtime coding |
| 2.4.4 Format translation | Must | Tinggi | Kompatibilitas alat beragam |
| 2.4.5/2.4.6/2.4.7/2.4.8 token saver, kuota, analitik, export | Should | Sedang | Efisiensi & portabilitas |
| 2.9 Chat Playground | Should | Sedang-Tinggi | Uji provider/combo interaktif ala Gemini/ChatGPT |
| Cost limits/telemetry (Roadmap §6) | Nice | Akan datang | Belum di-scope MVP |

## 7. Asumsi & Ketergantungan

- aigate dijalankan natively sebagai aplikasi Python (cross-platform, tanpa deployment & tanpa packaging) → lihat NFR PRD §5 / TSD ADR-009.
- CLI tool mengonsumsi env `OPENAI_API_BASE`/`OPENAI_API_KEY` standar.
- xterm.js + WebSocket PTY tersedia di stack (PRD §3).
- YAML/JSON config untuk ekspansi grup tool (Roadmap §6).

## 8. Definisi Selesai (Definition of Done)

- BRD lengkap & konsisten; setiap fitur inti ≥1 user story ber-acceptance criteria.
- Fitur terminal baru (floating control, scroll/swipe, grouping) tercakup eksplisit.
- Dev/QA dapat menurunkan test case langsung dari acceptance criteria.

---

*Dokumen ini ditulis di bawah scope `docs/business/` sesuai aturan specialist Business Analyst.*
