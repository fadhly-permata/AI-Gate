# Terminal ⌨️

**On the night bus again, and the build you started an hour ago is still running back at the desk.** The reflex is to reach for an SSH app — keys, hosts, a second thing to babysit. Here, it's one tab inside the page you already have open. Each tab is a real session on the device aigate runs on — not a picture of a terminal.

## It keeps working when you walk away 🔌

Let the phone freeze the tab, lose Wi-Fi mid-run — the job doesn't stop. The browser view detaches; the process keeps running and collecting output, so when you return, you scroll through everything it said in the meantime. A blip reconnects by itself. Close the whole page and reopen it — the live tabs come back.

Only two things end a session: you close it, or it sits detached from any tab with nothing new to show for about an hour. A job that's still working never gets swept away for having a quiet tab. **Keep Screen On**, the switch below, keeps your *screen* awake while you watch a run — it isn't life support; the session never needed it.

## The controls, all of them 🎛️

Along the top: a tab strip with a **new-tab button** pinned at its end. In the corner, a small floating cluster that never covers what you're reading:

- **Paste** — injects your clipboard into the live session, then hands focus straight back so you keep typing. Its menu adds **Paste as Code Block**: the text arrives fenced, so an agent reads it as one piece instead of running your lines one by one.
- **Settings** — holds **Keep Screen On** and **TUI Passthrough**.
- One button, two different sizes: **Full Page** fills the page with the terminal; **Fullscreen** is the browser's own full-screen mode.

## Scrolling, thumb included 📱

Wheel and trackpad do what you expect. A finger swipe tracks 1:1 under your thumb, natural direction, with a little throw when you let go. Inside full-screen terminal apps — vim, htop, less — the same swipe becomes that app's own scrolling, no switch needed. **TUI Passthrough** is the opposite demand: hand the app your raw touch, so drag-to-select works the way the app wants. The last **5,000 lines** of history stay scrollable.

## When things misbehave 🧯

A failed command or a missing tool prints a readable line, not a crash. A coding tool that isn't installed comes with the install command that fits your device — Termux included. Every tool you launch from [CLI Tools](CLI-Tools) opens here, in a new tab. Running aigate with the developer window (`AIGATE_DEV=1`) adds a log window to the page.

## The honest limit 🚪

This is a shell on the device aigate itself runs on — not a bridge to some other machine. And that device answers to everyone on the local network, which is why [Quick Start](Quick-Start) warns about cafés.

---

Made with ❤️ by Fadhly Permata
