# OpenAI API 🔌

**You have a script, a notebook, a small app of your own** — and you want it to talk to a model without
hard-coding one vendor's address and one vendor's key into it forever. That's what this page is for: aigate
answers on one local address, in the shape OpenAI already made popular, and *which* provider actually
replies is decided per request by a single field. Nothing to install on the caller's side.

## One address, one port 🚪

```
http://localhost:8080/v1
```

Same app, same port as the screen you've been clicking. Move the port with `AIGATE_PORT=9090` and both
move together — there is only ever one port open. (The host and port you type on an endpoint are a label
for your own notes, not a second door.)

## The three things it answers 🎯

- `GET /v1/models` — what you may call right now
- `POST /v1/chat/completions` — the usual one
- `POST /v1/responses` — the newer OpenAI shape

That's the whole surface. There are no other endpoints.

## `model` is how you aim 🎛️

Three spellings, three targets:

| you send | aigate understands |
|----------|--------------------|
| `combo:<name>` | a combo you set up — if it holds several members, the top-priority one answers first |
| `<provider>:<model>` | one specific provider, named exactly as it is on your providers screen |
| `some-model-id` | a bare name with no prefix → the OpenAI path: the active provider's own address |

## Body and streaming 📄

Request bodies follow the OpenAI format: `model`, `messages`, `stream`, `temperature`, `max_tokens`.
Set `"stream": true` and the answer flows token by token; leave it out and you get one normal JSON reply.

Raw, copy-pasteable:

```bash
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"combo:<your-combo>","messages":[{"role":"user","content":"hello"}]}'
```

Put your own combo's name where the angle brackets are — the combos screen shows every name, and
`GET /v1/models` lists what you can aim at. Prefer Python? The official OpenAI
library works once you point its `base_url` here (a third-party library, not part of aigate). The library
insists on a key string; aigate only checks it if you switched the endpoint's key on:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8080/v1", api_key="unused")
print(client.chat.completions.create(
    model="combo:my-combo",
    messages=[{"role": "user", "content": "hello"}],
))
```

## The key you might need 🔑

If you switched on the access key for this endpoint, send it as a header:

```bash
-H "Authorization: Bearer <your-key>"
```

If you left it **off**, the API is open to anyone who can reach that port — same network, same café. Worth
reading [Configuration and Keys](Configuration-and-Keys) before you run this anywhere but your own
machine.

## Nothing here is off the books 🧾

Requests made from your own code are logged like everything else: tokens in, tokens out, an estimated cost,
one entry per call. Pointing a script at aigate is not going around it.

---

Made with ❤️ by Fadhly Permata
