"use client";

import { useRef, useState } from "react";
import {
  AlertTriangle, Check, CloudUpload, FileSpreadsheet, Loader2, Plug, Upload, X,
} from "lucide-react";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, SectionHeader, Stat,
} from "@/components/runway/primitives";
import { api, session } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { inr, longDate, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

const STATUS_STYLE: Record<string, { cls: string; label: string }> = {
  available: { cls: "text-fin-gain bg-fin-gain-soft border-fin-gain/30", label: "Works today" },
  sandbox_required: { cls: "text-fin-warn bg-fin-warn-soft border-fin-warn/30", label: "Needs sandbox credentials" },
  partner_required: { cls: "text-fin-info bg-fin-info-soft border-fin-info/30", label: "Needs a partner agreement" },
  regulated_entity_required: { cls: "text-fin-loss bg-fin-loss-soft border-fin-loss/30", label: "Needs regulated-entity eligibility" },
  planned: { cls: "text-muted-foreground bg-surface border-border", label: "Planned" },
};

/** Renders the adapter's field mapping.
 *
 *  CSV adapters report a flat `column -> source column` map. The PDF
 *  adapter reports `{value, confidence, matched}` per field, because an
 *  extracted value and a mapped column carry very different amounts of
 *  trust and should not look the same on screen. */
function FieldMapping({ detected, mapping }: { detected: string; mapping: any }) {
  const entries = Object.entries(mapping).filter(([, v]) => v !== null && v !== "");
  const perField = entries.some(([, v]) => v && typeof v === "object" && "confidence" in (v as any));

  if (!perField) {
    return (
      <p className="mb-2 text-[11px] text-muted-foreground">
        Detected format <strong>{detected}</strong>. Columns mapped:{" "}
        {entries.map(([k, v]) => `${k} ← ${v}`).join(", ")}
      </p>
    );
  }
  return (
    <div className="mb-3">
      <p className="mb-1.5 text-[11px] text-muted-foreground">
        Read from the PDF by <strong>{mapping.extraction === "ocr" ? "OCR" : "its text layer"}</strong>.
        Each field carries its own confidence — anything uncertain is held for review.
      </p>
      <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
        {entries.filter(([k]) => k !== "extraction").map(([k, v]: any) => {
          const conf = v?.confidence ?? 0;
          const tone = conf >= 0.85 ? "text-fin-gain" : conf >= 0.7 ? "text-fin-warn" : "text-fin-loss";
          return (
            <div key={k} className="rounded-md border border-border bg-surface px-2.5 py-1.5">
              <div className="flex items-baseline justify-between gap-2">
                <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  {titleCase(k)}
                </span>
                <span className={cn("text-[10px] tnum", tone)}>{(conf * 100).toFixed(0)}%</span>
              </div>
              <p className="truncate text-[12px] tnum">
                {v?.value === null || v?.value === undefined ? "—" : String(v.value)}
              </p>
              {v?.matched && (
                <p className="truncate font-mono text-[9px] text-muted-foreground">{v.matched}</p>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function IntegrationsPage() {
  const cat = useApi<any>("/api/integrations");
  const accounts = useApi<any>("/api/integrations/accounts");
  const batches = useApi<any>("/api/integrations/batches");
  const [adapter, setAdapter] = useState("bank_csv");
  const [accountId, setAccountId] = useState("");
  const [preview, setPreview] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const acc = accountId || accounts.data?.accounts?.[0]?.id || "";

  async function run(dry: boolean, f?: File) {
    const target = f ?? file;
    if (!target || !acc) return;
    setBusy(true); setErr(null);
    try {
      const form = new FormData();
      form.set("adapter", adapter);
      form.set("account_id", acc);
      form.set("dry_run", String(dry));
      form.set("file", target);
      const r = await api.upload<any>("/api/integrations/import", form);
      setPreview(r);
      if (!dry) { batches.reload(); setFile(null); }
    } catch (e: any) { setErr(e?.message ?? "Import failed"); }
    finally { setBusy(false); }
  }

  async function loadSample() {
    setErr(null);
    const s = await api.get<any>(`/api/integrations/sample/${adapter}`);
    if (s.binary || !s.content) {
      // PDF has no pasteable sample; say what to do instead of failing.
      setErr([s.note, s.ocr_note].filter(Boolean).join(" "));
      return;
    }
    const f = new File([s.content], s.filename, { type: "text/plain" });
    setFile(f);
    run(true, f);
  }

  if (cat.error) return <ErrorState message={cat.error} onRetry={cat.reload} />;
  if (cat.loading || !cat.data) return <LoadingPanel rows={8} />;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Integrations"
        description="What connects today, and exactly what every other connector would need. Nothing here is described as live unless it is." />

      <div className="rw-surface flex items-start gap-3 p-3.5">
        <Plug className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
        <p className="text-xs leading-relaxed text-muted-foreground text-pretty">{cat.data.principle}</p>
      </div>

      {/* ── import ── */}
      <Panel title="Import financial data"
             description="Parsed, deduplicated, categorised and matched against open invoices — with a preview before anything is written.">
        <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto]">
          <label className="block">
            <span className="mb-1 block text-[11px] font-medium text-muted-foreground">Source</span>
            <select value={adapter} onChange={(e) => { setAdapter(e.target.value); setPreview(null); }}
                    className="h-9 w-full rounded-lg border border-border bg-surface px-2.5 text-sm outline-none">
              {cat.data.available.map((a: any) => (
                <option key={a.key} value={a.key}>{a.label}</option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-[11px] font-medium text-muted-foreground">Into account</span>
            <select value={acc} onChange={(e) => setAccountId(e.target.value)}
                    className="h-9 w-full rounded-lg border border-border bg-surface px-2.5 text-sm outline-none">
              {accounts.data?.accounts?.map((a: any) => (
                <option key={a.id} value={a.id}>{a.name}</option>
              ))}
            </select>
          </label>
          <button onClick={loadSample}
                  className="h-9 self-end rounded-lg border border-border px-3 text-xs hover:bg-surface-hover">
            {adapter === "pdf_invoice" ? "How to try this" : "Try a sample file"}
          </button>
        </div>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0];
                           if (f) { setFile(f); run(true, f); } }}
          className="mt-3 flex flex-col items-center gap-2 rounded-xl border border-dashed border-border bg-surface/40 px-4 py-8 text-center">
          <CloudUpload className="size-6 text-muted-foreground" aria-hidden />
          <p className="text-sm">
            {file ? file.name : "Drop a file here, or"}{" "}
            {!file && (
              <button onClick={() => inputRef.current?.click()} className="text-primary hover:underline">
                browse
              </button>
            )}
          </p>
          <p className="text-[11px] text-muted-foreground">
            {cat.data.available.find((a: any) => a.key === adapter)?.accepts?.join(", ")}
            {" · up to 12 MB · nothing is stored until you confirm"}
          </p>
          <input ref={inputRef} type="file" className="sr-only"
                 onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); run(true, f); } }} />
          {file && (
            <div className="mt-1 flex gap-2">
              <button onClick={() => run(true)} disabled={busy}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs hover:bg-surface-hover disabled:opacity-50">
                {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Upload className="size-3.5" />}
                Preview
              </button>
              <button onClick={() => setFile(null)}
                      className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-surface-hover">
                <X className="size-3.5" /> Clear
              </button>
            </div>
          )}
        </div>

        {err && (
          <p role="alert" className="mt-3 rounded-lg border border-fin-loss/30 bg-fin-loss-soft px-3 py-2 text-xs text-fin-loss">
            {err}
          </p>
        )}

        {preview && (
          <div className="mt-4 rounded-xl border border-border bg-surface/40 p-3.5">
            <div className="mb-3 grid gap-2 sm:grid-cols-5">
              <Stat label="Rows seen" value={preview.rows_seen} />
              <Stat label="Would import" value={preview.rows_imported || preview.preview.filter((p: any) => p.kind !== "duplicate_rejected").length} />
              <Stat label="Duplicates rejected" value={preview.duplicates_rejected}
                    tone={preview.duplicates_rejected ? "warn" : "neutral"} />
              <Stat label="Flagged for review" value={preview.duplicates_flagged} />
              <Stat label="Rejected rows" value={preview.rows_rejected}
                    tone={preview.rows_rejected ? "warn" : "neutral"} />
            </div>
            {preview.column_mapping && Object.keys(preview.column_mapping).length > 0 && (
              <FieldMapping detected={preview.detected_format}
                            mapping={preview.column_mapping} />
            )}
            <div className="max-h-64 overflow-auto rounded-lg border border-border">
              <table className="w-full text-[12px]">
                <thead className="sticky top-0 bg-surface">
                  <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                    <th className="px-2 py-1.5 font-medium">Date</th>
                    <th className="px-2 py-1.5 font-medium">Narration</th>
                    <th className="px-2 py-1.5 font-medium">Counterparty</th>
                    <th className="px-2 py-1.5 font-medium">Category</th>
                    <th className="px-2 py-1.5 text-right font-medium">Amount</th>
                    <th className="px-2 py-1.5 font-medium">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.preview.map((p: any, i: number) => (
                    <tr key={i} className={cn("border-b border-border/40 last:border-0",
                      p.kind === "duplicate_rejected" && "bg-fin-loss-soft/30",
                      p.needs_review && "bg-fin-warn-soft/30")}>
                      <td className="px-2 py-1 tnum">{p.date ?? "—"}</td>
                      <td className="max-w-xs truncate px-2 py-1">{p.narration ?? p.invoice_no}</td>
                      <td className="px-2 py-1">{p.counterparty ?? "—"}</td>
                      <td className="px-2 py-1">
                        {p.category ? titleCase(p.category) : p.kind}
                        {p.category_confidence !== undefined && (
                          <span className="ml-1 text-[10px] text-muted-foreground">
                            {(p.category_confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </td>
                      <td className="px-2 py-1 text-right tnum">{inr(p.amount_paise)}</td>
                      <td className="px-2 py-1 text-[10px] text-muted-foreground">
                        {p.reason || p.counterparty_reason || ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {preview.errors?.length > 0 && (
              <details className="mt-2">
                <summary className="cursor-pointer text-[11px] text-fin-warn">
                  {preview.errors.length} rows could not be read
                </summary>
                <ul className="mt-1 space-y-0.5">
                  {preview.errors.slice(0, 10).map((e: any, i: number) => (
                    <li key={i} className="text-[10px] text-muted-foreground">
                      Row {e.row}: {e.error}{e.value ? ` ("${e.value}")` : ""}
                    </li>
                  ))}
                </ul>
              </details>
            )}
            {preview.dry_run && (
              <div className="mt-3 flex items-center justify-between gap-3">
                <p className="text-[11px] text-muted-foreground">{preview.note}</p>
                <button onClick={() => run(false)} disabled={busy}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-50">
                  {busy ? <Loader2 className="size-3.5 animate-spin" /> : <Check className="size-3.5" />}
                  Confirm import
                </button>
              </div>
            )}
            {!preview.dry_run && (
              <p className="mt-3 rounded-lg border border-fin-gain/30 bg-fin-gain-soft px-3 py-2 text-xs text-fin-gain">
                Imported {preview.rows_imported} rows, {preview.auto_matched} matched to open
                invoices automatically. {preview.note}
              </p>
            )}
          </div>
        )}
      </Panel>

      {/* ── connector catalogue ── */}
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Working today" description="No credentials needed beyond a file you already have">
          <ul className="space-y-2.5">
            {cat.data.available.map((a: any) => (
              <li key={a.key} className="rounded-lg border border-border bg-surface p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium">{a.label}</p>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground text-pretty">
                      {a.description}
                    </p>
                  </div>
                  <span className={cn("rw-chip shrink-0", STATUS_STYLE.available.cls)}>
                    <Check className="size-3" /> live
                  </span>
                </div>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Declared, not claimed"
               description="These are built as adapters but are not connected. RUNWAY states exactly what each would require.">
          <ul className="space-y-2.5">
            {[...cat.data.requires_setup, ...cat.data.planned].map((a: any) => {
              const st = STATUS_STYLE[a.status] ?? STATUS_STYLE.planned;
              return (
                <li key={a.key} className="rounded-lg border border-border bg-surface p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[13px] font-medium">{a.label}</p>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground text-pretty">
                        {a.description}
                      </p>
                    </div>
                    <span className={cn("rw-chip shrink-0", st.cls)}>{st.label}</span>
                  </div>
                  {a.requirements?.length > 0 && (
                    <ul className="mt-2 space-y-0.5">
                      {a.requirements.map((r: string, i: number) => (
                        <li key={i} className="flex gap-1.5 text-[10px] text-muted-foreground">
                          <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden />
                          <span className="text-pretty">{r}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  {a.runway_support && (
                    <p className="mt-2 rounded border border-border bg-background/40 px-2 py-1.5 text-[10px] leading-relaxed text-muted-foreground text-pretty">
                      <strong className="text-foreground">What exists today: </strong>{a.runway_support}
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        </Panel>
      </div>

      <ImportHistory batches={batches.data?.batches ?? []} />
    </div>
  );
}


/* Every upload is kept - the ledger only ever grows, like a bank passbook -
   and each one records the headline figures just before and just after it,
   so any past upload can be opened and compared with today. */
function ImportHistory({ batches }: { batches: any[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);

  async function toggle(id: string) {
    if (open === id) { setOpen(null); return; }
    setOpen(id); setDetail(null);
    try { setDetail(await api.get<any>(`/api/integrations/batches/${id}?limit=50`)); }
    catch { setDetail({ error: true }); }
  }

  const fmt = (c: any, v: any) =>
    v === null || v === undefined ? "—"
      : c.unit === "paise" ? inr(v, { compact: true })
      : c.unit === "probability" ? `${(v * 100).toFixed(1)}%`
      : c.unit === "weeks" ? `${Number(v).toFixed(2)} wk`
      : Number(v).toLocaleString("en-IN");
  const delta = (c: any) => {
    if (c.change === null || c.change === undefined || c.change === 0) return "no change";
    const sign = c.change > 0 ? "+" : "−";
    const abs = Math.abs(c.change);
    return sign + (c.unit === "paise" ? inr(abs, { compact: true })
      : c.unit === "probability" ? `${(abs * 100).toFixed(1)} pts`
      : c.unit === "weeks" ? `${abs.toFixed(2)} wk` : abs.toLocaleString("en-IN"));
  };

  return (
    <Panel title="Import history"
           description="Every upload stays on record. Open one to see the rows it added and what it changed.">
      {batches.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                <th className="pb-2 font-medium">When</th>
                <th className="pb-2 font-medium">Source</th>
                <th className="pb-2 font-medium">File</th>
                <th className="pb-2 text-right font-medium">Imported</th>
                <th className="pb-2 text-right font-medium">Duplicates</th>
                <th className="pb-2 text-right font-medium">Cash change</th>
                <th className="pb-2" />
              </tr>
            </thead>
            <tbody>
              {batches.map((b: any) => {
                const cash = b.impact?.changes?.find((c: any) => c.key === "cash_in_hand_paise");
                return [
                  <tr key={b.id} className="border-b border-border/50">
                    <td className="py-2 tnum text-[12px]">{longDate(b.created_at.slice(0, 10))}</td>
                    <td className="py-2 text-[12px]">{b.adapter}</td>
                    <td className="max-w-[220px] truncate py-2 text-[12px] text-muted-foreground">{b.filename}</td>
                    <td className="py-2 text-right tnum">{b.rows_imported}</td>
                    <td className="py-2 text-right tnum">{b.rows_duplicate}</td>
                    <td className="py-2 text-right tnum text-[12px]">{cash ? delta(cash) : "—"}</td>
                    <td className="py-2 text-right">
                      <button className="btn btn-ghost btn-sm" onClick={() => toggle(b.id)}
                              aria-expanded={open === b.id}>
                        {open === b.id ? "Hide" : "Open"}
                      </button>
                    </td>
                  </tr>,
                  open === b.id && (
                    <tr key={b.id + "-d"} className="border-b border-border/50 bg-paper-2/40">
                      <td colSpan={7} className="px-3 py-4">
                        {!detail ? <p className="text-[12px] text-muted-foreground">Loading…</p>
                         : detail.error ? <p className="text-[12px] text-loss">Could not load this import.</p>
                         : (
                          <div className="grid gap-4 lg:grid-cols-2">
                            <div>
                              <p className="text-[12px] font-semibold">
                                What this upload changed{detail.impact ? ` (as of ${longDate(detail.impact.as_of)})` : ""}
                              </p>
                              {detail.impact?.changes?.length ? (
                                <table className="mt-2 w-full text-[12px]">
                                  <thead><tr className="text-left text-muted-foreground">
                                    <th className="font-medium">Figure</th>
                                    <th className="text-right font-medium">Before</th>
                                    <th className="text-right font-medium">After</th>
                                    <th className="text-right font-medium">Change</th></tr></thead>
                                  <tbody>
                                    {detail.impact.changes.map((c: any) => (
                                      <tr key={c.key} className="border-t border-border/40">
                                        <td className="py-1">{c.label}</td>
                                        <td className="py-1 text-right tnum">{fmt(c, c.before)}</td>
                                        <td className="py-1 text-right tnum">{fmt(c, c.after)}</td>
                                        <td className="py-1 text-right tnum">{delta(c)}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              ) : (
                                <p className="mt-2 text-[12px] text-muted-foreground">
                                  This upload was made before impact tracking existed, or the
                                  workspace was empty before it.
                                </p>
                              )}
                            </div>
                            <div>
                              <p className="text-[12px] font-semibold">
                                Rows added ({detail.transactions_total})
                                {detail.date_range ? ` · ${detail.date_range[0]} → ${detail.date_range[1]}` : ""}
                              </p>
                              <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto text-[12px]">
                                {detail.transactions.map((t: any) => (
                                  <li key={t.id} className="flex justify-between gap-3 border-t border-border/40 py-1">
                                    <span className="tnum text-muted-foreground">{t.date}</span>
                                    <span className="min-w-0 flex-1 truncate">{t.narration}</span>
                                    <span className={cn("tnum", t.direction === "credit" ? "text-fin-gain" : "")}>
                                      {t.direction === "credit" ? "+" : "−"}{t.amount.display}
                                    </span>
                                  </li>
                                ))}
                              </ul>
                              <a href={`/app/transactions?import_batch_id=${b.id}`}
                                 className="mt-2 inline-block text-[12px] font-semibold text-primary hover:underline">
                                See all rows from this upload →
                              </a>
                            </div>
                          </div>
                        )}
                      </td>
                    </tr>
                  ),
                ];
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="py-6 text-center text-sm text-muted-foreground">
          No imports yet. The demo workspace was generated, not imported.
        </p>
      )}
    </Panel>
  );
}
