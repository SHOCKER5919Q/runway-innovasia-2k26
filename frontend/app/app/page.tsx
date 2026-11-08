"use client";

import Link from "next/link";
import { useMemo } from "react";
import {
  AlertTriangle, ArrowRight, CalendarClock, CircleDollarSign, Gauge,
  Landmark, Lightbulb, Receipt, Sparkles, TrendingUp, Wallet,
} from "lucide-react";
import {
  AgeingBars, BreachBars, CashBandChart, FlowBars, HealthGauge,
} from "@/components/runway/charts";
import {
  Delta, Evidence, LevelPill, LoadingPanel, Panel, Provenance, SectionHeader,
  Stat, StateBadge, ErrorState,
} from "@/components/runway/primitives";
import { Reveal } from "@/components/runway/motion";
import { useApi } from "@/lib/use-api";
import { inr, longDate, money, pct, relDays, shortDate, weeks } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function HomePage() {
  const ov = useApi<any>("/api/overview");
  const br = useApi<any>("/api/briefing");

  if (ov.error) return <ErrorState message={ov.error} onRetry={ov.reload} />;
  if (ov.loading || !ov.data) return <HomeSkeleton />;

  const d = ov.data;
  const h = d.headline;
  const f = d.forecast;

  return (
    <div className="space-y-6">
      {/* ── briefing ── */}
      <Reveal>
        <section className="rw-card relative overflow-hidden">
          <div className="pointer-events-none absolute inset-0 rw-aurora opacity-60" aria-hidden />
          <div className="relative p-5 sm:p-6">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <h1 className="font-display text-2xl font-semibold tracking-tight text-balance">
                  {br.data?.greeting ?? "Your financial briefing"}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {br.data?.subtitle ?? `Here is ${d.business.name} at a glance.`}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="rw-chip border-border bg-surface text-muted-foreground">
                  <CalendarClock className="size-3" /> {longDate(d.as_of)}
                </span>
                <HealthChip score={h.health_score} band={h.health_band} />
              </div>
            </div>

            {br.data?.lines && (
              <ul className="mt-5 grid gap-2.5 lg:grid-cols-2">
                {br.data.lines.map((l: any, i: number) => (
                  <li key={i}
                      className="flex items-start gap-3 rounded-lg border border-border bg-background/40 p-3">
                    <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-md border border-border bg-surface">
                      <BriefIcon kind={l.kind} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[13px] leading-relaxed text-pretty">{l.text}</p>
                      <div className="mt-1.5"><StateBadge state={l.state} /></div>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            {br.data?.recommended_action && (
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/30 bg-primary-soft p-3.5">
                <div className="min-w-0">
                  <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
                    <Lightbulb className="size-3.5" /> Do this first
                  </p>
                  <p className="mt-1 text-sm font-medium">{br.data.recommended_action.title}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground text-pretty">
                    {br.data.recommended_action.action}
                  </p>
                </div>
                <Link href="/app/recommendations"
                      className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-xs font-medium text-primary-foreground hover:opacity-92">
                  View all <ArrowRight className="size-3.5" />
                </Link>
              </div>
            )}

            {br.data?.provenance && <Provenance>{br.data.provenance}</Provenance>}
          </div>
        </section>
      </Reveal>

      {/* ── headline tiles ── */}
      <Reveal delay={0.05}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Stat
            label="Available cash" value={money(h.available_cash)} state="actual"
            icon={<Wallet className="size-4" />}
            hint="Bank and cash balances less lien-marked and already-committed money"
            sub={<>of {money(h.cash_in_hand)} in hand</>}
            footer={<span className="text-[11px] text-muted-foreground">
              {money(h.restricted, true)} restricted · {money(h.committed, true)} committed
            </span>} />
          <Stat
            label="Receivables" value={money(h.receivables)} state="actual"
            icon={<CircleDollarSign className="size-4" />}
            tone={h.receivables_overdue?.paise > 0 ? "warn" : "neutral"}
            sub={<>{money(h.receivables_overdue)} overdue</>}
            footer={<Link href="/app/receivables" className="text-[11px] text-primary hover:underline">
              Collection list →
            </Link>} />
          <Stat
            label="Payables" value={money(h.payables)} state="actual"
            icon={<Receipt className="size-4" />}
            sub={<>{money(h.payables_overdue)} past due</>}
            footer={<Link href="/app/payables" className="text-[11px] text-primary hover:underline">
              Payment calendar →
            </Link>} />
          <Stat
            label="Cash runway" state="predicted"
            icon={<TrendingUp className="size-4" />}
            tone={h.runway_weeks_p10 < 4 ? "loss" : h.runway_weeks_p10 < 8 ? "warn" : "gain"}
            value={h.runway_censored ? `${f?.p50?.length ? f.p50.length - 1 : 13}+ wk` : weeks(h.runway_weeks_p50)}
            sub={<>P10 downside {weeks(h.runway_weeks_p10)}</>}
            footer={<span className="text-[11px] text-muted-foreground">
              {pct(h.breach_probability)} chance of breaching the buffer
            </span>} />
        </div>
      </Reveal>

      {/* ── forecast + health ── */}
      <div className="grid gap-4 xl:grid-cols-[1.75fr_1fr]">
        <Reveal delay={0.1}>
          <Panel
            title="Cash flow outlook"
            description={f ? `${f.paths.toLocaleString("en-IN")} simulated paths, seed ${f.seed}. The band is the P10–P90 range.` : undefined}
            actions={<Link href="/app/forecasts"
                           className="rounded-md border border-border px-2.5 py-1 text-xs hover:bg-surface-hover">
              Open forecast
            </Link>}
            bodyClass="p-2 pt-3">
            {f ? (
              <>
                <CashBandChart series={f} height={300} />
                {f.breach_prob_by_week?.some((p: number) => p > 0.05) && (
                  <div className="px-2 pb-1 pt-2">
                    <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                      Chance of breaching the safety buffer, by week
                    </p>
                    <BreachBars weeks={f.week_starts} probs={f.breach_prob_by_week} height={120} />
                  </div>
                )}
              </>
            ) : <LoadingPanel rows={4} />}
          </Panel>
        </Reveal>

        <Reveal delay={0.15}>
          <div className="flex h-full flex-col gap-4">
            <Panel title="Business health" bodyClass="p-4">
              <div className="flex items-center gap-4">
                <HealthGauge score={d.health.score} size={132} />
                <div className="min-w-0 flex-1">
                  <p className="font-display text-lg font-semibold">{d.health.band}</p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Weighted over eight dimensions
                  </p>
                  <ul className="mt-3 space-y-1.5">
                    {[...d.health.subscores]
                      .sort((a: any, b: any) => a.score - b.score).slice(0, 3)
                      .map((s: any) => (
                        <li key={s.key} className="flex items-center gap-2 text-[11px]">
                          <span className="min-w-0 flex-1 truncate text-muted-foreground">{s.label}</span>
                          <span className="h-1 w-14 shrink-0 overflow-hidden rounded-full bg-surface">
                            <span className="block h-full rounded-full"
                                  style={{ width: `${s.score}%`,
                                           background: s.score >= 65 ? "var(--fin-gain)"
                                                     : s.score >= 45 ? "var(--fin-warn)" : "var(--fin-loss)" }} />
                          </span>
                          <span className="w-7 shrink-0 text-right tnum">{s.score.toFixed(0)}</span>
                        </li>
                      ))}
                  </ul>
                  <Link href="/app/health"
                        className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline">
                    All dimensions <ArrowRight className="size-3" />
                  </Link>
                </div>
              </div>
            </Panel>

            {d.top_alert && (
              <Panel title="Top risk" bodyClass="p-4" className="flex-1">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="mt-0.5 size-4 shrink-0 text-fin-warn" aria-hidden />
                  <div className="min-w-0">
                    <div className="mb-1.5"><LevelPill level={d.top_alert.level} /></div>
                    <p className="text-sm font-medium text-pretty">{d.top_alert.title}</p>
                    <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground text-pretty">
                      {d.top_alert.what_happened}
                    </p>
                    <p className="mt-2 text-xs leading-relaxed text-pretty">
                      <span className="font-medium">Do: </span>
                      <span className="text-muted-foreground">{d.top_alert.recommended_action}</span>
                    </p>
                    <Link href="/app/risk"
                          className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline">
                      Risk centre <ArrowRight className="size-3" />
                    </Link>
                  </div>
                </div>
              </Panel>
            )}
          </div>
        </Reveal>
      </div>

      {/* ── ageing + obligations + flows ── */}
      <div className="grid gap-4 lg:grid-cols-3">
        <Reveal delay={0.2}>
          <Panel title="Receivables ageing"
                 description={`${pct(d.ageing.overdue_share)} of the book is past due`}
                 bodyClass="p-2 pt-3">
            <AgeingBars buckets={d.ageing.buckets} height={190} />
            <ul className="mt-2 space-y-1 px-2 pb-1 text-[11px]">
              {d.ageing.buckets.map((b: any) => (
                <li key={b.label} className="flex items-center justify-between">
                  <span className="text-muted-foreground">{b.label} · {b.count}</span>
                  <span className="tnum">{inr(b.amount_paise)}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </Reveal>

        <Reveal delay={0.25}>
          <Panel title="Due in the next 30 days"
                 description="Statutory and contractual commitments"
                 actions={<Link href="/app/compliance"
                                className="text-xs text-primary hover:underline">Calendar</Link>}>
            {d.obligations_next_30d?.length ? (
              <ul className="space-y-2">
                {d.obligations_next_30d.slice(0, 7).map((o: any) => (
                  <li key={o.id} className="flex items-start justify-between gap-3 border-b border-border/60 pb-2 last:border-0">
                    <div className="min-w-0">
                      <p className="truncate text-[13px]">{o.label}</p>
                      <p className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                        {relDays(o.due_date, d.as_of)}
                        {o.is_estimated && (
                          <span className="rw-chip border-fin-warn/30 bg-fin-warn-soft px-1.5 py-0 text-fin-warn">
                            estimate
                          </span>
                        )}
                        {o.statutory && (
                          <span className="rw-chip border-border bg-surface px-1.5 py-0">statutory</span>
                        )}
                      </p>
                    </div>
                    <span className="shrink-0 text-[13px] tnum">{inr(o.amount_paise)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="py-8 text-center text-sm text-muted-foreground">
                Nothing falls due in the next 30 days.
              </p>
            )}
          </Panel>
        </Reveal>

        <Reveal delay={0.3}>
          <Panel title="Expected cash movement"
                 description="Week by week, from the simulation" bodyClass="p-2 pt-3">
            {f ? <FlowBars weeks={f.week_starts} inflow={f.inflow_p50}
                           outflow={f.outflow_p50} height={240} /> : null}
          </Panel>
        </Reveal>
      </div>

      {/* ── recommendations ── */}
      <Reveal delay={0.35}>
        <SectionHeader
          title="What to do today"
          description="Ranked by urgency, cash impact, evidence, ease and reversibility. Nothing happens without your approval."
          actions={<Link href="/app/recommendations"
                         className="rounded-md border border-border px-2.5 py-1 text-xs hover:bg-surface-hover">
            All recommendations
          </Link>} />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {d.recommendations.map((r: any) => (
            <article key={r.code} className="rw-card flex flex-col p-4">
              <div className="flex items-start justify-between gap-2">
                <span className="rw-chip border-primary/30 bg-primary-soft text-primary">
                  P{r.priority}
                </span>
                {r.deadline && (
                  <span className="text-[10px] text-muted-foreground">
                    by {shortDate(r.deadline)}
                  </span>
                )}
              </div>
              <h3 className="mt-2.5 text-[13px] font-medium leading-snug text-pretty">{r.title}</h3>
              <p className="mt-1.5 flex-1 text-[11px] leading-relaxed text-muted-foreground text-pretty">
                {r.expected_effect_text}
              </p>
              <div className="mt-3 flex items-center justify-between border-t border-border pt-2.5">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  confidence {pct(r.confidence)}
                </span>
                <Link href="/app/recommendations"
                      className="text-[11px] text-primary hover:underline">Evidence →</Link>
              </div>
            </article>
          ))}
        </div>
      </Reveal>

      {/* ── data quality footer ── */}
      <Reveal delay={0.4}>
        <div className="rw-surface flex flex-wrap items-center justify-between gap-3 p-3.5">
          <div className="flex items-center gap-3">
            <Gauge className="size-4 text-muted-foreground" aria-hidden />
            <div>
              <p className="text-xs font-medium">
                Data quality {d.data_quality.score}/100 · {d.data_quality.band}
              </p>
              <p className="text-[11px] text-muted-foreground">
                {d.data_quality.warnings?.length
                  ? d.data_quality.warnings[0]
                  : "No data-quality warnings."}
              </p>
            </div>
          </div>
          <p className="text-[11px] text-muted-foreground">
            Actual v{d.state_refs.actual_version} · Predicted v{d.state_refs.predicted_version} ·
            engine {d.state_refs.engine_version} · computed in {d.state_refs.built_ms} ms
          </p>
        </div>
      </Reveal>
    </div>
  );
}

function HealthChip({ score, band }: { score: number; band: string }) {
  const tone = score >= 80 ? "text-fin-gain bg-fin-gain-soft border-fin-gain/30"
    : score >= 65 ? "text-fin-gain bg-fin-gain-soft border-fin-gain/25"
    : score >= 50 ? "text-fin-warn bg-fin-warn-soft border-fin-warn/30"
    : "text-fin-loss bg-fin-loss-soft border-fin-loss/30";
  return (
    <span className={cn("rw-chip", tone)}>
      <Gauge className="size-3" aria-hidden /> Health {score.toFixed(0)} · {band}
    </span>
  );
}

function BriefIcon({ kind }: { kind: string }) {
  const cls = "size-3.5 text-muted-foreground";
  if (kind === "cash") return <Wallet className={cls} />;
  if (kind === "forecast") return <TrendingUp className={cls} />;
  if (kind === "receivable") return <CircleDollarSign className={cls} />;
  if (kind === "obligation") return <CalendarClock className={cls} />;
  if (kind === "risk") return <AlertTriangle className="size-3.5 text-fin-warn" />;
  return <Sparkles className={cls} />;
}

function HomeSkeleton() {
  return (
    <div className="space-y-6">
      <LoadingPanel rows={4} title="briefing" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <LoadingPanel key={i} rows={1} />)}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.75fr_1fr]">
        <LoadingPanel rows={6} /><LoadingPanel rows={4} />
      </div>
    </div>
  );
}
