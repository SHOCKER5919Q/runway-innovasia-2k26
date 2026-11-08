"use client";

import { useEffect, useRef, useState } from "react";
import {
  Brain, ChevronRight, CornerDownLeft, Languages, Loader2, Mic, Sparkles, Wrench,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import {
  Evidence, LoadingPanel, Panel, Provenance, SectionHeader, StateBadge,
} from "@/components/runway/primitives";
import { EASE_OUT } from "@/components/runway/motion";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

type Turn = {
  role: "user" | "assistant";
  text: string;
  state?: string;
  tool?: { name: string; matched_phrase: string; routing_confidence: number };
  evidence?: { label: string; value: string }[];
  followups?: string[];
  generator?: string;
  disclaimer?: string | null;
  ok?: boolean;
};

export default function CopilotPage() {
  const suggestions = useApi<any>("/api/copilot/suggestions");
  const tools = useApi<any>("/api/copilot/tools");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [lang, setLang] = useState("en");
  const [conv, setConv] = useState<string | null>(null);
  const [listening, setListening] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [turns, busy]);

  async function ask(question: string) {
    if (!question.trim() || busy) return;
    setTurns((t) => [...t, { role: "user", text: question }]);
    setQ("");
    setBusy(true);
    try {
      const r = await api.post<any>("/api/copilot/ask",
        { question, conversation_id: conv, language: lang });
      setConv(r.conversation_id);
      setTurns((t) => [...t, {
        role: "assistant", text: r.answer, state: r.state, tool: r.tool,
        evidence: r.evidence, followups: r.followups, generator: r.generator,
        disclaimer: r.disclaimer, ok: r.ok,
      }]);
    } catch (e: any) {
      setTurns((t) => [...t, { role: "assistant", text: e?.message ?? "Something went wrong.", ok: false }]);
    } finally { setBusy(false); }
  }

  /* Voice input via the browser's own speech recognition where available.
     No audio leaves the device beyond what the browser itself does. */
  function toggleVoice() {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SR) { alert("This browser does not provide speech recognition."); return; }
    if (listening) { setListening(false); return; }
    const rec = new SR();
    rec.lang = lang === "hi" ? "hi-IN" : lang === "te" ? "te-IN" : lang === "ta" ? "ta-IN" : "en-IN";
    rec.interimResults = false;
    rec.onresult = (ev: any) => { setQ(ev.results[0][0].transcript); setListening(false); };
    rec.onerror = () => setListening(false);
    rec.onend = () => setListening(false);
    rec.start();
    setListening(true);
  }

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
      <div className="flex min-h-[calc(100dvh-8rem)] flex-col">
        <SectionHeader
          title="Talk to your business"
          description="Ask a question in plain language. RUNWAY routes it to a financial tool, runs the calculation, and explains the result — it never does the arithmetic in prose."
          actions={
            <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label="Language"
                    className="h-8 rounded-md border border-border bg-surface px-2 text-xs outline-none">
              {(suggestions.data?.languages ?? [{ code: "en", label: "English" }]).map((l: any) => (
                <option key={l.code} value={l.code}>{l.label}</option>
              ))}
            </select>} />

        <div className="flex-1 space-y-4 overflow-y-auto pb-4">
          {turns.length === 0 && (
            <div className="rw-card p-6 text-center">
              <span className="mx-auto grid size-12 place-items-center rounded-xl bg-primary-soft">
                <Brain className="size-6 text-primary" aria-hidden />
              </span>
              <p className="mt-3 font-display text-lg font-semibold">
                Ask anything about this business
              </p>
              <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground text-pretty">
                Every answer says whether it came from your recorded ledger, a model
                prediction, or a simulation — and shows the evidence behind it.
              </p>
              <div className="mx-auto mt-5 flex max-w-2xl flex-wrap justify-center gap-2">
                {(suggestions.data?.suggestions ?? []).map((s: string) => (
                  <button key={s} onClick={() => ask(s)}
                          className="rounded-full border border-border bg-surface px-3 py-1.5 text-[12px] text-muted-foreground transition-colors hover:border-primary/40 hover:bg-primary-soft hover:text-primary">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          <AnimatePresence initial={false}>
            {turns.map((t, i) => (
              <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.3, ease: EASE_OUT }}
                          className={cn("flex", t.role === "user" ? "justify-end" : "justify-start")}>
                {t.role === "user" ? (
                  <p className="max-w-[80%] rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
                    {t.text}
                  </p>
                ) : (
                  <article className="w-full max-w-[92%] rounded-2xl rounded-bl-sm border border-border bg-card p-4">
                    <div className="mb-2.5 flex flex-wrap items-center gap-2">
                      {t.state && t.state !== "unavailable" && <StateBadge state={t.state} />}
                      {t.state === "unavailable" && (
                        <span className="rw-chip border-fin-warn/30 bg-fin-warn-soft text-fin-warn">
                          not available
                        </span>
                      )}
                      {t.tool && (
                        <span className="rw-chip border-border bg-surface text-muted-foreground"
                              title={`Matched on "${t.tool.matched_phrase}"`}>
                          <Wrench className="size-3" /> {t.tool.name}
                        </span>
                      )}
                      {t.generator && (
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                          {t.generator.startsWith("llm") ? "model-written, figures verified"
                                                         : "deterministic"}
                        </span>
                      )}
                    </div>
                    <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-pretty">
                      {t.text}
                    </p>
                    {t.disclaimer && <Provenance>{t.disclaimer}</Provenance>}
                    {t.followups && t.followups.length > 0 && (
                      <div className="mt-3 flex flex-wrap gap-1.5 border-t border-border pt-3">
                        {t.followups.map((f) => (
                          <button key={f} onClick={() => ask(f)}
                                  className="inline-flex items-center gap-1 rounded-full border border-border bg-surface px-2.5 py-1 text-[11px] text-muted-foreground hover:border-primary/40 hover:text-primary">
                            {f} <ChevronRight className="size-3" />
                          </button>
                        ))}
                      </div>
                    )}
                  </article>
                )}
              </motion.div>
            ))}
          </AnimatePresence>

          {busy && (
            <div className="flex items-center gap-2 px-1 text-xs text-muted-foreground">
              <Loader2 className="size-3.5 animate-spin" />
              Running the financial engine…
            </div>
          )}
          <div ref={endRef} />
        </div>

        <form onSubmit={(e) => { e.preventDefault(); ask(q); }}
              className="sticky bottom-0 rounded-xl border border-border bg-card p-2 shadow-lg">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef} value={q} onChange={(e) => setQ(e.target.value)} rows={1}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(q); }
              }}
              placeholder="Ask about your cash, customers, forecast or a decision…"
              className="max-h-32 min-h-[40px] flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none placeholder:text-muted-foreground" />
            <button type="button" onClick={toggleVoice} aria-label="Dictate"
                    className={cn("rounded-lg border p-2",
                      listening ? "border-fin-loss/40 bg-fin-loss-soft text-fin-loss animate-pulse"
                                : "border-border text-muted-foreground hover:bg-surface-hover")}>
              <Mic className="size-4" />
            </button>
            <button type="submit" disabled={busy || !q.trim()} aria-label="Send"
                    className="rounded-lg bg-primary p-2 text-primary-foreground disabled:opacity-40">
              <CornerDownLeft className="size-4" />
            </button>
          </div>
        </form>
      </div>

      {/* ── side panel ── */}
      <aside className="space-y-4">
        <Panel title="How this works" bodyClass="p-4">
          <ol className="space-y-2 text-[12px]">
            {["Your question is routed to a tool by deterministic pattern matching",
              "The tool queries the financial engine and returns structured data",
              "A language model writes the explanation from that data only",
              "Every rupee figure is checked against the tool output before display"]
              .map((s, i) => (
                <li key={i} className="flex gap-2.5">
                  <span className="grid size-5 shrink-0 place-items-center rounded-full bg-primary-soft text-[10px] font-semibold text-primary">
                    {i + 1}
                  </span>
                  <span className="text-muted-foreground text-pretty">{s}</span>
                </li>
              ))}
          </ol>
          {suggestions.data && (
            <p className="mt-3 rounded-lg border border-border bg-surface p-2.5 text-[11px] leading-relaxed text-muted-foreground text-pretty">
              {suggestions.data.generator_note}
            </p>
          )}
        </Panel>

        {tools.data && (
          <Panel title={`${tools.data.tools.length} tools available`}
                 description="The complete set the copilot can call" bodyClass="p-3">
            <ul className="max-h-64 space-y-1 overflow-y-auto">
              {tools.data.tools.map((t: any) => (
                <li key={t.name} className="rounded-md border border-border bg-surface px-2.5 py-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px]">{t.name}</span>
                    <StateBadge state={t.state === "reconciliation" ? "predicted" : t.state} />
                  </div>
                  <p className="mt-0.5 text-[10px] text-muted-foreground text-pretty">
                    {t.description}
                  </p>
                </li>
              ))}
            </ul>
          </Panel>
        )}

        {tools.data?.guarantees && (
          <Panel title="Guarantees" bodyClass="p-4">
            <ul className="space-y-2">
              {tools.data.guarantees.map((g: string, i: number) => (
                <li key={i} className="flex gap-2 text-[11px] leading-relaxed text-muted-foreground">
                  <span className="mt-1.5 size-1 shrink-0 rounded-full bg-fin-gain" aria-hidden />
                  <span className="text-pretty">{g}</span>
                </li>
              ))}
            </ul>
          </Panel>
        )}
      </aside>
    </div>
  );
}
