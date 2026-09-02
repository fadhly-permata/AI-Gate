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

## Quality gate (CI)
- Semua unit test hijau.
- Integration test gateway minimal 1 provider mock hijau.
- E2E terminal: swipe->scroll & paste+focus wajib hijau (fitur baru).
- Coverage minimal 60% untuk modul `src/backend/**`.

## Bug tracking
Bug dicatat via command `/log-bug <title>` ke `pm/bugs.md`.
