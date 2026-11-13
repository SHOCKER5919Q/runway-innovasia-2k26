"use client";

import { useState } from "react";
import { AlertTriangle, Check, ShieldAlert, TrendingDown, X } from "lucide-react";
import { RiskHeatmap, RiskScatter } from "@/components/runway/charts";
import {
  ErrorState, Evidence, LevelPill, LoadingPanel, Panel, Provenance, SectionHeader,
  Stat, StateBadge,
} from "@/components/runway/primitives";
import { useApi } from "@/lib/use-api";
import { inr, money, pct, titleCase, weeks } from "@/lib/format";
import { cn } from "@/lib/utils";

const LEVELS = ["critical", "warning", "watch", "info"] as const;

export default function RiskPage() {
  const { data, loading, error, reload } = useApi<any>("/api/risk");
  const customers = useApi<any>("/api/customers");
  const [filter, setFilter] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={8} />;

  const alerts = filter ? data.alerts.filter((a: any) => a.level === filter) : data.alerts;
  const m = data.metrics;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Risk Centre"
        description="Early warnings from your own ledger, plus stress tests that ask whether the business survives — not whether the event will happen." />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Liquidity VaR (95%)" value={money(m.liquidity_var)} tone="warn"
              state="predicted" hint={m.definitions?.liquidity_var} />
        <Stat label="Liquidity CVaR (95%)" value={money(m.liquidity_cvar)} tone="loss"
              state="predicted" hint={m.definitions?.liquidity_cvar} />
        <Stat label="Minimum cash P10" value={money(m.min_cash_p10)} state="predicted"
              tone={(m.min_cash_p10?.paise ?? 0) < 0 ? "loss" : "warn"} />
        <Stat label="Chance of breach" value={pct(m.breach_probability)} state="predicted"
              tone={m.breach_probability > 0.3 ? "loss" : "warn"} />
        <Stat label="Negative cash risk" value={pct(m.negative_cash_probability)}
              state="predicted"
              tone={m.negative_cash_probability > 0.1 ? "loss" : "neutral"} />
      </div>

      {/* ── alerts ── */}
      <Panel title="Open alerts"
             description="Each alert answers six questions: what happened, why it matters, the evidence, the likely impact, what to do, and what happens if you do nothing."
             actions={
               <div className="flex flex-wrap gap-1.5">
                 <button onClick={() => setFilter(null)}
                   className={cn("rounded-md border px-2 py-0.5 text-[11px]",
                     !filter ? "border-primary bg-primary-soft text-primary" : "border-border text-muted-foreground")}>
                   All {data.alerts.length}
                 </button>
                 {LEVELS.filter((l) => data.counts[l] > 0).map((l) => (
                   <button key={l} onClick={() => setFilter(l === filter ? null : l)}
                     className={cn("rounded-md border px-2 py-0.5 text-[11px] capitalize",
                       filter === l ? "border-primary bg-primary-soft text-primary"
                                    : "border-border text-muted-foreground")}>
                     {l} {data.counts[l]}
                   </button>
                 ))}
               </div>}
             bodyClass="p-0">
        <ul className="divide-y divide-border">
          {alerts.map((a: any, idx: number) => {
            const alertKey = `${a.code}:${a.title}:${idx}`;
            return (
            <li key={alertKey}>
              <button onClick={() => setOpen(open === alertKey ? null : alertKey)}
                      aria-expanded={open === alertKey}
                      className="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-surface-hover">
                <span className="mt-0.5 shrink-0"><LevelPill level={a.level} /></span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[13px] font-medium text-pretty">{a.title}</span>
                  <span className="mt-0.5 block line-clamp-2 text-[11px] text-muted-foreground text-pretty">
                    {a.what_happened}
                  </span>
                </span>
                {a.impact?.paise > 0 && (
                  <span className="shrink-0 text-[13px] tnum text-muted-foreground">
                    {a.impact.compact}
                  </span>
                )}
              </button>
              {open === alertKey && (
                <div className="space-y-3 border-t border-border bg-surface/40 px-4 py-4 text-[13px]">
                  <Field label="What happened">{a.what_happened}</Field>
                  <Field label="Why it matters">{a.why_it_matters}</Field>
                  {a.evidence?.length > 0 && (
                    <div>
                      <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Evidence
                      </p>
                      <Evidence items={a.evidence} dense />
                    </div>
                  )}
                  <Field label="Likely financial impact">
                    {a.impact?.display ?? "—"}
                    {a.impact_date ? ` around ${a.impact_date}` : ""}
                  </Field>
                  <Field label="What to do">{a.recommended_action}</Field>
                  <Field label="If nothing is done">{a.if_ignored}</Field>
                </div>
              )}
            </li>
            );
          })}
          {alerts.length === 0 && (
            <li className="px-4 py-12 text-center text-sm text-muted-foreground">
              No alerts at this level. That is a result, not an empty screen.
            </li>
          )}
        </ul>
      </Panel>

      {/* ── stress tests ── */}
      <Panel title="Stress tests"
             description="Each shock is re-simulated against the same random draws as the baseline, so the delta is the shock itself.">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="pb-2 font-medium">Scenario</th>
                <th className="pb-2 text-right font-medium">Min cash P10</th>
                <th className="pb-2 text-right font-medium">Change</th>
                <th className="pb-2 text-right font-medium">Runway</th>
                <th className="pb-2 text-right font-medium">Breach</th>
                <th className="pb-2 text-right font-medium">Survives</th>
              </tr>
            </thead>
            <tbody>
              {data.stress_tests?.map((t: any) => (
                <tr key={t.key} className="border-b border-border/50 last:border-0">
                  <td className="py-2.5">
                    <p className="text-[13px]">{t.label}</p>
                    <p className="text-[11px] text-muted-foreground text-pretty">{t.description}</p>
                  </td>
                  <td className={cn("py-2.5 text-right tnum",
                    t.min_cash_p10_paise < 0 ? "text-fin-loss" : "")}>
                    {inr(t.min_cash_p10_paise)}
                  </td>
                  <td className="py-2.5 text-right tnum text-fin-loss">
                    {inr(t.min_cash_delta_paise, { compact: true })}
                  </td>
                  <td className="py-2.5 text-right tnum">{weeks(t.runway_weeks_p50)}</td>
                  <td className="py-2.5 text-right tnum">{pct(t.breach_probability)}</td>
                  <td className="py-2.5 text-right">
                    {t.survives ? (
                      <span className="rw-chip border-fin-gain/30 bg-fin-gain-soft text-fin-gain">
                        <Check className="size-3" /> yes
                      </span>
                    ) : t.survives_with_overdraft ? (
                      <span className="rw-chip border-fin-warn/30 bg-fin-warn-soft text-fin-warn">
                        with OD
                      </span>
                    ) : (
                      <span className="rw-chip border-fin-loss/30 bg-fin-loss-soft text-fin-loss">
                        <X className="size-3" /> no
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Provenance>
          "Survives" means the P10 cash path stays at or above zero. "With OD" means it
          only does so after drawing the sanctioned overdraft, which is credit, not cash.
        </Provenance>
      </Panel>

      {/* ── risk surface ── */}
      {data.risk_surface && (
        <Panel title="Risk surface"
               description="How likely cash is to fall below each level, week by week">
          <RiskHeatmap weeks={data.risk_surface.week_starts} levels={data.risk_surface.levels} />
        </Panel>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Customer risk map"
               description="Mean delay against open exposure. Bubble size is the reliability score.">
          {customers.data?.customers?.length ? (
            <RiskScatter points={customers.data.customers.map((c: any) => ({
              name: c.name, delay: c.mean_delay_days,
              exposure: c.outstanding_paise, reliability: c.reliability_score,
            }))} />
          ) : <LoadingPanel rows={3} />}
        </Panel>

        <Panel title="Concentration"
               description={data.concentration.interpretation}>
          <div className="grid grid-cols-3 gap-3">
            <Stat label="HHI" value={data.concentration.counterparty_hhi.toFixed(3)}
                  sub={data.concentration.counterparty_band}
                  tone={data.concentration.counterparty_band === "high" ? "loss"
                        : data.concentration.counterparty_band === "moderate" ? "warn" : "gain"} />
            <Stat label="Top customer" value={pct(data.concentration.top1_share)} />
            <Stat label="Top three" value={pct(data.concentration.top3_share)} />
          </div>
          <div className="mt-4">
            <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Do delays move together?
            </p>
            <p className="text-xs leading-relaxed text-muted-foreground text-pretty">
              {data.correlation?.interpretation ??
               data.correlation?.reason ?? "Not enough history to estimate."}
              {data.correlation?.mean_pairwise_r !== undefined &&
                ` Mean pairwise correlation ${data.correlation.mean_pairwise_r}.`}
            </p>
          </div>
        </Panel>
      </div>

      {/* ── anomalies ── */}
      <Panel title="Anomalies" description="Interpretable detectors only — every flag says why">
        {data.anomalies?.length ? (
          <ul className="space-y-2">
            {data.anomalies.slice(0, 12).map((a: any, i: number) => (
              <li key={i} className="flex items-start gap-3 border-b border-border/60 pb-2 last:border-0">
                <LevelPill level={a.severity === "watch" ? "watch" : a.severity} />
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] text-pretty">{a.why}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    {a.date} · {titleCase(a.category)}
                    {a.counterparty ? ` · ${a.counterparty}` : ""}
                  </p>
                </div>
                <span className="shrink-0 text-[12px] tnum">{inr(a.amount_paise, { compact: true })}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="py-6 text-center text-sm text-muted-foreground">No anomalies detected.</p>
        )}
      </Panel>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </p>
      <p className="leading-relaxed text-pretty">{children}</p>
    </div>
  );
}
