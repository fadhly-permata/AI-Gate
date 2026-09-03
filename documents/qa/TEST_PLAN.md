# Test / QA Plan — aigate

Peta acceptance criteria dari BRD ke test case. Merujuk BRD
(`documents/business/BRD.md`), FSD (`documents/analysis/FSD.md`), dan Backlog
(`documents/plan/BACKLOG.md`).

## Level
- **Unit**: fungsi kecil (rotasi proxy, parsing combo, injeksi env CLI).
- **Integration**: gateway -> provider, PTY bridge, CLI auto-install.
- **E2E**: alur user di UI (buka tab, jalanin CLI, scroll/swipe).

## Traceability (contoh)
| BRD ID | Fitur | Test case | Level | Gate |
|---|---|---|---|---|
| US-2.1 | CRUD Provider | buat/edit/hapus provider tersimpan di DB | unit+integration | green |
| US-2.2.2 | Rotasi proxy | request berganti proxy sesuai strategi | integration | green |
| US-2.3 | Combo fallback | provider A error -> lanjut B | integration | green |
| US-2.4 | Endpoint binding | /v1 route ke combo benar | integration | green |
| US-2.5.2 | Fullscreen toggle | tombol ubah ukuran terminal | e2e | green |
| US-2.5.3 | Paste + focus | teks masuk & fokus balik | e2e | green |
| US-2.5.5 | Swipe->scroll | swipe cepat = scroll cepat, lambat = halus | e2e | green |
| US-2.6.4 | Grouping A/B/C | tool terkelompok & ter-filter | e2e | green |
| US-2.7.1 | Collapsible sidebar (ikon saat collapse) | toggle sidebar → label hilang, ikon tetap; state persist | e2e | green |
| US-2.7.2 | Theme dark/light | toggle tema → seluruh UI + terminal ikut; persist | e2e | green |
| US-2.7.3 | i18n EN/ID | ganti bahasa → semua string UI berubah; persist | e2e | green |
| US-2.8.1 | Custom port & dev mode | server jalan di port arg; AIGATE_DEV=1 aktifkan fitur dev | integration | green |
| US-2.8.2 | Responsif + simulasi perangkat | toggle device → viewport berubah; phone bukan AdminLTE | e2e | green |
| US-2.8.3 | Log Window | panel tampil di dev mode; baca LogEntry + filter severity | e2e | green |
| US-2.8.4 | Mandatory logging | seluruh method log; warn/err + stacktrace di DB; no empty catch | static/integration | green |
| US-2.8.5 | Self-Heal | klik → branch + agentic CLI (atau popup bila none); loop fix/test; log terkait dihapus; bila pass → merge ke main + hapus branch | e2e | green |
| US-2.8.6 | Config di DB | setting baca/tulis via DB; tak ada file config sbg sumber | integration | green |

## Quality gate (CI)
- Semua unit test hijau.
- Integration test gateway minimal 1 provider mock hijau.
- E2E terminal: swipe->scroll & paste+focus wajib hijau (fitur baru).
- Coverage minimal 60% untuk modul `src/backend/**`.

## Bug tracking
Bug dicatat via command `/log-bug <title>` ke `pm/bugs.md`.
