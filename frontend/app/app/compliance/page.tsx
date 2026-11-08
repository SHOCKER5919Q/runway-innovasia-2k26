"use client";

import { CalendarDays, Scale, ShieldAlert } from "lucide-react";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { useApi } from "@/lib/use-api";
import { inr, longDate, money, pct, relDays, shortDate, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function CompliancePage() {
  const { data, loading, error, reload } = useApi<any>("/api/compliance");
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={8} />;

  const cal = data.calendar;
  const cov = data.coverage;
  const byMonth: Record<string, any[]> = {};
  cal.items.forEach((i: any) => {
    const k = i.due_date.slice(0, 7);
    (byMonth[k] ??= []).push(i);
  });

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Compliance Calendar"
        description="Statutory and contractual deadlines from your own ledger, with the money needed to meet them."
        actions={<StateBadge state="actual" />} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Due in 95 days" value={inr(cal.total_upcoming_paise)} state="actual" />
        <Stat label="Statutory portion" value={inr(cal.statutory_paise)} tone="warn" state="actual" />
        <Stat label="RUNWAY estimates" value={inr(cal.estimated_paise)} state="actual"
              hint="Derived from the ledger, not from a filed return" />
        <Stat label="45-day coverage" value={`${cov.coverage_ratio?.toFixed(2)}×`}
              tone={cov.coverage_ratio >= 1.2 ? "gain" : cov.coverage_ratio >= 1 ? "warn" : "loss"}
              state="predicted"
              sub={`cash alone ${cov.coverage_ratio_cash_only?.toFixed(2)}×`} />
      </div>

      {data.next_gst && (
        <div className="rw-card flex flex-wrap items-center justify-between gap-4 border-primary/25 p-4">
          <div className="flex items-start gap-3">
            <CalendarDays className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
            <div>
              <p className="text-sm font-medium">
                Next {data.next_gst.return} is due {longDate(data.next_gst.due_date)}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Covering {data.next_gst.period} · {data.next_gst.days_away} days away ·{" "}
                {data.next_gst.note}
              </p>
            </div>
          </div>
        </div>
      )}

      <Panel title="Obligation calendar" bodyClass="p-0">
        {Object.entries(byMonth).map(([m, items]) => (
          <div key={m}>
            <p className="sticky top-14 z-10 border-y border-border bg-surface px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {new Date(m + "-01T00:00:00").toLocaleDateString("en-IN", { month: "long", year: "numeric" })}
              <span className="ml-2 font-normal tnum">
                {inr(items.reduce((s, i) => s + i.amount_paise, 0))}
              </span>
            </p>
            <ul className="divide-y divide-border/60">
              {items.map((i: any) => (
                <li key={i.id} className={cn("flex items-start justify-between gap-4 px-4 py-2.5",
                  i.overdue && "bg-fin-loss-soft/30")}>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-[13px]">{i.label}</span>
                      {i.statutory && (
                        <span className="rw-chip border-fin-warn/30 bg-fin-warn-soft text-fin-warn">
                          statutory
                        </span>
                      )}
                      {i.is_estimated && (
                        <span className="rw-chip border-border bg-surface text-muted-foreground">
                          RUNWAY estimate
                        </span>
                      )}
                      {i.reserve_cash && (
                        <span className="rw-chip border-primary/30 bg-primary-soft text-primary">
                          cash reserved
                        </span>
                      )}
                      {i.overdue && (
                        <span className="rw-chip border-fin-loss/30 bg-fin-loss-soft text-fin-loss">
                          overdue
                        </span>
                      )}
                    </div>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {titleCase(i.kind)} · {shortDate(i.due_date)} · {relDays(i.due_date, data.as_of)}
                      {i.detail?.basis ? ` · ${i.detail.basis}` : ""}
                    </p>
                  </div>
                  <span className="shrink-0 text-[13px] tnum">{inr(i.amount_paise)}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
        <div className="px-4 py-3">
          <Provenance>{cal.note}</Provenance>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Can you cover it?" description={`Over the next ${cov.horizon_days} days`}>
          <Evidence items={[
            { label: "Obligations due", value: inr(cov.total_paise) },
            { label: "of which statutory", value: inr(cov.statutory_paise) },
            { label: "Available liquidity", value: inr(cov.available_liquidity_paise) },
            { label: "Expected collections", value: inr(cov.expected_collections_paise) },
            { label: "Coverage (cash only)", value: `${cov.coverage_ratio_cash_only?.toFixed(2)}×` },
            { label: "Coverage with collections", value: `${cov.coverage_ratio?.toFixed(2)}×` },
            { label: "With overdraft", value: `${cov.with_overdraft_ratio?.toFixed(2)}×` },
            { label: "Shortfall", value: cov.shortfall_paise ? inr(cov.shortfall_paise) : "none" },
          ]} dense />
          <Provenance>
            Expected collections are {cov.expected_collections_basis}. The cash-only ratio
            is the pessimistic read: it assumes nothing arrives at all.
          </Provenance>
        </Panel>

        <Panel title="Rules RUNWAY applies"
               description="Implemented in the engine, not just described here">
          <ul className="space-y-3">
            {data.rules.map((r: any) => (
              <li key={r.code} className="rounded-lg border border-border bg-surface p-3">
                <p className="flex items-center gap-2 text-[12px] font-medium">
                  <Scale className="size-3.5 text-muted-foreground" aria-hidden />
                  {r.code}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground text-pretty">
                  {r.summary}
                </p>
                <p className="mt-1.5 text-[11px] leading-relaxed text-pretty">
                  <span className="text-muted-foreground">How RUNWAY handles it: </span>
                  {r.runway_handling}
                </p>
              </li>
            ))}
          </ul>
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-fin-warn/30 bg-fin-warn-soft p-3">
            <ShieldAlert className="mt-0.5 size-3.5 shrink-0 text-fin-warn" aria-hidden />
            <p className="text-[11px] leading-relaxed text-fin-warn text-pretty">
              {data.disclaimer}
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
