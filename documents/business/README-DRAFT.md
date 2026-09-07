# aigate 🚪

One door for every AI provider you use. One playground where AI coding
agents do the typing for you. And the whole thing can run from your phone.

No Docker, no cloud account — aigate is just a plain Python app that lives
on your own laptop or Android device, and your API keys and history stay
right there with it.

## Picture this ☕

You're squeezed into an angkot on the way home, phone out, browser open.
Your side project keeps throwing errors. You type one sentence to your
agent and hit go — a tab comes alive and starts fixing the errors one by
one: run the test, read the failure, patch it, repeat. You just watch it
work while the city goes by. When the last error clears, the fixes land
back on your main branch and the scratch branch quietly disappears. All of
that from a phone, in a browser tab.

## What makes it different ✨

- **One door for all your AI providers.** Connect your provider accounts
  once and aigate routes your requests through them — when one is down or
  out of quota, the request still gets answered instead of failing.
- **24 AI coding tools, one tap.** Launch the popular AI coding assistants
  straight into aigate's built-in terminal tabs. Missing one? It suggests
  an install command that actually works on your device.
- **A self-heal loop you can watch.** Point it at your project's errors:
  it makes a branch, runs an agent in a live tab, fixes warning after
  warning, and merges back when things pass. Nothing hidden — and it never
  pretends a failed run succeeded.
- **It really runs on a phone.** aigate installs and runs natively in
  Termux on Android — no compilers, no build tools, nothing desktop-only.
- **Private by default.** Your API keys and history are local data on
  your device. Nothing talks to the cloud except the AI providers you
  chose yourself.
- **Comfortable to use.** Light and dark themes, seven languages, and a
  UI that behaves on a small screen.

## Try it in 60 seconds ⏱️

```bash
python run.py
```

Open **http://localhost:8080** — the first run grabs the few Python
packages it needs, then starts.

Port busy? Pick another one:

```bash
AIGATE_PORT=9090 python run.py
```

## Runs on your phone 📱

Install Termux on Android, get aigate in there, and start it the same way
as on a laptop. The trickier part of phone life is installing the *coding
tools* themselves — Android resolves packages differently than desktops —
so aigate knows when it's on Termux and suggests the install command that
actually works there, like a system package instead of the desktop one.

Feeling adventurous and want to run a full Linux distro inside your phone
(proot)? It *should* work — same plain Python app — but we haven't tested
that route on a device yet, so treat it as experimental for now.

<!-- TODO-VERIFY: belum dites di proot-distro -->

## Want the technical details? 📚

The API, architecture, setup options, and testing docs all live in the
[wiki](https://github.com/fadhly-permata/AI-Gate/wiki) — this README
stays friendly, the wiki goes deep.

## Status 📌

aigate is a personal, local-first tool under active development. The
gateway, console, and the phone path are the tested core; the proot route
above is the one unverified claim. Try it, break it, and tell me where it
hurts.
