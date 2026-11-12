"use client";

import { useEffect, useState } from "react";
import { Check, Loader2, RefreshCw, Save, Shuffle, SlidersHorizontal } from "lucide-react";
import {
  ErrorState, Evidence, LoadingPanel, Panel, Provenance, SectionHeader, Stat,
} from "@/components/runway/primitives";
import { api, session } from "@/lib/api";
import { useApi, useMutation } from "@/lib/use-api";
import { inr, pct } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Details } from "@/components/runway/page-kit";

export default function SettingsPage() {
  const biz = useApi<any>("/api/business");
  const scenarios = useApi<any>("/api/demo/scenarios");
  const meta = useApi<any>("/api/meta");
  const [form, setForm] = useState<any>(null);
  const [saved, setSaved] = useState(false);
  const [asOf, setAsOf] = useState<string>("");

  useEffect(() => {
    if (!biz.data) return;
    setForm({
      safety_buffer_paise: biz.data.policies.safety_buffer.paise,
      target_runway_weeks: biz.data.policies.target_runway_weeks,
      max_customer_concentration: biz.data.policies.max_customer_concentration,
      max_borrowing_apr: biz.data.policies.max_borrowing_apr,
      min_order_margin: biz.data.policies.min_order_margin,
      risk_appetite: biz.data.policies.risk_appetite,
    });
  }, [biz.data]);

  useEffect(() => { setAsOf(session.asOf ?? ""); }, []);

  const save = useMutation<void, any>(async () => {
    const r = await api.patch("/api/business", form);
    biz.reload();
    setSaved(true); setTimeout(() => setSaved(false), 2200);
    return r;
  });

  const switchScenario = useMutation<string, any>(async (key) => {
    const r = await api.post<any>("/api/demo/switch", { scenario: key, as_of: asOf || undefined });
    if (r.businesses?.[0]?.id) session.setBusiness(r.businesses[0].id);
    window.location.href = "/app";
    return r;
  });

  const refresh = useMutation<void, any>(async () => {
    const r = await api.post("/api/twin/refresh");
    window.location.reload();
    return r;
  });

  if (biz.error) return <ErrorState message={biz.error} onRetry={biz.reload} />;
  if (biz.loading || !biz.data || !form) return <LoadingPanel rows={8} />;

  return (
    <div className="space-y-5">
      <SectionHeader title="Settings"
        description="Policies drive the engine directly — changing one changes the forecast, the alerts and the decision optimiser." />

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel title="Financial policy"
               description="These are hard constraints in the decision optimiser, not preferences.">
          <div className="space-y-4">
            <Field label="Safety buffer"
                   hint="The cash floor you never want to cross. Drives the breach probability and the runway definition."
                   value={inr(form.safety_buffer_paise)}>
              <input type="number" min={0} step={10000}
                     value={Math.round(form.safety_buffer_paise / 100)}
                     onChange={(e) => setForm({ ...form, safety_buffer_paise: Number(e.target.value) * 100 })}
                     className="h-9 w-full rounded-lg border border-border bg-surface px-3 text-sm tnum outline-none focus:border-primary/60" />
            </Field>
            <Field label="Target runway" hint="Used by the liquidity health dimension."
                   value={`${form.target_runway_weeks} weeks`}>
              <input type="range" min={2} max={26} step={1} value={form.target_runway_weeks}
                     onChange={(e) => setForm({ ...form, target_runway_weeks: Number(e.target.value) })}
                     className="w-full accent-[var(--primary)]" />
            </Field>
            <Field label="Maximum customer concentration"
                   hint="Above this share of revenue from one buyer, RUNWAY raises a concentration alert."
                   value={pct(form.max_customer_concentration)}>
              <input type="range" min={10} max={90} step={1}
                     value={Math.round(form.max_customer_concentration * 100)}
                     onChange={(e) => setForm({ ...form, max_customer_concentration: Number(e.target.value) / 100 })}
                     className="w-full accent-[var(--primary)]" />
            </Field>
            <Field label="Maximum borrowing cost"
                   hint="Financing above this annualised rate is marked infeasible by the optimiser."
                   value={pct(form.max_borrowing_apr)}>
              <input type="range" min={5} max={48} step={1}
                     value={Math.round(form.max_borrowing_apr * 100)}
                     onChange={(e) => setForm({ ...form, max_borrowing_apr: Number(e.target.value) / 100 })}
                     className="w-full accent-[var(--primary)]" />
            </Field>
            <Field label="Minimum order margin"
                   hint="An order below this margin is flagged as violating policy."
                   value={pct(form.min_order_margin)}>
              <input type="range" min={0} max={60} step={1}
                     value={Math.round(form.min_order_margin * 100)}
                     onChange={(e) => setForm({ ...form, min_order_margin: Number(e.target.value) / 100 })}
                     className="w-full accent-[var(--primary)]" />
            </Field>
            <Field label="Risk appetite"
                   hint="Shifts the weights the decision optimiser uses between liquidity, profit, downside and cost.">
              <div className="flex gap-2">
                {["conservative", "balanced", "aggressive"].map((r) => (
                  <button key={r} onClick={() => setForm({ ...form, risk_appetite: r })}
                    className={cn("flex-1 rounded-lg border px-3 py-1.5 text-xs capitalize",
                      form.risk_appetite === r ? "border-primary bg-primary-soft text-primary"
                                               : "border-border text-muted-foreground hover:bg-surface-hover")}>
                    {r}
                  </button>
                ))}
              </div>
            </Field>
          </div>
          <button onClick={() => save.run()} disabled={save.pending}
                  className="mt-4 inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-primary text-xs font-medium text-primary-foreground disabled:opacity-50">
            {save.pending ? <Loader2 className="size-3.5 animate-spin" />
              : saved ? <Check className="size-3.5" /> : <Save className="size-3.5" />}
            {saved ? "Saved — the engine has been recomputed" : "Save policy"}
          </button>
          {save.error && <p role="alert" className="mt-2 text-[11px] text-fin-loss">{save.error}</p>}
        </Panel>

        <div className="space-y-4">
          <Panel title="Business" description="Identity and classification">
            <Evidence items={[
              { label: "Name", value: biz.data.name },
              { label: "Legal name", value: biz.data.legal_name ?? "—" },
              { label: "Industry", value: biz.data.industry.replace(/_/g, " ") },
              { label: "City", value: biz.data.city ?? "—" },
              { label: "GSTIN", value: biz.data.gstin ?? "—" },
              { label: "MSME class", value: biz.data.msme_class ?? "—" },
              { label: "Udyam", value: biz.data.udyam_number ?? "—" },
              { label: "Your role", value: biz.data.role },
            ]} dense />
          </Panel>

          <Panel title="Evaluation date"
                 description="Everything in RUNWAY is computed as of a date. Point-in-time evaluation is what makes forecast accuracy measurable.">
            <div className="flex gap-2">
              <input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)}
                     className="h-9 flex-1 rounded-lg border border-border bg-surface px-3 text-sm outline-none focus-visible:border-primary/60 focus-visible:ring-2 focus-visible:ring-primary/25" />
              <button onClick={() => { session.setAsOf(asOf || null); window.location.reload(); }}
                      className="rounded-lg border border-border px-3 text-xs hover:bg-surface-hover">
                Apply
              </button>
              <button onClick={() => { session.setAsOf(null); window.location.reload(); }}
                      className="rounded-lg px-3 text-xs text-muted-foreground hover:bg-surface-hover">
                Today
              </button>
            </div>
          </Panel>

          {biz.data.is_demo && scenarios.data && (
            <Panel title="Demonstration scenario"
                   description="Switching regenerates the entire synthetic workspace. Every module recomputes from the new ledger — nothing is hardcoded per scenario.">
              <ul className="space-y-2">
                {scenarios.data.scenarios.map((s: any) => (
                  <li key={s.key}>
                    <button onClick={() => switchScenario.run(s.key)}
                            disabled={switchScenario.pending}
                            className={cn("w-full rounded-lg border px-3 py-2.5 text-left transition-colors disabled:opacity-50",
                              biz.data.demo_scenario === s.key
                                ? "border-primary bg-primary-soft" : "border-border hover:bg-surface-hover")}>
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-[13px] font-medium">
                          {s.key} · {s.label}
                        </span>
                        {biz.data.demo_scenario === s.key && (
                          <span className="rw-chip border-primary/30 bg-primary-soft text-primary">active</span>
                        )}
                      </div>
                      <p className="mt-0.5 text-[11px] text-muted-foreground text-pretty">{s.summary}</p>
                    </button>
                  </li>
                ))}
              </ul>
              {switchScenario.pending && (
                <p className="mt-2 flex items-center gap-2 text-[11px] text-muted-foreground">
                  <Loader2 className="size-3 animate-spin" /> Regenerating the workspace…
                </p>
              )}
              <div className="mt-3">
            <Details label="How this is calculated">
              {scenarios.data.note}
            </Details>
          </div>
            </Panel>
          )}

          <Panel title="Recompute">
            <button onClick={() => refresh.run()} disabled={refresh.pending}
                    className="inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg border border-border text-xs hover:bg-surface-hover disabled:opacity-50">
              {refresh.pending ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCw className="size-3.5" />}
              Rebuild the digital twin now
            </button>
            <div className="mt-3">
            <Details label="How accuracy is measured">
              Forces a fresh actual state and a new forecast version. The previous versions
              are preserved so forecast accuracy stays measurable.
            </Details>
          </div>
          </Panel>

          {meta.data && (
            <Panel title="Engine" description={`RUNWAY ${meta.data.version} · ${meta.data.env}`}>
              <Evidence dense items={Object.entries(meta.data.capabilities).map(([k, v]) => ({
                label: k.replace(/_/g, " "), value: String(v),
              }))} />
              <ul className="mt-3 space-y-1.5">
                {meta.data.principles.map((p: string, i: number) => (
                  <li key={i} className="flex gap-2 text-[11px] text-muted-foreground">
                    <span className="mt-1.5 size-1 shrink-0 rounded-full bg-fin-gain" aria-hidden />
                    <span className="text-pretty">{p}</span>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, value, children }:
  { label: string; hint?: string; value?: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-3">
        <span className="text-[11px] font-medium text-muted-foreground">{label}</span>
        {value && <span className="text-[12px] tnum">{value}</span>}
      </div>
      {children}
      {hint && <p className="mt-1 text-[10px] leading-relaxed text-muted-foreground text-pretty">{hint}</p>}
    </div>
  );
}
