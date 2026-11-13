import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render } from "@testing-library/react";

vi.mock("@/lib/use-api", () => ({
  useApi: (path: string) => {
    if (path === "/api/twin/state") {
      return {
        loading: false,
        error: null,
        reload: () => {},
        data: {
          versions: { actual: 1, predicted: 1, ledger_fingerprint: "abc", last_updated: "2026-11-13T00:00:00Z" },
          financial_state: {
            available_liquidity: { paise: -100000, rupees: -1000, display: "-₹1,000", compact: "-₹1K" },
            receivables: { paise: 0, rupees: 0, display: "₹0", compact: "₹0" },
            payables: { paise: 0, rupees: 0, display: "₹0", compact: "₹0" },
          },
          forecast_summary: { runway_weeks_p50: 0, runway_weeks_p10: 0 },
          customer_state: [],
          supplier_state: [],
          operational_state: { missing: [], note: "" },
          data_quality: { score: 50, band: "Fair", verified_share: 0, reconciled_share: 0, staleness_days: 0 },
        },
      };
    }
    if (path === "/api/twin/graph") {
      return {
        loading: false,
        error: null,
        reload: () => {},
        data: {
          nodes: [
            { id: "biz:1", type: "business", label: "Zero Debug Works", value: 100 },
            { id: "acct:1", type: "account", label: "HDFC Overdraft", value: -500000 },
          ],
          edges: [{ source: "acct:1", target: "biz:1", meta: { overdue_share: 0 } }],
          insights: [],
        },
      };
    }
    return { loading: false, error: null, data: null, reload: () => {} };
  },
}));

import TwinPage from "@/app/app/twin/page";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("TwinPage GraphView negative/empty values", () => {
  it("renders without NaN attribute React warnings when an account balance is negative", () => {
    const nanErrors: string[] = [];
    const origErr = console.error;
    vi.spyOn(console, "error").mockImplementation((...args: any[]) => {
      const msg = args.map((a) => String(a)).join(" ");
      if (msg.includes("NaN")) nanErrors.push(msg);
      origErr.apply(console, args);
    });

    render(<TwinPage />);
    expect(nanErrors).toEqual([]);
  });
});
