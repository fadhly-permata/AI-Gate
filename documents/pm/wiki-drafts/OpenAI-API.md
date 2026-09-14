# OpenAI API 🔌

**You've wired a model into your own script before, and it never ends.** A vendor key in one file, an address in another, a model name hard-coded where you'll forget it. So you point the script at something that won't move: aigate answers on one local address, in the request shapes your code already speaks, and *which* provider replies is just a field you change per call. Nothing to install on the calling side.

## One address, one port 🚪

```
http://localhost:8080/v1
```

Same app and same port as the screen you've been clicking. Move it with `AIGATE_PORT=9090` and both move together — there is only ever one port. (The host and port on an endpoint are a label for your own notes, not a second door.)

## The paths that answer 🎯

- `GET /v1/models` — what you can aim at right now, built live from your providers and combos
- `POST /v1/chat/completions` — the familiar one
- `POST /v1/responses` — OpenAI's newer responses shape
- `POST /v1/messages` — the Anthropic Messages shape, too
- `POST /v1/messages/count_tokens` — its token counter

So "OpenAI-compatible" here means plain enough that any client speaking that JSON works — and a client speaking Anthropic's shape is accepted on the same address. The Anthropic path answers in full for now, not streaming.

## The `model` field is how you aim 🧭

Send a combo you set up — `combo:my-combo` — and if it holds several providers, the top one answers first, and a failure rolls on to the next ([Providers & Combos](Providers-and-Combos)). Or copy any id straight from `GET /v1/models`. Or just send a bare model name: aigate finds an enabled provider that offers it, and if more than one does, it picks the provider you marked as the one in use.

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"combo:my-combo","messages":[{"role":"user","content":"hello"}]}'
```

The reply comes back in the same style your client expects — the short version:

```json
{"choices":[{"message":{"content":"Hi there."}}],"usage":{"total_tokens":18}}
```

Send `"stream":true` to OpenAI-shape providers and it flows in pieces instead. Bodies follow the usual fields — `model`, `messages`, `temperature`, `max_tokens`. Prefer Python? The official OpenAI library works once you point its base URL here — a third-party library, not part of aigate.

## The key you might need 🔑

Turn an endpoint's access key on and send it as `Authorization: Bearer <key>` — or `x-api-key`, the header Anthropic clients use. Leave it off and the API is open to anyone who can reach that port: same network, same airport. That's the [Quick Start](Quick-Start) café warning again. [Configuration and Keys](Configuration-and-Keys) sets it.

## Nothing slips past the books 🧾

Every call from your own code is recorded like any other — tokens in, tokens out, an estimated cost. Pointing a script at aigate isn't going around it.

---

Made with ❤️ by Fadhly Permata
