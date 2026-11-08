/** Navigation configuration — a broken href is a dead screen. */
import { describe, expect, it } from "vitest";
import { ACCOUNTANT_NAV, GROUPS, NAV } from "@/components/runway/nav";

describe("navigation", () => {
  it("covers every group with at least one item", () => {
    for (const g of GROUPS) {
      expect(NAV.filter((i) => i.group === g).length).toBeGreaterThan(0);
    }
  });

  it("assigns every item to a declared group", () => {
    for (const item of [...NAV, ACCOUNTANT_NAV]) {
      expect(GROUPS).toContain(item.group);
    }
  });

  it("has no duplicate routes", () => {
    const hrefs = NAV.map((i) => i.href);
    expect(new Set(hrefs).size).toBe(hrefs.length);
  });

  it("keeps every route under /app", () => {
    for (const item of [...NAV, ACCOUNTANT_NAV]) {
      expect(item.href.startsWith("/app")).toBe(true);
    }
  });

  it("gives every item a label, an icon and an explanatory blurb", () => {
    for (const item of [...NAV, ACCOUNTANT_NAV]) {
      expect(item.label.length).toBeGreaterThan(2);
      expect(item.icon).toBeTruthy();
      expect(item.blurb.length).toBeGreaterThan(10);
    }
  });

  it("exposes the three states, the lab and the copilot", () => {
    const hrefs = NAV.map((i) => i.href);
    for (const required of ["/app", "/app/state-centre", "/app/twin",
                            "/app/forecasts", "/app/scenarios", "/app/copilot"]) {
      expect(hrefs).toContain(required);
    }
  });

  it("only badges items that can actually carry a count", () => {
    for (const item of NAV) {
      if (item.badge) expect(["alerts", "recs"]).toContain(item.badge);
    }
  });
});
