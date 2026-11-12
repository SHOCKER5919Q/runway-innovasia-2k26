"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { MessageSquare, Search } from "lucide-react";
import { AgeingBars } from "@/components/runway/charts";
import {
  ErrorState, LoadingPanel, Panel, RiskBand, Stat, StateBadge,
} from "@/components/runway/primitives";
import {
  Button, CopyButton, Details, ExportButton, Field, Grid, Modal, Note,
  PageHeader, Rows, Select, Tabs, inputCls, useTabs,
} from "@/components/runway/page-kit";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { inr, money, pct, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const TABS = [
  { key: "collect", label: "Collection list" },
  { key: "ageing", label: "Ageing" },
  { key: "customers", label: "Customers" },
];

export default function ReceivablesPage() {
  const { data, loading, error, reload } = useApi<any>("/api/receivables");
  const [tab, setTab] = useTabs("receivables", "collect");
  const [newOpen, setNewOpen] = useState(false);

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={8} />;

  const overdueCount = data.collection_list.filter((r: any) => r.days_past_due > 0).length;
  const tabs = TABS.map((t) =>
    t.key === "collect" ? { ...t, count: overdueCount } : t);

  return (
    <div>
      <PageHeader
        title="Receivables"
        subtitle="Who owes you, how overdue it is, and when each buyer is likely to pay."
        state={<StateBadge state="actual" />}
        actions={<>
          <ExportButton path="/api/exports/receivables.csv"
                        filename="runway-receivables.csv" label="Export" />
          <ExportButton path="/api/receivables/reminders.csv"
                        filename="runway-reminders.csv" label="Reminders CSV" />
          <Button tone="primary" onClick={() => setNewOpen(true)}>New invoice</Button>
        </>}
      />

      <Grid cols={4} className="mb-4">
        <Stat label="Total outstanding" value={money(data.total)} state="actual" />
        <Stat label="Overdue" value={money(data.overdue)} tone="warn" state="actual"
              sub={<>{pct(data.ageing.overdue_share)} of the book</>} />
        <Stat label="Open invoices"
              value={data.ageing.buckets.reduce((s: number, b: any) => s + b.count, 0)}
              state="actual" />
        <Stat label="Customers at risk"
              value={data.customers.filter((c: any) => ["high", "critical"].includes(c.risk_band)).length}
              tone="warn" state="actual" />
      </Grid>

      <Tabs tabs={tabs} active={tab} onChange={setTab} />

      {tab === "collect" && <CollectionList rows={data.collection_list} onChanged={reload} />}
      {tab === "ageing" && <AgeingTab data={data} />}
      {tab === "customers" && <CustomersTab customers={data.customers} />}

      <NewInvoiceModal open={newOpen} onOpenChange={setNewOpen} onCreated={reload} />
    </div>
  );
}

/* ── collection list ──────────────────────────────────────────── */

function CollectionList({ rows: all, onChanged }: { rows: any[]; onChanged: () => void }) {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<"priority" | "amount" | "age">("priority");
  const [onlyOverdue, setOnlyOverdue] = useState(false);

  const rows = useMemo(() => {
    let r = [...all];
    if (q) r = r.filter((x) =>
      `${x.customer} ${x.invoice_no}`.toLowerCase().includes(q.toLowerCase()));
    if (onlyOverdue) r = r.filter((x) => x.days_past_due > 0);
    r.sort((a, b) =>
      sort === "amount" ? b.outstanding_paise - a.outstanding_paise
      : sort === "age" ? b.days_past_due - a.days_past_due
      : b.priority_score - a.priority_score);
    return r;
  }, [all, q, sort, onlyOverdue]);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…"
                 aria-label="Filter invoices"
                 className="h-8 w-44 rounded-md border border-border bg-surface pl-8 pr-2 text-xs outline-none focus:border-primary/60" />
        </div>
        <Select value={sort} onChange={(v) => setSort(v as any)}
                options={[{ value: "priority", label: "By priority" },
                          { value: "amount", label: "By amount" },
                          { value: "age", label: "By days past due" }]}
                className="h-8 w-auto text-xs" />
        <label className="flex cursor-pointer items-center gap-1.5 text-xs text-muted-foreground">
          <input type="checkbox" checked={onlyOverdue} onChange={(e) => setOnlyOverdue(e.target.checked)}
                 className="size-3.5 accent-[var(--primary)]" />
          Overdue only
        </label>
      </div>

      <Panel bodyClass="p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="px-4 py-2.5 font-medium">Invoice</th>
                <th className="px-4 py-2.5 text-right font-medium">Outstanding</th>
                <th className="px-4 py-2.5 text-right font-medium">Due</th>
                <th className="px-4 py-2.5 text-right font-medium">Predicted</th>
                <th className="px-4 py-2.5 text-right font-medium">P(15d)</th>
                <th className="px-4 py-2.5 font-medium">Action</th>
                <th className="px-4 py-2.5 text-right font-medium">Reminder</th>
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
                    {r.predicted_delay_days != null && (
                      <p className="text-[10px] tnum text-muted-foreground">
                        {r.predicted_delay_days > 0 ? "+" : ""}{Number(r.predicted_delay_days).toFixed(0)}d vs terms
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-right tnum">
                    {r.prob_within_15 != null ? pct(r.prob_within_15) : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <p className="max-w-[16rem] text-[11px] text-muted-foreground text-pretty">
                      {r.recommended_action}
                    </p>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <ReminderCell row={r} />
                  </td>
                </tr>
              ))}
              {!rows.length && (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-sm text-muted-foreground">
                  Nothing matches that filter.
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      </Panel>

      <Details label="Where the predicted dates come from">
        An invoice-level payment-delay model, blended with each customer&rsquo;s own
        settled history and shipped only if it beats that baseline on held-out
        data. Intervals are conformally calibrated, so the stated coverage is
        the coverage you get. A probability is a probability, not a promise.
      </Details>
    </div>
  );
}

function ReminderCell({ row }: { row: any }) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [tone, setTone] = useState("firm");

  async function load() {
    setBusy(true);
    try {
      setData(await api.get<any>(
        `/api/receivables/${row.invoice_id}/reminder?tone=${tone}`));
      setOpen(true);
    } finally { setBusy(false); }
  }
  async function retone(t: string) {
    setTone(t);
    setData(await api.get<any>(`/api/receivables/${row.invoice_id}/reminder?tone=${t}`));
  }

  return (
    <>
      <Button size="sm" tone="ghost" busy={busy} onClick={load}
              icon={<MessageSquare className="size-3.5" />}
              title="Compose a payment reminder">
        Remind
      </Button>
      <Modal open={open} onClose={() => setOpen(false)} title="Payment reminder"
             subtitle={`${row.customer} · ${row.invoice_no}`}>
        {data ? (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Select value={tone} onChange={retone} className="h-8 w-auto text-xs"
                      options={[{ value: "polite", label: "Polite nudge" },
                                { value: "firm", label: "Firm follow-up" },
                                { value: "final", label: "Final notice" }]} />
              <span className="ml-auto text-xs text-muted-foreground">
                {data.days_past_due > 0 ? `${data.days_past_due} days overdue` : "not yet due"}
              </span>
            </div>
            <pre className="whitespace-pre-wrap rounded-lg border border-border bg-surface p-3 font-sans text-[13px] leading-relaxed">
              {data.text}
            </pre>
            <Rows items={[
              { k: "Outstanding", v: money(data.outstanding) },
              { k: "Invoice total", v: money(data.total) },
              { k: "Due date", v: shortDate(data.due_date) },
              { k: "Contact", v: data.customer?.phone ?? "—" },
            ]} />
            <div className="flex flex-wrap items-center justify-end gap-2">
              <CopyButton text={data.text} />
              <a href={data.share_url} target="_blank" rel="noreferrer">
                <Button tone="primary">Open in WhatsApp</Button>
              </a>
            </div>
            <Note tone="warn">
              RUNWAY composes this message — it does not send it and never
              contacts your customer. Read it before you forward it.
            </Note>
          </div>
        ) : <LoadingPanel rows={3} />}
      </Modal>
    </>
  );
}

/* ── ageing ───────────────────────────────────────────────────── */

function AgeingTab({ data }: { data: any }) {
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <Panel title="Ageing buckets" bodyClass="p-2 pt-3">
        <AgeingBars buckets={data.ageing.buckets} height={220} />
        <ul className="mt-2 space-y-1 px-2 pb-1 text-[11px]">
          {data.ageing.buckets.map((b: any) => (
            <li key={b.label} className="flex items-center justify-between">
              <span className="text-muted-foreground">{b.label} · {b.count} invoices</span>
              <span className="tnum">{inr(b.amount_paise)} ({pct(b.share)})</span>
            </li>
          ))}
        </ul>
      </Panel>
      <Panel title="What the ageing says" bodyClass="p-4">
        <Rows items={data.ageing.buckets.map((b: any) => ({
          k: b.label, v: `${inr(b.amount_paise)} · ${pct(b.share)}`,
        }))} />
        <div className="mt-3">
          <Details label="How ageing is computed" dense>
            Each open sales invoice is aged against its own due date as of the
            as-of date, not against its issue date — a 60-day invoice that is
            10 days past due belongs in the 1&ndash;30 bucket. Settled and
            written-off invoices are excluded.
          </Details>
        </div>
      </Panel>
    </div>
  );
}

/* ── customers ────────────────────────────────────────────────── */

function CustomersTab({ customers }: { customers: any[] }) {
  return (
    <Panel title="Payment behaviour" description="Computed from settled invoices only"
           bodyClass="p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Customer</th>
              <th className="px-4 py-2.5 text-right font-medium">Open</th>
              <th className="px-4 py-2.5 text-right font-medium">Mean delay</th>
              <th className="px-4 py-2.5 text-right font-medium">Reliability</th>
              <th className="px-4 py-2.5 text-right font-medium">Risk</th>
            </tr>
          </thead>
          <tbody>
            {customers.map((c: any) => (
              <tr key={c.counterparty_id} className="border-b border-border/50 last:border-0 hover:bg-surface-hover">
                <td className="px-4 py-2.5">
                  <Link href={`/app/customers?id=${c.counterparty_id}`}
                        className="text-[13px] hover:text-primary">{c.name}</Link>
                  <p className="text-[10px] text-muted-foreground">
                    {c.invoices_settled} settled · {pct(c.revenue_share)} of revenue
                  </p>
                </td>
                <td className="px-4 py-2.5 text-right tnum">{inr(c.outstanding_paise, { compact: true })}</td>
                <td className={cn("px-4 py-2.5 text-right tnum",
                  c.mean_delay_days > 20 ? "text-fin-loss"
                    : c.mean_delay_days > 8 ? "text-fin-warn" : "text-fin-gain")}>
                  {c.mean_delay_days > 0 ? "+" : ""}{c.mean_delay_days.toFixed(1)}d
                </td>
                <td className="px-4 py-2.5 text-right tnum">{c.reliability_score.toFixed(0)}</td>
                <td className="px-4 py-2.5 text-right"><RiskBand band={c.risk_band} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

/* ── new invoice ──────────────────────────────────────────────── */

function NewInvoiceModal({ open, onOpenChange, onCreated }:
  { open: boolean; onOpenChange: (v: boolean) => void; onCreated: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState<any>(null);
  const [form, setForm] = useState({
    kind: "sales", invoice_no: "", counterparty_name: "",
    issue_date: new Date().toISOString().slice(0, 10),
    credit_days: "30", amount_rupees: "", gst_rate: "0.18", notes: "",
  });

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const r = await api.post<any>("/api/invoices", {
        kind: form.kind,
        invoice_no: form.invoice_no,
        counterparty_name: form.counterparty_name,
        issue_date: form.issue_date,
        credit_days: Number(form.credit_days),
        amount_rupees: Number(form.amount_rupees),
        gst_rate: Number(form.gst_rate),
        notes: form.notes || undefined,
      });
      setDone(r);
      onCreated();
    } catch (e: any) {
      setErr(e?.message ?? "Could not save the invoice");
    } finally { setBusy(false); }
  }

  function close() {
    onOpenChange(false); setDone(null); setErr(null);
    setForm((f) => ({ ...f, invoice_no: "", counterparty_name: "", amount_rupees: "" }));
  }

  return (
    <Modal open={open} onClose={close} title="New invoice"
           subtitle="Raises a bill by hand and settles it against any payment already on the books.">
      {done ? (
        <div className="space-y-3">
          <div className="rounded-lg border border-fin-gain/30 bg-fin-gain-soft p-3 text-sm">
            <p className="font-medium">{done.invoice_no} saved.</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {done.counterparty.name} · {money(done.total)} · due {shortDate(done.due_date)}
            </p>
            {done.pipeline?.auto_matched_payments?.length > 0 && (
              <p className="mt-1.5 text-xs text-muted-foreground">
                Settled automatically by {done.pipeline.auto_matched_payments.length} payment
                already recorded.
              </p>
            )}
          </div>
          <Rows items={[
            { k: "Taxable", v: money(done.taxable) },
            { k: "GST", v: money(done.tax) },
            { k: "Total", v: money(done.total) },
            { k: "Status", v: done.status },
          ]} />
          <div className="flex justify-end"><Button onClick={close}>Done</Button></div>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Type">
              <Select value={form.kind} onChange={(v) => set("kind", v)}
                      options={[{ value: "sales", label: "Sales invoice (receivable)" },
                                { value: "purchase", label: "Purchase invoice (payable)" }]} />
            </Field>
            <Field label="Invoice number" required>
              <input required value={form.invoice_no} onChange={(e) => set("invoice_no", e.target.value)}
                     placeholder="INV-1234" className={inputCls} />
            </Field>
            <Field label="Customer / supplier" required
                   hint="Created if the name is new to this workspace.">
              <input required value={form.counterparty_name}
                     onChange={(e) => set("counterparty_name", e.target.value)}
                     placeholder="Ravi Traders" className={inputCls} />
            </Field>
            <Field label="Issue date" required>
              <input type="date" required value={form.issue_date}
                     onChange={(e) => set("issue_date", e.target.value)} className={inputCls} />
            </Field>
            <Field label="Total (₹, incl. GST)" required>
              <input type="number" step="0.01" min="0.01" required value={form.amount_rupees}
                     onChange={(e) => set("amount_rupees", e.target.value)}
                     placeholder="118000" className={inputCls} />
            </Field>
            <Field label="Credit days" hint="Used to set the due date.">
              <input type="number" min="0" max="365" value={form.credit_days}
                     onChange={(e) => set("credit_days", e.target.value)} className={inputCls} />
            </Field>
            <Field label="GST rate">
              <Select value={form.gst_rate} onChange={(v) => set("gst_rate", v)}
                      options={[{ value: "0", label: "0%" }, { value: "0.05", label: "5%" },
                                { value: "0.12", label: "12%" }, { value: "0.18", label: "18%" },
                                { value: "0.28", label: "28%" }]} />
            </Field>
          </div>

          {err && (
            <p role="alert" className="rounded-lg border border-fin-loss/30 bg-fin-loss-soft px-3 py-2 text-xs text-fin-loss">
              {err}
            </p>
          )}

          <div className="flex items-center justify-end gap-2 pt-1">
            <Button type="button" tone="ghost" onClick={close}>Cancel</Button>
            <Button type="submit" tone="primary" busy={busy}>Save invoice</Button>
          </div>
          <Note>
            A typed invoice is recorded as an owner estimate until it is matched
            against a payment or a document. It never overwrites an imported row.
          </Note>
        </form>
      )}
    </Modal>
  );
}
