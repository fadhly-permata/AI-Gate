# Memory Bank

## Project brief
(empty — diisi PM saat task pertama)

## Decisions
- 2026-09-03: Arsitektur agen PM + sub-agent spesialis (on-demand, scoped).

## Decisions
- 2026-09-10 (preferensi label PR): user minta SETIAP PR dikasih label (contoh "bug") → rule **R49**. PM auto-klassifikasi pakai label yang UDAH ada di repo (10 default: bug, enhancement, documentation, accessibility, duplicate, invalid, question, wontfix, good first issue, help wanted): `fix`/bug/tes merah → **`bug`**; `feat`/peningkatan UI → **`enhancement`** (+`accessibility` bila relevan); PR dokumen → **`documentation`**; campuran → multi-label. Label BARU (mis. `test`, `chore`) butuh ACC user dulu (API 422 kalau nama baru saat create). PR #15 di-tag **`bug`** (fix harness = defect). Ditanya soal retro-tag PR #14 (sudah merged): user jawab "2 aja" → cuma minta merge #15, jadi #14 TIDAK di-retro-tag.
- 2026-09-07 (merge origin/main → refactor/ui, PR #4): konflik 5 file diselesaiin
  (merge commit `6000b2c`). (a) **Tabrakan rule nomor**: `main` nambah R23=routing, kita
  udah punya R23=reports → routing `main` udah dicakup **R29** kita, duplikat gak
  dimasukkan (no dobel nomor). (b) **Konflik fitur sidebar**: dua cabang bikin grouped-sidebar
  beda desain → **keep desain refactor/ui** (`nav-section`, lebih lengkap), versi `main`
  (`nav-group`) dibuang (redundan, fitur tetap ada). Dua-duanya DILAPORKAN ke user buat
  veto. Verifikasi: 0 marker, backend terminal 65/1skip, frontend 442 pass. PR #4 CLEAN.
- 2026-09-07 (R33 + relokasi Memory Bank): folder `pm/` DIHAPUS dari root → pindah ke
  **`documents/pm/`** (`git mv`, history ke-jejak). Alasan: root repo harus ramping;
  `documents/` = rumah mapan dokumen proyek (R5). 46 referensi `pm/` di 13 file
  (AGENTS.md, README.md, .opencode/agents/ProjectManager.md, .opencode/skills/
  pm-orchestration/SKILL.md, dokumen BACKLOG/TEST_PLAN/SETUP/CODE_CHANGES/BRD/TSD/FSD,
  + file pm itu sendiri) diselaraskan ke `documents/pm/`. src/** & tests/** = 0 referensi.
  Rule **R33** ditulis: dilarang bikin file/folder baru di root; artefak baru masuk folder
  per peruntukan; belum ada tempat → tanya user dulu.
- 2026-09-07 (R30): Kata "terminal" = fitur terminal aigate (multi-tab xterm + PTY WS),
  BUKAN terminal OS/emulator. Investigasi repo dulu sebelum jawab pertanyaan fitur.
- 2026-09-06 (i18n label policy): Label UI TIDAK boleh berupa string gabungan bilingual
  ("Kombo/Combos"). Satu key = satu nilai per locale. **Locale baru** cukup 3 hal, tanpa
  ubah kode: (1) blok kamus `window.I18N.<code>`, (2) entri registry `window.LANGS`
  `{code, flag, nameKey}` + key `lang.<code>`, (3) lengkapi key yang dipakai dinamis
  (mis. `combobox.group_combos`) — kelengkapan ini DIPAKSA oleh parity-guard test di
  `src/frontend/tests/`. Grup yang di-pin (`groupOrder`) selalu di-resolve ulang tiap
  fetch, jadi header ikut locale otomatis.
- 2026-09-06 (R29): SEMUA request user routing lewat PM; main thread dilarang
  implementasi. Kalau terlanjur dikerjakan di luar PM → PM audit diff, accept/re-work,
  delegasi re-work ke pemilik scope, baru catat + commit.

## Progress
- 2026-09-09: **Harness tes FE dibenerin — 22 fail `localStorage` (mask Node≥22.4) — SELESAI (fe-dev, DI-COMMIT `95d46e4`, PR #15 open).** Isu #3 sesi bottom-nav. Akar (dikoreksi fe-dev; hipotesis awal PM `jsdom.url` GUGUR — vitest udah default url localhost:3000): **Node v26 punya global `localStorage`/`sessionStorage` webstorage sendiri** (getter `undefined` tanpa `--localstorage-file`); vitest 2.1.9 gak nyalin storage jsdom ke global krn namanya udah ada + gak masuk KEYS allow-list → tes lihat stub Node; `sessionStorage` Node jalan jadi cuma 22 (localStorage) kena. Fix (harness doang `src/frontend/**`): setupFile baru `tests/helpers/jsdom-storage.js` (re-point globalThis → storage window jsdom, guarded/configurable) + prepend di `vitest.config.js`. 0 tes dihapus/dilemahkan, 0 kode produksi, package.json tetap, isolate:false+maxForks:2 utuh. **GATE PM: `vitest run` 523 pass / 0 fail** (dulu 22 fail). PR #15 `fix/fe-test-env -> main` (base main pasca-merge #14). CAVEAT: bergantung `globalThis.jsdom` (dijaga) → re-run gate tiap Node/vitest/isolate berubah. Detail: CODE_CHANGES.md 2026-09-09 + `documents/pm/handover-20260909-fe-test-env.md`.
- 2026-09-09: **Bottom-nav ponsel dirapikan (hamburger-ilang + scroll + mirror 9 view + Repo + separator grup) — SELESAI (fe-dev, 3 iterasi; DI-COMMIT 6fb210b + docs 26b087d, pushed, PR #14 MERGED (a1777f1).** User lapor beruntun: (1) hamburger hide/show nge-bug di potret → ilangin; (2) menu bawah gak bisa diakses banyak → "masih gak bisa digeser / ada item di-hidden?"; (3) "tambahin link Repo + separator tiap grup". Temuan kunci: `.bottom-nav` dulu cuma 7 dari 9 view menu samping (usage+analytics gak pernah ke-render), BUKAN masalah scroll doang. Fix final (`src/frontend/**`): `#sidebarToggle{display:none}` dua shell phone; `.bottom-nav` `overflow-x:auto`+`justify-content:flex-start`+momentum; `.bn-item` `min-width:60px`; bottom-nav sekarang 9 app-view (urut spt sidebar) + 1 link Repo (no data-view → link eksternal asli) = 10 item + 4 `<span class="bn-sep">` di batas grup (Gateway|Operasi|Wawasan|Sistem|Repo); rule `.bn-sep` token `--panel-border`; cache-buster `styles.css?v=20260914`. Tablet/desktop gak kena (bottom-nav `display:none` di >600px; hamburger utuh). app.js/i18n.js GAK diubah (wiring generik + key udah ada). Verifikasi PM: `views.test.js` **25 pass** (paritas 9-view + repo-hadir + sep=4 + scroll=10 + hamburger-hidden), `git diff --check` bersih. ⚠️ **Scroll browser-asli UNVERIFIED** (no browser; jsdom gak ngukur layout) → user WAJIB tes manual di HP (R20). **TASK SUSULAN (terbuka):** suite FE penuh merah 22 fail `localStorage`/`sessionStorage` (logwindow+terminal_discard) = PRE-EXISTING/LINGKUNGAN (dibuktikan via git stash; npm ci vitest2.1.9+jsdom25.0.1), BUKAN efek perubahan → perlu qa/fe-dev benerin env tes. Detail per-file: `documents/dev/CODE_CHANGES.md` 2026-09-09 (+lanjutan).
- 2026-09-09: **CLI Compat catalog + `cli tools` view — DONE (branch `setup/cli-tools`).** Katalog kompatibilitas per-tool × per-platform (24 tool) di `src/backend/cli_compat.py` (`CLI_COMPAT`); endpoint `GET /api/cli-tools` kini balik `current_platform` + `compat` per tool; frontend `clitools.js` render 4 badge platform (sorot platform saat ini) + warning merah bila status ∈ {broken, no_install, not_a_cli, not_wired}. Mirror `documents/pm/cli-tools-compatibility.md`. Verifikasi: py_compile + `list_cli_tools()` end-to-end (`current_platform=termux`, claude termux=`broken`) + i18n parity 7 locale hijau. Stretch print-di-script di-skip. Belum di-push (user test Windows/Linux).
- 2026-09-09: **Anthropic `/v1/messages` inbound — DONE + DI-COMMIT + DI-MERGE KE `setup/cli-tools` (5 commit `253aae5`/`bb3b6c9`/`7f330a1`/`4986adc`/`41d24f8`, branch `feat/anthropic-inbound`).** aigate serve Anthropic-compatible `POST /v1/messages` **native** (tanpa litellm) supaya `claude-code` pakai `ANTHROPIC_BASE_URL=<aigate>/v1/messages`. Keputusan (dari `documents/architecture/anthropic-inbound-endpoint.md`): bare model id → `resolve_target` (reuse `_resolve_bare_model`, no static map); Stage 1 **non-streaming** (`stream:true`→400 `anthropic_streaming_unsupported`); **tools passthrough** (Anthropic↔OpenAI, bukan 400; extended-thinking/`cache_control` = future phase); auth terima **`Bearer` ATAU `x-api-key`** (terbuka spt chat/responses, client `x-api-key` tak diteruskan upstream). Translator baru: `anthropic_messages_request_to_openai_chat` (translator.py:630) + `openai_chat_response_to_anthropic_messages` (translator.py:718) + `AnthropicMessagesRequest` (translator.py:828) + helper inbound + extend `_translate_request_anthropic` (translator.py:183) forward tools. Router: `messages_completions` (router.py:500) + `_handle_anthropic_messages` (router.py:549) + sibling `/v1/messages/count_tokens` (router.py:658) + `/api/event_logging/batch` stub (router.py:696). `cli_presets` claude flip `LAUNCH_UNSUPPORTED`→`LAUNCH_VERIFIED` (cli_presets.py:171). `claude.sh` SUDAH di-rewire ke aigate (tanpa litellm). **QA LULUS** (`.opencode/reports/qa_anthropic_inbound_verification.md`): py_compile bersih, 11/11 pure test passed, 0 regression translator (17/17), R25 LULUS, R12 LULUS (0 `except:pass`). 9 route-level test gagal eksekusi murni env mismatch `httpx 0.28.1` vs `starlette 0.27.0` (pre-existing, BUKAN regression). Open: selaraskan `httpx<0.28` di `pyproject.toml` lalu jalanin `pytest tests/backend/test_anthropic_messages.py` di env user (R20) — belum dikerjakan.
  **MERGE:** 2026-09-09, `feat/anthropic-inbound` di-FF-merge ke `setup/cli-tools` (sekarang di `97e5557`). Fitur tidak lagi di branch terpisah. `feat/anthropic-inbound` dibiarkan apa adanya (jangan hapus tanpa instruksi). Tidak di-push/PR.
- 2026-09-08: **i18n 7 bahasa — DONE di branch `feat/i18n-locales` (`f7beaf9` + `c1477eb`).**
  User minta Rusia/Belanda/Jepang/Cina, pilih **opsi B = satu file per bahasa**, dan Cina
  **kedua varian** (zh Simplified + zh-tw Traditional). Hasil: `i18n.js` jadi registry+loader
  (793→150 baris), kamus pindah ke `static/i18n/{en,id}.js` (pindah murni, 379 kunci),
  +5 kamus baru (ru/nl/ja/zh/zh-tw, 379 kunci masing-masing), preloader `<head>` cuma
  meng-load EN + bahasa aktif, dropdown bahasa dibangun dari `window.LANGS`, parity guard
  jadi glob. **Pola delegasi: 1 task refactor (file bersama) → lalu 5 task PARALEL,
  masing-masing cuma nulis 1 file kamus** (nol tabrakan scope + hemat waktu). Gate PM:
  vitest **519 passed, 10.60s**; checker cepat
  `.opencode/tools/tests/i18n-parity-check.mjs <kode>` dipakai agen biar gak pada nyalain
  vitest barengan di HP. Backend gak perlu diubah (setting `locale` tanpa allowlist;
  StaticFiles sudah menyajikan subdirektori). **Terjemahan belum ditinjau penutur asli.**
- 2026-09-07 (malam): **Suite tes FE 1,5x lebih cepat — DONE (`618f7d7`, fe-dev).**
  Akar TERNAKTA bukan parse HTML doang: Termux lapor `os.cpus().length===0` → vitest
  fallback **8 fork** di HP ter-throttle. Kurva nyata: 1 fork 12.6s · **2 fork 8.3s** ·
  4 fork 10.4s · 8 fork 12.2s. Fix: `tests/helpers/dom.js` (parse `index.html` sekali per
  worker), `tests/helpers/quiet.js` sbg `setupFiles` (stop poller log/usage tiap tes —
  menutup flake yang muncul begitu fork dinaikkan), `maxForks:2`. Gate PM: **484 passed,
  13.86s** (saat throttle; 8.27s saat tidak) — collect 24.07→6.82s, environment
  28.63→5.61s, tests 23.82→9.71s. Artefak throwaway `tests_orig/` + `vitest.orig.config.js`
  dibuang. Open: guard `typeof fetch` di `app.js:1792` selalu lolos → poller nyala saat tes.
- 2026-09-07 (malam): **Sidebar + tautan Repository sticky — DONE (`86a5ef1`, belum masuk `main`).**
  User minta link repo (`https://github.com/fadhly-permata/AI-Gate`) nempel di dasar menu
  samping. FE-only: `.sidebar-footer` di luar `<nav>` (jaga rule `.nav-section:last-child`),
  `app.js` skip item tanpa `data-view` (kalau tidak, klik luar di-block), `.sidebar` jadi
  flex column + footer `sticky;bottom:0`+`margin-top:auto`, i18n `nav.repo` EN/ID,
  cache-buster `v=20260912`, +8 tes `views.test.js`. Gate PM: vitest **484 passed, 14.66s**.
  **PR #5 sudah MERGED (`0e290ae`) tapi keburu sebelum commit ini** -> 1 commit ini butuh PR
  susulan. PELAJARAN PROSES: user protes lama ("buset, lama amat") -> handover PM kepanjangan;
  spawn pertama dibatalin user, spawn kedua ~20 baris dan langsung kelar.
- 2026-09-07 (sesi ini, akhir): **BERES-BERES — semua kerjaan numpuk di-commit rapi + suite hijau.**
  (1) **Fitur cleanup log** (BE T1 + FE T2, handover `documents/pm/handover-20260907-logs-{be,fe}.md`):
  `DELETE /api/logs` (severity/before, wipe-all wajib `confirm=all`), retensi startup
  `log_retention_days` (default 7, fallback aman), kolom `LogEntry.resolved` + migrasi aditif,
  GET sembunyi resolved kecuali `show_resolved=true`, resolve tunggal+bulk, self-heal
  `current_issue()/_count_remaining()` skip baris resolved. FE: tombol Clear + modal pemilih
  lingkup, toggle Show resolved (localStorage), baris resolved redup+badge, tombol resolve
  per-baris (warning|error saja), Resolve-all (filtered), i18n EN/ID, **cache-buster
  styles.css/app.js/combobox.js/i18n.js/selfheal.js → v=20260911** (gap yang ketemu PM:
  aset berubah tapi tanpa `?v=` = jebakan cache terminal.js). DEVIASI tercatat: wipe-all
  tanpa confirm → 200 `{deleted:0,error}` (bukan 400); id tak dikenal → `{resolved:0}`
  (bukan 404); FE pakai modal, bukan `window.confirm` (lebih bagus, konsisten app).
  (2) **Self-heal** (pemilih CLI/model, combobox grouped, gerbang false-done, kualifikasi
  model) = kerjaan sesi-sesi sebelumnya yang baru di-commit. (3) **Kecepatan tes FE**:
  `vitest.config.js` `isolate:false` + `vi.resetModules()` di `terminal_exit.test.js`
  → 32-34s jadi **23.3s** (476 pass). Akar: jsdom dibangun ulang per file (environment
  84.9s kumulatif) + 1 tes ngandelin cache ref DOM basi — BUKAN bug aplikasi.
  (4) **PR #4 ternyata SUDAH MERGED** (lihat Decisions) → 4 commit + kerjaan sesi ini
  sekarang menunggu PR baru ke `main`. ANGKA FINAL: BE **478 passed/1 skip**,
  FE **476 passed (23 file)**. Item yang user TOLAK kerjakan: verifikasi flag `--model`
  per CLI lain (tetap open item).
- 2026-09-07: **PR #4 `refactor/ui` → `main` = MERGED 2026-09-06T21:30:12Z** (merge commit
  `b278afe`, 59 file, +4574/−722, 14 commit + 1 merge). Catatan lama di Memory Bank
  ("belum merge") SUDAH TIDAK berlaku. Laporan detail perubahan:
  `.opencode/reports/20260907/review/1934_pr4-change-detail.md` (dibuat `qa-engineer`).
  KOREKSI buat PM: angka "73 file via `origin/main...origin/refactor/ui`" basi — setelah
  merge diff itu cuma menyisakan 4 commit pasca-merge (24 file). Temuan QA: **4 commit di
  `refactor/ui` belum masuk `main`** (`a17264c`, `0523a05`, `68cc1bd`, `1bc8fda`) dan
  **tidak ada PR terbuka** → butuh PR susulan. Klaim "duplikat rule R23→R29" tidak
  terkonfirmasi (nomor R1…R33 rapi, tanpa duplikat). Deviasi kualitas: rule **R24**
  disisipkan di dalam commit fitur UI `38e3743` (langgar atomicity/R22) — dicatat, tidak dibongkar.
- 2026-09-07 (now): **BUGFIX Self-Heal false-done (issue-64) — SELESAI (PM proxy be-dev, uncommitted).** User lapor heal "sukses" tapi tidak ada yang diproses. Root cause (terverifikasi): `build_heal_command` manggil TUI default `opencode --model hy3 --prompt ...` (bukan `opencode run`; `run` gak punya `--prompt`, `-m` minta `provider/model`), separator `;` bikin `touch .done` jalan walau CLI gagal (false done), dan `hy3` mentah ambigu (`aigate/hy3` vs `bai/hy3` — dari setting `self_heal_model`, value combobox = `model_id` mentah DB). Fix (scope be-dev saja): (1) opencode -> `opencode run[-m <qualified>] "$(cat file)"`; (2) gate `&& { touch done; echo } || touch failed` + `wait_for_done(failedfile=)` return False seketika; (3) `qualify_opencode_model()` via `opencode models` (unique->pakai; ambigu->prefer `aigate/`; none->omit flag + warning; fail-open). CLI lain tetap bentuk lama (unverified) tapi dapat gating. Verifikasi: pytest backend **458 passed/1 skip** (+7 test baru) + dry-run live shim exit 0/1 (`.done` gak muncul saat gagal ✓). Rule baru **R34**. DEVIASI: sesi ini TIDAK ada Task tool -> PM tidak bisa spawn be-dev; implementasi PM kerjakan sendiri strictly di write scope be-dev (dicatat di status.md). PENDING user: restart aigate (R32); setting lama `self_heal_model='hy3'` sekarang otomatis ter-kualifikasi ke `aigate/hy3` saat run.
- 2026-09-07 (now): **Self-Heal model list -> group by provider + combo — SELESAI (paralel BE→FE).** User mau grup kayak dialog CLI Tools. be-dev: `list_self_heal_models()` balikin dict `{value,label,group}` (provider=provider.name, combo=sentinel `__combos__`); endpoint `/api/self-heal/models` -> dict. fe-dev: model combo `groupBy:group, subGroupBy:prefix, startExpanded` + pin grup Kombo di atas (lokal "Kombo"/"Combos"); sentinel `__combos__` di-map ke localized. cache-buster `selfheal.js?v=20260910`. Verifikasi PM: BE **451 passed/1 skip**, FE **459 passed (23 file)**. PENDING: restart + hard-refresh (R32). BELUM di-commit.
- 2026-09-07 (now): **Self-Heal dropdown -> searchable + grouped combobox (match CLI Tools dialog) — SELESAI (fe-dev).** User nyinyir dropdown self-heal cuma native `<select>` (gak search/group) padahal app standar pakai `createCombobox`. fe-dev ganti `selfHealCli`/`selfHealModel` ke `window.aigate.createCombobox`: CLI `searchInside:true, groupBy:none`; model `searchInside:true, groupBy:prefix, startExpanded:true` (family grouping, tanpa BE change). Default "Auto"/"No model" = value "". `combobox.js` di-tweak render opsi tanpa grup + opt `startExpanded`. cache-buster `selfheal.js?v=20260909`. Verifikasi PM: vitest penuh **459 passed (23 file)**. PENDING: restart + hard-refresh (R32). BELUM di-commit.
- 2026-09-07 (now): **Self-Heal: pilihan agentic-CLI + model + live preview — SELESAI (paralel BE→FE, uncommitted).** User mau pilih CLI & model buat self-heal + lihat preview proses jalan (hipotesis: stuck gara2 tool/model). BE (be-dev): `list_agentic_clis()` + `list_self_heal_models()` (dari `provider_models`), setting `self_heal_cli`/`self_heal_model`, `run_self_heal(cli,model,...)` + `build_heal_command` append `--model` via `CLI_MODEL_FLAGS` (hanya CLI dikenal), state `progress` kaya (phase/cli/model/branch/iteration/current_issue_id/started_at/remaining) di `heal_status()`. Router: `GET /api/self-heal/clis`, `GET /api/self-heal/models`, `POST /api/self-heal/run` terima `{cli,model}`, `GET /api/self-heal/status` +`progress`. FE (fe-dev): dropdown CLI + model (default Auto/No-model), panel preview (progress poll 2.5s + log feed stream dari `/api/logs` filter `source` `backend.selfheal`), i18n +22 key (EN/ID, parity guard lolos), cache-buster `selfheal.js?v=20260908`. Verifikasi PM: **BE 451 passed/1 skip, FE 458 passed (23 file)**, 0 regresi. PENDING: user restart aigate (R32) + hard-refresh. Open: flag `--model` per-CLI lain (claude/opencode/aider sudah `--model`; codex/gemini/goose/amp/qwen/cline/kilo belum diverifikasi ke CLI asli — map bisa dikoreksi).
- 2026-09-07: **Self-Heal progress terlihat — SELESAI (sekuensial BE→FE, uncommitted).**
  Root cause: POST /api/self-heal/run sinkron + CLI via subprocess tersembunyi.
  Fix BE (be-dev): CLI jalan di PTY key `self-heal` (command diketik, prompt file
  temp anti-injection, donefile poll, timeout 1800s/issue, abort bila tab mati);
  run async (start_self_heal, 409 already_running) + GET /api/self-heal/status
  {running, last}. Fix FE (fe-dev): klik Run → buka+fokus tab "Self-Heal" +
  polling 5s; i18n +2 key. PM: cache-buster v=20260907 (selfheal/terminal/i18n),
  docs FSD/TSD/BRD sinkron, CODE_CHANGES.md. Verifikasi PM: **BE 438 passed/
  1 skipped, FE 453 passed (23 files)**. PENDING: user restart aigate + hard-refresh
  (R32); belum commit (menunggu approve). Open: FE poll max-age cutoff (opsional).
- 2026-09-07: **Request Log kolom Model/Endpoint kosong — SELESAI + DI-COMMIT
  `a17264c` + PUSH `origin/refactor/ui`.** Root cause: combo ref → resolver `upstream_model=""` →
  router nimpa `ctx["model"]` jadi `''` (RequestLog.model kosong utk semua request
  combo); Endpoint kosong = by-design (model-based, tanpa header
  `X-Aigate-Endpoint`). Fix: BE `_upgrade_ctx_model` helper (6 situs, upgrade
  hanya bila non-empty; combo → prefer model member dari envelope upstream,
  fallback combo ref) + DTO `endpoint_name` (Pydantic v1); FE `orDash`/
  `reqlogEndpoint` (nama → id → "—") + cache-buster `analytics.js?v=20260906`
  (pola precedent terminal.js, PM-owned 1 baris). Verifikasi PM: **BE 423 passed/
  1 skipped, FE 445 passed (23 files)**. Baris lama `model=''` tidak di-backfill.
  PENDING: user restart aigate (R32) + hard-refresh. Detail:
  `documents/dev/CODE_CHANGES.md` 2026-09-07.
- 2026-09-07: **Terminal tab auto-close on shell exit — SELESAI (uncommitted, mode
  sekuensial BE→FE).** Kontrak exit (sumber kebenaran): server kirim TEXT frame
  `{"type":"exit","code":<int>}` (code = exit status; -1 bila tak terbaca) ke view
  attached, LALU tutup WS (1000). Frame TIDAK masuk ring-buffer replay. FE tangkep →
  `closeTab(id,{exited:true})` (tanpa kill-frame, tanpa auto-open → empty state,
  forget saved id). BE: `pty.py` +`exit_status`; `session.py` `PtyExit` sentinel +
  `notify_exit()`/`resolved_exit_code()`/`read_exit_code()`/`close_view()` + reaper
  reap exited-walau-attached; `router.py` `_pump` → `exit_frame()` (json.dumps) lalu
  close 1000. TEST ASLI (PM re-run): backend terminal **64 passed, 1 skipped**
  (skip=test_terminal.py:59 native PTY dep); FE terminal_exit **14 passed**; FE full
  **436 passed (23 files)**, no regresi. Catatan env: `ruff` tak terpasang (lint gate
  tak jalan); vitest harus dipanggil via `node node_modules/.bin/vitest` (shebang env
  Termux rusak). AKAR MASALAH SESUNGGUHNYA (temuan akhir): tab gak nutup karena
  **`terminal.js` ke-cache browser tanpa cache-buster** — kode FE beneran gak ke-load
  versi baru. BE **terbukti benar via runtime** (frame exit + close 1000 terkirim).
  RESOLUSI FINAL: FE hardened (exit frame + close(1000) → tutup tab) + **toast
  `term.session_ended` (id+en)** + **cache-buster `?v=20260906` di index.html**.
  ANGKA FINAL (PM re-run): FE **442 passed**, BE **65 passed / 1 skipped**.
  **DI-COMMIT `a06ef9b` + PUSH `origin/refactor/ui`. PR #4 `refactor/ui`→`main`:**
  https://github.com/fadhly-permata/AI-Gate/pull/4 (belum merge; scope PR lebar =
  11 commit/49 file, terminal + seluruh UI-refactor branch — sudah dicatat di body). RULE BARU **R32**: dilarang nyuruh sub-agent kill/restart proses aigate
  (sesi opencode hidup DI DALAM aigate = bunuh diri); bukti kode lama aktif cukup
  bandingkan start-time vs mtime + laporkan, user yang restart.
- 2026-09-07: **Terminal tab auto-close on shell exit** — investigasi PM (read-only).
  Temuan: fitur ini SUDAH di-spec TSD §3.2 (frame `{"type":"exit","code":N}` + langkah
  "saat shell keluar, kirim kontrol exit, tutup WS") tapi BELUM diimplementasi.
  Gap: (BE) `session.py:353-356` reader thread cuma set `exited=True` + log, TIDAK
  notify client; `try_reap` skip session yang masih `attached` (`session.py:290-291`)
  → shell exit = tab nyangkut (zombie view). (FE) `terminal.js:374-387` `handleWsMessage`
  buang SEMUA control frame non-ping → gak ada jalur "exit". Perlu task be-dev + fe-dev.
- 2026-09-06: Header grup "Kombo" di model picker CLI Tools kini terlokalisasi penuh
  (EN "Combos" / ID "Kombo") lewat key `combobox.group_combos`; literal bilingual
  dihapus dari kode produksi; `combobox.js` dapat `setGroupOrder()` supaya grup yang
  di-pin ikut locale (controller dibuat lazy + di-cache, jadi pin lama bisa basi).
  Dikerjakan inline oleh main thread (PELANGGARAN → R29), lalu diaudit PM (diterima
  fungsional) dan di-hardening oleh `fe-dev` (parity guard + test re-pin + pembersihan
  fixture) dengan gate `qa-engineer`. Suite awal: 422 passed / 22 files.
- 2026-09-06: Label teks tombol utama toolbar terminal dihapus; toolbar kini ikon-only dengan tooltip/ARIA, sedangkan label lengkap tetap di submenu. Vitest 395 passed (21 files).
- 2026-09-06: Toolbar terminal ditata ulang menjadi tiga dropdown berurutan: Paste (normal/code block), Settings (TUI passthrough/Keep Screen On), Full (Full Page/Fullscreen). Wiring, ARIA state, dan test fixture diselaraskan. Vitest 394 passed (21 files).
- 2026-09-06: Tooltip icon-only dibuat transient (tap auto-close 2 detik; Escape/outside/scroll/resize tetap menutup). State Full Page dan true Fullscreen dipisah eksplisit; hanya mode aktif yang biru, caret tidak aktif. Vitest 394 passed (21 files), terminal toolbar 62 passed.
- 2026-09-06: Terminal Keep Screen On dikembalikan dengan ikon perangkat yang lebih jelas (`fa-mobile-screen-button`). Popover tooltip global ditambahkan untuk kontrol ikon-only; mendukung hover, focus, tap, Escape, outside click, dan kontrol dinamis. Frontend Vitest 392 passed.
- 2026-09-06: Side menu dikelompokkan berdasarkan kebutuhan pengguna: Gateway Setup, Operations, Insights, System. EN/ID, aksesibilitas, dan test frontend diperbarui; Vitest 392 passed.
- 2026-09-09: **CLI Tools install scripts — progress 21/24 (A1 claude + A2 opencode + A3 gemini + A4 codex + A5 antigravity + A6 phi + A7 aider + A8 goose + A9 amp + A10 qwen + A11 cline + A12 kilo + B1 openhands done + B2 swe-agent done (NO_INSTALL) + B3 open-interpreter done (OpenAI-compatible, verified, `LAUNCH_VERIFIED` cli_presets.py:196, commit `31b9a04`) + B4 autogpt done (NO_INSTALL, pesan+exit, commit `a5d1a91`) + C1 llm done (OpenAI-compatible, verified, `LAUNCH_VERIFIED` cli_presets.py:219, `pip install llm` + wiring `llm openai endpoint ... --chat/--models`, commit ini)). **GRUP A SELESAI (12/12); B1 openhands = done (OpenAI-compatible, verified, `LAUNCH_VERIFIED` cli_presets.py:190).** Lanjut Grup B (B4..B6) + Grup C (C2..C6).** Branch `setup/cli-tools`. A8 (`goose.sh`) commit `414ea06`: **NO_INSTALL** — script HANYA pesan `goose: NO_INSTALL — belum ada install terverifikasi di environment ini.` + `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:77` (`install: NO_INSTALL`) + `cli_presets.py:178` (`LAUNCH_UNSUPPORTED`/`REASON_NO_BINARY`); `TERMUX_INSTALL` tidak punya entry goose; cross-check 5 sumber (npm `goose`=Golang tak terkait, `@block/goose` 404, PyPI `goose`=SQL migration, Homebrew `goose`=pressly/goose migrasi DB, install resmi Block curl script tak punya build aarch64-android/termux terverifikasi) → TIDAK ada install terverifikasi. **A9 (`amp.sh`) commit `446f78f`: NO_INSTALL — script HANYA pesan `amp: NO_INSTALL — belum ada install terverifikasi di environment ini.` + `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:78` (`install: NO_INSTALL`) + `cli_presets.py:179` (`LAUNCH_UNSUPPORTED`/`REASON_NO_BINARY`); `TERMUX_INSTALL` tidak punya entry amp; cross-check 5 sumber (npm unscoped `amp`=library messaging tak terkait tjholowaychuk/node-amp, `@ampcode/cli` ADA tapi optional deps HANYA darwin/linux/win32 — gak ada build android/termux, PyPI `AMP`=parser matematika, Homebrew `amp`=text editor terminal amp.rs) → TIDAK ada install terverifikasi. A1 (`claude.sh`) + `_common.sh` sudah commit sebelumnya. A7 (`aider.sh`) commit `5a960e7`: install `python3 -m pip install aider-chat` (mirror `cli_presets.py:76`), wiring `OPENAI_API_BASE`+`OPENAI_API_KEY` + flags `--openai-api-base`/`--openai-api-key` ke aigate `/v1/chat/completions`, model `--model openai/<m>`; fakta `cli_presets.py:172` (`LAUNCH_VERIFIED`) + `cli_tools_router.py:355-369` (`_aider_builder`). A2 (`opencode.sh`, 122 baris) commit `f8d9f0b`: install `npm i -g opencode-ai`, wiring `OPENAI_API_BASE`+`OPENAI_API_KEY` ke aigate `/v1/chat/completions`, generate `opencode.json` di CWD. A3 (`gemini.sh`, 114 baris) native Google mode: install `npm i -g @google/gemini-cli`, launch langsung dengan kredensial Google (GEMINI_API_KEY/GOOGLE_API_KEY/OAuth) — TIDAK di-wire aigate karena `cli_presets.py:175` mark gemini `LAUNCH_UNSUPPORTED`/`REASON_GEMINI_ONLY` (aigate hanya serve OpenAI `/v1/chat/completions` + Anthropic `/v1/messages`, no Google generateContent inbound). A4 (`codex.sh`, 136 baris) commit `7f22713`: native OpenAI mode, TIDAK di-wire aigate karena `cli_presets.py:180` mark codex `LAUNCH_UNSUPPORTED`/`REASON_RESPONSES_ONLY` (aigate `/v1/responses` non-streaming only, `responses.py:227-233`; codex CLI wajib streaming). A5 (`antigravity.sh`, 69 baris) commit `2259c1c`: **NO_INSTALL** — script HANYA pesan `antigravity: NO_INSTALL — tidak ada paket CLI terverifikasi` + `exit 0`, TIDAK memasang apa pun (no side-effect). Bukti `cli_presets.py:74` (`install: NO_INSTALL`) + `cli_presets.py:176` (`LAUNCH_UNSUPPORTED`/`REASON_NOT_A_CLI`); `TERMUX_INSTALL` tidak punya entry antigravity; npm/pip/brew tidak ada rute resmi. Install: Termux `pkg install codex` (`cli_presets.py:243`) / non-Termux `npm i -g @openai/codex`. Known caveat: Termux npm `os` field tanpa `"android"`. Sisa 19 tool menyusul.
- Inisialisasi PM agent + rules + skills selesai.
- 2026-09-03: Enhance PRD terminal — floating control, scroll/swipe natural,
  grouping CLI tools (agentic-first, 3 grup).
- 2026-09-03: Sequential doc creation SELESAI — BRD (documents/business/BRD.md),
  FSD+ERD (documents/analysis/FSD.md, ERD.md), TSD (documents/architecture/TSD.md).
  Spesialis business-analyst, system-analyst, tech-architect + skill-nya
  di-generate on-demand (belum terdaftar di sesi; pakai 'general' stand-in).
  Semua dokumen di `documents/` (R5).
- 2026-09-03: Execution docs SELESAI (mode sekuensial) — #1 Backlog
  (documents/plan/BACKLOG.md), #3 API Contract (documents/api/), #4 Test Plan
  (documents/qa/), #5 Dev Setup (documents/dev/), #6 Terminal UX (documents/ux/),
  #7 CLI Config Schema (documents/config/). ADR-007 & ADR-008 resolved.

- 2026-09-03: PRD diselaraskan ke 9router (R17 capture). Fitur adopsi baru (token
  saver, pelacak kuota, penerjemah format, multi-akun, OAuth refresh, export/import
  lokal) SUDAH di PRD tapi BELUM di BACKLOG & BELUM diimplementasi. Perlu backlog
  baru + /run-impl.

- 2026-09-05/06: CLI tool launcher — audit SEMUA 24 preset, satu per satu,
  1 tool = 1 commit, delegasi ke `be-dev` (R21). Hasil: **11 verified**
  (aider, opencode, aichat, qwen, cline, kilo, llm, gptme, open-interpreter,
  oterm, openhands), **13 unsupported** beralasan (claude/gemini = format
  bukan-OpenAI; codex = butuh /v1/responses; antigravity/gpt-researcher/crewai
  = bukan CLI launchable; goose/amp/mods/aichat-ish/sgpt = gak ada paket
  platform ini; phi/swe-agent/autogpt = nama paket gak ketemu), **0 pending**.
  Bug ikutan ketemu & dibenerin: install string salah paket (`openhands-ai`
  gak punya console script -> `openhands`; `aider` -> `aider-chat`; npm vs pip),
  preset gak pernah nyampe DB (seed skip) -> jadi upsert, UI nyoret tool yang
  belum verified + `resolve` balas 409 daripada ngarang command.
  Dasar verifikasi dicatat per tool di CLI_CONFIG_SCHEMA: dijalankan langsung
  di perangkat (aider, opencode, aichat) vs dokumen resmi (sisanya — npm/pip
   gak bisa dipasang di Termux, user larang install).
- 2026-09-05: Terminal stay-alive (sesi ini). Task1 env: `~/.bashrc` auto
  `termux-wake-lock` (tanpa install) biar server aigate gak di-freeze Android saat
  layar mati. Task2 (fe-dev, DONE+verif): persist `tab_id` via sessionStorage ->
  terminal survive Chrome tab DISCARD (`terminal.js` +123/-18, test baru
  `terminal_discard.test.js` 16; suite 330 passed). Task3 (fe-dev, DONE+verif):
  toolbar Keep Screen On (wake lock) + dropdown Fullscreen (full page/true FS) +
  dropdown Paste (normal/blok kode) -> 2 spawn ke-interupsi tapi diff mendarat; PM
  review + sisa fe-dev benerin typo regex tes; suite 390 passed (330+60), 0 regresi.
  RULE BARU **R22**: tiap perubahan kode dicatat per-file di
  `documents/dev/CODE_CHANGES.md` (code↔doc align).

- 2026-09-09: **CLI Tools — GRUP B SELESAI (6/6):** B1 openhands (OpenAI-compatible, verified) + B2 swe-agent/B4 autogpt (NO_INSTALL) + B3 open-interpreter (OpenAI-compatible, verified) + B5 gpt-researcher/B6 crewai (NOT_A_CLI). Progres keseluruhan cli-tools **21/24** (C1 llm done + C2 sgpt done + C3 mods done, keduanya NO_INSTALL). Lanjut Grup C (C4 oterm, C5 gptme, C6 aichat).
- 2026-09-09: **aider.sh BUGFIX — version-guard Python 3.10–3.12** (branch `setup/cli-tools`, commit `1d1a31c`): `pip install aider-chat` gagal di device (Python 3.14.6; aider `requires_python ">=3.10,<3.13"` per PyPI 0.86.2). Skrip lama cuma `NOTE` Termux-only post-install (setelah `ensure_installed` → raw pip error). Fix: guard pre-install + `exit 1`; hapus NOTE lama; wiring launch utuh. `bash -n` clean; simulasi guard lulus (3.10/3.11/3.12 lanjut, sisanya exit 1). Catatan: spawn tool sub-agent TIDAK tersedia di sesi ini → PM edit langsung dalam scope `scripts/cli-tools/aider.sh` (deviasi R21, transparan per R29).

- 2026-09-09: **openhands.sh BUGFIX — version-guard Python 3.12** (branch `setup/cli-tools`, commit `313a2c2`): `pip install openhands` (fallback) gagal di device (Python 3.14.6; openhands `requires_python ==3.12.*` per PyPI 1.16.0). Fix: guard pre-install — `have_cmd uv`→lanjut (uv fetch 3.12 sendiri); `elif python3` major.minor !=3.12→ERROR + `exit 1` TANPA install; parse-gagal→WARN. Wiring launch utuh; `bash -n` clean. **crewai.sh & gpt-researcher.sh di-VERIFIKASI = NOT_A_CLI (hanya pesan + `exit 0`, TIDAK ada `pip`/`uv install`) → version-guard TIDAK relevan, TIDAK diubah.** (R14/R35 verified.)

- 2026-09-09: **cli-tools C2 sgpt + C3 mods = done (NO_INSTALL, message + exit 0, no side-effect)** — `scripts/cli-tools/sgpt.sh` + `scripts/cli-tools/mods.sh` di-commit (commit ini). Bukti `cli_presets.py:101`/`cli_presets.py:224` (sgpt: `NO_INSTALL` + `LAUNCH_UNSUPPORTED`/`REASON_INSTALL_UNVERIFIED`) dan `cli_presets.py:102`/`cli_presets.py:225` (mods: `NO_INSTALL` + `LAUNCH_UNSUPPORTED`/`REASON_NO_BINARY`); `TERMUX_INSTALL` tidak punya entry sgpt/mods; registry npm `sgpt`/`mods` = squat tak terkait, PyPI 404, GitHub `tbckr/sgpt` (Rust) & `charmbracelet/mods` (Go) gak build Termux/android-arm64. `bash -n` clean, pesan literal (TIDAK ada backtick/`$()`). Progres keseluruhan cli-tools **21/24**.

- 2026-09-09: **cli-tools C4 oterm = done (OpenAI-compatible, verified)** — `scripts/cli-tools/oterm.sh` di-commit (`aea87c3`). Bukti `cli_presets.py:103` (`pip install oterm`) + `cli_presets.py:222` (`oterm` = `LAUNCH_VERIFIED`) + `cli_tools_router.py:891-917` (`_oterm_builder`: tulis `.oterm-aigate/config.json` blok `openaiCompatible.aigate` {base_url=gateway, api_key="${OPENAI_API_KEY}"}, set `OTERM_DATA_DIR=.oterm-aigate` + env `OPENAI_API_BASE`/`OPENAI_API_KEY` ke `/v1/chat/completions`). PyPI `oterm` 0.24.0 butuh Python >=3.10. Catatan Termux (known-broken, bukan blocker): `pip install oterm` di aarch64/Py3.14 diprediksi gagal build `jiter` (no Android wheel) → script handle hint + `exit 1`. `bash -n` clean; mode exec. Progres keseluruhan cli-tools **22/24**. Lanjut C5 gptme, C6 aichat.
- 2026-09-09: **cli-tools C5 gptme = done (OpenAI-compatible, verified)** — `scripts/cli-tools/gptme.sh` di-commit (`16d36f9`). Bukti `cli_presets.py:104` (`pip install gptme`) + `cli_presets.py:223` (`gptme` = `LAUNCH_VERIFIED`) + `cli_tools_router.py:595-612` (`_gptme_builder`: env `OPENAI_BASE_URL` = gateway base [gptme baca `OPENAI_BASE_URL` BUKAN `OPENAI_API_BASE`] + `OPENAI_API_KEY` + flag `-m local/<model>` ke `/v1/chat/completions`). PyPI `gptme` 0.33.0 butuh Python `>=3.10,<3.15`. Catatan Termux (known-broken, bukan blocker): `pip install gptme` di aarch64/Py3.14 diprediksi gagal build `jiter` (no Android wheel) → script handle hint + `exit 1`. `bash -n` clean; mode exec. Progres keseluruhan cli-tools **23/24**. Sisa: C6 aichat.
- 2026-09-09: **cli-tools C6 aichat = done (OpenAI-compatible, verified)** — `scripts/cli-tools/aichat.sh` di-commit (`1c4e592`). Bukti `cli_presets.py:105` (`cargo install aichat`) + `cli_presets.py:226` (`aichat` = `LAUNCH_VERIFIED`) + `cli_presets.py:242` (`TERMUX_INSTALL["aichat"]="pkg install aichat"`, "verified 0.30.0 runs" di Termux) + `cli_tools_router.py:469-511` (`_aichat_builder`: generate `aichat-aigate.yaml` client `aigate` openai-compatible {api_base=gateway, api_key}, set env `AICHAT_CONFIG_FILE`, model `aigate:<raw>` ke `/v1/chat/completions`). crates.io `aichat` 0.30.0 (Rust). Catatan Termux (terbukti WORKING, bukan blocker): `pkg install aichat` di Termux terbukti jalan (usable di Termux). `bash -n` clean; mode exec. **Progres keseluruhan cli-tools 24/24 (ALL DONE — A1–A12, B1–B6, C1–C6 SELESAI).**

## Decisions
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

## Open risks
- Agent file business-analyst / system-analyst / tech-architect SUDAH dibuat tapi
  belum terdaftar di sesi berjalan; perlu reload opencode agar bisa dipakai sbg
  subagent_type asli (selama ini pakai 'general' stand-in).
- ADR-007 & ADR-008 SUDAH RESOLVED (2026-09-03) — lihat Decisions. Tidak ada
  lagi ADR Proposed yang blokir implementasi.
- **Termux runtime risk:** RESOLVED (2026-09-03) — user pilih opsi (C): pin
  `fastapi>=0.95,<0.100` + `pydantic>=1.10,<2` (Pydantic v1 pure Python, tanpa
  pydantic-core/Rust). Semua dep inti pure Python → aigate jalan di Termux & semua
  platform tanpa compile Rust. Expo/React Native ditolak (bukan pengganti backend
   Python; tak kasih PTY utk CLI). Lihat TSD ADR-002.

## Tooling
- 2026-09-07: **Kecepatan shell (lingkungan, di luar repo).** User komplain semua perintah
  bash lama. Akar: `~/.bashrc` manggil `termux-wake-lock` di SETIAP shell interaktif
  (Termux = tiap panggilan tool bikin shell baru) → **+1,2 detik per perintah**.
  Fix: cache state-file `~/.termux-wake-lock.ts` + refresh maks 1x/6 jam + jalan di
  BACKGROUND. Ukur: `time bash -ic true` **1,452s → 0,047s** (≈25x); fungsi wake lock
  tetap jalan (`termux-wake-lock` exit 0). Rule baru **R37** (jalur tiap-shell wajib bebas
  blocking + ukur dulu) dan **R38** (handover pendek utk task kecil — user juga protes
  soal itu). Laten lain yang diketahui: `npx` shebang rusak (pakai
  `node node_modules/.bin/…`), `os.cpus()=0` → vitest 1 fork, throttling Android bikin
  angka antar-run beda 1,5–2x, dan fungsi `opencode()` di `.bashrc` manggil
  `sync-bai-models.sh` (jaringan) tiap opencode dimulai.
- 2026-09-06: **codegraph = colbymchenry/codegraph (BUKAN xnuinside)**. User rujuk repo
  https://github.com/colbymchenry/codegraph. PM sempat salah pakai xnuinside/codegraph
  (v1.2.0 pip, se-nama) → di-uninstall & diganti yang benar (R27).
- Install (global, BUKAN dep project — R26): `npm i -g @colbymchenry/codegraph`
  (v1.6.0). `codegraph init` di project root → bangun indeks di `.codegraph/`
  (`codegraph.db` 11.3MB). Hasil: **121 files (80 py + 41 js), 2,851 nodes, 9,151
  edges** in 2.0s. `codegraph status` → "Index is up to date".
- **Termux/Android workaround (wajib, env luar repo):** tool ini Rust-kernel + bundled
  Node glibc; di Termux gak ada build `android-arm64` & binary glibc butuh loader yg
  gak ada. 3 patch (lihat CODE_CHANGES.md Environment): (1) force `target='linux-arm64'`
  di shim; (2) shebang shim → node absolut; (3) launcher bundle exec `node` lewat loader
  glibc `/usr/glibc/lib/ld-linux-aarch64.so.1` (loader glibc Termux ada & jalan).
  Tanpa patch `codegraph` gagal total di Termux. Patch di env global / cache bundle —
  hilang kalau npm reinstall / bundle dihapus.
- Catatan: 1 baris error pasca-init `error while loading shared libraries: -e:` (spawn
  daemon auto-sync gagal di Termux) — indeks tetap ke-build utuh & query-able. Auto-sync
  watcher mungkin gak jalan di Termux; rebuild manual via `codegraph init` bila perlu.
- RULE BARU **R28**: baca kode HARUS lewat codegraph dulu (dapet path + line) baru baca
  file yg bersangkutan — hemat token, hindari broad grep/Explore. Reinit via
  `codegraph init` kalau index usang. Berlaku utk PM + semua sub-agent.

## Dokumen wiki — keputusan (2026-09-08)
- Kerja dokumen wiki jalan di **branch `docs/wiki`** (basis `origin/main`) di repo ini.
  BUKAN repo terpisah — user mengoreksi (R39). Wiki GitHub sendiri sudah berupa repo git
  terpisah (`AI-Gate.wiki.git`), jadi file wiki toh gak pernah nyampur sama `src/**`.
- Kendala terverifikasi: fitur Wiki tidak bisa dinyalakan lewat API (`PATCH has_wiki`
  diabaikan GitHub) → perlu 1 klik web UI (Settings → Features → Wikis). **SUDAH dilakukan
  user (2026-09-08)** — wiki hidup di branch `master`, halaman awal `Home.md`. Izin tulis
  diverifikasi lewat `git push --dry-run` (diterima, 0 byte ditulis) → auto-commit siap.
- **BATAS IKAT dari user:** jangan menulis/meng-push apa pun ke wiki sampai izin turun.
  Boleh: baca, clone, probe/dry-run.
- Rencana tooling (belum dikerjakan): script publisher di `.opencode/tools/docs/wiki/`
  (idempoten, wajib ada `--dry-run`), token dari `gh auth token` / `.env` (rule secrets,
  gak di-hardcode), sumber konten = `.md` di branch `docs/wiki` ini; wiki = hasil publikasi.
- Repo `fadhly-permata/AI-Gate-docs` (private) = **artefak salah**, tidak dipakai. User sudah
  perintahkan hapus, tapi **terblokir**: PAT gak punya scope `delete_repo` (HTTP 403).
  Menunggu user hapus lewat web atau menambah scope.

### Konfirmasi maintainer (sumber kebenaran — jangan pasang caveat lagi)
- 2026-09-08, user: **aigate SUDAH DITES di Linux, Windows, dan Android/Termux**, termasuk
  menjalankan distro Linux penuh di dalam HP. Materi publik menulis ini sebagai fakta teruji;
  DILARANG muncul kata "untested/experimental/belum diverifikasi" untuk hal ini (R42).
- Nama produk ditulis **`aigate`** (huruf kecil semua), termasuk judul README.
- README: bahasa **Inggris**, kultur **netral** (tanpa rujukan khas negara/daerah), nada ceria +
  emoji, **tanpa path/nama file** (pengecualian `run.py` di perintah), detail teknis dialihkan ke
  wiki → https://github.com/fadhly-permata/AI-Gate/wiki
- Kalimat penutup README yang di-ACC user: "Try it, break it, and tell me where it hurts."
  + baris kredit terakhir: "Made with ❤️ by Fadhly Permata".

### Fakta wajib soal daftar CLI tool (berlaku README + semua varian + halaman wiki)
- Jumlah preset saat ini **24** (dihitung dari `src/backend/cli_presets.py`: 12 agentic +
  6 autonomous + 6 chat/shell). Sebut angkanya **cukup satu kali** per dokumen.
- **Daftarnya masih dikembangkan** — wajib ditulis sebagai catatan: versi berikutnya bisa
  menambah/mengubah tool (sebagian preset belum punya jalur install di semua platform).
  EN: "The list is still growing — future versions may add or change tools."
  ID: "Daftarnya masih terus dikembangkan — versi berikutnya bisa menambah atau mengubah tool
  yang tersedia."

### Baris bahasa di README (konvensi lintas varian)
- Sumber daftar bahasa = registry aplikasi: `src/frontend/static/i18n.js` (`LANGS`) — 7 kode:
  `en id ru nl ja zh zh-tw` dengan bendera 🇺🇸🇮🇩🇷🇺🇳🇱🇯🇵🇨🇳🇹🇼 dan **endonym** (English,
  Bahasa Indonesia, Русский, Nederlands, 日本語, 简体中文, 繁體中文) yang TIDAK diterjemahkan.
- Setiap file README (root + semua varian) wajib punya 1 baris `🌐 …` tepat setelah intro;
  bahasa dokumen itu sendiri ditebalkan tanpa link.
- Path relatif: dari root → `documents/readme-variants/README.<kode>.md`; antar varian → cukup
  `README.<kode>.md`; dari varian ke root → `../../README.md`.
- Varian yang belum dibuat = link mati → PR jangan di-merge sampai 6 varian ada.

### Peta file kerja wiki (2026-09-08) — baca ini dulu kalau sesi putus
- Rencana + batas konten + pertanyaan terbuka → `documents/pm/wiki-plan.md`
- Task list hidup (W0.x / W1.1–W1.8 / W2.x) → `documents/pm/wiki-backlog.md`
- Draft per halaman (staging, BUKAN wiki asli) → `documents/pm/wiki-drafts/`
- Aturan terikat: **R44** (publik tidak membocorkan `documents/`, sumber fakta = kode/perilaku,
  sekuensial satu-per-satu) + R43 (varian bahasa = tulisan asli) + R39 (branch `docs/wiki`).

### CLI-tools script bugs (2026-09-09) — DONE
- 4 bug nyata di `scripts/cli-tools/` diverifikasi & dibenerin: aichat.sh (`pkg install -y`, `export AICHAT_CONFIG_FILE` + `exec $BIN $@`), codex.sh (`pkg install -y`), oterm.sh (`export OTERM_DATA_DIR` + `exec $BIN $@`). Kelas bug: (a) `pkg install` tanpa `-y` abort di non-interaktif; (b) `exec VAR=val $BIN` → quoted assignment dibaca sebagai command name (exit 127).
- Re-test aichat sukses (EXIT 0). Env Termux read-only `/etc/apt` (hope2333-mirrorlist) blokir install/uninstall via pkg — di luar script.
- Commit: `61d64337b686a8b5ee0f58d17d52807119922d0a`.
