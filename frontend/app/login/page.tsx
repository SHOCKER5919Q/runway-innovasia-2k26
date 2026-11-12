"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Loader2, Lock, Mail, ShieldCheck } from "lucide-react";
import { Logo } from "@/components/runway/shell";
import { api, login, session } from "@/lib/api";

type DemoAccount = { email: string; password: string; role: string; name: string; sees: string };

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("owner@runway.demo");
  const [password, setPassword] = useState("demo1234");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<DemoAccount[]>([]);

  useEffect(() => {
    api.get<{ accounts: DemoAccount[] }>("/api/auth/demo-accounts")
      .then((r) => setAccounts(r.accounts)).catch(() => {});
    // Pin the demo clock so the workspace matches the documented figures.
    if (!session.asOf) session.setAsOf("2026-11-07");
  }, []);

  async function submit(e: React.FormEvent, overrideEmail?: string, overridePw?: string) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await login(overrideEmail ?? email, overridePw ?? password);
      router.push("/app");
    } catch (err: any) {
      setError(err?.message ?? "Sign-in failed");
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      {/* left: the promise */}
      <section className="relative hidden flex-col justify-between border-r border-border bg-surface/30 p-10 lg:flex xl:p-14">
        <Link href="/"><Logo /></Link>
        <div className="max-w-md">
          <h1 className="font-display text-[32px] font-semibold leading-[1.12] tracking-[-0.02em] text-balance xl:text-4xl">
            See the business.
            <br />Understand the future.
            <br /><span className="text-primary">Test the decision.</span>
          </h1>
          <p className="mt-4 text-[14.5px] leading-relaxed text-muted-foreground text-pretty">
            RUNWAY reconciles your transactions against your invoices and projects
            thirteen weeks of cash with an honest uncertainty band.
          </p>
          <ul className="mt-7 space-y-2.5 text-[13.5px] text-muted-foreground">
            {[
              "Actual, predicted and simulated kept strictly apart",
              "Every number traceable to an invoice or a transaction",
              "Nothing moves money without your approval",
            ].map((t) => (
              <li key={t} className="flex items-start gap-2.5">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-fin-gain" aria-hidden />
                <span>{t}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs text-muted-foreground">
          INNOVASIA 2K26 · PS-04 · Vasavi College of Engineering
        </p>
      </section>

      {/* right: the form */}
      <section className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          <div className="lg:hidden"><Logo /></div>
          <h2 className="mt-8 font-display text-2xl font-semibold tracking-tight lg:mt-0">
            Sign in
          </h2>
          <p className="mt-1 text-[13.5px] text-muted-foreground">
            Use a demo account below, or sign in with your own.
          </p>

          <form onSubmit={submit} className="mt-7 space-y-4">
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Email</span>
              <span className="relative block">
                <Mail className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <input type="email" value={email} onChange={(e) => setEmail(e.target.value)}
                       required autoComplete="username"
                       className="h-11 w-full rounded-lg border border-border bg-surface pl-10 pr-3 text-sm outline-none transition-colors focus:border-primary/60" />
              </span>
            </label>
            <label className="block">
              <span className="mb-1.5 block text-xs font-medium text-muted-foreground">Password</span>
              <span className="relative block">
                <Lock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                <input type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                       required autoComplete="current-password"
                       className="h-11 w-full rounded-lg border border-border bg-surface pl-10 pr-3 text-sm outline-none transition-colors focus:border-primary/60" />
              </span>
            </label>

            {error && (
              <p role="alert"
                 className="rounded-lg border border-fin-loss/30 bg-fin-loss-soft px-3 py-2 text-xs text-fin-loss">
                {error}
              </p>
            )}

            <button type="submit" disabled={busy}
                    className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-primary text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <>Sign in <ArrowRight className="size-4" /></>}
            </button>
          </form>

          {accounts.length > 0 && (
            <div className="mt-8">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Demo accounts
              </p>
              <ul className="mt-2.5 space-y-2">
                {accounts.map((a) => (
                  <li key={a.email}>
                    <button
                      onClick={(e) => { setEmail(a.email); setPassword(a.password); submit(e, a.email, a.password); }}
                      className="group flex w-full items-center gap-3 rounded-lg border border-border bg-surface px-3 py-2.5 text-left transition-colors hover:bg-surface-hover">
                      <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary/15 text-[11px] font-semibold text-primary">
                        {a.name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[13px] font-medium">{a.role}</span>
                        <span className="block truncate text-[11px] text-muted-foreground">{a.sees}</span>
                      </span>
                      <ArrowRight className="size-3.5 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
                These accounts open a synthetic business. Production authentication
                is separate.
              </p>
            </div>
          )}

          <p className="mt-8 text-[11.5px] text-muted-foreground">
            <Link href="/" className="hover:text-foreground">← Back to runway</Link>
          </p>
        </div>
      </section>
    </div>
  );
}
