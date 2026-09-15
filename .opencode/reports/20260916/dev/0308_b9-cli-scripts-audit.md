# Laporan Audit Skrip Install/Launch CLI (B9) — Fullstack-Dev

- Tugas: `handover-20260916-b9-audit-cli-scripts.md`
- Tanggal: 2026-09-16
- Pemilik eksekusi: fullstack-dev
- Cakupan tulis: `scripts/cli-tools/*.sh` (hanya saat ada defect terbukti) + laporan ini.
- Tidak diubah: `src/backend/**`, sistem user (`~/.aigate`, `:8080`), dependensi, `git add -A`, commit/push.

## 1. Ringkasan

Audit mendalam 25 file (`_common.sh` + 24 skrip tool) selesai. **Satu defect logika
terbukti** ditemukan dan diperbaiki: blok "best-effort reachability check" di **13 skrip**
mengandung *dead code* — peringatan "aigate not reachable" **tidak pernah muncul** meski
gateway mati. Akar: `rc=$?` diambil **setelah** `if ! curl ...`, sehingga menangkap `0`
(hasil negasi `!`), bukan kode keluar curl yang asli (7/28).

`llm.sh` sudah menggunakan pola yang benar (`if curl; then :; else rc=$?`); digunakan
sebagai referensi. Sisa 11 skrip + `_common.sh` **bersih** (termasuk 2 guard versi Python
yang diverifikasi batasannya).

Bukti repro dijalankan **100% di luar repo** (scratch `/data/.../.cache/opencode/tmp/b9-scratch`)
dengan shim PATH/fungsi — **tidak ada `npm`/`pip`/`pkg`/`cargo`/`uv` asli yang dijalankan**.

## 2. Metode & Keamanan (wajib)

- Semua shim `pkg/npm/pip/pip3/cargo/uv/node/curl` + biner tool diletakkan di direktori
  shim di luar repo. `PATH` diisi shim dulu → perintah install **ter-stub jadi no-op** yang
  mencatat ke `calls.log` bila pernah dipanggil.
- `HOME` diarahkan ke `fakehome` di scratch; `AIGATE_DB_PATH` diarahkan ke file `.db`
  tidak-ada → `load_gateway_config` tidak membaca/menyentuh `~/.aigate` asli.
- Biner tool "sudah ada" (shim) → `ensure_installed` memotong (idempoten), jadi jalur
  install tidak pernah tersentuh.
- `curl` shim **selalu `exit 7`** (simulasi gateway tidak terjangkau) untuk membuktikan
  perilaku peringatan.

## 3. Temuan per Skrip

| Skrip | Status | Catatan |
|---|---|---|
| `_common.sh` | BERSIH | double-source guard + `BASH_SOURCE` path — terbukti (lihat §5.1) |
| `aider.sh` | **FIXED** | reachability dead-code; guard 3.10–3.12 terverifikasi benar |
| `aichat.sh` | **FIXED** | reachability dead-code |
| `claude.sh` | **FIXED** | reachability dead-code; `AIGATE_ROOT` strip `/v1` konsisten dgn builder |
| `cline.sh` | **FIXED** | reachability dead-code |
| `codex.sh` | **FIXED** | reachability dead-code; native-mode (tak di-wire) sesuai preset |
| `gemini.sh` | **FIXED** | reachability dead-code; native Google (tak di-wire) sesuai preset |
| `gptme.sh` | **FIXED** | reachability dead-code |
| `kilo.sh` | **FIXED** | reachability dead-code |
| `opencode.sh` | **FIXED** | reachability dead-code (lihat kandidat §6.1) |
| `open-interpreter.sh` | **FIXED** | reachability dead-code; binernya `interpreter` |
| `openhands.sh` | **FIXED** | reachability dead-code; guard 3.12 terverifikasi benar |
| `oterm.sh` | **FIXED** | reachability dead-code; `${OPENAI_API_KEY}` literal benar |
| `qwen.sh` | **FIXED** | reachability dead-code |
| `llm.sh` | BERSIH | satu-satunya yang **sudah** pakai pola benar (referensi) |
| `antigravity.sh` | BERSIH | NO_INSTALL no-op; exit 0, 0 panggilan pkg |
| `phi.sh` | BERSIH | NO_INSTALL no-op |
| `goose.sh` | BERSIH | NO_INSTALL no-op |
| `amp.sh` | BERSIH | NO_INSTALL no-op |
| `swe-agent.sh` | BERSIH | NO_INSTALL no-op (regresi backtick lama sdh beres) |
| `autogpt.sh` | BERSIH | NO_INSTALL no-op |
| `sgpt.sh` | BERSIH | NO_INSTALL no-op |
| `mods.sh` | BERSIH | NO_INSTALL no-op |
| `gpt-researcher.sh` | BERSIH | NOT_A_CLI no-op; exit 0, 0 panggilan pkg |
| `crewai.sh` | BERSIH | NOT_A_CLI no-op; exit 0, 0 panggilan pkg |

Total: **13 FIXED**, **11 BERSIH** (termasuk `llm.sh`), + `_common.sh` BERSIH = 25 file.

## 4. Defect Terbukti #1 — Reachability warning = dead code (13 skrip)

### 4.1 Bukti (repro aman, sebelum perbaikan)

Tes minimal di scratch:
```bash
set -euo pipefail
fake_curl_7() { (exit 7); }
if ! fake_curl_7; then rc=$?; echo "rc captured = $rc"; fi
# → "rc captured = 0"   (bukan 7!)
```
Penjelasan: di `if ! cmd; then ... fi`, `$?` di dalam blok `then` adalah status keluar
dari **pernyataan negasi `!`** (selalu `0` saat kondisi "benar"=gagal), bukan `cmd`.
Maka `if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]` tak pernah cocok → cabang WARN mati.

Bukti end-to-end (shim `curl` `exit 7`) sebelum fix, jalankan 24 skrip:
- `WARN=YES` hanya **`llm.sh`** (1 skrip).
- `WARN=NO` untuk **13 skrip** lain yang punya blok tersebut (aider, aichat, claude,
  cline, codex, gemini, gptme, kilo, opencode, open-interpreter, openhands, oterm, qwen).
- `calls.log` mencatat **0** baris `PKG_CALL` (tidak ada npm/pip/pkg/cargo/uv asli dijalankan).

### 4.2 Perbaikan

Ganti pola `if ! curl ...; then rc=$?` menjadi pola yang sudah benar di `llm.sh`
(`if curl ...; then :; else rc=$?`). Perubahan identik di 13 file, contoh `aider.sh`:

```diff
 if have_cmd curl; then
-  if ! curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
+  if curl -fsS -o /dev/null --max-time 3 "${AIGATE_BASE}/models" 2>/dev/null; then
+    : # gateway reachable; nothing to warn about
+  else
     rc=$?
     if [ "$rc" -eq 7 ] || [ "$rc" -eq 28 ]; then
       log_msg "WARN: aigate not reachable at $AIGATE_BASE ..."
```

### 4.3 Bukti sesudah perbaikan

Shim `curl` `exit 7` dijalankan lagi → sekarang **14 skrip** (`llm.sh` + 13 yang diperbaiki)
mencetak `WARN: aigate not reachable`; 10 skrip NO_INSTALL/NOT_A_CLI (yang memang tak punya
probe) tetap `WARN=NO` dan `exit 0`. `calls.log` tetap **0** `PKG_CALL`.

`bash -n` pada **ke-25 file = 0 error** (sebelum & sesudah).

Catatan keamanan: di perangkat Termux **asli curl tidak terpasang**, jadi blok probe
sepenuhnya dilewati (`have_cmd curl`=false) — defect ini **tidak teramati** di box ini,
tapi tetap cacat logika untuk environment apapun yang punya curl (macOS/Linux/WSL selalu
memilikinya). Perbaikan menyelaraskan 13 skrip ke `llm.sh` yang sudah benar.

diffstat: `13 files changed, 39 insertions(+), 13 deletions(-)`.

## 5. Item Audit Lain — TERBUKTI BERSIH (dengan bukti)

### 5.1 Source `_common.sh` benar
`AIGATE_COMMON_LOADED` guard + `source "$SCRIPT_DIR/_common.sh"` (`BASH_SOURCE`-based).
Dites: source 2× dari `/tmp` (CWD beda) → `AIGATE_COMMON_LOADED=1` tetap, `log_msg`/`detect_os`
masih hidup, `AIGATE_OS=termux` terdeteksi. **Path-independent & idempoten.** BERSIH.

### 5.2 Pesan literal aman (tidak ada command-substitution tereksesusi)
Grep backtick → **hanya di baris komentar** (header riset). Grep `$(` → hanya legit
(`uname`, `python3 -c`, `esc`, `printf` untuk `MODEL_JSON`). Tidak ada `$(...)` di dalam
argumen `log_msg` yang mengeksekusi perintah. NO_INSTALL/NOT_A_CLI punya pesan statis
(tidak ada regresi backtick seperti swe-agent lama). `oterm.sh` menulis `${OPENAI_API_KEY}`
literal via heredoc `\${...}` — terbukti benar (`config.json` valid). BERSIH.

### 5.3 NO_INSTALL / NOT_A_CLI = no-op terbukti
Jalankan 10 skrip no-op di harness → **semua `exit 0`**, `calls.log` = 0 `PKG_CALL`
(tidak ada npm/pip/pkg/cargo/uv yang dipanggil), tidak ada `WOULD_EXEC`. BERSIH & tanpa
side-effect.

### 5.4 Idempoten + path-independent
Semua skrip pakai `SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)`. Di harness,
jalankan dari CWD scratch → config (`opencode.json`, `aichat-aigate.yaml`, `.kilo/`,
`.oterm-aigate/`, `.qwen/`) ditulis ke CWD scratch (bukan repo/`~`). `ensure_installed`
memotong bila biner sudah ada. Re-run aman. BERSIH.

### 5.5 Konsistensi launcher vs `cli_presets.py` + `cli_tools_router.py`
Flag/env tiap installer cocok dengan builder di `cli_tools_router.py`:
aider (`--openai-api-base/--openai-api-key`), claude (`ANTHROPIC_BASE_URL` root + strip
`/v1` = `_claude_builder`), gptme (`OPENAI_BASE_URL` + `-m local/<m>`),
open-interpreter (`--api_base/--api_key`), openhands (`LLM_* + --override-with-envs`),
aichat/oterm/qwen/kilo (config file + env scope), cline (`cline auth --provider
openai-native`), codex/gemini (native, tak di-wire, sesuai `LAUNCH_UNSUPPORTED` di preset).
BERSIH untuk flag/env utama.

### 5.6 Version-guard (aider 3.10–3.12, openhands 3.12) terverifikasi
Dengan shim `python3` lapor versi bervariasi:
- **aider**: terima 3.10/3.11/3.12; **tolak** 3.9/3.13/3.14/2.7/4.0 (sesuai PyPI
  `requires_python ">=3.10,<3.13"`).
- **openhands**: `uv` absen → wajib **persis** 3.12 (tolak 3.11/3.13/3.14);
  `uv` ada → lewat rute `uv` (lolos di 3.14). Sesuai `requires_python ==3.12.*`.

Keduanya benar. BERSIH.

## 6. Kandidat Non-Blocking (BUKAN bug terbukti — perlu konfirmasi, tidak diubah)

### 6.1 `opencode.sh`: `models: {}` kosong bila tanpa `AIGATE_MODEL`
Skrip menulis `"models": {}` (tidak menyertakan model terpilih), sementara
`_opencode_builder` (router) mengisi peta model dari `provider_models`. Tanpa entri model,
opencode mungkin tak menemukan model yang dipilih. **Belum dibuktikan** (opencode tak bisa
dijalankan di sini). Sifatnya juga perbedaan *standalone-vs-backend* (skrip CLI tak punya
sesi DB untuk enumerasi model). Tidak diubah — lihat pertanyaan §7.

### 6.2 Enumerasi `provider_models` hanya ada di backend
aichat/qwen/kilo/opencode di backend menyertakan SELURUH model provider terdiscovery;
skrip CLI hanya menyematkan `AIGATE_MODEL` tunggal (atau kosong). Ini perbedaan rancangan,
bukan defect terbukti. Dicatat agar tidak dikira bug saat review.

## 7. DaFTAR PERTANYAAN SPESIFIK UNTUK USER

User melaporkan "masih ada bug" tanpa gejala spesifik. Mohon jawab agar bisa direproduksi:

1. **Tool mana** yang bermasalah? (dari 24: claude, opencode, codex, gemini, antigravity,
   phi, aider, goose, amp, qwen, cline, kilo, openhands, swe-agent, open-interpreter,
   autogpt, gpt-researcher, crewai, llm, sgpt, mods, oterm, gptme, aichat)
2. **Pesan error persis** apa yang muncul? (copy-paste) — khususnya saat `bash <tool>.sh`.
3. **Langkah mana** yang gagal: (a) install (`ensure_installed`/pkg/npm/pip), atau
   (b) launch setelah terpasang, atau (c) koneksi ke gateway (chat gagal)?
4. **`command -v curl`** di perangkat — ada/tidak? (di box ini curl **tidak** ada, jadi
   peringatan reachability tidak muncul; itu sebabnya fix #1 butuh user punya curl untuk
   terlihat efeknya.)
5. **Diperoleh dari mana** skrip dijalankan: lewat terminal UI aigate, atau manual
   `bash scripts/cli-tools/<tool>.sh`? (dan `AIGATE_MODEL` disetel atau tidak.)
6. Untuk tool "known-broken di Termux/aarch64" (claude/kilo/cline butuh biner android yang
   tak ada; llm/oterm/gptme/openhands gagal build `jiter` Rust di Python 3.14): apakah
   gejalanya **install error** atau **tool mati setelah install**? Bedakan ini (keterbatasan
   platform/wheel, bukan script bug) dari bug logika sungguhan.
7. Bila berkenaan dengan §6.1: pernahkah `opencode` gagal temukan model yang dipilih
   (`AIGATE_MODEL`) saat launch? Kalau ya, itu kandidat #6.1.

## 8. Catatan Repo

- `documents/pm/status.md` terlihat berubah di `git status`, tapi **BUKAN ubahan saya**
  (isi = record memory-bank PM B6 wiki-review, append-only). Tidak saya sentuh.
- File handover `documents/pm/handovers/handover-20260916-b9-audit-cli-scripts.md` muncul
  sebagai untracked — itu sumber tugas, bukan ubahan saya.
- **Tidak ada commit/push.** Menunggu arahan PM.
