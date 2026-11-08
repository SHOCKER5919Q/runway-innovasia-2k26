"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowRight, Database, LineChart, Sparkles, Target } from "lucide-react";
import { motion } from "motion/react";
import { CashBandChart } from "@/components/runway/charts";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { Reveal, EASE_OUT } from "@/components/runway/motion";
import { useApi } from "@/lib/use-api";
import { inr, longDate, money, pct, shortDate, weeks, STATE_META } from "@/lib/format";
import { cn } from "@/lib/utils";

type Tab = "actual" | "predicted" | "simulated" | "compare";

export default function StateCentrePage() {
  const [tab, setTab] = useState<Tab>("actual");
  const actual = useApi<any>("/api/states/actual");
  const predicted = useApi<any>("/api/states/predicted");
  const scenarios = useApi<any>("/api/scenarios");
  const recon = useApi<any>("/api/states/reconcile");

  if (actual.error) return <ErrorState message={actual.error} onRetry={actual.reload} />;

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Business State Centre"
        description="RUNWAY keeps three separate representations of your business. They are stored separately, versioned separately and never mixed — which is what stops an expectation being read as a fact."
      />

      {/* state selector */}
      <div className="grid gap-3 sm:grid-cols-3">
        {(["actual", "predicted", "simulated"] as const).map((k) => {
          const meta = STATE_META[k];
          const active = tab === k;
          return (
            <button key={k} onClick={() => setTab(k)} aria-pressed={active}
              className={cn("rw-card relative overflow-hidden p-4 text-left",
              "transition-[border-color,background-color,transform]",
                active ? "ring-1" : "hover:bg-surface-hover")}
              style={active ? { borderColor: meta.color, boxShadow: `0 0 0 1px ${meta.color}` } : undefined}>
              {active && (
                <motion.span layoutId="state-glow" transition={{ duration: 0.35, ease: EASE_OUT }}
                  className="pointer-events-none absolute inset-0" aria-hidden
                  style={{ background: meta.soft }} />
              )}
              <div className="relative">
                <div className="flex items-center justify-between">
                  <StateBadge state={k} size="md" />
                  {k === "actual" && <Database className="size-4 text-muted-foreground" />}
                  {k === "predicted" && <LineChart className="size-4 text-muted-foreground" />}
                  {k === "simulated" && <Sparkles className="size-4 text-muted-foreground" />}
                </div>
                <p className="mt-2.5 font-display text-sm font-semibold">{meta.question}</p>
                <p className="mt-1 text-xs text-muted-foreground text-pretty">{meta.blurb}</p>
              </div>
            </button>
          );
        })}
      </div>

      <div className="flex flex-wrap gap-2">
        {(["actual", "predicted", "simulated", "compare"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={cn("rounded-lg border px-3 py-1.5 text-xs capitalize transition-colors",
              tab === t ? "border-primary bg-primary-soft text-primary"
                        : "border-border text-muted-foreground hover:bg-surface-hover")}>
            {t === "compare" ? "Compare all three" : t}
          </button>
        ))}
      </div>

      {tab === "actual" && <ActualView data={actual.data} loading={actual.loading} />}
      {tab === "predicted" && (
        <PredictedView data={predicted.data} loading={predicted.loading} recon={recon.data} />
      )}
      {tab === "simulated" && <SimulatedView scenarios={scenarios.data} />}
      {tab === "compare" && (
        <CompareView actual={actual.data} predicted={predicted.data} scenarios={scenarios.data} />
      )}
    </div>
  );
}

function ActualView({ data, loading }: { data: any; loading: boolean }) {
  if (loading || !data) return <LoadingPanel rows={6} />;
  return (
    <div className="space-y-4">
      <Panel title="Actual state — financial reality"
             description={data.definition}
             actions={<StateBadge state="actual" />}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label="Cash in hand" value={money(data.cash)} />
          <Stat label="Restricted" value={money(data.restricted)}
                hint="Lien-marked or pledged — cannot fund operations" />
          <Stat label="Committed" value={money(data.committed)}
                hint="Reserved against obligations inside the commitment horizon" />
          <Stat label="Available liquidity" value={money(data.available_liquidity)} tone="gain" />
          <Stat label="Receivables" value={money(data.receivables)}
                sub={<>{money(data.receivables_overdue)} overdue</>} />
          <Stat label="Payables" value={money(data.payables)}
                sub={<>{money(data.payables_overdue)} past due</>} />
          <Stat label="Loan outstanding" value={money(data.loan_outstanding)} />
          <Stat label="Working capital" value={money(data.working_capital)} />
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Accounts" description="Opening balance plus credits less debits">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="pb-2 font-medium">Account</th>
                  <th className="pb-2 text-right font-medium">Opening</th>
                  <th className="pb-2 text-right font-medium">Credits</th>
                  <th className="pb-2 text-right font-medium">Debits</th>
                  <th className="pb-2 text-right font-medium">Closing</th>
                </tr>
              </thead>
              <tbody>
                {data.accounts.map((a: any) => (
                  <tr key={a.account_id} className="border-b border-border/50 last:border-0">
                    <td className="py-2">
                      <p className="text-[13px]">{a.name}</p>
                      <p className="text-[10px] text-muted-foreground">
                        {a.masked_number ?? a.kind}
                        {a.restricted_paise > 0 && ` · ${inr(a.restricted_paise, { compact: true })} restricted`}
                      </p>
                    </td>
                    <td className="py-2 text-right tnum">{inr(a.opening_paise)}</td>
                    <td className="py-2 text-right tnum text-fin-gain">{inr(a.credits_paise)}</td>
                    <td className="py-2 text-right tnum text-fin-loss">{inr(a.debits_paise)}</td>
                    <td className="py-2 text-right font-medium tnum">{inr(a.closing_paise)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Provenance>
            Opening balance + credits − debits = closing balance holds exactly for every
            account. Amounts are stored as integer paise, so no rounding drift is possible.
          </Provenance>
        </Panel>

        <Panel title="Committed cash" description="What has already been spoken for">
          {data.committed_breakdown?.length ? (
            <Evidence items={data.committed_breakdown.map((c: any) => ({
              label: `${c.label} (${shortDate(c.due_date)})`,
              value: inr(c.amount_paise),
            }))} />
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              Nothing is currently ring-fenced.
            </p>
          )}
          <div className="mt-4 rounded-lg border border-border bg-surface p-3 text-[11px] leading-relaxed text-muted-foreground">
            <strong className="text-foreground">Data quality {data.data_quality.score}/100.</strong>{" "}
            {data.data_quality.warnings?.join(" ") || "No warnings."}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function PredictedView({ data, loading, recon }: { data: any; loading: boolean; recon: any }) {
  if (loading || !data) return <LoadingPanel rows={6} />;
  const s = data.series;
  return (
    <div className="space-y-4">
      <Panel title="Predicted state — the likely future"
             description={data.definition} actions={<StateBadge state="predicted" />}
             bodyClass="p-2 pt-3">
        {s && <CashBandChart series={s} height={320} />}
        <div className="grid gap-3 p-2 sm:grid-cols-2 xl:grid-cols-4">
          <Stat label="Runway P50" value={weeks(s?.runway_weeks_p50)} state="predicted" />
          <Stat label="Runway P10" value={weeks(s?.runway_weeks_p10)} tone="warn" state="predicted" />
          <Stat label="Minimum cash P10" value={inr(s?.min_cash_p10_paise)}
                tone={s?.min_cash_p10_paise < 0 ? "loss" : "neutral"} state="predicted" />
          <Stat label="Chance of breach" value={pct(s?.breach_probability)}
                tone={s?.breach_probability > 0.3 ? "loss" : s?.breach_probability > 0.12 ? "warn" : "gain"}
                state="predicted" />
        </div>
        <div className="px-2 pb-2">
          <Provenance>{data.quantile_convention}</Provenance>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="What drives this forecast"
               description="Largest contributions first, with the evidence class for each">
          <ul className="space-y-2">
            {data.drivers?.map((d: any, i: number) => (
              <li key={i} className="flex items-start justify-between gap-3 border-b border-border/60 pb-2 last:border-0">
                <div className="min-w-0">
                  <p className="text-[13px]">{d.driver}</p>
                  <p className="text-[11px] text-muted-foreground">{d.evidence}</p>
                </div>
                <span className={cn("shrink-0 text-[13px] tnum",
                  d.direction === "inflow" ? "text-fin-gain" : "text-fin-loss")}>
                  {d.direction === "inflow" ? "+" : "−"}{inr(d.amount_paise, { compact: true })}
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Measured forecast accuracy"
               description="Past forecasts scored against what actually happened">
          {recon?.available ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                      <th className="pb-2 font-medium">Horizon</th>
                      <th className="pb-2 text-right font-medium">n</th>
                      <th className="pb-2 text-right font-medium">MAE</th>
                      <th className="pb-2 text-right font-medium">WAPE</th>
                      <th className="pb-2 text-right font-medium">P10–P90 coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recon.cash_forecast_by_horizon.slice(0, 8).map((h: any) => (
                      <tr key={h.horizon_weeks} className="border-b border-border/50 last:border-0">
                        <td className="py-1.5">{h.horizon_weeks} wk</td>
                        <td className="py-1.5 text-right tnum text-muted-foreground">{h.n}</td>
                        <td className="py-1.5 text-right tnum">{inr(h.mae_paise, { compact: true })}</td>
                        <td className="py-1.5 text-right tnum">{pct(h.wape, 1)}</td>
                        <td className={cn("py-1.5 text-right tnum",
                          h.p10_p90_coverage >= 0.7 ? "text-fin-gain" : "text-fin-warn")}>
                          {pct(h.p10_p90_coverage)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {recon.payment_prediction_accuracy && (
                <p className="mt-3 text-xs text-muted-foreground">
                  Payment-date predictions: MAE {recon.payment_prediction_accuracy.mae_days} days
                  over {recon.payment_prediction_accuracy.n} resolved invoices, with
                  {" "}{pct(recon.payment_prediction_accuracy.p10_p90_coverage)} falling inside the
                  P10–P90 band against an 80% target.
                </p>
              )}
              <Provenance>{recon.interpretation}</Provenance>
            </>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground text-pretty">
              {recon?.note ?? "No forecast has reached its target week yet."}
            </p>
          )}
        </Panel>
      </div>

      <Panel title="Assumptions on the record"
             description="Everything the forecast took as given, stored with the state version">
        <pre className="max-h-72 overflow-auto rounded-lg border border-border bg-surface p-3 text-[11px] leading-relaxed text-muted-foreground">
{JSON.stringify(data.assumptions, null, 2)}
        </pre>
      </Panel>
    </div>
  );
}

function SimulatedView({ scenarios }: { scenarios: any }) {
  const list = scenarios?.scenarios ?? [];
  return (
    <Panel title="Simulated state — alternative futures"
           description="Scenarios branch from a fixed baseline and never touch the ledger."
           actions={<Link href="/app/scenarios"
                          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:opacity-92">
             <Sparkles className="size-3.5" /> Open Scenario Lab
           </Link>}>
      {list.length === 0 ? (
        <div className="py-10 text-center">
          <p className="text-sm text-muted-foreground">No scenarios saved yet.</p>
          <Link href="/app/scenarios"
                className="mt-3 inline-flex items-center gap-1.5 text-sm text-primary hover:underline">
            Build your first one <ArrowRight className="size-3.5" />
          </Link>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="pb-2 font-medium">Scenario</th>
                <th className="pb-2 text-right font-medium">Min cash P50</th>
                <th className="pb-2 text-right font-medium">Min cash P10</th>
                <th className="pb-2 text-right font-medium">Runway</th>
                <th className="pb-2 text-right font-medium">Breach risk</th>
                <th className="pb-2 text-right font-medium">Decision</th>
              </tr>
            </thead>
            <tbody>
              {list.map((s: any) => (
                <tr key={s.id} className="border-b border-border/50 last:border-0">
                  <td className="py-2">
                    <Link href="/app/scenarios" className="text-[13px] hover:text-primary">{s.name}</Link>
                    <p className="text-[10px] capitalize text-muted-foreground">
                      {s.kind.replace(/_/g, " ")}
                    </p>
                  </td>
                  <td className="py-2 text-right tnum">{money(s.summary?.min_cash_p50)}</td>
                  <td className="py-2 text-right tnum">{money(s.summary?.min_cash_p10)}</td>
                  <td className="py-2 text-right tnum">{weeks(s.summary?.runway_weeks_p50)}</td>
                  <td className="py-2 text-right tnum">{pct(s.summary?.breach_probability)}</td>
                  <td className="py-2 text-right text-[11px] capitalize text-muted-foreground">
                    {s.decision?.status ?? "draft"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Provenance>
        A simulated payment is not a payment and a simulated loan is not a liability.
        There is no code path from the scenario engine to a ledger table.
      </Provenance>
    </Panel>
  );
}

function CompareView({ actual, predicted, scenarios }:
  { actual: any; predicted: any; scenarios: any }) {
  const s = predicted?.series;
  const scen = scenarios?.scenarios?.find((x: any) => x.summary);
  if (!s) return <LoadingPanel rows={6} />;
  return (
    <div className="space-y-4">
      <Panel title="All three states on one timeline"
             description="Actual is solid, predicted carries its uncertainty band, simulated is dashed. Each state also has its own hue, but the line treatment carries the meaning on its own."
             bodyClass="p-2 pt-3">
        <CashBandChart series={s} height={340} actualTo={0}
                       scenario={null} />
        <div className="flex flex-wrap gap-4 px-3 pb-2 pt-1 text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4"
              stroke="var(--state-actual)" strokeWidth="2.5" /></svg>
            Actual — recorded
          </span>
          <span className="flex items-center gap-1.5">
            <svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4"
              stroke="var(--state-predicted)" strokeWidth="2.5" /></svg>
            Predicted — with P10–P90 band
          </span>
          <span className="flex items-center gap-1.5">
            <svg width="26" height="8" aria-hidden><line x1="0" y1="4" x2="26" y2="4"
              stroke="var(--state-simulated)" strokeWidth="2.5" strokeDasharray="6 4" /></svg>
            Simulated — a what-if
          </span>
        </div>
      </Panel>

      <div className="grid gap-3 md:grid-cols-3">
        {[
          { k: "actual", title: "What is", rows: [
            ["Cash in hand", money(actual?.cash)],
            ["Available liquidity", money(actual?.available_liquidity)],
            ["Receivables", money(actual?.receivables)],
            ["Payables", money(actual?.payables)]] },
          { k: "predicted", title: "What is likely", rows: [
            ["Closing cash P50", inr(s.p50[s.p50.length - 1])],
            ["Minimum cash P10", inr(s.min_cash_p10_paise)],
            ["Runway P50", weeks(s.runway_weeks_p50)],
            ["Chance of breach", pct(s.breach_probability)]] },
          { k: "simulated", title: "What could be", rows: scen ? [
            [scen.name, ""],
            ["Minimum cash P50", money(scen.summary?.min_cash_p50)],
            ["Runway P50", weeks(scen.summary?.runway_weeks_p50)],
            ["Chance of breach", pct(scen.summary?.breach_probability)]]
            : [["No scenario saved yet", ""]] },
        ].map((col) => (
          <Panel key={col.k} title={col.title} actions={<StateBadge state={col.k as any} />}>
            <dl className="space-y-2 text-sm">
              {col.rows.map(([k, v], i) => (
                <div key={i} className="flex items-center justify-between gap-3 border-b border-border/50 pb-1.5 last:border-0">
                  <dt className="text-muted-foreground">{k}</dt>
                  <dd className="tnum">{v}</dd>
                </div>
              ))}
            </dl>
          </Panel>
        ))}
      </div>
    </div>
  );
}
