"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, Briefcase, Calculator, Crown, Loader2 } from "lucide-react";
import { Logo } from "@/components/runway/brand";
import { register } from "@/lib/api";
import { cn } from "@/lib/utils";

type Role = "owner" | "manager" | "accountant";

const ROLES: { key: Role; label: string; icon: any; who: string; approval: string }[] = [
  { key: "owner", label: "Owner", icon: Crown,
    who: "You run the business. You create its workspace and decide who joins.",
    approval: "No approval needed - your workspace opens straight away." },
  { key: "manager", label: "Manager", icon: Briefcase,
    who: "You run day-to-day money: imports, collections, payments.",
    approval: "The owner must approve you before you can see anything." },
  { key: "accountant", label: "Accountant", icon: Calculator,
    who: "You keep the books, reconcile and file for one or more businesses.",
    approval: "Both the manager and the owner must approve you." },
];

export default function SignupPage() {
  const router = useRouter();
  const [role, setRole] = useState<Role>("owner");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [business, setBusiness] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const current = ROLES.find((r) => r.key === role)!;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const r = await register({
        email, password, full_name: name, role,
        ...(role === "owner" ? { business_name: business } : { join_code: code }),
      });
      router.push(r.active_business_id ? "/app" : "/pending");
    } catch (err: any) {
      setError(err?.message ?? "Could not create the account");
      setBusy(false);
    }
  }

  return (
    <div className="min-h-dvh bg-paper px-6 py-8 sm:px-12">
      <Link href="/" aria-label="Runway home"><Logo /></Link>
      <div className="mx-auto max-w-[520px] py-10">
        <p className="eyebrow">Create an account</p>
        <h1 className="display mt-3 text-[32px] sm:text-[36px]">Who are you in the business?</h1>

        <div role="radiogroup" aria-label="Role" className="mt-6 grid gap-2 sm:grid-cols-3">
          {ROLES.map((r) => (
            <button key={r.key} type="button" role="radio" aria-checked={role === r.key}
                    onClick={() => setRole(r.key)}
                    className={cn("rounded-xl border px-3 py-3 text-left transition-colors",
                      role === r.key ? "border-forest bg-sage" : "border-line bg-card hover:bg-paper-2")}>
              <r.icon className="size-4 text-forest" aria-hidden />
              <span className="mt-1.5 block text-[14px] font-semibold">{r.label}</span>
            </button>
          ))}
        </div>
        <div className="mt-3 rounded-xl border border-line bg-card px-4 py-3 text-[13px]">
          <p className="text-ink-2">{current.who}</p>
          <p className="mt-1 font-semibold text-forest">{current.approval}</p>
        </div>

        <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <label htmlFor="name" className="label">Full name</label>
            <input id="name" className="field" value={name} onChange={(e) => setName(e.target.value)}
                   autoComplete="name" required />
          </div>
          <div>
            <label htmlFor="email" className="label">Email</label>
            <input id="email" className="field" type="email" value={email}
                   onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
          </div>
          <div>
            <label htmlFor="pw" className="label">Password (at least 8 characters)</label>
            <input id="pw" className="field" type="password" minLength={8} value={password}
                   onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required />
          </div>
          {role === "owner" ? (
            <div>
              <label htmlFor="biz" className="label">Business name</label>
              <input id="biz" className="field" value={business}
                     onChange={(e) => setBusiness(e.target.value)} required />
            </div>
          ) : (
            <div>
              <label htmlFor="code" className="label">Join code from the owner</label>
              <input id="code" className="field font-mono uppercase" placeholder="RW-XXXXXXXX"
                     value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} required />
              <p className="mt-1 text-[12px] text-ink-3">
                The owner finds it under Team in their Runway workspace.
              </p>
            </div>
          )}
          {error && <p role="alert" className="text-sm font-semibold text-loss">{error}</p>}
          <button type="submit" disabled={busy} className="btn btn-primary h-[50px] w-full">
            {busy ? <Loader2 className="size-4 animate-spin" />
                  : <>Create {current.label.toLowerCase()} account <ArrowRight className="size-4" /></>}
          </button>
        </form>
        <p className="mt-4 text-center text-[13.5px] text-ink-2">
          Already have an account?{" "}
          <Link href="/login" className="font-semibold text-forest underline-offset-4 hover:underline">Sign in</Link>
        </p>
      </div>
    </div>
  );
}
