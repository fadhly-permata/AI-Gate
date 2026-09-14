# Laporan Implementasi: Tutup Tab Terakhir (X) + Banner Reconnect Terminal

**Tanggal:** 2026-09-13
**Pelaksana:** fe-dev (frontend, 2 putaran: fix utama + penyesuaian test yang terdampak)
**Verifikasi PM:** mandiri, `node ./node_modules/vitest/vitest.mjs run` → **6 berkas / 171 tes LOLOS, 0 gagal**
**Status kode:** BELUM di-commit (menunggu perintah user)

## 1. Masalah (dari laporan user)
1. Menutup tab terminal terakhir lewat tombol X tidak menutup tab sama sekali — selalu muncul tab baru. Sedangkan perintah `exit` menutup semua tab.
2. Teks "Reconnecting… / Reconnected" tidak pernah dihapus setelah koneksi pulih, sehingga menumpuk dan tumpang tindih dengan TUI (aplikasi layar penuh seperti vim/htop/less).

## 2. Akar Masalah (terverifikasi, ada file:line)
- **#1 — `src/frontend/static/terminal.js`** `closeTab()` baris 694–705. Cabang tutup manual (tanpa flag `exited`) pada tab terakhir memanggil `openTab()` (baris 703), jadi sengaja selalu menyisakan satu tab hidup. Jalur `exit` (flag `exited`) justru menampilkan empty state (baris 698–700) — itulah sebabnya beda perilaku.
- **#2 — `src/frontend/static/terminal.js`** `writeStatus()` baris 300–304 menulis status langsung ke dalam buffer xterm via `tab.term.write("\r\n\x1b[2m"+text+"\x1b[0m\r\n")`. Baris itu tidak pernah dihapus dan mencekik posisi kursor TUI saat PTY mengulang gambar layar (replay ring buffer), sehingga terjadi tumpang tindih.

## 3. Perubahan
**`terminal.js`**
- `writeStatus()` (≈300–338): status kini dirender sebagai banner DOM overlay (`.term-status-banner`) di dalam `.term-tab-container`, BUKAN ke buffer xterm. Ditambah `statusBanner(tab)` (lazy, `role="status"`, `aria-live="polite"`) dan `clearStatus(tab)` (sembunyi + lepas + batalkan timer).
- `ws.onopen` (≈462–476): `clearStatus(tab)` setiap koneksi terbuka; bila `reconnectShown` aktif, tampilkan "Reconnected" lalu auto-`clearStatus` setelah 1800 ms.
- `scheduleReconnect` (≈339–342): tetap memanggil `writeStatus` (sekarang via banner); penjaga "tampil sekali per episode" (`reconnectShown`) dipertahankan.
- `openTab` — baris "Connecting" awal (≈596) dialihkan ke `writeStatus` (banner), tidak lagi `term.write`.
- `closeTab` cabang tab terakhir (≈746–753): dihapus `openTab()`; kini `clearStatus(tab)` + `activeId = null` → empty state, tanpa respawn. Kill frame di jalur `!opts.exited` tetap dikirim (PTY tetap dibunuh). Tab shape ditambah `statusBannerEl`, `statusTimer`.

**`styles.css`**
- `.term-tab-container` ditambah `position: relative` (jangkar overlay).
- Baru: `.term-status-banner` + `[hidden]` (absolut, atas-tengah, redup, `pointer-events:none`), memakai token `--term-chrome` / `--term-chrome-fg-strong` yang sudah ada.

## 4. Test yang Disesuaikan (semua masih `src/frontend/tests/**`)
- `terminal_exit.test.js` (≈368): describe "deliberate close behavior is unchanged" diganti "deliberate close of the LAST tab → empty state" — menuntut kill frame terkirim, `tabs.size===0`, `termEmpty.hidden===false`.
- `terminal_reconnect.test.js` (≈182): 3 test baru — (a) drop → banner berisi "Reconnecting", TIDAK di `term.writes`, retry tak menambah banner; (b) reattach → banner "Reconnected" lalu `null` setelah 1800 ms; (c) openTab → banner "Connecting", tidak di buffer.
- `terminal_discard.test.js` (≈280, 327, 333): 4 assertion lama yang mengasumsikan "tutup tab terakhir → respawn" disesuaikan ke kontrak baru (no tab + empty state).
- `terminal_layout.test.js` (≈399): test "opening a tab clears hint" diperluas — tutup ke tab terakhir justru MENAMPILKAN empty hint.

## 5. Gate Verifikasi (PM mandiri)
```
RUN v2.1.9 ... 6 passed (6)
Tests  171 passed (171)   Duration 5.86s
```
Per berkas: layout 28, reconnect 26, toolbar 63, swipe 18, exit 20, discard 16 — **0 gagal**.

## 6. Lingkup & Kepatuhan
- **7 berkas berubah** (setelah koreksi cache-buster §8): `index.html`, `terminal.js`, `styles.css` + 4 berkas test. Semua `src/frontend/**` / `tests/frontend/**` — nol backend, nol file di root, nol hex baru.
- i18n: pakai key ADA (`term.reconnecting`, `term.reconnected`, `term.connecting`) — tidak ada key baru.
- Reconnect/reattach/backoff/liveness TIDAK diubah — hanya cara render status (bug #2) dan cabang tutup tab terakhir (bug #1).

## 7. Sisa Milik User
- **Uji mata di perangkat nyata** (G3): tutup tab terakhir via X → empty state; putus/reconnect saat TUI (vim/htop) jalan → banner muncul lalu hilang tanpa tumpang tindih. (Catatan: browser nyata ada di Termux — bisa di-exercise sendiri jika diinginkan.)
- **Commit / push / PR** (aturan D1: menunggu perintah user; belum di-commit).

## 8. KOREKSI (follow-up hari yang sama) — cache-buster tidak ikut di-bump

**Gejala:** user balik lapor "masih gak nutup terminalnya" padahal 171 test hijau. Ini menegakkan **aturan G3** (aplikasi harus diuji nyata; test hijau ≠ aplikasi jalan).

**Akar:** perubahan `terminal.js` & `styles.css` TIDAK mengubah token `?v=` di `index.html`. Browser serve salinan cached (URL sama → tidak re-fetch), jadi kode lama yang masih punya bug tetap dipakai user.

```
index.html:61    <link rel="stylesheet" href="styles.css?v=20260920" />   ← stale token
index.html:1425  <script src="terminal.js?v=20260907" defer></script>      ← stale token
```

**Celah proses:** `index.html` TIDAK termasuk scope handover fe-dev (cuma `terminal.js`, `styles.css`, 4 test) → PM yang kelewat memasukkan berkas cache-buster ke scope.

**Fix (fe-dev, scope `index.html` saja, satu putaran):**
- `styles.css?v=20260920` → `styles.css?v=20260913`
- `terminal.js?v=20260907`   → `terminal.js?v=20260913`
`git diff index.html` = 2 baris. Aset itu sendiri TIDAK diubah.

**Verifikasi ulang PM:** `node ./node_modules/vitest/vitest.mjs run tests/terminal_exit.test.js tests/terminal_reconnect.test.js tests/terminal_discard.test.js tests/terminal_layout.test.js` → **90 passed / 0 gagal**.

**Langkah user:** **muat ulang (refresh) halaman** — karena `?v=` berubah, browser WAJIB ambil ulang aset → fix kini sampai. Lalu uji nyata (G3).

**Pelajaran proses (dicatat, belum jadi rule baru):** setiap ubah `.js` / `.css` frontend WAJIB ikut ubah token `?v=` di `index.html`. PM wajib memasukkan `index.html` ke scope handover FE ATAU mengecek eksplisit saat integrasi. Guard `tests/i18n.test.js:307-316` hanya memeriksa token cache-buster SEBAGIAN aset — tidak semua — jadi tidak menangkap kelalaian ini.

