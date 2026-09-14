# Lembar Desain — Header kolom toggle + menu tiga titik (edit/hapus) di tabel anggota kombo

- Tanggal: 2026-09-13 · Penulis: ProjectManager (aturan **D6**: lembar desain + ACC user sebelum spawn fe-dev).
- Status: **DI-ACC — user perintah eksplisit** ("toggle enable/disable per model kenapa gak ada nama kolomnya" + "tombol aksi edit dan hapus mending diganti tombol tiga titik dengan submenu edit dan delete").
- Dasar: fitur toggle per-model (`7f351f9`) sudah jalan; kolom pertamanya header-nya dibiarin kosong (`<th></th>`) sehingga user bingung mencari toggle. Tombol edit (pencil) + hapus (trash) masih terpisah.

## A. Beri nama kolom di toggle enable/disable (frontend-only — fe-dev)

### Fakta
- Header tabel anggota kombo di `index.html` (modal edit kombo): kolom ke-1 = `<th></th>` (kosong), lalu Model, Weight, `<th></th>` (aksi).
- Kolom ke-1 di `renderMembers` (`combos.js:461-467`) isinya grip `js-mem-drag` + checkbox toggle `js-mem-enabled`.
- `combos.member.enabled` sudah ada di 7 kamus (= "Enabled").

### Desain
- Isi `<th></th>` kolom ke-1 dengan `data-i18n="combos.member.enabled"` (teks "Enabled"). Kolom ini memang berisi grip + toggle; label merujuk ke toggle (kontrol yang berarti). 
- Nol kolom baru (tetap 4 kolom); `colspan="4"` baris kosong tetap.

## B. Ganti edit+hapus jadi satu tombol tiga titik (kebab) dengan submenu (frontend-only — fe-dev)

### Fakta
- Aksi sekarang (`combos.js:476-486`): `<span class="member-move">[▲▼]</span>` + tombol `js-mem-edit` (pencil) + `js-mem-del` (trash), ditangani di listener delegasi tbody (`combos.js:449-506`).
- Pola kebab SUDAH ada & dipakai tabel lain: `window.aigate.rowMenuCellHtml()` (`app.js:733`) + `window.aigate.wireRowMenu(scope, getActions)` (`app.js:741`); menu pakai kelas `.row-menu` / `.row-menu-item`, item `danger` untuk hapus.

### Desain
- Hapus tombol `js-mem-edit` + `js-mem-del`. Ganti dengan SATU kebab (`rowMenuCellHtml()`) di dalam cell aksi, sebelah ▲▼.
- Submenu = **[Edit, Delete(danger)]**, label pakai `getStr("combos.member.edit")` + `getStr("combos.member.remove")` (dua key ini sudah ada, parity aman).
- `getActions(tr)` mengembalikan item dengan `onClick` yang memanggil logika SAMA persis seperti `combos.js:505-506`:
  - Edit → `editMemberRow(mid, idx)`.
  - Delete → `if (selectedId && mid != null) removeMember(mid); else removeMemberLocal(idx);`
- ▲▼ tetap di luar kebab (tombol move terpisah, seperti sekarang).
- Wiring kebab di combo: karena `renderMembers` menulis ulang `innerHTML` tiap mutasi, **re-wire setelah tiap render** — panggil `window.aigate.wireRowMenu(body, getActions)` di akhir `renderMembers`, dengan guard supaya listener `document`-level penutup menu tidak didaftarkan berulang (cek flag modul, atau andalkan guard `wireRowMenu` bila ada). JANGAN biarkan menu gagal terbuka setelah reorder/reload.
- Pastikan kebab tidak bentrok dengan handler grip/drag di listener delegasi (grip pakai `pointerdown`; kebab pakai `click` via wireRowMenu).

## C. Yang tidak diubah
- Backend tidak disentuh (toggle + edit/hapus sudah ter-wiring ke API). `enabled` cols, ▲▼, drag, animasi tetap.
- Tidak ada warna hex baru.

## D. Risiko jujur
1. Kolom ke-1 berisi grip + toggle tapi di-header "Enabled" — bisa sedikit aneh karena grip juga di situ. Kalau user mau toggle dipisah jadi kolom sendiri, bilang (butuh ubah colspan jadi 5).
2. Kebab di tabel yang innerHTML-nya ditulis ulang tiap render rawan listener ganda — fe-dev wajib guard.

## E. DoD (fe-dev)
- `node node_modules/.bin/vitest run` HIJAU (baseline 26 file / 664 tes + tes baru). Tes: kolom ke-1 punya header "Enabled"; kebab membuka submenu Edit+Delete; klik Edit → `editMemberRow`, Delete → remove (saved/buffer); parity i18n 7/7 utuh.
- `git diff --check` bersih; `git status --short` hanya `src/frontend/**`; nol hex baru; reorder/drag/animasi/toggle tetap jalan.
