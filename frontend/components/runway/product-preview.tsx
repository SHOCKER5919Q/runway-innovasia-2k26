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
   genuinely redraws ACTUAL (blue, solid, one point — the as-of week),
   PREDICTED (forest band) and SIMULATED (amber, dashed) in one frame.

   Figures: the synthetic wholesale distributor shipped with the demo seed,
   copied from the engine's own output (see the note above WEEK_STARTS).
   Nothing here is invented for the marketing page.
   ───────────────────────────────────────────────────────────────────────── */

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight, CircleDollarSign, GitBranch, Layers, ShieldAlert, Wallet,
} from "lucide-react";
import { motion } from "motion/react";
import { CashBandChart, BreachBars, HealthGauge, type CashSeries } from "./charts";
import { Delta, Evidence, Panel, Provenance, Stat, StateBadge } from "./primitives";
import { Reveal } from "./motion";
import { EASE_OUT } from "./motion";
import { inr, weeks as fmtWeeks, pct } from "@/lib/format";

/* ── the demo tenant's thirteen-week board ───────────────────── */

const L = (lakh: number) => Math.round(lakh * 100_000 * 100); // ₹ lakh → paise

/* Every figure below is copied from the running engine for demo scenario B
   (Sri Lakshmi Industrial Supplies) as of 2026-11-07, engine 0.9.0, 4,000
   paths, seed 20260101: GET /api/overview, /api/risk, /api/customers and
   POST /api/scenarios/quick-run. If the seed or the engine changes, re-pull
   them; do not hand-tune them. Week 0 is the as-of date (one actual point). */
const WEEK_STARTS = [
  "2026-11-07", "2026-11-14", "2026-11-21", "2026-11-28", "2026-12-05",
  "2026-12-12", "2026-12-19", "2026-12-26", "2027-01-02", "2027-01-09",
  "2027-01-16", "2027-01-23", "2027-01-30", "2027-02-06",
];

/** Cash after lien-marked balances (the forecast's opening point). */
const AVAILABLE_CASH = 47_722_173; // ₹4,77,221 — also net of committed payments
const HEALTH_TODAY = 72.8;

const BASE: CashSeries = {
  week_starts: WEEK_STARTS,
  p50: [9.07, 16.86, 21.02, 26.07, 23.55, 19.65, 18.99, 19.58, 23.46, 25.38, 28.27, 25.22, 27.47, 27.30].map(L),
  p10: [9.07, 6.48, 6.71, 10.34, 8.49, 6.41, 5.07, 4.77, 7.24, 8.94, 11.96, 9.36, 12.18, 12.53].map(L),
  p90: [9.07, 32.39, 35.49, 38.44, 36.27, 33.49, 33.94, 36.23, 40.44, 42.93, 45.60, 42.05, 44.45, 43.72].map(L),
  safety_buffer_paise: L(3),
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
  cvarLakh: number;
  note: string;
};

const SCENARIOS: Scenario[] = [
  {
    id: "baseline",
    label: "Baseline",
    lever: "No lever pulled",
    overlay: null,
    runwayP10: 4.85,
    breach: 0.2175,
    breachWeeks: [0.022, 0.043, 0.020, 0.045, 0.069, 0.075, 0.081, 0.053, 0.040, 0.023, 0.046, 0.028, 0.025],
    cvarLakh: 12.34,
    note: "The forecast as the ledger stands. The P10 path comes closest to the buffer in the week of 26 Dec.",
  },
  {
    id: "supplier",
    label: "Pay suppliers 7 days later",
    lever: "supplier_terms +7d, MSMED respected",
    overlay: {
      p50: [9.07, 16.89, 21.84, 26.13, 23.61, 19.80, 18.99, 19.58, 23.46, 25.38, 28.26, 25.22, 27.47, 27.30].map(L),
      p10: [9.07, 6.49, 7.54, 10.36, 8.56, 6.56, 5.07, 4.77, 7.24, 8.94, 11.96, 9.36, 12.18, 12.53].map(L),
    },
    runwayP10: 4.98,
    breach: 0.215,
    breachWeeks: [0.021, 0.035, 0.019, 0.045, 0.068, 0.075, 0.081, 0.053, 0.040, 0.023, 0.046, 0.028, 0.025],
    cvarLakh: 12.31,
    note: "Almost no headroom: eight of ten suppliers are micro or small, so MSMED §15 protects their invoices. Only 2 bills worth ₹1,08,854 can move.",
  },
  {
    id: "concentration",
    label: "Largest customer pays 30 days late",
    lever: "payment_delay ABC Distributors +30d",
    overlay: {
      p50: [9.07, 10.20, 9.83, 10.48, 6.00, 2.21, 2.39, 3.95, 8.13, 11.21, 16.02, 15.20, 21.00, 23.58].map(L),
      p10: [9.07, 4.02, 1.58, 2.19, -3.65, -10.10, -13.14, -13.25, -10.12, -7.37, -2.70, -3.31, 2.19, 6.16].map(L),
    },
    runwayP10: 1.46,
    breach: 0.7298,
    breachWeeks: [0.060, 0.150, 0.124, 0.354, 0.525, 0.518, 0.468, 0.354, 0.288, 0.185, 0.198, 0.111, 0.069],
    cvarLakh: 28.56,
    note: "One customer is 28.5% of last year's sales and owes ₹40.8 L across 43 open invoices. The P10 path goes below zero in week four.",
  },
];

/* ── the section ─────────────────────────────────────────────── */

export function ProductPreview() {
  const [i, setI] = useState(0);
  const s = SCENARIOS[i];
  const base = SCENARIOS[0];
  const simulated = s.overlay !== null;

  return (
    <section id="product" className="relative mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
      <Reveal y={18}>
        <div className="mx-auto max-w-3xl text-center">
          <p className="atelier-eyebrow text-primary">04 / The product</p>
          <h2 className="mt-4 font-editorial text-[clamp(2.3rem,4.8vw,4rem)] leading-[1.05] text-balance">
            This is the real screen, not a picture of one.
          </h2>
          <p className="mx-auto mt-5 max-w-xl text-pretty text-[15px] leading-relaxed text-muted-foreground">
            Pull a lever. The amber line is a simulation sharing a random seed with
            the baseline, so the gap between the two is the decision and not noise.
          </p>
        </div>
      </Reveal>

      {/* the product frame — 16px, DESIGN.md's xl radius */}
      <Reveal delay={0.1} y={18}>
        <div className="atelier-frame mt-12">
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
              as of 7 Nov 2026
            </span>
          </div>

          {/* the lever rail */}
          <div className="flex flex-wrap items-center gap-2 border-b border-line bg-card px-4 py-3">
            <span className="mr-1 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
              <GitBranch className="size-3.5" aria-hidden /> Lever
            </span>
            {SCENARIOS.map((sc, n) => (
              <button
                key={sc.id}
                onClick={() => setI(n)}
                aria-pressed={n === i}
                className={`rounded-full px-3.5 py-1.5 text-[12px] font-semibold transition-colors ${
                  n === i
                    ? "bg-forest text-white"
                    : "bg-paper-2 text-ink-2 hover:text-ink"
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
                value={inr(AVAILABLE_CASH, { compact: true })}
                sub="Reconciled across 3 accounts"
                icon={<Wallet className="size-4" />}
                state="actual"
                footer={
                  <span className="font-mono text-[10px] text-muted-foreground">
                    1,864 txns
                  </span>
                }
              />
              <Stat
                label="Runway (P10)"
                value={fmtWeeks(s.runwayP10)}
                sub={simulated ? "Against a ₹3.00L buffer" : "Pessimistic decile"}
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
              title="Health · today"
              description="Scored on the ledger, so a scenario does not change it."
              bodyClass="grid place-items-center p-3"
            >
              <motion.div
                key={s.id}
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.45, ease: EASE_OUT }}
              >
                <HealthGauge score={HEALTH_TODAY} size={128} />
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
                  { label: "Liquidity CVaR₉₅", value: inr(L(s.cvarLakh), { compact: true }) },
                  { label: "Receivables outstanding", value: inr(L(100.33), { compact: true }) },
                  { label: "MSMED-exposed payables", value: inr(L(28.37), { compact: true }) },
                ]}
              />
            </Panel>
          </div>

          {/* provenance strip — the app shows one on every computed screen */}
          <div className="border-t border-border px-4 py-2.5">
            <Provenance>
              ledger fingerprint <code className="font-mono">660ab0d5…</code> · 4,000 paths ·
              seed shared with baseline · split-conformal P10–P90, 84% empirical coverage ·
              {simulated ? " nothing written to the ledger" : " no scenario applied"}
            </Provenance>
          </div>
        </div>
      </Reveal>

      <Reveal delay={0.15} y={18}>
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
      </Reveal>
    </section>
  );
}

export default ProductPreview;
