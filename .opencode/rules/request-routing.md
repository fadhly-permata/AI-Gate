---
name: request-routing
description: Route every user interaction to ProjectManager as sole project entrypoint.
---

# USER REQUEST ROUTING

Every user input routes to `@ProjectManager` before handling.

Applies to all user commands, questions, requests, feedback, corrections,
status checks, and other interactions. `@ProjectManager` owns decomposition,
execution choice, specialist handoff, integration, verification, and response.

Do not bypass `@ProjectManager` for direct implementation or specialist work.
Preserve user intent and full relevant context during handoff. System,
developer, and tool instructions remain higher priority and are not user input.
