# Configuration and Keys 🔑

**You add a provider, paste the key, press save — done.** Then the thought lands: that key sits somewhere on this machine — where, and who else could read it? The honest answer, limits included.

## What a provider record holds 🗂️

A provider is a handful of plain choices. A name you'll recognise. The kind — `openai`, `anthropic`/`claude`, `gemini`, `ollama`, `openrouter`, `litellm`, `openai-compatible`, `cursor`, `kiro`, `vertex`, `antigravity`, or `other`; a kind aigate hasn't heard of counts as OpenAI, so odd providers answer. The address it answers on — plain `http://` and localhost both work; a model on your own machine joins with nothing extra to switch on. Then its key, an on/off switch, a service tier (subscription by default), a quota cap and reset, extra headers, a default model.

## Keys, stored honestly 🗝️

No encryption — keys sit in the open inside the data file; aigate expects a device you own. Whoever can read that file — a shared laptop, a lost phone — can read your keys. Don't set this up on a shared device. Some providers sign in with an account instead; the option sits on the providers screen.

## Where everything lives 📁

Settings and records go into one database file, `aigate.db`, in a `.aigate` folder inside your home directory — back it up. `AIGATE_DB_PATH` moves it elsewhere. The app knows exactly three environment variables: `AIGATE_PORT`, `AIGATE_DEV`, `AIGATE_DB_PATH`. Anything else does nothing. Prefer downloads? Export settings as JSON for another device, or a report as CSV. That JSON holds your keys — keep it out of git.

## On the settings screen 🎛️

There's Port, developer mode, theme (light or dark), and language — eight. Three quieter choices exist behind that screen rather than on it: detailed per-request logging (off by default), how long records are kept (a week), and when a lost terminal session is dropped (an hour). They hold their defaults until you deliberately change them.

## One port, and who can reach it 🌐

Screen and API are one app on one port — `8080`, changeable here or with `AIGATE_PORT=9090 python run.py` ([Quick Start](Quick-Start)). Coding tools get `http://localhost:8080/v1` — one setting; change it if aigate lives elsewhere. That port answers across your whole network. The real lock is per endpoint: its own access key, checked at the gate. Leave it off and anyone nearby can spend your quota. A trap: the host and port you type on an endpoint are labels — they open no second port, and `127.0.0.1` there locks nothing. Only the key does. Outbound proxies, the advanced corner: one pool per endpoint, used in turn, status and speed logged.

## The step people skip ▶️

A saved key isn't enough — choose which provider is the one in use. Until you do, the terminal, the tools, and the API stay silent. [Providers & Combos](Providers-and-Combos) is next.

---
