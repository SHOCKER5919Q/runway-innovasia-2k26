import Link from "next/link";
import {
  ArrowRight, CalendarClock, Check, Database, GitBranch, LineChart,
  ShieldCheck, Users,
} from "lucide-react";
import { MarketingShell, Section, SectionLabel, SectionTitle, FeatureCard }
  from "@/components/marketing/site";
import ProductPreview from "@/components/runway/product-preview";

export const metadata = {
  title: "RUNWAY — See your cash 13 weeks ahead",
  description:
    "RUNWAY reconciles an MSME's bank, invoice and GST data into one ledger, " +
    "projects 13 weeks of cash with an honest uncertainty band, and lets you " +
    "test a decision before you commit to it.",
};

const STEPS = [
  { n: "1", title: "Connect your data",
    body: "Upload bank statements, invoices and GST returns. RUNWAY dedupes, matches counterparties and reconciles payments to invoices." },
  { n: "2", title: "See the next 13 weeks",
    body: "A Monte Carlo forecast built from your actual invoices and obligations — with a P10–P90 band instead of a single confident number." },
  { n: "3", title: "Test the decision",
    body: "Take the order, hire the people, delay the purchase. Each scenario runs on the same engine, so the difference is the decision, not the noise." },
];

const PROOF = [
  { k: "13 weeks", v: "forecast horizon" },
  { k: "P10–P90", v: "uncertainty band" },
  { k: "3 states", v: "actual · predicted · simulated" },
  { k: "0", v: "hardcoded figures" },
];

export default function Landing() {
  return (
    <MarketingShell>
      {/* ── hero ── */}
      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 rw-aurora" aria-hidden />
        <div className="relative mx-auto max-w-6xl px-5 pb-10 pt-16 sm:px-8 sm:pt-24">
          <div className="mx-auto max-w-3xl text-center">
            <span className="rw-chip border-primary/25 bg-primary-soft text-primary">
              For Indian MSMEs
            </span>
            <h1 className="mt-5 font-display text-[clamp(2.1rem,5vw,3.5rem)] font-semibold leading-[1.08] tracking-[-0.03em] text-balance">
              Know your cash position
              <br className="hidden sm:block" />{" "}
              <span className="text-primary">13 weeks before it happens.</span>
            </h1>
            <p className="mx-auto mt-5 max-w-xl text-[15.5px] leading-relaxed text-muted-foreground text-pretty">
              RUNWAY turns scattered bank, invoice and GST data into one reconciled
              ledger, then forecasts your cash with a real uncertainty band — so you
              act while there is still time to act.
            </p>
            <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
              <Link href="/login"
                    className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90">
                Open the live demo <ArrowRight className="size-4" />
              </Link>
              <Link href="/how-it-works"
                    className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface px-5 py-2.5 text-sm font-medium transition-colors hover:bg-surface-hover">
                How it works
              </Link>
            </div>
            <p className="mt-4 text-xs text-muted-foreground">
              No card, no setup. Pre-filled demo credentials.
            </p>
          </div>

          <div className="mt-14">
            <ProductPreview />
          </div>
        </div>
      </section>

      {/* ── proof strip ── */}
      <Section className="!py-10">
        <dl className="grid grid-cols-2 gap-6 rounded-xl border border-border bg-card px-6 py-6 sm:grid-cols-4">
          {PROOF.map((p) => (
            <div key={p.k} className="text-center">
              <dt className="font-display text-2xl font-semibold tracking-tight tnum">{p.k}</dt>
              <dd className="mt-1 text-xs text-muted-foreground">{p.v}</dd>
            </div>
          ))}
        </dl>
      </Section>

      {/* ── how it works ── */}
      <Section id="how">
        <SectionLabel>How it works</SectionLabel>
        <div className="mt-3">
          <SectionTitle>Three steps from raw statements to a decision you can defend.</SectionTitle>
        </div>
        <ol className="mt-10 grid gap-6 md:grid-cols-3">
          {STEPS.map((s) => (
            <li key={s.n} className="relative">
              <span className="grid size-8 place-items-center rounded-lg border border-border bg-surface font-display text-sm font-semibold text-primary">
                {s.n}
              </span>
              <h3 className="mt-4 font-display text-[15px] font-semibold tracking-tight">
                {s.title}
              </h3>
              <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground text-pretty">
                {s.body}
              </p>
            </li>
          ))}
        </ol>
      </Section>

      {/* ── features ── */}
      <Section id="features" className="border-t border-border bg-surface/20">
        <SectionLabel>What you get</SectionLabel>
        <div className="mt-3">
          <SectionTitle
            sub="Every figure is computed from your own ledger. Nothing is hardcoded, and a prediction is never shown as a fact.">
            Built for the way an MSME actually runs.
          </SectionTitle>
        </div>
        <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <FeatureCard icon={<Database className="size-4.5" />} title="One reconciled ledger"
            body="Bank, gateway, invoice and GST rows deduped, categorised and matched to invoices. Every number traces back to a source row." />
          <FeatureCard icon={<LineChart className="size-4.5" />} title="13-week cash forecast"
            body="Built from your real invoices and obligations, not a curve fitted to past balances. P10–P90 band, breach probability, runway in weeks." />
          <FeatureCard icon={<GitBranch className="size-4.5" />} title="Scenario lab"
            body="Model a new order, a late customer, a cost rise or a loan. Same engine, same random draws — so the difference is the decision." />
          <FeatureCard icon={<Users className="size-4.5" />} title="Customer & supplier behaviour"
            body="Who pays on time, who stretches, which suppliers you depend on, and what MSMED deadlines are bearing down on you." />
          <FeatureCard icon={<CalendarClock className="size-4.5" />} title="Obligation calendar"
            body="GST, payroll, PF/ESI, rent and EMIs scheduled on their real due dates, with 45-day coverage shown against expected inflows." />
          <FeatureCard icon={<ShieldCheck className="size-4.5" />} title="Cash Health Passport"
            body="A shareable report for a lender or your CA. Every figure carries its basis and evidence rank, and it is not a credit score." />
        </div>
        <div className="mt-8">
          <Link href="/features"
                className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline">
            See all features <ArrowRight className="size-3.5" />
          </Link>
        </div>
      </Section>

      {/* ── pricing ── */}
      <Section id="pricing">
        <SectionLabel>Pricing</SectionLabel>
        <div className="mt-3">
          <SectionTitle sub="RUNWAY is a demonstration build. There is nothing to buy here — the pricing below is what a product like this would look like, shown so the page reads like a real SaaS site.">
            Simple, when it ships.
          </SectionTitle>
        </div>
        <div className="mt-10 grid gap-4 lg:grid-cols-3">
          {[
            { name: "Owner", price: "₹1,499", unit: "/month",
              for: "One business, one owner",
              items: ["13-week forecast", "Scenario lab", "Ledger imports", "WhatsApp briefing"] },
            { name: "Business", price: "₹4,999", unit: "/month", featured: true,
              for: "With your accountant in the loop",
              items: ["Everything in Owner", "Accountant access", "Cash Health Passport", "CSV exports", "Prioritised collections"] },
            { name: "Lender", price: "Custom", unit: "",
              for: "Portfolio-level visibility",
              items: ["Everything in Business", "Multi-business portfolio", "Consented passport sharing", "Portfolio risk roll-up"] },
          ].map((p) => (
            <div key={p.name}
                 className={"rounded-xl border p-5 " + (p.featured
                   ? "border-primary/40 bg-primary-soft/40" : "border-border bg-card")}>
              {p.featured && (
                <span className="rw-chip border-primary/30 bg-primary-soft text-primary">
                  Most useful
                </span>
              )}
              <h3 className="mt-2 font-display text-[15px] font-semibold">{p.name}</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">{p.for}</p>
              <p className="mt-4 font-display text-3xl font-semibold tracking-tight">
                {p.price}<span className="text-sm font-normal text-muted-foreground">{p.unit}</span>
              </p>
              <ul className="mt-4 space-y-2">
                {p.items.map((i) => (
                  <li key={i} className="flex items-start gap-2 text-[13px] text-muted-foreground">
                    <Check className="mt-0.5 size-3.5 shrink-0 text-primary" />
                    {i}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      {/* ── closing ── */}
      <Section className="border-t border-border">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-[26px] font-semibold leading-tight tracking-tight text-balance sm:text-3xl">
            Open the demo workspace.
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground text-pretty">
            A synthetic wholesale distributor with two years of history, twelve
            months of GST and a live 13-week forecast. Sign in with the pre-filled
            credentials and explore every screen.
          </p>
          <Link href="/login"
                className="mt-7 inline-flex items-center gap-1.5 rounded-lg bg-primary px-5 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90">
            Open the live demo <ArrowRight className="size-4" />
          </Link>
        </div>
      </Section>
    </MarketingShell>
  );
}
