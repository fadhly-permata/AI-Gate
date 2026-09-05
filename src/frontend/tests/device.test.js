import { describe, it, expect } from "vitest";

// device.js is a side-effect module: it attaches window.aigate.deviceAttr
// (jsdom provides window). Pure + browser-safe.
import "../static/device.js";

describe("deviceAttr (B4.2)", () => {
  it("returns canonical 'phone' for phone", () => {
    expect(window.aigate.deviceAttr("phone")).toBe("phone");
  });

  it("returns canonical 'tablet' for tablet", () => {
    expect(window.aigate.deviceAttr("tablet")).toBe("tablet");
  });

  it("returns canonical 'desktop' for desktop", () => {
    expect(window.aigate.deviceAttr("desktop")).toBe("desktop");
  });

  it("normalizes case and whitespace", () => {
    expect(window.aigate.deviceAttr("PHONE")).toBe("phone");
    expect(window.aigate.deviceAttr(" Tablet ")).toBe("tablet");
    expect(window.aigate.deviceAttr("DESKTOP")).toBe("desktop");
  });

  it("defaults unknown input to 'desktop'", () => {
    expect(window.aigate.deviceAttr("watch")).toBe("desktop");
    expect(window.aigate.deviceAttr("")).toBe("desktop");
    expect(window.aigate.deviceAttr(null)).toBe("desktop");
    expect(window.aigate.deviceAttr(undefined)).toBe("desktop");
    expect(window.aigate.deviceAttr(42)).toBe("desktop");
  });

  it("only ever returns one of the three canonical tokens", () => {
    var out = window.aigate.deviceAttr("anything");
    expect(["phone", "tablet", "desktop"]).toContain(out);
  });
});
