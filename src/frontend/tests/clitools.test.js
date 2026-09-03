import { describe, it, expect } from "vitest";

// clitools.js is an IIFE attaching pure helpers onto window.aigate.
// It only touches window.Terminal / DOM inside methods, so importing it
// under jsdom (no xterm, no backend) is safe — buildLaunchCommand is fully
// testable.
import "../static/clitools.js";

const buildLaunchCommand = window.aigate.buildLaunchCommand;

describe("buildLaunchCommand (B3.4 CLI launcher, pure helper)", () => {
  it("returns install_command verbatim when binary is missing", () => {
    const dto = {
      binary_found: false,
      install_command: "pip install claude-code",
      run_command: "claude",
      env: { OPENAI_API_BASE: "http://localhost:8080/v1", OPENAI_API_KEY: "sk-x" }
    };
    expect(buildLaunchCommand(dto)).toBe("pip install claude-code");
  });

  it("returns '' (not crash) when binary missing and install_command is null", () => {
    expect(buildLaunchCommand({ binary_found: false, install_command: null })).toBe("");
  });

  it("builds export lines + run_command with proper newlines when binary present", () => {
    const dto = {
      binary_found: true,
      install_command: null,
      run_command: "claude",
      env: { OPENAI_API_BASE: "http://localhost:8080/v1", OPENAI_API_KEY: "sk-secret" }
    };
    const cmd = buildLaunchCommand(dto);
    const lines = cmd.split("\n");
    // 3 logical lines + trailing empty line from the final "\n".
    expect(lines[0]).toBe("export OPENAI_API_BASE='http://localhost:8080/v1'");
    expect(lines[1]).toBe("export OPENAI_API_KEY='sk-secret'");
    expect(lines[2]).toBe("claude");
    expect(cmd.endsWith("\n")).toBe(true);
    // Whole-string sanity: exports appear before the run command.
    expect(cmd.indexOf("export OPENAI_API_BASE")).toBeLessThan(cmd.indexOf("export OPENAI_API_KEY"));
    expect(cmd.indexOf("export OPENAI_API_KEY")).toBeLessThan(cmd.indexOf("claude"));
  });

  it("injects env values even when run_command is empty", () => {
    const cmd = buildLaunchCommand({
      binary_found: true,
      run_command: "",
      env: { OPENAI_API_BASE: "B", OPENAI_API_KEY: "K" }
    });
    expect(cmd).toContain("export OPENAI_API_BASE='B'");
    expect(cmd).toContain("export OPENAI_API_KEY='K'");
    expect(cmd.endsWith("\n\n")).toBe(true); // export + blank run line + final newline
  });

  it("tolerates missing env (uses empty strings)", () => {
    const cmd = buildLaunchCommand({ binary_found: true, run_command: "llm" });
    expect(cmd).toBe("export OPENAI_API_BASE=''\nexport OPENAI_API_KEY=''\nllm\n");
  });

  it("does not mask the plaintext OPENAI_API_KEY (ADR-007, local app)", () => {
    const cmd = buildLaunchCommand({
      binary_found: true, run_command: "x", env: { OPENAI_API_KEY: "sk-plaintext-internal" }
    });
    expect(cmd).toContain("sk-plaintext-internal");
  });
});
