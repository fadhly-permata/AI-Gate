# Configuration and Keys 🔑

**You add a provider, paste a key, press save — and then the question lands: where does that secret
actually live, and who else could read it?** Right question. Here is the whole answer, the limits
included.

## What one provider record holds 🗂️

Each provider you add is a handful of plain choices. A name you'll recognise. The kind of service it is:
`openai`, `anthropic`/`claude`, `gemini`, `ollama`, `openrouter`, `litellm`, `openai-compatible`,
`cursor`, `kiro`, `vertex`, `antigravity`, or `other`. A kind aigate hasn't heard of is handled as if it
were OpenAI, so an unusual provider still answers instead of breaking.

Then the address where that provider answers — plain `http://` and localhost are both allowed, which is
how a model running on your own machine joins in with nothing extra switched on. Its key. Whether it is
switched on at all. The service tier, defaulting to *subscription*. A quota limit and the period it
resets over. Any extra headers the provider asks for, and the model to use when nothing else says.

## Keys, honestly 🗝️

Keys are stored **unencrypted** in the data file. aigate expects a device you own. If somebody can read
that file — a shared laptop, a phone you lost — they can read your keys. So don't set this up on a
device you share. Some providers also let you sign in with an account instead of pasting a key; that
option sits on the providers screen.

## Where everything lives 📁

Settings and records all go into one database file, `aigate.db`, inside a `.aigate` folder in your home
directory. That file is the thing to back up; move it with `AIGATE_DB_PATH`. In total the app knows
**three** environment variables: `AIGATE_PORT`, `AIGATE_DEV`, `AIGATE_DB_PATH`. Any other name is
ignored.

Prefer a download: export your settings as one JSON file, or export a report as CSV. Both downloads
carry your keys, so keep them out of git.

## Address, port, and who can reach you 🌐

The screen and the API are one app on one port — `8080`, unless you change it (the setting is right
there on the screen, and `AIGATE_PORT` does the same from the command line). That port answers on the
whole network, so anything near you can see it. The real lock is per endpoint: switch on its access key
and require callers to present it. Leave that off and anyone on the network can use your providers and
spend your quota.

Outbound proxies are the advanced corner: one pool per endpoint, each member a host, a port and a
protocol, taken in turn, with aigate noting each one's status and speed. The host and port you type on
an endpoint are a label for your own bookkeeping — they do not open a second port.

## The step people skip ▶️

A saved key is not enough. Choose which provider is the one in use — until you do, the terminal, the
tools and the API stay silent. [Providers & Combos](Providers-and-Combos) is next.

---

Made with ❤️ by Fadhly Permata
