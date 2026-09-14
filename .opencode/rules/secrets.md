# SECRETS
API key / JWT / PAT / token / alike. Store in `.env`. Never hardcode in code. Never commit.

## Agent credentials (absorbs old R51; single home for this rule)
Cred source = repo root `.env`, nothing else. Absent var -> read file, do not invent a store.
Before claiming "cannot / no access": read `.opencode/rules/*.md` + `.env` first. Wrong claim = violation.
Git needs auth -> one-shot inline helper, value from `.env`, never written to disk:
`git -c credential.helper='!f(){ echo username=x-access-token; echo "password=$GITHUB_TOKEN"; }; f' <cmd>`
Never create new credential homes (`credential.helper store`, `~/.git-credentials`, SSH, config) unless user asks.
Token rejected / short scope -> report endpoint + status + scope, ask user. Do not switch mechanism alone.
Never print secret value: name + length + prefix + short hash only.
Product-side plaintext-in-DB secrets are a maintainer decision (OPERATING_RULES J3) — different domain, do not "clean".
