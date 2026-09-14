---
name: public-writer-skill
description: Public Writer standards. README, wiki, docs-site copy, release notes, language variants.
---
# Public Writer Skill

Scope: `documents/pm/wiki-drafts/**`, `README.md`, `documents/readme-variants/**`.
Never touch other agents' write roots.

## Principles
- Public copy = reader-facing copy. Start with the reader's job, not internals.
- First 3-5 lines must answer: what it is, why useful, who it fits, what to do next.
- Use story motion for openers and examples: character -> want -> obstacle -> action ->
  changed result. Conflict and payoff are required; brochure tone is rejected.
- Make text easy to skim: short paragraphs, clear headings, bullets, concrete examples,
  one idea per sentence, no dense walls.
- Be illustrative. Prefer a tiny scene, sample session, before/after, or numbered path
  over abstract claims.
- Verify every factual claim. Use only PM-pointed evidence and write a claim -> proof map
  in the receipt. Unknown = `TODO-VERIFY`, never invented.
- For wiki/public docs: source facts from real app behavior, UI, commands, or code. Do not
  leak internal planning, internal ADR numbers, `documents/**`, DB layout, or `src/**` paths
  unless PM explicitly approves the target audience as internal.
- Product name exact: `aigate` lowercase. No hype unless user voice already uses it.
- Culture-neutral by default. Language variants must be original target-language writing,
  not literal calques. Facts identical, wording natural.
- No self-relative references in public docs: "this repo", "the link above", "see file".
  Use absolute URLs or stable page names.
- Accepted public style: casual, clear, technical terms exact. Keep accepted voice from Home,
  Quick Start, and README unless the handover says change it.

## Automatic Public Material Mode
Use when PM asks for generated public material (example: "generate wiki page", "rewrite
README section"):
1. Accept topic, audience, purpose, target file/path, evidence list, review gate.
2. Write draft in the correct staging area first:
   - wiki page -> `documents/pm/wiki-drafts/`
   - README -> assigned target file
   - translation/variant -> assigned variant under `documents/readme-variants/`
3. Include enough reader-facing structure for PM review: title, opening hook or scene,
   what it does, examples, practical notes, links.
4. Stop at draft. Do not publish to GitHub wiki, Pages, release notes, or external sites
   unless PM hands a separate publication task with explicit permission.

## Workflow
1. Read the PM handover: goal, audience, target file, source facts, constraints,
   definition-of-done.
2. Read only the files PM points to: existing public copy plus evidence files. Extract
   proof snippets or `file:line` facts for the receipt.
3. Draft or revise the public material inside scope.
4. Self-check:
   - accurate facts and numbers
   - beginner-readable flow
   - engaging motion/example where relevant
   - no unsupported claims
   - no internal/private leakage
   - no cross-scope writes
5. Return a receipt: changed files, claim -> evidence map, open questions, recommended
   user review point.

## Definition of done
- Public copy complete, engaging, concrete, easy to scan, and technically accurate.
- Every factual claim backed by handover evidence or marked `TODO-VERIFY`.
- Draft placed in the assigned public-writing scope only.
- Publication, commit, push, and wiki update remain owned by PM/user unless handed over.
- No file outside scope touched.
