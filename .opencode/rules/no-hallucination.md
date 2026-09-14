# NO HALLUCINATION
Task start, clueless what do. Do not assume. Do not hallucinate.
Resolve via: skill, web search, or ask user direct.
Skill dynamic via context7 (https://context7.com). Save token -> store skill in `.opencode/skills/*`.
Need skill: check `.opencode/skills/` first. Absent -> search context7.
Context7 API key: env `CONTEXT7_API_KEY` (in `.env`, never inline).

## Proof required (absorbs old R47; canonical clause)
Every technical claim carry proof: `file:line`, URL, or user confirmation. No proof -> say "UNKNOWN", ask, or verify.
External facts (package, binary, os/cpu/libc, platform) need >=2 independent sources, cross-checked; conflict -> investigate to consistency. One source is not enough.
Capability or policy answer without reading the source file first = hallucination.
