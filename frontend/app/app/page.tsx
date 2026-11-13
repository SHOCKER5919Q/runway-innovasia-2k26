"use client";

import Link from "next/link";
import { useState } from "react";
import {
  AlertTriangle, ArrowRight, CalendarClock, CircleDollarSign, Gauge,
  Lightbulb, MessageSquare, Receipt, Sparkles, TrendingUp, Wallet,
} from "lucide-react";
import {
  AgeingBars, BreachBars, CashBandChart, FlowBars, HealthGauge,
} from "@/components/runway/charts";
import {
  LevelPill, LoadingPanel, Panel, Stat, StateBadge, ErrorState,
} from "@/components/runway/primitives";
import {
  Button, CopyButton, Details, ExportButton, Grid, Note, PageHeader,
  Rows, Tabs, useTabs,
} from "@/components/runway/page-kit";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { inr, longDate, money, pct, relDays, shortDate, weeks } from "@/lib/format";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "today", label: "Today" },
  { key: "cash", label: "Cash" },
  { key: "books", label: "Receivables & payables" },
  { key: "actions", label: "Actions" },
];

export default function HomePage() {
  const ov = useApi<any>("/api/overview");
  const br = useApi<any>("/api/briefing");
  const [tab, setTab] = useTabs("home", "today");

  if (ov.error) return <ErrorState message={ov.error} onRetry={ov.reload} />;
  if (ov.loading || !ov.data) return <HomeSkeleton />;

  const d = ov.data;
  const h = d.headline;
  const f = d.forecast;

  return (
    <div>
      <PageHeader
        title={br.data?.greeting ?? "Your briefing"}
        subtitle={br.data?.subtitle ?? `${d.business.name} at a glance.`}
        crumb={<span className="flex items-center gap-1"><CalendarClock className="size-3" />{longDate(d.as_of)}</span>}
        state={<>
          <span className={cn("rw-chip", healthTone(h.health_score))}>
            <Gauge className="size-3" /> Health {h.health_score.toFixed(0)} · {h.health_band}
          </span>
          <StateBadge state="actual" />
        </>}
        actions={<BriefingActions />}
      />

      <Tabs tabs={TABS} active={tab} onChange={setTab} />

      {tab === "today" && <TodayTab d={d} br={br.data} />}
      {tab === "cash" && <CashTab d={d} f={f} />}
      {tab === "books" && <BooksTab d={d} f={f} />}
      {tab === "actions" && <ActionsTab d={d} />}

      <footer className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3 text-[11px] text-muted-foreground">
        <span>
          Data quality {d.data_quality.score}/100 · {d.data_quality.band}
          {d.data_quality.warnings?.length ? ` — ${d.data_quality.warnings[0]}` : ""}
        </span>
        <span className="tnum">
          Actual v{d.state_refs.actual_version} · Predicted v{d.state_refs.predicted_version}
          {" · "}engine {d.state_refs.engine_version} · {d.state_refs.built_ms} ms
        </span>
      </footer>
    </div>
  );
}

/* ── briefing actions ─────────────────────────────────────────── */

function BriefingActions() {
  const [text, setText] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function load() {
    if (text) { setOpen(true); return; }
    setBusy(true);
    try {
      const r = await api.get<{ text: string }>("/api/briefing/whatsapp");
      setText(r.text);
      setOpen(true);
    } finally { setBusy(false); }
  }

  return (
    <>
      <Button icon={<MessageSquare className="size-3.5" />} onClick={load} busy={busy}>
        Share briefing
      </Button>
      {open && text && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm"
               onClick={() => setOpen(false)} aria-hidden />
          <div className="relative w-full max-w-md rounded-2xl border border-border bg-card p-5 shadow-2xl">
            <h3 className="font-display text-[15px] font-semibold">WhatsApp briefing</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Copy it, or open it in WhatsApp to send to yourself or a partner.
            </p>
            <pre className="mt-3 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-border bg-surface p-3 text-[12px] leading-relaxed">
              {text}
            </pre>
            <div className="mt-3 flex items-center justify-end gap-2">
              <Button onClick={() => setOpen(false)} tone="ghost">Close</Button>
              <a href={`https://wa.me/?text=${encodeURIComponent(text)}`}
                 target="_blank" rel="noreferrer">
                <Button tone="primary">Open in WhatsApp</Button>
              </a>
              <CopyButton text={text} />
            </div>
          </div>
        </div>
      )}
    </>
  );
}

/* ── today ────────────────────────────────────────────────────── */

function TodayTab({ d, br }: { d: any; br: any }) {
  const h = d.headline;
  return (
    <div className="space-y-4">
      <Grid cols={4}>
        <Stat label="Available cash" value={money(h.available_cash)} state="actual"
              icon={<Wallet className="size-4" />}
              hint="Bank and cash balances less lien-marked and already-committed money"
              sub={<>of {money(h.cash_in_hand)} in hand</>}
              footer={<span className="text-[11px] text-muted-foreground">
                {money(h.restricted, true)} restricted · {money(h.committed, true)} committed
              </span>} />
        <Stat label="Receivables" value={money(h.receivables)} state="actual"
              icon={<CircleDollarSign className="size-4" />}
              tone={h.receivables_overdue?.paise > 0 ? "warn" : "neutral"}
              sub={<>{money(h.receivables_overdue)} overdue</>}
              footer={<Link href="/app/receivables" className="text-[11px] text-primary hover:underline">Collect →</Link>} />
        <Stat label="Payables" value={money(h.payables)} state="actual"
              icon={<Receipt className="size-4" />}
              sub={<>{money(h.payables_overdue)} past due</>}
              footer={<Link href="/app/payables" className="text-[11px] text-primary hover:underline">Schedule →</Link>} />
        <Stat label="Cash runway" state="predicted"
              icon={<TrendingUp className="size-4" />}
              tone={h.runway_weeks_p10 < 4 ? "loss" : h.runway_weeks_p10 < 8 ? "warn" : "gain"}
              value={h.runway_censored ? "13+ wk" : weeks(h.runway_weeks_p50)}
              sub={<>P10 downside {weeks(h.runway_weeks_p10)}</>}
              footer={<span className="text-[11px] text-muted-foreground">
                {pct(h.breach_probability)} breach risk
              </span>} />
      </Grid>

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Panel title="Where you stand">
          {br?.lines ? (
            <ul className="space-y-2.5">
              {br.lines.map((l: any, i: number) => (
                <li key={i} className="flex items-start gap-3">
                  <BriefIcon kind={l.kind} />
                  <div className="min-w-0 flex-1">
                    <p className="text-[13px] leading-relaxed text-pretty">{l.text}</p>
                    <div className="mt-1"><StateBadge state={l.state} /></div>
                  </div>
                </li>
              ))}
            </ul>
          ) : <LoadingPanel rows={3} />}
        </Panel>

        <div className="space-y-4">
          {br?.recommended_action && (
            <div className="rounded-lg border border-primary/30 bg-primary-soft p-4">
              <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-primary">
                <Lightbulb className="size-3.5" /> Do this first
              </p>
              <p className="mt-1.5 text-sm font-medium">{br.recommended_action.title}</p>
              <p className="mt-1 text-xs text-muted-foreground text-pretty">
                {br.recommended_action.action}
              </p>
              <Link href="/app/recommendations"
                    className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline">
                See the ranked list <ArrowRight className="size-3" />
              </Link>
            </div>
          )}

          {d.top_alert && (
            <Panel title="Top risk" bodyClass="p-4">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-fin-warn" aria-hidden />
                <div className="min-w-0">
                  <LevelPill level={d.top_alert.level} />
                  <p className="mt-2 text-[13px] font-medium text-pretty">{d.top_alert.title}</p>
                  <p className="mt-1 text-xs leading-relaxed text-muted-foreground text-pretty">
                    {d.top_alert.what_happened}
                  </p>
                  <p className="mt-2 text-xs text-pretty">
                    <span className="font-medium">Do: </span>
                    <span className="text-muted-foreground">{d.top_alert.recommended_action}</span>
                  </p>
                  <Link href="/app/risk"
                        className="mt-2.5 inline-flex items-center gap-1 text-xs text-primary hover:underline">
                    Risk centre <ArrowRight className="size-3" />
                  </Link>
                </div>
              </div>
            </Panel>
          )}

          <Details label="What is a fact and what is a prediction">
            Lines marked <StateBadge state="actual" /> come from your reconciled ledger.
            Lines marked <StateBadge state="predicted" /> are model estimates with a stated
            uncertainty band — they are what the engine expects, not what has happened.
            Runway, breach probability and health are all predicted.
          </Details>
        </div>
      </div>
    </div>
  );
}

/* ── cash ─────────────────────────────────────────────────────── */

function CashTab({ d, f }: { d: any; f: any }) {
  const h = d.headline;
  return (
    <div className="space-y-4">
      <Panel
        title="13-week cash outlook"
        description={f ? `${f.paths.toLocaleString("en-IN")} simulated paths · seed ${f.seed}` : undefined}
        actions={<Link href="/app/forecasts" className="text-xs text-primary hover:underline">
          Full forecast <ArrowRight className="inline size-3" /></Link>}
        bodyClass="p-2 pt-3">
        {f ? (
          <>
            <CashBandChart series={f} height={300} />
            {f.breach_prob_by_week?.some((p: number) => p > 0.05) && (
              <div className="px-2 pb-1 pt-2">
                <p className="mb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                  Chance of breaching the safety buffer, by week
                </p>
                <BreachBars weeks={f.week_starts} probs={f.breach_prob_by_week} height={110} />
              </div>
            )}
          </>
        ) : <LoadingPanel rows={4} />}
      </Panel>

      <div className="grid gap-4 lg:grid-cols-[1fr_1fr_1fr]">
        <Panel title="Expected movement" description="Week by week, from the simulation"
               bodyClass="p-2 pt-3">
          {f ? <FlowBars weeks={f.week_starts} inflow={f.inflow_p50}
                         outflow={f.outflow_p50} height={220} /> : null}
        </Panel>

        <Panel title="Business health" bodyClass="p-4">
          <div className="flex items-center gap-4">
            <HealthGauge score={d.health.score} size={120} />
            <div className="min-w-0 flex-1">
              <p className="font-display text-lg font-semibold">{d.health.band}</p>
              <ul className="mt-2.5 space-y-1.5">
                {[...d.health.subscores].sort((a: any, b: any) => a.score - b.score)
                  .slice(0, 4).map((s: any) => (
                  <li key={s.key} className="flex items-center gap-2 text-[11px]">
                    <span className="min-w-0 flex-1 truncate text-muted-foreground">{s.label}</span>
                    <span className="h-1 w-12 shrink-0 overflow-hidden rounded-full bg-surface">
                      <span className="block h-full rounded-full"
                            style={{ width: `${s.score}%`,
                                     background: s.score >= 65 ? "var(--fin-gain)"
                                       : s.score >= 45 ? "var(--fin-warn)" : "var(--fin-loss)" }} />
                    </span>
                    <span className="w-6 shrink-0 text-right tnum">{s.score.toFixed(0)}</span>
                  </li>
                ))}
              </ul>
              <Link href="/app/health" className="mt-2.5 inline-flex items-center gap-1 text-xs text-primary hover:underline">
                All dimensions <ArrowRight className="size-3" />
              </Link>
            </div>
          </div>
        </Panel>

        <Panel title="The numbers behind it" bodyClass="p-3">
          <Rows items={[
            { k: "Opening cash", v: money(f?.opening_cash_paise ?? 0, true) },
            { k: "Safety buffer", v: money(f?.safety_buffer_paise ?? 0, true) },
            { k: "Minimum cash (P50)", v: money(f?.min_cash_p50_paise ?? 0, true) },
            { k: "Minimum cash (P10)", v: money(f?.min_cash_p10_paise ?? 0, true) },
            { k: "Breach probability", v: pct(f?.breach_probability) },
            { k: "Runway P10 / P50 / P90",
              v: `${weeks(f?.runway_weeks_p10)} / ${weeks(f?.runway_weeks_p50)} / ${weeks(f?.runway_weeks_p90)}` },
            { k: "Paths", v: f?.paths?.toLocaleString("en-IN") ?? "—" },
          ]} />
          <div className="mt-3">
            <Details label="How the band is produced" dense>
              Each week&rsquo;s cash movement is assembled from your open invoices,
              obligations and estimated run-rate sales, then simulated 4,000 times.
              P10 is a pessimistic path and P90 an optimistic one. They are
              simulation quantiles, not guarantees.
              {f?.assumptions?.revenue_delay_coupling > 0 && (
                <> Weak demand and slow payment are drawn from one shared market
                   factor (coupling {f.assumptions.revenue_delay_coupling.toFixed(2)}),
                   so a downturn path is lighter on sales <em>and</em> slower on
                   collections.</>
              )}
            </Details>
          </div>
        </Panel>
      </div>
    </div>
  );
}

/* ── books ────────────────────────────────────────────────────── */

function BooksTab({ d, f }: { d: any; f: any }) {
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Panel title="Receivables ageing"
             description={`${pct(d.ageing.overdue_share)} of the book is past due`}
             actions={<ExportButton path="/api/exports/receivables.csv"
                                    filename="runway-receivables.csv" size="sm"
                                    label="CSV" />}
             bodyClass="p-2 pt-3">
        <AgeingBars buckets={d.ageing.buckets} height={180} />
        <ul className="mt-2 space-y-1 px-2 pb-1 text-[11px]">
          {d.ageing.buckets.map((b: any) => (
            <li key={b.label} className="flex items-center justify-between">
              <span className="text-muted-foreground">{b.label} · {b.count}</span>
              <span className="tnum">{inr(b.amount_paise)}</span>
            </li>
          ))}
        </ul>
      </Panel>

      <Panel title="Due in 30 days"
             actions={<Link href="/app/compliance" className="text-xs text-primary hover:underline">Calendar</Link>}>
        {d.obligations_next_30d?.length ? (
          <ul className="space-y-2">
            {d.obligations_next_30d.slice(0, 7).map((o: any) => (
              <li key={o.id} className="flex items-start justify-between gap-3 border-b border-border/60 pb-2 last:border-0">
                <div className="min-w-0">
                  <p className="truncate text-[13px]">{o.label}</p>
                  <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                    {relDays(o.due_date, d.as_of)}
                    {o.is_estimated && (
                      <span className="rw-chip border-fin-warn/30 bg-fin-warn-soft px-1.5 py-0 text-fin-warn">estimate</span>
                    )}
                    {o.statutory && <span className="rw-chip border-border bg-surface px-1.5 py-0">statutory</span>}
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

      <Panel title="Payables calendar"
             actions={<ExportButton path="/api/exports/payables.csv"
                                    filename="runway-payables.csv" size="sm" label="CSV" />}>
        <ul className="space-y-2">
          {(d.payables_calendar ?? []).slice(0, 6).map((w: any, i: number) => (
            <li key={i} className="flex items-center justify-between gap-3 border-b border-border/60 pb-2 last:border-0">
              <div className="min-w-0">
                <p className="text-[13px]">{shortDate(w.week_start)}</p>
                <p className="text-[11px] text-muted-foreground">
                  {w.count} bill{w.count === 1 ? "" : "s"}
                  {w.msmed_amount_paise > 0 && ` · ${money({ paise: w.msmed_amount_paise } as any, true)} MSMED`}
                </p>
              </div>
              <span className="shrink-0 text-[13px] tnum">{inr(w.amount_paise)}</span>
            </li>
          ))}
          {!d.payables_calendar?.length && (
            <p className="py-8 text-center text-sm text-muted-foreground">No bills scheduled.</p>
          )}
        </ul>
        <Link href="/app/payables" className="mt-3 inline-flex items-center gap-1 text-xs text-primary hover:underline">
          Full schedule <ArrowRight className="size-3" />
        </Link>
      </Panel>
    </div>
  );
}

/* ── actions ──────────────────────────────────────────────────── */

function ActionsTab({ d }: { d: any }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {d.recommendations.map((r: any) => (
          <article key={r.code} className="rw-card flex flex-col p-4">
            <div className="flex items-start justify-between gap-2">
              <span className="rw-chip border-primary/30 bg-primary-soft text-primary">P{r.priority}</span>
              {r.deadline && <span className="text-[10px] text-muted-foreground">by {shortDate(r.deadline)}</span>}
            </div>
            <h3 className="mt-2.5 text-[13px] font-medium leading-snug text-pretty">{r.title}</h3>
            <p className="mt-1.5 flex-1 text-[11px] leading-relaxed text-muted-foreground text-pretty">
              {r.expected_effect_text}
            </p>
            <div className="mt-3 flex items-center justify-between border-t border-border pt-2.5">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                confidence {pct(r.confidence)}
              </span>
              <Link href="/app/recommendations" className="text-[11px] text-primary hover:underline">
                Evidence →
              </Link>
            </div>
          </article>
        ))}
      </div>
      <Note>
        Ranked by urgency, cash impact, evidence, ease and reversibility. None of
        them execute themselves — RUNWAY never moves money or changes a contract.
      </Note>
    </div>
  );
}

/* ── bits ─────────────────────────────────────────────────────── */

function healthTone(score: number) {
  return score >= 65 ? "text-fin-gain bg-fin-gain-soft border-fin-gain/30"
    : score >= 50 ? "text-fin-warn bg-fin-warn-soft border-fin-warn/30"
    : "text-fin-loss bg-fin-loss-soft border-fin-loss/30";
}

function BriefIcon({ kind }: { kind: string }) {
  const cls = "mt-0.5 size-3.5 shrink-0 text-muted-foreground";
  if (kind === "cash") return <Wallet className={cls} />;
  if (kind === "forecast") return <TrendingUp className={cls} />;
  if (kind === "receivable") return <CircleDollarSign className={cls} />;
  if (kind === "obligation") return <CalendarClock className={cls} />;
  if (kind === "risk") return <AlertTriangle className="mt-0.5 size-3.5 shrink-0 text-fin-warn" />;
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
