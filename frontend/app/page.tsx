"use client";

import Link from "next/link";
import { useRef } from "react";
import {
  ArrowDown, ArrowRight, Brain, CheckCircle2, CircleDollarSign, Database,
  GitBranch, LineChart, Lock, Play, ShieldCheck, Sparkles, Workflow,
} from "lucide-react";
import { motion } from "motion/react";
import { Logo } from "@/components/runway/shell";
import { EASE_OUT, SmoothScroll } from "@/components/runway/motion";
import {
  Counter, GridBeam, Magnetic, Marquee, Rise, Scramble, ScrollFloat,
  ScrollProgress, SplitText, TiltCard, useGsapContext,
} from "@/components/runway/bits";
import HeroCanvas from "@/components/runway/hero3d-loader";
import ProductPreview from "@/components/runway/product-preview";
import { ChapterRail, IntroCurtain } from "@/components/runway/premium";

export default function Landing() {
  return (
    <SmoothScroll>
      <div className="relative min-h-dvh overflow-x-clip bg-background rw-noise">
        <IntroCurtain />
        <ScrollProgress />
        <ChapterRail sections={CHAPTERS} />
        <Nav />
        <Hero />
        <Ticker />
        <Problem />
        <ThreeStates />
        <Decision />
        <ProductPreview />
        <Capabilities />
        <Honesty />
        <Closing />
        <Footer />
      </div>
    </SmoothScroll>
  );
}

/* The rail indexes these, and the nav links to a subset of them. Both read
   from one list so a renamed section cannot leave a dead anchor behind. */
const CHAPTERS = [
  { id: "problem", label: "The problem" },
  { id: "states", label: "Three states" },
  { id: "decision", label: "The decision" },
  { id: "product", label: "The product" },
  { id: "capabilities", label: "Capabilities" },
  { id: "honesty", label: "Limits" },
] as const;

/* ───────────────────────────── nav ───────────────────────────── */

function Nav() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/50 bg-background/60 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 sm:px-8">
        <Logo />
        <nav className="hidden items-center gap-8 text-[13px] text-muted-foreground lg:flex">
          {[["#states", "Three states"], ["#decision", "The decision"],
            ["#product", "The product"], ["#capabilities", "Capabilities"],
            ["#honesty", "What it won't do"]].map(([h, l]) => (
            <a key={h} href={h}
               className="relative py-1 transition-colors hover:text-foreground
                          after:absolute after:inset-x-0 after:-bottom-0.5 after:h-px
                          after:origin-left after:scale-x-0 after:bg-primary
                          after:transition-transform hover:after:scale-x-100">
              {l}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/login"
                className="hidden rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground sm:block">
            Sign in
          </Link>
          <Magnetic strength={0.25}>
            <Link href="/login"
                  className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground transition-shadow hover:shadow-[var(--glow-primary)]">
              Open the demo <ArrowRight className="size-3.5" />
            </Link>
          </Magnetic>
        </div>
      </div>
    </header>
  );
}

/* ───────────────────────────── hero ──────────────────────────── */

function Hero() {
  const scope = useGsapContext(({ gsap }) => {
    gsap.to(".hero-copy", {
      yPercent: -22, opacity: 0, ease: "none",
      scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.6 },
    });
    gsap.to(".hero-canvas", {
      yPercent: 14, scale: 0.92, ease: "none",
      scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: 0.6 },
    });
  });

  return (
    <section ref={scope as never}
             className="hero relative min-h-[100svh] overflow-hidden">
      <div className="pointer-events-none absolute inset-0 rw-aurora" />
      <GridBeam />

      <div className="relative mx-auto grid max-w-7xl items-center gap-8 px-5 pb-24 pt-14 sm:px-8 lg:min-h-[100svh] lg:grid-cols-[1.05fr_0.95fr] lg:pt-0">
        <div className="hero-copy relative z-10">
          <motion.span
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, ease: EASE_OUT }}
            className="rw-chip border-primary/25 bg-primary-soft text-primary">
            <span className="size-1.5 rounded-full bg-primary rw-ring" />
            INNOVASIA 2K26 · PS-04 · FinTech
          </motion.span>

          <h1 className="mt-6 font-display text-[clamp(2.4rem,5.6vw,4.4rem)] font-semibold leading-[1.04] tracking-[-0.03em]">
            <SplitText text="Your business." className="block" />
            <SplitText text="Its financial future." className="block" delay={0.18} />
            <span className="block text-primary">
              <SplitText text="In one runway." delay={0.36} />
            </span>
          </h1>

          <motion.p
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.75, duration: 0.7, ease: EASE_OUT }}
            className="mt-6 max-w-lg text-pretty text-[15px] leading-relaxed text-muted-foreground sm:text-[16.5px]">
            A financial intelligence layer for Indian MSMEs. It reconciles your bank,
            invoice and GST data into one ledger, projects thirteen weeks of cash with an
            honest uncertainty band, and lets you test a decision before you commit to it.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.9, duration: 0.7, ease: EASE_OUT }}
            className="mt-8 flex flex-wrap items-center gap-3">
            <Magnetic>
              <Link href="/login"
                    className="group inline-flex items-center gap-2 rounded-xl bg-primary px-6 py-3.5 text-sm font-semibold text-primary-foreground shadow-[var(--glow-primary)] transition-transform hover:-translate-y-0.5">
                Open the live demo
                <ArrowRight className="size-4 transition-transform group-hover:translate-x-1" />
              </Link>
            </Magnetic>
            <Magnetic strength={0.2}>
              <a href="#decision"
                 className="inline-flex items-center gap-2 rounded-xl border border-border bg-card/70 px-6 py-3.5 text-sm backdrop-blur transition-colors hover:bg-surface-hover">
                <Play className="size-3.5 text-primary" /> See it decide
              </a>
            </Magnetic>
          </motion.div>

          <motion.dl
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.15 }}
            className="mt-12 grid max-w-xl grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-4">
            {[
              { v: 13, label: "week probabilistic forecast" },
              { v: 12, label: "decision scenarios" },
              { v: 8, label: "stress tests" },
              { v: 285, label: "predictions scored" },
            ].map((s) => (
              <div key={s.label}>
                <dt className="font-display text-[1.75rem] font-semibold tracking-tight text-foreground">
                  <Counter to={s.v} />
                </dt>
                <dd className="mt-1 text-[11.5px] leading-snug text-muted-foreground">{s.label}</dd>
              </div>
            ))}
          </motion.dl>
        </div>

        <div className="hero-canvas relative h-[340px] sm:h-[460px] lg:h-[78vh]">
          <HeroCanvas className="absolute inset-0" />
        </div>
      </div>

      <motion.a href="#problem"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.6 }}
        className="absolute inset-x-0 bottom-7 z-10 mx-auto flex w-fit flex-col items-center gap-1.5 text-[10px] uppercase tracking-[0.22em] text-muted-foreground transition-colors hover:text-foreground">
        Scroll
        <ArrowDown className="size-3.5 animate-bounce" />
      </motion.a>
    </section>
  );
}

/* ──────────────────────────── ticker ─────────────────────────── */

function Ticker() {
  const rows = [
    ["Available cash", "₹4,77,221", "actual"],
    ["Receivables", "₹1,00,32,867", "actual"],
    ["Runway P10", "4.85 weeks", "predicted"],
    ["Breach probability", "17%", "predicted"],
    ["Liquidity CVaR", "₹13,67,426", "predicted"],
    ["ABC Distributors", "+22.4 days", "actual"],
    ["Health score", "72.8 / 100", "predicted"],
    ["MSMED exposed", "₹48,58,621", "actual"],
  ] as const;
  const tone = { actual: "text-fin-info", predicted: "text-primary" };
  return (
    <div className="relative border-y border-border/60 bg-card/30 py-3.5">
      <Marquee speed={48}>
        {rows.map(([k, v, s]) => (
          <span key={k} className="flex items-center gap-2.5 text-[12px] whitespace-nowrap">
            <span className="text-muted-foreground">{k}</span>
            <span className={`font-mono tnum ${tone[s]}`}>{v}</span>
            <span className="text-[9px] uppercase tracking-widest text-muted-foreground/50">{s}</span>
            <span className="text-border">/</span>
          </span>
        ))}
      </Marquee>
    </div>
  );
}

/* ──────────────────────────── problem ────────────────────────── */

function Problem() {
  return (
    <section id="problem" className="relative mx-auto max-w-5xl px-5 py-32 sm:px-8 sm:py-44">
      <p className="mb-8 text-[11px] uppercase tracking-[0.22em] text-primary">The problem</p>
      <h2 className="font-display text-[clamp(1.8rem,4.6vw,3.3rem)] font-semibold leading-[1.18] tracking-[-0.02em] text-balance">
        <ScrollFloat text="An owner opens a dashboard and sees eighteen lakh. Is it in the bank, or does it include invoices someone still owes? Is it today, or a projection? Does it assume the order they are about to accept?" />
      </h2>
      <Rise delay={0.1}>
        <p className="mt-10 max-w-2xl text-pretty text-[15px] leading-relaxed text-muted-foreground">
          When reality, expectation and possibility share a screen without being
          distinguished, the owner either learns to distrust every number — or, worse,
          acts on one of them as if it were the other.
        </p>
      </Rise>
    </section>
  );
}

/* ────────────────────── three states (pinned) ────────────────── */

const STATES = [
  {
    k: "Actual", q: "What is happening?", icon: Database, colour: "var(--state-actual)",
    body: "A reconciled ledger built from bank statements, invoices, GST registers and settlement files. Every figure traces back to a source row, and duplicate detection never silently merges two payments.",
    stat: "4,996", statLabel: "accounting invariants checked",
  },
  {
    k: "Predicted", q: "What is likely to happen?", icon: LineChart, colour: "var(--state-predicted)",
    body: "A 13-week projection assembled from the invoices and obligations already on file, then simulated four thousand times. P10, P50 and P90 — with the model's measured calibration published beside them.",
    stat: "84%", statLabel: "P10–P90 coverage, target 80%",
  },
  {
    k: "Simulated", q: "What could happen?", icon: GitBranch, colour: "var(--state-simulated)",
    body: "Scenarios branch from a fixed baseline and share its random draws, so the difference you see is the decision rather than the noise. Nothing a scenario does can reach the ledger.",
    stat: "12", statLabel: "decision scenarios, all isolated",
  },
];

function ThreeStates() {
  const scope = useGsapContext(({ gsap, ScrollTrigger }) => {
    const cards = gsap.utils.toArray(".state-card") as HTMLElement[];
    if (!cards.length) return;

    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: ".states-pin",
        start: "top top",
        end: () => `+=${cards.length * 70}%`,
        pin: true,
        scrub: 0.8,
        anticipatePin: 1,
      },
    });

    cards.forEach((card, i) => {
      gsap.set(card, { autoAlpha: i === 0 ? 1 : 0, y: i === 0 ? 0 : 52, scale: i === 0 ? 1 : 0.96 });
      if (i === 0) return;
      tl.to(cards[i - 1], { autoAlpha: 0, y: -52, scale: 0.96, duration: 0.5 }, i - 1 + 0.5)
        .to(card, { autoAlpha: 1, y: 0, scale: 1, duration: 0.5 }, i - 1 + 0.75);
    });

    (gsap.utils.toArray(".state-dot") as HTMLElement[]).forEach((dot, i) => {
      ScrollTrigger.create({
        trigger: ".states-pin",
        start: () => `top+=${i * 70}% top`,
        end: () => `top+=${(i + 1) * 70}% top`,
        onToggle: (self: { isActive: boolean }) => dot.classList.toggle("is-active", self.isActive),
      });
    });
  });

  return (
    <section id="states" ref={scope as never} className="relative">
      <div className="states-pin relative flex min-h-[100svh] items-center overflow-hidden">
        <div className="pointer-events-none absolute inset-0 rw-aurora opacity-50" />
        <div className="relative mx-auto grid w-full max-w-7xl items-center gap-12 px-5 sm:px-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <p className="mb-6 text-[11px] uppercase tracking-[0.22em] text-primary">
              The architecture
            </p>
            <h2 className="font-display text-[clamp(1.9rem,4.4vw,3.2rem)] font-semibold leading-[1.1] tracking-[-0.025em] text-balance">
              Three states.
              <br />Kept strictly apart.
            </h2>
            <p className="mt-6 max-w-md text-pretty text-[15px] leading-relaxed text-muted-foreground">
              Separated in the database, in the API and on screen. An estimate can never
              be mistaken for a bank balance.
            </p>
            <ol className="mt-9 space-y-3">
              {STATES.map((s, i) => (
                <li key={s.k} className="state-dot group flex items-center gap-3 opacity-40 transition-opacity [&.is-active]:opacity-100">
                  <span className="grid size-6 shrink-0 place-items-center rounded-full border text-[10px] font-semibold transition-colors"
                        style={{ borderColor: s.colour, color: s.colour }}>
                    {i + 1}
                  </span>
                  <span className="text-sm">{s.k}</span>
                  <span className="h-px flex-1 origin-left scale-x-0 transition-transform duration-500 group-[.is-active]:scale-x-100"
                        style={{ background: s.colour }} />
                </li>
              ))}
            </ol>
          </div>

          <div className="relative h-[430px] sm:h-[400px]">
            {STATES.map((s) => {
              const Icon = s.icon;
              return (
                <article key={s.k}
                  className="state-card absolute inset-0 flex flex-col justify-center rounded-3xl border border-border bg-card/80 p-8 backdrop-blur-xl sm:p-10"
                  style={{ boxShadow: "var(--shadow-float)" }}>
                  <span className="grid size-12 place-items-center rounded-2xl"
                        style={{ background: `color-mix(in oklch, ${s.colour} 14%, transparent)` }}>
                    <Icon className="size-5" style={{ color: s.colour }} />
                  </span>
                  <p className="mt-6 text-[11px] font-semibold uppercase tracking-[0.18em]"
                     style={{ color: s.colour }}>{s.k}</p>
                  <h3 className="mt-2 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
                    {s.q}
                  </h3>
                  <p className="mt-4 max-w-lg text-pretty text-[14.5px] leading-relaxed text-muted-foreground">
                    {s.body}
                  </p>
                  <div className="mt-7 flex items-baseline gap-3 border-t border-border pt-5">
                    <span className="font-display text-3xl font-semibold tnum"
                          style={{ color: s.colour }}>{s.stat}</span>
                    <span className="text-[12px] text-muted-foreground">{s.statLabel}</span>
                  </div>
                </article>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
}

/* ───────────────── the decision (scrollytelling) ─────────────── */

const BASE = [11.1, 12.4, 13.8, 12.9, 11.6, 11.1, 11.3, 12.8, 14.6, 16.2, 18.1, 17.0, 19.3];
const SCEN = [11.1, 12.4, 10.2, 5.1, 2.1, 1.8, 2.4, 3.9, 6.2, 9.8, 13.4, 15.1, 18.9];

function Decision() {
  const scope = useGsapContext(({ gsap }) => {
    const tl = gsap.timeline({
      scrollTrigger: {
        trigger: ".decision-pin", start: "top top", end: "+=320%",
        pin: true, scrub: 0.9, anticipatePin: 1,
      },
    });

    tl.from(".d-step-1", { autoAlpha: 0, y: 26, duration: 0.6 })
      .to(".d-base-path", { strokeDashoffset: 0, duration: 1.4 }, "<")
      .to(".d-step-1", { autoAlpha: 0, y: -26, duration: 0.5 }, "+=0.5")
      .from(".d-step-2", { autoAlpha: 0, y: 26, duration: 0.6 }, "<0.2")
      .to(".d-scen-path", { strokeDashoffset: 0, duration: 1.4 }, "<")
      .to(".d-gap", { autoAlpha: 1, duration: 0.6 }, "<0.7")
      .to(".d-step-2", { autoAlpha: 0, y: -26, duration: 0.5 }, "+=0.6")
      .from(".d-step-3", { autoAlpha: 0, y: 26, duration: 0.6 }, "<0.2")
      .to(".d-scen-path", {
        attr: { d: pathFor(SCEN.map((v, i) => v + [0, 0, 2.6, 4.2, 4.4, 4.0, 3.4, 2.6, 1.8, 1.0, 0.4, 0.2, 0][i])) },
        stroke: "var(--fin-gain)", duration: 1.0,
      }, "<0.25")
      .to(".d-gap", { autoAlpha: 0.25, duration: 0.6 }, "<");
  });

  return (
    <section id="decision" ref={scope as never} className="relative">
      <div className="decision-pin relative flex min-h-[100svh] items-center overflow-hidden border-y border-border/50">
        <GridBeam className="opacity-40" />
        <div className="relative mx-auto grid w-full max-w-7xl items-center gap-10 px-5 sm:px-8 lg:grid-cols-[0.85fr_1.15fr]">
          <div className="relative min-h-[300px]">
            <p className="mb-6 text-[11px] uppercase tracking-[0.22em] text-primary">
              The decision
            </p>

            <Step className="d-step-1" n="01" title="A ₹15 lakh order arrives"
              body="Eighteen percent margin, sixty-day terms. Every accounting tool will tell you it is profitable. That is not the question."
              stat="₹2,70,000" statLabel="expected profit" tone="text-fin-gain" />

            <Step className="d-step-2" n="02" title="RUNWAY answers with the funding gap"
              body="₹12,30,000 of materials is payable on day 37. The balance arrives on day 88. For 51 days the business is funding somebody else's inventory."
              stat="51 days" statLabel="cash out before cash in" tone="text-fin-loss" />

            <Step className="d-step-3" n="03" title="Negotiate a 30% advance"
              body="Same order. Same margin. Minimum cash recovers from ₹2.1 lakh to ₹6.2 lakh and the chance of breaching the safety buffer falls from 54% to 35%."
              stat="−19 pts" statLabel="breach probability" tone="text-primary" />
          </div>

          <DecisionChart />
        </div>
      </div>
    </section>
  );
}

function Step({ className, n, title, body, stat, statLabel, tone }: {
  className: string; n: string; title: string; body: string;
  stat: string; statLabel: string; tone: string;
}) {
  return (
    <div className={`${className} absolute inset-x-0 top-14`}>
      <span className="font-mono text-[11px] text-muted-foreground">{n}</span>
      <h3 className="mt-2 font-display text-[clamp(1.5rem,3vw,2.3rem)] font-semibold leading-tight tracking-tight text-balance">
        {title}
      </h3>
      <p className="mt-4 max-w-md text-pretty text-[14.5px] leading-relaxed text-muted-foreground">
        {body}
      </p>
      <div className="mt-6 flex items-baseline gap-3">
        <span className={`font-display text-3xl font-semibold tnum ${tone}`}>{stat}</span>
        <span className="text-[12px] text-muted-foreground">{statLabel}</span>
      </div>
    </div>
  );
}

const W = 760, H = 380, PAD = 34;
function pathFor(series: number[]) {
  const max = 21, min = 0;
  return series.map((v, i) => {
    const x = PAD + (i / (series.length - 1)) * (W - PAD * 2);
    const y = H - PAD - ((v - min) / (max - min)) * (H - PAD * 2);
    return `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
}

function DecisionChart() {
  const buffer = 3;
  const by = H - PAD - (buffer / 21) * (H - PAD * 2);
  return (
    <div className="rounded-3xl border border-border bg-card/70 p-4 backdrop-blur-xl"
         style={{ boxShadow: "var(--shadow-float)" }}>
      <div className="mb-3 flex items-center justify-between px-2">
        <span className="text-[11px] uppercase tracking-wider text-muted-foreground">
          13-week cash projection
        </span>
        <span className="flex items-center gap-3 text-[10px]">
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <svg width="18" height="6"><line x1="0" y1="3" x2="18" y2="3"
              stroke="var(--state-predicted)" strokeWidth="2" /></svg>Baseline
          </span>
          <span className="flex items-center gap-1.5 text-muted-foreground">
            <svg width="18" height="6"><line x1="0" y1="3" x2="18" y2="3"
              stroke="var(--state-simulated)" strokeWidth="2" strokeDasharray="5 3" /></svg>Scenario
          </span>
        </span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img"
           aria-label="Baseline cash projection against the same business after accepting a ₹15 lakh order, showing a dip below the safety buffer around week five">
        {[0, 1, 2, 3, 4].map((i) => (
          <line key={i} x1={PAD} x2={W - PAD}
                y1={PAD + i * ((H - PAD * 2) / 4)} y2={PAD + i * ((H - PAD * 2) / 4)}
                stroke="var(--chart-grid)" strokeDasharray="3 5" />
        ))}
        <rect className="d-gap" x={PAD} y={by} width={W - PAD * 2} height={H - PAD - by}
              fill="var(--fin-loss)" opacity={0} style={{ opacity: 0 }} />
        <line x1={PAD} x2={W - PAD} y1={by} y2={by}
              stroke="var(--fin-warn)" strokeWidth="1.5" strokeDasharray="6 5" />
        <text x={PAD + 6} y={by - 8} fontSize="11" fill="var(--fin-warn)">Safety buffer</text>

        <path className="d-base-path" d={pathFor(BASE)} fill="none"
              stroke="var(--state-predicted)" strokeWidth="2.6" strokeLinecap="round"
              strokeDasharray="2000" strokeDashoffset="2000" />
        <path className="d-scen-path" d={pathFor(SCEN)} fill="none"
              stroke="var(--state-simulated)" strokeWidth="2.6" strokeLinecap="round"
              strokeDasharray="2000" strokeDashoffset="2000" />
      </svg>
      <p className="px-2 pb-1 text-[10.5px] text-muted-foreground">
        Both paths simulated with the same seed, so the difference is the decision —
        not the noise.
      </p>
    </div>
  );
}

/* ────────────────────────── capabilities ─────────────────────── */

function Capabilities() {
  const items = [
    { icon: CircleDollarSign, t: "Receivables intelligence",
      d: "Per-customer payment behaviour from settled invoices only, with a predicted payment date and a calibrated probability band for each open invoice." },
    { icon: Workflow, t: "Business financial digital twin",
      d: "A living model of accounts, buyers, suppliers, invoices and obligations — rebuilt whenever the ledger moves, and auditable by fingerprint." },
    { icon: Sparkles, t: "Scenario lab",
      d: "Twelve decision types: a new order, a late payer, a hire, a machine, a loan, invoice discounting. Compare branches against one baseline." },
    { icon: ShieldCheck, t: "Early warning",
      d: "Alerts that answer what happened, why it matters, the evidence, the likely impact, what to do, and what happens if you do nothing." },
    { icon: LineChart, t: "Risk, borrowed from markets",
      d: "Liquidity VaR and CVaR, Monte Carlo with correlated payment delays, Herfindahl concentration and eight predefined stress tests." },
    { icon: Brain, t: "A copilot that cannot invent numbers",
      d: "Questions route to deterministic tools. Every rupee figure in a reply is verified against the tool output before it reaches the screen." },
  ];
  return (
    <section id="capabilities" className="relative mx-auto max-w-7xl px-5 py-28 sm:px-8 sm:py-36">
      <Rise>
        <p className="mb-5 text-[11px] uppercase tracking-[0.22em] text-primary">Capabilities</p>
        <h2 className="max-w-3xl font-display text-[clamp(1.8rem,4.2vw,3rem)] font-semibold leading-[1.1] tracking-[-0.025em] text-balance">
          Built to be used daily, not demoed once
        </h2>
      </Rise>
      <div className="mt-14 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {items.map((it, i) => {
          const Icon = it.icon;
          return (
            <Rise key={it.t} delay={(i % 3) * 0.08}>
              <TiltCard className="h-full rounded-2xl border border-border bg-card/70 p-6 backdrop-blur-sm transition-colors hover:border-primary/30">
                <span className="grid size-10 place-items-center rounded-xl bg-primary-soft">
                  <Icon className="size-4.5 text-primary" />
                </span>
                <h3 className="mt-4 font-display text-[17px] font-semibold tracking-tight">{it.t}</h3>
                <p className="mt-2.5 text-[13.5px] leading-relaxed text-muted-foreground text-pretty">
                  {it.d}
                </p>
              </TiltCard>
            </Rise>
          );
        })}
      </div>
    </section>
  );
}

/* ──────────────────────────── honesty ────────────────────────── */

function Honesty() {
  const items = [
    "RUNWAY never moves money, applies for credit or changes a contract. Every recommendation requires your approval.",
    "The health score is RUNWAY's own transparent indicator. It is not a credit score and no lender is obliged to recognise it.",
    "No accuracy figure is shown that has not been measured on forecasts whose target week has already passed.",
    "A model ships only if it beats its baseline by a statistically significant margin. On the demo book the simpler per-customer median wins — and RUNWAY says so on its own screen.",
    "No live Account Aggregator, GST or TReDS connection is claimed. Each connector states exactly what it would require.",
    "Demonstration data is synthetic and labelled as such on every screen.",
  ];
  return (
    <section id="honesty" className="relative mx-auto max-w-5xl px-5 py-28 sm:px-8">
      <Rise>
        <div className="overflow-hidden rounded-3xl border border-border bg-card/70 backdrop-blur-xl"
             style={{ boxShadow: "var(--shadow-float)" }}>
          <div className="border-b border-border bg-surface/50 px-7 py-6">
            <h2 className="flex items-center gap-3 font-display text-xl font-semibold tracking-tight sm:text-2xl">
              <Lock className="size-5 text-fin-gain" />
              What RUNWAY will not do
            </h2>
            <p className="mt-1.5 text-[13.5px] text-muted-foreground text-pretty">
              In a product about someone's money, the constraints matter more than the features.
            </p>
          </div>
          <ul className="divide-y divide-border">
            {items.map((t, i) => (
              <motion.li key={i}
                initial={{ opacity: 0, x: -12 }} whileInView={{ opacity: 1, x: 0 }}
                viewport={{ once: true, margin: "-8%" }}
                transition={{ delay: i * 0.07, duration: 0.55, ease: EASE_OUT }}
                className="flex items-start gap-3.5 px-7 py-4">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-fin-gain" />
                <span className="text-[14px] leading-relaxed text-pretty">{t}</span>
              </motion.li>
            ))}
          </ul>
        </div>
      </Rise>

      <Rise delay={0.15} className="mt-10">
        <div className="rounded-2xl border border-border bg-surface/40 p-6 text-center">
          <p className="font-mono text-[12px] text-muted-foreground">
            <Scramble text="210 backend tests · 75 frontend tests · 4,996 accounting invariants" />
          </p>
          <p className="mt-2 text-[12px] text-muted-foreground">
            Green on SQLite <span className="text-primary">and</span> PostgreSQL.
          </p>
        </div>
      </Rise>
    </section>
  );
}

/* ──────────────────────────── closing ────────────────────────── */

function Closing() {
  return (
    <section className="relative mx-auto max-w-7xl px-5 pb-28 sm:px-8">
      <Rise>
        <div className="relative overflow-hidden rounded-[2rem] border border-border px-6 py-20 text-center sm:px-14 sm:py-28">
          <div className="pointer-events-none absolute inset-0 rw-aurora" />
          <GridBeam className="opacity-50" />
          <div className="relative">
            <h2 className="mx-auto max-w-3xl font-display text-[clamp(1.9rem,4.6vw,3.2rem)] font-semibold leading-[1.08] tracking-[-0.025em] text-balance">
              <SplitText text="See the business." by="word" />{" "}
              <SplitText text="Understand the future." by="word" delay={0.15} />{" "}
              <span className="text-primary">
                <SplitText text="Test the decision." by="word" delay={0.3} />
              </span>
            </h2>
            <p className="mx-auto mt-6 max-w-xl text-pretty text-[15px] text-muted-foreground">
              The demo opens a complete synthetic wholesale distributor with eighteen
              months of reconciled history, a live forecast and a working scenario lab.
            </p>
            <Magnetic>
              <Link href="/login"
                    className="mt-10 inline-flex items-center gap-2 rounded-xl bg-primary px-7 py-4 text-sm font-semibold text-primary-foreground shadow-[var(--glow-primary)] transition-transform hover:-translate-y-0.5">
                Open the demo <ArrowRight className="size-4" />
              </Link>
            </Magnetic>
            <p className="mt-5 font-mono text-[11px] text-muted-foreground">
              owner@runway.demo · demo1234
            </p>
          </div>
        </div>
      </Rise>
    </section>
  );
}

function Footer() {
  return (
    <footer className="relative border-t border-border">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-5 py-9 text-[12px] text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-8">
        <Logo />
        <p className="text-pretty">
          INNOVASIA 2K26 · PS-04 · Team SignalForge · Vasavi College of Engineering, Hyderabad
        </p>
        <p>Demonstration data is synthetic.</p>
      </div>
    </footer>
  );
}
