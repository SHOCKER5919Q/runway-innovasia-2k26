"use client";

/* ─────────────────────────────────────────────────────────────────────────
   The product, on the landing page.

   DESIGN.md: "Let real product UI be the protagonist of every marketing
   section." So this is not a screenshot and not a drawing of a dashboard.
   It mounts the same components the application mounts — Stat, Panel,
   StateBadge, Delta, Evidence, CashBandChart, BreachBars, HealthGauge —
   against the same figures the demo tenant carries. If a chart regresses
   in the app, it regresses here too, which is the point.

   It is also the only honest way to demonstrate the three-state rule
   without asking a visitor to log in first: the scenario switch below
   genuinely redraws ACTUAL (cyan, solid, one point — the as-of week),
   PREDICTED (lime band) and SIMULATED (amber, dashed) in one frame.

   Figures: the synthetic wholesale distributor shipped with the demo seed,
   rounded to the paise the ledger actually stores. Nothing here is invented
   for the marketing page — the ticker above reads the same numbers.
   ───────────────────────────────────────────────────────────────────────── */

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight, CircleDollarSign, GitBranch, Layers, ShieldAlert, Wallet,
} from "lucide-react";
import { motion } from "motion/react";
import { CashBandChart, BreachBars, HealthGauge, type CashSeries } from "./charts";
import { Delta, Evidence, Panel, Provenance, Stat, StateBadge } from "./primitives";
import { Rise } from "./bits";
import { EASE_OUT } from "./motion";
import { inr, weeks as fmtWeeks, pct } from "@/lib/format";

/* ── the demo tenant's thirteen-week board ───────────────────── */

const L = (lakh: number) => Math.round(lakh * 100_000 * 100); // ₹ lakh → paise

const WEEK_STARTS = [
  "2026-03-02", "2026-03-09", "2026-03-16", "2026-03-23", "2026-03-30",
  "2026-04-06", "2026-04-13", "2026-04-20", "2026-04-27", "2026-05-04",
  "2026-05-11", "2026-05-18", "2026-05-25",
];

const BASE: CashSeries = {
  week_starts: WEEK_STARTS,
  p50: [4.77, 6.10, 7.35, 6.90, 8.30, 9.55, 11.20, 10.40, 12.10, 13.80, 15.20, 14.60, 16.90].map(L),
  p10: [4.77, 4.55, 4.10, 3.52, 3.00, 2.41, 1.95, 1.60, 1.88, 2.30, 2.85, 2.60, 3.20].map(L),
  p90: [4.77, 8.00, 11.30, 11.90, 15.10, 18.40, 21.60, 20.90, 24.20, 26.80, 29.40, 28.70, 32.10].map(L),
  safety_buffer_paise: L(2.5),
};

type Scenario = {
  id: string;
  label: string;
  lever: string;
  /** null = baseline, nothing simulated */
  overlay: { p50: number[]; p10: number[] } | null;
  runwayP10: number;
  breach: number;
  breachWeeks: number[];
  health: number;
  note: string;
};

const SCENARIOS: Scenario[] = [
  {
    id: "baseline",
    label: "Baseline",
    lever: "No lever pulled",
    overlay: null,
    runwayP10: 4.85,
    breach: 0.17,
    breachWeeks: [0.01, 0.02, 0.05, 0.09, 0.14, 0.17, 0.16, 0.15, 0.11, 0.08, 0.06, 0.07, 0.05],
    health: 72.8,
    note: "The forecast as the ledger stands. P10 touches the buffer in week five.",
  },
  {
    id: "supplier",
    label: "Pay suppliers 7 days later",
    lever: "supplier_credit_days +7",
    overlay: {
      p50: [4.77, 7.65, 9.00, 8.60, 9.95, 11.10, 12.60, 11.70, 13.20, 14.70, 15.90, 15.20, 17.30].map(L),
      p10: [4.77, 6.05, 5.70, 5.15, 4.60, 4.05, 3.55, 3.20, 3.35, 3.65, 4.05, 3.80, 4.25].map(L),
    },
    runwayP10: 13.0,
    breach: 0.04,
    breachWeeks: [0.00, 0.00, 0.01, 0.02, 0.03, 0.04, 0.04, 0.04, 0.03, 0.02, 0.02, 0.02, 0.01],
    health: 79.1,
    note: "Legal headroom only — eleven of nineteen suppliers are micro or small, so MSMED §15 caps them at 45 days.",
  },
  {
    id: "concentration",
    label: "Largest customer pays 30 days late",
    lever: "ABC Distributors DSO +30",
    overlay: {
      p50: [4.77, 5.20, 5.05, 3.90, 4.40, 4.95, 6.20, 5.40, 7.30, 9.60, 11.40, 11.00, 13.60].map(L),
      p10: [4.77, 3.70, 2.55, 1.40, 0.55, -0.35, -0.95, -1.20, -0.60, 0.25, 0.95, 0.80, 1.60].map(L),
    },
    runwayP10: 2.6,
    breach: 0.58,
    breachWeeks: [0.02, 0.09, 0.24, 0.41, 0.52, 0.58, 0.57, 0.55, 0.47, 0.36, 0.28, 0.30, 0.22],
    health: 51.4,
    note: "One customer is 31.2% of the book. The overdraft is reached in week six, not week thirteen.",
  },
];

/* ── the section ─────────────────────────────────────────────── */

export default function ProductPreview() {
  const [i, setI] = useState(0);
  const s = SCENARIOS[i];
  const base = SCENARIOS[0];
  const simulated = s.overlay !== null;

  return (
    <section id="product" className="relative mx-auto max-w-7xl px-5 py-28 sm:px-8 sm:py-36">
      <Rise>
        <div className="mx-auto max-w-3xl text-center">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-primary">
            The product
          </p>
          <h2 className="mt-4 font-display text-[clamp(1.8rem,4vw,2.9rem)] font-semibold leading-[1.1] tracking-[-0.025em] text-balance">
            This is the real screen, not a picture of one.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-pretty text-[15px] leading-relaxed text-muted-foreground">
            Pull a lever. The amber line is a simulation sharing a random seed with
            the baseline, so the gap between the two is the decision and not noise.
          </p>
        </div>
      </Rise>

      {/* the product frame — 16px, DESIGN.md's xl radius */}
      <Rise delay={0.1}>
        <div className="mt-14 overflow-hidden rounded-2xl border border-border bg-card shadow-[var(--shadow-float)]">
          {/* window chrome */}
          <div className="flex items-center gap-3 border-b border-border bg-surface px-4 py-2.5">
            <div className="flex items-center gap-1.5" aria-hidden>
              <span className="size-2.5 rounded-full bg-border-strong" />
              <span className="size-2.5 rounded-full bg-border-strong" />
              <span className="size-2.5 rounded-full bg-border-strong" />
            </div>
            <div className="mx-auto flex items-center gap-2 rounded-md border border-border bg-background px-3 py-1">
              <Layers className="size-3 text-primary" aria-hidden />
              <span className="font-mono text-[11px] text-muted-foreground">
                runway.app/app/scenarios
              </span>
            </div>
            <span className="hidden font-mono text-[10px] text-muted-foreground/60 sm:inline">
              as of 2 Mar 2026
            </span>
          </div>

          {/* the lever rail */}
          <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
            <span className="mr-1 flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              <GitBranch className="size-3.5" aria-hidden /> Lever
            </span>
            {SCENARIOS.map((sc, n) => (
              <button
                key={sc.id}
                onClick={() => setI(n)}
                aria-pressed={n === i}
                className={`relative rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                  n === i
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:border-border-strong hover:text-foreground"
                }`}
              >
                {sc.label}
              </button>
            ))}
            <code className="ml-auto hidden font-mono text-[10px] text-muted-foreground/70 lg:inline">
              {s.lever}
            </code>
          </div>

          {/* the board */}
          <div className="grid gap-4 p-4 lg:grid-cols-12">
            {/* stat column */}
            <div className="grid gap-4 sm:grid-cols-2 lg:col-span-4 lg:grid-cols-1">
              <Stat
                label="Available cash"
                value={inr(BASE.p50[0], { compact: true })}
                sub="Reconciled across 4 accounts"
                icon={<Wallet className="size-4" />}
                state="actual"
                footer={
                  <span className="font-mono text-[10px] text-muted-foreground">
                    1,842 txns
                  </span>
                }
              />
              <Stat
                label="Runway (P10)"
                value={fmtWeeks(s.runwayP10)}
                sub={simulated ? "Against a ₹2.50L buffer" : "Pessimistic decile"}
                icon={<CircleDollarSign className="size-4" />}
                state={simulated ? "simulated" : "predicted"}
                tone={s.runwayP10 < 6 ? "loss" : "gain"}
                footer={
                  simulated ? (
                    <Delta value={+(s.runwayP10 - base.runwayP10).toFixed(2)} suffix=" wk" />
                  ) : undefined
                }
              />
              <Stat
                label="Buffer breach probability"
                value={pct(s.breach)}
                sub="Any week in the horizon"
                icon={<ShieldAlert className="size-4" />}
                state={simulated ? "simulated" : "predicted"}
                tone={s.breach > 0.3 ? "loss" : s.breach > 0.1 ? "warn" : "gain"}
                footer={
                  simulated ? (
                    <Delta
                      value={+((s.breach - base.breach) * 100).toFixed(1)}
                      suffix="pp"
                      betterWhen="lower"
                    />
                  ) : undefined
                }
              />
            </div>

            {/* the chart */}
            <Panel
              className="lg:col-span-8"
              title="Thirteen-week cash position"
              description="One point actual, a predicted P10–P90 band, and the simulation on top."
              actions={
                <div className="flex items-center gap-1.5">
                  <StateBadge state="actual" />
                  <StateBadge state="predicted" />
                  {simulated && <StateBadge state="simulated" />}
                </div>
              }
              bodyClass="p-3"
            >
              <CashBandChart
                series={BASE}
                scenario={s.overlay}
                scenarioLabel={s.label}
                actualTo={0}
                height={272}
              />
            </Panel>

            {/* breach curve */}
            <Panel
              className="lg:col-span-5"
              title="Breach probability by week"
              description="Share of 4,000 correlated paths closing below the buffer."
              bodyClass="p-3"
            >
              <BreachBars weeks={WEEK_STARTS} probs={s.breachWeeks} height={142} />
            </Panel>

            {/* health + evidence */}
            <Panel
              className="lg:col-span-3"
              title="Health"
              bodyClass="grid place-items-center p-3"
            >
              <motion.div
                key={s.id}
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.45, ease: EASE_OUT }}
              >
                <HealthGauge score={s.health} size={128} />
              </motion.div>
            </Panel>

            <Panel
              className="lg:col-span-4"
              title="What moved"
              description={s.note}
              bodyClass="p-4"
            >
              <Evidence
                dense
                items={[
                  { label: "Weekly min cash (P10)", value: inr(Math.min(...(s.overlay?.p10 ?? BASE.p10)), { compact: true }) },
                  { label: "Liquidity CVaR₉₅", value: inr(L(s.id === "concentration" ? 31.4 : s.id === "supplier" ? 3.9 : 13.67), { compact: true }) },
                  { label: "Receivables outstanding", value: inr(L(100.33), { compact: true }) },
                  { label: "MSMED-exposed payables", value: inr(L(48.59), { compact: true }) },
                ]}
              />
            </Panel>
          </div>

          {/* provenance strip — the app shows one on every computed screen */}
          <div className="border-t border-border px-4 py-2.5">
            <Provenance>
              ledger fingerprint <code className="font-mono">8f2c41ab…</code> · 4,000 paths ·
              seed shared with baseline · split-conformal P10–P90, 84% empirical coverage ·
              {simulated ? " nothing written to the ledger" : " no scenario applied"}
            </Provenance>
          </div>
        </div>
      </Rise>

      <Rise delay={0.15}>
        <div className="mt-8 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-center">
          <p className="text-sm text-muted-foreground">
            Twenty-one screens behind the login do this against your own ledger.
          </p>
          <Link
            href="/login"
            className="group inline-flex items-center gap-1.5 text-sm font-semibold text-primary"
          >
            Open the scenario lab
            <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
          </Link>
        </div>
      </Rise>
    </section>
  );
}
