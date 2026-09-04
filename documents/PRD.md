# Product Requirement Document (PRD): aigate

## 1. Executive Summary
**aigate** adalah aplikasi berbasis Python (multiplatform) yang berfungsi sebagai AI Proxy Gateway & Management Tool. Aplikasi ini mempermudah pengelolaan *AI Providers*, *Proxy Pools*, *Combos* (routing/load-balancing logic), serta penyediaan *custom Open-AI-compatible endpoints*. Selain itu, **aigate** menyediakan Terminal terintegrasi berbasis `xterm` (multi-tab) lengkap dengan kontrol mengambang (fullscreen & paste) serta dukungan scroll/swipe ala trackpad, dan fitur integrasi instan untuk *CLI tools* (dikelompokkan per kategori) yang secara otomatis mengonfigurasi/memilih model dari provider atau combos yang aktif.

---

## 2. Core Features & Functional Requirements

### 2.1 Providers Management *(adopsi dari 9router)*
- **CRUD Provider:** kelola 40+ penyedia AI (OpenAI, Anthropic, Gemini, OpenRouter, Ollama, LiteLLM, dsb) dalam satu daftar.
- **Penyimpanan Kredensial:** simpan API Key, Base URL, dan custom headers. Untuk penyedia resmi (Claude Code, Codex, Cursor, Antigravity, GitHub Copilot, dll) mendukung login OAuth + **token diperbarui otomatis** (tanpa login ulang manual).
- **Multi-Akun:** bisa menambah beberapa akun per penyedia; dibagi beban (round-robin) atau jadi cadangan otomatis.
- **Model Auto-Discovery:** ambil daftar model otomatis dari penyedia yang mendukung endpoint `/models`.

### 2.2 Proxy Pools *(fitur tambahan aigate — tidak diadopsi dari 9router — opsional)*
- **Opsional:** Fitur ini tidak wajib. Tanpa proxy yang diisi, aigate tetap menghubungi penyedia AI secara langsung (berjalan normal).
- **Proxy Configuration:** Mendukung protokol HTTP, HTTPS, dan SOCKS5.
- **Rotation Strategy:** Opsi rotasi proxy (Round Robin, Random, Failover).
- **Health Check:** Pengecekan status latensi dan uptime proxy secara berkala.

### 2.3 Combos (Smart Routing & Fallback) *(adopsi dari 9router)*
- **Custom Pipeline:** gabungkan beberapa provider/model ke dalam satu grup "Combo" (bisa campur langganan, murah, dan gratis).
- **Fallback 3 Tingkat:** otomatis pindah berurutan — (1) langganan → (2) murah → (3) gratis — kalau kuota habis atau error, supaya coding gak berhenti.
- **Cadangan Antar-Akun:** kalau satu akun kena limit, pindah ke akun lain di penyedia yang sama (multi-akun, lihat 2.1).
- **Sadar Kuota:** routing mempertimbangkan sisa kuota/limit tiap provider (lihat bagian Pelacak Kuota) supaya langganan dipakai optimal dulu.
- **Load Balancing & Tercepat/Termurah:** bagi beban antar provider berdasar bobot, atau arahkan ke model tercepat/termurah (tetap dipertahankan sebagai opsi).

### 2.4 Endpoints *(adopsi dari 9router)*
- **OpenAI-Compatible Gateway:** server HTTP lokal (misal `http://localhost:8080/v1`) yang kompatibel format API OpenAI (`/v1/chat/completions`, `/v1/models`).
- **Penerjemah Format Antar-Alat:** aigate otomatis menerjemahkan permintaan & jawaban antar format berbeda — OpenAI ↔ Claude ↔ Gemini ↔ Cursor ↔ Kiro ↔ Vertex ↔ Antigravity ↔ Ollama. Jadi alat CLI apa pun yang cuma paham format OpenAI bisa dipakai dengan penyedia mana pun.
- **Endpoint Binding:** memetakan endpoint ke Provider atau Combo tertentu.
- **Access Control:** API Key internal opsional untuk mengamankan akses lokal.

### 2.4.1 Penghemat Token (Token Savers) *(adopsi dari 9router)*
- **RTK Token Saver:** otomatis memadatkan hasil alat (seperti `git diff`, `grep`, `ls`, `tree`) sebelum dikirim ke AI — hemat 20–40% token input per request. Kalau gagal, pakai teks asli (aman, gak bikin request rusak).
- **Mode Caveman:** menyuntikkan gaya jawaban singkat & padat ke AI → hemat hingga 65% token output (isi teknis tetap utuh).
- **Ponytail (Senior Malas):** menyuntikkan instruksi "tulis kode minimal, utamakan yang sudah ada" → output lebih pendek & lebih sedikit refactoring.
- Semua bisa diatur nyala/mati per endpoint di konsol.

### 2.4.2 Pelacak Kuota & Pemakaian *(adopsi dari 9router)*
- **Kuota Real-Time:** tampilkan sisa token & hitung mundur reset (per jam / harian / mingguan) tiap provider berlangganan.
- **Estimasi Biaya:** perkiraan biaya untuk tier berbayar.
- **Optimasi Langganan:** bantu pakai seluruh kuota langganan sebelum reset supaya gak terbuang.
- **Sadar Kuota di Routing:** dipakai Combo (lihat 2.3) untuk menentukan kapan pindah ke tier murah/gratis.

### 2.4.3 Log Permintaan & Laporan Pemakaian *(adopsi dari 9router)*
- **Request Logging:** mode debug mencatat seluruh permintaan & jawaban (header, isi) untuk bantu cari masalah.
- **Usage Analytics:** lacak token & tren pemakaian per provider/model; laporan bulanan + perkiraan penghematan dari fitur token saver.
- **Catatan:** ini beda dengan wajib-logging ke database di 2.8 (punya aigate) — 2.4.3 fokus ke analitik & debug level permintaan.

### 2.4.4 Export & Import Setting (Lokal) *(pengganti cloud sync — request user)*
- **Export:** menu di konsol untuk menyimpan SELURUH setting (provider, combo, akun, proxy, endpoint, preferensi) ke satu file (misal `aigate-settings.json`).
- **Import:** buka file tersebut di device lain → semua setting langsung pulih, gak perlu setup ulang.
- **Lokal sepenuhnya:** gak ada kirim-ke-cloud; file ada di tangan lu. (Alternatif dari sinkron cloud 9router.)

### 2.5 Integrated Multi-Tab Terminal (xterm)
- **Web-based / UI Terminal:** Menggunakan `xterm.js` yang terhubung via WebSocket ke backend PTY (Pseudo-Terminal) Python.
- **Multi-Tab Support:** Membuka banyak tab terminal secara independen di dalam aplikasi UI.
- **Shell Auto-Detect:** Mendukung Bash/Zsh di Linux/macOS dan PowerShell/CMD di Windows.
- **Floating Control (Kontrol Mengambang):** Ikon mengambang di dalam area terminal untuk akses cepat:
  - **Toggle Fullscreen:** Memperbesar terminal menutupi seluruh area kerja (dan kembali ke ukuran normal).
  - **Paste:** Tombol tempel yang menyuntikkan isi clipboard langsung ke PTY aktif tanpa bergantung shortcut OS. Setelah menempel, fokus input langsung dikembalikan ke terminal aktif agar user bisa mengetik lanjutan tanpa klik ulang.

### 2.5.1 Scroll & Swipe (Trackpad / Mouse)
- **Scroll Mouse & Trackpad:** Mendukung scroll vertikal (dan horizontal bila tersedia) melalui roda mouse atau gesture trackpad.
- **Swipe → Scroll (bukan navigasi TUI):** Pada banyak aplikasi TUI, gesture swipe sering salah ditangani (memicu navigasi/escape yang merusak tampilan). aigate mengubah event swipe menjadi proses scroll pada buffer terminal.
- **Respons Natural & Berbasis Kecepatan (Velocity-based):** Kecepatan swipe menentukan kecepatan scroll — swipe cepat menghasilkan scroll layar cepat (bisa melompat beberapa layar), swipe lambat menghasilkan scroll halus baris-per-baris. Diberikan efek easing agar terasa natural, tidak *abrupt*.
- **Damping & Batas:** Scroll diberi peredaman (*damping*) agar berhenti halus di ujung buffer. Aplikasi TUI yang memang membutuhkan input swipe khusus dapat dikecualikan per-aplikasi bila diperlukan.

### 2.6 CLI Tools Auto-Launcher & Auto-Configuration *(inti adopsi dari 9router, diperkaya aigate)*
- **Sambungkan Alat ke Pintu API:** intinya, alat CLI (Claude Code, Codex, Cursor, Cline, OpenCode, dsb) cukup diarahkan ke endpoint aigate (`http://localhost:8080/v1`) + API key aigate, lalu jalan lewat provider/combo pilihan. Ini cara kerja yang diadopsi dari 9router.
- **Auto-Install Check (tambahan aigate):** saat tool diklik, backend cek dulu apakah terpasang (`which aider`/`where aider`); kalau belum, pasang otomatis (`pip install`/`uv`) di tab terminal aktif.
- **Interactive Model & Provider Picker:** sebelum jalan, tampilkan popup berisi daftar Provider/Combo + Model aktif di aigate.
- **Auto-Injection Envs/Flags (tambahan aigate):** otomatis set environment (`OPENAI_API_BASE`, `OPENAI_API_KEY`) atau tambah flag saat menjalankan command di terminal.

### 2.6.1 Pengelompokan Tool CLI (Grouping)
Daftar tool CLI dikelompokkan agar mudah ditemukan. Setiap grup minimal berisi 5 preset. Prioritas utama: *agentic CLI* (agen coding & otomatisasi).

- **Grup A — Agentic Coding Assistants (Asisten Coding Agen):**
  `claude` (Claude Code), `opencode`, `codex` (OpenAI Codex CLI), `gemini` (Gemini CLI), `antigravity` (Google Antigravity), `phi` (Microsoft Phi), `aider`, `goose` (Block Goose), `amp` (Sourcegraph Amp), `qwen` (Qwen Code), `cline`, `kilo` (Kilo Code).
- **Grup B — Autonomous Software Agents (Agen Perangkat Lunak Otonom):**
  `openhands`, `swe-agent`, `open-interpreter` (interpreter), `autogpt`, `gpt-researcher`, `crewai`.
- **Grup C — Chat & Shell Assistants (Asisten Obrolan & Shell):**
  `llm` (simonw/llm), `sgpt` (shell-gpt), `mods`, `oterm`, `gptme`, `aichat`.

> Catatan: Daftar di atas dapat diperluas via config YAML/JSON (lihat Roadmap 6).

### 2.7 Antarmuka Web (Admin Console)
Konsol manajemen (Providers, Combos, Proxy Pools, Endpoints, CLI Tools) serta
Terminal terintegrasi disajikan dalam **antarmuka web lokal** bergaya
**AdminLTE** (sidebar kiri + area kerja kanan), tanpa framework/build JavaScript
(lihat TSD ADR-001 & §3.4):
- **Collapsible Sidebar:** Sidebar dapat di-expand/collapse. Saat collapse, tetap
  menampilkan menu **minimal berupa ikon** (tanpa teks judul) agar navigasi tetap
  cepat.
- **Dark / Light Theme Switcher:** Tersedia tombol pengalih tema gelap/terang;
  preferensi disimpan di sisi klien (localStorage).
- **Multi-Bahasa (i18n):** UI mendukung minimal **Bahasa Inggris & Indonesia**;
  pemilihan bahasa via pengalih di header; string UI dikelola dalam kamus
  terjemahan sisi klien (extensible ke bahasa lain via config).

### 2.8 Mode Developer, Logging & Self-Heal
aigate memiliki mode operasional ekstra (diaktifkan via flag run / env `AIGATE_DEV=1`):
- **Custom Port & Developer Mode:** Server dijalankan di port arbitrer (arg
  `--port` / env) dan mode developer menyalakan fitur operasional di bawah.
- **UI Responsif + Simulasi Perangkat:** UI menyesuaikan layout untuk phone /
  tablet / desktop; di mode developer tersedia tombol simulasi perangkat
  (phone/tablet/desktop). **Untuk layar phone, layout TIDAK menggunakan gaya
  AdminLTE** (nav disederhanakan, mis. bottom-nav) demi kenyamanan mobile.
- **Log Window:** Panel log (info/warning/error) di UI (mode developer) terhubung
  ke log yang tersimpan di database.
- **Mandatory Logging:** SETIAP method (frontend & backend) WAJIB menulis log
  dengan severity (info / warning / error). Untuk **warning & error wajib
  menyertakan stacktrace / inner exception**. Log disimpan ke database (ERD
  `LogEntry`). SETIAP method WAJIB membungkus logic rentan dalam try/catch —
  **dilarang try/catch kosong** (no empty catch). Aturan wajib (code-review gate).
- **Self-Heal (menu CLI-Tool):** (1) pastikan repo git ada (`git init` bila
  belum), (2) buat branch baru `aigate/self-heal-*`, (3) tentukan agentic CLI
  yang **sudah terinstall** (Grup A); bila tidak ada → popup "Self-Heal tidak
  bisa jalan: tidak ada agentic CLI terinstall", (4) ambil log severity warning
  & error, (5) jalankan agentic CLI di tab terminal untuk memperbaiki berdasar
  log, (6) loop fix→test→fix→test sampai benar-benar "sembuh" (tidak ada lagi
  log warning/error) atau batas iterasi. (7) Setelah suatu issue/bug/warning
  selesai dikerjakan, **hapus baris `LogEntry` terkait** agar isu yang sama tidak
  di-fix ulang. (8) Setelah **seluruh issue terbukti pass** (test hijau / build
  hijau), lakukan `git merge` branch `aigate/self-heal-*` ke `main`, `git checkout
  main`, lalu **hapus branch fixing** tersebut — sehingga run berikutnya memakai
  versi aigate terbaru (latest).
- **Konfigurasi di Database:** SELURUH konfigurasi aplikasi (port default, mode,
  toggle fitur, preset CLI, dst.) disimpan di **SQLite (DB)**, bukan file
  terpisah. (Secret tetap plaintext di DB sesuai ADR-007 — tanpa enkripsi.)

### 2.9 Chat Playground *(fitur tambahan aigate — UI percakapan ala Gemini/ChatGPT)*
aigate menyediakan halaman **chat** di web console untuk mengobrol langsung dengan
model AI lewat gateway — mirip Gemini/ChatGPT, tapi memakai provider/combo yang
sudah dikonfigurasi di aigate (bukan layanan pihak ketiga).
- **Pilih tujuan:** tiap sesi chat memakai satu **Provider+Model** atau satu
  **Combo** (routing) yang sudah ada; picker model memakai combobox auto-fetch +
  search (lihat §2.3/§2.7).
- **Percakapan streaming:** user kirim pesan → respons model dialirkan **streaming**
  (SSE) dan dirender bertahap. Payload dibangun dari riwayat sesi, diteruskan ke
  gateway `/v1/chat/completions` (penerjemah format + token saver + kuota tetap
  berlaku, transparan).
- **Multi-sesi + riwayat:** daftar sesi di sidebar (buat/ganti nama/hapus). Riwayat
  pesan **disimpan di DB** (`ChatSession`, `ChatMessage`) sehingga bertahan setelah
  reload dan bisa dilanjutkan.
- **Parameter:** system prompt per sesi, temperature, dll.
- **Tetap lokal:** tidak ada pengiriman ke layanan chat pihak ketiga; hanya ke
  provider yang user konfigurasi. Memakai fitur yang sudah ada (providers, combos,
  format translator, token saver, usage tracking) — bukan mesin LLM baru.

---

## 3. Technology Stack Recommendations

| Component | Technology / Library |
| :--- | :--- |
| **Language** | Python 3.10+ |
| **GUI Framework** | `CustomTkinter` / `PyQt6` / `PySide6` ATAU Web-based UI (`FastAPI` + `NiceGUI` / `Flet` / `Streamlit`) |
| **Local Gateway Server** | `FastAPI` + `Uvicorn` / `httpx` |
| **PTY / Terminal** | `ptyprocess` (Unix), `pywinpty` (Windows), `xterm.js` via WebSocket |
| **Configuration Engine** | SQLite (via `SQLAlchemy` / `peewee`) atau JSON/YAML storage |

---

## 4. Architecture & Workflow

[KODE_KONTAINER]
+-----------------------------------------------------------------------+
|                              aigate UI                                |
|  +-------------------+  +------------------------------------------+  |
|  | Providers/Combos  |  | Multi-Tab Terminal (xterm.js)            |  |
|  | & Proxy Pools     |  | +-----------------+  +-----------------+ |  |
|  | Management        |  | | Tab 1: bash     |  | Tab 2: aider    | |  |
|  +---------+---------+  +--------+----------+--+-----------------+ |  |
+------------|---------------------|------------------------------------+
             |                     | (WebSocket / PTY)
             v                     v
+-----------------------------------------------------------------------+
|                          aigate Core (Python)                         |
|  +-------------------+  +--------------------+  +------------------+  |
|  | Local Gateway     |  | CLI Tool Manager   |  | Proxy & Routing  |  |
|  | (OpenAI API /v1)  |  | & Auto Injector    |  | Engine           |  |
|  +-------------------+  +--------------------+  +------------------+  |
+-----------------------------------------------------------------------+
[KODE_KONTAINER]

### CLI Tool Execution Flow:
1. User memilih/klik CLI tool dari daftar UI.
2. App mengecek ketersediaan binary tool.
3. Jika **belum ada**: Buka tab terminal baru -> jalankan instalasi (`pip install ...`).
4. Jika **sudah ada**: Pop-up dialog meminta user memilih *Provider/Combo* & *Model*.
5. App membuka tab terminal baru, menyuntikkan `OPENAI_API_BASE="http://localhost:8080/v1"`, `OPENAI_API_KEY="..."`, lalu menjalankan CLI tool dengan model yang dipilih.

---

## 5. Non-Functional Requirements
- **Multiplatform:** Berjalan **native** di Windows, macOS, dan Linux sebagai aplikasi Python (cross-platform, tanpa perlu deployment/container).
- **Low Footprint:** Penggunaan CPU dan RAM yang efisien saat idle.
- **Native Execution (tanpa deployment & tanpa packaging):** aigate dijalankan langsung sebagai aplikasi Python (`python -m aigate` / `uvicorn aigate.server:app`) — tidak memerlukan deployment, container, maupun packaging single-binary. (Lihat TSD ADR-009.)

---

## 6. Future Roadmap
- Telemetry & Usage Analytics (Token usage per Provider/Combo).
- Cost limits & Rate limiting per Endpoint/Key.
- Custom Plugin support untuk CLI tools tambahan via YAML/JSON config.
