"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, Building2, CalendarClock, Check, CloudUpload, Download,
  FileSpreadsheet, Landmark, Loader2, Plus, Receipt, ShieldCheck, Wallet,
} from "lucide-react";
import {
  ErrorState, LoadingPanel, Panel, Provenance, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { inr, longDate, money, shortDate, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

type StepId = "cash" | "invoices" | "obligations" | "bank";

const STEPS: { id: StepId; num: string; label: string; desc: string }[] = [
  { id: "cash", num: "01", label: "Bank balance & floor", desc: "Cash in hand, OD limit & safety buffer" },
  { id: "invoices", num: "02", label: "Invoices & bills", desc: "Who owes you & whom you owe" },
  { id: "obligations", num: "03", label: "Monthly commitments", desc: "Payroll, rent, GST & loan EMIs" },
  { id: "bank", num: "04", label: "Bank transactions", desc: "Upload bank CSV or add entries" },
];

const OBLIGATION_PRESETS = [
  { kind: "payroll", label: "Monthly staff & worker payroll", recurring: true },
  { kind: "rent", label: "Factory / shop rent", recurring: true },
  { kind: "gst", label: "Monthly GSTR-3B payment", recurring: false },
  { kind: "utility", label: "Electricity & power bill", recurring: true },
];

function isoOffset(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

function rupeesToPaise(val: string): number {
  const n = Number(val);
  return Number.isFinite(n) ? Math.round(n * 100) : 0;
}

export default function OnboardingPage() {
  const ov = useApi<any>("/api/overview");
  const biz = useApi<any>("/api/business");
  const accs = useApi<any>("/api/accounts");
  const comp = useApi<any>("/api/compliance");
  const [step, setStep] = useState<StepId>("cash");
  const [banner, setBanner] = useState<string | null>(null);

  const reloadAll = () => {
    ov.reload();
    biz.reload();
    accs.reload();
    comp.reload();
  };

  if (ov.error) return <ErrorState message={ov.error} onRetry={reloadAll} />;
  if (ov.loading || biz.loading || accs.loading) return <LoadingPanel rows={8} />;

  const h = ov.data?.headline;
  const accountsList = accs.data?.position?.accounts ?? [];

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Set up your business data"
        description="Enter your numbers directly or upload a CSV/PDF. Every screen — Cash Runway, Scenario Lab, Risk Centre, Recommendations, Health & Copilot — immediately computes from your ledger."
        actions={
          <Link href="/app" className="btn btn-primary h-9 px-4 text-xs">
            Open live dashboard <ArrowRight className="size-3.5" />
          </Link>
        }
      />

      {banner && (
        <div role="status" className="flex items-center justify-between gap-3 rounded-xl border border-gain/30 bg-gain/10 px-4 py-3 text-xs font-medium text-gain">
          <span className="flex items-center gap-2"><Check className="size-4 shrink-0" /> {banner}</span>
          <button onClick={() => setBanner(null)} className="text-[11px] underline">Dismiss</button>
        </div>
      )}

      {/* live progress summary */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="Cash in hand" value={money(h?.cash_in_hand)} state="actual"
              icon={<Wallet className="size-4" />}
              sub={<>{accountsList.length} account{accountsList.length === 1 ? "" : "s"} connected</>} />
        <Stat label="Open receivables" value={money(h?.receivables)} state="actual"
              icon={<Receipt className="size-4" />}
              sub={<>{h?.receivables_overdue?.paise > 0 ? `${money(h.receivables_overdue)} overdue` : "Customer invoices"}</>} />
        <Stat label="Open payables" value={money(h?.payables)} state="actual"
              icon={<Landmark className="size-4" />}
              sub={<>Supplier bills on file</>} />
        <Stat label="Runway P50" state="predicted"
              value={h?.runway_censored ? "13+ wk" : `${Number(h?.runway_weeks_p50 ?? 0).toFixed(1)} wk`}
              sub={<>Safety floor {money(biz.data?.policies?.safety_buffer)}</>} />
      </div>

      {/* step switcher */}
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((s) => {
          const active = step === s.id;
          return (
            <button key={s.id} type="button" onClick={() => setStep(s.id)}
              className={cn("rounded-2xl border p-4 text-left transition",
                active ? "border-forest bg-forest text-white" : "border-line bg-card hover:border-forest-3")}>
              <div className="flex items-center justify-between">
                <span className={cn("text-[11px] font-bold tracking-wider",
                  active ? "text-lime" : "text-ink-3")}>STEP {s.num}</span>
                {active && <span className="size-2 rounded-full bg-lime" />}
              </div>
              <p className="mt-1.5 text-sm font-semibold">{s.label}</p>
              <p className={cn("mt-0.5 text-xs", active ? "text-white/75" : "text-ink-3")}>{s.desc}</p>
            </button>
          );
        })}
      </div>

      {step === "cash" && (
        <CashAndBufferStep
          accounts={accountsList}
          safetyBufferPaise={biz.data?.policies?.safety_buffer?.paise ?? 0}
          onDone={(msg) => { setBanner(msg); reloadAll(); }}
          onNext={() => setStep("invoices")}
        />
      )}

      {step === "invoices" && (
        <InvoicesStep
          accountId={accountsList[0]?.account_id ?? ""}
          onDone={(msg) => { setBanner(msg); reloadAll(); }}
          onNext={() => setStep("obligations")}
        />
      )}

      {step === "obligations" && (
        <ObligationsStep
          upcoming={comp.data?.calendar?.items ?? []}
          onDone={(msg) => { setBanner(msg); reloadAll(); }}
          onNext={() => setStep("bank")}
        />
      )}

      {step === "bank" && (
        <BankAndTransactionsStep
          accounts={accountsList}
          onDone={(msg) => { setBanner(msg); reloadAll(); }}
        />
      )}
    </div>
  );
}

/* ─────────────────────────── STEP 1: CASH & BUFFER ─────────────────────────── */

function CashAndBufferStep({
  accounts, safetyBufferPaise, onDone, onNext,
}: {
  accounts: any[];
  safetyBufferPaise: number;
  onDone: (msg: string) => void;
  onNext: () => void;
}) {
  const first = accounts[0];
  const [accId, setAccId] = useState(first?.account_id ?? "");
  const [accName, setAccName] = useState(first?.name ?? "Primary Bank Account");
  const [openingRupees, setOpeningRupees] = useState(
    first ? String(Math.round(first.opening_paise / 100)) : "500000"
  );
  const [odRupees, setOdRupees] = useState(
    first ? String(Math.round(first.overdraft_limit_paise / 100)) : "0"
  );
  const [restrictedRupees, setRestrictedRupees] = useState(
    first ? String(Math.round(first.restricted_paise / 100)) : "0"
  );
  const [bufferRupees, setBufferRupees] = useState(String(Math.round(safetyBufferPaise / 100)));
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const selected = accounts.find((a) => a.account_id === accId) ?? accounts[0];
    if (selected) {
      setAccId(selected.account_id);
      setAccName(selected.name);
      setOpeningRupees(String(Math.round(selected.opening_paise / 100)));
      setOdRupees(String(Math.round(selected.overdraft_limit_paise / 100)));
      setRestrictedRupees(String(Math.round(selected.restricted_paise / 100)));
    }
  }, [accId, accounts]);

  async function save(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const payload = {
        name: accName.trim() || "Primary Bank Account",
        opening_balance_paise: rupeesToPaise(openingRupees),
        overdraft_limit_paise: Math.max(0, rupeesToPaise(odRupees)),
        restricted_paise: Math.max(0, rupeesToPaise(restrictedRupees)),
      };
      if (accId) {
        await api.patch(`/api/accounts/${accId}`, payload);
      } else {
        await api.post("/api/accounts", payload);
      }
      await api.patch("/api/business", {
        safety_buffer_paise: Math.max(0, rupeesToPaise(bufferRupees)),
      });
      onDone("Bank balance and safety floor saved — forecast updated.");
    } catch (e: any) {
      setErr(e?.message ?? "Could not save bank details");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1.2fr_.8fr]">
      <Panel title="1. Your bank account & cash floor"
             description="If you are not uploading past bank statements, enter today's actual bank balance as your opening balance.">
        <form onSubmit={save} className="space-y-4">
          {accounts.length > 1 && (
            <label className="block">
              <span className="label">Select account</span>
              <select className="field" value={accId} onChange={(e) => setAccId(e.target.value)}>
                {accounts.map((a) => (
                  <option key={a.account_id} value={a.account_id}>{a.name}</option>
                ))}
              </select>
            </label>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="label">Account label</span>
              <input className="field" value={accName} onChange={(e) => setAccName(e.target.value)} required />
            </label>
            <label className="block">
              <span className="label">Opening / current bank cash (₹)</span>
              <input className="field tnum" type="number" step="100" value={openingRupees}
                     onChange={(e) => setOpeningRupees(e.target.value)} required />
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="label">Overdraft / CC limit (₹)</span>
              <input className="field tnum" type="number" min={0} step="1000" value={odRupees}
                     onChange={(e) => setOdRupees(e.target.value)} />
            </label>
            <label className="block">
              <span className="label">Lien / FD-locked cash (₹)</span>
              <input className="field tnum" type="number" min={0} step="1000" value={restrictedRupees}
                     onChange={(e) => setRestrictedRupees(e.target.value)} />
            </label>
            <label className="block">
              <span className="label">Safety cash floor (₹)</span>
              <input className="field tnum" type="number" min={0} step="5000" value={bufferRupees}
                     onChange={(e) => setBufferRupees(e.target.value)} />
            </label>
          </div>
          {err && <p role="alert" className="text-xs font-semibold text-loss">{err}</p>}
          <div className="flex flex-wrap items-center gap-3 pt-1">
            <button type="submit" disabled={busy} className="btn btn-primary h-10 px-5 text-xs">
              {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
              Save cash & floor
            </button>
            <button type="button" onClick={onNext} className="btn btn-ghost h-10 px-5 text-xs">
              Next: Invoices & bills <ArrowRight className="size-3.5" />
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="Why these numbers matter" description="Plain-English meaning">
        <ul className="space-y-3 text-xs leading-relaxed text-ink-2">
          <li><strong>Bank cash vs available cash:</strong> Lien-marked FDs and upcoming GST/payroll commitments are kept separate from spendable cash.</li>
          <li><strong>Overdraft headroom:</strong> Reported separately as borrowing capacity, never disguised as cash in the bank.</li>
          <li><strong>Safety cash floor:</strong> Runway weeks and breach probability measure the risk of dropping below this minimum reserve.</li>
        </ul>
      </Panel>
    </div>
  );
}

/* ─────────────────────────── STEP 2: INVOICES & BILLS ─────────────────────────── */

function InvoicesStep({
  accountId, onDone, onNext,
}: {
  accountId: string;
  onDone: (msg: string) => void;
  onNext: () => void;
}) {
  const [kind, setKind] = useState<"sales" | "purchase">("sales");
  const [party, setParty] = useState("");
  const [invNo, setInvNo] = useState("");
  const [issueDate, setIssueDate] = useState(isoOffset(-15));
  const [dueDate, setDueDate] = useState(isoOffset(15));
  const [totalRupees, setTotalRupees] = useState("");
  const [paidRupees, setPaidRupees] = useState("");
  const [settledDate, setSettledDate] = useState("");
  const [msmeClass, setMsmeClass] = useState("none");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [adapter, setAdapter] = useState("invoices_csv");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [impBusy, setImpBusy] = useState(false);
  const [impErr, setImpErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function addInvoice(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const totalPaise = rupeesToPaise(totalRupees);
      const settledPaise = rupeesToPaise(paidRupees || "0");
      if (totalPaise <= 0) {
        setErr("Enter an invoice amount greater than zero.");
        setBusy(false);
        return;
      }
      await api.post("/api/invoices", {
        kind,
        counterparty_name: party,
        invoice_no: invNo,
        issue_date: issueDate,
        due_date: dueDate || undefined,
        total_paise: totalPaise,
        settled_paise: settledPaise,
        settled_date: settledDate || undefined,
        msme_class: kind === "purchase" && msmeClass !== "none" ? msmeClass : undefined,
      });
      setParty("");
      setInvNo("");
      setTotalRupees("");
      setPaidRupees("");
      setSettledDate("");
      onDone(`${kind === "sales" ? "Customer invoice" : "Supplier bill"} ${invNo} added to ledger.`);
    } catch (e: any) {
      setErr(e?.message ?? "Could not add invoice");
    } finally {
      setBusy(false);
    }
  }

  async function runImport(dry: boolean, f?: File) {
    const target = f ?? file;
    if (!target || !accountId) return;
    setImpBusy(true); setImpErr(null);
    try {
      const form = new FormData();
      form.set("adapter", adapter);
      form.set("account_id", accountId);
      form.set("dry_run", String(dry));
      form.set("file", target);
      const r = await api.upload<any>("/api/integrations/import", form);
      setPreview(r);
      if (!dry) {
        setFile(null);
        onDone(`Imported ${r.rows_imported} records from ${target.name}.`);
      }
    } catch (e: any) {
      setImpErr(e?.message ?? "Import failed");
    } finally {
      setImpBusy(false);
    }
  }

  async function tryTemplate(downloadOnly: boolean) {
    setImpErr(null);
    try {
      const s = await api.get<any>(`/api/integrations/sample/${adapter}`);
      if (s.binary || !s.content) {
        setImpErr([s.note, s.ocr_note].filter(Boolean).join(" "));
        return;
      }
      if (downloadOnly) {
        const blob = new Blob([s.content], { type: "text/csv;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url; a.download = s.filename; a.click();
        URL.revokeObjectURL(url);
        return;
      }
      const f = new File([s.content], s.filename, { type: "text/csv" });
      setFile(f);
      await runImport(true, f);
    } catch (e: any) {
      setImpErr(e?.message ?? "Could not load template");
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Add an invoice or supplier bill manually"
             description="Add open bills so RUNWAY knows what cash is coming in and going out. Add a few past paid invoices too so it learns buyer delays.">
        <form onSubmit={addInvoice} className="space-y-3.5">
          <div className="grid grid-cols-2 gap-2">
            {(["sales", "purchase"] as const).map((k) => (
              <button key={k} type="button" onClick={() => setKind(k)}
                className={cn("rounded-xl border px-3 py-2 text-xs font-semibold transition",
                  kind === k ? "border-forest bg-sage text-forest" : "border-line text-ink-2 hover:bg-paper-2")}>
                {k === "sales" ? "Customer invoice (Receivable)" : "Supplier bill (Payable)"}
              </button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="label">{kind === "sales" ? "Customer name" : "Supplier name"}</span>
              <input className="field" placeholder={kind === "sales" ? "Bharat Heavy Components" : "Kaveri Steel Mills"}
                     value={party} onChange={(e) => setParty(e.target.value)} required />
            </label>
            <label className="block">
              <span className="label">Invoice / bill #</span>
              <input className="field" placeholder={kind === "sales" ? "INV-1001" : "BILL-501"}
                     value={invNo} onChange={(e) => setInvNo(e.target.value)} required />
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <label className="block">
              <span className="label">Issue date</span>
              <input className="field" type="date" value={issueDate} onChange={(e) => setIssueDate(e.target.value)} required />
            </label>
            <label className="block">
              <span className="label">Due date</span>
              <input className="field" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} />
            </label>
            <label className="block">
              <span className="label">Total amount (₹)</span>
              <input className="field tnum" type="number" min={1} placeholder="150000"
                     value={totalRupees} onChange={(e) => setTotalRupees(e.target.value)} required />
            </label>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="label">Already paid (₹, optional)</span>
              <input className="field tnum" type="number" min={0} placeholder="0 if unpaid"
                     value={paidRupees} onChange={(e) => setPaidRupees(e.target.value)} />
            </label>
            {Number(paidRupees) > 0 ? (
              <label className="block">
                <span className="label">Date paid (optional)</span>
                <input className="field" type="date" value={settledDate} onChange={(e) => setSettledDate(e.target.value)} />
              </label>
            ) : kind === "purchase" ? (
              <label className="block">
                <span className="label">Supplier MSME status (43B(h))</span>
                <select className="field" value={msmeClass} onChange={(e) => setMsmeClass(e.target.value)}>
                  <option value="none">Not MSME / unknown</option>
                  <option value="micro">Micro enterprise (45-day rule)</option>
                  <option value="small">Small enterprise (45-day rule)</option>
                  <option value="medium">Medium enterprise</option>
                </select>
              </label>
            ) : (
              <div className="flex items-end pb-2 text-[11px] text-ink-3">
                GST is estimated at 18% inclusive unless imported separately.
              </div>
            )}
          </div>
          {err && <p role="alert" className="text-xs font-semibold text-loss">{err}</p>}
          <div className="flex flex-wrap gap-2 pt-1">
            <button type="submit" disabled={busy} className="btn btn-primary h-9 px-4 text-xs">
              {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
              Add to ledger
            </button>
            <button type="button" onClick={onNext} className="btn btn-ghost h-9 px-4 text-xs">
              Next: Monthly commitments <ArrowRight className="size-3.5" />
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="Or bulk upload CSV / GST JSON / Tally / PDF"
             description="Download our CSV template or upload any existing GSTR-1 JSON, Tally XML, or PDF invoice.">
        <div className="space-y-3">
          <div className="flex flex-wrap items-end gap-2">
            <label className="min-w-[200px] flex-1">
              <span className="label">File format</span>
              <select className="field" value={adapter} onChange={(e) => { setAdapter(e.target.value); setPreview(null); }}>
                <option value="invoices_csv">Invoices & bills CSV (recommended)</option>
                <option value="gst_invoice_json">GST register (GSTR-1 JSON / CSV)</option>
                <option value="pdf_invoice">PDF invoice (text or OCR)</option>
                <option value="tally_xml">TallyPrime Daybook XML</option>
              </select>
            </label>
            {adapter !== "pdf_invoice" && (
              <>
                <button type="button" onClick={() => tryTemplate(false)}
                        className="h-10 rounded-xl border border-line px-3 text-xs font-medium hover:bg-paper-2">
                  Preview sample
                </button>
                <button type="button" onClick={() => tryTemplate(true)}
                        className="inline-flex h-10 items-center gap-1.5 rounded-xl border border-line px-3 text-xs font-medium hover:bg-paper-2">
                  <Download className="size-3.5" /> Template
                </button>
              </>
            )}
          </div>

          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) { setFile(f); runImport(true, f); } }}
            className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-paper-2/50 px-4 py-6 text-center">
            <CloudUpload className="size-5 text-ink-3" />
            <p className="text-xs">
              {file ? file.name : "Drop a file here, or "}
              <button type="button" onClick={() => inputRef.current?.click()} className="font-semibold text-forest underline">
                browse computer
              </button>
            </p>
            <input ref={inputRef} type="file" className="sr-only"
                   onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); runImport(true, f); } }} />
          </div>

          {impErr && <p role="alert" className="text-xs font-semibold text-loss">{impErr}</p>}

          {preview && (
            <div className="space-y-2 rounded-xl border border-line bg-paper-2/40 p-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  Seen <strong>{preview.rows_seen}</strong> · Ready{" "}
                  <strong>{preview.preview?.filter((p: any) => p.kind !== "duplicate_rejected").length ?? 0}</strong> ·
                  Duplicates skipped <strong>{preview.duplicates_rejected ?? 0}</strong>
                  {preview.rows_rejected > 0 && <> · Rejected <strong>{preview.rows_rejected}</strong></>}
                </span>
                {preview.dry_run && (preview.preview?.length ?? 0) > 0 && (
                  <button type="button" disabled={impBusy} onClick={() => runImport(false)}
                          className="btn btn-primary h-8 px-3 text-xs">
                    {impBusy ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                    Confirm & import
                  </button>
                )}
              </div>
              {preview.errors?.length > 0 && (
                <p role="alert" className="text-xs font-semibold text-loss">
                  Row {preview.errors[0].row}: {preview.errors[0].error}
                </p>
              )}
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}

/* ─────────────────────────── STEP 3: OBLIGATIONS & LOANS ─────────────────────────── */

function ObligationsStep({
  upcoming, onDone, onNext,
}: {
  upcoming: any[];
  onDone: (msg: string) => void;
  onNext: () => void;
}) {
  const [kind, setKind] = useState("payroll");
  const [label, setLabel] = useState("Monthly staff & worker payroll");
  const [dueDate, setDueDate] = useState(isoOffset(10));
  const [amountRupees, setAmountRupees] = useState("");
  const [recurring, setRecurring] = useState(true);
  const [reserveCash, setReserveCash] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function addObligation(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const amt = rupeesToPaise(amountRupees);
      if (amt <= 0) {
        setErr("Enter an amount greater than zero.");
        setBusy(false);
        return;
      }
      await api.post("/api/obligations", {
        kind,
        label,
        due_date: dueDate,
        amount_paise: amt,
        is_recurring: recurring,
        recurrence: recurring ? "monthly" : null,
        reserve_cash: reserveCash,
      });
      setAmountRupees("");
      onDone(`Added '${label}' due ${dueDate}. Cash Runway & Compliance Calendar updated.`);
    } catch (e: any) {
      setErr(e?.message ?? "Could not add commitment");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Add fixed commitments (payroll, rent, GST, EMI)"
             description="Un-invoiced cash outflows that repeat every month or fall due soon.">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {OBLIGATION_PRESETS.map((p) => (
            <button key={p.kind} type="button"
              onClick={() => { setKind(p.kind); setLabel(p.label); setRecurring(p.recurring); }}
              className={cn("rounded-full border px-3 py-1 text-[11px] font-medium transition",
                kind === p.kind ? "border-forest bg-sage text-forest" : "border-line text-ink-2 hover:bg-paper-2")}>
              {titleCase(p.kind)}
            </button>
          ))}
        </div>

        <form onSubmit={addObligation} className="space-y-3.5">
          <label className="block">
            <span className="label">Commitment label</span>
            <input className="field" value={label} onChange={(e) => setLabel(e.target.value)} required />
          </label>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="label">Amount (₹)</span>
              <input className="field tnum" type="number" min={1} placeholder="180000"
                     value={amountRupees} onChange={(e) => setAmountRupees(e.target.value)} required />
            </label>
            <label className="block">
              <span className="label">Next due date</span>
              <input className="field" type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} required />
            </label>
          </div>
          <div className="flex flex-wrap gap-5 text-xs text-ink-2">
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={recurring} onChange={(e) => setRecurring(e.target.checked)} />
              Repeats monthly (projects across 13 weeks)
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={reserveCash} onChange={(e) => setReserveCash(e.target.checked)} />
              Ring-fence from spendable cash
            </label>
          </div>
          {err && <p role="alert" className="text-xs font-semibold text-loss">{err}</p>}
          <div className="flex flex-wrap gap-2 pt-1">
            <button type="submit" disabled={busy} className="btn btn-primary h-9 px-4 text-xs">
              {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
              Add commitment
            </button>
            <button type="button" onClick={onNext} className="btn btn-ghost h-9 px-4 text-xs">
              Next: Bank statements <ArrowRight className="size-3.5" />
            </button>
          </div>
        </form>
      </Panel>

      <Panel title="Commitments on file" description="Automatically checked against your cash runway & compliance calendar">
        {upcoming.length === 0 ? (
          <p className="py-8 text-center text-xs text-ink-3">No commitments added yet. Add payroll, rent or GST on the left.</p>
        ) : (
          <ul className="space-y-2">
            {upcoming.slice(0, 8).map((o: any) => (
              <li key={o.id} className="flex items-center justify-between gap-3 rounded-xl border border-line bg-paper-2/50 px-3 py-2 text-xs">
                <div>
                  <p className="font-semibold">{o.label}</p>
                  <p className="text-[11px] text-ink-3">Due {shortDate(o.due_date)} · {o.reserve_cash ? "cash ring-fenced" : "unreserved"}</p>
                </div>
                <span className="font-semibold tnum">{inr(o.amount_paise)}</span>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

/* ─────────────────────────── STEP 4: BANK STATEMENT / MANUAL TXN ─────────────────────────── */

function BankAndTransactionsStep({
  accounts, onDone,
}: {
  accounts: any[];
  onDone: (msg: string) => void;
}) {
  const [accountId, setAccountId] = useState(accounts[0]?.account_id ?? "");
  const [direction, setDirection] = useState<"credit" | "debit">("credit");
  const [dateVal, setDateVal] = useState(isoOffset(-1));
  const [amountRupees, setAmountRupees] = useState("");
  const [narration, setNarration] = useState("");
  const [party, setParty] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [impBusy, setImpBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  async function addTxn(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setErr(null);
    try {
      const amt = rupeesToPaise(amountRupees);
      if (amt <= 0) {
        setErr("Enter an amount greater than zero.");
        setBusy(false);
        return;
      }
      await api.post("/api/transactions", {
        account_id: accountId || undefined,
        value_date: dateVal,
        amount_paise: amt,
        direction,
        narration,
        counterparty_name: party || undefined,
      });
      setAmountRupees("");
      setNarration("");
      setParty("");
      onDone("Bank transaction recorded, auto-categorised and matched against open invoices.");
    } catch (e: any) {
      setErr(e?.message ?? "Could not record transaction");
    } finally {
      setBusy(false);
    }
  }

  async function runBankCsv(dry: boolean, f?: File) {
    const target = f ?? file;
    const acc = accountId || accounts[0]?.account_id;
    if (!target) return;
    if (!acc) {
      setErr("Create a bank account in Step 01 first.");
      return;
    }
    setImpBusy(true); setErr(null);
    try {
      const form = new FormData();
      form.set("adapter", "bank_csv");
      form.set("account_id", acc);
      form.set("dry_run", String(dry));
      form.set("file", target);
      const r = await api.upload<any>("/api/integrations/import", form);
      setPreview(r);
      if (!dry) {
        setFile(null);
        onDone(`Imported ${r.rows_imported} bank transactions (auto-matched ${r.auto_matched} to invoices).`);
      }
    } catch (e: any) {
      setErr(e?.message ?? "Bank CSV import failed");
    } finally {
      setImpBusy(false);
    }
  }

  async function downloadBankTemplate() {
    const s = await api.get<any>("/api/integrations/sample/bank_csv");
    if (s.content) {
      const blob = new Blob([s.content], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = s.filename; a.click();
      URL.revokeObjectURL(url);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title="Upload a bank statement CSV"
             description="HDFC, ICICI, SBI, Axis or any CSV with date, narration & debit/credit columns. Duplicates are rejected automatically.">
        <div className="space-y-3">
          {accounts.length > 0 && (
            <label className="block">
              <span className="label">Target bank account</span>
              <select className="field" value={accountId} onChange={(e) => setAccountId(e.target.value)}>
                {accounts.map((a) => <option key={a.account_id} value={a.account_id}>{a.name}</option>)}
              </select>
            </label>
          )}
          <div className="flex items-center gap-2">
            <button type="button" onClick={downloadBankTemplate}
                    className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-line px-3 text-xs font-medium hover:bg-paper-2">
              <Download className="size-3.5" /> Download sample bank CSV
            </button>
          </div>
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) { setFile(f); runBankCsv(true, f); } }}
            className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-line bg-paper-2/50 px-4 py-6 text-center">
            <FileSpreadsheet className="size-5 text-ink-3" />
            <p className="text-xs">
              {file ? file.name : "Drop your bank CSV here, or "}
              <button type="button" onClick={() => inputRef.current?.click()} className="font-semibold text-forest underline">
                browse file
              </button>
            </p>
            <input ref={inputRef} type="file" className="sr-only"
                   onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); runBankCsv(true, f); } }} />
          </div>
          {preview && (
            <div className="space-y-2 rounded-xl border border-line bg-paper-2/40 p-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span>
                  Seen <strong>{preview.rows_seen}</strong> · Ready{" "}
                  <strong>{preview.preview?.filter((p: any) => p.kind !== "duplicate_rejected").length ?? 0}</strong> ·
                  Duplicates rejected <strong>{preview.duplicates_rejected ?? 0}</strong>
                  {preview.rows_rejected > 0 && <> · Rejected <strong>{preview.rows_rejected}</strong></>}
                </span>
                {preview.dry_run && (preview.preview?.length ?? 0) > 0 && (
                  <button type="button" disabled={impBusy} onClick={() => runBankCsv(false)}
                          className="btn btn-primary h-8 px-3 text-xs">
                    {impBusy ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                    Confirm & import
                  </button>
                )}
              </div>
              {preview.errors?.length > 0 && (
                <p role="alert" className="text-xs font-semibold text-loss">
                  Row {preview.errors[0].row}: {preview.errors[0].error}
                </p>
              )}
            </div>
          )}
        </div>
      </Panel>

      <Panel title="Or record a single bank credit / debit"
             description="Matches against your open invoices automatically if narration or party matches.">
        <form onSubmit={addTxn} className="space-y-3.5">
          <div className="grid grid-cols-2 gap-2">
            {(["credit", "debit"] as const).map((d) => (
              <button key={d} type="button" onClick={() => setDirection(d)}
                className={cn("rounded-xl border px-3 py-2 text-xs font-semibold transition",
                  direction === d ? "border-forest bg-sage text-forest" : "border-line text-ink-2 hover:bg-paper-2")}>
                {d === "credit" ? "Money received (Credit)" : "Money paid (Debit)"}
              </button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="label">Date</span>
              <input className="field" type="date" value={dateVal} onChange={(e) => setDateVal(e.target.value)} required />
            </label>
            <label className="block">
              <span className="label">Amount (₹)</span>
              <input className="field tnum" type="number" min={1} placeholder="50000"
                     value={amountRupees} onChange={(e) => setAmountRupees(e.target.value)} required />
            </label>
          </div>
          <label className="block">
            <span className="label">Narration / description</span>
            <input className="field" placeholder="NEFT CR-BHARAT HEAVY-INV-1002"
                   value={narration} onChange={(e) => setNarration(e.target.value)} required />
          </label>
          <label className="block">
            <span className="label">Counterparty name (optional)</span>
            <input className="field" placeholder="Bharat Heavy Components"
                   value={party} onChange={(e) => setParty(e.target.value)} />
          </label>
          {err && <p role="alert" className="text-xs font-semibold text-loss">{err}</p>}
          <div className="flex flex-wrap gap-2 pt-1">
            <button type="submit" disabled={busy} className="btn btn-primary h-9 px-4 text-xs">
              {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
              Record transaction
            </button>
            <Link href="/app" className="btn btn-ghost h-9 px-4 text-xs">
              Finish & open dashboard <ArrowRight className="size-3.5" />
            </Link>
          </div>
        </form>
      </Panel>
    </div>
  );
}
