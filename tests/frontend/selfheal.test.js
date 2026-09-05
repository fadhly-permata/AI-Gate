import { describe, it, expect } from "vitest";

// Pure helpers for the B4.1 Self-Heal UI. Import the i18n dictionary first so
// `window.I18N` is populated, then the module under test. No DOM needed for
// renderSelfHealStatus / renderAgenticCheck — they are pure.
import "../../src/frontend/static/i18n.js";
import "../../src/frontend/static/selfheal.js";

const renderSelfHealStatus = window.aigate.renderSelfHealStatus;
const renderAgenticCheck = window.aigate.renderAgenticCheck;

describe("renderAgenticCheck (GET /api/self-heal/agentic-cli)", () => {
  it("flags missing CLI and returns the no-agentic-CLI message (EN)", () => {
    const v = renderAgenticCheck({ available: false, cli: null }, "en");
    expect(v.available).toBe(false);
    expect(v.message).toBe("Self-Heal can't run: no agentic CLI installed");
  });

  it("flags missing CLI with null body and returns ID message", () => {
    const v = renderAgenticCheck(null, "id");
    expect(v.available).toBe(false);
    expect(v.message).toBe("Self-Heal tidak bisa berjalan: tidak ada agentic CLI terinstall");
  });

  it("reports available CLI name (EN)", () => {
    const v = renderAgenticCheck({ available: true, cli: "claude" }, "en");
    expect(v.available).toBe(true);
    expect(v.cli).toBe("claude");
    expect(v.message).toBe("Agentic CLI detected: claude");
  });

  it("reports available CLI name (ID)", () => {
    const v = renderAgenticCheck({ available: true, cli: "aider" }, "id");
    expect(v.available).toBe(true);
    expect(v.message).toBe("Agentic CLI terdeteksi: aider");
  });
});

describe("renderSelfHealStatus (POST /api/self-heal/run)", () => {
  it("no_agentic_cli -> error with no-CLI message (EN)", () => {
    const v = renderSelfHealStatus({ ok: false, reason: "no_agentic_cli" }, "en");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Self-Heal can't run: no agentic CLI installed");
  });

  it("no_agentic_cli -> ID message", () => {
    const v = renderSelfHealStatus({ ok: false, reason: "no_agentic_cli" }, "id");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Self-Heal tidak bisa berjalan: tidak ada agentic CLI terinstall");
  });

  it("git_failed -> error with detail appended (EN)", () => {
    const v = renderSelfHealStatus({ ok: false, reason: "git_failed", detail: "not a repo" }, "en");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Git operation failed (not a repo)");
  });

  it("git_failed -> ID message + detail", () => {
    const v = renderSelfHealStatus({ ok: false, reason: "git_failed", detail: "bukan repo" }, "id");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Operasi git gagal (bukan repo)");
  });

  it("merged:true -> ok with iteration count (EN)", () => {
    const v = renderSelfHealStatus({ ok: true, merged: true, iterations: 3 }, "en");
    expect(v.kind).toBe("ok");
    expect(v.message).toBe("Self-Heal complete: all issues resolved & merged to main (3 iterations).");
  });

  it("merged:true -> ID with iteration count", () => {
    const v = renderSelfHealStatus({ ok: true, merged: true, iterations: 3 }, "id");
    expect(v.kind).toBe("ok");
    expect(v.message).toBe("Self-Heal selesai: semua issue teratasi & di-merge ke main. (3 iterasi).");
  });

  it("merged:false -> warn with remaining count (EN)", () => {
    const v = renderSelfHealStatus({ ok: true, merged: false, remaining: 2 }, "en");
    expect(v.kind).toBe("warn");
    expect(v.message).toBe("Self-Heal ran but 2 issue(s) remain unresolved.");
  });

  it("merged:false -> ID with remaining count", () => {
    const v = renderSelfHealStatus({ ok: true, merged: false, remaining: 2 }, "id");
    expect(v.kind).toBe("warn");
    expect(v.message).toBe("Self-Heal berjalan tapi 2 issue belum teratasi.");
  });

  it("unexpected 500 error envelope -> error with message", () => {
    const v = renderSelfHealStatus(
      { error: { message: "boom", type: "internal", code: "self_heal_failed" } }, "en"
    );
    expect(v.kind).toBe("error");
    expect(v.message).toBe("boom");
  });

  it("network failure sentinel -> generic error (EN)", () => {
    const v = renderSelfHealStatus({ _networkError: true }, "en");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Self-Heal failed unexpectedly.");
  });

  it("null result -> generic error (EN)", () => {
    const v = renderSelfHealStatus(null, "en");
    expect(v.kind).toBe("error");
    expect(v.message).toBe("Self-Heal failed unexpectedly.");
  });
});
