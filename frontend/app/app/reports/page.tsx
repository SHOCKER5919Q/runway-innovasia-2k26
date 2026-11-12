"use client";

import { useState } from "react";
import {
  Check, Copy, Download, FileBarChart, Link2, Loader2, ShieldCheck, Trash2,
} from "lucide-react";
import {
  ErrorState, LoadingPanel, Panel, StateBadge,
} from "@/components/runway/primitives";
import { Button, CopyButton, Details, ExportButton, Note, PageHeader, Tabs, useTabs }
  from "@/components/runway/page-kit";
import { api } from "@/lib/api";
import { useApi, useMutation } from "@/lib/use-api";
import { inr, longDate, pct, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

const VERIFY_STYLE: Record<string, string> = {
  verified_actual: "text-fin-gain bg-fin-gain-soft border-fin-gain/25",
  derived_from_verified_ledger: "text-fin-info bg-fin-info-soft border-fin-info/25",
  measured: "text-fin-info bg-fin-info-soft border-fin-info/25",
  mixed_verified_and_estimated: "text-fin-warn bg-fin-warn-soft border-fin-warn/25",
  model_prediction: "text-primary bg-primary-soft border-primary/25",
  derived_indicator: "text-primary bg-primary-soft border-primary/25",
};

export default function ReportsPage() {
  const passport = useApi<any>("/api/reports/passport");
  const shares = useApi<any>("/api/reports/shared");
  const [recipient, setRecipient] = useState("");
  const [days, setDays] = useState(30);
  const [issued, setIssued] = useState<any>(null);
  const [tab, setTab] = useTabs("reports", "passport");

  const share = useMutation<void, any>(async () => {
    const r = await api.post<any>("/api/reports/passport/share",
      { recipient, expires_in_days: days });
    setIssued(r); shares.reload(); return r;
  });

  function download() {
    const blob = new Blob([JSON.stringify(passport.data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `runway-cash-health-passport-${passport.data.as_of}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (passport.error) return <ErrorState message={passport.error} onRetry={passport.reload} />;
  if (passport.loading || !passport.data) return <LoadingPanel rows={8} />;
  const p = passport.data;

  return (
    <div className="space-y-5">
      <PageHeader
        title="Reports"
        subtitle="Your Cash Health Passport, assembled from your ledger and shared only when you choose."
        actions={<>
          <ExportButton path="/api/exports/passport.csv"
                        filename="runway-passport.csv" label="Export CSV" />
          <Button icon={<Download className="size-3.5" />} onClick={download}>JSON</Button>
        </>} />

      <Tabs active={tab} onChange={setTab} tabs={[
        { key: "passport", label: "Passport" },
        { key: "sharing", label: "Sharing" },
      ]} />

      {tab !== "passport" ? <Sharing shares={shares} recipient={recipient}
        setRecipient={setRecipient} days={days} setDays={setDays}
        share={share} issued={issued} /> : (
      <>
      <Panel title={p.report_type}
             description={`${p.business.name} · as of ${longDate(p.as_of)} · version ${p.version}`}
             actions={<span className="rw-chip border-border bg-surface text-muted-foreground">
               engine {p.state_refs.engine_version}
             </span>}>
        <div className="space-y-3">
          {p.sections.map((s: any) => (
            <section key={s.key} className="rounded-lg border border-border bg-surface/50 p-3.5">
              <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-[13px] font-medium">{s.label}</h3>
                <span className={cn("rw-chip", VERIFY_STYLE[s.verification] ?? "border-border bg-surface text-muted-foreground")}>
                  {titleCase(s.verification)}
                </span>
              </div>
              <SectionValue value={s.value} />
              <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground text-pretty">
                {s.basis}
              </p>
            </section>
          ))}
        </div>

        <div className="mt-4 space-y-2 rounded-lg border border-fin-warn/30 bg-fin-warn-soft p-3.5">
          {p.declarations.map((d: string, i: number) => (
            <p key={i} className="text-[11px] leading-relaxed text-fin-warn text-pretty">· {d}</p>
          ))}
        </div>
      </Panel>
      </>
      )}
    </div>
  );
}

function Sharing({ shares, recipient, setRecipient, days, setDays, share, issued }: any) {
  return (
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Share with a lender, NBFC or accountant"
               description="Issues a revocable, expiring link under an explicit consent record.">
          <div className="space-y-3">
            <label className="block">
              <span className="mb-1 block text-[11px] font-medium text-muted-foreground">Recipient</span>
              <input value={recipient} onChange={(e) => setRecipient(e.target.value)}
                     placeholder="e.g. HDFC Bank — MSME lending desk"
                     className="h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none focus:border-primary/60" />
            </label>
            <label className="block">
              <span className="mb-1 flex items-baseline justify-between text-[11px]">
                <span className="font-medium text-muted-foreground">Link expires in</span>
                <span className="tnum">{days} days</span>
              </span>
              <input type="range" min={1} max={180} value={days}
                     onChange={(e) => setDays(Number(e.target.value))}
                     className="w-full accent-[var(--primary)]" />
            </label>
            <button onClick={() => share.run()} disabled={!recipient.trim() || share.pending}
                    className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-primary text-xs font-medium text-primary-foreground disabled:opacity-50">
              {share.pending ? <Loader2 className="size-3.5 animate-spin" /> : <Link2 className="size-3.5" />}
              Issue a consented link
            </button>
            {share.error && (
              <p role="alert" className="text-[11px] text-fin-loss">{share.error}</p>
            )}
            {issued && (
              <div className="rounded-lg border border-fin-gain/30 bg-fin-gain-soft p-3">
                <p className="text-[11px] text-fin-gain">Link issued for {issued.recipient}</p>
                <div className="mt-1.5 flex items-center gap-2">
                  <code className="min-w-0 flex-1 truncate rounded bg-background/50 px-2 py-1 font-mono text-[10px]">
                    {typeof window !== "undefined" ? window.location.origin : ""}/shared/{issued.token}
                  </code>
                  <CopyButton text={`${window.location.origin}/shared/${issued.token}`}
                              size="sm" className="border border-border" />
                </div>
                <p className="mt-1.5 text-[10px] text-muted-foreground">{issued.note}</p>
              </div>
            )}
          </div>
          <div className="mt-3">
            <Details label="What happens when you share">
              Sharing creates a consent record with a purpose, a grantee and an
              expiry. Revoking it disables the link immediately. RUNWAY never
              sells or syndicates this data.
            </Details>
          </div>
        </Panel>

        <Panel title="Issued links" description="Everyone who currently has access">
          {shares.data?.shares?.length ? (
            <ul className="space-y-2">
              {shares.data.shares.map((s: any) => (
                <li key={s.id} className="flex items-start justify-between gap-3 rounded-lg border border-border bg-surface p-2.5">
                  <div className="min-w-0">
                    <p className="truncate text-[12px] font-medium">{s.recipient}</p>
                    <p className="mt-0.5 text-[10px] text-muted-foreground">
                      Issued {longDate(s.created_at.slice(0, 10))}
                      {s.expires_at && ` · expires ${longDate(s.expires_at.slice(0, 10))}`}
                      {" · "}{s.view_count} view{s.view_count === 1 ? "" : "s"}
                    </p>
                  </div>
                  {s.active ? (
                    <button onClick={async () => {
                              await api.post(`/api/reports/shared/${s.id}/revoke`); shares.reload();
                            }}
                            className="inline-flex shrink-0 items-center gap-1 rounded-md border border-fin-loss/30 px-2 py-1 text-[10px] text-fin-loss hover:bg-fin-loss-soft">
                      <Trash2 className="size-3" /> Revoke
                    </button>
                  ) : (
                    <span className="shrink-0 text-[10px] text-muted-foreground">revoked</span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">
              No links issued. Nobody outside this workspace can see your figures.
            </p>
          )}
        </Panel>
      </div>
  );
}

function SectionValue({ value }: { value: any }) {
  if (value === null || value === undefined) return <p className="text-sm text-muted-foreground">—</p>;
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return <p className="text-[12px] text-muted-foreground">
        Nothing measured yet. RUNWAY leaves this empty rather than quoting a figure it has not computed.
      </p>;
    }
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-[12px]">
          <thead>
            <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
              {Object.keys(value[0]).map((k) => (
                <th key={k} className="pb-1 pr-3 font-medium">{titleCase(k)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {value.slice(0, 8).map((row: any, i: number) => (
              <tr key={i} className="border-b border-border/40 last:border-0">
                {Object.entries(row).map(([k, v]) => (
                  <td key={k} className="py-1 pr-3 tnum">{fmt(k, v)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }
  if (typeof value === "object") {
    return (
      <dl className="grid gap-x-6 gap-y-1 sm:grid-cols-2">
        {Object.entries(value).filter(([k]) => !Array.isArray((value as any)[k]))
          .map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-3 border-b border-border/40 pb-1 text-[12px]">
              <dt className="text-muted-foreground">{titleCase(k)}</dt>
              <dd className="tnum">{fmt(k, v)}</dd>
            </div>
          ))}
      </dl>
    );
  }
  return <p className="text-sm tnum">{String(value)}</p>;
}

function fmt(k: string, v: any): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "object" && "display" in v) return (v as any).display;
  if (typeof v === "number") {
    if (/share|ratio|probability|coverage|wape/.test(k)) return pct(v, 1);
    if (/paise/.test(k)) return inr(v);
    return String(Number.isInteger(v) ? v : v.toFixed(2));
  }
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}