# Functional Specification Document (FSD): aigate

**Versi:** 1.0
**Tanggal:** 2026-09-03
**Penulis:** System Analyst (stand-in)
**Sumber rujukan:** `documents/PRD.md` (PRD aigate), `docs/business/BRD.md` (BRD aigate), `pm/memory-bank.md`, `pm/status.md`
**Storage engine target:** SQLite (lihat PRD §3 — Configuration Engine)

---

## 0. Pendahuluan & Konvensi Dokumen

Dokumen ini mendefinisikan spesifikasi fungsional target-state untuk produk **aigate**. Semua spesifikasi menggambarkan *bagaimana fitur seharusnya bekerja* (target state), bukan implementasi kode. Setiap spesifikasi fitur dilengkapi:

- **Deskripsi fungsional** — apa yang dilakukan fitur.
- **Input / Output** — data yang masuk dan keluar.
- **Process flow** — alur langkah (step list).
- **Traceability** — pemetaan ke ID User Story di BRD (`docs/business/BRD.md`).

Entitas penyimpanan (data model) dijelaskan terpisah di `ERD.md`.

---

## 1. Model State (Current vs Target)

### 1.1 Current State
- Belum ada produk; hanya dokumen kebutuhan (PRD, BRD) dan rencana PM.
- Tidak ada konfigurasi tersimpan, tidak ada gateway berjalan.

### 1.2 Target State
- Aplikasi desktop Python multiplatform dengan:
  - Config engine SQLite menyimpan Provider, ProxyPool, Combo, Endpoint, grouping CLI, session terminal.
  - Gateway lokal OpenAI-compatible (`/v1`) aktif saat aigate jalan.
  - Terminal xterm multi-tab terintegrasi dengan floating control & scroll/swipe natural.
  - Launcher CLI tool dengan auto-install, picker model/provider, auto-injection env.

---

## 2. Spesifikasi Fitur Inti

---

### 2.1 Providers Management

**Deskripsi fungsional**
Fitur pengelolaan AI Provider: menambah, mengedit, melihat daftar, dan menghapus provider AI (OpenAI, Anthropic, OpenRouter, Ollama, LiteLLM, dsb.). Kredensial disimpan aman (masked + terenkripsi di storage). Daftar model diambil otomatis via endpoint `/models` bila provider mendukung.

**Input**
- `name` (string) — nama provider.
- `type` (enum) — kategori provider (openai-compatible, anthropic, ollama, dll.).
- `base_url` (string) — URL dasar API.
- `api_key` (secret string, masked) — kunci autentikasi.
- `custom_headers[]` (key-value pairs) — header tambahan.
- `enabled` (boolean) — status aktif.

**Output**
- Daftar provider (tabel/read-only view).
- Detail provider (kredensial masked).
- Daftar model ter-discover (`model_id`, `model_name`).
- Konfirmasi CRUD (sukses/gagal + error).

**Process flow**
1. User buka panel Providers → klik "Tambah".
2. Isi form (name, type, base_url, api_key, headers) → Simpan.
3. Sistem validasi field → simpan ke tabel `Provider` (api_key terenkripsi).
4. Sistem panggil `GET {base_url}/models` (bila provider mendukung discovery).
5. Hasil discovery disimpan ke `ProviderModel` / ditampilkan; bila gagal, user input manual.
6. Edit/Hapus: konfirmasi hapus → cascade hapus relasi (ComboMember, EndpointBinding).

**Traceability**
- US-2.1.1 (CRUD Provider) — M
- US-2.1.2 (Credential Storage Aman) — M
- US-2.1.3 (Model Auto-Discovery) — S

---

### 2.2 Proxy Pools

**Deskripsi fungsional**
Mengelola kumpulan proxy (HTTP/HTTPS/SOCKS5) untuk merutekan traffic ke provider, dengan strategi rotasi (Round Robin / Random / Failover) dan health check latensi/uptime berkala di background.

**Input**
- `ProxyPool`: `name`, `rotation_strategy` (enum: round_robin | random | failover), `enabled`.
- `ProxyNode`: `host`, `port`, `protocol` (http | https | socks5), `username?`, `password?`, `pool_id` (FK).

**Output**
- Daftar pool & node dengan status (`healthy` / `dead` / `unknown`).
- Metrik latensi terakhir & uptime %.
- Pilihan pool aktif untuk routing keluar.

**Process flow**
1. User buka panel Proxy Pools → Tambah pool (pilih strategi rotasi).
2. Tambah node (host:port, protokol, kredensial opsional) → validasi format address.
3. Sistem jalankan health check background: ping/connect ke node, ukur latensi.
4. Status node diperbarui (healthy/dead); node dead dilewati rotasi.
5. Saat request keluar (Provider/Combo), engine pilih node per strategi rotasi pada pool terikat.

**Traceability**
- US-2.2.1 (Proxy Configuration Multi-Protokol) — M
- US-2.2.2 (Rotation Strategy) — S
- US-2.2.3 (Health Check) — S

---

### 2.3 Combos (Smart Routing & Fallback)

**Deskripsi fungsional**
Menggabungkan beberapa provider/model menjadi satu tujuan logis ("Combo") dengan strategi routing: Fallback (alihkan bila A error/429), Load Balancing (berbobot), atau Lowest Latency / Cost Optimization.

**Input**
- `Combo`: `name`, `strategy` (enum: fallback | load_balance | latency_cost), `enabled`.
- `ComboMember`: `combo_id` (FK), `provider_id` (FK) atau `provider_model` (string), `priority` (int), `weight` (float, untuk load_balance).

**Output**
- Daftar combo & anggotanya (urutan prioritas / bobot).
- Pemilihan anggota saat request masuk via endpoint terikat.

**Process flow (routing)**
1. Request masuk ke endpoint terikat Combo.
2. Engine pilih anggota berdasar strategi:
   - *Fallback*: coba prioritas 1 → bila 5xx/429, lanjut prioritas 2, dst.
   - *Load Balance*: pilih anggota berbobot (weight-normalized random).
   - *Latency/Cost*: pilih anggota dengan latensi/estimasi biaya terendah (data dari health check / metadata model).
3. Bila semua anggota gagal → kembalikan error gateway ke client.

**Traceability**
- US-2.3.1 (Custom Pipeline) — M
- US-2.3.2 (Fallback Strategy) — M
- US-2.3.3 (Load Balancing & Cost/Latency Optimization) — S

---

### 2.4 Endpoints (OpenAI-Compatible Gateway)

**Deskripsi fungsional**
Menyediakan server HTTP lokal (`http://localhost:8080/v1`) kompatibel OpenAI (`/v1/chat/completions`, `/v1/models`). Setiap endpoint di-bind ke satu Provider atau satu Combo. Akses dapat diamankan dengan API key internal opsional.

**Input**
- `Endpoint`: `name`, `listen_host`, `listen_port`, `bind_type` (provider | combo), `bind_id` (FK), `access_control_enabled` (bool), `internal_api_key?` (secret).
- `EndpointBinding`: relasi endpoint → provider_id / combo_id.

**Output**
- Server gateway aktif saat aigate jalan.
- Respons OpenAI-format (`/v1/chat/completions`, `/v1/models`).
- Penolakan 401 bila access control aktif & key tidak valid.

**Process flow**
1. aigate start → start gateway server di `listen_host:listen_port`.
2. Request masuk ke `/v1/chat/completions`.
3. Bila `access_control_enabled`: validasi `Authorization`/`x-api-key` vs `internal_api_key` → tolak bila gagal.
4. Resolusi binding: bila `bind_type=provider` → route langsung; bila `combo` → jalankan strategi Combo (§2.3).
5. Teruskan ke provider target (lewat Proxy Pool bila terikat) → kembalikan respons OpenAI-format.
6. `/v1/models` mengembalikan daftar model dari provider/combo terikat.

**Traceability**
- US-2.4.1 (OpenAI-Compatible Gateway) — M
- US-2.4.2 (Endpoint Binding) — M
- US-2.4.3 (Access Control) — S

---

### 2.5 Integrated Multi-Tab Terminal (xterm)

**Deskripsi fungsional**
Terminal web/UI berbasis `xterm.js` multi-tab, terhubung via WebSocket ke PTY Python backend. Mendukung deteksi shell (Bash/Zsh/PowerShell/CMD). Menyediakan floating control (fullscreen, paste+return focus).

#### 2.5.0 Floating Control — umum
Ikon mengambang di area terminal memberikan akses cepat tanpa menu.

**Input (floating):**
- Klik ikon fullscreen; klik ikon paste + isi clipboard OS.

**Output:**
- Toggle ukuran terminal (normal ↔ fullscreen).
- Injeksi clipboard ke PTY aktif + fokus input kembali ke terminal aktif.

#### 2.5.1 Scroll & Swipe (Trackpad / Mouse)

**Deskripsi**
Scroll vertikal (dan horizontal bila tersedia) via roda mouse/trackpad. Gesture *swipe* diubah menjadi scroll buffer (bukan navigasi/escape TUI). Kecepatan swipe menentukan kecepatan scroll (velocity-based) dengan easing & damping di ujung buffer. Aplikasi TUI yang butuh swipe khusus dapat dikecualikan per-aplikasi.

**Input**
- Event roda mouse (delta vertikal/horizontal).
- Event swipe (gesture trackpad/touch) → diterjemahi jadi velocity vector.

**Output**
- Scroll buffer terminal (baris atau lompat layar).
- Efek easing/damping halus di ujung buffer.

**Process flow (swipe → scroll)**
1. Capture gesture swipe → hitung velocity (px/ms).
2. Map velocity → kecepatan scroll (cepat = lompat layar, lambat = halus baris-per-baris).
3. Terapkan easing curve + damping saat mendekati ujung buffer.
4. Render scroll pada buffer xterm; jangan emit escape/navigasi TUI.
5. Pengecualian: bila tab menjalankan aplikasi TUI terdaftar butuh swipe khusus → bypass map.

**Traceability**
- US-2.5.1 (Web/UI Terminal Multi-Tab) — M
- US-2.5.2 (Floating: Toggle Fullscreen) — M
- US-2.5.3 (Floating: Paste + Auto Return Focus) — M
- US-2.5.4 (Scroll Mouse & Trackpad) — S
- US-2.5.5 (Swipe → Scroll) — M
- US-2.5.6 (Velocity-based Scroll & Damping) — S

---

### 2.6 CLI Tools Auto-Launcher & Auto-Configuration

**Deskripsi fungsional**
Launcher tool CLI populer: cek ketersediaan binary (`which`/`where`); bila tiada, install otomatis (`pip`/`uv`) di tab terminal; bila ada, tampilkan modal picker Provider/Combo & Model aktif; lalu suntikkan env (`OPENAI_API_BASE`, `OPENAI_API_KEY`) dan jalankan tool.

**Input**
- Pilihan tool dari UI (referensi `CLITool` + `CLIToolGroup`).
- Pilihan dari picker: `provider_id` / `combo_id` + `model_id`.
- Config instalasi (pip/uv, argumen flag opsional).

**Output**
- Tab terminal baru berisi: instalasi (bila perlu) / command tool dengan env ter-injeksi.
- Tool berjalan terhadap gateway lokal aigate.

**Process flow**
1. User klik tool CLI dari grup (A/B/C).
2. Backend cek binary via `which`/`where`.
3. Bila **tiada** → buka tab terminal → jalankan `pip install`/`uv` tool.
4. Bila **ada** → tampilkan modal picker Provider/Combo & Model (hanya yg aktif).
5. Buka tab terminal baru → set `OPENAI_API_BASE="http://localhost:8080/v1"`, `OPENAI_API_KEY="<internal>"`.
6. Jalankan command tool dengan model terpilih.

**Traceability**
- US-2.6.1 (CLI Tool Presets & Auto-Install) — M
- US-2.6.2 (Interactive Model & Provider Picker) — M
- US-2.6.3 (Auto-Injection Envs/Flags) — M

#### 2.6.1 Pengelompokan Tool CLI (Grouping)

**Deskripsi**
Tool CLI dikelompokkan minimal 3 grup (A/B/C), masing-masing ≥5 preset; Grup A (agentic coding) diutamakan. Dapat diperluas via YAML/JSON (Roadmap §6).

| Grup | Nama | Preset (≥5) |
| :--- | :--- | :--- |
| A | Agentic Coding Assistants | `claude`, `opencode`, `codex`, `gemini`, `antigravity`, `phi`, `aider`, `goose`, `amp`, `qwen`, `cline`, `kilo` |
| B | Autonomous Software Agents | `openhands`, `swe-agent`, `open-interpreter`, `autogpt`, `gpt-researcher`, `crewai` |
| C | Chat & Shell Assistants | `llm`, `sgpt`, `mods`, `oterm`, `gptme`, `aichat` |

**Input:** definisi grup & preset (default + YAML/JSON override).
**Output:** UI terbagi per grup, Grup A ditonjolkan.

**Traceability**
- US-2.6.4 (Grouping Tool CLI Grup A/B/C) — M

---

## 3. Cross-Feature Data Flows

```
[Provider] ──< belong to >── [ComboMember] ──< compose >── [Combo]
[ProxyPool] ──< contains >── [ProxyNode]  (health check → status)
[Combo]    ──< bound to >── [EndpointBinding] ──< serves >── [Endpoint/Gateway /v1]
[Provider] ──< directly bound >── [EndpointBinding]
[Endpoint /v1] ──< consumed by >── [CLITool] (via env injection)
[CLIToolGroup] ──< contains >── [CLITool] ──< launched in >── [TerminalTab]
[TerminalSession] ──< owns >── [TerminalTab]
```

Routing keluar: `Endpoint → (Combo → ComboMember → Provider) | Provider` → lewat `ProxyPool` (bila terikat) → provider eksternal.

---

## 4. Non-Functional Alignment (dari PRD §5)
- **Multiplatform:** config SQLite portabel antar OS.
- **Low footprint:** health check & gateway background ringan.
- **Native Python run:** aigate dijalankan langsung sebagai aplikasi Python (tanpa deployment/container, tanpa packaging); semua entitas di storage lokal, zero external runtime.

---

## 5. Traceability Matrix (Ringkasan)

| Fitur | User Story BRD | Prioritas |
| :--- | :--- | :--- |
| 2.1 Providers | US-2.1.1, US-2.1.2, US-2.1.3 | M,M,S |
| 2.2 Proxy Pools | US-2.2.1, US-2.2.2, US-2.2.3 | M,S,S |
| 2.3 Combos | US-2.3.1, US-2.3.2, US-2.3.3 | M,M,S |
| 2.4 Endpoints | US-2.4.1, US-2.4.2, US-2.4.3 | M,M,S |
| 2.5 Terminal | US-2.5.1 s/d US-2.5.6 | M×4, S×2 |
| 2.6 Launcher | US-2.6.1, US-2.6.2, US-2.6.3, US-2.6.4 | M×4 |

---

*Dokumen ini ditulis di bawah scope `docs/analysis/` sesuai aturan specialist System Analyst.*
