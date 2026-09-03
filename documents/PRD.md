# Product Requirement Document (PRD): aigate

## 1. Executive Summary
**aigate** adalah aplikasi berbasis Python (multiplatform) yang berfungsi sebagai AI Proxy Gateway & Management Tool. Aplikasi ini mempermudah pengelolaan *AI Providers*, *Proxy Pools*, *Combos* (routing/load-balancing logic), serta penyediaan *custom Open-AI-compatible endpoints*. Selain itu, **aigate** menyediakan Terminal terintegrasi berbasis `xterm` (multi-tab) lengkap dengan kontrol mengambang (fullscreen & paste) serta dukungan scroll/swipe ala trackpad, dan fitur integrasi instan untuk *CLI tools* (dikelompokkan per kategori) yang secara otomatis mengonfigurasi/memilih model dari provider atau combos yang aktif.

---

## 2. Core Features & Functional Requirements

### 2.1 Providers Management
- **CRUD Provider:** Menambah, mengedit, menghapus, dan melihat daftar AI Provider (seperti OpenAI, Anthropic, OpenRouter, Ollama, LiteLLM, dsb.).
- **Credential Storage:** Menyimpan API Key, Base URL, serta custom headers secara aman.
- **Model Auto-Discovery:** Mengambil daftar model yang tersedia secara otomatis dari provider (jika provider mendukung endpoint `/models`).

### 2.2 Proxy Pools
- **Proxy Configuration:** Mendukung protokol HTTP, HTTPS, dan SOCKS5.
- **Rotation Strategy:** Opsi rotasi proxy (Round Robin, Random, Failover).
- **Health Check:** Pengecekan status latensi dan uptime proxy secara berkala.

### 2.3 Combos (Smart Routing & Fallback)
- **Custom Pipeline:** Menggabungkan beberapa provider/model ke dalam satu grup "Combo".
- **Strategy Selection:**
  - *Fallback:* Mengalihkan request ke provider B jika provider A error/rate limited.
  - *Load Balancing:* Membagi beban request antar provider/model berdasarkan bobot.
  - *Lowest Latency / Cost Optimization:* Mengarahkan ke model tercepat/termurah.

### 2.4 Endpoints
- **OpenAI-Compatible Gateway:** Menyediakan server HTTP lokal (misal: `http://localhost:8080/v1`) yang kompatibel dengan format API OpenAI (`/v1/chat/completions`, `/v1/models`).
- **Endpoint Binding:** Memetakan endpoint ke Provider tertentu atau Combo tertentu.
- **Access Control:** API Key internal opsional untuk mengamankan akses lokal.

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

### 2.6 CLI Tools Auto-Launcher & Auto-Configuration
- **Supported CLI Tools Presets:** Pengelolaan tool CLI populer (seperti `aider`, `interpreter`, `llm`, `sgpt`, `mods`, dll.).
- **Auto-Install Check:**
  - Saat tool diklik, backend mengeksekusi pengecekan perintah (misal: `which aider` atau `where aider`).
  - Jika belum terinstal, jalankan proses instalasi otomatis (misal: `pip install aider-chat` atau via `uv`) langsung di tab terminal aktif.
- **Interactive Model & Provider Picker:**
  - Sebelum menjalankan CLI tool, tampilkan pilihan modal/popup berisi daftar *Provider* atau *Combos* beserta *Model* yang aktif di **aigate**.
- **Auto-Injection Envs/Flags:**
  - Secara otomatis mengeset environment variable (misal: `OPENAI_API_BASE`, `OPENAI_API_KEY`) atau menambahkan argumen flag saat menjalankan command di terminal.

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
