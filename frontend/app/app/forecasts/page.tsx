"use client";

import { useState } from "react";
import { Activity, Gauge, Info, Shuffle, TrendingDown } from "lucide-react";
import { BreachBars, CashBandChart, FlowBars } from "@/components/runway/charts";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Stat, StateBadge,
} from "@/components/runway/primitives";
import {
  Details, ExportButton, Note, PageHeader, Rows, Tabs, useTabs,
} from "@/components/runway/page-kit";
import { useApi } from "@/lib/use-api";
import { inr, pct, shortDate, weeks } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function ForecastsPage() {
  const { data, loading, error, reload } = useApi<any>("/api/states/predicted");
  const [show, setShow] = useTabs("forecasts", "cash");

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data?.series) return <LoadingPanel rows={8} />;
  const s = data.series;
  const a = data.assumptions ?? {};

  return (
    <div className="space-y-5">
      <PageHeader
        title="Cash runway"
        subtitle="Assembled from the invoices and obligations already on file, then simulated to show the range rather than a single number."
        state={<StateBadge state="predicted" size="md" />} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Runway P50" value={weeks(s.runway_weeks_p50)} state="predicted"
              hint="Median weeks before cash falls below the safety buffer"
              sub={s.runway_weeks_p50 >= s.horizon_weeks ? "beyond the horizon" : undefined} />
        <Stat label="Runway P10" value={weeks(s.runway_weeks_p10)} tone="warn" state="predicted"
              hint="The pessimistic path — the one worth planning against" />
        <Stat label="Minimum cash P50" value={inr(s.min_cash_p50_paise)} state="predicted" />
        <Stat label="Minimum cash P10" value={inr(s.min_cash_p10_paise)} state="predicted"
              tone={s.min_cash_p10_paise < 0 ? "loss" : "warn"} />
        <Stat label="Chance of breach" value={pct(s.breach_probability)} state="predicted"
              tone={s.breach_probability > 0.3 ? "loss" : s.breach_probability > 0.12 ? "warn" : "gain"}
              sub={s.first_breach_week ? `first in week ${s.first_breach_week}` : "no breach in the median path"} />
      </div>

      <Tabs active={show} onChange={(k) => setShow(k as any)} tabs={[
        { key: "cash", label: "Cash position" },
        { key: "flows", label: "Inflow vs outflow" },
      ]} />

      <Panel
        title={show === "cash" ? "Projected cash position" : "Expected movement by week"}
        description={`${s.paths.toLocaleString("en-IN")} Monte Carlo paths · seed ${s.seed} · horizon ${s.horizon_weeks} weeks`}
        bodyClass="p-2 pt-3">
        {show === "cash"
          ? <CashBandChart series={s} height={360} />
          : <FlowBars weeks={s.week_starts} inflow={s.inflow_p50} outflow={s.outflow_p50} height={340} />}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Where the risk sits"
               description="Probability of falling below the safety buffer, week by week"
               bodyClass="p-2 pt-3">
          <BreachBars weeks={s.week_starts} probs={s.breach_prob_by_week} height={200} />
          <div className="grid gap-3 p-2 sm:grid-cols-3">
            <Stat label="Liquidity VaR (95%)" value={inr(s.liquidity_var_paise)} tone="warn"
                  hint="Shortfall against the buffer at the 95th percentile" />
            <Stat label="Liquidity CVaR (95%)" value={inr(s.liquidity_cvar_paise)} tone="loss"
                  hint="Average shortfall in the worst 5% of paths" />
            <Stat label="Negative cash risk" value={pct(s.negative_cash_probability)}
                  tone={s.negative_cash_probability > 0.1 ? "loss" : "neutral"} />
          </div>
          <div className="px-2 pb-1">
            <Note>{a.var_definition}</Note>
          </div>
        </Panel>

        <Panel title="Sensitivity"
               description="How the minimum cash position moves when one assumption changes. Each row uses the same random draws as the baseline, so the difference is the assumption rather than noise.">
          {data.sensitivity?.length ? (
            <ul className="space-y-2">
              {data.sensitivity.map((row: any, i: number) => (
                <li key={i} className="flex items-center justify-between gap-3 border-b border-border/60 pb-2 last:border-0">
                  <span className="min-w-0 flex-1 text-[13px] text-pretty">{row.assumption}</span>
                  <span className="flex shrink-0 items-center gap-3">
                    <span className={cn("text-[13px] tnum",
                      row.min_cash_p50_delta_paise >= 0 ? "text-fin-gain" : "text-fin-loss")}>
                      {row.min_cash_p50_delta_paise >= 0 ? "+" : "−"}
                      {inr(Math.abs(row.min_cash_p50_delta_paise), { compact: true })}
                    </span>
                    <span className="w-16 text-right text-[11px] text-muted-foreground tnum">
                      {row.runway_p50_delta_weeks >= 0 ? "+" : ""}
                      {row.runway_p50_delta_weeks} wk
                    </span>
                  </span>
                </li>
              ))}
            </ul>
          ) : <p className="py-6 text-center text-sm text-muted-foreground">Not computed for this view.</p>}
        </Panel>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Forecast drivers" description="What is actually moving the number">
          <ul className="space-y-2">
            {s.drivers?.map((d: any, i: number) => (
              <li key={i} className="flex items-start justify-between gap-3 border-b border-border/60 pb-2 last:border-0">
                <div className="min-w-0">
                  <p className="text-[13px]">{d.driver}</p>
                  <p className="text-[11px] text-muted-foreground">
                    {d.count} item{d.count === 1 ? "" : "s"} · {d.evidence}
                  </p>
                </div>
                <span className={cn("shrink-0 text-[13px] tnum",
                  d.direction === "inflow" ? "text-fin-gain" : "text-fin-loss")}>
                  {d.direction === "inflow" ? "+" : "−"}{inr(d.amount_paise, { compact: true })}
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Method and assumptions"
               description="Stated plainly, because a forecast you cannot interrogate is a forecast you should not trust">
          <Evidence items={[
            { label: "Method", value: "Ledger-driven Monte Carlo" },
            { label: "Paths", value: s.paths.toLocaleString("en-IN") },
            { label: "Seed", value: String(s.seed) },
            { label: "Delay correlation ρ", value: String(a.delay_correlation_rho ?? "—") },
            ...(a.revenue_delay_coupling
              ? [{ label: "Revenue/delay coupling", value: String(a.revenue_delay_coupling) }] : []),
            { label: "Correlation source", value: a.delay_correlation_source ?? "—" },
            { label: "Revenue CV", value: String(a.revenue_cv ?? "—") },
            { label: "Collection lag (median)", value: `${a.collection_lag_days_median ?? "—"} days` },
            { label: "Open receivables", value: inr(a.open_receivables_paise ?? 0) },
            { label: "Scheduled outflows", value: inr(a.scheduled_outflows_paise ?? 0) },
            { label: "Revenue run-rate method", value: a.revenue_runrate?.method ?? "—" },
            { label: "Operating cost basis", value: a.recurring_opex?.method ?? "—" },
          ]} dense />
          <div className="mt-3 space-y-2">
            {a.revenue_delay_coupling_note && (
              <Details label="Why demand and payment speed are linked" dense>
                {a.revenue_delay_coupling_note}
              </Details>
            )}
            {a.horizon_truncation_note && (
              <Details label="Reading a revenue shock" dense>
                {a.horizon_truncation_note}
              </Details>
            )}
            {a.quantile_convention && (
              <Details label="What P10 and P90 mean" dense>{a.quantile_convention}</Details>
            )}
          </div>
          {a.beyond_horizon_paise && (
            <div className="mt-3">
              <Details label="What falls outside the 13-week window" dense>
                {a.beyond_horizon_paise.note} Receivables{" "}
                {inr(a.beyond_horizon_paise.receivables)}, future sales{" "}
                {inr(a.beyond_horizon_paise.sales_not_yet_invoiced)}, payables{" "}
                {inr(a.beyond_horizon_paise.payables)}.
              </Details>
            </div>
          )}
          {a.payment_delay_model && (
            <div className="mt-3 rounded-lg border border-border bg-surface p-3">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Payment-delay model
              </p>
              <p className="mt-1.5 text-[11px] leading-relaxed text-muted-foreground text-pretty">
                {a.payment_delay_model.model_selection ?? a.payment_delay_model.reason}
              </p>
              {a.payment_delay_model.model && (
                <p className="mt-1.5 text-[11px] text-muted-foreground tnum">
                  Held-out MAE {a.payment_delay_model.model.mae_days} days ·
                  baseline {a.payment_delay_model.baseline_customer_median?.mae_days} days ·
                  P10–P90 coverage {pct(a.payment_delay_model.coverage_p10_p90_conformal)} (target 80%)
                </p>
              )}
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}
