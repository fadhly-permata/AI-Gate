# Arsip Decisions lama memory-bank (dipindah 2026-09-10, isi utuh)

## Decisions (arsip lama — keputusan terbaru ada di heading pertama)
- 2026-09-08: Materi publik TIDAK boleh menulis "this repo"/"repo ini" untuk menunjuk diri sendiri —
  teks ikut ter-fork jadi ambigu. Klaim identitas resmi wajib pakai URL absolut
  `https://github.com/fadhly-permata/AI-Gate`. Diumumkan sebagai aturan **R45** setelah user menegur
  kalimat README. Link UI ke repo sudah absolut (sidebar) → fork tetap menunjuk asal.
- 2026-09-06: Semua laporan wajib berada di `.opencode/reports/**`; root-level `reports/**` dihapus dan scope QA/agent diperbaiki sesuai R23.
- 2026-09-03: Terminal UX — swipe diubah jadi scroll (bukan navigasi TUI) karena
  TUI sering salah tangani swipe. Scroll velocity-based + damping agar natural.
  KOREKSI 2026-09-05: keputusan lama bikin swipe MATI di TUI (alt-buffer tidak
  punya scrollback, `term.scrollLines()` no-op di sana) dan terasa tidak natural
  di shell (arah dibalik + lompat per velocity). Sekarang swipe = event `wheel`
  sintetis ke elemen xterm -> xterm yang mapping: buffer normal scroll 1:1,
  alt-buffer kirim cursor key / mouse-wheel report ke aplikasi. Momentum rAF +
  friction. Tombol TUI jadi passthrough eksplisit (gesture mentah ke app).
  Doc diselaraskan: PRD §2.5.1, FSD §2.5.1, ux/TERMINAL_UX §2.
- 2026-09-03: CLI tool presets dikelompokkan; prioritas agentic CLI (claude, opencode, codex, gemini, antigravity, phi, aider, goose, amp, qwen, cline,
  kilo, dst). Dapat diperluas via YAML/JSON.
  KOREKSI 2026-09-05: (1) semua install pakai `pip install <nama>` padahal nama
  PyPI-nya milik proyek lain (codex=web server komik, gemini=framework DB
  genetika, claude-code=stub reserved, aichat=proyek lain) -> install string
  sekarang diverifikasi ke registry npm/PyPI (npm untuk CLI Node). (2) guard
  seed "skip kalau tabel sudah berisi" bikin semua fix preset jadi dead code ->
  jadi UPSERT idempoten (kolom preset disegarkan, `enabled` + baris user utuh).
  (3) flag tebakan (`claude openai-compatible`) dihapus: bentuk launch milik
  builder. (4) registry `LAUNCH_SUPPORT` (verified/pending/unsupported + reason
  code) = sumber kebenaran di kode, bukan kolom DB; UI mencoret nama yang belum
  verified, `resolve` menolak 409. Builder per-tool: satu per satu, 1 commit/tool.
- 2026-09-03 (TSD ADRs): GUI = web UI lokal (FastAPI static + xterm.js);
  PTY = ptyprocess/pywinpty + xterm.js via WebSocket; swipe exception =
  SwipeException registry + per-tab tui_mode.
  - ADR-007 (secrets): RESOLVED — app lokal, simpan di file biasa TANPA enkripsi,
    UI tidak perlu redaksi/masking. (putus 2026-09-03)
  - ADR-008 (proxy binding): RESOLVED — binding di level Endpoint; Endpoint
    menunjuk ke Combo (Endpoint -> Combo). (putus 2026-09-03)

- 2026-09-06: Semua input user diroute ke `@ProjectManager` sebagai entrypoint
  tunggal melalui `.opencode/rules/request-routing.md`; instruksi priority lebih
  tinggi tetap berlaku.
- 2026-09-06: Durable request-routing rule selesai dibuat. (Di `main` dinomori
  **R23**; di branch `refactor/ui` konsep yang sama = **R29** — lihat
  `documents/pm/OPERATING_RULES.md`. Saat merge #4, duplikat R23-routing `main`
  tidak dimasukkan karena sudah tercakup R29.)


### Keputusan lisensi (2026-09-08) — user: "kita pake mit aja dulu"
- Lisensi proyek: **MIT**, `Copyright (c) 2026 Fadhly Permata`, file `LICENSE` di branch `chore/mit-license`.
  Badan teks diverifikasi identik byte dengan teks resmi SPDX (bukan ditulis dari ingatan).
- Dikatakan eksplisit oleh user: **SEMENTARA**. Pemicu review lagi: sebelum rilis publik pertama /
  sebelum kontribusi luar masuk / kalau ada yang ngomersialkan klon. Salinan MIT yang sudah tersebar
  tidak bisa ditarik balik; naik ke copyleft nanti hanya melindungi versi ke depan.
- Efek: larangan kata "free / open source" di materi publik DICABUT.
- 2026-09-08: user memilih urutan **B** (lisensi naik SETELAH PR #10). PR #10 ternyata sudah merged
  (8b72f84, 7 varian README ikut masuk main) → lisensi naik sebagai **PR #11** (clean, 9 commit).
  Catatan: klaim "open source" TIDAK pernah tayang di main tanpa LICENSE, jadi gak ada publikasi
  yang menyesatkan selama proses ini. Alasan "repo ini satu-satunya
  sumber resmi" ikut ditulis, karena MIT tidak mewajibkan apa pun ke peng-copy.
- Ketaatan pihak ketiga: notis MIT xterm.js (di-vendor) disimpan di `THIRD_PARTY_NOTICES.md`; versi
  xterm TIDAK tercatat di repo → masih utang (WL.4). Font Awesome cuma lewat CDN (tidak didistribusikan),
  tapi memuat CDN = icons mati tanpa internet + request keluar → bertentangan dengan klaim privasi (WL.5).
