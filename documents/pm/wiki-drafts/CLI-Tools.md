# CLI Tools 🛠️

**Your coding tool isn't the problem — the setup ritual is.** Find its config, paste a key, type the address, spell the model name exactly right. Do it five times and you stop switching. So aigate keeps **24 of these tools** lined up with the wiring done: pick one, pick a model, and it opens in a fresh terminal tab already pointed where it should go.

## What a pick looks like ▶️

Open the coding-tools area, choose a tool, then a provider (or a combo) and a model. It launches in its own terminal tab, set up. From then on it calls aigate's local address like any client — switch the active provider or the whole [combo](Providers-and-Combos), and the change shows up inside the tool you're typing in.

## What's in the list 🧰

Three groups — agentic coding assistants, autonomous software agents, and chat-and-shell helpers — and the list keeps growing. Names you'll know: claude, codex, aider, opencode, goose, cline, plus shell helpers like llm and aichat. Two honest caveats: not every launch path is wired yet, and some install routes aren't on every platform.

## What aigate changes, per tool ⚙️

Two mechanisms, and it differs per tool. Some get their settings **written into the tool's own config file**. Others start with **environment variables in front of the command**, the address and model name riding along. You edit neither — that's why it already knows where to talk. One more: aigate now answers the Anthropic format too, so claude-code points straight at it with no middleman.

## Tool not installed? 📥

aigate won't install tools for you. It shows the command and you run it — something like `npm install -g @anthropic-ai/claude-code`. On a phone in Termux you get a line that fits Android instead — a couple of tools have their own (`pkg install aichat`), the rest use the usual pip/npm/cargo form where a package exists.

## Self-Heal 🩹

The card under the tool list: it makes its own git branch, runs an agentic tool you've already installed in a live tab, works through each warning in the log, runs the tests, and merges the branch back only when things pass — every step logged, a failure ending as a safe status, not a crash. It needs a git project and one of those agentic tools installed. **Read the risk:** it writes code and merges a branch — watch the tab and review what lands.

## If a tool pushes back 🧯

- **It asks for a key, or says nothing** → no provider or model was picked. Pick both, launch again.
- **`command not found`** → you saw the install line but haven't run it. Run it, then retry.
- **No launch offered for that tool** → that path isn't checked yet. A plain [Terminal](Terminal) tab still runs it.

---
