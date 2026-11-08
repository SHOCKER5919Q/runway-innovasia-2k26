/**
 * UI primitives.
 *
 * The assertions here are mostly accessibility and the "colour is never the
 * only channel" rule, because those are the properties that silently rot.
 */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import {
  Delta, Evidence, EmptyState, ErrorState, LevelPill, Panel, Provenance,
  RiskBand, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";

afterEach(cleanup);

describe("StateBadge", () => {
  it.each(["actual", "predicted", "simulated"] as const)("renders %s", (s) => {
    render(<StateBadge state={s} />);
    expect(screen.getByText(/Actual|Predicted|Simulated/)).toBeTruthy();
  });

  it("carries the explanation as a tooltip", () => {
    const { container } = render(<StateBadge state="simulated" />);
    const el = container.querySelector("[title]");
    expect(el?.getAttribute("title")?.toLowerCase()).toContain("ledger");
  });

  it("renders nothing for an unknown state rather than guessing", () => {
    const { container } = render(<StateBadge state="nonsense" />);
    expect(container.firstChild).toBeNull();
  });
});

describe("Delta — colour is never the only signal", () => {
  it("always includes a screen-reader label", () => {
    render(<Delta value={2.4} />);
    expect(screen.getByText("improved")).toBeTruthy();
  });

  it("labels a worse value as worse", () => {
    render(<Delta value={-2.4} />);
    expect(screen.getByText("worse")).toBeTruthy();
  });

  it("inverts the reading when lower is better", () => {
    render(<Delta value={-2.4} betterWhen="lower" />);
    expect(screen.getByText("improved")).toBeTruthy();
  });

  it("shows the magnitude without its sign, since the glyph carries it", () => {
    render(<Delta value={-2.4} suffix=" wk" />);
    expect(screen.getByText(/2\.4 wk/)).toBeTruthy();
  });
});

describe("Stat", () => {
  it("renders a label and a value", () => {
    render(<Stat label="Available cash" value="₹4,77,221" />);
    expect(screen.getByText("Available cash")).toBeTruthy();
    expect(screen.getByText("₹4,77,221")).toBeTruthy();
  });

  it("exposes the hint as a tooltip", () => {
    const { container } = render(
      <Stat label="Runway" value="13 wk" hint="Weeks before the buffer is breached" />);
    expect(container.querySelector("[title]")?.getAttribute("title"))
      .toContain("buffer");
  });

  it("becomes a button when it is clickable", () => {
    render(<Stat label="Receivables" value="₹1 Cr" onClick={() => {}} />);
    expect(screen.getByRole("button")).toBeTruthy();
  });

  it("stays a plain element when it is not", () => {
    render(<Stat label="Receivables" value="₹1 Cr" />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("LevelPill and RiskBand", () => {
  it.each([
    ["critical", "Critical"], ["warning", "Warning"],
    ["watch", "Watch"], ["info", "Info"],
  ])("renders %s with a word, not just a colour", (level, label) => {
    render(<LevelPill level={level} />);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it("falls back to Info for an unknown level", () => {
    render(<LevelPill level="unheard-of" />);
    expect(screen.getByText("Info")).toBeTruthy();
  });

  it("names the risk band in words", () => {
    render(<RiskBand band="high" />);
    expect(screen.getByText("high")).toBeTruthy();
  });
});

describe("Evidence", () => {
  it("renders a definition list so the pairing is semantic", () => {
    const { container } = render(
      <Evidence items={[{ label: "Breach probability", value: "17%" }]} />);
    expect(container.querySelector("dl")).toBeTruthy();
    expect(container.querySelector("dt")?.textContent).toBe("Breach probability");
    expect(container.querySelector("dd")?.textContent).toBe("17%");
  });

  it("renders nothing when there is nothing to show", () => {
    const { container } = render(<Evidence items={[]} />);
    expect(container.firstChild).toBeNull();
  });
});

describe("Panel and SectionHeader", () => {
  it("uses a section landmark with a heading", () => {
    const { container } = render(<Panel title="Cash flow outlook">body</Panel>);
    expect(container.querySelector("section")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Cash flow outlook" })).toBeTruthy();
  });

  it("renders without a header when it has no title", () => {
    const { container } = render(<Panel>body</Panel>);
    expect(container.querySelector("header")).toBeNull();
  });

  it("gives SectionHeader a real heading element", () => {
    render(<SectionHeader title="Scenario Lab" description="Test a decision" />);
    expect(screen.getByRole("heading", { name: "Scenario Lab" })).toBeTruthy();
  });
});

describe("error and empty states", () => {
  it("announces an error to assistive technology", () => {
    render(<ErrorState message="Network unreachable" />);
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByText("Network unreachable")).toBeTruthy();
  });

  it("offers a retry only when one is possible", () => {
    const { rerender } = render(<ErrorState message="x" />);
    expect(screen.queryByText("Retry")).toBeNull();
    rerender(<ErrorState message="x" onRetry={() => {}} />);
    expect(screen.getByText("Retry")).toBeTruthy();
  });

  it("explains an empty state rather than showing a blank panel", () => {
    render(<EmptyState title="No scenarios yet" description="Build your first one" />);
    expect(screen.getByText("No scenarios yet")).toBeTruthy();
    expect(screen.getByText("Build your first one")).toBeTruthy();
  });
});

describe("Provenance", () => {
  it("renders the note so a figure can always be questioned", () => {
    render(<Provenance>Estimated from the trailing ledger.</Provenance>);
    expect(screen.getByText(/Estimated from the trailing ledger/)).toBeTruthy();
  });
});
