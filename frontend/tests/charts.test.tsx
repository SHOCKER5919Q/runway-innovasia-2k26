import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children, width, height }: any) => {
      const w = typeof width === "number" ? width : 600;
      const h = typeof height === "number" ? height : 240;
      return (
        <div style={{ width: w, height: h }}>
          {React.isValidElement(children)
            ? React.cloneElement(children as React.ReactElement<any>, { width: w, height: h })
            : children}
        </div>
      );
    },
  };
});

import {
  AgeingBars, BreachBars, CashBandChart, ConcentrationPie,
  FlowBars, HealthGauge, RiskScatter, Spark,
} from "@/components/runway/charts";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("charts — zero, empty, and non-finite edge cases", () => {
  it("renders all charts cleanly without NaN attribute React warnings", () => {
    const errors: string[] = [];
    const origErr = console.error;
    vi.spyOn(console, "error").mockImplementation((...args: any[]) => {
      const msg = args.map((a) => String(a)).join(" ");
      if (msg.includes("NaN") || msg.includes("Received")) {
        errors.push(msg);
      }
      origErr.apply(console, args);
    });

    const weeks = ["2026-11-13", "2026-11-20", "2026-11-27", "2026-12-04"];
    const zeros = [0, 0, 0, 0];

    render(
      <div>
        <CashBandChart
          series={{ week_starts: weeks, p10: zeros, p50: zeros, p90: zeros, safety_buffer_paise: 0 }}
          scenario={{ p50: zeros, p10: zeros }}
          actualTo={0}
        />
        <CashBandChart
          series={{ week_starts: [], p10: [], p50: [], p90: [], safety_buffer_paise: 0 }}
        />
        <FlowBars weeks={weeks} inflow={zeros} outflow={zeros} />
        <FlowBars weeks={[]} inflow={[]} outflow={[]} />
        <AgeingBars
          buckets={[
            { label: "Not due", amount_paise: 0, count: 0, share: 0 },
            { label: "1-30 days", amount_paise: 0, count: 0, share: 0 },
          ]}
        />
        <AgeingBars buckets={[]} />
        <ConcentrationPie items={[]} />
        <ConcentrationPie items={[{ name: "Zero", volume_paise: 0, share: 0 }]} />
        <HealthGauge score={0} />
        <HealthGauge score={Number.NaN} />
        <Spark data={[]} />
        <Spark data={zeros} />
        <BreachBars weeks={weeks} probs={[0, 0, 0]} />
        <BreachBars weeks={[]} probs={[]} />
        <RiskScatter points={[]} />
        <RiskScatter points={[{ name: "A", delay: 0, exposure: 0, reliability: 0 }]} />
      </div>
    );

    expect(errors).toEqual([]);
  });
});
