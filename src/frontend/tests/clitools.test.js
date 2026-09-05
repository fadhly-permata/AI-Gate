import { describe, it, expect } from "vitest";

// clitools.js is an IIFE attaching pure helpers onto window.aigate.
// It only touches window.Terminal / DOM inside methods, so importing it
// under jsdom (no xterm, no backend) is safe — buildLaunchCommand is fully
// testable.
import "../static/clitools.js";

const buildLaunchCommand = window.aigate.buildLaunchCommand;

// A representative aider DTO. NOTE binary_found:false on purpose: the server
// PATH hint must NOT force install-only — the PTY-side `command -v` decides.
const AIDER = {
  binary_found: false,
  binary_name: "aider",
  install_command: "pip install aider-chat",
  run_command:
    "aider --openai-api-base http://localhost:8080/v1 --openai-api-key sk-secret --model openai/gpt-5.5",
  env: { OPENAI_API_BASE: "http://localhost:8080/v1", OPENAI_API_KEY: "sk-secret" },
  model: "openai/gpt-5.5"
};

describe("buildLaunchCommand (B3.4 CLI launcher, PTY-side self-deciding)", () => {
  it("emits the full if/then/else/fi structure for a found tool", () => {
    const cmd = buildLaunchCommand(AIDER);
    const lines = cmd.split("\n");
    // Exact shape (2-space indented branches, trailing newline after `fi`).
    expect(lines[0]).toBe("export OPENAI_API_BASE='http://localhost:8080/v1'");
    expect(lines[1]).toBe("export OPENAI_API_KEY='sk-secret'");
    expect(lines[2]).toBe("if command -v aider >/dev/null 2>&1; then");
    expect(lines[3]).toBe("  " + AIDER.run_command);
    expect(lines[4]).toBe("else");
    expect(lines[5]).toBe("  pip install aider-chat");
    expect(lines[6]).toBe("fi");
    expect(lines[7]).toBe(""); // trailing newline
    expect(cmd.endsWith("fi\n")).toBe(true);
  });

  it("LAUNCHES (run_command present) even when server hint binary_found is false", () => {
    // Regression for the reported bug: an already-installed tool must not be
    // reduced to install-only just because the SERVER PATH missed the binary.
    const cmd = buildLaunchCommand({ ...AIDER, binary_found: false });
    expect(cmd).toContain("command -v aider");
    expect(cmd).toContain(AIDER.run_command); // run in the `then` branch
    expect(cmd).toContain("pip install aider-chat"); // install in the `else` branch
    // run_command must appear BEFORE install_command (then precedes else).
    expect(cmd.indexOf(AIDER.run_command)).toBeLessThan(cmd.indexOf("pip install aider-chat"));
  });

  it("keeps both export lines (env injected for generic tools)", () => {
    const cmd = buildLaunchCommand(AIDER);
    expect(cmd).toContain("export OPENAI_API_BASE=");
    expect(cmd).toContain("export OPENAI_API_KEY=");
  });

  it("does not mask the plaintext OPENAI_API_KEY (ADR-007, local app)", () => {
    const cmd = buildLaunchCommand({
      binary_name: "aider", run_command: "aider", install_command: "i",
      env: { OPENAI_API_KEY: "sk-plaintext-internal" }
    });
    expect(cmd).toContain("sk-plaintext-internal");
  });

  it("empty install_command -> else branch is a clear no-op message, no crash", () => {
    const cmd = buildLaunchCommand({
      binary_name: "foo", run_command: "foo --x", install_command: "", env: {}
    });
    expect(cmd).toContain("if command -v foo >/dev/null 2>&1; then");
    expect(cmd).toContain("  foo --x");
    expect(cmd).toContain('echo "aigate: \'foo\' not installed and no install command configured"');
    expect(cmd).toContain("else");
    expect(cmd).toContain("fi");
  });

  it("null install_command is treated like empty (message branch)", () => {
    const cmd = buildLaunchCommand({
      binary_name: "bar", run_command: "bar", install_command: null, env: {}
    });
    expect(cmd).toContain("not installed and no install command configured");
  });

  it("single-quote escaping in base/key does not break the command", () => {
    const cmd = buildLaunchCommand({
      binary_name: "aider", run_command: "aider", install_command: "i",
      env: { OPENAI_API_BASE: "http://x/it's", OPENAI_API_KEY: "sk-abc'def" }
    });
    // '\'' idiom: close-quote, escaped-quote, reopen-quote.
    expect(cmd).toContain("export OPENAI_API_BASE='http://x/it'\\''s'");
    expect(cmd).toContain("export OPENAI_API_KEY='sk-abc'\\''def'");
  });

  it("missing binary_name falls back to first token of run_command", () => {
    const cmd = buildLaunchCommand({
      run_command: "llm chat --model openai/gpt-5.5",
      install_command: "pip install llm",
      env: {}
    });
    expect(cmd).toContain("if command -v llm >/dev/null 2>&1; then");
    expect(cmd).toContain("  llm chat --model openai/gpt-5.5");
    expect(cmd).toContain("  pip install llm");
  });

  it("blank binary_name also falls back to run_command first token", () => {
    const cmd = buildLaunchCommand({
      binary_name: "   ", run_command: "claude --continue", install_command: "i", env: {}
    });
    expect(cmd).toContain("command -v claude");
  });

  it("empty run_command -> `then` is a `:` no-op (still valid shell)", () => {
    const cmd = buildLaunchCommand({
      binary_name: "aider", run_command: "", install_command: "pip install aider-chat", env: {}
    });
    const lines = cmd.split("\n");
    expect(lines[2]).toBe("if command -v aider >/dev/null 2>&1; then");
    expect(lines[3]).toBe("  :");
    expect(lines[4]).toBe("else");
    expect(lines[5]).toBe("  pip install aider-chat");
  });

  it("tolerates missing env (empty quoted exports)", () => {
    const cmd = buildLaunchCommand({ binary_name: "llm", run_command: "llm" });
    expect(cmd).toContain("export OPENAI_API_BASE=''");
    expect(cmd).toContain("export OPENAI_API_KEY=''");
  });

  it("tolerates a null/undefined dto without crashing", () => {
    expect(() => buildLaunchCommand(null)).not.toThrow();
    expect(() => buildLaunchCommand(undefined)).not.toThrow();
    const cmd = buildLaunchCommand({});
    expect(cmd).toContain("if command -v ");
    expect(cmd).toContain("fi");
  });
});

/* =====================================================================
 * renderGroups: a tool without a verified launch form is STRUCK THROUGH
 * (the operator's to-do marker) and must never open the launch modal.
 * ===================================================================== */
import "../static/i18n.js";

const renderGroups = window.aigate.cliTools._test.renderGroups;

const GROUPS = [
  {
    code: "agentic_coding",
    name: "Agentic Coding Assistants",
    tools: [
      { id: 1, name: "aider", binary_name: "aider", launch_mode: "verified", launch_reason: "" },
      { id: 2, name: "codex", binary_name: "codex", launch_mode: "pending", launch_reason: "" },
      { id: 3, name: "claude", binary_name: "claude", launch_mode: "unsupported", launch_reason: "anthropic_only" },
      { id: 4, name: "legacy", binary_name: "legacy", enabled: false } // no launch_mode at all
    ]
  }
];

function mount() {
  document.body.innerHTML =
    '<div id="cliGroups"></div>' +
    '<div id="cliLoadMsg" class="settings-msg"></div>' +
    '<div id="cliLaunchModal" class="modal" hidden></div>';
  renderGroups(GROUPS);
  return Array.from(document.querySelectorAll("#cliGroups .cli-tool"));
}

describe("renderGroups — strike-through for unverified tools", () => {
  it("a verified tool is NOT struck and keeps its binary tooltip", () => {
    const [aider] = mount();
    expect(aider.textContent).toBe("aider");
    expect(aider.classList.contains("cli-tool-unsupported")).toBe(false);
    expect(aider.getAttribute("aria-disabled")).toBe(null);
    expect(aider.title).toBe("aider");
  });

  it("pending + unsupported tools are struck through with a reason tooltip", () => {
    const [, codex, claude] = mount();
    expect(codex.classList.contains("cli-tool-unsupported")).toBe(true);
    expect(claude.classList.contains("cli-tool-unsupported")).toBe(true);
    expect(codex.getAttribute("aria-disabled")).toBe("true");
    // The tooltip explains WHY, translated from the server's reason code.
    expect(codex.title).toBe(window.I18N.en["cli.reason.pending"]);
    expect(claude.title).toBe(window.I18N.en["cli.reason.anthropic_only"]);
    expect(claude.title).not.toBe(codex.title);
  });

  it("a missing launch_mode (stale server) fails closed: struck, not launchable", () => {
    const [, , , legacy] = mount();
    expect(legacy.classList.contains("cli-tool-unsupported")).toBe(true);
    expect(legacy.classList.contains("cli-tool-disabled")).toBe(true); // enabled:false kept
  });

  it("clicking a struck tool shows the note and opens NO launch modal", () => {
    const [, codex] = mount();
    const modal = document.getElementById("cliLaunchModal");
    const msg = document.getElementById("cliLoadMsg");
    codex.click();
    expect(modal.hidden, "launch modal must stay closed for an unverified tool").toBe(true);
    expect(msg.textContent).toBe(window.I18N.en["cli.reason.pending"]);
    expect(msg.className).toContain("settings-msg-warn");
  });
});
