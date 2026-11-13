import Link from "next/link";
import {
  ArrowRight, Banknote, BarChart3, Boxes, Brain, CalendarClock, Database,
  FileBarChart, GitBranch, LineChart, MessageSquare, Plug, Receipt,
  ShieldAlert, ShieldCheck, Users, Workflow,
} from "lucide-react";
import { MarketingShell, Section, SectionLabel, SectionTitle } from "@/components/marketing/site";

export const metadata = {
  title: "Features",
  description:
    "Everything RUNWAY does: reconciled ledger, 13-week probabilistic cash " +
    "forecast, scenario lab, collection priorities, obligation calendar and a " +
    "shareable Cash Health Passport.",
};

const GROUPS: {
  id: string; label: string; blurb: string;
  items: { icon: any; title: string; body: string }[];
}[] = [
  {
    id: "ledger", label: "The ledger",
    blurb: "One reconciled view of money in, money out and money owed.",
    items: [
      { icon: Database, title: "Multi-source import",
        body: "Bank CSV, payment-gateway settlements, sales and purchase invoices, and GST returns land in one normalised schema with their raw rows preserved." },
      { icon: Receipt, title: "Automatic categorisation",
        body: "Every transaction is classified with a stated confidence and the rule that fired. Low-confidence rows are surfaced for review instead of guessed away." },
      { icon: ShieldCheck, title: "Duplicate detection",
        body: "A hard duplicate on a bank reference is rejected. A soft duplicate is imported and flagged — a business genuinely can pay the same supplier twice." },
      { icon: Workflow, title: "Payment matching",
        body: "Inbound and outbound payments are allocated to open invoices with a confidence score and a written rationale for every match." },
    ],
  },
  {
    id: "forecast", label: "The forecast",
    blurb: "Thirteen weeks, built from things that actually exist.",
    items: [
      { icon: LineChart, title: "13-week probabilistic cash path",
        body: "Monte Carlo over your real invoices, obligations and run-rate sales. P10, P50 and P90 — never a single confident line." },
      { icon: BarChart3, title: "Breach probability and runway",
        body: "How many simulated paths fall below your safety buffer, when the median path first crosses it, and runway in weeks at P10/P50/P90." },
      { icon: ShieldAlert, title: "Liquidity VaR and CVaR",
        body: "Shortfall against your buffer at a stated confidence, plus the mean shortfall beyond it. Defined in the assumptions, with no regulatory pretence." },
      { icon: Brain, title: "Payment-delay prediction",
        body: "Invoice-level predicted payment dates with a conformal interval, shipped only if the model beats its own baseline on held-out data." },
    ],
  },
  {
    id: "decisions", label: "Decisions",
    blurb: "Test it before you commit to it.",
    items: [
      { icon: GitBranch, title: "Scenario lab",
        body: "New order, late customer, default, revenue shock, cost rise, hiring, equipment, financing, invoice discounting, supplier terms, deferred purchase, one-off expense." },
      { icon: BarChart3, title: "Common random numbers",
        body: "Baseline and scenario share their random draws, so a difference in the result is the decision rather than sampling noise." },
      { icon: ShieldAlert, title: "Stress tests",
        body: "Standardised shocks run side by side so you can see which one actually threatens the buffer." },
      { icon: Brain, title: "Ranked recommendations",
        body: "Every action carries its expected effect, its downside, the evidence behind it and a deadline — and none of them execute themselves." },
    ],
  },
  {
    id: "money", label: "Customers and suppliers",
    blurb: "Who pays, who stretches, and what is bearing down on you.",
    items: [
      { icon: Users, title: "Payment behaviour per buyer",
        body: "Mean delay against terms, reliability score, risk band and open exposure — computed on settled invoices only, because an open invoice says nothing about speed." },
      { icon: Boxes, title: "Supplier dependency",
        body: "Concentration, terms, early-payment discounts you are leaving on the table, and MSMED-protected exposure." },
      { icon: CalendarClock, title: "Obligation calendar",
        body: "GST, TDS, payroll, PF/ESI, rent, insurance and EMIs on their real due dates, with 45-day coverage against expected inflows." },
      { icon: Banknote, title: "Collection priorities",
        body: "Overdue invoices ranked by size, urgency and counterparty risk, with a specific recommended action for each." },
    ],
  },
  {
    id: "share", label: "Reporting and sharing",
    blurb: "For your CA, your bank, and your own records.",
    items: [
      { icon: FileBarChart, title: "Cash Health Passport",
        body: "Every disclosed figure carries its basis and evidence rank. Explicitly not a credit rating and not issued by a credit information company." },
      { icon: ShieldCheck, title: "Consented sharing",
        body: "Share the passport by link with an expiry you set, and revoke it at any time. Every access is audited." },
      { icon: MessageSquare, title: "Briefings you can forward",
        body: "The morning briefing as a WhatsApp or email message, and a payment reminder composed from the customer's own numbers — you send it, not us." },
      { icon: Plug, title: "CSV exports",
        body: "Transactions, receivables, payables and the passport as CSV with paise kept integral and figures labelled by state." },
    ],
  },
];

export default function FeaturesPage() {
  return (
    <MarketingShell>
      <Section className="!pb-0 !pt-14">
        <SectionLabel>Features</SectionLabel>
        <div className="mt-3">
          <SectionTitle sub="Five groups, one engine. Each figure below is produced by the same deterministic pipeline that runs in the workspace — there is no second, simpler path used for demos.">
            Everything RUNWAY does.
          </SectionTitle>
        </div>
      </Section>

      {GROUPS.map((g) => (
        <Section key={g.id} id={g.id} className="!py-10">
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-border pb-3">
            <h2 className="font-display text-lg font-semibold tracking-tight">{g.label}</h2>
            <p className="text-[13.5px] text-muted-foreground">{g.blurb}</p>
          </div>
          <div className="mt-6 grid gap-4 sm:grid-cols-2">
            {g.items.map((it) => {
              const Icon = it.icon;
              return (
                <div key={it.title}
                     className="rounded-xl border border-border bg-card p-5 transition-colors hover:border-border-strong">
                  <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="size-4.5" />
                  </span>
                  <h3 className="mt-3.5 font-display text-[15px] font-semibold tracking-tight">
                    {it.title}
                  </h3>
                  <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground text-pretty">
                    {it.body}
                  </p>
                </div>
              );
            })}
          </div>
        </Section>
      ))}

      <Section className="border-t border-border">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="font-display text-[26px] font-semibold leading-tight tracking-tight text-balance">
            See it on real numbers.
          </h2>
          <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">
            The demo workspace has two years of history and a live forecast.
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
