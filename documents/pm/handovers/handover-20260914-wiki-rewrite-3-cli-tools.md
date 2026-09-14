# Handover — Wiki Rewrite, halaman 5 `CLI-Tools.md` (owner: public-writer)

**PM → public-writer · 2026-09-14 · branch `docs/wiki` · SEKUENSIAL (halaman 3,4 selesai, ini ke-3).**

## Tugas
Tulis ULANG `documents/pm/wiki-drafts/CLI-Tools.md` pakai suara & standar Public Writer.
Sudut pandang: orang buka halaman ini karena mau **alat coding yang SUDAH dipakai** jalan di model
pilihannya — tulis dari sudut itu, bukan dari sudut "fitur".

## Baca (READ, urutan)
1. `Home.md` + `Quick-Start.md` → suara ACC. JANGAN ubah.
2. `documents/pm/wiki-drafts/CLI-Tools.md` → draf lama.
3. `documents/pm/handovers/2026-09-08-wiki-sheetB.md` bagian "HALAMAN 5" → lembar fakta.
4. `documents/plan/wiki-plan.md` §2 → konten TERLARANG.

## Fakta (terverifikasi PM dari kode hari ini)
Bukti read-only: `src/backend/cli_presets.py` (CLI_PRESETS list 3 grup, LAUNCH_SUPPORT,
TERMUX_INSTALL), `src/backend/gateway/router.py:528` (`/v1/messages` inbound Anthropic).
- **24 alat**, 3 grup: **Agentic Coding Assistants** (12: claude, opencode, codex, gemini, antigravity,
  phi, aider, goose, amp, qwen, cline, kilo), **Autonomous Software Agents** (6: openhands, swe-agent,
  open-interpreter, autogpt, gpt-researcher, crewai), **Chat & Shell Assistants** (6: llm, sgpt, mods,
  oterm, gptme, aichat). Catatan WAJIB: daftar masih terus bertambah, dan **sebagian jalur pasang belum
  ada di semua platform**.
- **claude sekarang TERVERIFIKASI** (`LAUNCH_SUPPORT['claude'].mode='verified'`, pasang:
  `npm install -g @anthropic-ai/claude-code`) — tidak lagi "unsupported". aigate kini juga menjawab
  **format Anthropic** (`/v1/messages`, `router.py:528`) sehingga claude-code menunjuk ke situ tanpa
  perantara litellm.
- Nama alat sebut sebagai CONTOH (jangan daftarkan ke-24): claude, opencode, codex, gemini, aider,
  goose, amp, qwen, cline, kilo, openhands, open-interpreter, gptme, aichat, llm, sgpt, mods, oterm,
  antigravity, phi, swe-agent, autogpt, gpt-researcher, crewai.
- Alur pakai: buka area alat coding → pilih alat → pilih penyedia/model → alat **dibuka di tab
  terminal baru** dengan setelan yang sudah disiapin.
- Cara penyetelan **beda per alat**: sebagian ditulisin ke **berkas konfigurasi alatnya**, sebagian
  lewat **variabel lingkungan di depan perintah**.
- **Termux**: sebagian alat punya perintah pasang khusus Termux (contoh: `aichat` via cargo, `codex`
  via npm); untuk alat lain aigate menyodorkan perintah pasang yang sesuai perangkat bila ada.
  (Jangan over-claim "semua alat cocok Termux" — hanya 2 punya override Termux hari ini; sisanya
  pakai perintah pip/npm/cargo umum yang juga jalan di Termux. `TODO-VERIFY` kalau mau lebih teliti.)
- **JANGAN** tulis angka per kelompok (12/6/6) — basi kalau daftar tumbuh; cukup sebut "24 alat,
  tiga kelompok" sekali, dan jangan tempel daftarnya di halaman lain.
- **JANGAN** klaim "marked not launchable" — yang benar: sebagian alat tidak ditawarkan jalur
  launch-nya (belum terverifikasi).

- **Self-Heal** ada di halaman **alat coding** ini (kartu Self-Heal di view `cli`, `index.html:856-880`).
  Fakta terverifikasi (`src/backend/selfheal.py`, `selfheal_router.py`):
  - Membuat **branch git** sendiri, meluncurkan **agentic CLI** (binary yang user pasang, mis. claude/opencode)
    di **tab terminal langsung (live)**, jalanin putaran perbaikan dari baris peringatan/error di log,
    lalu **merge balik ke `main`** dan hapus branch.
  - Butuh: **proyek git** + **satu agentic CLI terpasang** di PATH. Tiap langkah tercatat; kegagalan jadi
    status aman, bukan crash.
  - **RISIKO WAJIB ditulis jujur**: fitur ini **menulis kode dan menggabungkan branch** — user wajib review
    hasil sebelum memakai. Jangan jual sebagai "otomatis beres tanpa awasi".
  - Jangan jelaskan langkah teknis; arahkan ke layarnya. Boleh sebut "bikin branch, jalanin agen di tab
    live, benerin warning, merge balik kalau lulus" (sesuai bunyi README yang sudah di-ACC).

## Yang harus berubah dari draf lama
- Pembuka wajib story motion: orang yang alatnya biasa berhenti nanya key+alamat → sekarang langsung jalan.
- Hindari brosur; 1 ide 1 kalimat.
- Nol rujukan self-relative (R45).

## Larangan keras (sama halaman 3/4)
Path `src/**`/`documents/**`, nama file sumber, tabel/kolom DB, ADR/R#, "MIT", "this repo",
"untested/experimental", jumlah baris/komit. `TODO-VERIFY` kalau ragu. `aigate` kecil. Taut cuma 8
nama halaman. Baris terakhir: `Made with ❤️ by Fadhly Permata`. **JANGAN** git/commit/push/publik.

## Panjang
360–480 kata (badan).

## DoD + Receipt
Sama format halaman 3. Peta klaim→bukti wajib rujuk `cli_presets.py` (line untuk CLI_PRESETS /
LAUNCH_SUPPORT / TERMUX_INSTALL) dan `gateway/router.py:528`.
