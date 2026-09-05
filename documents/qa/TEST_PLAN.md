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
| US-2.1.4 | Multi-akun | provider punya ≥1 akun; routing pakai akun lain bila limit | integration | green |
| US-2.1.5 | OAuth + refresh | login OAuth; token diperbarui otomatis & request jalan | integration | green |
| US-2.3.4 | 3-tier fallback | habis kuota/error → pindah tier bawah otomatis | integration | green |
| US-2.3.5 | multi-akun + kuota | akun limit → akun lain; routing sadar kuota | integration | green |
| US-2.4.4 | Format translation | client OpenAI jalan ke provider non-OpenAI via terjemahan | integration | green |
| US-2.4.5 | Token saver | RTK kurangi token; toggle mati → normal (fail-open) | unit+integration | green |
| US-2.4.6 | Kuota tracking | dashboard kuota & reset countdown tepat | integration | green |
| US-2.4.7 | Log + Analytics | debug log & laporan pemakaian tersedia | integration | green |
| US-2.4.8 | Export/Import | export → import pulih setting | e2e | green |
| US-2.9.1 | Chat streaming | kirim pesan → jawaban SSE bertahap via gateway | integration | todo |
| US-2.9.2 | Multi-sesi + riwayat | sesi tersimpan; reload → riwayat utuh; buat/hapus sesi | integration | todo |
| US-2.9.3 | Pilih tujuan | provider+model ATAU combo; combobox auto-fetch/search | e2e | todo |
| US-2.9.4 | System prompt & parameter | system prompt + temperature diterapkan ke request | integration | todo |

## Quality gate (CI)
- Semua unit test hijau.
- Integration test gateway minimal 1 provider mock hijau.
- E2E terminal: swipe->scroll & paste+focus wajib hijau (fitur baru).
- Coverage minimal 60% untuk modul `src/backend/**`.

## Bug tracking
Bug dicatat via command `/log-bug <title>` ke `pm/bugs.md`.
