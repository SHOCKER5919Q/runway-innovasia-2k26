"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowLeft, Phone, TrendingUp, User } from "lucide-react";
import { ConcentrationPie, RiskScatter, Spark } from "@/components/runway/charts";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, RiskBand, SectionHeader,
  Stat, StateBadge,
} from "@/components/runway/primitives";
import { Details, Note, PageHeader } from "@/components/runway/page-kit";
import { useApi } from "@/lib/use-api";
import { inr, pct, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function Page() {
  return <Suspense fallback={<LoadingPanel rows={6} />}><CustomersPage /></Suspense>;
}

function CustomersPage() {
  const params = useSearchParams();
  const [selected, setSelected] = useState<string | null>(params.get("id"));
  const list = useApi<any>("/api/customers");
  const detail = useApi<any>(selected ? `/api/customers/${selected}` : null, [selected]);

  if (list.error) return <ErrorState message={list.error} onRetry={list.reload} />;
  if (list.loading || !list.data) return <LoadingPanel rows={8} />;

  if (selected && detail.data) return <CustomerDetail d={detail.data} onBack={() => setSelected(null)} />;

  const cs = list.data.customers;
  const conc = list.data.concentration;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Customers"
        subtitle="Payment behaviour per buyer, computed only from invoices they have actually settled."
        state={<StateBadge state="actual" />} />

      <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <Panel title="Delay against exposure"
               description="The top-right quadrant is where the money and the risk are both large">
          <RiskScatter points={cs.map((c: any) => ({
            name: c.name, delay: c.mean_delay_days,
            exposure: c.outstanding_paise, reliability: c.reliability_score }))} height={280} />
        </Panel>
        <Panel title="Revenue concentration" description={conc.interpretation} bodyClass="p-2 pt-3">
          <ConcentrationPie items={conc.top_counterparties.slice(0, 6)} height={240} />
          <div className="grid grid-cols-3 gap-2 px-2 pb-1">
            <Stat label="HHI" value={conc.counterparty_hhi.toFixed(3)} sub={conc.counterparty_band} />
            <Stat label="Top 1" value={pct(conc.top1_share)} />
            <Stat label="Effective n" value={String(conc.effective_counterparties)} />
          </div>
        </Panel>
      </div>

      <Panel title="All customers" bodyClass="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Customer</th>
                <th className="px-4 py-2.5 text-right font-medium">Revenue share</th>
                <th className="px-4 py-2.5 text-right font-medium">Open</th>
                <th className="px-4 py-2.5 text-right font-medium">Overdue</th>
                <th className="px-4 py-2.5 text-right font-medium">Mean / median delay</th>
                <th className="px-4 py-2.5 text-right font-medium">On time</th>
                <th className="px-4 py-2.5 text-right font-medium">DSO</th>
                <th className="px-4 py-2.5 text-right font-medium">Reliability</th>
                <th className="px-4 py-2.5 text-right font-medium">Risk</th>
              </tr>
            </thead>
            <tbody>
              {cs.map((c: any) => (
                <tr key={c.counterparty_id}
                    onClick={() => setSelected(c.counterparty_id)}
                    className="cursor-pointer border-b border-border/50 last:border-0 hover:bg-surface-hover">
                  <td className="px-4 py-2.5">
                    <p className="text-[13px] font-medium">{c.name}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {c.sector} · {c.region} · {c.credit_days}-day terms
                    </p>
                  </td>
                  <td className="px-4 py-2.5 text-right tnum">{pct(c.revenue_share, 1)}</td>
                  <td className="px-4 py-2.5 text-right tnum">{inr(c.outstanding_paise, { compact: true })}</td>
                  <td className="px-4 py-2.5 text-right tnum">
                    {c.overdue_paise ? inr(c.overdue_paise, { compact: true }) : "—"}
                  </td>
                  <td className={cn("px-4 py-2.5 text-right tnum",
                    c.mean_delay_days > 20 ? "text-fin-loss"
                      : c.mean_delay_days > 8 ? "text-fin-warn" : "text-fin-gain")}>
                    {c.mean_delay_days > 0 ? "+" : ""}{c.mean_delay_days.toFixed(1)} /{" "}
                    {c.median_delay_days > 0 ? "+" : ""}{c.median_delay_days.toFixed(0)}d
                  </td>
                  <td className="px-4 py-2.5 text-right tnum">{pct(c.on_time_rate)}</td>
                  <td className="px-4 py-2.5 text-right tnum">{c.dso_days ?? "—"}</td>
                  <td className="px-4 py-2.5 text-right tnum">{c.reliability_score.toFixed(0)}</td>
                  <td className="px-4 py-2.5 text-right"><RiskBand band={c.risk_band} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 pb-3">
          <div className="mt-3">
            <Details label="How this is calculated">
              Reliability blends punctuality (55%), consistency of timing (25%) and current
            overdue exposure (20%). Open invoices are excluded from the delay statistics
            because an unpaid invoice says nothing about how fast someone pays.
            </Details>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function CustomerDetail({ d, onBack }: { d: any; onBack: () => void }) {
  const c = d.counterparty;
  const b = d.behaviour;
  const delays = d.monthly.filter((m: any) => m.mean_delay_days !== null)
    .map((m: any) => m.mean_delay_days);
  return (
    <div className="space-y-5">
      <button onClick={onBack}
              className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> All customers
      </button>

      <SectionHeader title={c.name}
        description={`${c.sector ?? ""} · ${c.region ?? ""} · ${c.credit_days}-day credit terms`}
        actions={b && <RiskBand band={b.risk_band} />} />

      {b && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Stat label="Open exposure" value={inr(b.outstanding_paise)} state="actual" />
          <Stat label="Overdue" value={inr(b.overdue_paise)} tone="warn" state="actual"
                sub={b.oldest_overdue_days ? `oldest ${b.oldest_overdue_days}d` : undefined} />
          <Stat label="Mean delay" value={`${b.mean_delay_days > 0 ? "+" : ""}${b.mean_delay_days.toFixed(1)}d`}
                tone={b.mean_delay_days > 15 ? "loss" : b.mean_delay_days > 5 ? "warn" : "gain"}
                state="actual" sub={`median ${b.median_delay_days.toFixed(0)}d, P90 ${b.p90_delay_days.toFixed(0)}d`} />
          <Stat label="Reliability" value={`${b.reliability_score.toFixed(0)}/100`} state="actual"
                sub={`${pct(b.on_time_rate)} on time`} />
          <Stat label="Revenue share" value={pct(b.revenue_share, 1)} state="actual"
                sub={`${b.invoices_settled} settled invoices`} />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Payment behaviour over time"
               description="Mean days against terms, per month">
          {delays.length > 2 ? (
            <>
              <Spark data={delays} color="var(--fin-warn)" height={80} />
              <div className="mt-2 overflow-x-auto">
                <table className="w-full text-[12px]">
                  <thead>
                    <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                      <th className="pb-1.5 font-medium">Month</th>
                      <th className="pb-1.5 text-right font-medium">Billed</th>
                      <th className="pb-1.5 text-right font-medium">Invoices</th>
                      <th className="pb-1.5 text-right font-medium">Mean delay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.monthly.slice(-10).reverse().map((m: any) => (
                      <tr key={m.month} className="border-b border-border/50 last:border-0">
                        <td className="py-1.5">{m.month}</td>
                        <td className="py-1.5 text-right tnum">{inr(m.billed_paise, { compact: true })}</td>
                        <td className="py-1.5 text-right tnum text-muted-foreground">{m.count}</td>
                        <td className={cn("py-1.5 text-right tnum",
                          (m.mean_delay_days ?? 0) > 15 ? "text-fin-loss"
                            : (m.mean_delay_days ?? 0) > 5 ? "text-fin-warn" : "")}>
                          {m.mean_delay_days === null ? "—"
                            : `${m.mean_delay_days > 0 ? "+" : ""}${m.mean_delay_days}d`}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : <p className="py-6 text-center text-sm text-muted-foreground">Not enough settled history.</p>}
        </Panel>

        <Panel title="Evidence behind the assessment">
          {b && <Evidence items={b.evidence.map((e: string, i: number) => ({ label: `#${i + 1}`, value: e }))} dense />}
          <div className="mt-4 space-y-1.5 text-[12px]">
            {c.contact_name && <p><span className="text-muted-foreground">Contact: </span>{c.contact_name}</p>}
            {c.contact_phone && <p><span className="text-muted-foreground">Phone: </span>{c.contact_phone}</p>}
            {c.gstin && <p><span className="text-muted-foreground">GSTIN: </span><span className="font-mono">{c.gstin}</span></p>}
            <p><span className="text-muted-foreground">Credit limit: </span>{inr(c.credit_limit?.paise ?? 0)}</p>
          </div>
        </Panel>
      </div>

      <Panel title="Invoices" bodyClass="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Invoice</th>
                <th className="px-4 py-2.5 text-right font-medium">Issued</th>
                <th className="px-4 py-2.5 text-right font-medium">Due</th>
                <th className="px-4 py-2.5 text-right font-medium">Settled</th>
                <th className="px-4 py-2.5 text-right font-medium">Delay</th>
                <th className="px-4 py-2.5 text-right font-medium">Total</th>
                <th className="px-4 py-2.5 text-right font-medium">Outstanding</th>
                <th className="px-4 py-2.5 text-right font-medium">Predicted pay</th>
              </tr>
            </thead>
            <tbody>
              {d.invoices.map((i: any) => (
                <tr key={i.id} className="border-b border-border/50 last:border-0">
                  <td className="px-4 py-2 font-mono text-[11px]">{i.invoice_no}</td>
                  <td className="px-4 py-2 text-right tnum">{shortDate(i.issue_date)}</td>
                  <td className="px-4 py-2 text-right tnum">{shortDate(i.due_date)}</td>
                  <td className="px-4 py-2 text-right tnum">
                    {i.settled_date ? shortDate(i.settled_date) : "—"}
                  </td>
                  <td className={cn("px-4 py-2 text-right tnum",
                    (i.delay_days ?? 0) > 15 ? "text-fin-loss" : (i.delay_days ?? 0) > 0 ? "text-fin-warn" : "")}>
                    {i.delay_days === null ? "—" : `${i.delay_days > 0 ? "+" : ""}${i.delay_days}d`}
                  </td>
                  <td className="px-4 py-2 text-right tnum">{i.total.display}</td>
                  <td className="px-4 py-2 text-right tnum">
                    {i.outstanding.paise > 0 ? i.outstanding.display : "—"}
                  </td>
                  <td className="px-4 py-2 text-right tnum text-muted-foreground">
                    {i.prediction ? shortDate(i.prediction.predicted_pay_date) : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
