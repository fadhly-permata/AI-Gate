# CLI Tool Presets & Plugin — Config Schema

Skema config untuk grouping tool CLI (PRD §2.6.1, FSD §2.6.1, UX §3). Runtime
config (grup & tool preset) disimpan di **DB** (tabel `CLIToolGroup` / `CLITool` per
ERD) — lihat ADR-010 (config di DB, bukan file). File YAML/JSON di bawah hanya
berlaku sebagai **format seed/import** (Roadmap §6), bukan sumber kebenaran.

## Schema (YAML)
```yaml
version: 1
groups:
  - id: agentic_coding        # Grup A
    label: "Agentic Coding Assistants"
    tools:
      - name: claude
        binary: claude
        install: "pip install claude-code"   # atau uv
        presets: ["openai-compatible"]
      - name: opencode
        binary: opencode
      - name: codex
        binary: codex
      - name: gemini
        binary: gemini
      - name: antigravity
        binary: antigravity
      - name: phi
        binary: phi
      - name: aider
        binary: aider
      - name: goose
        binary: goose
      - name: amp
        binary: amp
      - name: qwen
        binary: qwen
      - name: cline
        binary: cline
      - name: kilo
        binary: kilo
  - id: autonomous_agents     # Grup B
    label: "Autonomous Software Agents"
    tools:
      - name: openhands
      - name: swe-agent
      - name: open-interpreter   # CLI: interpreter
        binary: interpreter
      - name: autogpt
      - name: gpt-researcher
      - name: crewai
  - id: chat_shell            # Grup C
    label: "Chat & Shell Assistants"
    tools:
      - name: llm
        binary: llm
      - name: sgpt
        binary: sgpt
      - name: mods
        binary: mods
      - name: oterm
        binary: oterm
      - name: gptme
        binary: gptme
      - name: aichat
        binary: aichat
```

## Field
- `groups[].id` unik, `label` tampilan.
- `tools[].name` id, `binary` perintah cek (`which`/`where`), `install` opsional.
- Minimal 5 tool per grup.

## Plugin
File tambahan (YAML/JSON) bisa di-drop di folder `config/cli-plugins/` dan di-merge
ke tabel DB (`CLIToolGroup`/`CLITool`) saat startup (nama grup bebas asal `id` unik).
