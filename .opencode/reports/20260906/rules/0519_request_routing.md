# Laporan Tugas: Routing Semua Input ke ProjectManager

## Informasi Dasar
- Tanggal: 2026-09-06
- Jenis Tugas: rules/configuration
- Waktu Mulai: 05:19

## Permintaan Pengguna
Setiap command, pertanyaan, interaksi, atau input serupa harus di-handoff ke
agent `@ProjectManager` dan aturan ini dibuat durable di lokasi konfigurasi/rules
project.

## Rencana Pekerjaan
1. Inspeksi aturan `.opencode`, agent ProjectManager, konfigurasi, dan PM rules.
2. Tambah aturan routing project-level tanpa mengubah file unrelated.
3. Simpan aturan durable di PM operating rules, lalu verifikasi diff dan status.

## Realisasi Pekerjaan
- [05:19] `.opencode/rules/*.md`, `.opencode/agents/ProjectManager.md`,
  `opencode.json`, dan `pm/*` diinspeksi.
- [05:19] `.opencode/rules/request-routing.md` dibuat sebagai aturan routing
  utama untuk semua input user ke `@ProjectManager`.
- [05:19] `pm/OPERATING_RULES.md` ditambah R23 sesuai kebijakan durable PM.
- [05:19] Hasil perubahan diverifikasi melalui pembacaan file dan pemeriksaan
  status/diff git.

## Status Akhir
Berhasil — project rule baru mengarahkan seluruh input user ke
`@ProjectManager`; instruksi dengan prioritas lebih tinggi tetap berlaku.
