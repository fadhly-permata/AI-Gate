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
Fitur pengelolaan AI Provider: menambah, mengedit, melihat daftar, dan menghapus provider AI (OpenAI, Anthropic, OpenRouter, Ollama, LiteLLM, dsb.). Kredensial disimpan plaintext di DB tanpa enkripsi dan tanpa masking UI (ADR-007). Daftar model diambil otomatis via endpoint `/models` bila provider mendukung. Satu provider dapat punya beberapa akun (multi-akun) dengan kredensial sendiri; penyedia resmi mendukung login OAuth dengan token diperbarui otomatis (lihat `ProviderAccount` di ERD).

**Input**
- `name` (string) — nama provider.
- `type` (enum) — kategori provider (openai-compatible, anthropic, ollama, dll.).
- `base_url` (string) — URL dasar API.
- `api_key` (secret string, plaintext per ADR-007) — kunci autentikasi.
- `custom_headers[]` (key-value pairs) — header tambahan.
- `enabled` (boolean) — status aktif.

**Output**
- Daftar provider (tabel/read-only view).
- Detail provider (kredensial plaintext per ADR-007, tidak di-redaksi UI).
- Daftar model ter-discover (`model_id`, `model_name`).
- Konfirmasi CRUD (sukses/gagal + error).

**Process flow**
1. User buka panel Providers → klik "Tambah".
2. Isi form (name, type, base_url, api_key, headers) → Simpan.
3. Sistem validasi field → simpan ke tabel `Provider` (api_key plaintext per ADR-007, tanpa enkripsi).
4. Sistem panggil `GET {base_url}/models` (bila provider mendukung discovery).
5. Hasil discovery disimpan ke `ProviderModel` / ditampilkan; bila gagal, user input manual.
6. Edit/Hapus: konfirmasi hapus → cascade hapus relasi (ComboMember, EndpointBinding).
7. **Multi-Akun:** user dapat menambah `ProviderAccount` (label, auth_type, api_key atau oauth token) ke provider yang sama; routing memilih akun (round-robin) atau pakai sebagai cadangan.
8. **OAuth:** bila `auth_type=oauth`, klik Connect memicu flow OAuth; token + `refresh_token` + `expires_at` disimpan. Sebelum request, sistem otomatis refresh bila hampir kedaluwarsa (tanpa login ulang).

**Traceability**
- US-2.1.1 (CRUD Provider) — M
- US-2.1.2 (Credential Storage Aman) — M
- US-2.1.3 (Model Auto-Discovery) — S
- US-2.1.4 (Multi-Akun per Provider) — M
- US-2.1.5 (OAuth + Token Refresh) — M

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
Menggabungkan beberapa provider/model menjadi satu tujuan logis ("Combo") dengan strategi routing: **3-Tier Fallback** (langganan → murah → gratis, otomatis pindah bila kuota habis/error), **Cadangan Antar-Akun** (akun lain di provider sama bila satu kena limit), **Load Balancing** (berbobot), atau **Lowest Latency / Cost Optimization** — dengan **routing sadar kuota** (mempertimbangkan sisa kuota tiap provider).

**Input**
- `Combo`: `name`, `strategy` (enum: three_tier | fallback | load_balance | latency_cost), `enabled`.
- `ComboMember`: `combo_id` (FK), `provider_id` (FK) atau `provider_model` (string), `priority` (int), `weight` (float, untuk load_balance).

**Output**
- Daftar combo & anggotanya (urutan prioritas / bobot).
- Pemilihan anggota saat request masuk via endpoint terikat.

**Process flow (routing)**
1. Request masuk ke endpoint terikat Combo.
2. Engine pilih anggota berdasar strategi:
    - *3-Tier*: urut langganan → murah → gratis; bila tier atas habis/error → lanjut tier bawah otomatis (coding tak berhenti).
    - *Fallback*: coba prioritas 1 → bila 5xx/429, lanjut prioritas 2, dst.
    - *Load Balance*: pilih anggota berbobot (weight-normalized random).
    - *Latency/Cost*: pilih anggota dengan latensi/estimasi biaya terendah.
    - *Cadangan Antar-Akun*: bila anggota punya beberapa `ProviderAccount`, dan akun aktif kena limit → pakai akun lain di provider sama.
3. **Sadar Kuota:** sebelum pilih anggota, engine cek sisa kuota (`UsageRecord`/quota tracker); preferensi ke langganan yang masih punya kuota.
4. Bila semua anggota & akun gagal → kembalikan error gateway ke client.

**Traceability**
- US-2.3.1 (Custom Pipeline) — M
- US-2.3.2 (Fallback Strategy) — M
- US-2.3.3 (Load Balancing & Cost/Latency Optimization) — S
- US-2.3.4 (3-Tier Fallback) — M
- US-2.3.5 (Multi-Akun + Sadar Kuota) — M

---

### 2.4 Endpoints (OpenAI-Compatible Gateway)

**Deskripsi fungsional**
Menyediakan server HTTP lokal (`http://localhost:8080/v1`) kompatibel OpenAI (`/v1/chat/completions`, `/v1/models`). Setiap endpoint di-bind ke satu Provider atau satu Combo. Akses dapat diamankan dengan API key internal opsional. Endpoint juga menjalankan **penerjemah format** otomatis (OpenAI↔Claude↔Gemini↔Cursor↔Kiro↔Vertex↔Antigravity↔Ollama) sehingga alat CLI apa pun bisa dipakai dengan provider mana pun (transparan).

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
- US-2.4.4 (Format Translation) — M

#### 2.4.1 Penghemat Token (Token Savers) *(adopsi 9router)*
**Deskripsi:** hook pra-terjemah/pra-kirim yang mengurangi token. RTK memadatkan hasil alat (`git diff`, `grep`, `ls`, `tree`) sebelum ke LLM (hemat 20–40% input); mode Caveman menyuntikkan gaya jawaban singkat (hemat hingga 65% output); Ponytail menyuntikkan instruksi "tulis kode minimal". Semua toggle per-endpoint, fail-open (bila gagal → teks asli).
**Input:** `Endpoint.token_saver` (enum: off | rtk | caveman | ponytail).
**Output:** request/response lebih kecil; metrik penghematan di Usage Analytics.
**Traceability:** US-2.4.5.

#### 2.4.2 Pelacak Kuota & Pemakaian *(adopsi 9router)*
**Deskripsi:** pelacakan kuota real-time per provider berlangganan (sisa token + hitung mundur reset), estimasi biaya, dan optimasi pemakaian langganan sebelum reset. Dipakai Combo untuk routing sadar kuota.
**Input/Output:** `UsageRecord` (provider_id, account_id?, tokens_in, tokens_out, cost_est, ts); `GET /api/usage`, `GET /api/quota`.
**Traceability:** US-2.4.6.

#### 2.4.3 Log Permintaan (Debug) + Usage Analytics *(adopsi 9router)*
**Deskripsi:** mode debug mencatat tiap permintaan & jawaban (header/isi, opsional); laporan pemakaian token & tren per provider/model. Terpisah dari wajib-logging DB (§2.8 / ADR-011).
**Input/Output:** `RequestLog` (ts, endpoint, model, durasi, tokens); dashboard analitik.
**Traceability:** US-2.4.7.

#### 2.4.4 Export / Import Setting Lokal *(request user — pengganti cloud sync)*
**Deskripsi:** export seluruh setting (provider, akun, combo, proxy, endpoint, preferensi) ke satu file JSON; import di device lain memulihkan setting. Lokal sepenuhnya, tanpa cloud.
**Input/Output:** `GET /api/settings/export` → JSON; `POST /api/settings/import` (body JSON).
**Traceability:** US-2.4.8.

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
Scroll vertikal (dan horizontal bila tersedia) via roda mouse/trackpad. Gesture *swipe* diperlakukan sama dengan roda mouse (event `wheel` sintetis), sehingga buffer terminal di-scroll 1:1 dengan jari dan aplikasi full-screen (TUI, alt-buffer) tetap bisa di-scroll lewat input scroll-nya sendiri. Drag 1:1 + momentum saat lepas jari (velocity-based) dengan damping di ujung buffer. Aplikasi yang butuh gesture mentah dapat dikecualikan per-tab (passthrough).

**Input**
- Event roda mouse (delta vertikal/horizontal).
- Event swipe (gesture trackpad/touch) → delta px (1:1) + velocity vector (px/ms) untuk momentum.

**Output**
- Scroll buffer terminal (baris atau lompat layar) pada buffer normal.
- Input scroll aplikasi (Up/Down cursor key / mouse-wheel report) pada alt-buffer.
- Efek easing/damping halus di ujung buffer + momentum pasca-lepas jari.

**Process flow (swipe → scroll)**
1. Capture gesture swipe → hitung delta (px) + velocity (px/ms) untuk pelepasan.
2. Ubah delta swipe menjadi event `wheel` sintetis pada elemen terminal (swipe
   diperlakukan sama dengan roda mouse).
3. Buffer normal: xterm scroll viewport 1:1 dengan jari (pixel delta), easing/
   damping otomatis saat mendekati ujung buffer.
4. Buffer alternate (TUI, tanpa scrollback): xterm menerjemahkan wheel menjadi
   input scroll aplikasi — Up/Down cursor key, atau mouse-wheel report bila
   aplikasi meminta mouse tracking. (Catatan: `scrollLines()` tidak berpengaruh
   di alt-buffer, jadi swipe di TUI harus lewat jalur ini.)
5. Setelah jari dilepas: jalankan momentum (loop rAF + friction) sampai velocity
   habis atau posisi buffer mentok ujung.
6. Pengecualian: tab dengan *passthrough* aktif (`tui_mode`, atau aplikasi
   terdaftar di registry) tidak di-hijack → gesture mentah sampai ke aplikasi.

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

### 2.7 Antarmuka Web / Admin Console UI

**Deskripsi fungsional**
Konsol manajemen (Providers, Combos, Proxy Pools, Endpoints, CLI Tools) dan Terminal disajikan dalam UI web lokal bergaya AdminLTE: sidebar kiri dapat di-collapse (saat collapse hanya menampilkan ikon), tombol pengalih tema gelap/terang, dan pengalih bahasa (EN/ID). Semua preferensi UI (collapse, tema, bahasa) disimpan di sisi klien (localStorage) — tidak mengubah data model (lihat ERD; tidak ada entitas baru).

**Input**
- Aksi toggle sidebar (expand/collapse).
- Aksi pilih tema (`dark` / `light`).
- Aksi pilih bahasa (`en` / `id`).

**Output**
- Layout sidebar berubah (label tersembunyi saat collapsed, ikon tetap tampil).
- Seluruh UI (termasuk Terminal pane) mengikuti tema via CSS variables.
- Seluruh string UI (menu, label, tombol) berganti ke bahasa terpilih via kamus i18n klien.
- Preferensi tersimpan di localStorage dan dipulihkan saat reload.

**Process flow (UI shell)**
1. Saat load: baca `localStorage` (theme, locale, sidebar state) → terapkan ke `<html>` (atribut `data-theme`, `data-locale`, class `sidebar-collapsed`).
2. Klik toggle sidebar → JS tambah/hapus class `sidebar-collapsed` → CSS sembunyikan teks, tampilkan ikon → simpan state ke localStorage.
3. Klik pengalih tema → set `data-theme` + simpan localStorage.
4. Klik pengalih bahasa → muat kamus `i18n[locale]` → ganti node ber-`data-i18n` → simpan localStorage.
5. Tema & i18n bersifat global (mencakup Terminal pane); tidak ada round-trip ke backend.

**Catatan implementasi (TSD §3.4):** Tanpa framework/build (ADR-001) — layout & gaya ditulis vanilla CSS meniru AdminLTE; ikon via Font Awesome CDN (atau SVG inline); tema via CSS custom properties.

**Traceability**
- US-2.7.1 (Collapsible Sidebar) — M
- US-2.7.2 (Dark/Light Theme Switcher) — M
- US-2.7.3 (Multi-Bahasa EN/ID) — M

---

### 2.8 Mode Developer, Logging & Self-Heal

**Deskripsi fungsional**
Mode developer (flag run / env `AIGATE_DEV=1`) menambah: (a) run di custom port;
(b) UI responsif + simulasi perangkat (phone/tablet/desktop; phone TIDAK pakai
AdminLTE); (c) Log Window membaca `LogEntry` dari DB; (d) aturan logging wajib
(semua method log severity; warning/error + stacktrace; simpan ke DB; no empty
catch); (e) Self-Heal dari menu CLI-Tool (git branch + agentic CLI + fix/test loop);
(f) seluruh konfigurasi di DB (`Setting` table), bukan file.

**Input**
- Arg/env `--port`, env `AIGATE_DEV=1`.
- Aksi UI: toggle simulasi perangkat, buka Log Window, klik Self-Heal.
- Log dihasilkan otomatis tiap method (info/warning/error + stacktrace).

**Output**
- Server listen di port pilihan; mode developer mengaktifkan panel UI ekstra.
- Log Window menampilkan `LogEntry` (filter severity) dari DB, auto-refresh.
- Self-Heal: branch git baru, agentic CLI jalan di tab terminal, loop sampai log
  warning/error habis (atau batas iterasi); bila tak ada agentic CLI → popup.

**Process flow — Logging (wajib)**
1. Tiap method panggil logger dengan level (info/warning/error).
2. warning/error: sertakan `stacktrace` (traceback / inner exception).
3. Handler logger tulis baris ke tabel `LogEntry` (timestamp, severity, source,
   message, stacktrace). Frontend: log client di-forward ke backend lalu disimpan DB.
4. Tidak ada try/catch kosong; semua exception ditangani & di-log.

**Process flow — Self-Heal**
1. Klik Self-Heal di menu CLI-Tool → cek agentic CLI terinstall (Grup A, `which`).
2. Bila tidak ada → popup "Self-Heal tidak bisa jalan: tidak ada agentic CLI
   terinstall"; STOP.
3. Bila ada → pastikan git repo (`git init` bila belum), buat branch
   `aigate/self-heal-<ts>`.
4. Ambil `LogEntry` severity warning & error (ORDER BY timestamp).
5. Buka tab terminal, jalankan agentic CLI dengan prompt perbaiki issue berdasar
   log. Agent menjalankan fix & test.
6. Loop: setelah test, cek ulang log warning/error; bila masih ada → ulangi (5);
   bila kosong → "sembuh" (optional commit). Batas iterasi (mis. 10) cegah hang.
6b. Setelah satu issue spesifik (warning/error tertentu) berhasil di-fix & test
    hijau, **hapus baris `LogEntry` terkait** agar tidak di-fix ulang.
7. Setelah **seluruh issue terbukti pass** (test hijau), helper `selfheal` lakukan
   `git merge` branch `aigate/self-heal-*` ke `main`, `git checkout main`, lalu
   **hapus branch fixing**. Run berikutnya memakai versi aigate terbaru (latest).

**Process flow — Config di DB**
1. Semua setting (port default, mode, toggle fitur, preset CLI) di tabel `Setting`
   (key-value). Tidak ada file config terpisah sebagai sumber kebenaran.
2. Baca/tulis via repository; seed bila tabel kosong.

**Catatan (TSD §3.5):** Aturan logging + no-empty-catch = code-review gate (ADR-011).
Secret tetap plaintext di DB (ADR-007).

**Traceability**
- US-2.8.1 (Custom Port & Dev Mode) — M
- US-2.8.2 (Responsif + Simulasi Perangkat) — M
- US-2.8.3 (Log Window) — M
- US-2.8.4 (Mandatory Logging) — M
- US-2.8.5 (Self-Heal) — M
- US-2.8.6 (Konfigurasi di DB) — M

---

### 2.9 Chat Playground *(fitur tambahan aigate — PRD §2.9)*

**Deskripsi fungsional**
Halaman percakapan AI di web console ala Gemini/ChatGPT, memakai provider/combo
yang sudah dikonfigurasi aigate. User memilih tujuan (Provider+Model atau Combo),
mengirim pesan, dan menerima jawaban **streaming**. Riwayat tersimpan di DB
(`ChatSession`, `ChatMessage`) sehingga multi-sesi + bertahan reload.

**Input**
- `ChatSession`: `title`, `provider_id?`/`combo_id?`, `model`, `system_prompt?`, `temperature?`.
- Pesan user (string) + riwayat sesi.

**Output**
- Daftar sesi; thread pesan (role user/assistant/system); jawaban model (streaming SSE).

**Process flow**
1. User buka Chat → buat/pilih sesi → pilih provider+model atau combo (combobox auto-fetch/search).
2. User kirim pesan → server simpan `ChatMessage(role=user)` → rakit `messages` (system + riwayat + pesan baru).
3. Server teruskan ke gateway `/v1/chat/completions` (stream) ke provider/combo terpilih (format translator + token saver + kuota tetap berlaku).
4. Delta streaming dikirim ke UI (SSE) dan dirender bertahap; saat selesai, `ChatMessage(role=assistant)` disimpan (+ tokens).
5. User bisa ganti judul / hapus sesi / mulai sesi baru; semua tersimpan di DB.

**Traceability**
- US-2.9.1 (Percakapan streaming) — M
- US-2.9.2 (Multi-sesi + riwayat di DB) — M
- US-2.9.3 (Pilih provider/model/combo) — M
- US-2.9.4 (System prompt & parameter) — S

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

Entitas tambahan (adopsi 9router): `ProviderAccount` (banyak akun per Provider; OAuth + refresh token), `UsageRecord` (token in/out + estimasi biaya per request), `RequestLog` (debug log permintaan). Alur: `Provider --< has >-- ProviderAccount`; `ProviderAccount --< dipakai oleh >-- ComboMember`; `Endpoint --< menghasilkan >-- UsageRecord/RequestLog`.

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
| 2.4 Endpoints | US-2.4.1, US-2.4.2, US-2.4.3, US-2.4.4, US-2.4.5, US-2.4.6, US-2.4.7, US-2.4.8 | M,M,S,M,S,S,S,S |
| 2.5 Terminal | US-2.5.1 s/d US-2.5.6 | M×4, S×2 |
| 2.6 Launcher | US-2.6.1, US-2.6.2, US-2.6.3, US-2.6.4 | M×4 |
| 2.7 Admin Console UI | US-2.7.1, US-2.7.2, US-2.7.3 | M×3 |
| 2.8 Dev Mode, Logging & Self-Heal | US-2.8.1 s/d US-2.8.6 | M×6 |

---

*Dokumen ini ditulis di bawah scope `docs/analysis/` sesuai aturan specialist System Analyst.*
