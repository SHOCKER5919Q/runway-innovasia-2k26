"use client";

import { useMemo, useRef, useState } from "react";
import {
  Activity, Boxes, Building2, CircleDollarSign, Clock, FileText, Landmark,
  Receipt, Users, Workflow,
} from "lucide-react";
import { motion } from "motion/react";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { Details } from "@/components/runway/page-kit";
import { useApi } from "@/lib/use-api";
import { inr, longDate, money, pct, shortDate, titleCase, weeks } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function TwinPage() {
  const state = useApi<any>("/api/twin/state");
  const graph = useApi<any>("/api/twin/graph");
  const timeline = useApi<any>("/api/twin/timeline");
  const activity = useApi<any>("/api/twin/activity");
  const [tab, setTab] = useState<"map" | "timeline" | "log">("map");

  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />;
  if (state.loading || !state.data) return <LoadingPanel rows={8} />;
  const d = state.data;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Business Financial Digital Twin"
        description="A continuously-rebuilt computational model of how this business behaves financially: its state, its relationships, and the events heading towards it."
        actions={
          <span className="rw-chip border-border bg-surface text-muted-foreground">
            <Clock className="size-3" /> rebuilt {longDate(d.versions.last_updated.slice(0, 10))}
          </span>} />

      {/* state snapshot */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Available liquidity" value={money(d.financial_state.available_liquidity)}
              state="actual" icon={<Landmark className="size-4" />} />
        <Stat label="Receivables" value={money(d.financial_state.receivables)}
              state="actual" icon={<CircleDollarSign className="size-4" />} />
        <Stat label="Payables" value={money(d.financial_state.payables)}
              state="actual" icon={<Receipt className="size-4" />} />
        <Stat label="Runway P50"
              value={d.forecast_summary ? weeks(d.forecast_summary.runway_weeks_p50) : "—"}
              state="predicted" icon={<Activity className="size-4" />}
              sub={d.forecast_summary ? `P10 ${weeks(d.forecast_summary.runway_weeks_p10)}` : undefined} />
      </div>

      <div className="flex gap-2">
        {([["map", "Relationship map"], ["timeline", "Future timeline"], ["log", "Activity log"]] as const)
          .map(([k, label]) => (
            <button key={k} onClick={() => setTab(k as any)}
              className={cn("rounded-lg border px-3 py-1.5 text-xs",
                tab === k ? "border-primary bg-primary-soft text-primary"
                          : "border-border text-muted-foreground hover:bg-surface-hover")}>
              {label}
            </button>
          ))}
      </div>

      {tab === "map" && <GraphView data={graph.data} loading={graph.loading} />}
      {tab === "timeline" && <TimelineView data={timeline.data} loading={timeline.loading} />}
      {tab === "log" && <ActivityView data={activity.data} loading={activity.loading} />}

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="Customer state" description={`${d.customer_state.length} buyers modelled`}>
          <ul className="space-y-1.5 text-[12px]">
            {d.customer_state.slice(0, 7).map((c: any) => (
              <li key={c.counterparty_id} className="flex items-center justify-between gap-2 border-b border-border/50 pb-1.5 last:border-0">
                <span className="min-w-0 flex-1 truncate">{c.name}</span>
                <span className="tnum text-muted-foreground">
                  {c.mean_delay_days > 0 ? "+" : ""}{c.mean_delay_days.toFixed(0)}d
                </span>
                <span className="w-20 shrink-0 text-right tnum">
                  {inr(c.outstanding_paise, { compact: true })}
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Supplier state" description={`${d.supplier_state.length} suppliers modelled`}>
          <ul className="space-y-1.5 text-[12px]">
            {d.supplier_state.slice(0, 7).map((s: any) => (
              <li key={s.counterparty_id} className="flex items-center justify-between gap-2 border-b border-border/50 pb-1.5 last:border-0">
                <span className="min-w-0 flex-1 truncate">{s.name}</span>
                <span className="tnum text-muted-foreground">{pct(s.spend_share, 0)}</span>
                <span className="w-20 shrink-0 text-right tnum">
                  {inr(s.outstanding_paise, { compact: true })}
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Operational state"
               description="What the twin does not know, stated plainly">
          <ul className="space-y-1.5">
            {d.operational_state.missing.map((m: string) => (
              <li key={m} className="flex items-center gap-2 text-[12px] text-muted-foreground">
                <span className="size-1.5 rounded-full bg-fin-warn" aria-hidden />
                <span className="capitalize">{m}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3">
            <Details label="How this is calculated">
              {d.operational_state.note}
            </Details>
          </div>
        </Panel>
      </div>

      <Panel title="Twin integrity"
             description="Versions, fingerprint and data quality, so the model can always be audited">
        <Evidence dense items={[
          { label: "Actual state version", value: `v${d.versions.actual}` },
          { label: "Predicted state version", value: `v${d.versions.predicted}` },
          { label: "Ledger fingerprint", value: d.versions.ledger_fingerprint },
          { label: "Last rebuilt", value: d.versions.last_updated },
          { label: "Data quality", value: `${d.data_quality.score}/100 (${d.data_quality.band})` },
          { label: "Verified share", value: pct(d.data_quality.verified_share) },
          { label: "Reconciled share", value: pct(d.data_quality.reconciled_share) },
          { label: "Staleness", value: `${d.data_quality.staleness_days} days since last transaction` },
        ]} />
      </Panel>
    </div>
  );
}

/* ── relationship graph (hand-drawn SVG radial layout) ─────────── */

function GraphView({ data, loading }: { data: any; loading: boolean }) {
  const [hover, setHover] = useState<string | null>(null);
  const layout = useMemo(() => {
    if (!data) return null;
    const W = 980, H = 520, cx = W / 2, cy = H / 2;
    const biz = data.nodes.find((n: any) => n.type === "business");
    const customers = data.nodes.filter((n: any) => n.type === "customer");
    const suppliers = data.nodes.filter((n: any) => n.type === "supplier");
    const accounts = data.nodes.filter((n: any) => n.type === "account");
    const obligations = data.nodes.filter((n: any) => n.type === "obligation").slice(0, 8);
    const pos = new Map<string, { x: number; y: number; r: number; n: any }>();
    pos.set(biz.id, { x: cx, y: cy, r: 34, n: biz });

    const maxV = Math.max(1, ...data.nodes.filter((n: any) => n.type !== "business")
      .map((n: any) => n.value));
    const place = (arr: any[], x: number, spread: number) => {
      arr.forEach((n, i) => {
        const t = arr.length === 1 ? 0.5 : i / (arr.length - 1);
        pos.set(n.id, {
          x, y: cy - spread / 2 + t * spread,
          r: 8 + 16 * Math.sqrt(n.value / maxV), n,
        });
      });
    };
    place(customers, 130, 420);
    place(suppliers, W - 130, 420);
    place(accounts, cx - 150, 0);
    accounts.forEach((n: any, i: number) => {
      pos.set(n.id, { x: cx - 120 + i * 120, y: cy - 170,
                      r: 10 + 12 * Math.sqrt(n.value / maxV), n });
    });
    obligations.forEach((n: any, i: number) => {
      const t = obligations.length === 1 ? 0.5 : i / (obligations.length - 1);
      pos.set(n.id, { x: cx - 300 + t * 600, y: cy + 190, r: 7, n });
    });
    const edges = data.edges.filter((e: any) => pos.has(e.source) && pos.has(e.target));
    return { W, H, pos, edges, biz };
  }, [data]);

  if (loading || !layout) return <LoadingPanel rows={6} />;

  return (
    <Panel title="Financial relationship map"
           description="Node size is open exposure. Hover a node for detail."
           bodyClass="p-0">
      <div className="overflow-x-auto p-3">
        <svg viewBox={`0 0 ${layout.W} ${layout.H}`} className="w-full" role="img"
             aria-label="Graph of customers, suppliers, accounts and obligations around the business">
          <defs>
            <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5"
                    markerHeight="5" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="var(--border-strong)" />
            </marker>
          </defs>
          {layout.edges.map((e: any, i: number) => {
            const a = layout.pos.get(e.source)!, b = layout.pos.get(e.target)!;
            const active = hover === e.source || hover === e.target;
            const overdue = (e.meta?.overdue_share ?? 0) > 0.2;
            return (
              <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                    stroke={active ? "var(--primary)" : overdue ? "var(--fin-warn)" : "var(--border)"}
                    strokeWidth={active ? 2 : 1}
                    strokeOpacity={active ? 0.9 : hover ? 0.18 : 0.5}
                    markerEnd="url(#arrow)" />
            );
          })}
          {[...layout.pos.entries()].map(([id, p]) => {
            const n = p.n;
            const fill = n.type === "business" ? "var(--primary)"
              : n.type === "customer" ? "var(--fin-gain)"
              : n.type === "supplier" ? "var(--fin-loss)"
              : n.type === "account" ? "var(--fin-info)"
              : "var(--fin-warn)";
            const active = hover === id;
            return (
              <g key={id} onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover(null)}
                 style={{ cursor: "pointer" }}>
                <circle cx={p.x} cy={p.y} r={p.r} fill={fill}
                        fillOpacity={active ? 0.9 : hover ? 0.2 : 0.55}
                        stroke={fill} strokeWidth={active ? 2 : 1} />
                <text x={p.x} y={p.y + p.r + 12}
                      textAnchor="middle" fontSize="10"
                      fill={active ? "var(--foreground)" : "var(--chart-tick)"}>
                  {String(n.label).length > 20 ? String(n.label).slice(0, 19) + "…" : n.label}
                </text>
                {n.type !== "business" && (
                  <text x={p.x} y={p.y + p.r + 23} textAnchor="middle" fontSize="9"
                        fill="var(--chart-tick)">
                    {inr(n.value, { compact: true })}
                  </text>
                )}
              </g>
            );
          })}
        </svg>
      </div>
      <div className="flex flex-wrap gap-4 border-t border-border px-4 py-2.5 text-[11px] text-muted-foreground">
        {[["Business", "var(--primary)"], ["Customers", "var(--fin-gain)"],
          ["Suppliers", "var(--fin-loss)"], ["Accounts", "var(--fin-info)"],
          ["Obligations", "var(--fin-warn)"]].map(([l, c]) => (
          <span key={l} className="flex items-center gap-1.5">
            <span className="size-2.5 rounded-full" style={{ background: c as string }} aria-hidden />{l}
          </span>
        ))}
      </div>
      <div className="border-t border-border px-4 py-3">
        <ul className="space-y-1">
          {data.insights.map((i: string, k: number) => (
            <li key={k} className="text-[12px] text-muted-foreground text-pretty">· {i}</li>
          ))}
        </ul>
      </div>
    </Panel>
  );
}

function TimelineView({ data, loading }: { data: any; loading: boolean }) {
  if (loading || !data) return <LoadingPanel rows={6} />;
  const future = data.events.filter((e: any) => e.tense === "future");
  const CERT: Record<string, string> = {
    actual: "border-fin-gain/30 bg-fin-gain-soft text-fin-gain",
    contractual: "border-fin-info/30 bg-fin-info-soft text-fin-info",
    estimated: "border-fin-warn/30 bg-fin-warn-soft text-fin-warn",
    predicted: "border-primary/30 bg-primary-soft text-primary",
  };
  return (
    <div className="space-y-4">
      <Panel title="Expected financial events"
             description="Everything heading towards the business, with the certainty of each stated">
        <div className="mb-3 flex flex-wrap gap-3 text-[11px]">
          {Object.entries(data.legend).map(([k, v]) => (
            <span key={k} className={cn("rw-chip", CERT[k])}>{k}: {v as string}</span>
          ))}
        </div>
        <ol className="relative space-y-2 border-l border-border pl-5">
          {future.slice(0, 40).map((e: any) => (
            <li key={e.id} className="relative">
              <span className="absolute -left-[23px] top-2 size-2 rounded-full"
                    style={{ background: e.amount_paise >= 0 ? "var(--fin-gain)" : "var(--fin-loss)" }}
                    aria-hidden />
              <div className="flex flex-wrap items-start justify-between gap-2 rounded-lg border border-border bg-surface/50 p-2.5">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-[12px] font-medium">{e.label}</span>
                    <span className={cn("rw-chip", CERT[e.certainty])}>{e.certainty}</span>
                    {e.overdue && (
                      <span className="rw-chip border-fin-loss/30 bg-fin-loss-soft text-fin-loss">overdue</span>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] text-muted-foreground text-pretty">{e.detail}</p>
                  {e.range && (
                    <p className="mt-0.5 text-[10px] text-muted-foreground">
                      Range {shortDate(e.range.p10_date)} – {shortDate(e.range.p90_date)}
                    </p>
                  )}
                </div>
                <div className="shrink-0 text-right">
                  <p className={cn("text-[13px] tnum",
                    e.amount_paise >= 0 ? "text-fin-gain" : "text-fin-loss")}>
                    {e.amount_paise >= 0 ? "+" : "−"}{inr(Math.abs(e.amount_paise))}
                  </p>
                  <p className="text-[10px] text-muted-foreground">{shortDate(e.date)}</p>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </Panel>

      <Panel title="Weekly roll-up">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="pb-2 font-medium">Week</th>
                <th className="pb-2 text-right font-medium">Events</th>
                <th className="pb-2 text-right font-medium">Expected in</th>
                <th className="pb-2 text-right font-medium">Expected out</th>
                <th className="pb-2 text-right font-medium">Net</th>
                <th className="pb-2 text-right font-medium">Predicted share</th>
              </tr>
            </thead>
            <tbody>
              {data.weekly.map((w: any) => {
                const tot = w.predicted_paise + w.contractual_paise;
                return (
                  <tr key={w.week_start} className="border-b border-border/50 last:border-0">
                    <td className="py-2 tnum">{shortDate(w.week_start)}</td>
                    <td className="py-2 text-right tnum text-muted-foreground">{w.events}</td>
                    <td className="py-2 text-right tnum text-fin-gain">{inr(w.inflow_paise)}</td>
                    <td className="py-2 text-right tnum text-fin-loss">{inr(w.outflow_paise)}</td>
                    <td className={cn("py-2 text-right tnum",
                      w.net_paise >= 0 ? "text-fin-gain" : "text-fin-loss")}>
                      {inr(w.net_paise)}
                    </td>
                    <td className="py-2 text-right tnum text-muted-foreground">
                      {tot ? pct(w.predicted_paise / tot) : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="mt-3">
            <Details label="Where these numbers come from">
              "Predicted share" is how much of that week's movement rests on a model estimate
          rather than a dated commitment. A high share means the week is less certain than
          the totals suggest.
            </Details>
          </div>
      </Panel>
    </div>
  );
}

function ActivityView({ data, loading }: { data: any; loading: boolean }) {
  if (loading || !data) return <LoadingPanel rows={6} />;
  return (
    <Panel title="Digital twin activity log"
           description="Every state rebuild, forecast run and scenario, in order">
      <ol className="relative space-y-2.5 border-l border-border pl-5">
        {data.events.map((e: any) => (
          <li key={e.id} className="relative">
            <span className="absolute -left-[23px] top-1.5 size-2 rounded-full bg-primary" aria-hidden />
            <p className="text-[12px] text-pretty">{e.summary}</p>
            <p className="mt-0.5 text-[10px] text-muted-foreground">
              {titleCase(e.kind)} · {new Date(e.at).toLocaleString("en-IN")}
              {e.state_id ? ` · state ${e.state_id.slice(0, 8)}` : ""}
            </p>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
