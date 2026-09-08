# aigate 📱

**The only machine you own is a phone** — a second-hand one — yet most coding guides open with "grab a real laptop and a GPU." So the idea stayed parked for some future budget. Then you find a route that asks for none of it. The heavy AI thinking never runs on your phone — it runs at the providers you pick; your phone only routes traffic. Now, on a night bus with one hand on the screen, you ship from your pocket. The gear stopped being the excuse.

## What this is, and why it feels different ✨

aigate is a plain Python app you run yourself — Linux, Windows, Android (Termux), or a full Linux distro on a phone. No GPU, no compiler, nothing desktop-only. Start it and a page opens at a local address: no server, no account. Nothing talks back to us — your requests go only to the AI providers *you* chose, never through someone else's middleman. It's free and open source, and anyone may copy the code, so aigate's one true home is [github.com/fadhly-permata/AI-Gate](https://github.com/fadhly-permata/AI-Gate).

## What you can do with it 🧭

- **Build on a small screen.** Made for phones, in seven languages, light or dark.
- **Keep going when a key runs dry.** Line up a few providers in one group: when one errors or hits its quota, aigate moves to the next without a resend. [Set that up](Providers-and-Combos)
- **See where your AI money went.** Each request logs tokens and an *estimated* cost, grouped your way, plus a CSV export.
- **A real terminal in the browser.** 24 coding tools launch into a fresh tab with your chosen model. Missing one? You get an install command matched to your device — list still growing. [Look around](Terminal) · [See the tools](CLI-Tools)
- **Call it from your own code.** One local address, any language. [Here's how](OpenAI-API)

## Pick your starting point 🚀

| I want to… | Read this |
|------------|-----------|
| get it running on my phone | [Quick Start](Quick-Start) |
| hook up my coding tool | [CLI Tools](CLI-Tools) |
| choose and line up providers | [Providers & Combos](Providers-and-Combos) |
| send requests from my own code | [OpenAI API](OpenAI-API) |

## How it works, in one paragraph 🧠

Add the providers you have, put them side by side in a group — aigate calls it a *combo* — and each combo gives one tidy local address. Terminal, tools, your scripts: all point there. Which provider answers is aigate's problem, not yours. Your device only routes; models run on someone else's hardware, over your normal connection.

---

That's the map. [Quick Start](Quick-Start) is the first step.

Made with ❤️ by Fadhly Permata
