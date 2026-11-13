"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { Check, Clock, Loader2, RefreshCw, X } from "lucide-react";
import { Logo } from "@/components/runway/brand";
import { api, session } from "@/lib/api";

/** Shown to a manager or accountant whose access is not yet approved.
 *  It reads only the user's own session - no business figures exist here. */
export default function PendingPage() {
  const router = useRouter();
  const [me, setMe] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!session.token) { router.replace("/login"); return; }
    setBusy(true);
    try {
      const r = await api.get<any>("/api/auth/me");
      if (r.active_business_id) {
        session.set(session.token!, r.active_business_id);
        router.replace("/app");
        return;
      }
      setMe(r);
    } finally { setBusy(false); }
  }, [router]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="min-h-dvh bg-paper px-6 py-8 sm:px-12">
      <Link href="/" aria-label="Runway home"><Logo /></Link>
      <div className="mx-auto max-w-[560px] py-14">
        <span className="grid size-12 place-items-center rounded-2xl bg-sage text-forest">
          <Clock className="size-6" aria-hidden />
        </span>
        <h1 className="display mt-4 text-[30px]">Waiting for approval</h1>
        <p className="mt-2 text-[15px] text-ink-2 text-pretty">
          Your account exists, but nothing in the business is visible until the
          people responsible approve you. This page checks again when you press refresh.
        </p>

        {(me?.pending_memberships ?? []).map((p: any, i: number) => (
          <div key={i} className="mt-6 rounded-2xl border border-line bg-card p-5">
            <p className="text-[13px] text-ink-3">Request to join</p>
            <p className="text-[18px] font-semibold">{p.business_name}</p>
            <p className="mt-0.5 text-[13px] capitalize text-ink-2">as {p.role}</p>
            {p.status === "rejected" ? (
              <p className="mt-4 flex items-center gap-2 text-sm font-semibold text-loss">
                <X className="size-4" /> This request was declined.
              </p>
            ) : (
              <ul className="mt-4 space-y-1.5 text-[13.5px]">
                {(p.approvals ?? []).filter((a: any) => a.decision === "approved").map((a: any) => (
                  <li key={a.role} className="flex items-center gap-2 text-gain">
                    <Check className="size-4" /> Approved by the {a.role} ({a.name})
                  </li>
                ))}
                {(p.waiting_for ?? []).map((r: string) => (
                  <li key={r} className="flex items-center gap-2 text-ink-2">
                    <Clock className="size-4" /> Waiting for the {r}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}

        <div className="mt-6 flex gap-2">
          <button onClick={load} disabled={busy} className="btn btn-primary">
            {busy ? <Loader2 className="size-4 animate-spin" /> : <RefreshCw className="size-4" />}
            Check again
          </button>
          <button onClick={() => { session.clear(); router.push("/login"); }} className="btn btn-ghost">
            Sign out
          </button>
        </div>
      </div>
    </div>
  );
}
