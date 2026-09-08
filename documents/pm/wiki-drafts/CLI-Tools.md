# CLI Tools 🛠️

**Your coding tool isn't the problem — the ritual is.** Find its config file, paste a key, type an
address, name a model in the spelling only that tool accepts. Do that five times and you stop switching
providers. aigate has **24** of them lined up, wiring already done — a click instead of a chore.

## The flow ▶️

Open the coding-tools area → pick a tool → pick a provider or a combo, and a model → the tool starts in a
**new terminal tab**, already set up.

From then on the tool calls aigate's local address like any other client. That's the payoff: move a combo
or change the active provider on the aigate side, and the shift shows up inside the tool you're typing in.

## What's in the list 🧰

Three kinds:

- **agentic coding assistants** — the ones that write and edit code with you
- **autonomous software agents** — the ones you point at a job and let run
- **chat and shell helpers** — the ones that answer, or wrap a command

Names you'll recognise: claude, opencode, codex, gemini, aider, goose, amp, qwen, cline, openhands,
aichat, llm, sgpt. Two honest caveats: the list is still growing, and some install paths aren't available
on every platform yet. A few tools can't be launched through this feature at all — aigate marks those
rather than pretending.

## What gets set, and how ⚙️

Not one mechanism; two. Worth knowing if you're curious about what happened behind the click:

- some tools have their settings **written into the tool's own config file**;
- others are started with **environment variables in front of the command** — the base address and the
  model name riding along with that one launch.

You don't edit either. That's why the tool that opens already knows where to talk.

## Tool not installed? 📥

aigate won't install tools for you. If the tool isn't there, it **shows you the install command** and you
run it. On a phone in Termux you get the Android-shaped command, not the desktop one — the app knows it's
in Termux and offers what fits your device.

## If the tool protests 🧯

- **Nothing answers, or it asks for a key** → provider or model wasn't picked. Pick both, launch again.
- **`command not found`** → you saw the install command but haven't run it yet. Run it, then retry.
- **aigate offers no launch for that tool** → it isn't a supported path yet. [Terminal](Terminal)
  still gives you a plain shell; [Providers & Combos](Providers-and-Combos) explains what you're aiming at.

---

Made with ❤️ by Fadhly Permata
