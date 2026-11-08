"use client";

import { use, useEffect, useState } from "react";
import { FileBarChart, Lock, Printer, ShieldAlert } from "lucide-react";
import { Logo } from "@/components/runway/shell";
import { LoadingPanel, Panel, Provenance } from "@/components/runway/primitives";
import { ReportValue, VerificationChip } from "@/components/runway/report-value";
import { longDate } from "@/lib/format";

/** Consented, unauthenticated view of a Cash Health Passport.
 *
 *  This is the only RUNWAY screen someone outside the business ever opens,
 *  and whoever opens it is usually deciding whether to extend credit. So it
 *  gets the same treatment as the authenticated screens: every figure
 *  formatted, every section carrying how it was arrived at, and the
 *  declarations impossible to miss. It also has to survive being printed,
 *  because that is what actually happens to a document sent to a bank.
 */
export default function SharedReport({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/public/shared/${token}`)
      .then(async (r) => {
        const b = await r.json();
        if (!r.ok) throw new Error(b.detail ?? "This link is not valid");
        setData(b);
      })
      .catch((e) => setError(e.message));
  }, [token]);

  return (
    <div className="min-h-dvh rw-noise">
      <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur-md print:static print:bg-transparent">
        <div className="mx-auto flex max-w-4xl items-center justify-between gap-3 px-5 py-4">
          <Logo />
          <div className="flex items-center gap-2">
            <span className="hidden items-center gap-1.5 text-[11px] text-muted-foreground sm:inline-flex">
              <Lock className="size-3" aria-hidden /> Shared financial report
            </span>
            {data && (
              <button
                onClick={() => window.print()}
                className="rounded-lg border border-border px-2.5 py-1.5 text-[11px] text-muted-foreground transition-colors hover:bg-surface-hover print:hidden"
              >
                <Printer className="mr-1 inline size-3" aria-hidden /> Print
              </button>
            )}
          </div>
        </div>
      </header>

      {/* rw-stage cascades the sections in, exactly as the app screens do */}
      <main className="rw-stage mx-auto max-w-4xl px-5 py-8">
        <div className="space-y-5">
          {error && (
            <div className="rw-card border-fin-loss/30 p-6 text-center">
              <ShieldAlert className="mx-auto size-6 text-fin-loss" aria-hidden />
              <p className="mt-3 font-medium">{error}</p>
              <p className="mt-1 text-sm text-muted-foreground">
                A business can revoke a shared report at any time.
              </p>
            </div>
          )}

          {!error && !data && <LoadingPanel rows={6} title="Opening the report…" />}

          {data && (
            <>
              {/* ── masthead ── */}
              <div className="rw-card relative overflow-hidden p-6">
                <span aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent" />
                <div className="flex items-start gap-3">
                  <FileBarChart className="mt-1 size-5 shrink-0 text-primary" aria-hidden />
                  <div className="min-w-0">
                    <h1 className="font-display text-2xl font-semibold tracking-tight text-balance">
                      {data.report.business.name}
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {data.report.report_type} · as of {longDate(data.report.as_of)}
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      Shared with {data.recipient} on {longDate(data.shared_at.slice(0, 10))}
                      {data.expires_at && ` · expires ${longDate(data.expires_at.slice(0, 10))}`}
                    </p>
                  </div>
                </div>
              </div>

              {/* ── the sections ── */}
              {data.report.sections.map((s: any) => (
                <Panel
                  key={s.key}
                  title={s.label}
                  description={s.basis}
                  actions={<VerificationChip kind={s.verification} />}
                  className="break-inside-avoid"
                >
                  <ReportValue value={s.value} />
                </Panel>
              ))}

              {/* ── what the business is on the record as saying ── */}
              <div className="rw-card border-fin-warn/30 bg-fin-warn-soft p-4 break-inside-avoid">
                <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-fin-warn">
                  Declarations
                </p>
                <ul className="space-y-1">
                  {data.report.declarations.map((d: string, i: number) => (
                    <li key={i} className="flex gap-2 text-[11px] leading-relaxed text-fin-warn text-pretty">
                      <span aria-hidden>·</span>
                      <span>{d}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <Provenance>{data.notice}</Provenance>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
