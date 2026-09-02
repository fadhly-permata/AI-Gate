---
description: Manage skills via Context7 (MCP first, curl v2 fallback) and local store
---
Manage skills. Action = first arg. `get` and `search` MUST use Context7.

Primary: Context7 MCP tools.
Fallback (MCP unavailable): Context7 v2 REST API, Bearer token.
  Key: env `CONTEXT7_API_KEY`, else read `.env`.

Args: $ARGUMENTS

If first arg in `help` / `info` / `information` / `?` -> print usage below, stop.

Usage: /context7-proc <action> [args]
  get <topic> [name]           Fetch from Context7, save .opencode/skills/<name>/SKILL.md
  search <query> [limit]       Search Context7 (default limit 5)
  delete <name>                Remove .opencode/skills/<name>/
  help|info|information|?      Show this usage

Key resolve (fallback):
  KEY="${CONTEXT7_API_KEY:-$(grep CONTEXT7_API_KEY .env | cut -d= -f2)}"

search (MCP first, else curl v2):
  curl -X GET "https://context7.com/api/v2/libs/search?libraryName=<query>&query=<query>" \
    -H "Authorization: Bearer $KEY"

get (MCP first, else curl v2):
  1. search v2 -> grab first result libraryId.
  2. curl -X GET "https://context7.com/api/v2/context?libraryId=<id>&query=<topic>&type=txt" \
       -H "Authorization: Bearer $KEY"
  3. Make dir `.opencode/skills/<name>/` (name default = topic slug).
  4. Write returned docs as `SKILL.md` (English caveman ultra per project rules).
  5. Report saved path.

delete:
  1. Check `.opencode/skills/<name>/` exist.
  2. Remove that dir.
  3. Report deleted.
