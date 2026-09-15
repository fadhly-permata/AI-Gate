# Providers & Combos 🧩

**Mid-task, the provider that answered all week hits its limit.** The tool waits a beat — and usually nothing worse happens: aigate moves on to the next member without you resending. That move rests on three words: provider, combo, endpoint. If you read one page besides [Quick Start](Quick-Start), read this one.

## The chain 🔗

**A provider** is one AI service — a key plus an address to reach it. Kinds and setup live in [Configuration & Keys](Configuration-and-Keys). The address may even point at the device aigate runs on, which is how a model with no internet at all still answers.

**One provider can hold several accounts**, in the order you set. Walk them either way: run the first until it runs dry, then move on — or share the turns with a cap per account before the next steps up.

**A combo** is a list of provider-and-model choices lined up as one option. None arrive ready-made, and you name them yourself. Each member gets a place in the row and a share of traffic, and the combo runs on one **strategy** — next section.

**An endpoint** is the tidy local address a combo exposes to your tools — the line you paste into a coding tool. One combo, one address; which member answers is aigate's business, not yours.

## The strategy, in words 🎲

Five choices sit on the combo screen:

**fallback** — the standard one. A queue by row order: ask the first; if it errors, move on **without a resend**. A quota or access complaint first tries the same provider's next account. If the whole queue fails, the last error surfaces as written.

**load_balance** — a dice roll weighted per request: work spreads over several accounts instead of grinding one down.

**latency_cost** — reads each share as a cost guess and takes the cheapest, exactly once: if the cheap one is down, the request fails rather than quietly moving elsewhere. Cheap-and-steady over always-answers, on purpose.

**three_tier** — the same queue, ordered by service level first: subscription, then cheap, then free; row order decides inside each level.

**round_robin** — strict turns, shares ignored: one member per request, walking the list and wrapping around. A just-failed member is stepped past, so the next request starts elsewhere.

Queue-style strategies also read quotas: a member whose provider is at zero remaining moves to the back, never out.

## Keys and the way out 🔌

Each endpoint can require its own access key, so lending a laptop doesn't hand your combo to everyone. Each may also leave through a **proxy pool** — hosts and ports you exit through, taken in turn, each one's health and delay probed and recorded. Wiring an address into your own code: [OpenAI API](OpenAI-API).

## The one-sentence version ✍️

Gather three providers into one combo — call it my-combo, point every tool at its single address, let aigate take the turns. Reshuffle the list in one place, and every connected tool follows.

---
