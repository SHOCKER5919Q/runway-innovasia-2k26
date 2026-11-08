"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpDown, Phone, Search } from "lucide-react";
import { AgeingBars } from "@/components/runway/charts";
import {
  ErrorState, LoadingPanel, Panel, Provenance, RiskBand, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { useApi } from "@/lib/use-api";
import { inr, money, pct, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function ReceivablesPage() {
  const { data, loading, error, reload } = useApi<any>("/api/receivables");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"priority" | "amount" | "age">("priority");

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={8} />;

  let rows = [...data.collection_list];
  if (q) rows = rows.filter((r: any) =>
    `${r.customer} ${r.invoice_no}`.toLowerCase().includes(q.toLowerCase()));
  rows.sort((a: any, b: any) =>
    sort === "amount" ? b.outstanding_paise - a.outstanding_paise
    : sort === "age" ? b.days_past_due - a.days_past_due
    : b.priority_score - a.priority_score);

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Receivables"
        description="Who owes you, how overdue it is, and when each buyer is actually likely to pay."
        actions={<StateBadge state="actual" />} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Total outstanding" value={money(data.total)} state="actual" />
        <Stat label="Overdue" value={money(data.overdue)} tone="warn" state="actual"
              sub={<>{pct(data.ageing.overdue_share)} of the book</>} />
        <Stat label="Open invoices" value={data.ageing.buckets.reduce((s: number, b: any) => s + b.count, 0)}
              state="actual" />
        <Stat label="Customers at risk"
              value={data.customers.filter((c: any) => ["high", "critical"].includes(c.risk_band)).length}
              tone="warn" state="actual" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.6fr]">
        <Panel title="Ageing" bodyClass="p-2 pt-3">
          <AgeingBars buckets={data.ageing.buckets} height={200} />
          <ul className="mt-2 space-y-1 px-2 pb-1 text-[11px]">
            {data.ageing.buckets.map((b: any) => (
              <li key={b.label} className="flex items-center justify-between">
                <span className="text-muted-foreground">{b.label} · {b.count} invoices</span>
                <span className="tnum">{inr(b.amount_paise)} ({pct(b.share)})</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Customer payment behaviour"
               description="Computed from settled invoices only">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="pb-2 font-medium">Customer</th>
                  <th className="pb-2 text-right font-medium">Open</th>
                  <th className="pb-2 text-right font-medium">Mean delay</th>
                  <th className="pb-2 text-right font-medium">Reliability</th>
                  <th className="pb-2 text-right font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {data.customers.map((c: any) => (
                  <tr key={c.counterparty_id} className="border-b border-border/50 last:border-0">
                    <td className="py-2">
                      <Link href={`/app/customers?id=${c.counterparty_id}`}
                            className="text-[13px] hover:text-primary">{c.name}</Link>
                      <p className="text-[10px] text-muted-foreground">
                        {c.invoices_settled} settled · {pct(c.revenue_share)} of revenue
                      </p>
                    </td>
                    <td className="py-2 text-right tnum">{inr(c.outstanding_paise, { compact: true })}</td>
                    <td className={cn("py-2 text-right tnum",
                      c.mean_delay_days > 20 ? "text-fin-loss"
                        : c.mean_delay_days > 8 ? "text-fin-warn" : "text-fin-gain")}>
                      {c.mean_delay_days > 0 ? "+" : ""}{c.mean_delay_days.toFixed(1)}d
                    </td>
                    <td className="py-2 text-right tnum">{c.reliability_score.toFixed(0)}</td>
                    <td className="py-2 text-right"><RiskBand band={c.risk_band} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <Panel
        title="Prioritised collection list"
        description="Ranked by outstanding amount, days past due and the buyer's measured reliability. Every term is visible."
        actions={
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…"
                     className="h-8 w-40 rounded-md border border-border bg-surface pl-8 pr-2 text-xs outline-none focus:border-primary/60" />
            </div>
            <select value={sort} onChange={(e) => setSort(e.target.value as any)}
                    aria-label="Sort by"
                    className="h-8 rounded-md border border-border bg-surface px-2 text-xs outline-none">
              <option value="priority">By priority</option>
              <option value="amount">By amount</option>
              <option value="age">By days past due</option>
            </select>
          </div>}
        bodyClass="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Invoice</th>
                <th className="px-4 py-2.5 text-right font-medium">Outstanding</th>
                <th className="px-4 py-2.5 text-right font-medium">Due</th>
                <th className="px-4 py-2.5 text-right font-medium">Predicted</th>
                <th className="px-4 py-2.5 text-right font-medium">P(15 days)</th>
                <th className="px-4 py-2.5 text-right font-medium">Priority</th>
                <th className="px-4 py-2.5 font-medium">Recommended action</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: any) => (
                <tr key={r.invoice_id} className="border-b border-border/50 last:border-0 hover:bg-surface-hover">
                  <td className="px-4 py-2.5">
                    <p className="text-[13px] font-medium">{r.customer}</p>
                    <p className="font-mono text-[10px] text-muted-foreground">{r.invoice_no}</p>
                  </td>
                  <td className="px-4 py-2.5 text-right tnum">{inr(r.outstanding_paise)}</td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="tnum">{shortDate(r.due_date)}</span>
                    <p className={cn("text-[10px] tnum",
                      r.days_past_due > 30 ? "text-fin-loss"
                        : r.days_past_due > 0 ? "text-fin-warn" : "text-muted-foreground")}>
                      {r.days_past_due > 0 ? `${r.days_past_due}d overdue` : `in ${-r.days_past_due}d`}
                    </p>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="tnum">{shortDate(r.predicted_pay_date)}</span>
                    {r.predicted_delay_days !== null && r.predicted_delay_days !== undefined && (
                      <p className="text-[10px] tnum text-muted-foreground">
                        {r.predicted_delay_days > 0 ? "+" : ""}{Number(r.predicted_delay_days).toFixed(0)}d vs terms
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right tnum">
                    {r.prob_within_15 !== null && r.prob_within_15 !== undefined
                      ? pct(r.prob_within_15) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="h-1 w-10 overflow-hidden rounded-full bg-surface">
                        <span className="block h-full rounded-full bg-primary"
                              style={{ width: `${Math.min(100, r.priority_score)}%` }} />
                      </span>
                      <span className="tnum text-[11px]">{r.priority_score.toFixed(0)}</span>
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <p className="max-w-xs text-[11px] text-muted-foreground text-pretty">
                      {r.recommended_action}
                    </p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 pb-3">
          <Provenance>
            Predicted dates come from an invoice-level model whose intervals are
            conformally calibrated. A probability is a probability, not a promise.
          </Provenance>
        </div>
      </Panel>
    </div>
  );
}
