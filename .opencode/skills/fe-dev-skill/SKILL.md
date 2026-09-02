---
name: fe-dev-skill
description: Frontend Developer standards. UI, components, client state, styling, routing, browser.
---
# Frontend Developer Skill
Scope: src/frontend/**, tests/frontend/**. Never touch other agents' write roots.
## Principles
- Component-driven & composable; colocate local state.
- Consume backend contracts from documents/api/OPENAI_COMPATIBLE_CONTRACT.md and
  TSD terminal WS protocol (treat as source of truth).
- Accessibility: ARIA, keyboard nav, sufficient contrast.
- Design tokens; lazy routes where applicable.
- NO secrets in the frontend bundle. Keys stay server-side / injected via PTY env.
- Keep JS clear; type where used.
## Domain specifics (aigate — Web UI lokal, ADR-001)
- UI served by the SAME FastAPI server as the gateway (static + SPA JS).
- Terminal pane: xterm.js multi-tab + FitAddon/WebLinksAddon.
- REST JSON for management; WebSocket /ws/pty/{tab_id} for terminal I/O.
- WS protocol: binary frame = raw PTY I/O; text JSON control = resize/title/focus/
  paste/tui_mode/exit (TSD §3.1).
- Floating control (overlay div, z-index, pointer-events only on buttons):
  - Fullscreen toggle (requestFullscreen or CSS class). Per-pane, not global.
  - Paste: navigator.clipboard.readText() -> send control `paste` -> backend writes
    raw to PTY -> term.focus() to auto-return focus (TSD §3.2, UX §1).
- Scroll & Swipe (UX §2, TSD §3.3):
  - Wheel/trackpad native scroll via xterm.
  - Swipe -> Scroll (NOT TUI nav): intercept pointer events (threshold 10px),
    preventDefault+stopPropagation so TUI never gets the swipe.
  - Velocity-based: low |v| -> line-by-line; high -> page jumps (saturating map).
  - Damping: exponential decay on pointerup via requestAnimationFrame.
  - Whitelist TUI: per-tab tui_mode (scroll default / passthrough) via SwipeException
    registry + manual override toggle.
- CLI Tool Grouping UI (UX §3): groups A (agentic) / B (autonomous) / C (chat-shell);
  click tool -> check binary -> install tab if missing -> picker Provider/Combo+Model
  -> launch with injected env.
## Workflow
1. Read the PM handover (goal, context, definition-of-done).
2. Do the work strictly inside your write scope.
3. Return a receipt: files changed, decisions, open questions.
## Definition of done
- Work complete & verified inside scope (UI loads, interactions wired to contracts).
- No cross-scope file writes.
