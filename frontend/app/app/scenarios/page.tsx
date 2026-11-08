"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Check, ChevronRight, GitBranch, Loader2, Play, Plus, Save, Scale, Sparkles,
  Trash2, TriangleAlert,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { CashBandChart } from "@/components/runway/charts";
import {
  Delta, EmptyState, ErrorState, LoadingPanel, Panel, Provenance, SectionHeader,
  Stat, StateBadge,
} from "@/components/runway/primitives";
import { EASE_OUT, Reveal } from "@/components/runway/motion";
import { api } from "@/lib/api";
import { useApi, useMutation } from "@/lib/use-api";
import { inr, money, pct, weeks } from "@/lib/format";
import { cn } from "@/lib/utils";

type Param = {
  key: string; label: string; kind: string; default: any;
  options?: { value: string; label: string }[]; help?: string;
};
type Kind = {
  kind: string; label: string; question: string; description: string; params: Param[];
};

export default function ScenarioLabPage() {
  const cat = useApi<{ catalogue: Kind[]; isolation: string; reproducibility: string }>(
    "/api/scenarios/catalogue");
  const saved = useApi<any>("/api/scenarios");
  const [selected, setSelected] = useState<string>("new_order");
  const [values, setValues] = useState<Record<string, any>>({});
  const [result, setResult] = useState<any>(null);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const [compareResult, setCompareResult] = useState<any>(null);
  const [name, setName] = useState("");

  const kind = useMemo(
    () => cat.data?.catalogue.find((k) => k.kind === selected),
    [cat.data, selected]);

  useEffect(() => {
    if (!kind) return;
    const v: Record<string, any> = {};
    kind.params.forEach((p) => { v[p.key] = p.default; });
    setValues(v);
    setName(kind.label);
    setResult(null);
  }, [kind]);

  const run = useMutation<void, any>(async () => {
    const r = await api.post<any>("/api/scenarios/quick-run",
      { kind: selected, parameters: values, paths: 2500 });
    setResult(r);
    return r;
  });

  const save = useMutation<void, any>(async () => {
    const r = await api.post<any>("/api/scenarios",
      { name: name || kind?.label, kind: selected, parameters: values, run_now: true });
    saved.reload();
    return r;
  });

  const compare = useMutation<void, any>(async () => {
    const r = await api.post<any>("/api/scenarios/compare", { scenario_ids: compareIds });
    setCompareResult(r);
    return r;
  });

  if (cat.error) return <ErrorState message={cat.error} onRetry={cat.reload} />;
  if (cat.loading || !cat.data) return <LoadingPanel rows={8} />;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Scenario Lab"
        description="Change an assumption, see the consequence. Baseline and scenario are simulated with the same random draws, so the difference you see is the decision — not the noise."
        actions={<StateBadge state="simulated" size="md" />} />

      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        {/* ── builder ── */}
        <div className="space-y-4">
          <Panel title="Choose a question" bodyClass="p-2">
            <ul className="max-h-[320px] space-y-0.5 overflow-y-auto">
              {cat.data.catalogue.map((k) => (
                <li key={k.kind}>
                  <button onClick={() => setSelected(k.kind)}
                    className={cn("w-full rounded-lg px-3 py-2.5 text-left transition-colors",
                      selected === k.kind ? "bg-primary-soft" : "hover:bg-surface-hover")}>
                    <p className={cn("text-[13px] font-medium",
                      selected === k.kind && "text-primary")}>{k.label}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground text-pretty">{k.question}</p>
                  </button>
                </li>
              ))}
            </ul>
          </Panel>

          {kind && (
            <Panel title="Set the assumptions" description={kind.description}>
              <div className="space-y-3.5">
                {kind.params.map((p) => (
                  <ParamField key={p.key} param={p} value={values[p.key]}
                              onChange={(v) => setValues((s) => ({ ...s, [p.key]: v }))} />
                ))}
              </div>
              <div className="mt-4 flex gap-2">
                <button onClick={() => run.run()} disabled={run.pending}
                  className="inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-xs font-medium text-primary-foreground hover:opacity-92 disabled:opacity-60">
                  {run.pending ? <Loader2 className="size-3.5 animate-spin" /> : <Play className="size-3.5" />}
                  Simulate
                </button>
                <button onClick={() => save.run()} disabled={save.pending}
                  className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs hover:bg-surface-hover disabled:opacity-60">
                  {save.pending ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
                  Save
                </button>
              </div>
              {(run.error || save.error) && (
                <p role="alert" className="mt-2 rounded-md border border-fin-loss/30 bg-fin-loss-soft px-2.5 py-1.5 text-[11px] text-fin-loss">
                  {run.error || save.error}
                </p>
              )}
              <input value={name} onChange={(e) => setName(e.target.value)}
                     placeholder="Name this scenario"
                     className="mt-3 h-9 w-full rounded-lg border border-border bg-surface px-3 text-xs outline-none focus:border-primary/60" />
            </Panel>
          )}
        </div>

        {/* ── result ── */}
        <div className="space-y-4">
          <AnimatePresence mode="wait">
            {result ? (
              <motion.div key="res" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.35, ease: EASE_OUT }} className="space-y-4">
                <ScenarioResult result={result} />
                {result.long_horizon && <LongHorizon lh={result.long_horizon} />}
              </motion.div>
            ) : (
              <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
                <Panel title="Result">
                  <EmptyState
                    icon={<Sparkles className="size-5" />}
                    title="Pick a question and press Simulate"
                    description="RUNWAY will run the baseline and your scenario side by side over the same simulated futures, then show exactly what changed."
                  />
                  <Provenance>{cat.data.isolation} {cat.data.reproducibility}</Provenance>
                </Panel>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── saved scenarios & comparison ── */}
          <Panel title="Saved scenarios"
                 description="Select two or more to compare them against the same baseline"
                 actions={compareIds.length >= 2 && (
                   <button onClick={() => compare.run()} disabled={compare.pending}
                     className="inline-flex items-center gap-1.5 rounded-lg border border-primary/40 bg-primary-soft px-2.5 py-1 text-xs text-primary">
                     {compare.pending ? <Loader2 className="size-3 animate-spin" /> : <Scale className="size-3" />}
                     Compare {compareIds.length}
                   </button>)}>
            {saved.data?.scenarios?.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                      <th className="w-8 pb-2" />
                      <th className="pb-2 font-medium">Scenario</th>
                      <th className="pb-2 text-right font-medium">Min cash P50</th>
                      <th className="pb-2 text-right font-medium">Min cash P10</th>
                      <th className="pb-2 text-right font-medium">Runway</th>
                      <th className="pb-2 text-right font-medium">Breach</th>
                      <th className="w-8 pb-2" />
                    </tr>
                  </thead>
                  <tbody>
                    {saved.data.scenarios.map((s: any) => (
                      <tr key={s.id} className="border-b border-border/50 last:border-0">
                        <td className="py-2">
                          <input type="checkbox" checked={compareIds.includes(s.id)}
                                 aria-label={`Compare ${s.name}`}
                                 onChange={(e) => setCompareIds((ids) =>
                                   e.target.checked ? [...ids, s.id] : ids.filter((i) => i !== s.id))}
                                 className="size-3.5 accent-[var(--primary)]" />
                        </td>
                        <td className="py-2">
                          <p className="text-[13px]">{s.name}</p>
                          <p className="text-[10px] capitalize text-muted-foreground">
                            {s.kind.replace(/_/g, " ")}
                            {s.parent_scenario_id && " · branch"}
                          </p>
                        </td>
                        <td className="py-2 text-right tnum">{money(s.summary?.min_cash_p50)}</td>
                        <td className="py-2 text-right tnum">{money(s.summary?.min_cash_p10)}</td>
                        <td className="py-2 text-right tnum">{weeks(s.summary?.runway_weeks_p50)}</td>
                        <td className="py-2 text-right tnum">{pct(s.summary?.breach_probability)}</td>
                        <td className="py-2 text-right">
                          <button aria-label={`Archive ${s.name}`}
                                  onClick={async () => { await api.del(`/api/scenarios/${s.id}`); saved.reload(); }}
                                  className="rounded p-1 text-muted-foreground hover:bg-surface-hover hover:text-fin-loss">
                            <Trash2 className="size-3.5" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                Nothing saved yet. Run a scenario and press Save.
              </p>
            )}
          </Panel>

          {compareResult && <ComparisonPanel data={compareResult} />}
        </div>
      </div>
    </div>
  );
}

function ParamField({ param, value, onChange }:
  { param: Param; value: any; onChange: (v: any) => void }) {
  const id = `p-${param.key}`;
  if (param.kind === "money") {
    const rupees = Math.round((value ?? 0) / 100);
    return (
      <div>
        <label htmlFor={id} className="mb-1 flex items-baseline justify-between text-[11px]">
          <span className="font-medium text-muted-foreground">{param.label}</span>
          <span className="tnum text-foreground">{inr(value ?? 0)}</span>
        </label>
        <input id={id} type="number" min={0} step={1000} value={rupees}
               onChange={(e) => onChange(Math.round(Number(e.target.value || 0) * 100))}
               className="h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm tnum outline-none focus:border-primary/60" />
      </div>
    );
  }
  if (param.kind === "percent") {
    const p = Math.round((value ?? 0) * 1000) / 10;
    return (
      <div>
        <label htmlFor={id} className="mb-1 flex items-baseline justify-between text-[11px]">
          <span className="font-medium text-muted-foreground">{param.label}</span>
          <span className="tnum text-foreground">{p}%</span>
        </label>
        <input id={id} type="range" min={0} max={100} step={1} value={p}
               onChange={(e) => onChange(Number(e.target.value) / 100)}
               className="w-full accent-[var(--primary)]" />
      </div>
    );
  }
  if (param.kind === "days" || param.kind === "int") {
    return (
      <div>
        <label htmlFor={id} className="mb-1 flex items-baseline justify-between text-[11px]">
          <span className="font-medium text-muted-foreground">{param.label}</span>
          <span className="tnum text-foreground">
            {value}{param.kind === "days" ? " days" : ""}
          </span>
        </label>
        <input id={id} type="number" min={0} value={value ?? 0}
               onChange={(e) => onChange(Number(e.target.value || 0))}
               className="h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm tnum outline-none focus:border-primary/60" />
      </div>
    );
  }
  if (param.kind === "select") {
    return (
      <div>
        <label htmlFor={id} className="mb-1 block text-[11px] font-medium text-muted-foreground">
          {param.label}
        </label>
        <select id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value)}
                className="h-9 w-full rounded-lg border border-border bg-surface px-2.5 text-sm outline-none focus:border-primary/60">
          {(param.options ?? []).map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>
    );
  }
  if (param.kind === "bool") {
    return (
      <label className="flex items-center justify-between gap-3 text-[11px]">
        <span className="font-medium text-muted-foreground">{param.label}</span>
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)}
               className="size-4 accent-[var(--primary)]" />
      </label>
    );
  }
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-[11px] font-medium text-muted-foreground">
        {param.label}
      </label>
      <input id={id} value={value ?? ""} onChange={(e) => onChange(e.target.value)}
             className="h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary/60" />
    </div>
  );
}

function ScenarioResult({ result }: { result: any }) {
  const cmp = result.comparison;
  const base = result.baseline_series;
  const scen = result.scenario_series;
  const econ = result.economics ?? {};
  return (
    <>
      <Panel title="Baseline versus scenario"
             description={econ.narrative}
             actions={<span className={cn("rw-chip",
               cmp.verdict === "improves liquidity"
                 ? "border-fin-gain/30 bg-fin-gain-soft text-fin-gain"
                 : cmp.verdict === "worsens liquidity"
                 ? "border-fin-loss/30 bg-fin-loss-soft text-fin-loss"
                 : "border-border bg-surface text-muted-foreground")}>
               {cmp.verdict}
             </span>}
             bodyClass="p-2 pt-3">
        <CashBandChart series={base} scenario={{ p50: scen.p50, p10: scen.p10 }}
                       scenarioLabel="Scenario (P50)" height={300} />
      </Panel>

      <Panel title="What changes" description={cmp.method}>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="pb-2 font-medium">Metric</th>
                <th className="pb-2 text-right font-medium">Baseline</th>
                <th className="pb-2 text-right font-medium">Scenario</th>
                <th className="pb-2 text-right font-medium">Change</th>
              </tr>
            </thead>
            <tbody>
              {cmp.rows.map((r: any) => {
                const fmt = (v: number) =>
                  r.unit === "paise" ? inr(v)
                  : r.unit === "probability" ? pct(v)
                  : `${Number(v).toFixed(2)} wk`;
                return (
                  <tr key={r.metric} className="border-b border-border/50 last:border-0">
                    <td className="py-2 text-[13px]">{r.metric}</td>
                    <td className="py-2 text-right tnum text-muted-foreground">{fmt(r.baseline)}</td>
                    <td className="py-2 text-right font-medium tnum">{fmt(r.scenario)}</td>
                    <td className={cn("py-2 text-right text-[12px] tnum",
                      r.direction === "improved" ? "text-fin-gain"
                        : r.direction === "worse" ? "text-fin-loss" : "text-muted-foreground")}>
                      {r.direction === "improved" ? "▲" : r.direction === "worse" ? "▼" : "→"}{" "}
                      {fmt(Math.abs(r.delta))}
                      <span className="sr-only"> {r.direction}</span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {Object.keys(econ).length > 0 && (
          <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {[
              ["expected_revenue_paise", "Expected revenue"],
              ["expected_profit_paise", "Expected profit"],
              ["cash_out_before_cash_in_paise", "Cash out before cash in"],
              ["financing_cost_paise", "Financing cost"],
              ["total_cost_paise", "Total cost of credit"],
              ["net_advance_paise", "Net advance"],
              ["emi_paise", "Monthly EMI"],
              ["total_cost_paise", "Total cost"],
            ].filter(([k]) => econ[k] !== undefined).slice(0, 4).map(([k, label]) => (
              <Stat key={k} label={label as string} value={inr(econ[k as string])} state="simulated" />
            ))}
          </div>
        )}

        {econ.funding_gap_days ? (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-fin-warn/30 bg-fin-warn-soft p-3">
            <TriangleAlert className="mt-0.5 size-4 shrink-0 text-fin-warn" aria-hidden />
            <p className="text-xs leading-relaxed text-pretty">
              You fund this for <strong>{econ.funding_gap_days} days</strong> before the
              money comes back. That gap, not the margin, is what decides whether the
              business can take this on.
            </p>
          </div>
        ) : null}

        {econ.disclaimer && <Provenance>{econ.disclaimer}</Provenance>}
        <Provenance>{result.isolation_guarantee ?? "Nothing was written to your ledger."}</Provenance>
      </Panel>
    </>
  );
}

/** Second-quarter cross-check.
 *
 *  A 13-week window sees the purchases a revenue change causes before the
 *  collections they fund. Rather than disclose that bias in a footnote,
 *  the engine runs the same comparison over 26 weeks and this panel shows
 *  both — so a scenario that looks mild over one quarter cannot be read as
 *  mild when it is not. */
function LongHorizon({ lh }: { lh: any }) {
  const d13 = lh.closing_delta_at_13w_paise;
  const d26 = lh.closing_delta_at_26w_paise;
  const grows = lh.effect_grows_beyond_13_weeks;
  const series = {
    week_starts: lh.week_starts,
    p10: lh.baseline_p50, p50: lh.baseline_p50, p90: lh.baseline_p50,
    safety_buffer_paise: 0,
  };
  return (
    <Panel
      title="Second-quarter cross-check"
      description={`The same comparison re-run over ${lh.horizon_weeks} weeks, because a 13-week window sees the cash cost of a revenue change before the collections it funds.`}
      actions={grows ? (
        <span className="rw-chip border-fin-warn/30 bg-fin-warn-soft text-fin-warn">
          <TriangleAlert className="size-3" /> impact grows after week 13
        </span>
      ) : (
        <span className="rw-chip border-border bg-surface text-muted-foreground">
          13 weeks already captures it
        </span>
      )}
      bodyClass="p-2 pt-3">
      <CashBandChart series={series} scenario={{ p50: lh.scenario_p50 }}
                     scenarioLabel="Scenario (26-week)" height={240} showBuffer={false} />
      <div className="grid gap-3 p-2 sm:grid-cols-4">
        <Stat label="Closing cash change at 13 weeks" value={inr(d13)}
              tone={d13 < 0 ? "loss" : "gain"} state="simulated" />
        <Stat label="Closing cash change at 26 weeks" value={inr(d26)}
              tone={d26 < 0 ? "loss" : "gain"} state="simulated" />
        <Stat label="Minimum cash P10 change" value={inr(lh.min_cash_p10_delta_paise)}
              tone={lh.min_cash_p10_delta_paise < 0 ? "loss" : "gain"} state="simulated" />
        <Stat label="Breach probability change"
              value={`${lh.breach_delta >= 0 ? "+" : ""}${(lh.breach_delta * 100).toFixed(1)} pp`}
              tone={lh.breach_delta > 0 ? "loss" : "gain"} state="simulated" />
      </div>
      <div className="px-2 pb-1">
        <Provenance>{lh.interpretation}</Provenance>
      </div>
    </Panel>
  );
}

function ComparisonPanel({ data }: { data: any }) {
  const rows = [
    { key: "min_cash_p10", label: "Minimum cash P10", better: "higher" as const },
    { key: "min_cash_p50", label: "Minimum cash P50", better: "higher" as const },
    { key: "closing_cash_p50", label: "Closing cash P50", better: "higher" as const },
    { key: "peak_working_capital", label: "Peak working capital", better: "lower" as const },
    { key: "expected_profit", label: "Expected profit", better: "higher" as const },
    { key: "financing_cost", label: "Financing cost", better: "lower" as const },
  ];
  return (
    <Panel title="Scenario comparison"
           description={data.warning ?? "All scenarios run against the same baseline."}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="pb-2 font-medium">Metric</th>
              <th className="pb-2 text-right font-medium">Baseline</th>
              {data.scenarios.map((s: any) => (
                <th key={s.scenario_id} className="pb-2 text-right font-medium">{s.name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="border-b border-border/50 last:border-0">
                <td className="py-2 text-[13px]">{r.label}</td>
                <td className="py-2 text-right tnum text-muted-foreground">
                  {money((data.baseline as any)?.[r.key]) }
                </td>
                {data.scenarios.map((s: any) => (
                  <td key={s.scenario_id} className="py-2 text-right tnum">{money(s[r.key])}</td>
                ))}
              </tr>
            ))}
            <tr>
              <td className="py-2 text-[13px]">Runway P50</td>
              <td className="py-2 text-right tnum text-muted-foreground">
                {weeks(data.baseline?.runway_weeks_p50)}
              </td>
              {data.scenarios.map((s: any) => (
                <td key={s.scenario_id} className="py-2 text-right tnum">
                  {weeks(s.runway_weeks_p50)}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-2 text-[13px]">Chance of breach</td>
              <td className="py-2 text-right tnum text-muted-foreground">
                {pct(data.baseline?.breach_probability)}
              </td>
              {data.scenarios.map((s: any) => (
                <td key={s.scenario_id} className="py-2 text-right tnum">
                  {pct(s.breach_probability)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      {data.best_by_min_cash && (
        <p className="mt-3 flex items-center gap-2 text-xs">
          <Check className="size-3.5 text-fin-gain" aria-hidden />
          <span>
            On worst-case cash, <strong>{data.best_by_min_cash}</strong> holds up best.
            That is one criterion among several — profit, relationship and strategy are
            not in this table.
          </span>
        </p>
      )}
    </Panel>
  );
}
