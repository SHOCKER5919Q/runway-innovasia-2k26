"use client";

import { ConcentrationPie } from "@/components/runway/charts";
import {
  ErrorState, LoadingPanel, Panel, Provenance, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { useApi } from "@/lib/use-api";
import { inr, pct, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function SuppliersPage() {
  const { data, loading, error, reload } = useApi<any>("/api/suppliers");
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={8} />;

  const s = data.suppliers;
  const totalSpend = s.reduce((a: number, x: any) => a + x.lifetime_spend_paise, 0);
  const discounts = s.filter((x: any) => x.discount_opportunity_paise > 0);

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Suppliers"
        description="Where your outgoing commitments concentrate, and which of them are negotiable."
        actions={<StateBadge state="actual" />} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Suppliers" value={s.length} state="actual" />
        <Stat label="Total open" value={inr(s.reduce((a: number, x: any) => a + x.outstanding_paise, 0))}
              state="actual" />
        <Stat label="Concentrated suppliers" value={s.filter((x: any) => x.concentration_flag).length}
              tone={s.some((x: any) => x.concentration_flag) ? "warn" : "gain"} state="actual"
              hint="More than 25% of purchase spend from one source" />
        <Stat label="Discounts available"
              value={inr(discounts.reduce((a: number, x: any) => a + x.discount_opportunity_paise, 0))}
              tone="gain" state="actual" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.5fr]">
        <Panel title="Spend concentration" bodyClass="p-2 pt-3">
          <ConcentrationPie items={s.slice(0, 6).map((x: any) => ({
            name: x.name, volume_paise: x.lifetime_spend_paise, share: x.spend_share }))}
            height={250} />
        </Panel>

        <Panel title="Early-payment discounts"
               description="Taking a discount is an investment. It is only worth it if the annualised return beats your cost of credit and the forecast says the cash is spare.">
          {discounts.length ? (
            <ul className="space-y-2.5">
              {discounts.map((x: any) => (
                <li key={x.counterparty_id} className="flex items-start justify-between gap-4 border-b border-border/60 pb-2.5 last:border-0">
                  <div className="min-w-0">
                    <p className="text-[13px]">{x.name}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground">
                      {pct(x.early_discount_pct, 2)} if paid within {x.early_discount_days} days
                      {" "}(terms are {x.credit_days} days)
                    </p>
                  </div>
                  <div className="shrink-0 text-right">
                    <p className="text-[13px] tnum text-fin-gain">
                      {inr(x.discount_opportunity_paise)}
                    </p>
                    <p className="text-[11px] tnum text-muted-foreground">
                      ≈ {pct(x.discount_annualised_return, 1)} p.a.
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No supplier currently offers an early-payment discount on an open invoice.
            </p>
          )}
        </Panel>
      </div>

      <Panel title="All suppliers" bodyClass="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Supplier</th>
                <th className="px-4 py-2.5 text-right font-medium">Spend share</th>
                <th className="px-4 py-2.5 text-right font-medium">18-month spend</th>
                <th className="px-4 py-2.5 text-right font-medium">Open</th>
                <th className="px-4 py-2.5 text-right font-medium">Overdue</th>
                <th className="px-4 py-2.5 text-right font-medium">Terms</th>
                <th className="px-4 py-2.5 text-right font-medium">Mean days to pay</th>
                <th className="px-4 py-2.5 text-right font-medium">MSME class</th>
                <th className="px-4 py-2.5 text-right font-medium">MSMED exposed</th>
              </tr>
            </thead>
            <tbody>
              {s.map((x: any) => (
                <tr key={x.counterparty_id} className="border-b border-border/50 last:border-0 hover:bg-surface-hover">
                  <td className="px-4 py-2.5">
                    <p className="text-[13px]">{x.name}</p>
                    <p className="text-[10px] text-muted-foreground">{x.sector}</p>
                  </td>
                  <td className={cn("px-4 py-2.5 text-right tnum",
                    x.concentration_flag && "font-medium text-fin-warn")}>
                    {pct(x.spend_share, 1)}
                  </td>
                  <td className="px-4 py-2.5 text-right tnum">{inr(x.lifetime_spend_paise, { compact: true })}</td>
                  <td className="px-4 py-2.5 text-right tnum">{inr(x.outstanding_paise, { compact: true })}</td>
                  <td className="px-4 py-2.5 text-right tnum">
                    {x.overdue_paise ? inr(x.overdue_paise, { compact: true }) : "—"}
                  </td>
                  <td className="px-4 py-2.5 text-right tnum text-muted-foreground">{x.credit_days}d</td>
                  <td className="px-4 py-2.5 text-right tnum">{x.mean_days_to_pay}d</td>
                  <td className="px-4 py-2.5 text-right text-[11px] capitalize text-muted-foreground">
                    {x.msme_class ?? "—"}
                  </td>
                  <td className={cn("px-4 py-2.5 text-right tnum",
                    x.msmed_breaches > 0 && "text-fin-loss")}>
                    {x.msmed_exposed_paise ? inr(x.msmed_exposed_paise, { compact: true }) : "—"}
                    {x.msmed_breaches > 0 && (
                      <span className="ml-1 text-[10px]">({x.msmed_breaches} late)</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="px-4 pb-3">
          <Provenance>
            The MSME class shown is what is recorded against each supplier in this
            workspace. Confirm Udyam registration before relying on it for a tax position.
          </Provenance>
        </div>
      </Panel>
    </div>
  );
}
