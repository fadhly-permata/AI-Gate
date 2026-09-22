# Handover: Fix Chat Playground Shimmer Border — Flowing Rainbow Trace

**Date:** 2026-09-19
**Owner:** fe-dev
**Priority:** high
**Type:** CSS fix (no JS change expected)

## Goal
Replace the current "rotating conic-gradient" shimmer border on the chat loading bubble with a **flowing rainbow border-trace** animation — where the rainbow colors travel *along* the border line like light running around the edge, instead of the entire gradient spinning in place.

## User complaint (verbatim)
> "chat playground berantakan banget. border shimmer kenapa malah muter gak jelas. gua cuma pengen shimmer border dengan loop pelangi"

User confirmed: they want the rainbow to **flow along the border path**, not rotate the whole box.

## Current implementation (PROBLEM)
File: `src/frontend/static/styles.css` lines 2748–2773

The `.chat-msg.chat-msg-loading::before` pseudo-element uses:
- `conic-gradient(from 0deg, #ff3b3b, #ff8a00, ...)` as background
- `-webkit-mask` trick to clip it to a 2px border ring
- `animation: chat-rainbow-spin 4.2s linear infinite` which does `transform: rotate(360deg)`

**Why it looks wrong:** The entire conic gradient rotates around the center of the box. On a rectangular element with border-radius, this creates a chaotic spinning effect where colors don't follow the border path — they just spin in place. The user describes this as "muter gak jelas".

## Target implementation
A **border-trace** animation where rainbow colors flow smoothly along the border perimeter. Common approaches (pick whichever works best cross-browser):

### Option A (preferred): Oversized rotating gradient behind mask
- Make the `::before` pseudo-element much larger than the parent (e.g., 200% width/height, centered)
- Apply the conic-gradient to this oversized element
- Rotate the oversized element (not the mask)
- The mask clips it to the border ring, creating the illusion of colors traveling along the edge
- This is the most performant and widely supported approach

### Option B: @property + hue-rotate or gradient-position animation
- Use CSS `@property` to animate a custom property that controls gradient position
- More complex, less browser support

### Option C: SVG border with animated stroke-dashoffset
- Most precise but heaviest; avoid unless Options A/B fail

**PM default (D2):** Go with **Option A**. If you find a better approach that achieves the same visual result with equal or better performance, use it and note the decision in your receipt.

## Constraints
1. **Pure CSS only** — no JavaScript changes. No new dependencies.
2. **Keep existing class names** — `.chat-msg.chat-msg-loading`, `.chat-loader-rainbow` must remain unchanged (other code/tests reference them).
3. **Preserve reduced-motion support** — the `@media (prefers-reduced-motion: reduce)` block at line 2798–2802 must continue to disable animation.
4. **Same color palette** — keep the existing rainbow stops (`#ff3b3b, #ff8a00, #ffd400, #36c740, #00b3ff, #7a5cff, #ff4fd8, #ff3b3b`) unless there's a good reason to adjust.
5. **Same border thickness** — 2px visible border.
6. **Same animation speed ballpark** — ~4s per cycle is fine; adjust if needed for smoothness but don't make it frantic.
7. **Also fix `.chat-loader-rainbow`** (line 2781–2791) — the small ring beside the text uses the same broken pattern. Apply the same flowing-border technique (adapted for circular shape).
8. **No new hex colors** unless strictly necessary for the technique.
9. **Cache-buster update** — bump `styles.css?v=` in `index.html` line 61 (current value needs checking; increment date to `20260919`).
10. **F6 compliance** — this is purely visual CSS; no behavioral change to the page.

## File scope
- **WRITE:** `src/frontend/static/styles.css`, `src/frontend/static/index.html` (cache-buster only)
- **WRITE:** `src/frontend/tests/**` if any existing tests assert on the old animation behavior
- **READ:** `documents/pm/` for context
- **DO NOT TOUCH:** `src/backend/**`, `src/shared/**`, any non-frontend files

## Definition of done
1. The chat loading bubble border shows rainbow colors **flowing along the border path** (not spinning in place).
2. The small `.chat-loader-rainbow` ring also flows correctly.
3. Reduced-motion preference still respected.
4. All existing vitest tests pass (`npx vitest run` from `src/frontend/`).
5. Cache-buster updated in `index.html`.
6. Receipt includes: files changed, technique chosen, any decisions made.

## Reference
- Current CSS: `src/frontend/static/styles.css:2748-2802`
- Memory bank context: `documents/pm/memory-bank.md` (search "Chat Playground B6")
- F6 rule: preview/isolation not applicable here (pure CSS fix), but general principle of no behavioral side-effects applies.

</content>