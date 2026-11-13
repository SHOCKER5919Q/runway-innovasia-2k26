"use client";

import { useState } from "react";
import { Check, ChevronDown, Lightbulb, Loader2, ShieldCheck, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, SectionHeader,
} from "@/components/runway/primitives";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { inr, money, pct, shortDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function RecommendationsPage() {
  const { data, loading, error, reload } = useApi<any>("/api/recommendations");
  const [open, setOpen] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  async function setStatus(code: string, status: string) {
    setBusy(code);
    try { await api.post(`/api/recommendations/${code}/status`, { status }); reload(); }
    finally { setBusy(null); }
  }

  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={6} />;

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Recommendations"
        description="Deterministic rules over your ledger, ranked by a published score. No language model decides what you should do." />

      <div className="rw-surface flex items-start gap-3 p-3.5">
        <ShieldCheck className="mt-0.5 size-4 shrink-0 text-fin-gain" aria-hidden />
        <p className="text-xs leading-relaxed text-muted-foreground text-pretty">{data.guarantee}</p>
      </div>

      {data.approved_plan && (
        <div className="rw-card grid gap-4 p-5 sm:grid-cols-[1fr_auto_1fr_auto_1fr] sm:items-center">
          <div>
            <p className="text-[12px] text-muted-foreground">Available cash now</p>
            <p className="mt-1 font-display text-2xl font-semibold tnum">{data.approved_plan.available_now.display}</p>
            <p className="text-[11px] text-muted-foreground">recorded</p>
          </div>
          <span className="hidden text-xl text-muted-foreground sm:block">+</span>
          <div>
            <p className="text-[12px] text-muted-foreground">
              {data.approved_plan.approved} approved action{data.approved_plan.approved === 1 ? "" : "s"}
            </p>
            <p className="mt-1 font-display text-2xl font-semibold tnum text-fin-gain">
              {data.approved_plan.expected_lift.display}
            </p>
            <p className="text-[11px] text-muted-foreground">expected effect</p>
          </div>
          <span className="hidden text-xl text-muted-foreground sm:block">=</span>
          <div>
            <p className="text-[12px] text-muted-foreground">If you complete them</p>
            <p className="mt-1 font-display text-2xl font-semibold tnum">
              {data.approved_plan.available_if_done.display}
            </p>
            <p className="text-[11px] text-muted-foreground">{data.approved_plan.note}</p>
          </div>
        </div>
      )}

      <div className="space-y-3">
        {data.recommendations.map((r: any, idx: number) => (
          <motion.article key={r.code} className="rw-card overflow-hidden"
                          initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                          transition={{ delay: Math.min(idx * 0.04, 0.3) }}>
            <div className="flex items-start gap-4 p-4">
              <div className="flex shrink-0 flex-col items-center gap-1">
                <span className="grid size-11 place-items-center rounded-lg border border-primary/30 bg-primary-soft font-display text-sm font-semibold text-primary tnum">
                  {r.priority}
                </span>
                <span className="text-[9px] uppercase tracking-wider text-muted-foreground">rank</span>
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-[15px] font-medium text-pretty">{r.title}</h3>
                  {r.tags?.map((t: string) => (
                    <span key={t} className="rw-chip border-border bg-surface text-muted-foreground">
                      {t.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
                <p className="mt-1.5 text-[13px] leading-relaxed text-muted-foreground text-pretty">
                  {r.expected_effect_text}
                </p>
                <p className="mt-2 text-[13px] leading-relaxed text-pretty">
                  <span className="font-medium">Action: </span>{r.action}
                </p>
                <div className="mt-2.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                  {r.expected_effect?.paise ? (
                    <span>Effect <span className="tnum text-foreground">{r.expected_effect.display}</span></span>
                  ) : null}
                  <span>Confidence <span className="tnum text-foreground">{pct(r.confidence)}</span></span>
                  {r.deadline && <span>By <span className="text-foreground">{shortDate(r.deadline)}</span></span>}
                  {r.requires_approval && (
                    <span className="rw-chip border-border bg-surface">needs your approval</span>
                  )}
                </div>
              </div>

              <div className="flex shrink-0 flex-col gap-1.5">
                {r.status && r.status !== "open" ? (
                  <>
                    <span className={cn("rw-chip justify-center capitalize",
                      r.status === "accepted" ? "border-fin-gain/30 bg-fin-gain-soft text-fin-gain"
                        : r.status === "done" ? "border-fin-gain/30 bg-fin-gain-soft text-fin-gain"
                        : "border-border bg-surface text-muted-foreground")}>
                      <Check className="size-3" /> {r.status === "accepted" ? "Approved - in progress" : r.status}
                    </span>
                    {r.status === "accepted" && (
                      <button onClick={() => setStatus(r.code, "done")} disabled={busy === r.code}
                              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-fin-gain/30 px-2.5 py-1.5 text-[11px] text-fin-gain hover:bg-fin-gain-soft">
                        Mark done
                      </button>
                    )}
                    <button onClick={() => setStatus(r.code, "open")} disabled={busy === r.code}
                            className="inline-flex items-center justify-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[11px] text-muted-foreground hover:bg-surface-hover">
                      Undo
                    </button>
                  </>
                ) : (<>
                <button onClick={() => setStatus(r.code, "accepted")} disabled={busy === r.code}
                        className="inline-flex items-center gap-1.5 rounded-md border border-fin-gain/30 bg-fin-gain-soft px-2.5 py-1.5 text-[11px] text-fin-gain hover:opacity-85 disabled:opacity-50">
                  {busy === r.code ? <Loader2 className="size-3 animate-spin" /> : <Check className="size-3" />}
                  Accept
                </button>
                <button onClick={() => setStatus(r.code, "dismissed")} disabled={busy === r.code}
                        className="inline-flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-[11px] text-muted-foreground hover:bg-surface-hover disabled:opacity-50">
                  <X className="size-3" /> Dismiss
                </button>
                </>)}
                <button onClick={() => setOpen(open === r.code ? null : r.code)}
                        aria-expanded={open === r.code}
                        className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-[11px] text-primary hover:bg-surface-hover">
                  Evidence
                  <ChevronDown className={cn("size-3 transition-transform", open === r.code && "rotate-180")} />
                </button>
              </div>
            </div>

            <AnimatePresence initial={false}>
              {open === r.code && (
                <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22 }}
                            className="overflow-hidden border-t border-border bg-surface/40">
                  <div className="grid gap-5 p-4 lg:grid-cols-2">
                    <div>
                      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Triggering evidence
                      </p>
                      <Evidence items={r.evidence} dense />
                    </div>
                    <div className="space-y-3">
                      <div>
                        <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                          Why this ranks where it does
                        </p>
                        <div className="space-y-1">
                          {["urgency", "impact", "confidence", "ease", "reversibility"].map((t) => (
                            <div key={t} className="flex items-center gap-2 text-[11px]">
                              <span className="w-24 shrink-0 capitalize text-muted-foreground">{t}</span>
                              <span className="h-1 flex-1 overflow-hidden rounded-full bg-surface">
                                <span className="block h-full rounded-full bg-primary"
                                      style={{ width: `${(r.score_terms?.[t] ?? 0) * 100}%` }} />
                              </span>
                              <span className="w-9 shrink-0 text-right tnum">
                                {((r.score_terms?.[t] ?? 0) as number).toFixed(2)}
                              </span>
                            </div>
                          ))}
                        </div>
                        <p className="mt-1.5 font-mono text-[10px] text-muted-foreground">
                          {r.score_terms?.formula}
                        </p>
                      </div>
                      <div>
                        <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                          Downside
                        </p>
                        <p className="text-[12px] leading-relaxed text-pretty">{r.downside}</p>
                      </div>
                      <div>
                        <p className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                          How this was computed
                        </p>
                        <p className="text-[12px] leading-relaxed text-muted-foreground text-pretty">
                          {r.explanation}
                        </p>
                      </div>
                    </div>
                  </div>

                  {r.score_terms?.funding_options && (
                    <div className="border-t border-border p-4">
                      <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                        Funding options, cheapest first
                      </p>
                      <div className="overflow-x-auto">
                        <table className="w-full text-[12px]">
                          <thead>
                            <tr className="border-b border-border text-left text-[10px] uppercase tracking-wider text-muted-foreground">
                              <th className="pb-1.5 font-medium">Option</th>
                              <th className="pb-1.5 text-right font-medium">Liquidity</th>
                              <th className="pb-1.5 text-right font-medium">Cost</th>
                              <th className="pb-1.5 text-right font-medium">Speed</th>
                              <th className="pb-1.5 text-right font-medium">Covers gap</th>
                            </tr>
                          </thead>
                          <tbody>
                            {r.score_terms.funding_options.map((o: any) => (
                              <tr key={o.option} className="border-b border-border/50 last:border-0">
                                <td className="py-1.5">
                                  <p>{o.option}</p>
                                  <p className="text-[10px] text-muted-foreground text-pretty">{o.cost_note}</p>
                                </td>
                                <td className="py-1.5 text-right tnum">{inr(o.liquidity_paise, { compact: true })}</td>
                                <td className="py-1.5 text-right tnum">{inr(o.cost_paise, { compact: true })}</td>
                                <td className="py-1.5 text-right tnum text-muted-foreground">{o.speed_days}d</td>
                                <td className="py-1.5 text-right">
                                  {o.covers_gap
                                    ? <span className="text-fin-gain">yes</span>
                                    : <span className="text-muted-foreground">partly</span>}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.article>
        ))}
      </div>

      <Panel title="How ranking works" description={data.ranking.method}>
        <Evidence items={Object.entries(data.ranking.terms).map(([k, v]) => ({
          label: k, value: v as string,
        }))} dense />
      </Panel>
    </div>
  );
}
