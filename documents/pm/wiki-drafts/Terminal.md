# Terminal ⌨️

**"A terminal, inside a browser tab?"** Healthy skepticism — it sounds like a drawing of one. It's the
real thing: each tab is a live session on the device aigate runs on. What used to need a separate SSH
app is now a tab beside your providers.

## What's on the screen 🎛️

- **Tabs.** Open several; each is its own session.
- **Full screen and split.** Fill the display, or put two sessions side by side.
- **Keep-awake.** Keeps the screen on while you watch something run. (Not a life-support for the session —
  see the last section.)
- **A floating button** in the corner of the terminal area, plus a small menu for rare choices.

## Paste, scroll, swipe 📋

Pasting injects your clipboard into the active session, and focus comes back by itself so you keep
typing. Wheel and trackpad scroll; on a phone, so do fingers. Inside full-screen terminal programs — the
editor-looking ones — a swipe becomes that program's own scroll, natural direction, 1:1 with your finger.
History holds about 5,000 lines.

## Where the coding tools open 🛠️

Every tool launched from the coding-tools screen opens **in a new tab here** — that's the path behind
[CLI Tools](CLI-Tools). With `AIGATE_DEV=1` you also get a log window and developer helpers.

## Self-Heal 🤖

The part people don't believe, stated exactly as it behaves. Point aigate at a project's errors:

1. It makes a **branch**, so your main line stays untouched while it works.
2. It runs a coding agent **in a live tab** — you watch, nothing runs hidden.
3. It fixes warnings and errors **one at a time**, re-running checks and clearing entries that came out
   clean.
4. If everything passes, it **merges into the main line**. It never claims success on a failed run: a
   command that exits badly is marked failed, plainly.

Needs an installed coding agent (your pick) and a project to aim it at. The risk, straight: it writes
real code and merges it — use it where you can read what it did. No promises; your project and agent
decide how far it gets.

## The honest limit 🔌

The browser view and the session behind it are different things. Close the tab, lose Wi-Fi, let your
phone freeze a backgrounded page — a running job doesn't stop. It keeps running and buffering, and next
time you open that tab you catch up.

Only two things end a session: you close it, or it sits detached with no output for a while (an hour by
default, adjustable in settings). A job that's still working never gets swept away because a tab went
quiet.

---

Made with ❤️ by Fadhly Permata
