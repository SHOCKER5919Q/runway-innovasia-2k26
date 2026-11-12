"use client";

import Link from "next/link";
import { AlertTriangle, Building2, ChevronRight } from "lucide-react";
import {
  ErrorState, LevelPill, LoadingPanel, Panel, Provenance, SectionHeader, Stat,
} from "@/components/runway/primitives";
import { session } from "@/lib/api";
import { Details } from "@/components/runway/page-kit";
import { useApi } from "@/lib/use-api";
import { money, pct, weeks } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function AccountantPage() {
  const { data, loading, error, reload } = useApi<any>("/api/accountant/portfolio");
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={6} />;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Client portfolio"
        description="Exception-based, not a wall of numbers. Clients are ordered by how much they need attention." />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Clients" value={data.summary.clients} icon={<Building2 className="size-4" />} />
        <Stat label="Needing attention" value={data.summary.needing_attention}
              tone={data.summary.needing_attention ? "warn" : "gain"}
              icon={<AlertTriangle className="size-4" />} />
        <Stat label="Total receivables" value={money(data.summary.total_receivables)} />
        <Stat label="Total overdue" value={money(data.summary.total_overdue)} tone="warn" />
      </div>

      <div className="space-y-3">
        {data.clients.map((c: any) => (
          <article key={c.business.id} className="rw-card p-4">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <h3 className="text-[15px] font-medium">{c.business.name}</h3>
                <p className="mt-0.5 text-[11px] capitalize text-muted-foreground">
                  {c.business.industry.replace(/_/g, " ")} · {c.business.city} · your role: {c.business.role}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className={cn("rw-chip",
                  c.health.score >= 65 ? "border-fin-gain/30 bg-fin-gain-soft text-fin-gain"
                    : c.health.score >= 50 ? "border-fin-warn/30 bg-fin-warn-soft text-fin-warn"
                    : "border-fin-loss/30 bg-fin-loss-soft text-fin-loss")}>
                  Health {c.health.score} · {c.health.band}
                </span>
                <button
                  onClick={() => { session.setBusiness(c.business.id); window.location.href = "/app"; }}
                  className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1 text-xs hover:bg-surface-hover">
                  Open <ChevronRight className="size-3" />
                </button>
              </div>
            </div>

            <div className="mt-3 grid gap-2 text-[12px] sm:grid-cols-3 lg:grid-cols-6">
              <Metric label="Cash" value={money(c.cash)} />
              <Metric label="Receivables" value={money(c.receivables)}
                      sub={`${money(c.receivables_overdue, true)} overdue`} />
              <Metric label="Payables" value={money(c.payables)} />
              <Metric label="Runway P50" value={weeks(c.runway_weeks_p50)}
                      sub={`P10 ${weeks(c.runway_weeks_p10)}`} />
              <Metric label="Breach risk" value={pct(c.breach_probability)} />
              <Metric label="Unreconciled" value={String(c.unreconciled)}
                      sub={`DQ ${c.data_quality}/100`} />
            </div>

            {c.exceptions.length > 0 && (
              <ul className="mt-3 space-y-1.5 border-t border-border pt-3">
                {c.exceptions.map((e: any, i: number) => (
                  <li key={i} className="flex items-start gap-2">
                    <LevelPill level={e.level} />
                    <span className="text-[12px] text-pretty">{e.title}</span>
                  </li>
                ))}
              </ul>
            )}

            {(c.msmed_breached?.paise > 0 || c.next_gst) && (
              <div className="mt-3 flex flex-wrap gap-4 border-t border-border pt-2.5 text-[11px] text-muted-foreground">
                {c.msmed_breached?.paise > 0 && (
                  <span className="text-fin-loss">
                    MSMED breach exposure {c.msmed_breached.display}
                  </span>
                )}
                {c.next_gst && (
                  <span>
                    Next GST {c.next_gst.label}: {c.next_gst.amount_paise ? money({ paise: c.next_gst.amount_paise } as any) : ""}
                    {" "}in {c.next_gst.days_away} days
                  </span>
                )}
              </div>
            )}
          </article>
        ))}
      </div>

      <div className="mt-3">
            <Details label="How this is calculated">
              {data.note}
            </Details>
          </div>
    </div>
  );
}

function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface px-2.5 py-2">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <p className="mt-0.5 tnum">{value}</p>
      {sub && <p className="text-[10px] text-muted-foreground tnum">{sub}</p>}
    </div>
  );
}
