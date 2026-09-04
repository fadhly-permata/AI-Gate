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
