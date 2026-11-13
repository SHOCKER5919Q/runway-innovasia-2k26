"use client";

/* ─────────────────────────────────────────────────────────────────────────
   RUNWAY / Grove — the marketing surface (Drive reference).

   The design decision is simple: the product is the illustration. There is no
   stock photography, no 3D glass, no generated screenshot. Every number in
   the hero and the bento grid is drawn from the same synthetic demo ledger the
   application reads, and the chart is the actual CashBandChart component.

   Motion is restrained to entrance reveals and one interactive lever. A
   financial product earns trust by being calm, not by being kinetic.
   ───────────────────────────────────────────────────────────────────────── */

import Link from "next/link";
import { useState, type ReactNode } from "react";
import { motion } from "motion/react";
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, Banknote, Brain,
  Check, ChevronDown, CircleDollarSign, Database, GitBranch, Landmark,
  Layers, LineChart, Lock, Menu, Play, Receipt, ShieldCheck, Sparkles,
  TrendingUp, Wallet, X,
} from "lucide-react";
import { Reveal, EASE_OUT } from "./motion";
import { Counter, Marquee } from "./bits";
import { CashBandChart, HealthGauge, Spark, type CashSeries } from "./charts";
import { StateBadge } from "./primitives";
import { ProductPreview } from "./product-preview";
import { Logo } from "./brand";
import { STATE_META } from "@/lib/format";
import { cn } from "@/lib/utils";

/* ── the demo tenant's numbers, in paise ──────────────────────────────── */
const L = (lakh: number) => Math.round(lakh * 100_000 * 100);
/* Copied from the running engine for demo scenario B as of 2026-11-07
   (engine 0.9.0, 4,000 paths, seed 20260101). Week 0 is the as-of date.
   Re-pull these from the API if the seed or engine changes; never hand-tune. */
const WEEKS = [
  "2026-11-07", "2026-11-14", "2026-11-21", "2026-11-28", "2026-12-05",
  "2026-12-12", "2026-12-19", "2026-12-26", "2027-01-02", "2027-01-09",
  "2027-01-16", "2027-01-23", "2027-01-30", "2027-02-06",
];
const HERO_SERIES: CashSeries = {
  week_starts: WEEKS,
  p50: [9.07, 16.86, 21.02, 26.07, 23.55, 19.65, 18.99, 19.58, 23.46, 25.38, 28.27, 25.22, 27.47, 27.30].map(L),
  p10: [9.07, 6.48, 6.71, 10.34, 8.49, 6.41, 5.07, 4.77, 7.24, 8.94, 11.96, 9.36, 12.18, 12.53].map(L),
  p90: [9.07, 32.39, 35.49, 38.44, 36.27, 33.49, 33.94, 36.23, 40.44, 42.93, 45.60, 42.05, 44.45, 43.72].map(L),
  safety_buffer_paise: L(3),
};
const SPARK = HERO_SERIES.p50;

const NAV_LINKS = [
  ["#why", "Why RUNWAY"],
  ["#instrument", "The instrument"],
  ["#states", "Three states"],
  ["#product", "Live demo"],
  ["#proof", "Proof"],
] as const;

export default function GroveLanding() {
  return (
    <div className="relative min-h-dvh overflow-x-clip bg-background rw-noise">
      <Nav />
      <main>
        <Hero />
        <DataTicker />
        <Positioning />
        <Instrument />
        <States />
        <ProductPreview />
        <DecisionStory />
        <Proof />
        <FAQ />
        <Closing />
      </main>
      <Footer />
    </div>
  );
}

/* ───────────────────────────── nav ───────────────────────────── */

function Nav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-50 border-b border-line/70 bg-paper/85 backdrop-blur-lg">
      <div className="mx-auto flex h-[72px] max-w-[1200px] items-center justify-between gap-4 px-5 sm:px-8">
        <Link href="/" className="shrink-0" aria-label="Runway home"><Logo /></Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main">
          {NAV_LINKS.map(([href, label]) => (
            <a key={href} href={href}
               className="rounded-full px-4 py-2 text-[15px] font-medium text-ink-2 transition hover:bg-card hover:text-ink hover:ring-1 hover:ring-line">
              {label}
            </a>
          ))}
        </nav>

        <div className="flex shrink-0 items-center gap-2">
          <Link href="/login"
                className="hidden px-4 py-2 text-[15px] font-semibold text-ink-2 hover:text-ink sm:block">
            Sign in
          </Link>
          <Link href="/login" className="btn btn-primary btn-sm hidden sm:inline-flex">
            Try the demo
          </Link>
          <button onClick={() => setOpen((v) => !v)}
                  className="grid size-11 place-items-center rounded-xl border border-line bg-card md:hidden"
                  aria-label={open ? "Close menu" : "Open menu"} aria-expanded={open}>
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-line bg-paper px-5 pb-6 pt-3 md:hidden" aria-label="Mobile">
          {NAV_LINKS.map(([href, label]) => (
            <a key={href} href={href} onClick={() => setOpen(false)}
               className="block border-b border-line py-3.5 text-[17px] font-medium">
              {label}
            </a>
          ))}
          <div className="mt-5 flex gap-3">
            <Link href="/login" onClick={() => setOpen(false)} className="btn btn-ghost flex-1">Sign in</Link>
            <Link href="/login" onClick={() => setOpen(false)} className="btn btn-primary flex-1">Try the demo</Link>
          </div>
        </nav>
      )}
    </header>
  );
}

/* ──────────────────────────── hero ───────────────────────────── */

function Hero() {
  return (
    <section className="grain relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 rw-aurora" aria-hidden />
      <div className="mx-auto max-w-[1200px] px-5 pb-24 pt-16 text-center sm:px-8 sm:pt-24">
        <motion.p
          initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: .65, ease: EASE_OUT }}
          className="rise mx-auto inline-flex items-center gap-2 rounded-full border border-line bg-card py-1.5 pl-2 pr-4 text-[13px] font-medium text-ink-2"
        >
          <span className="rounded-full bg-lime px-2.5 py-0.5 text-xs font-bold text-forest">New</span>
          Now tracks the MSME 45-day payment rule
        </motion.p>

        <motion.h1
          initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: .8, ease: EASE_OUT, delay: .08 }}
          className="display rise rise-2 mx-auto mt-7 max-w-4xl text-[clamp(2.6rem,7vw,5.2rem)]"
        >
          Know when cash gets tight, <em>weeks</em> before it does.
        </motion.h1>
        <motion.p
          initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: .8, ease: EASE_OUT, delay: .2 }}
          className="rise rise-3 mx-auto mt-6 max-w-xl text-[18px] leading-relaxed text-ink-2 text-pretty"
        >
          Runway reads your invoices, bank statements and GST dates, and shows where
          your balance is heading over the next 13 weeks. Then you can test a decision
          before you make it.
        </motion.p>
        <div className="rise rise-3 mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <Link href="/login" className="btn btn-primary h-[52px] px-7 text-[15px]">
            Open the live demo <ArrowRight className="size-4" />
          </Link>
          <a href="#product" className="btn btn-ghost h-[52px] px-7 text-[15px]">
            See how it works
          </a>
        </div>
        <p className="mt-4 text-sm text-ink-3">No sign-up. The demo logs you in with a sample business.</p>

        <Reveal delay={.15} y={24}>
          <div className="mt-16 text-left sm:mt-20">
            <HeroDashboard />
          </div>
        </Reveal>

        <div className="mx-auto mt-5 flex max-w-6xl flex-wrap items-center justify-between gap-3 text-[11px] text-ink-3">
          <span className="eyebrow">Fig. 01 — the actual overview screen</span>
          <span>Not a mockup. The same chart component the app mounts.</span>
        </div>
      </div>
    </section>
  );
}

function MiniStat({ label, value, note, state, tone = "neutral" }:
  { label: string; value: string; note: string; state: "actual" | "predicted"; tone?: "neutral" | "gain" | "warn" }) {
  const toneClass = tone === "gain" ? "text-fin-gain" : tone === "warn" ? "text-fin-warn" : "text-foreground";
  return (
    <div className="atelier-card p-3.5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-medium uppercase tracking-[.12em] text-muted-foreground">{label}</p>
        <StateBadge state={state} />
      </div>
      <p className={cn("mt-2 font-display text-xl font-semibold tracking-tight tnum", toneClass)}>{value}</p>
      <p className="mt-1 text-[10.5px] leading-snug text-muted-foreground">{note}</p>
    </div>
  );
}

function HeroDashboard() {
  const rail = [
    { icon: Layers, label: "Overview", on: true },
    { icon: Database, label: "State Centre" },
    { icon: TrendingUp, label: "Cash Runway" },
    { icon: GitBranch, label: "Scenario Lab" },
    { icon: Brain, label: "AI Copilot" },
  ];
  return (
    <div className="atelier-frame mx-auto mt-12 max-w-6xl text-left">
      {/* window chrome */}
      <div className="flex items-center gap-3 border-b border-border bg-surface px-4 py-2.5">
        <div className="flex items-center gap-1.5" aria-hidden>
          <span className="size-2.5 rounded-full bg-border-strong" />
          <span className="size-2.5 rounded-full bg-border-strong" />
          <span className="size-2.5 rounded-full bg-primary-bright" />
        </div>
        <div className="mx-auto flex items-center gap-2 rounded-md border border-border bg-card px-3 py-1">
          <Lock className="size-3 text-primary" aria-hidden />
          <span className="font-mono text-[10.5px] text-muted-foreground">runway.app / overview</span>
        </div>
        <span className="hidden font-mono text-[10px] text-muted-foreground/70 sm:inline">as of 7 Nov 2026</span>
      </div>

      <div className="grid lg:grid-cols-[188px_1fr]">
        {/* mini rail */}
        <div className="hidden flex-col border-r border-border bg-surface/70 p-3 lg:flex">
          <div className="px-2 pb-4"><Logo compact /></div>
          <p className="px-2 pb-1.5 text-[9px] font-semibold uppercase tracking-[.16em] text-muted-foreground/70">Today</p>
          <ul className="space-y-0.5">
            {rail.map(({ icon: Icon, label, on }) => (
              <li key={label}>
                <span className={cn("flex items-center gap-2 rounded-md px-2 py-1.5 text-[11px]",
                  on ? "bg-primary-soft font-medium text-primary" : "text-muted-foreground")}>
                  <Icon className="size-3.5" aria-hidden /> {label}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-auto rounded-lg border border-border bg-card p-2.5">
            <p className="text-[9px] uppercase tracking-wider text-muted-foreground">Data quality</p>
            <p className="mt-1 font-display text-lg font-semibold tnum">98<span className="text-xs text-muted-foreground">/100</span></p>
            <div className="mt-2 h-1 overflow-hidden rounded-full bg-surface">
              <div className="h-full w-[98%] rounded-full bg-primary-bright" />
            </div>
          </div>
        </div>

        {/* screen */}
        <div className="min-w-0 p-4 sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="atelier-eyebrow">Overview · Sharma Distributors</p>
              <h3 className="mt-1.5 font-editorial text-[28px] leading-tight sm:text-[34px]">
                Good morning, Amit.
              </h3>
              <p className="mt-1 text-[12px] text-muted-foreground">
                Here is what changed, what is likely, and the one decision worth making today.
              </p>
            </div>
            <span className="atelier-pill"><span className="size-1.5 rounded-full bg-fin-gain" /> Ledger reconciled</span>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <MiniStat label="Available cash" value="₹4,77,221" note="Across 3 accounts · actual" state="actual" />
            <MiniStat label="Receivables" value="₹1,00,32,867" note="102 invoices · ₹35.8L overdue" state="actual" tone="warn" />
            <MiniStat label="Payables" value="₹29,46,239" note="15 invoices · actual" state="actual" />
            <MiniStat label="Runway P10" value="4.85 wk" note="22% chance of buffer breach" state="predicted" tone="warn" />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[1.65fr_1fr]">
            <div className="atelier-card p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-[12px] font-semibold">Thirteen-week cash position</p>
                  <p className="mt-0.5 text-[10.5px] text-muted-foreground">4,000 paths · P10–P90 band · buffer ₹3.00 L</p>
                </div>
                <StateBadge state="predicted" />
              </div>
              <div className="mt-2 -ml-2">
                <CashBandChart series={HERO_SERIES} actualTo={0} height={208} />
              </div>
            </div>

            <div className="atelier-card flex flex-col p-4">
              <div className="flex items-center justify-between">
                <p className="atelier-eyebrow">Decision desk</p>
                <Sparkles className="size-3.5 text-primary" aria-hidden />
              </div>
              <h4 className="mt-2 font-editorial text-[21px] leading-tight">Negotiate a 30% advance</h4>
              <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground text-pretty">
                On the ₹15 L order, this cuts the cash tied up in the 51-day funding gap from ₹12.3 L to ₹7.8 L.
              </p>
              <dl className="mt-4 space-y-2 text-[11px]">
                {[
                  ["Minimum cash (P10)", "−₹12.2 L → −₹7.4 L"],
                  ["Breach probability", "60% → 42%"],
                  ["Scenario isolation", "Nothing written to ledger"],
                ].map(([k, v]) => (
                  <div key={k} className="flex items-start justify-between gap-3 border-b border-border/70 pb-2 last:border-0">
                    <dt className="text-muted-foreground">{k}</dt>
                    <dd className="text-right font-medium tnum">{v}</dd>
                  </div>
                ))}
              </dl>
              <Link href="/login" className="atelier-cta-dark mt-auto w-full pt-3"
                    style={{ marginTop: "auto", padding: ".7rem 1rem", fontSize: 12 }}>
                Review the scenario <ArrowRight className="size-3.5" />
              </Link>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-border pt-3 text-[10.5px] text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded bg-state-actual" /> Actual · solid</span>
            <span className="flex items-center gap-1.5"><span className="h-2 w-5 rounded bg-state-predicted-soft" /> Predicted · band</span>
            <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 rounded border-t-2 border-dashed border-state-simulated" /> Simulated · dashed</span>
            <span className="ml-auto font-mono">fingerprint 660ab0d5…</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────────────────── data ticker ───────────────────────── */

function DataTicker() {
  const rows = [
    ["Available cash", "₹4,77,221", "actual"],
    ["Receivables", "₹1,00,32,867", "actual"],
    ["Runway P10", "4.85 weeks", "predicted"],
    ["Breach probability", "22%", "predicted"],
    ["Liquidity CVaR₉₅", "₹12,33,721", "predicted"],
    ["ABC Distributors", "+22.4 days", "actual"],
    ["Health score", "72.8 / 100", "predicted"],
    ["MSMED exposed", "₹28,37,385", "actual"],
  ] as const;
  return (
    <div className="relative mt-20 border-y border-border bg-card/60 py-3.5 sm:mt-28">
      <Marquee speed={52}>
        {rows.map(([k, v, s]) => (
          <span key={k} className="flex items-center gap-2.5 whitespace-nowrap text-[11.5px]">
            <span className="text-muted-foreground">{k}</span>
            <span className={cn("font-mono tnum", s === "actual" ? "text-fin-info" : "text-primary")}>{v}</span>
            <span className="atelier-eyebrow atelier-eyebrow-sm">{s}</span>
            <span className="text-border">/</span>
          </span>
        ))}
      </Marquee>
    </div>
  );
}

/* ───────────────────────── positioning ──────────────────────── */

function Positioning() {
  return (
    <section id="why" className="mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
      <div className="atelier-rule" />
      <div className="mt-10 grid gap-12 lg:grid-cols-[1.1fr_.9fr] lg:gap-20">
        <Reveal>
          <p className="atelier-eyebrow text-primary">01 / The problem</p>
          <h2 className="mt-5 font-editorial text-[clamp(2.4rem,5.2vw,4.4rem)] leading-[1.03] text-balance">
            Accounting tells you what happened. A decision needs{" "}
            <em className="text-primary">what happens next</em>.
          </h2>
        </Reveal>

        <Reveal delay={.1}>
          <p className="text-pretty text-[15.5px] leading-relaxed text-muted-foreground">
            An owner opens a dashboard and sees eighteen lakh. Is it in the bank,
            or does it include invoices someone still owes? Is it today, or a
            projection? Does it assume the order they are about to accept?
          </p>
          <p className="mt-4 text-pretty text-[15.5px] leading-relaxed text-muted-foreground">
            When reality, expectation and possibility share a screen without being
            distinguished, the owner learns to distrust every number — or acts on
            one of them as if it were the other.
          </p>

          <div className="mt-8 space-y-0">
            {[
              { n: "01", t: "One ledger", d: "Bank, invoices, GST and settlements reconciled, with duplicate detection that never silently merges two payments." },
              { n: "02", t: "One honest forecast", d: "Thirteen weeks, four thousand paths, and the measured calibration printed beside the band." },
              { n: "03", t: "One decision at a time", d: "Change an assumption, see the consequence, and leave the ledger untouched." },
            ].map((x) => (
              <div key={x.n} className="grid grid-cols-[42px_1fr] gap-3 border-t border-border py-4 last:border-b">
                <span className="atelier-index pt-1">{x.n}</span>
                <div>
                  <p className="text-[13.5px] font-semibold">{x.t}</p>
                  <p className="mt-1 text-[12.5px] leading-relaxed text-muted-foreground text-pretty">{x.d}</p>
                </div>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ───────────────────────── the instrument ───────────────────── */

function Instrument() {
  return (
    <section id="instrument" className="border-y border-border bg-surface/45 py-24 sm:py-32">
      <div className="mx-auto max-w-7xl px-5 sm:px-8">
        <Reveal>
          <div className="flex flex-wrap items-end justify-between gap-6">
            <div>
              <p className="atelier-eyebrow text-primary">02 / The instrument</p>
              <h2 className="mt-4 max-w-2xl font-editorial text-[clamp(2.3rem,4.8vw,4rem)] leading-[1.05] text-balance">
                Six parts. One calm surface.
              </h2>
            </div>
            <p className="max-w-sm text-pretty text-[14px] leading-relaxed text-muted-foreground">
              Every tile below is a real piece of the product, not a feature icon.
              The numbers come from the same demo ledger you open after sign-in.
            </p>
          </div>
        </Reveal>

        <div className="mt-12 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <Reveal delay={.02}><BentoCard index="01" title="A ledger that can be questioned" icon={Database} className="lg:col-span-2">
            <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_1fr]">
              <div className="rounded-lg border border-border bg-card p-3">
                <p className="atelier-eyebrow atelier-eyebrow-sm">Sources joined</p>
                <ul className="mt-2.5 space-y-1.5 text-[11.5px]">
                  {[["Bank CSV", "1,842 txns"], ["Tally vouchers", "416"], ["GST register", "98"], ["UPI settlements", "264"]].map(([a, b]) => (
                    <li key={a} className="flex justify-between gap-3 border-b border-border/60 pb-1.5 last:border-0">
                      <span className="text-muted-foreground">{a}</span><span className="font-mono tnum">{b}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="rounded-lg border border-border bg-card p-3">
                <p className="atelier-eyebrow atelier-eyebrow-sm">Invariants</p>
                <p className="mt-2 font-display text-3xl font-semibold tracking-tight tnum">4,996</p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                  checked on every build. Debits equal credits; no orphan rows;
                  no negative money objects.
                </p>
                <p className="mt-3 font-mono text-[10px] text-muted-foreground">ledger fp · 660ab0d5…</p>
              </div>
            </div>
          </BentoCard></Reveal>

          <Reveal delay={.06}><BentoCard index="02" title="Thirteen weeks, not one number" icon={TrendingUp}>
            <div className="mt-4 rounded-lg border border-border bg-card p-3">
              <div className="flex items-center justify-between text-[10.5px] text-muted-foreground">
                <span>P50 cash position</span><span className="font-mono">P10–P90</span>
              </div>
              <div className="mt-2"><Spark data={SPARK} height={88} color="var(--chart-1)" /></div>
              <div className="mt-2 flex items-center justify-between text-[10.5px]">
                <span className="text-muted-foreground">Empirical coverage</span>
                <span className="font-semibold tnum text-fin-gain">84%</span>
              </div>
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground text-pretty">
              The band is published with its measured calibration. A forecast that
              cannot say how often it was right is not a forecast.
            </p>
          </BentoCard></Reveal>

          <Reveal delay={.1}><BentoCard index="03" title="Three states, never mixed" icon={Layers}>
            <div className="mt-5 space-y-3">
              {(["actual", "predicted", "simulated"] as const).map((k) => (
                <div key={k} className="flex items-center gap-3">
                  <span className="w-20 shrink-0"><StateBadge state={k} /></span>
                  <span className="h-2 flex-1 rounded-full"
                        style={{
                          background: k === "actual" ? "var(--state-actual)"
                            : k === "predicted" ? "var(--state-predicted-soft)"
                            : "repeating-linear-gradient(90deg, var(--state-simulated) 0 6px, transparent 6px 10px)",
                          border: k === "predicted" ? "1px solid var(--state-predicted)" : undefined,
                        }} />
                </div>
              ))}
            </div>
            <p className="mt-4 text-[11.5px] leading-relaxed text-muted-foreground text-pretty">
              Solid, banded, dashed. Printed in greyscale, the three still stay apart.
            </p>
          </BentoCard></Reveal>

          <Reveal delay={.14}><BentoCard index="04" title="Decisions you can test" icon={GitBranch}>
            <div className="mt-4 flex flex-wrap gap-1.5">
              {["30% advance", "+7 supplier days", "Delay capex"].map((t) => (
                <span key={t} className="rw-chip border-border bg-card text-muted-foreground">{t}</span>
              ))}
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2">
              <div className="rounded-lg border border-border bg-card p-3">
                <p className="atelier-eyebrow atelier-eyebrow-sm">Min cash P10</p>
                <p className="mt-1.5 font-display text-xl font-semibold tnum text-fin-loss">−₹12.2 L</p>
                <p className="text-[10px] text-muted-foreground">as-is</p>
              </div>
              <div className="rounded-lg border border-fin-gain/30 bg-fin-gain-soft p-3">
                <p className="atelier-eyebrow atelier-eyebrow-sm">Min cash P10</p>
                <p className="mt-1.5 font-display text-xl font-semibold tnum text-fin-warn">−₹7.4 L</p>
                <p className="text-[10px] text-muted-foreground">with 30% advance</p>
              </div>
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground text-pretty">
              Baseline and scenario share random draws, so the gap is the decision — not noise.
            </p>
          </BentoCard></Reveal>

          <Reveal delay={.18}><BentoCard index="05" title="Every number has a source" icon={Receipt} className="lg:col-span-2">
            <div className="mt-5 grid gap-3 sm:grid-cols-[1.2fr_.8fr]">
              <div className="rounded-lg border border-border bg-card p-3">
                <p className="atelier-eyebrow atelier-eyebrow-sm">Evidence trail</p>
                {[
                  ["Invoice INV-1846", "₹61,626"],
                  ["Bank NEFT 4159…", "₹61,626"],
                  ["Settled", "6 Nov 2026"],
                  ["Match confidence", "0.99"],
                ].map(([k, v], i) => (
                  <div key={k} className="mt-2 flex items-center justify-between gap-3 border-b border-border/60 pb-1.5 text-[11.5px] last:border-0">
                    <span className="flex items-center gap-2 text-muted-foreground">
                      <span className="font-mono text-[9px] text-primary">0{i + 1}</span>{k}
                    </span>
                    <span className="font-mono tnum">{v}</span>
                  </div>
                ))}
              </div>
              <div className="flex flex-col justify-between rounded-lg border border-border bg-card p-3">
                <ShieldCheck className="size-5 text-fin-gain" aria-hidden />
                <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground text-pretty">
                  Click any figure in the app and land on the rows that produced it.
                  An AI summary you cannot check is not intelligence.
                </p>
                <p className="mt-3 font-mono text-[10px] text-muted-foreground">source-of-truth ↗</p>
              </div>
            </div>
          </BentoCard></Reveal>

          <Reveal delay={.22}><BentoCard index="06" title="AI that shows its work" icon={Brain}>
            <div className="mt-4 space-y-2.5">
              <div className="rounded-lg rounded-tr-sm border border-border bg-surface p-3 text-[11.5px] leading-relaxed">
                What if my largest customer pays 30 days late?
              </div>
              <div className="rounded-lg rounded-tl-sm border border-primary/25 bg-primary-soft p-3">
                <p className="text-[11.5px] leading-relaxed">
                  Runway (P10) falls from 4.85 to <strong className="tnum">1.5 weeks</strong> and breach
                  probability rises from 22% to <strong className="tnum">73%</strong>.
                </p>
                <p className="mt-2 font-mono text-[9.5px] text-muted-foreground">
                  tool: customer_delay · verified against deterministic output
                </p>
              </div>
            </div>
            <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground text-pretty">
              No invented figures. No hidden certainty. A human can override every suggestion.
            </p>
          </BentoCard></Reveal>
        </div>
      </div>
    </section>
  );
}

function BentoCard({ index, title, icon: Icon, children, className }:
  { index: string; title: string; icon: any; children: ReactNode; className?: string }) {
  return (
    <article className={cn("atelier-card flex h-full flex-col p-5", className)}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="grid size-8 place-items-center rounded-lg border border-border bg-surface text-primary">
            <Icon className="size-4" aria-hidden />
          </span>
          <h3 className="font-display text-[14px] font-semibold tracking-tight">{title}</h3>
        </div>
        <span className="atelier-index">{index}</span>
      </div>
      <div className="mt-3 flex-1">{children}</div>
    </article>
  );
}

/* ───────────────────────── three states ─────────────────────── */

const STATE_COPY = [
  {
    k: "actual" as const, n: "01", q: "What is happening?",
    body: "A reconciled ledger built from bank statements, invoices, GST registers and settlement files. Every figure traces back to a source row.",
    stat: "4,996", statLabel: "accounting invariants checked",
  },
  {
    k: "predicted" as const, n: "02", q: "What is likely to happen?",
    body: "A 13-week projection assembled from the invoices and obligations already on file, then simulated four thousand times with a published P10–P90 band.",
    stat: "84%", statLabel: "empirical band coverage",
  },
  {
    k: "simulated" as const, n: "03", q: "What could happen?",
    body: "Scenarios branch from a fixed baseline and share its random draws. Nothing a scenario does can reach the ledger.",
    stat: "12", statLabel: "decision scenarios, all isolated",
  },
];

function States() {
  return (
    <section id="states" className="mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
      <Reveal>
        <p className="atelier-eyebrow text-primary">03 / The architecture</p>
        <div className="mt-5 flex flex-wrap items-end justify-between gap-6">
          <h2 className="max-w-2xl font-editorial text-[clamp(2.3rem,4.8vw,4rem)] leading-[1.05] text-balance">
            Three states. Kept strictly apart.
          </h2>
          <p className="max-w-sm text-pretty text-[14px] leading-relaxed text-muted-foreground">
            Separated in the database, in the API and on screen. An estimate can
            never be mistaken for a bank balance.
          </p>
        </div>
      </Reveal>

      <div className="mt-12 grid gap-4 lg:grid-cols-3">
        {STATE_COPY.map((s, i) => {
          const meta = STATE_META[s.k];
          return (
            <Reveal key={s.k} delay={i * .07}>
              <article className="atelier-card relative h-full overflow-hidden p-6">
                <span className="pointer-events-none absolute inset-x-0 top-0 h-1"
                      style={{
                        background: s.k === "actual" ? meta.color
                          : s.k === "predicted" ? `linear-gradient(90deg, ${meta.color}, transparent)`
                          : `repeating-linear-gradient(90deg, ${meta.color} 0 8px, transparent 8px 14px)`,
                      }} />
                <div className="flex items-center justify-between">
                  <span className="atelier-index">{s.n} / 03</span>
                  <StateBadge state={s.k} size="md" />
                </div>
                <h3 className="mt-7 font-editorial text-[30px] leading-tight">{s.q}</h3>
                <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground text-pretty">{s.body}</p>
                <div className="mt-8 flex items-baseline gap-3 border-t border-border pt-5">
                  <span className="font-display text-3xl font-semibold tracking-tight tnum" style={{ color: meta.color }}>{s.stat}</span>
                  <span className="text-[11.5px] leading-snug text-muted-foreground">{s.statLabel}</span>
                </div>
              </article>
            </Reveal>
          );
        })}
      </div>

      <Reveal delay={.1}>
        <div className="rw-sidebar atelier-ink-panel mt-4 flex flex-wrap items-center justify-between gap-4 rounded-2xl px-6 py-5">
          <div className="flex items-center gap-3">
            <Layers className="size-5 text-primary-bright" aria-hidden />
            <p className="text-[13.5px] font-medium">Compare all three on one screen</p>
          </div>
          <p className="max-w-xl text-[12px] leading-relaxed text-sidebar-muted">
            The Business State Centre puts actual, predicted and simulated side by
            side without ever summing them into one misleading total.
          </p>
          <Link href="/login" className="atelier-cta" style={{ padding: ".6rem 1rem", fontSize: 12 }}>
            Open the centre <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </Reveal>
    </section>
  );
}

/* ───────────────────────── decision story ───────────────────── */

// Weekly P10 cash (₹ lakh), quick-run new_order ₹15 L, 18% margin, 60-day terms.
const BASE_PATH = [9.07, 6.48, 6.71, 10.34, 8.49, 6.41, 5.07, 4.77, 7.24, 8.94, 11.96, 9.36, 12.18, 12.53];
const GAP_PATH = [9.07, 6.41, 6.78, 10.62, 9.12, 3.17, -6.92, -7.55, -4.94, -3.42, 0.09, -2.26, 1.42, 6.68];
const FIXED_PATH = [9.07, 8.11, 10.99, 14.92, 13.37, 8.08, -2.12, -2.79, -0.32, 1.31, 4.58, 1.80, 5.52, 8.13];
const CHART_MIN = -10, CHART_MAX = 16, BUFFER_LAKH = 3;
const W = 640, H = 300, PAD = 30;
const yFor = (v: number) => H - PAD - ((v - CHART_MIN) / (CHART_MAX - CHART_MIN)) * (H - PAD * 2);
function pathFor(series: number[]) {
  return series.map((v, i) => {
    const x = PAD + (i / (series.length - 1)) * (W - PAD * 2);
    return `${i ? "L" : "M"}${x.toFixed(1)},${yFor(v).toFixed(1)}`;
  }).join(" ");
}

function DecisionStory() {
  const [mode, setMode] = useState<"asIs" | "advance">("asIs");
  const lever = mode === "asIs";
  return (
    <section id="decision" className="border-y border-border bg-surface/45 py-24 sm:py-32">
      <div className="mx-auto grid max-w-7xl items-center gap-12 px-5 sm:px-8 lg:grid-cols-[.85fr_1.15fr]">
        <Reveal>
          <p className="atelier-eyebrow text-primary">05 / The decision</p>
          <h2 className="mt-5 font-editorial text-[clamp(2.3rem,4.8vw,4rem)] leading-[1.05] text-balance">
            One order. Three honest answers.
          </h2>
          <p className="mt-5 max-w-md text-pretty text-[14.5px] leading-relaxed text-muted-foreground">
            A ₹15 lakh order arrives: eighteen percent margin, sixty-day terms.
            Every accounting tool will tell you it is profitable. That is not the
            question the owner is asking.
          </p>

          <div className="mt-8 flex flex-wrap gap-2" role="group" aria-label="Decision lever">
            <button onClick={() => setMode("asIs")} aria-pressed={lever}
                    className={cn("rounded-lg border px-3.5 py-2 text-[12px] font-medium transition-colors",
                      lever ? "border-primary bg-primary-soft text-primary" : "border-border bg-card text-muted-foreground hover:text-foreground")}>
              Accept as-is
            </button>
            <button onClick={() => setMode("advance")} aria-pressed={!lever}
                    className={cn("rounded-lg border px-3.5 py-2 text-[12px] font-medium transition-colors",
                      !lever ? "border-fin-gain/40 bg-fin-gain-soft text-fin-gain" : "border-border bg-card text-muted-foreground hover:text-foreground")}>
              Negotiate a 30% advance
            </button>
          </div>

          <div className="mt-8 grid grid-cols-2 gap-4 border-t border-border pt-6">
            <div>
              <p className="atelier-eyebrow atelier-eyebrow-sm">Minimum cash (P10)</p>
              <p className={cn("mt-1.5 font-display text-3xl font-semibold tracking-tight tnum", lever ? "text-fin-loss" : "text-fin-warn")}>
                {lever ? "−₹12.2 L" : "−₹7.4 L"}
              </p>
            </div>
            <div>
              <p className="atelier-eyebrow atelier-eyebrow-sm">Breach probability</p>
              <p className={cn("mt-1.5 font-display text-3xl font-semibold tracking-tight tnum", lever ? "text-fin-loss" : "text-fin-warn")}>
                {lever ? "60%" : "42%"}
              </p>
            </div>
          </div>
          <p className="mt-5 max-w-md text-[12.5px] leading-relaxed text-muted-foreground text-pretty">
            {lever
              ? "Materials are payable on day 37; the balance arrives on day 88. For 51 days the business funds somebody else's inventory."
              : "Same order, same margin. The advance brings ₹4.5 L in up front, so the gap shrinks from ₹12.3 L to ₹7.8 L. It does not close: the P10 path still dips below zero. The scenario never touches the ledger."}
          </p>
        </Reveal>

        <Reveal delay={.1}>
          <div className="rw-sidebar atelier-ink-panel rounded-2xl border border-sidebar-border p-5 sm:p-7">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="atelier-eyebrow atelier-eyebrow-muted">Downside cash (P10) · ₹ lakh</p>
                <p className="mt-1 text-[12px] text-sidebar-muted">13 weeks from the as-of date</p>
              </div>
              <div className="flex flex-wrap gap-3 text-[10.5px] text-sidebar-muted">
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-primary-bright" /> Baseline</span>
                <span className="flex items-center gap-1.5"><span className="h-0.5 w-4 rounded bg-fin-gain" /> {lever ? "Order as-is" : "With advance"}</span>
              </div>
            </div>

            <svg viewBox={`0 0 ${W} ${H}`} className="mt-5 w-full" role="img"
                 aria-label={lever ? "Downside cash falls to minus 7.6 lakh when the order is accepted as-is" : "With a 30 percent advance, downside cash still dips, to minus 2.8 lakh"}>
              {[-10, -5, 0, 5, 10, 15].map((v) => {
                const y = yFor(v);
                return <g key={v}>
                  <line x1={PAD} x2={W - PAD} y1={y} y2={y} stroke="var(--sidebar-border)" strokeWidth="1" />
                  <text x={PAD - 8} y={y + 3} textAnchor="end" fontSize="9" fill="var(--sidebar-muted)">{v}</text>
                </g>;
              })}
              <line x1={PAD} x2={W - PAD} y1={yFor(BUFFER_LAKH)} y2={yFor(BUFFER_LAKH)}
                    stroke="var(--fin-warn)" strokeWidth="1" strokeDasharray="4 4" />
              <motion.path key={`base-${mode}`} d={pathFor(BASE_PATH)} fill="none"
                           stroke="var(--primary-bright)" strokeWidth="2.4" strokeLinecap="round"
                           initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: .5 }} />
              <motion.path key={`scen-${mode}`} d={pathFor(lever ? GAP_PATH : FIXED_PATH)} fill="none"
                           stroke={lever ? "var(--fin-loss)" : "var(--fin-gain)"} strokeWidth="2.8" strokeLinecap="round"
                           initial={{ opacity: 0, pathLength: 0 }} animate={{ opacity: 1, pathLength: 1 }}
                           transition={{ duration: .8, ease: EASE_OUT }} />
              {[0, 4, 8, 13].map((i) => (
                <text key={i} x={PAD + (i / 13) * (W - PAD * 2)} y={H - 8}
                      textAnchor="middle" fontSize="9" fill="var(--sidebar-muted)">{i ? `W${i}` : "Now"}</text>
              ))}
            </svg>

            <div className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-3">
              {[
                ["Order value", "₹15.00 L"],
                ["Cash tied up", lever ? "₹12.3 L" : "₹7.8 L"],
                ["Funding gap", "51 days"],
              ].map(([k, v]) => (
                <div key={k}>
                  <p className="atelier-eyebrow atelier-eyebrow-sm atelier-eyebrow-muted">{k}</p>
                  <p className="mt-1 font-display text-lg font-semibold tnum">{v}</p>
                </div>
              ))}
            </div>
            <p className="mt-4 font-mono text-[9.5px] leading-relaxed text-sidebar-muted">
              4,000 correlated paths · shared seed · split-conformal P10–P90 · nothing written to the ledger
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ───────────────────────────── proof ────────────────────────── */

const LIMITS = [
  { icon: Lock, t: "Never moves money", d: "No payment, no credit application, no contract change. Every action waits for explicit approval." },
  { icon: ShieldCheck, t: "Never claims to be a credit score", d: "The health indicator is transparent, configurable and carries its disclaimer into the API." },
  { icon: Activity, t: "Never publishes an unmeasured accuracy", d: "Where no forecast has matured, the product says nothing has matured." },
  { icon: Brain, t: "Never lets a model invent a number", d: "Copilot figures are verified against deterministic tool output before they are shown." },
];

function Proof() {
  return (
    <section id="proof" className="mx-auto max-w-7xl px-5 py-24 sm:px-8 sm:py-32">
      <Reveal>
        <p className="atelier-eyebrow text-primary">06 / Proof, not promises</p>
        <div className="mt-5 grid gap-8 lg:grid-cols-[1fr_1fr] lg:items-end">
          <h2 className="font-editorial text-[clamp(2.3rem,4.8vw,4rem)] leading-[1.05] text-balance">
            The refusals are the feature.
          </h2>
          <p className="max-w-md text-pretty text-[14.5px] leading-relaxed text-muted-foreground">
            In a product about someone else&apos;s money, knowing what it will not
            do matters more than a long list of what it can. These commitments are
            enforced in code and asserted in tests.
          </p>
        </div>
      </Reveal>

      <div className="mt-12 grid gap-4 sm:grid-cols-2">
        {LIMITS.map((x, i) => (
          <Reveal key={x.t} delay={i * .05}>
            <article className="atelier-card flex h-full gap-4 p-5">
              <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-surface text-primary">
                <x.icon className="size-4" aria-hidden />
              </span>
              <div>
                <h3 className="text-[13.5px] font-semibold">{x.t}</h3>
                <p className="mt-1.5 text-[12.5px] leading-relaxed text-muted-foreground text-pretty">{x.d}</p>
              </div>
            </article>
          </Reveal>
        ))}
      </div>

      <Reveal delay={.1}>
        <div className="mt-10 grid gap-6 border-y border-border py-8 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { to: 13, suffix: "", label: "week probabilistic forecast" },
            { to: 4000, suffix: "", label: "correlated Monte Carlo paths" },
            { to: 84, suffix: "%", label: "measured P10–P90 coverage" },
            { to: 21, suffix: "", label: "working screens behind the login" },
          ].map((s) => (
            <div key={s.label}>
              <p className="font-display text-4xl font-semibold tracking-tight tnum">
                <Counter to={s.to} suffix={s.suffix} />
              </p>
              <p className="mt-2 max-w-[150px] text-[11.5px] leading-snug text-muted-foreground">{s.label}</p>
            </div>
          ))}
        </div>
      </Reveal>
    </section>
  );
}

/* ────────────────────────────── FAQ ─────────────────────────── */

const QUESTIONS = [
  { q: "Do I have to migrate away from Tally or my bank?", a: "No. RUNWAY is an intelligence layer on top of what you already use. It imports bank CSV, Tally voucher XML, GST register JSON/CSV, gateway settlements and text-layer PDF invoices. You keep your accounting system." },
  { q: "Is this a loan product or a credit score?", a: "Neither. RUNWAY never moves money, never applies for credit and never promises approval. Its health indicator is its own transparent measure, not a bureau score, and it carries that disclaimer everywhere it appears." },
  { q: "How do I know the forecast is not just a confident guess?", a: "Every stored forecast is scored against what actually happened, per horizon. The band is built with split-conformal calibration and its empirical coverage is published beside it. Where no predictions have matured, the product says so." },
  { q: "What happens to a scenario I run?", a: "Nothing outside the scenario. Simulated state is structurally isolated from the ledger, shares a random seed with the baseline so comparisons are fair, and can be saved, compared or discarded without writing a single accounting row." },
];

function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section className="border-y border-border bg-surface/45 py-20 sm:py-28">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 sm:px-8 lg:grid-cols-[.7fr_1.3fr]">
        <Reveal>
          <p className="atelier-eyebrow text-primary">07 / Questions</p>
          <h2 className="mt-4 font-editorial text-[clamp(2.1rem,4vw,3.4rem)] leading-[1.06] text-balance">
            Straight answers, before you ask.
          </h2>
          <p className="mt-5 max-w-sm text-[13.5px] leading-relaxed text-muted-foreground">
            Trust is built by putting the awkward questions on the page, not by
            hiding them behind a sales call.
          </p>
        </Reveal>

        <Reveal delay={.08}>
          <div className="border-t border-border">
            {QUESTIONS.map((x, i) => {
              const on = open === i;
              return (
                <div key={x.q} className="border-b border-border">
                  <button onClick={() => setOpen(on ? null : i)} aria-expanded={on}
                          className="flex w-full items-center justify-between gap-4 py-5 text-left">
                    <span className="text-[14px] font-medium text-pretty">{x.q}</span>
                    <ChevronDown className={cn("size-4 shrink-0 text-muted-foreground transition-transform", on && "rotate-180")} />
                  </button>
                  {on && (
                    <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }}
                              className="overflow-hidden pb-5 text-[13px] leading-relaxed text-muted-foreground text-pretty">
                      {x.a}
                    </motion.p>
                  )}
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ─────────────────────────── closing ────────────────────────── */

function Closing() {
  return (
    <section className="mx-auto max-w-[1200px] px-5 pb-24 sm:px-8">
      <Reveal>
        <div className="relative overflow-hidden rounded-[32px] bg-lime px-6 py-16 text-center sm:py-20">
          <div className="dots pointer-events-none absolute inset-0 opacity-40" aria-hidden />
          <div className="relative mx-auto max-w-3xl">
            <p className="eyebrow text-forest">The live demo</p>
            <h2 className="display mx-auto mt-4 max-w-2xl text-[clamp(2rem,4.4vw,3.4rem)] text-forest">
              See your next 13 weeks in two minutes.
            </h2>
            <p className="mx-auto mt-5 max-w-md text-[17px] text-forest/75">
              The demo comes with a full sample business. Click around, break things.
              Nothing here describes a real company.
            </p>
            <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link href="/login" className="btn btn-primary h-[52px] px-7">
                Open the live demo <ArrowRight className="size-4" />
              </Link>
              <Link href="/login" className="btn btn-ghost h-[52px] px-7 text-forest hover:bg-forest/10">
                Sign in
              </Link>
            </div>
            <div className="mx-auto mt-8 inline-flex flex-col rounded-2xl border border-forest/20 bg-forest/10 px-5 py-3 text-left">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-forest/70">Demo credentials</p>
              <p className="mt-1 font-mono text-[12px] text-forest">owner@runway.demo · demo1234</p>
            </div>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

/* ─────────────────────────── footer ─────────────────────────── */

function Footer() {
  return (
    <footer className="border-t border-border bg-card/60">
      <div className="mx-auto grid max-w-7xl gap-10 px-5 py-14 sm:px-8 lg:grid-cols-[1.4fr_1fr_1fr]">
        <div>
          <Logo />
          <p className="mt-4 max-w-sm text-[12.5px] leading-relaxed text-muted-foreground text-pretty">
            A financial intelligence layer for Indian MSMEs. Built for INNOVASIA
            2K26 · PS-04 by Team SignalForge, Vasavi College of Engineering.
          </p>
          <p className="mt-5 font-mono text-[10px] text-muted-foreground">
            Synthetic demonstration data · not financial advice
          </p>
        </div>
        <div>
          <p className="atelier-eyebrow">Explore</p>
          <ul className="mt-4 space-y-2.5 text-[12.5px] text-muted-foreground">
            {NAV_LINKS.map(([h, l]) => <li key={h}><a href={h} className="hover:text-foreground">{l}</a></li>)}
          </ul>
        </div>
        <div>
          <p className="atelier-eyebrow">The workspace</p>
          <ul className="mt-4 space-y-2.5 text-[12.5px] text-muted-foreground">
            <li><Link href="/login" className="hover:text-foreground">Sign in</Link></li>
            <li><Link href="/login" className="hover:text-foreground">Open the demo</Link></li>
            <li><Link href="/app/state-centre" className="hover:text-foreground">Business State Centre</Link></li>
            <li><Link href="/app/forecasts" className="hover:text-foreground">Cash Runway</Link></li>
            <li><Link href="/app/scenarios" className="hover:text-foreground">Scenario Lab</Link></li>
          </ul>
        </div>
      </div>
      <div className="border-t border-border">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-5 text-[10.5px] text-muted-foreground sm:px-8">
          <span>© 2026 RUNWAY · Grove design system v3</span>
          <span className="font-mono">Actual · Predicted · Simulated — never mixed</span>
        </div>
      </div>
    </footer>
  );
}
