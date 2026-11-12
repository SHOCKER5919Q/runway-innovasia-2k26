"use client";

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, ChevronLeft, ChevronRight, Filter, Loader2, Search, X,
} from "lucide-react";
import {
  ErrorState, Evidence, LoadingPanel, Panel, StateBadge,
} from "@/components/runway/primitives";
import {
  Button, Details, ExportButton, Field, Modal, Note, PageHeader, Select, Rows,
  inputCls,
} from "@/components/runway/page-kit";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { longDate, shortDate, titleCase } from "@/lib/format";
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
  const [newOpen, setNewOpen] = useState(false);

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
  const exportQs = useMemo(() => {
    const p = new URLSearchParams();
    if (debounced) p.set("q", debounced);
    if (category) p.set("category", category);
    if (direction) p.set("direction", direction);
    return p.toString() ? `?${p}` : "";
  }, [debounced, category, direction]);
  const detail = useApi<any>(openId ? `/api/transactions/${openId}` : null, [openId]);

  if (error) return <ErrorState message={error} onRetry={reload} />;

  const anyFilter = debounced || category || recon || direction || needsReview;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Transactions"
        subtitle="Every row keeps its original source record and the full chain of transformations applied to it."
        state={<StateBadge state="actual" />}
        actions={<>
          <ExportButton path={`/api/exports/transactions.csv${exportQs}`}
                        filename="runway-transactions.csv" label="Export" />
          <Button tone="primary" onClick={() => setNewOpen(true)}>Add transaction</Button>
        </>} />

      <Panel bodyClass="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <input value={q} onChange={(e) => setQ(e.target.value)}
                   placeholder="Search narration or reference…"
                   className="h-9 w-full rounded-lg border border-border bg-surface pl-8 pr-3 text-sm outline-none focus:border-primary/60" />
          </div>
          <Select value={category}
                  onChange={(v) => { setCategory(v); setPage(1); }}
                  options={[{ value: "", label: "All categories" },
                    ...(data?.facets?.categories ?? []).map((c: any) => ({
                      value: c.value, label: `${titleCase(c.value)} (${c.count})` }))]} />
          <Select value={recon}
                  onChange={(v) => { setRecon(v); setPage(1); }}
                  options={[{ value: "", label: "All statuses" },
                    ...(data?.facets?.recon_status ?? []).map((c: any) => ({
                      value: c.value, label: `${RECON_LABEL[c.value]?.label ?? c.value} (${c.count})` }))]} />
          <Select value={direction}
                  onChange={(v) => { setDirection(v); setPage(1); }}
                  options={[{ value: "", label: "In and out" },
                            { value: "credit", label: "Money in" },
                            { value: "debit", label: "Money out" }]} />
          <Select value={sort} onChange={setSort}
                  options={[{ value: "date_desc", label: "Newest first" },
                            { value: "date_asc", label: "Oldest first" },
                            { value: "amount_desc", label: "Largest first" },
                            { value: "amount_asc", label: "Smallest first" }]} />
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
          <div className="mt-3">
            <Details label="Provenance chain for this row" dense>
              The original imported row is retained verbatim and every
              normalisation step is logged, so any figure on any screen can be
              traced back to its source record.
            </Details>
          </div>
        </Panel>
      )}

      <NewTxnModal open={newOpen} onOpenChange={setNewOpen} onCreated={() => { reload(); setPage(1); }} />
    </div>
  );
}

/* ── add a transaction by hand ────────────────────────────────── */

function NewTxnModal({ open, onOpenChange, onCreated }:
  { open: boolean; onOpenChange: (v: boolean) => void; onCreated: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<any>(null);
  const [form, setForm] = useState({
    direction: "debit", amount_rupees: "", narration: "",
    value_date: new Date().toISOString().slice(0, 10),
    counterparty_name: "", reference_no: "", category: "", fee_rupees: "",
  });
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const r = await api.post<any>("/api/transactions", {
        direction: form.direction,
        amount_rupees: Number(form.amount_rupees),
        narration: form.narration,
        value_date: form.value_date,
        counterparty_name: form.counterparty_name || undefined,
        reference_no: form.reference_no || undefined,
        category: form.category || undefined,
        fee_rupees: form.fee_rupees ? Number(form.fee_rupees) : undefined,
      });
      setDone(r);
      onCreated();
    } catch (e: any) {
      setErr(e?.message ?? "Could not save the transaction");
    } finally { setBusy(false); }
  }

  function close() {
    onOpenChange(false); setDone(null); setErr(null);
    setForm((f) => ({ ...f, amount_rupees: "", narration: "", counterparty_name: "",
                      reference_no: "", fee_rupees: "" }));
  }

  return (
    <Modal open={open} onClose={close} title="Add transaction"
           subtitle="Typed rows go through the same pipeline as an import: duplicate check, counterparty matching, classification and reconciliation.">
      {done ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-fin-gain/30 bg-fin-gain-soft p-3 text-sm">
            <p className="font-medium">Saved{done.duplicate_of ? " and flagged" : ""}.</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {titleCase(done.category)} · {done.recon_status.replace(/_/g, " ")}
              {done.counterparty ? ` · ${done.counterparty.name}` : ""}
            </p>
          </div>
          <Rows items={[
            { k: "Amount", v: done.amount.display },
            { k: "Allocated", v: done.allocated.display },
            { k: "Unallocated", v: done.unallocated.display },
            { k: "Evidence", v: titleCase(done.evidence) },
            ...(done.duplicate_of
              ? [{ k: "Flagged", v: "possible duplicate — review it in the list" }] : []),
          ]} />
          <p className="text-[11px] leading-relaxed text-muted-foreground text-pretty">
            {done.pipeline.reconciliation.note}
          </p>
          <div className="flex justify-end"><Button onClick={close}>Done</Button></div>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Direction">
              <Select value={form.direction} onChange={(v) => set("direction", v)}
                      options={[{ value: "debit", label: "Money out" },
                                { value: "credit", label: "Money in" }]} />
            </Field>
            <Field label="Amount (₹)" required>
              <input type="number" step="0.01" min="0.01" required value={form.amount_rupees}
                     onChange={(e) => set("amount_rupees", e.target.value)}
                     placeholder="12500" className={inputCls} />
            </Field>
            <Field label="Date" required>
              <input type="date" required value={form.value_date}
                     onChange={(e) => set("value_date", e.target.value)} className={inputCls} />
            </Field>
            <Field label="Reference" hint="A bank reference makes duplicate detection exact.">
              <input value={form.reference_no} onChange={(e) => set("reference_no", e.target.value)}
                     placeholder="NEFT-123456" className={inputCls} />
            </Field>
            <div className="sm:col-span-2">
              <Field label="Narration" required>
                <input required value={form.narration} onChange={(e) => set("narration", e.target.value)}
                       placeholder="Paid to Godavari Packaging for cartons" className={inputCls} />
              </Field>
            </div>
            <Field label="Counterparty" hint="Leave blank to let the engine match it from the narration.">
              <input value={form.counterparty_name}
                     onChange={(e) => set("counterparty_name", e.target.value)}
                     placeholder="Godavari Packaging" className={inputCls} />
            </Field>
            <Field label="Category" hint="Optional — otherwise it is classified for you.">
              <Select value={form.category} onChange={(v) => set("category", v)}
                      options={[{ value: "", label: "Classify automatically" },
                                { value: "customer_receipt", label: "Customer receipt" },
                                { value: "supplier_payment", label: "Supplier payment" },
                                { value: "payroll", label: "Payroll" },
                                { value: "gst_payment", label: "GST payment" },
                                { value: "rent", label: "Rent" },
                                { value: "utilities", label: "Utilities" },
                                { value: "freight", label: "Freight" },
                                { value: "bank_charges", label: "Bank charges" },
                                { value: "other_expense", label: "Other expense" },
                                { value: "other_income", label: "Other income" }]} />
            </Field>
            {form.direction === "credit" && (
              <Field label="Gateway fee (₹)"
                     hint="Set this when the bank credited less than the customer paid.">
                <input type="number" step="0.01" min="0" value={form.fee_rupees}
                       onChange={(e) => set("fee_rupees", e.target.value)}
                       placeholder="0" className={inputCls} />
              </Field>
            )}
          </div>

          {err && (
            <p role="alert" className="rounded-lg border border-fin-loss/30 bg-fin-loss-soft px-3 py-2 text-xs text-fin-loss">
              {err}
            </p>
          )}

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button type="button" tone="ghost" onClick={close}>Cancel</Button>
            <Button type="submit" tone="primary" busy={busy}>Save transaction</Button>
          </div>
          <Note>
            A typed row is recorded as an owner estimate. It is promoted to
            verified only when it is matched against an invoice already on file.
          </Note>
        </form>
      )}
    </Modal>
  );
}
