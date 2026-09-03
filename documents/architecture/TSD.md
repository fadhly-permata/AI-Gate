# Technical Specification Document (TSD): aigate

**Versi:** 1.0
**Tanggal:** 2026-09-03
**Penulis:** Tech Architect (stand-in)
**Sumber rujukan:** `documents/PRD.md` (PRD aigate), `docs/business/BRD.md` (BRD), `docs/analysis/FSD.md` (FSD), `docs/analysis/ERD.md` (ERD), `pm/memory-bank.md`, `pm/status.md`
**Lingkup tulis:** `docs/architecture/` (per aturan specialist Tech Architect).

---

## 0. Pendahuluan

Dokumen ini memuat spesifikasi teknis *target-state* produk **aigate** — AI Proxy Gateway & Management Tool desktop berbasis Python. TSD mendefinisikan batas modul, kontrak internal (contract-first), keputusan tech stack beserta *trade-off*, arsitektur terminal mendalam, desain gateway, ADR, keamanan, dan catatan desain evolusioner.

TSD konsisten dengan PRD §2–§6, BRD (semua user story), FSD (alur fitur), dan ERD (model penyimpanan SQLite). TSD **hanya mendesain**, tidak memuat implementasi kode.

---

## 1. Batas Modul & Kontrak Internal (Layered, Contract-First)

Arsitektur dibagi menjadi 7 modul berlapis. Komunikasi antar modul mengikuti kontrak (antarmuka) eksplisit; dependensi mengalir satu arah ke bawah (UI → Core → Infra), kecuali kontrak balik (callback/event) yang didefinisikan eksplisit.

```
┌──────────────────────────────────────────────────────────────────────┐
│  UI Layer (Web UI: FastAPI static + xterm.js + SPA JS)                │
│   - Panel Providers/Combos/Proxy/Endpoints/CLI Tools                  │
│   - Terminal Pane (xterm.js multi-tab + floating control)             │
└───────────────┬───────────────────────────────────┬──────────────────┘
                │ HTTP/REST (manajemen)             │ WS /pty (terminal)
                ▼                                    ▼
┌──────────────────────────┐          ┌──────────────────────────────────┐
│ Gateway Server            │          │ Terminal/PTY Service             │
│ (FastAPI + Uvicorn)       │          │ (WebSocket bridge → ptyprocess)  │
│  - /v1 OpenAI-compatible  │          └───────────────┬──────────────────┘
└───────────────┬────────────┘                          │ spawn/attach
                │ (resolve binding)                     ▼
┌───────────────┴──────────────┐            ┌────────────────────────────┐
│ Proxy & Routing Engine        │◄──bind────│ Local Shell / CLI Tools     │
│  - Combo engine               │           │ (binary exec via PTY)       │
│  - Provider adapter           │           └────────────────────────────┘
│  - Proxy rotation/health      │
└───────────────┬──────────────┘
                │ upstream HTTP (httpx, lewat proxy)
                ▼
        ┌───────────────────┐
        │ External AI       │
        │ Providers (OpenAI,│
        │ Anthropic, dst)   │
        └───────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ CLI Tool Manager & Auto-Injector (modul lintas-ui)                     │
│  - consume Gateway (env injection) + Terminal/PTY Service (eksekusi)   │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ Config Engine (SQLAlchemy + SQLite) — dibaca oleh semua modul di atas │
└──────────────────────────────────────────────────────────────────────┘
```

### 1.1 Tabel Modul & Kontrak (Who-Calls-Whom)

| # | Modul | Pemanggil utama | Dipanggil | Kontrak (antarmuka) |
| :-- | :-- | :-- | :-- | :-- |
| 1 | **UI Layer** | User | Gateway Server (REST/WS), Terminal/PTY Service (WS) | REST JSON API; WebSocket PTY frame protocol (§3.2) |
| 2 | **Gateway Server** | UI, CLI Tools (via env), external clients | Proxy & Routing Engine | `resolve_endpoint(req) → upstream_target`; `forward(req) → response` |
| 3 | **Proxy & Routing Engine** | Gateway Server | Provider Adapter, Proxy Pool | `route(req, binding) → provider_call`; `select_proxy(pool) → node` |
| 4 | **Combo Engine** | Proxy & Routing Engine | Provider Adapter | `select_member(strategy, combo) → member` (fallback/load_balance/latency_cost) |
| 5 | **Provider Adapter** | Proxy & Routing Engine, Combo Engine | External Provider (HTTP via httpx) | `chat_completion(req) → resp` (OpenAI-format); `list_models() → models` |
| 6 | **CLI Tool Manager & Auto-Injector** | UI | Gateway Server, Terminal/PTY Service, Config Engine | `launch(tool, picker) → spawn_tab`; `inject_env(tab, endpoint)` |
| 7 | **Terminal/PTY Service** | UI (WS), CLI Tool Manager | OS PTY (ptyprocess/pywinpty) | `open_tab(shell) → tab_id`; `write(tab, data)`; `resize(tab, rows, cols)` |

**Aturan kontrak:**
- Setiap modul mengekspos kontrak melalui objek/router terpisah (mis. `GatewayAPI`, `RoutingEngine`, `PTYService`). Tidak ada panggilan langsung ke variabel global lintas modul.
- Modul 2–5 berjalan di proses Python yang sama (Core). Modul 1 (UI) dapat disajikan oleh server FastAPI yang sama (lihat ADR-001).
- Config Engine dipakai *read/write* oleh semua modul melalui repository layer (SQLAlchemy session per request/thread), bukan akses DB langsung.

---

## 2. Keputusan Tech Stack & Trade-off

| Komponen | Pilihan direkomendasikan | Alternatif ditolak / ditunda | Rasional |
| :-- | :-- | :-- | :-- |
| Bahasa | Python 3.10+ | — | Konsisten PRD §3 |
| GUI Framework | **Web UI lokal**: FastAPI (statik + SPA JS) + `xterm.js` | CustomTkinter / PyQt6 / PySide6 (native) | xterm.js butuh *canvas* browser; native toolkit butuh *webview bridge* (CEF/QtWebEngine) yang menambah kompleksitas packaging. Web UI menyatukan satu server HTTP/WS (FastAPI) untuk UI + Gateway + PTY. Lihat ADR-001. |
| Gateway | FastAPI + Uvicorn + httpx (async) | Flask/Tornado | Async streaming (SSE) esensial untuk token streaming OpenAI; httpx mendukung proxy SOCKS5 + async. |
| Terminal PTY | `ptyprocess` (Unix), `pywinpty` (Windows) + `xterm.js` via WebSocket | `pexpect` (terlalu high-level), `pyte` (only emulator, no real PTY) | ptyprocess/pywinpty memberi PTY nyata (shell asli); xterm.js render sisi klien. |
| Config Engine | SQLAlchemy (ORM) + SQLite | peewee, JSON/YAML murni | ERD eksplisit butuh relasi & migrasi; SQLite portabel antar-OS (NFR). SQLAlchemy memberi repository layer bersih. |


### ADR-001 — Pemilihan GUI Framework: Web UI lokal (FastAPI + xterm.js)
- **Status:** Accepted (recommended default).
- **Konteks:** PRD §3 memberi dua opsi: native toolkit (CustomTkinter/PyQt6) atau web UI (FastAPI+NiceGUI/Flet/Streamlit). Terminal butuh xterm.js (browser-based).
- **Keputusan:** Gunakan **Web UI yang disajikan oleh server FastAPI yang sama** dengan Gateway. Frontend berupa halaman statis (HTML/CSS/JS **vanilla** SPA — tanpa framework JS, tanpa build step/Node) plus `xterm.js` + `xterm-addon-fit` + `xterm-addon-web-links`. Komunikasi manajemen via REST, terminal via WebSocket pada path terpisah (`/ws/pty/{tab_id}`).
- **Trade-off:**
  - *Pro:* Satu server (FastAPI) untuk UI + Gateway + PTY → distribusi & penyatuan lebih mudah; xterm.js terintegrasi native tanpa webview; konsistensi kontrak WS/HTTP.
  - *Kontra:* Tampilan bukan "native OS chrome"; cukup membuka di browser lokal (atau WebView OS) ke `http://localhost:<port>`.
- **Catatan evolusi:** Jika nanti butuh look native, bisa diganti PyQt6 + QtWebEngine tanpa mengubah kontrak (UI Layer tetap berbicara REST/WS).

### ADR-002 — Gateway Stack
- **Status:** Accepted.
- FastAPI + Uvicorn (ASGI) + httpx async client. Streaming respons (`StreamingResponse`/SSE) untuk `/v1/chat/completions`. Lihat §4.
- **Catatan portabilitas (2026-09-03):** FastAPI di-pin `<0.100` + Pydantic `<2`
  (Pydantic v1, **pure Python, tanpa pydantic-core/Rust**) agar aigate jalan di
  Termux & platform yang tak punya wheel Rust. Semua dep inti (uvicorn, starlette,
  sqlalchemy, httpx, ptyprocess) juga pure Python → nol dependensi compile.

### ADR-003 — PTY Bridge Stack
- **Status:** Accepted.
- `ptyprocess` (POSIX), `pywinpty` (Windows); `xterm.js` di klien. Satu koneksi WebSocket per tab terminal. Lihat §3.

### ADR-004 — Config Engine
- **Status:** Accepted.
- SQLAlchemy 2.x (declarative) + SQLite file tunggal (`~/.aigate/aigate.db`). Skema sesuai ERD.md. Semua akses via repository layer.

### ADR-009 — Native Python Execution (tanpa deployment)
- **Status:** Accepted (resolved 2026-09-03 per user request).
- **Konteks:** User meminta aigate dapat berjalan **native tanpa perlu deployment**, menggunakan Python yang sudah terbukti cross-platform. Untuk frontend, user memberi kebebasan (baseline: Web UI lokal per ADR-001).
- **Keputusan:** aigate dijalankan langsung sebagai aplikasi Python (`python -m aigate` / `uvicorn aigate.server:app`) di Windows/macOS/Linux — tidak memerlukan container/Docker/deployment step, dan tanpa packaging single-binary. Frontend: implementasi bebas di tangan dev; ADR-001 (Web UI lokal FastAPI + xterm.js, **vanilla JS SPA tanpa framework/build**) tetap baseline kecuali diubah kelak.
- **Trade-off:** tiap user perlu Python + `pip install -e .` (install sekali). Keuntungan: dev & sinkronisasi lintas-OS jauh lebih sederhana, tidak ada beban container maupun packaging.

---

## 3. Deep-Dive Arsitektur Terminal

### 3.1 xterm.js ↔ WebSocket ↔ Python PTY Bridge

**Topologi:** Satu WebSocket per tab terminal: `ws://localhost:<port>/ws/pty/{tab_id}`. Backend `PTYService` memetakan `tab_id` → objek PTY (ptyprocess/pywinpty) yang menyimpan *file descriptor* master.

**Protokol frame (WebSocket):**
- *Binary frame* → stream I/O mentah (stdout PTY → klien; stdin klien → PTY). Tidak di-JSON-kan untuk efisiensi.
- *Text frame* (JSON) → pesan kontrol:
  ```json
  { "type": "resize", "rows": 24, "cols": 80 }
  { "type": "title",  "title": "aider — main.py" }
  { "type": "focus",  "state": "gained|lost" }
  { "type": "paste",  "data": "<clipboard content>" }
  { "type": "tui_mode", "mode": "scroll|passthrough" }
  { "type": "exit",   "code": 0 }
  ```

**Alur I/O:**
1. UI buka tab → `PTYService.open_tab(shell)` spawn PTY, kembalikan `tab_id`.
2. Klien hubungkan WS `/ws/pty/{tab_id}`.
3. PTY *master fd* dipantau (asyncio `loop.add_reader` / thread reader) → setiap output dibungkus binary frame ke WS.
4. Input dari xterm (`onData`) dikirim binary frame → ditulis ke PTY *master*.
5. `resize`: xterm `onResize` → kontrol `resize` → `pty.setwinsize(rows, cols)` + kirim `SIGWINCH` (Unix).
6. `exit`: saat shell keluar, kirim kontrol `exit`, tutup WS, tandai `TerminalTab.pty_pid` bebas.

**Deteksi shell:** Saat `open_tab`, baca `$SHELL`/`COMSPEC` → `bash|zsh|powershell|cmd` (disimpan ke `TerminalTab.shell_type` per ERD).

### 3.2 Floating Control (Fullscreen + Paste + Focus-Return)

**Penempatan komponen:** Floating control adalah **overlay HTML** (`<div class="float-ctrl">`) dengan `position: absolute` di dalam container terminal pane (bukan jendela OS). Dua tombol ikon: ⛶ (fullscreen) dan 📋 (paste). Overlay selalu di atas viewport xterm (`z-index`), tapi `pointer-events` hanya pada tombol agar tidak memblokir scroll area.

- **Toggle Fullscreen:** Klik ⛶ → JS panggil `container.requestFullscreen()` (Fullscreen API) ATAU, bila berjalan di `pywebview`/tanpa Fullscreen API, toggle class CSS `fullscreen` yang mengubah layout grid sehingga terminal pane meluas menutupi seluruh workspace (selain bar toolbar minimal). State disimpan ke `TerminalTab.is_fullscreen` (ERD). Tab lain tidak terpengaruh (fullscreen bersifat per-pane/view, bukan global app).
- **Paste + Auto-Return Focus:**
  1. Klik 📋 → JS baca `navigator.clipboard.readText()` (izin clipboard).
  2. Kirim kontrol `paste` berisi teks ke WS.
  3. Backend tulis teks mentah ke PTY *master* (tanpa modifikasi, termasuk newline bila ada).
  4. Setelah kirim, JS panggil `term.focus()` untuk mengembalikan fokus kursor ke xterm textarea aktif → user bisa lanjut mengetik tanpa klik ulang.
  - *Catatan keamanan:* paste melewati jalur PTY (bukan shell history), sehingga `OPENAI_API_KEY` yang di-inject tidak tercatat di riwayat shell (selaras US-2.6.3 best-effort).

### 3.3 Scroll & Swipe (Velocity-Based) — Resolusi Desain

**Scroll mouse & trackpad (roda):** xterm.js menangani natif via `onScroll`/wheel → buffer scroll. Horizontal didukung bila `wheelEvent` membawa `deltaX` (trackpad). Tidak perlu intervensi khusus.

**Swipe → Scroll (bukan navigasi TUI):** Diperlukan karena banyak TUI salah menangani swipe (memicu escape/navigasi). Pendekatan konkret:

1. **Intercept:** Pada container xterm, pasang *listener* `pointerdown/pointermove/pointerup` (Pointer Events mencakup touch + trackpad). Saat gerakan dikenali sebagai swipe (drag dengan arah dominan vertikal, melebihi *threshold* 10px, kecepatan rendah-sedang), **cegah event mencapai xterm** (`preventDefault` + `stopPropagation`) agar tidak jadi input TUI.
2. **Velocity computation:** Hitung `v = Δpixel / Δtime` (px/ms) per frame gerak. Simpan sebagai *velocity vector* vertikal `v_y`.
3. **Mapping velocity → scroll:**
   - `|v_y|` rendah → scroll halus **baris-per-baris** (`term.scrollLines(±1)` per frame, akumulasi fractional).
   - `|v_y|` tinggi → scroll **lompat layar** (`term.scrollPages(±k)` di mana `k` naik dengan `|v_y|`, mis. `k = clamp(round(|v_y| / V_THRESHOLD), 1, 5)`).
   - Kurva pemetaan: `scrollAmount = sign(v_y) * f(|v_y|)` dengan `f` fungsi saturating (sub-linear di ujung atas agar tidak meledak).
4. **Damping & easing:** Saat `pointerup`, kecepatan tersisa di-decat (exponential decay): `v ← v * DAMPING (0.85–0.92)` per frame hingga `|v| < EPS`. Scroll sisa diaplikasikan tiap frame via `requestAnimationFrame` → efek *glide* halus. Di ujung buffer (`term.buffer.active.viewportY` di 0 atau maks), scroll dihentikan lembut (tidak *abrupt* bounce) — cukup clamp.
5. **Rendering:** Semua scroll via API xterm (`scrollLines`/`scrollPages`), **tanpa** mengirim escape sequence ke PTY → TUI di bawah tidak menerima event navigasi.

#### 3.3.1 Mekanisme Whitelist Pengecualian TUI per-Aplikasi (Resolusi Open Question FSD)

**Open question (FSD §2.5.1):** "Aplikasi TUI yang memang membutuhkan input swipe khusus dapat dikecualikan per-aplikasi — bagaimana mekanismenya?"

**Pendekatan terpilih (proposed → accepted dalam TSD):** Sistem **kebijakan swipe per-tab berbasis metadata proses**.

- **Sumber kebijakan — `SwipePolicy` registry:** Tambah entitas penyimpanan (JSON/YAML atau tabel SQLite `swipe_exception`):
  ```
  SwipeException { id, app_name, match_pattern (regex pada cmd/title),
                   mode: "scroll" | "passthrough", priority }
  ```
  Default global = `scroll` (swipe diubah jadi scroll untuk semua tab). Entri whitelist menandai aplikasi yang butuh swipe mentah → `mode = "passthrough"`.
- **Deteksi foreground app per tab:** `PTYService` melacak *command line* tab dari dua sumber:
  - (a) Metadata eksplisit saat CLI Tool di-launch (CLI Tool Manager mengirim `launch` dengan `binary_name` → mapping ke `SwipeException`); atau
  - (b) Inspeksi ringan judul/process (Unix: baca `/proc/<pid>/cmdline` dari `pty_pid`; Windows: `pywinpty`/`psutil`).
  Hasil pencocokan `match_pattern` menentukan `tui_mode` tab.
- **Penerapan:** Setiap tab membawa flag `tui_mode` (`scroll` default). Saat `pointermove` swipe:
  - bila `tui_mode == "scroll"` → intercept & convert (§3.3 langkah 1–4).
  - bila `tui_mode == "passthrough"` → **biarkan event lewat ke xterm/PTY** (swipe diteruskan sebagai input mentah ke aplikasi TUI).
- **Override manual:** Floating control menyediakan toggle kecil per tab untuk memaksa `scroll`/`passthrough` (berguna bila deteksi otomatis gagal). Toggle mengirim kontrol `tui_mode`.
- **Contoh whitelist awal:** `less`, `man`, `vim` (mode navigasi internal), dan TUI tertentu yang memang mengonsumsi swipe — diisi bertahap; default aman = `scroll`.

> **Dampak ERD:** TSD mengusulkan penambahan tabel `SwipeException` (atau penyimpanan di `config.yaml`). Ini *evolusi* skema, tidak mengubah tabel existing. (Lihat §7).

---

### 3.4 Web Admin Console UI Shell (Frontend, tanpa framework/build)

Konsol manajemen + Terminal disajikan sebagai **SPA vanilla** (ADR-001): HTML/CSS/JS tanpa framework JS dan tanpa build step (Node). Tata letak meniru **AdminLTE** (sidebar kiri + area kerja kanan) menggunakan **vanilla CSS** (tidak memakai Bootstrap/AdminLTE bundle agar tetap no-build).

- **Layout:** Grid dua kolom — `aside.sidebar` (navigasi) + `main.workspace` (konten + Terminal pane). Header memuat pengalih tema & bahasa.
- **Collapsible Sidebar (ikon-only saat collapse):** Root `<html>`/`body` membawa class `sidebar-collapsed`. CSS: saat collapsed, `.nav-label` `display:none`, `.nav-icon` tetap tampil (lebar sidebar menyusut ke ukuran ikon). Toggle via JS → simpan state di `localStorage['aigate.sidebar']`.
- **Theme (dark/light):** Tema diimplementasikan dengan **CSS custom properties** di `<html data-theme="dark|light">` (`--bg`, `--fg`, `--panel`, `--accent`, dst). Toggle men-set atribut + simpan `localStorage['aigate.theme']`. Berlaku global termasuk Terminal pane (xterm theme disesuaikan via `term.setOption('theme', …)` saat tema berubah).
- **i18n (EN/ID):** Kamus terjemahan sisi klien `i18n = { en: {...}, id: {...} }` (ekstensible). Node dengan atribut `data-i18n="key"` diganti teksnya oleh `applyLocale(locale)`. Pengalih bahasa set `localStorage['aigate.locale']` + panggil `applyLocale`. Bahasa awal: `en`, `id`.
- **Ikon:** Font Awesome via CDN (`<link>` tanpa build) atau SVG inline; collapsed sidebar menampilkan ikon saja (tanpa teks).
- **Persistensi:** Semua preferensi UI (sidebar, theme, locale) di `localStorage` — **tidak ada entitas DB baru** (ERD tidak berubah). Tidak ada round-trip ke backend untuk ganti tema/bahasa.

> **Catatan desain:** AdminLTE *ditiru secara visual* dengan vanilla CSS (bukan mengimpor paket Bootstrap/AdminLTE) agar tetap memenuhi ADR-001 (no framework/build). Jika kelak butuh komponen kaya, dapat dipertimbangkan webview native tanpa mengubah kontrak (lihat §7).

### 3.5 Logging, Run Modes, Self-Heal & Config-in-DB

**Run / Launch:** native (`uvicorn backend.server:app`). Port via arg `--port` (default dari `Setting` DB atau 8080); mode developer via env `AIGATE_DEV=1`. Lihat SETUP.md.

**Mandatory Logging (ADR-011):** SELURUH method (frontend & backend) wajib log level info/warning/error. Level warning & error **wajib menyertakan stacktrace / inner exception**. Logger backend menulis ke tabel `LogEntry` (SQLAlchemy handler). Frontend: log client di-forward ke backend (`POST /api/logs`) lalu disimpan. **Dilarang try/catch kosong** — semua exception ditangani & di-log. Aturan ini = code-review gate (CI/git hook dapat menolak `except: pass`).

**Log Window (dev mode):** Panel di UI mode developer membaca `GET /api/logs` (filter `?severity=warning,error`), auto-refresh.

**Responsif + Simulasi Perangkat:** UI responsif (CSS media/container queries). Di mode developer, tombol simulasi phone/tablet/desktop men-set class `.device-phone/.device-tablet/.device-desktop` pada root. **Di breakpoint phone, layout menyimpang dari AdminLTE** (nav bawah / hamburger) demi mobile.

**Self-Heal (menu CLI-Tool):** lihat FSD §2.8. Backend helper `selfheal.run()`: (1) cek agentic CLI terinstall (`which` di Grup A); bila nihil → signal popup "Self-Heal tidak bisa jalan: tidak ada agentic CLI terinstall"; (2) `git init` bila belum ada repo, buat branch `aigate/self-heal-<ts>`; (3) query `LogEntry` severity warning|error; (4) buka tab terminal & jalankan agentic CLI dengan prompt fix berbasis log; (5) loop fix→test sampai tak ada warning/error (atau max iterasi).    LogWindow memantau progress. Setelah suatu issue selesai dikerjakan, baris
   `LogEntry` terkait **dihapus** agar tidak di-fix ulang. Setelah seluruh issue
   terbukti pass, helper melakukan `git merge` branch self-heal ke `main`,
   `git checkout main`, dan hapus branch fixing — run berikutnya pakai versi latest.

**Config-in-DB (ADR-010):** SELURUH konfigurasi aplikasi (port default, mode, toggle fitur, preset CLI) di tabel `Setting` (key-value) di SQLite — **bukan file terpisah**. ADR-007 (secret) tetap: secret plaintext di DB (kolom `api_key` dkk), tanpa enkripsi. File `secrets.json` dari B0.3 bersifat legacy/opsional; sumber kebenaran utama = DB.

---

## 4. Desain Gateway (OpenAI-Compatible)

### 4.1 Request Flow — `/v1/chat/completions`

```
Client (CLI Tool / UI / external)
   │  POST /v1/chat/completions  (Authorization / x-api-key opsional)
   ▼
[Gateway Server — FastAPI]
   1. Access Control: bila endpoint.access_control_enabled →
      validasi token vs Endpoint.internal_api_key (401 bila gagal)
   2. Resolve EndpointBinding → bind_type (provider | combo), bind_id
   3. Bila provider → panggil Provider Adapter langsung
      Bila combo   → panggil Combo Engine (strategi routing)
   4. Combo Engine pilih anggota (fallback / load_balance / latency_cost)
   5. Provider Adapter: ambil ProxyPool terikat (jika ada) →
      pilih node per rotation_strategy → httpx upstream call ke base_url
   6. Teruskan respons (streaming SSE bila request stream=true) ke client
```

### 4.2 OpenAI-Compatible Contract
- `POST /v1/chat/completions` — menerima & mengembalikan schema OpenAI (`messages`, `model`, `stream`, dst). `model` dipetakan ke `provider_model` anggota Combo / model Provider.
- `GET /v1/models` — mengembalikan daftar model dari sumber terikat (ProviderModel / anggota Combo).
- Error dipetakan ke format OpenAI (`error.message`, `error.type`, status HTTP).
- **Access Control:** `internal_api_key` di-generate acak saat endpoint dibuat (atau direset). Dikirim lewat header `Authorization: Bearer <key>` atau `x-api-key`. Validasi dilakukan *sebelum* resolve binding. CLI Tool Manager menyuntikkan key ini ke env `OPENAI_API_KEY` (lihat §6).

### 4.3 Combo Engine — Strategi Routing
- **Fallback:** urut `priority` asc; bila anggota returns 5xx/429/timeout → lanjut anggota berikutnya; bila habis → error gateway.
- **Load Balance:** pemilihan *weighted random* (`weight` dinormalisasi).
- **Latency/Cost:** pilih anggota dengan `last_latency_ms` (dari ProxyNode health check) atau estimasi biaya terendah (metadata `ProviderModel.capabilities`/`cost`). Data historis disiapkan untuk telemetry roadmap.
- Semua strategi memanggil **Provider Adapter** yang sama → konsisten kontrak upstream.

### 4.4 Proxy & Routing Binding (Resolusi)
**Open question:** bagaimana ProxyPool terikat ke Provider/routing?
- TSD mengusulkan **binding ProxyPool opsional pada Endpoint** (FK `proxy_pool_id` di `Endpoint`, atau asosiasi `EndpointProxyBinding`). Saat request keluar, engine memakai pool terikat endpoint; bila tidak ada, fallback ke pool default global (jika dikonfigurasi) atau koneksi langsung.
- Alternatif (kompatibel): binding per-Combo via `Combo.proxy_pool_id`. Rekomendasi: binding di **Endpoint** (cakupan traffic keluar per gateway) + opsi override di Combo. Ini menjaga `EndpointBinding` tetap polymorphic murni ke Provider/Combo (sesuai ERD).
- **Rotation strategy** (round_robin/random/failover) diterapkan oleh `ProxyPool.select_node()`; node `status=dead` dilewati (health check background).

---

## 5. Security

### 5.1 Penyimpanan `api_key` & `internal_api_key` (Resolusi: ADR-007)
**Keputusan (ADR-007, RESOLVED 2026-09-03):** aigate adalah aplikasi **lokal**; secret disimpan di **file biasa** (`.env` / config JSON / kolom SQLite) **TANPA enkripsi**, dan **UI tidak me-redaksi/masking** nilainya. Ini menggantikan usulan Fernet di draft sebelumnya.

- **Penyimpanan:** `api_key` (Provider), `internal_api_key` (Endpoint), `password` proxy (ProxyNode) ditulis apa adanya ke storage lokal (SQLite / `.env`). Tidak ada field `*_encrypted` yang dienkripsi.
- **Internal API key:** di-generate `secrets.token_urlsafe(32)` saat endpoint dibuat; tidak pernah ditulis ke shell history (di-inject via env PTY, lihat §3.2 & §6).
- **Clipboard paste** tidak mengekspos key ke disk.
- *Catatan:* Enkripsi at-rest ditunda ke roadmap bila ada kebutuhan multi-user/remote; untuk aplikasi lokal saat ini tidak diperlukan (selaras PRD §5 NFR & BACKLOG B0.3).

### 5.2 ProxyPool ↔ Provider Routing Binding
Lihat §4.4. Binding dilakukan lewat `Endpoint.proxy_pool_id` (FK opsional). Selected node diteruskan ke httpx via `proxies=` (http/https/socks5). Tidak ada key proxy yang mengalir ke provider; kredensial proxy hanya dipakai pada hop keluar.

### 5.3 Lainnya
- Gateway hanya listen di `localhost` (default) — tidak ekspos ke jaringan除非 `listen_host` diubah (dan peringatan di UI).
- Validasi input semua REST endpoint (pydantic) untuk cegah injection ke shell/PTY.

---

## 6. CLI Tool Manager & Auto-Injector (Kontrak & Alur)

- **Presets & grouping:** `CLIToolGroup` (A/B/C per ERD) + `CLITool` (binary, install_command, default_flags). Grup A (agentic) `display_priority` tertinggi.
- **Alur (sesuai FSD §2.6, BRD US-2.6.1–2.6.4):**
  1. Klik tool → `CLI Tool Manager.check_binary(binary_name)` jalankan `which`/`where` via PTY.
  2. Tiada → buka tab terminal → jalankan `install_command` (pip/uv).
  3. Ada → tampilkan **picker modal** (Provider/Combo + Model aktif dari Config Engine).
  4. Buka tab terminal baru → set env: `OPENAI_API_BASE=http://localhost:<port>/v1`, `OPENAI_API_KEY=<internal_api_key endpoint terikat>` (di-inject lewat PTY spawn env, bukan echo ke shell).
  5. Jalankan command tool + `default_flags` + model terpilih.
- **Auto-inject contract:** `PTYService.open_tab(shell, env_extra=...)` menerima env tambahan → diteruskan ke PTY spawn. Key tidak tercatat di `bash_history` karena diset sebagai env proses, bukan perintah.
- **Swipe mode:** saat launch tool TUI yang terdaftar di `SwipeException`, kirim `tui_mode=passthrough` ke tab (§3.3.1).

---

## 7. Evolvable Design & Roadmap Plug-in

Desain dibuat *contract-first* agar item roadmap (PRD §6) menempel tanpa refactor besar:

- **Telemetry & Usage Analytics:** `Provider Adapter` & `Combo Engine` sudah menghasilkan event (token in/out, latency, status). Tambah modul `TelemetrySink` yang mengonsumsi event ini → simpan ke tabel baru `UsageRecord`. UI cukup tambah panel; gateway tidak berubah.
- **Cost Limits & Rate Limiting:** Terapkan sebagai *middleware* di Gateway Server (sebelum resolve binding) membaca kuota dari `Endpoint`/`Key` config baru (`RateLimitPolicy`). Tidak mengubah kontrak upstream.
- **Plugin YAML untuk CLI Tools:** `CLI Tool Manager` memuat `plugins/cli_tools/*.yaml` yang memetakan ke `CLITool`/`CLIToolGroup` saat startup → insert/merge ke Config Engine. Mekanisme `SwipeException` juga dapat diisi via YAML (`swipe_policies.yaml`).
- **Evolusi skema:** Penambahan `SwipeException`, `proxy_pool_id` (Endpoint), `UsageRecord`, `RateLimitPolicy` dilakukan via Alembic migration (SQLAlchemy) → backward compatible.
- **Ganti GUI native nanti:** mungkin karena UI Layer hanya berbicara REST/WS (ADR-001).

---

## 8. Ringkasan ADR

| ADR | Keputusan | Status |
| :-- | :-- | :-- |
| ADR-001 | GUI = Web UI lokal (FastAPI statik + xterm.js) | Accepted |
| ADR-002 | Gateway = FastAPI + Uvicorn + httpx async | Accepted |
| ADR-003 | PTY = ptyprocess/pywinpty + xterm.js via WS | Accepted |
| ADR-004 | Config = SQLAlchemy + SQLite | Accepted |
| ADR-009 | Native Python execution, no deployment & no packaging required | Accepted (2026-09-03) |
| ADR-006 | Swipe per-app exception = `SwipeException` registry + `tui_mode` per tab | Proposed→Accepted (TSD) |
| ADR-007 | Secret at rest = plaintext di SQLite DB (tanpa enkripsi), UI tanpa redaksi | Accepted (2026-09-03) |
| ADR-008 | ProxyPool binding = FK `proxy_pool_id` di Endpoint (+ override Combo) | Accepted (2026-09-03) |
| ADR-010 | Config storage = SQLite (`Setting` table), tanpa file config terpisah | Accepted (2026-09-03) |
| ADR-011 | Mandatory logging ke DB (severity + stacktrace pd warn/err), no empty catch | Accepted (2026-09-03) |

---

## 9. Definisi Selesai (TSD)

- TSD lengkap, konsisten dengan PRD/BRD/FSD/ERD. ✔
- Terminal swipe/scroll & floating control didesain konkret (§3). ✔
- Open questions FSD terresolve: swipe-exception whitelist (§3.3.1), proxy↔provider binding (§4.4), secret storage (§5.1). ✔
- Tulis hanya di `docs/architecture/` (no cross-scope). ✔

---

*Dokumen ini ditulis di bawah scope `docs/architecture/` sesuai aturan specialist Tech Architect.*
