"use client";

import { useState } from "react";
import { ChevronDown, Gauge, Info } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { HealthGauge } from "@/components/runway/charts";
import {
  ErrorState, LoadingPanel, Panel, Provenance, SectionHeader, Stat, StateBadge,
} from "@/components/runway/primitives";
import { Details, Note, PageHeader } from "@/components/runway/page-kit";
import { useApi } from "@/lib/use-api";
import { inr, money, pct } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function HealthPage() {
  const { data, loading, error, reload } = useApi<any>("/api/health");
  const [open, setOpen] = useState<string | null>(null);
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (loading || !data) return <LoadingPanel rows={8} />;

  const subs = [...data.subscores].sort((a: any, b: any) => b.contribution - a.contribution);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Financial health"
        subtitle="A transparent indicator over eight dimensions. Every weight, threshold and input is visible." />

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Panel bodyClass="flex flex-col items-center p-6">
          <HealthGauge score={data.score} size={190} />
          <p className="mt-3 font-display text-xl font-semibold">{data.band}</p>
          <p className="mt-1 text-center text-xs text-muted-foreground text-pretty">
            Weighted mean of eight dimension scores, each on 0–100.
          </p>
          <div className="mt-4 w-full rounded-lg border border-fin-warn/30 bg-fin-warn-soft p-3">
            <p className="text-[11px] leading-relaxed text-fin-warn text-pretty">
              {data.methodology.disclaimer}
            </p>
          </div>
        </Panel>

        <div className="space-y-2">
          {subs.map((s: any, i: number) => (
            <motion.div key={s.key} className="rw-card overflow-hidden"
                        initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: Math.min(i * 0.04, 0.3) }}>
              <button onClick={() => setOpen(open === s.key ? null : s.key)}
                      aria-expanded={open === s.key}
                      className="flex w-full items-center gap-4 px-4 py-3 text-left hover:bg-surface-hover">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[13px] font-medium">{s.label}</span>
                    <span className="flex items-center gap-2.5">
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                        weight {pct(s.weight)}
                      </span>
                      <span className={cn("font-display text-base font-semibold tnum",
                        s.score >= 65 ? "text-fin-gain" : s.score >= 45 ? "text-fin-warn" : "text-fin-loss")}>
                        {s.score.toFixed(0)}
                      </span>
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface">
                    <motion.div className="h-full rounded-full"
                      initial={{ width: 0 }} animate={{ width: `${s.score}%` }}
                      transition={{ duration: 0.8, delay: 0.15 + i * 0.04, ease: [0.16, 1, 0.3, 1] }}
                      style={{ background: s.score >= 65 ? "var(--fin-gain)"
                                         : s.score >= 45 ? "var(--fin-warn)" : "var(--fin-loss)" }} />
                  </div>
                </div>
                <ChevronDown className={cn("size-4 shrink-0 text-muted-foreground transition-transform",
                  open === s.key && "rotate-180")} />
              </button>
              <AnimatePresence initial={false}>
                {open === s.key && (
                  <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
                              exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.22 }}
                              className="overflow-hidden border-t border-border bg-surface/40">
                    <ul className="space-y-1.5 p-4">
                      {s.evidence.map((e: string, j: number) => (
                        <li key={j} className="flex items-start gap-2 text-[12px] text-muted-foreground">
                          <span className="mt-1.5 size-1 shrink-0 rounded-full bg-muted-foreground" aria-hidden />
                          <span className="text-pretty">{e}</span>
                        </li>
                      ))}
                      <li className="pt-2 text-[11px] text-muted-foreground">
                        Contributes <strong className="text-foreground tnum">{s.contribution.toFixed(2)}</strong>{" "}
                        points to the overall score ({s.score.toFixed(0)} × {pct(s.weight)}).
                      </li>
                    </ul>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Working capital" description="Current assets against current liabilities">
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Working capital" value={money({ paise: data.working_capital.working_capital_paise } as any)
              || inr(data.working_capital.working_capital_paise)} />
            <Stat label="Current ratio" value={String(data.working_capital.current_ratio ?? "—")}
                  tone={(data.working_capital.current_ratio ?? 0) >= 1.5 ? "gain" : "warn"} />
          </div>
          <ul className="mt-4 space-y-1.5 text-[12px]">
            {Object.entries(data.working_capital.components).map(([k, v]) => (
              <li key={k} className="flex items-center justify-between border-b border-border/50 pb-1.5 last:border-0">
                <span className="capitalize text-muted-foreground">{k.replace(/_paise$/, "").replace(/_/g, " ")}</span>
                <span className="tnum">{inr(v as number)}</span>
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Methodology" description={data.methodology.shape}>
          <ul className="space-y-1.5 text-[12px]">
            {Object.entries(data.weights).map(([k, v]) => (
              <li key={k} className="flex items-center justify-between border-b border-border/50 pb-1.5 last:border-0">
                <span className="capitalize text-muted-foreground">{k.replace(/_/g, " ")}</span>
                <span className="tnum">{pct(v as number)}</span>
              </li>
            ))}
          </ul>
          <div className="mt-3">
            <Details label="How this is calculated">
              Scores are configurable per business and per industry. Changing a weight
            changes the score transparently rather than silently.
            </Details>
          </div>
        </Panel>
      </div>
    </div>
  );
}
