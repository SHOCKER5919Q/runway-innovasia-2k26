"use client";

import { AlertTriangle, CalendarDays, Scale } from "lucide-react";
import { AgeingBars } from "@/components/runway/charts";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { useApi } from "@/lib/use-api";
import { inr, money, pct, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function PayablesPage() {
  const { data, loading, error, reload } = useApi<any>("/api/payables");
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={8} />;
  const m = data.msmed;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Payables"
        description="What you owe, when it is contractually due, and where a statutory deadline arrives first."
        actions={<StateBadge state="actual" />} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Total payable" value={inr(data.ageing.total_paise)} state="actual" />
        <Stat label="Overdue" value={inr(data.ageing.overdue_paise)} tone="warn" state="actual" />
        <Stat label="Owed to micro/small suppliers" value={inr(m.covered_outstanding_paise)}
              state="actual" hint="Covered by MSMED s.15 and Income-tax s.43B(h)" />
        <Stat label="Past the statutory window" value={inr(m.already_breached_paise)}
              tone={m.already_breached_paise > 0 ? "loss" : "gain"} state="actual" />
      </div>

      {(m.already_breached_paise > 0 || m.due_within_14_days_paise > 0) && (
        <div className="rw-card border-fin-warn/30 p-4">
          <div className="flex items-start gap-3">
            <Scale className="mt-0.5 size-4 shrink-0 text-fin-warn" aria-hidden />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">MSMED / Section 43B(h) exposure</p>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground text-pretty">{m.rule}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground text-pretty">{m.caveat}</p>
              {m.items?.length > 0 && (
                <div className="mt-3 overflow-x-auto">
                  <table className="w-full text-[12px]">
                    <thead>
                      <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                        <th className="pb-1.5 font-medium">Invoice</th>
                        <th className="pb-1.5 font-medium">Supplier</th>
                        <th className="pb-1.5 font-medium">Class</th>
                        <th className="pb-1.5 text-right font-medium">Amount</th>
                        <th className="pb-1.5 text-right font-medium">Statutory deadline</th>
                      </tr>
                    </thead>
                    <tbody>
                      {m.items.slice(0, 10).map((i: any) => (
                        <tr key={i.invoice_id} className="border-b border-border/50 last:border-0">
                          <td className="py-1.5 font-mono text-[11px]">{i.invoice_no}</td>
                          <td className="py-1.5">{i.supplier}</td>
                          <td className="py-1.5 capitalize text-muted-foreground">{i.msme_class}</td>
                          <td className="py-1.5 text-right tnum">{inr(i.amount_paise)}</td>
                          <td className={cn("py-1.5 text-right tnum",
                            i.days_remaining < 0 ? "text-fin-loss" : "text-fin-warn")}>
                            {shortDate(i.statutory_deadline)}
                            <span className="ml-1 text-[10px]">
                              ({i.days_remaining < 0 ? `${-i.days_remaining}d late` : `${i.days_remaining}d`})
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[1fr_1.5fr]">
        <Panel title="Payables ageing" bodyClass="p-2 pt-3">
          <AgeingBars buckets={data.ageing.buckets} height={200} />
        </Panel>

        <Panel title="Supplier payment calendar"
               description="Scheduled at the earlier of the contractual due date and the statutory deadline">
          <ul className="space-y-2">
            {data.calendar.slice(0, 9).map((w: any) => (
              <li key={w.week_start} className="border-b border-border/60 pb-2 last:border-0">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-2 text-[13px]">
                    <CalendarDays className="size-3.5 text-muted-foreground" aria-hidden />
                    Week of {shortDate(w.week_start)}
                    <span className="text-[11px] text-muted-foreground">
                      {w.count} invoice{w.count === 1 ? "" : "s"}
                    </span>
                  </span>
                  <span className="tnum text-[13px]">{inr(w.amount_paise)}</span>
                </div>
                {w.msmed_amount_paise > 0 && (
                  <p className="mt-0.5 text-[10px] text-fin-warn">
                    {inr(w.msmed_amount_paise)} of this is owed to micro/small suppliers
                  </p>
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <Panel title="Suppliers" description="Dependency, terms and the discounts on the table">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="pb-2 font-medium">Supplier</th>
                <th className="pb-2 text-right font-medium">Spend share</th>
                <th className="pb-2 text-right font-medium">Open</th>
                <th className="pb-2 text-right font-medium">Overdue</th>
                <th className="pb-2 text-right font-medium">Terms</th>
                <th className="pb-2 text-right font-medium">MSME</th>
                <th className="pb-2 text-right font-medium">Early discount</th>
              </tr>
            </thead>
            <tbody>
              {data.suppliers.map((s: any) => (
                <tr key={s.counterparty_id} className="border-b border-border/50 last:border-0">
                  <td className="py-2">
                    <p className="text-[13px]">{s.name}</p>
                    <p className="text-[10px] text-muted-foreground">{s.sector}</p>
                  </td>
                  <td className={cn("py-2 text-right tnum",
                    s.concentration_flag && "text-fin-warn font-medium")}>
                    {pct(s.spend_share)}
                  </td>
                  <td className="py-2 text-right tnum">{inr(s.outstanding_paise, { compact: true })}</td>
                  <td className="py-2 text-right tnum">
                    {s.overdue_paise > 0 ? inr(s.overdue_paise, { compact: true }) : "—"}
                  </td>
                  <td className="py-2 text-right tnum text-muted-foreground">{s.credit_days}d</td>
                  <td className="py-2 text-right text-[11px] capitalize text-muted-foreground">
                    {s.msme_class ?? "—"}
                  </td>
                  <td className="py-2 text-right">
                    {s.discount_annualised_return ? (
                      <span className="tnum text-[12px] text-fin-gain">
                        {pct(s.early_discount_pct, 2)} → {pct(s.discount_annualised_return, 1)} p.a.
                      </span>
                    ) : <span className="text-muted-foreground">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Provenance>
          The annualised equivalent of a discount d taken n days early is
          (d / (1 − d)) × (365 / n). Compare it against your cost of credit before taking it.
        </Provenance>
      </Panel>
    </div>
  );
}
