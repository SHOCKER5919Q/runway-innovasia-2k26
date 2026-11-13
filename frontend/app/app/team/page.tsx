"use client";

import { useState } from "react";
import { Check, Copy, KeyRound, RefreshCw, ShieldCheck, X } from "lucide-react";
import {
  EmptyState, ErrorState, LoadingPanel, Panel, SectionHeader,
} from "@/components/runway/primitives";
import { api } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { cn } from "@/lib/utils";

export default function TeamPage() {
  const team = useApi<any>("/api/team");
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  if (team.error) return <ErrorState message={team.error} onRetry={team.reload} />;
  if (team.loading || !team.data) return <LoadingPanel rows={6} />;
  const d = team.data;

  async function decide(id: string, approve: boolean) {
    setBusy(id); setMsg(null);
    try {
      const r = await api.post<any>(`/api/team/${id}/${approve ? "approve" : "reject"}`, {});
      setMsg(r.status === "pending"
        ? `Your approval is recorded. Still waiting for: ${r.waiting_for.join(", ")}.`
        : r.status === "approved" ? "Approved - they can now sign in and see this business."
        : "Request declined.");
      team.reload();
    } catch (e: any) { setMsg(e?.message ?? "Could not record the decision"); }
    finally { setBusy(null); }
  }

  async function rotate() {
    setBusy("rotate");
    try { await api.post("/api/team/join-code/rotate", {}); team.reload(); }
    finally { setBusy(null); }
  }

  return (
    <div className="space-y-5">
      <SectionHeader
        title="Team & approvals"
        description="Who can see this business, and who is waiting to. A manager needs the owner's approval; an accountant needs both the manager's and the owner's." />

      {msg && <p className="rounded-lg border border-line bg-card px-4 py-2.5 text-[13px]">{msg}</p>}

      {d.join_code && (
        <Panel title="Join code" description="Share this with a manager or accountant so they can ask to join. Rotating it stops the old code at once.">
          <div className="flex flex-wrap items-center gap-3">
            <KeyRound className="size-4 text-forest" aria-hidden />
            <code className="rounded-lg bg-paper-2 px-3 py-1.5 font-mono text-[16px] font-semibold tracking-wider">
              {d.join_code}
            </code>
            <button className="btn btn-ghost btn-sm"
                    onClick={() => navigator.clipboard?.writeText(d.join_code)}>
              <Copy className="size-3.5" /> Copy
            </button>
            <button className="btn btn-ghost btn-sm" onClick={rotate} disabled={busy === "rotate"}>
              <RefreshCw className="size-3.5" /> New code
            </button>
          </div>
        </Panel>
      )}

      <Panel title={`Waiting for approval (${d.requests.length})`} bodyClass="p-0">
        {d.requests.length === 0 ? (
          <div className="p-5"><EmptyState title="No pending requests" /></div>
        ) : (
          <ul className="divide-y divide-line">
            {d.requests.map((m: any) => (
              <li key={m.membership_id} className="flex flex-wrap items-center gap-4 px-6 py-4">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{m.name} <span className="font-normal text-ink-3">· {m.email}</span></p>
                  <p className="mt-0.5 text-[13px] capitalize text-ink-2">wants to join as {m.role}</p>
                  <p className="mt-1 flex flex-wrap gap-1.5 text-[12px]">
                    {m.required.map((r: string) => {
                      const done = m.approvals.some((a: any) => a.role === r && a.decision === "approved");
                      return (
                        <span key={r} className={cn("pill", done ? "pill-gain" : "")}>
                          {done ? <Check className="size-3" /> : null} {r}
                        </span>
                      );
                    })}
                  </p>
                </div>
                {m.you_can_decide ? (
                  <div className="flex gap-2">
                    <button className="btn btn-primary btn-sm" disabled={busy === m.membership_id}
                            onClick={() => decide(m.membership_id, true)}>
                      <Check className="size-3.5" /> Approve
                    </button>
                    <button className="btn btn-ghost btn-sm" disabled={busy === m.membership_id}
                            onClick={() => decide(m.membership_id, false)}>
                      <X className="size-3.5" /> Decline
                    </button>
                  </div>
                ) : (
                  <span className="text-[12px] text-ink-3">
                    Waiting for {m.waiting_for.join(" and ")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel title={`Members (${d.members.length})`} bodyClass="p-0">
        <ul className="divide-y divide-line">
          {d.members.map((m: any) => (
            <li key={m.membership_id} className="flex items-center gap-4 px-6 py-3">
              <ShieldCheck className="size-4 text-forest" aria-hidden />
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-semibold">{m.name}</p>
                <p className="text-[12px] text-ink-3">{m.email}</p>
              </div>
              <span className="pill capitalize">{m.role}</span>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
