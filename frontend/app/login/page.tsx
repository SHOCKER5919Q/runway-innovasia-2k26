"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Loader2, Lock, Mail, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { Logo } from "@/components/runway/shell";
import { EASE_OUT } from "@/components/runway/motion";
import { GridBeam, Magnetic, SplitText } from "@/components/runway/bits";
import HeroCanvas from "@/components/runway/hero3d-loader";
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
    // Pin the demo clock so a judge sees the same workspace the docs describe.
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
    <div className="relative grid min-h-dvh lg:grid-cols-[1.05fr_1fr]">
      <div className="pointer-events-none absolute inset-0 rw-aurora" aria-hidden />
      <GridBeam />

      {/* left: the promise */}
      <section className="relative hidden flex-col justify-between p-10 lg:flex xl:p-14">
        <Link href="/"><Logo /></Link>
        <div className="relative max-w-lg">
          <HeroCanvas className="pointer-events-none absolute -right-28 -top-56 h-[30rem] w-[30rem] opacity-70" />
          <h1 className="relative font-display text-4xl font-semibold leading-[1.08] tracking-[-0.025em] text-balance xl:text-5xl">
            <SplitText text="See the business." className="block" />
            <SplitText text="Understand the future." className="block" delay={0.22} />
            <span className="block text-primary">
              <SplitText text="Test the decision." delay={0.44} />
            </span>
          </h1>
          <motion.p
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8, duration: 0.6, ease: EASE_OUT }}
            className="mt-5 text-pretty text-[15px] leading-relaxed text-muted-foreground">
            RUNWAY reads your transactions, reconciles them against your invoices, and
            projects thirteen weeks of cash with an honest uncertainty band — so you can
            see a liquidity problem while there is still time to act on it.
          </motion.p>
          <motion.ul
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 1.0 }}
            className="mt-7 space-y-2.5 text-sm text-muted-foreground">
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
          </motion.ul>
        </div>
        <p className="text-xs text-muted-foreground">
          INNOVASIA 2K26 · PS-04 · Team SignalForge · Vasavi College of Engineering
        </p>
      </section>

      {/* right: the form */}
      <section className="relative flex items-center justify-center p-6 sm:p-10">
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE_OUT }}
          className="w-full max-w-md">
          <div className="lg:hidden"><Logo /></div>
          <h2 className="mt-6 font-display text-2xl font-semibold tracking-tight lg:mt-0">
            Welcome back
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">Sign in to your RUNWAY workspace.</p>

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
              <p role="alert" className="rounded-lg border border-fin-loss/30 bg-fin-loss-soft px-3 py-2 text-xs text-fin-loss">
                {error}
              </p>
            )}

            <button type="submit" disabled={busy}
                    className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--glow-primary)] transition-transform hover:-translate-y-0.5 disabled:translate-y-0 disabled:opacity-60">
              {busy ? <Loader2 className="size-4 animate-spin" /> : <>Sign in <ArrowRight className="size-4" /></>}
            </button>
          </form>

          {accounts.length > 0 && (
            <div className="mt-8">
              <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
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
                These accounts exist only in the demonstration workspace and open a
                synthetic business. Production authentication is separate.
              </p>
            </div>
          )}
        </motion.div>
      </section>
    </div>
  );
}
