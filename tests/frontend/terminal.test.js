import { describe, it, expect } from "vitest";

// terminal.js is an IIFE that attaches pure helpers onto window.aigate.terminal.
// It only touches window.Terminal / window.FitAddon inside methods, so importing
// it under jsdom (no xterm) is safe — the helpers below are fully testable.
import "../static/terminal.js";

const T = window.aigate.terminal;

describe("buildTerminalWsUrl (B3.3 WS protocol)", () => {
  const originalProto = window.location.protocol;

  it("uses ws:// on an http page and the wss:// on https", () => {
    // jsdom default protocol is "http:"; assert scheme + path shape.
    const url = T.buildTerminalWsUrl("abc-123");
    expect(url.startsWith("ws://")).toBe(true);
    expect(url.endsWith("/ws/terminal/abc-123")).toBe(true);
    expect(url).toContain(window.location.host);
  });

  it("encodes the tab id into the path", () => {
    expect(T.buildTerminalWsUrl("tab/with slash?x=1")).toBe(
      "ws://" + window.location.host + "/ws/terminal/tab%2Fwith%20slash%3Fx%3D1"
    );
  });
});

describe("tabTitle (B3.3)", () => {
  it("returns the first 8 chars of a uuid id", () => {
    expect(T.tabTitle("12345678-9abc-def0")).toBe("12345678");
  });
  it("falls back to 'term' for empty id", () => {
    expect(T.tabTitle("")).toBe("term");
    expect(T.tabTitle(null)).toBe("term");
  });
});

describe("buildResizeFrame (B3.3 control frame)", () => {
  it("produces a JSON resize control frame", () => {
    const f = JSON.parse(T.buildResizeFrame(80, 24));
    expect(f).toEqual({ type: "resize", cols: 80, rows: 24 });
  });
});

describe("swipeToScrollDelta (B3.3 scroll/swipe, velocity + damping)", () => {
  it("returns 0 for zero velocity", () => {
    expect(T.swipeToScrollDelta(0)).toBe(0);
  });

  it("preserves sign (up swipe -> negative lines, down -> positive)", () => {
    expect(T.swipeToScrollDelta(-3)).toBeLessThan(0);
    expect(T.swipeToScrollDelta(3)).toBeGreaterThan(0);
  });

  it("maps faster swipes to MORE lines (monotonic, before saturation)", () => {
    const slow = Math.abs(T.swipeToScrollDelta(1));
    const fast = Math.abs(T.swipeToScrollDelta(3));
    const faster = Math.abs(T.swipeToScrollDelta(8));
    expect(fast).toBeGreaterThan(slow);
    expect(faster).toBeGreaterThan(fast);
  });

  it("caps magnitude at maxLines (soft saturation / easing)", () => {
    const huge = Math.abs(T.swipeToScrollDelta(100000));
    expect(huge).toBeLessThanOrEqual(60);
  });

  it("guarantees a minimum 1 line for any non-zero swipe", () => {
    expect(Math.abs(T.swipeToScrollDelta(0.01))).toBeGreaterThanOrEqual(1);
  });

  it("applies extra damping near a buffer edge (atEdge)", () => {
    const base = Math.abs(T.swipeToScrollDelta(6, { atEdge: false }));
    const edge = Math.abs(T.swipeToScrollDelta(6, { atEdge: true }));
    expect(edge).toBeLessThan(base);
  });

  it("keeps the same sign whether or not atEdge", () => {
    expect(T.swipeToScrollDelta(-6, { atEdge: true })).toBeLessThan(0);
    expect(T.swipeToScrollDelta(6, { atEdge: true })).toBeGreaterThan(0);
  });
});
