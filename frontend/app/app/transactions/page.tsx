"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, ChevronLeft, ChevronRight, Filter, Loader2, Search, X,
} from "lucide-react";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { inr, longDate, shortDate, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

const RECON_LABEL: Record<string, { label: string; cls: string }> = {
  matched: { label: "Matched", cls: "text-fin-gain bg-fin-gain-soft border-fin-gain/25" },
  partially_matched: { label: "Part matched", cls: "text-fin-info bg-fin-info-soft border-fin-info/25" },
  needs_review: { label: "Needs review", cls: "text-fin-warn bg-fin-warn-soft border-fin-warn/30" },
  duplicate_suspect: { label: "Possible duplicate", cls: "text-fin-loss bg-fin-loss-soft border-fin-loss/30" },
  unreconciled: { label: "Unmatched", cls: "text-muted-foreground bg-surface border-border" },
  ignored: { label: "Not invoice-settling", cls: "text-muted-foreground bg-surface border-border" },
};

export default function TransactionsPage() {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const [page, setPage] = useState(1);
  const [category, setCategory] = useState("");
  const [recon, setRecon] = useState("");
  const [direction, setDirection] = useState("");
  const [needsReview, setNeedsReview] = useState(false);
  const [sort, setSort] = useState("date_desc");
  const [openId, setOpenId] = useState<string | null>(null);

  useEffect(() => {
    const t = setTimeout(() => { setDebounced(q); setPage(1); }, 300);
    return () => clearTimeout(t);
  }, [q]);

  const qs = useMemo(() => {
    const p = new URLSearchParams({ page: String(page), page_size: "50", sort });
    if (debounced) p.set("q", debounced);
    if (category) p.set("category", category);
    if (recon) p.set("recon_status", recon);
    if (direction) p.set("direction", direction);
    if (needsReview) p.set("needs_review", "true");
    return p.toString();
  }, [page, debounced, category, recon, direction, needsReview, sort]);

  const { data, loading, error, reload } = useApi<any>(`/api/transactions?${qs}`, [qs]);
  const detail = useApi<any>(openId ? `/api/transactions/${openId}` : null, [openId]);

  if (error) return <ErrorState message={error} onRetry={reload} />;

  const anyFilter = debounced || category || recon || direction || needsReview;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Transactions"
        description="The unified ledger. Every row keeps its original source record and the full chain of transformations applied to it."
        actions={<StateBadge state="actual" />} />

      <Panel bodyClass="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <input value={q} onChange={(e) => setQ(e.target.value)}
                   placeholder="Search narration or reference…"
                   className="h-9 w-full rounded-lg border border-border bg-surface pl-8 pr-3 text-sm outline-none focus:border-primary/60" />
          </div>
          <select value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}
                  aria-label="Category"
                  className="h-9 rounded-lg border border-border bg-surface px-2.5 text-xs outline-none">
            <option value="">All categories</option>
            {data?.facets?.categories?.map((c: any) => (
              <option key={c.value} value={c.value}>{titleCase(c.value)} ({c.count})</option>
            ))}
          </select>
          <select value={recon} onChange={(e) => { setRecon(e.target.value); setPage(1); }}
                  aria-label="Reconciliation status"
                  className="h-9 rounded-lg border border-border bg-surface px-2.5 text-xs outline-none">
            <option value="">All statuses</option>
            {data?.facets?.recon_status?.map((c: any) => (
              <option key={c.value} value={c.value}>
                {RECON_LABEL[c.value]?.label ?? c.value} ({c.count})
              </option>
            ))}
          </select>
          <select value={direction} onChange={(e) => { setDirection(e.target.value); setPage(1); }}
                  aria-label="Direction"
                  className="h-9 rounded-lg border border-border bg-surface px-2.5 text-xs outline-none">
            <option value="">In and out</option>
            <option value="credit">Money in</option>
            <option value="debit">Money out</option>
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value)} aria-label="Sort"
                  className="h-9 rounded-lg border border-border bg-surface px-2.5 text-xs outline-none">
            <option value="date_desc">Newest first</option>
            <option value="date_asc">Oldest first</option>
            <option value="amount_desc">Largest first</option>
            <option value="amount_asc">Smallest first</option>
          </select>
          <button onClick={() => { setNeedsReview((v) => !v); setPage(1); }}
                  aria-pressed={needsReview}
                  className={cn("inline-flex h-9 items-center gap-1.5 rounded-lg border px-3 text-xs",
                    needsReview ? "border-fin-warn/40 bg-fin-warn-soft text-fin-warn"
                                : "border-border text-muted-foreground hover:bg-surface-hover")}>
            <AlertTriangle className="size-3.5" /> Needs review
          </button>
          {anyFilter && (
            <button onClick={() => { setQ(""); setCategory(""); setRecon(""); setDirection("");
                                     setNeedsReview(false); setPage(1); }}
                    className="inline-flex h-9 items-center gap-1 rounded-lg px-2.5 text-xs text-muted-foreground hover:bg-surface-hover">
              <X className="size-3.5" /> Clear
            </button>
          )}
        </div>
      </Panel>

      <Panel bodyClass="p-0"
             title={data ? `${data.total.toLocaleString("en-IN")} transactions` : "Transactions"}
             actions={data && (
               <div className="flex items-center gap-1.5 text-xs">
                 <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1}
                         aria-label="Previous page"
                         className="rounded-md border border-border p-1 disabled:opacity-40 hover:bg-surface-hover">
                   <ChevronLeft className="size-3.5" />
                 </button>
                 <span className="tnum text-muted-foreground">{page} / {data.pages}</span>
                 <button onClick={() => setPage((p) => Math.min(data.pages, p + 1))}
                         disabled={page >= data.pages} aria-label="Next page"
                         className="rounded-md border border-border p-1 disabled:opacity-40 hover:bg-surface-hover">
                   <ChevronRight className="size-3.5" />
                 </button>
               </div>)}>
        {loading && !data ? <LoadingPanel rows={8} /> : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <th className="px-4 py-2.5 font-medium">Date</th>
                  <th className="px-4 py-2.5 font-medium">Narration</th>
                  <th className="px-4 py-2.5 font-medium">Counterparty</th>
                  <th className="px-4 py-2.5 font-medium">Category</th>
                  <th className="px-4 py-2.5 text-right font-medium">Amount</th>
                  <th className="px-4 py-2.5 text-right font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {data?.items?.map((t: any) => {
                  const rs = RECON_LABEL[t.recon_status] ?? RECON_LABEL.unreconciled;
                  return (
                    <tr key={t.id}
                        // The row is the disclosure control, so it has to answer
                        // the keyboard too: Enter and Space, a focus ring, and an
                        // expanded state a screen reader can read.
                        tabIndex={0}
                        role="button"
                        aria-expanded={t.id === openId}
                        onClick={() => setOpenId(t.id === openId ? null : t.id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            setOpenId(t.id === openId ? null : t.id);
                          }
                        }}
                        className={cn("cursor-pointer border-b border-border/50 last:border-0 hover:bg-surface-hover",
                          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-primary/50",
                          t.needs_review && "bg-fin-warn-soft/30")}>
                      <td className="whitespace-nowrap px-4 py-2 tnum text-[12px]">{shortDate(t.date)}</td>
                      <td className="px-4 py-2">
                        <p className="max-w-md truncate text-[12px]">{t.narration}</p>
                        {t.reference_no && (
                          <p className="font-mono text-[10px] text-muted-foreground">{t.reference_no}</p>
                        )}
                      </td>
                      <td className="px-4 py-2 text-[12px]">{t.counterparty ?? "—"}</td>
                      <td className="px-4 py-2">
                        <span className="text-[11px]">{titleCase(t.category)}</span>
                        {t.category_confidence < 0.55 && (
                          <p className="text-[10px] text-fin-warn">low confidence</p>
                        )}
                      </td>
                      <td className={cn("whitespace-nowrap px-4 py-2 text-right tnum",
                        t.direction === "credit" ? "text-fin-gain" : "text-fin-loss")}>
                        {t.direction === "credit" ? "+" : "−"}{t.amount.display}
                        {t.fee && <p className="text-[10px] text-muted-foreground">fee {t.fee.display}</p>}
                      </td>
                      <td className="px-4 py-2 text-right">
                        <span className={cn("rw-chip", rs.cls)}>{rs.label}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {openId && detail.data && (
        <Panel title={`Transaction ${detail.data.reference_no ?? ""}`}
               description={detail.data.narration}
               actions={<button onClick={() => setOpenId(null)}
                                className="rounded-md p-1 text-muted-foreground hover:bg-surface-hover"
                                aria-label="Close detail"><X className="size-4" /></button>}>
          <div className="grid gap-5 lg:grid-cols-3">
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Facts
              </p>
              <Evidence dense items={[
                { label: "Value date", value: longDate(detail.data.date) },
                { label: "Direction", value: titleCase(detail.data.direction) },
                { label: "Amount", value: detail.data.amount.display },
                ...(detail.data.gross ? [{ label: "Gross", value: detail.data.gross.display }] : []),
                ...(detail.data.fee ? [{ label: "Fee", value: detail.data.fee.display }] : []),
                { label: "Category", value: `${titleCase(detail.data.category)} (${(detail.data.category_confidence * 100).toFixed(0)}%)` },
                { label: "Rule", value: detail.data.category_rule },
                { label: "Evidence class", value: titleCase(detail.data.evidence) },
                { label: "Status", value: RECON_LABEL[detail.data.recon_status]?.label ?? detail.data.recon_status },
              ]} />
            </div>
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Allocations
              </p>
              {detail.data.allocations?.length ? (
                <ul className="space-y-2">
                  {detail.data.allocations.map((a: any, i: number) => (
                    <li key={i} className="rounded-lg border border-border bg-surface p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-mono text-[11px]">{a.invoice_no ?? a.invoice_id.slice(0, 8)}</span>
                        <span className="tnum text-[12px]">{a.amount.display}</span>
                      </div>
                      <p className="mt-1 text-[10px] text-muted-foreground text-pretty">{a.rationale}</p>
                      <p className="mt-0.5 text-[10px] text-muted-foreground">
                        {a.method} · confidence {(a.confidence * 100).toFixed(0)}%
                      </p>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[12px] text-muted-foreground">
                  Not allocated to any invoice.
                </p>
              )}
            </div>
            <div>
              <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Provenance
              </p>
              <p className="text-[11px] text-muted-foreground">
                Source: {detail.data.provenance.source_system}
              </p>
              <ol className="mt-2 space-y-1.5">
                {(detail.data.provenance.transform_log ?? []).map((s: any, i: number) => (
                  <li key={i} className="rounded border border-border bg-surface px-2 py-1.5 text-[10px]">
                    <span className="font-medium">{s.step}</span>
                    {Object.entries(s).filter(([k]) => k !== "step").map(([k, v]) => (
                      <span key={k} className="block text-muted-foreground">
                        {k}: {String(v).slice(0, 100)}
                      </span>
                    ))}
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <Provenance>
            The original imported row is retained verbatim and every normalisation step is
            logged, so any figure on any screen can be traced back to its source record.
          </Provenance>
        </Panel>
      )}
    </div>
  );
}
