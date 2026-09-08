# Quick Start

**Nothing installed → one command → aigate running.** Not sure yet? Skim [Home](Home) first.
I wrote these pages so a spare evening is all you need; if a step feels muddy, tell me — that's a
bug in the page, not in you.

## What you need 🧰

Python 3.10 or newer. That's genuinely it. No GPU, no special laptop, no compiler, no Docker, no
cloud account.

You don't pay us anything — aigate is free and open source. The only thing that might cost money is
the AI provider account *you* use, and some of those have free tiers.

## Get it running ▶️

Clone it, step inside, run:

```bash
git clone https://github.com/fadhly-permata/AI-Gate
cd AI-Gate
python run.py
```

No git? GitHub's archive download works too — unzip and open a terminal in that folder first.

That last line grabs the Python pieces it's missing, then starts. There's no separate install step;
that step doesn't exist. First launch takes a moment.

Then the part everyone misses: **the browser doesn't open itself.** Type
`http://localhost:8080` and the page is just there.

Linux and Windows are identical here. On Windows, the terminal support it needs arrives on that
first run, by itself.

## On your phone 📱

Install Termux, then run the exact same command as on a laptop. Tested on real phones, including a
full Linux distro on one.

One heads-up: the fiddly part on a phone isn't aigate, it's your coding tool. Android handles
packages differently, so aigate notices it's in Termux and offers the install command that actually
matches your device. [CLI Tools](CLI-Tools) covers that.

## Port busy? Sharing a network? 🔌

If something already holds 8080, pick another port:

```bash
AIGATE_PORT=9090 python run.py
```

On Windows, set it first: `$env:AIGATE_PORT = "9090"` in PowerShell, `set AIGATE_PORT=9090` in the
old command prompt.

A quiet warning: aigate answers anyone on the same network — that's how your other devices reach it.
So don't leave it running at a café or an airport.

## Your first three minutes ✨

1. Open `http://localhost:8080` in your browser.
2. Add the key or account of a provider you already have — [here's where](Configuration-and-Keys).
3. Choose that provider as the one to use.

Only then do the terminal, the coding tools, and the API come alive.

## When something goes wrong 🧯

- **A wall of unfamiliar text before anything starts?** Your Python is older than 3.10. One line
  tells you: `python --version` (on Windows, `py --version`). Install a newer Python, run again.
- **Browser stayed empty?** It never opens itself — type the address above.
- **Address refused, or a port error?** Use another port; the command is above.
- **Page loads but nothing answers?** You likely stopped before step 2 or 3 — a key added *and* a
  provider chosen. Still stuck, run it with the developer window and extra helpers:

```bash
AIGATE_DEV=1 python run.py
```

---

Made with ❤️ by Fadhly Permata
