/**
 * The shared-passport renderer.
 *
 * This component is what an outside lender reads, so the assertions here are
 * about never misrepresenting a figure: a fraction must not be printed as if
 * it were a count, money must not lose its denomination, and a shape the
 * backend adds later must degrade to something readable instead of throwing.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ReportValue, VerificationChip } from "@/components/runway/report-value";

afterEach(cleanup);

const money = (paise: number) => ({ paise, rupees: paise / 100, display: "", compact: "" });

describe("money", () => {
  it("renders a Money object as rupees, not as a paise integer", () => {
    render(<ReportValue value={money(47722100)} />);
    // ₹4,77,221 — the Indian grouping, and never the raw 47722100
    expect(screen.getByText(/4,77,221/)).toBeTruthy();
    expect(screen.queryByText(/47722100/)).toBeNull();
  });

  it("renders nested Money inside a group", () => {
    render(<ReportValue value={{ available: money(47722100), cash: money(10000000) }} />);
    expect(screen.getByText("Available")).toBeTruthy();
    expect(screen.getByText(/4,77,221/)).toBeTruthy();
    expect(screen.getByText(/1,00,000/)).toBeTruthy();
  });
});

describe("numbers are read through their key", () => {
  it("prints a share as a percentage, not as a bare fraction", () => {
    render(<ReportValue value={{ overdue_share: 0.312 }} />);
    expect(screen.getByText("31.2%")).toBeTruthy();
  });

  it("prints a probability as a percentage", () => {
    render(<ReportValue value={{ breach_probability: 0.17 }} />);
    expect(screen.getByText("17.0%")).toBeTruthy();
  });

  it("prints a score out of a hundred so it cannot read as money", () => {
    render(<ReportValue value={{ score: 72.8 }} />);
    expect(screen.getByText("72.8 / 100")).toBeTruthy();
  });

  it("prints a delay in days", () => {
    render(<ReportValue value={{ mean_delay_days: 22.4 }} />);
    expect(screen.getByText(/22\.4\s*days?/)).toBeTruthy();
  });

  it("leaves a plain count alone", () => {
    render(<ReportValue value={{ paths: 4000 }} />);
    expect(screen.getByText("4,000")).toBeTruthy();
  });
});

describe("row lists", () => {
  it("renders an array of records as a table with humanised headers", () => {
    render(<ReportValue value={[
      { customer: "ABC Distributors", mean_delay_days: 22.4, risk_band: "elevated" },
      { customer: "Orient Traders", mean_delay_days: 3.1, risk_band: "low" },
    ]} />);
    expect(screen.getByRole("table")).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Customer" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Mean delay days" })).toBeTruthy();
    expect(screen.getByText("ABC Distributors")).toBeTruthy();
    // a snake_case enum is title-cased rather than shown raw
    expect(screen.getByText("Elevated")).toBeTruthy();
  });

  it("lines up rows whose keys differ", () => {
    render(<ReportValue value={[{ a: 1 }, { b: 2 }]} />);
    expect(screen.getAllByRole("columnheader")).toHaveLength(2);
    // the missing cell is an em dash, not "undefined"
    expect(screen.queryByText("undefined")).toBeNull();
  });
});

describe("empty and unknown shapes", () => {
  it("explains an empty measurement instead of showing an empty box", () => {
    render(<ReportValue value={[]} />);
    expect(screen.getByText(/once the first measurement lands/i)).toBeTruthy();
  });

  it("says a null section is unavailable", () => {
    render(<ReportValue value={null} />);
    expect(screen.getByText(/not available/i)).toBeTruthy();
  });

  it("renders a shape it has never seen without throwing", () => {
    expect(() =>
      render(<ReportValue value={{ future: { deeply: { nested: [1, 2, 3] } } }} />),
    ).not.toThrow();
  });
});

describe("VerificationChip", () => {
  it.each([
    ["verified_actual", "Verified actual"],
    ["model_prediction", "Model prediction"],
    ["mixed_verified_and_estimated", "Partly estimated"],
    ["measured", "Measured"],
  ])("labels %s in words", (kind, label) => {
    render(<VerificationChip kind={kind} />);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it("falls back to a readable label for an unknown kind", () => {
    render(<VerificationChip kind="some_new_basis" />);
    expect(screen.getByText("Some New Basis")).toBeTruthy();
  });
});
