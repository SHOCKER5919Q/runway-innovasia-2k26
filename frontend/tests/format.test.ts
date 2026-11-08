/**
 * Money and display formatting.
 *
 * These matter more than they look. Indian digit grouping is not the
 * western one, and a mis-grouped figure is a different number to the
 * person reading it: ₹1,00,000 and ₹100,000 are both "one lakh" to a
 * formatter and visually distinct to an owner.
 */
import { describe, expect, it } from "vitest";
import {
  days, direction, inr, longDate, money, paiseOf, pct, relDays, shortDate,
  signedPct, STATE_META, titleCase, weeks,
} from "@/lib/format";

describe("inr — Indian digit grouping", () => {
  it.each([
    [0, "₹0"],
    [10000, "₹100"],
    [82400000, "₹8,24,000"],
    [123456780, "₹12,34,568"],
    [1234567800, "₹1,23,45,678"],
    [99900, "₹999"],
  ])("formats %i paise as %s", (paise, expected) => {
    expect(inr(paise)).toBe(expected);
  });

  it("groups by lakh and crore, not by thousand", () => {
    // The western grouping would give ₹1,234,568 — a different number to read.
    expect(inr(123456780)).toBe("₹12,34,568");
    expect(inr(123456780)).not.toContain("1,234,568");
  });

  it("uses a true minus sign, not a hyphen", () => {
    expect(inr(-50000000)).toBe("−₹5,00,000");
  });

  it("renders compact lakh and crore", () => {
    expect(inr(187000000, { compact: true })).toBe("₹18.70 L");
    expect(inr(4800000000, { compact: true })).toBe("₹4.80 Cr");   // ₹4.8 crore
    expect(inr(5500000, { compact: true })).toBe("₹55.0 K");
  });

  it("returns an em dash for missing values rather than ₹0", () => {
    // ₹0 is a fact. A missing figure is not, and must not look like one.
    expect(inr(null)).toBe("—");
    expect(inr(undefined)).toBe("—");
    expect(inr(NaN)).toBe("—");
    expect(inr(0)).toBe("₹0");
  });
});

describe("money", () => {
  const m = { paise: 82400000, rupees: 824000, display: "₹8,24,000", compact: "₹8.24 L" };
  it("prefers the server's own rendering", () => {
    expect(money(m)).toBe("₹8,24,000");
    expect(money(m, true)).toBe("₹8.24 L");
  });
  it("handles a missing value", () => {
    expect(money(null)).toBe("—");
  });
  it("extracts paise from either shape", () => {
    expect(paiseOf(m)).toBe(82400000);
    expect(paiseOf(500)).toBe(500);
    expect(paiseOf(null)).toBe(0);
  });
});

describe("percentages and durations", () => {
  it("formats probabilities", () => {
    expect(pct(0.1734)).toBe("17%");
    expect(pct(0.1734, 1)).toBe("17.3%");
    expect(pct(null)).toBe("—");
  });
  it("signs a change explicitly", () => {
    expect(signedPct(0.052)).toBe("+5.2%");
    expect(signedPct(-0.052)).toBe("−5.2%");
  });
  it("always signs a day count, because +3 and −3 mean opposite things", () => {
    expect(days(22.4)).toBe("+22 days");
    expect(days(-3)).toBe("−3 days");
    expect(days(1)).toBe("+1 day");
  });
  it("formats weeks", () => {
    expect(weeks(5.25)).toBe("5.3 wk");
  });
});

describe("dates", () => {
  it("formats without a timezone shift", () => {
    // A bare ISO date parsed as UTC then rendered locally can land on the
    // previous day. The formatter pins midnight to avoid it.
    expect(shortDate("2026-11-07")).toBe("7 Nov");
    expect(longDate("2026-11-07")).toBe("7 Nov 2026");
  });
  it("handles missing dates", () => {
    expect(shortDate(null)).toBe("—");
    expect(longDate(undefined)).toBe("—");
  });
  it("describes relative days from a reference", () => {
    expect(relDays("2026-11-07", "2026-11-07")).toBe("today");
    expect(relDays("2026-11-08", "2026-11-07")).toBe("tomorrow");
    expect(relDays("2026-11-20", "2026-11-07")).toBe("in 13 days");
    expect(relDays("2026-11-01", "2026-11-07")).toBe("6 days ago");
  });
});

describe("direction — colour is never the only signal", () => {
  it("pairs every tone with a glyph and a label", () => {
    for (const d of [direction(100), direction(-100), direction(0),
                     direction(100, "lower"), direction(-100, "lower")]) {
      expect(d.glyph).toBeTruthy();
      expect(d.label).toBeTruthy();
    }
  });
  it("knows that lower is better for a risk metric", () => {
    expect(direction(-100, "lower").tone).toBe("gain");
    expect(direction(100, "lower").tone).toBe("loss");
    expect(direction(100, "higher").tone).toBe("gain");
  });
  it("treats no change as neutral", () => {
    expect(direction(0).tone).toBe("neutral");
  });
});

describe("the three states", () => {
  it("defines all three with a question and a blurb", () => {
    for (const k of ["actual", "predicted", "simulated"] as const) {
      expect(STATE_META[k].label).toBeTruthy();
      expect(STATE_META[k].question).toMatch(/\?$/);
      expect(STATE_META[k].blurb).toBeTruthy();
      expect(STATE_META[k].color).toBeTruthy();
    }
  });
  it("gives each state a distinct colour", () => {
    const colours = new Set(["actual", "predicted", "simulated"].map(
      (k) => (STATE_META as any)[k].color));
    expect(colours.size).toBe(3);
  });
  it("says a simulation is not a record", () => {
    expect(STATE_META.simulated.blurb.toLowerCase()).toContain("ledger");
  });
});

describe("titleCase", () => {
  it("humanises an enum value", () => {
    expect(titleCase("customer_receipt")).toBe("Customer Receipt");
    expect(titleCase("gst_payment")).toBe("Gst Payment");
  });
});
