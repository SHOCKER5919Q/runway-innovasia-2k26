import Link from "next/link";
import { ArrowRight, Ban, CircleDot, Cpu, Eye, Layers } from "lucide-react";
import { MarketingShell, Section, SectionLabel, SectionTitle } from "@/components/marketing/site";

export const metadata = {
  title: "How it works",
  description:
    "The method behind RUNWAY: a ledger-driven 13-week forecast, a single-factor " +
    "correlation model for payment delays, revenue/downturn coupling, and the " +
    "three-state separation between what is recorded, what is predicted and what " +
    "is simulated.",
};

const STATES = [
  { key: "actual", label: "ACTUAL",
    line: "What is recorded.",
    body: "Reconciled bank and cash balances, open invoices, obligations and settled history. Ranked by evidence: verified against a document, or imported and not yet verified." },
  { key: "predicted", label: "PREDICTED",
    line: "What is likely.",
    body: "Invoice-level payment dates, the 13-week cash band, customer risk bands. Every predicted figure carries the interval and the model it came from." },
  { key: "simulated", label: "SIMULATED",
    line: "What could happen.",
    body: "A scenario you chose to run. It never writes back into the ledger and is never shown in the same colour as a fact." },
];

const METHOD = [
  { title: "Ledger-driven, not curve-fitted",
    body: "A statistical extrapolation of past balances throws away the information an MSME actually has: the thirty-odd invoices and obligations whose dates and amounts are already on file. Each week's movement is assembled from those, with the unknown residual — sales not yet invoiced — estimated separately and labelled as an estimate." },
  { title: "Correlated payment delays",
    body: "Treating customers as independent understates liquidity risk, because when money is tight everybody pays late at once. Each simulated path draws one market-wide factor and every customer's delay loads onto it — the same single-factor device used for correlated defaults in credit portfolios." },
  { title: "Demand and delay move together",
    body: "A downturn is one event, not two. The shared market factor that lowers a path's sales also stretches that path's collections. The effect is one-sided: a strong market does not make customers pay early, it simply leaves the predicted dates alone." },
  { title: "Committed purchasing",
    body: "Materials for the next few weeks are already ordered or under a minimum commitment, so a revenue shock cuts collections long before it cuts cash out. Without this, \"revenue falls 20%\" comes out as a cash improvement — both wrong and dangerous to show an owner." },
  { title: "Common random numbers",
    body: "A scenario re-uses the baseline's random draws, so the difference between the two is the decision rather than sampling noise. That is what makes a 0.3-week runway difference mean something at 4,000 paths." },
  { title: "Measured accuracy",
    body: "Past forecasts are scored against the cash positions actually recorded, by horizon. No accuracy figure is published that has not been measured, and a model ships only if it beats its own baseline by a statistically significant margin." },
];

const LIMITS = [
  "RUNWAY never moves money, borrows, or changes a contract.",
  "It is not a credit rating, not a credit score, and not issued by a credit information company. No lender is obliged to recognise the Passport.",
  "GST figures are estimates derived from recorded sales and purchases until confirmed against a filed return.",
  "Supplier MSMED status is taken from your own records; confirm Udyam registration before relying on statutory deadlines.",
  "The assistant answers only from your workspace's computed figures. It does not browse the internet and does not give tax or legal advice.",
  "A 13-week window sees the cash cost of a revenue change sooner than its collection effect. Read a revenue shock over two quarters, not one.",
];

export default function HowItWorksPage() {
  return (
    <MarketingShell>
      <Section className="!pb-0 !pt-14">
        <SectionLabel>How it works</SectionLabel>
        <div className="mt-3">
          <SectionTitle sub="One deterministic pipeline: import, reconcile, forecast, simulate. This page is the method, including the parts that are estimates.">
            Where every number comes from.
          </SectionTitle>
        </div>
      </Section>

      {/* ── three states ── */}
      <Section id="states" className="!py-12">
        <div className="grid gap-4 md:grid-cols-3">
          {STATES.map((s) => (
            <div key={s.key} className="rounded-xl border border-border bg-card p-5">
              <span className="rw-chip border-border bg-surface"
                    style={s.key === "actual"
                      ? { color: "var(--state-actual)", background: "var(--state-actual-soft)" }
                      : s.key === "predicted"
                        ? { color: "var(--state-predicted)", background: "var(--state-predicted-soft)" }
                        : { color: "var(--state-simulated)", background: "var(--state-simulated-soft)" }}>
                <CircleDot className="size-3" /> {s.label}
              </span>
              <h3 className="mt-3 font-display text-[15px] font-semibold tracking-tight">
                {s.line}
              </h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground text-pretty">
                {s.body}
              </p>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-muted-foreground">
          The three states are separated in the database, the API and the interface.
          A value can be demoted freely but is only ever promoted by an explicit,
          audited action.
        </p>
      </Section>

      {/* ── method ── */}
      <Section id="method" className="border-t border-border">
        <div className="flex items-center gap-2">
          <Cpu className="size-4 text-primary" />
          <h2 className="font-display text-lg font-semibold tracking-tight">The model</h2>
        </div>
        <div className="mt-6 grid gap-x-10 gap-y-7 md:grid-cols-2">
          {METHOD.map((m) => (
            <div key={m.title}>
              <h3 className="font-display text-[14.5px] font-semibold tracking-tight">
                {m.title}
              </h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground text-pretty">
                {m.body}
              </p>
            </div>
          ))}
        </div>
      </Section>

      {/* ── pipeline ── */}
      <Section id="pipeline" className="border-t border-border bg-surface/20">
        <div className="flex items-center gap-2">
          <Layers className="size-4 text-primary" />
          <h2 className="font-display text-lg font-semibold tracking-tight">The pipeline</h2>
        </div>
        <ol className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[
            "Parse — adapter per source, raw rows kept verbatim",
            "Fingerprint — stable identity from reference, date, amount, narration",
            "Dedupe — hard reject on reference, soft flag without one",
            "Resolve — counterparty matching with a confidence and a runner-up check",
            "Classify — rule set with stated confidence and the rule that fired",
            "Reconcile — allocate payments to invoices, never past either side's limit",
            "Forecast — 13-week Monte Carlo over the reconciled ledger",
            "Simulate — scenario mutations on a copy, never on the baseline",
            "Recommend — ranked actions with effect, downside and evidence",
          ].map((s, i) => (
            <li key={s}
                className="flex items-start gap-3 rounded-lg border border-border bg-card px-4 py-3 text-[13px] text-muted-foreground">
              <span className="tnum font-mono text-xs text-primary">{i + 1}</span>
              <span className="text-pretty">{s}</span>
            </li>
          ))}
        </ol>
      </Section>

      {/* ── limits ── */}
      <Section id="limits" className="border-t border-border">
        <div className="flex items-center gap-2">
          <Ban className="size-4 text-fin-warn" />
          <h2 className="font-display text-lg font-semibold tracking-tight">
            What it will not do
          </h2>
        </div>
        <p className="mt-2 max-w-2xl text-[13.5px] leading-relaxed text-muted-foreground">
          The limits are part of the product, not a footnote. A tool that hides them
          is a tool you cannot safely act on.
        </p>
        <ul className="mt-6 grid gap-3 md:grid-cols-2">
          {LIMITS.map((l) => (
            <li key={l}
                className="flex items-start gap-2.5 rounded-lg border border-border bg-card px-4 py-3 text-[13px] leading-relaxed text-muted-foreground">
              <Eye className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" />
              <span className="text-pretty">{l}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section className="border-t border-border">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-[26px] font-semibold leading-tight tracking-tight text-balance">
            Read the method against real numbers.
          </h2>
          <Link href="/login"
                className="mt-7 inline-flex items-center gap-1.5 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90">
            Open the live demo <ArrowRight className="size-4" />
          </Link>
        </div>
      </Section>
    </MarketingShell>
  );
}
