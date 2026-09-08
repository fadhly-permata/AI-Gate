# Providers & Combos 🧩

**Three words explain everything else in the app: provider, combo, endpoint.** If you read one page
besides [Quick Start](Quick-Start), read this one. No architecture talk — the kitchen version.

## The chain, in order 🔗

**A provider** is one account that can answer: a key, plus an address to reach it. The address may
even point at the very device aigate runs on, like a local model service that speaks OpenAI's language
on port 11434. That's how working with no internet at all becomes possible — the app's own pages
already come from your device, never the internet, and traffic only leaves toward providers *you*
picked.

**A combo** is a handful of providers lined up together. Each member gets a **priority** and a
**weight**, and the combo runs on one **strategy** — next section. Combos are yours to build: none
arrive ready-made, and the names come from your keyboard.

**An endpoint** is the local address a combo hands to your other tools and apps — what you paste into
a coding tool or a script. Each endpoint can carry its own access key and optionally its own
outbound proxy. The host and port you type there are labels for your own notes; the app still runs on
one port — `8080` unless you move it with `AIGATE_PORT`. One door, whatever the labels say.

## The strategy, in words 🎲

The screen shows three names — `fallback`, `load_balance`, `latency_cost`. What they do:

**Fallback — a queue.** Try the top-priority provider first; if it errors, hits a quota, or stops
answering, move down the list. Small nuance: when a provider is throttled or its access goes
bad, aigate first tries **another account of that same provider** before switching providers. And if
the whole list fails, you see the **last** error message as written — it doesn't hide what happened.
This is the "keep going when a key runs dry" from [Home](Home).

**Load balance — a weighted dice roll.** Each request picks at random, steered by the weights, so work
spreads across several accounts instead of grinding one down.

**Latency cost — the careful spender.** Here the weights are read as cost estimates: the cheapest
option gets the request, **once**. No retries, no jumping sideways — if that cheap provider happens to
be down, the request fails rather than quietly moving elsewhere. Cheap-and-steady over always-answers,
on purpose; don't mix it up with fallback.

## Quotas 📊

Any provider can carry a quota limit and a reset period. Usage is recorded as it happens and shows up
on the analytics page. What I won't claim: that aigate slams the door the moment a limit is crossed.
What it does: the numbers stay visible, and they feed the choosing.

## Why bother 🧠

Because of what happens at the other end. Your tools and scripts point at an aigate address and never
need it changed. Switch the provider, reshuffle a combo, add a cheaper account — here, in one place,
and every tool follows. The only list you maintain is this one.

---

Made with ❤️ by Fadhly Permata
