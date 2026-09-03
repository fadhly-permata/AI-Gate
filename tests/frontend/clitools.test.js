import { describe, it, expect } from "vitest";

// Mirror of the B3.4 CLI launcher unit test, placed at the spec-named path
// tests/frontend/clitools.test.js. Imports the helper from the frontend
// static module. (Project's npm test runs src/frontend/tests; this copy keeps
// the literal deliverable path in scope.)
import "../../src/frontend/static/clitools.js";

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

  it("builds export lines + run_command with proper newlines when binary present", () => {
    const dto = {
      binary_found: true,
      install_command: null,
      run_command: "claude",
      env: { OPENAI_API_BASE: "http://localhost:8080/v1", OPENAI_API_KEY: "sk-secret" }
    };
    const cmd = buildLaunchCommand(dto);
    const lines = cmd.split("\n");
    expect(lines[0]).toBe("export OPENAI_API_BASE='http://localhost:8080/v1'");
    expect(lines[1]).toBe("export OPENAI_API_KEY='sk-secret'");
    expect(lines[2]).toBe("claude");
    expect(cmd.endsWith("\n")).toBe(true);
    expect(cmd.indexOf("export OPENAI_API_BASE")).toBeLessThan(cmd.indexOf("claude"));
  });

  it("tolerates missing env (empty strings) and does not mask the key (ADR-007)", () => {
    const cmd = buildLaunchCommand({
      binary_found: true, run_command: "x", env: { OPENAI_API_KEY: "sk-plaintext-internal" }
    });
    expect(cmd).toContain("export OPENAI_API_BASE=''");
    expect(cmd).toContain("sk-plaintext-internal");
  });
});
