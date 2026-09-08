# aigate 👋

Your own AI gateway — one place to connect, route, and use AI models from lots of
providers, right on your own device.

aigate is free, open source, and built around privacy: it runs locally, so your prompts
and data stay under your control instead of passing through someone else's service.

No account, no sign-up, no phone-home. Download it, run it, own it.

## What you can do with it 🧭

- **Chat and build with the AI you already pay for.** Bring your own API keys.
- **Use one AI when another fails.** aigate switches to a backup automatically.
- **Track what you spend.** See every request and how much it costs you.
- **Plug it into your coding tools.** It speaks the same language as OpenAI's API, so
  the CLIs you already use can talk to it.
- **Work right in your browser.** A real terminal, tabs and all — nothing extra to install.

## Pick your starting point 🚀

| I want to... | Read this |
|--------------|-----------|
| get it running right now | [Quick Start](Quick-Start) |
| use it with Claude Code, opencode, Codex, etc. | [Using aigate with CLI Tools](CLI-Tools) |
| send requests from my own program | [OpenAI-Compatible API](OpenAI-API) |
| understand how it is put together | [Providers and Combos](Providers-and-Combos) |

## How it works, in one paragraph 🧠

aigate sits between you and the AI providers. You register your keys, group them into
*combos*, and point aigate at the combo. aigate then exposes one address on your device
that anything can use — the built-in terminal, your browser, or a coding tool on your
machine.

## Found a problem? 💬

Open an issue on the repo, or drop a suggestion in Discussions.

---

*aigate is maintained by [Fadhly Permata](https://github.com/fadhly-permata).*

<!--
PROVENANCE — not part of the page
Draft v0, ditulis PM 2026-09-08 sebagai CONTOH GAYA (belum di-ACC user, belum dilempar ke specialist).
Status: [!] nunggu review user.
Kalau arah gaya ini disetujui, business-analyst yang bikin versi finalnya.
Lolos R44: nol path `documents/**`, nol path sumber, nol nama tabel, nol nomor ADR.
Yang masih harus dibuktikan sebelum publik: klaim "free" (cek lisensi), "switches to a backup
automatically" (cek perilaku failover), "see every request and how much it costs you" (cek
halaman analytics), "tabs and all" (cek UI terminal).
-->
