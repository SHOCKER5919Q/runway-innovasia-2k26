"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowRight, Check, Loader2, ShieldCheck, TrendingUp } from "lucide-react";
import { motion } from "motion/react";
import { Logo } from "@/components/runway/brand";
import { EASE_OUT } from "@/components/runway/motion";
import { api, login, register, session } from "@/lib/api";

type DemoAccount = { email: string; password: string; role: string; name: string; sees: string };

const INDUSTRIES = [
  { value: "manufacturing", label: "Manufacturing" },
  { value: "wholesale_distribution", label: "Wholesale / Distribution" },
  { value: "retail", label: "Retail" },
  { value: "services", label: "Services" },
];

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"signin" | "register">("signin");
  const [email, setEmail] = useState("owner@runway.demo");
  const [password, setPassword] = useState("demo1234");
  const [fullName, setFullName] = useState("");
  const [businessName, setBusinessName] = useState("");
  const [industry, setIndustry] = useState("manufacturing");
  const [city, setCity] = useState("");
  const [openingRupees, setOpeningRupees] = useState("");
  const [bufferRupees, setBufferRupees] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<DemoAccount[]>([]);

  useEffect(() => {
    api.get<{ accounts: DemoAccount[] }>("/api/auth/demo-accounts")
      .then((r) => setAccounts(r.accounts)).catch(() => {});
    if (typeof window !== "undefined") {
      const m = new URLSearchParams(window.location.search).get("mode");
      if (m === "register") {
        setMode("register");
        setEmail("");
        setPassword("");
      } else if (!session.asOf) {
        session.setAsOf("2026-11-07");
      }
    }
  }, []);

  function switchMode(next: "signin" | "register") {
    setMode(next);
    setError(null);
    if (next === "register") {
      if (email === "owner@runway.demo") setEmail("");
      if (password === "demo1234") setPassword("");
    } else {
      if (!email) setEmail("owner@runway.demo");
      if (!password) setPassword("demo1234");
    }
  }

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

  async function submitRegister(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      const openingPaise = Math.round((Number(openingRupees || 0) || 0) * 100);
      const bufferPaise = Math.max(0, Math.round((Number(bufferRupees || 0) || 0) * 100));
      await register({
        email,
        password,
        full_name: fullName,
        business_name: businessName,
        industry,
        city: city || undefined,
        opening_balance_paise: openingPaise,
        safety_buffer_paise: bufferPaise,
      });
      router.push("/app/onboarding");
    } catch (err: any) {
      setError(err?.message ?? "Could not create account");
      setBusy(false);
    }
  }

  return (
    <div className="grid min-h-dvh bg-paper lg:grid-cols-[1fr_1.05fr]">
      {/* left: the form, on paper */}
      <div className="flex flex-col px-6 py-8 sm:px-12">
        <Link href="/" aria-label="Runway home"><Logo /></Link>
        <motion.div
          initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: EASE_OUT }}
          className="mx-auto flex w-full max-w-[440px] flex-1 flex-col justify-center py-10"
        >
          <div className="mb-6 grid grid-cols-2 rounded-xl border border-line bg-card p-1">
            <button type="button" onClick={() => switchMode("signin")}
              className={`rounded-lg py-2 text-xs font-semibold transition ${
                mode === "signin" ? "bg-forest text-white" : "text-ink-2 hover:text-ink"
              }`}>
              Sign in / Demo
            </button>
            <button type="button" onClick={() => switchMode("register")}
              className={`rounded-lg py-2 text-xs font-semibold transition ${
                mode === "register" ? "bg-forest text-white" : "text-ink-2 hover:text-ink"
              }`}>
              Create account
            </button>
          </div>

          {mode === "signin" ? (
            <>
              <p className="eyebrow">Welcome back</p>
              <h1 className="display mt-3 text-[34px] sm:text-[38px]">Sign in to Runway.</h1>
              <p className="mb-8 mt-2 text-[15px] text-ink-2">See your cash forecast and test the next decision.</p>

              <form onSubmit={submit} className="space-y-5">
                <div>
                  <label htmlFor="email" className="label">Email</label>
                  <input id="email" className="field" type="email" value={email}
                         onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
                </div>
                <div>
                  <label htmlFor="pw" className="label">Password</label>
                  <input id="pw" className="field" type="password" value={password}
                         onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
                </div>
                {error && <p role="alert" className="text-sm font-semibold text-loss">{error}</p>}
                <button type="submit" disabled={busy} className="btn btn-primary h-[50px] w-full">
                  {busy ? <Loader2 className="size-4 animate-spin" /> : <>Sign in <ArrowRight className="size-4" /></>}
                </button>
              </form>

              {accounts.length > 0 && (
                <div className="mt-8 rounded-2xl bg-sage p-5">
                  <p className="text-sm font-semibold">Demo accounts</p>
                  <p className="mt-0.5 text-[13px] text-ink-2">
                    Same sample business, different roles. Password is demo1234.
                  </p>
                  <div className="mt-4 grid gap-2">
                    {accounts.map((a) => (
                      <button key={a.email} type="button"
                              onClick={(e) => { setEmail(a.email); setPassword(a.password); submit(e, a.email, a.password); }}
                              className={`flex items-center justify-between gap-3 rounded-xl border bg-card px-4 py-2.5 text-left text-sm transition hover:border-forest ${email === a.email ? "border-forest" : "border-line"}`}>
                        <span className="font-semibold">{a.role}</span>
                        <span className="truncate text-xs text-ink-3">{a.sees}</span>
                      </button>
                    ))}
                  </div>
                  <p className="mt-4 flex items-start gap-1.5 text-[11px] leading-relaxed text-ink-2">
                    <Check className="mt-0.5 size-3 shrink-0 text-gain" aria-hidden />
                    These accounts exist only in the demonstration workspace and open a
                    synthetic business. Switch to Create account to use your own numbers.
                  </p>
                </div>
              )}
            </>
          ) : (
            <>
              <p className="eyebrow">New business workspace</p>
              <h1 className="display mt-3 text-[32px] sm:text-[36px]">Set up your Runway.</h1>
              <p className="mb-6 mt-2 text-[14px] text-ink-2">
                Create your own private ledger, enter or upload your numbers, and run all forecasts on your real data.
              </p>

              <form onSubmit={submitRegister} className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label htmlFor="reg-name" className="label">Your name</label>
                    <input id="reg-name" className="field" type="text" placeholder="Ramesh Kumar"
                           value={fullName} onChange={(e) => setFullName(e.target.value)} required />
                  </div>
                  <div>
                    <label htmlFor="reg-city" className="label">City (optional)</label>
                    <input id="reg-city" className="field" type="text" placeholder="Hyderabad"
                           value={city} onChange={(e) => setCity(e.target.value)} />
                  </div>
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label htmlFor="reg-biz" className="label">Business name</label>
                    <input id="reg-biz" className="field" type="text" placeholder="Sri Sai Precision Works"
                           value={businessName} onChange={(e) => setBusinessName(e.target.value)} required />
                  </div>
                  <div>
                    <label htmlFor="reg-ind" className="label">Industry</label>
                    <select id="reg-ind" className="field" value={industry}
                            onChange={(e) => setIndustry(e.target.value)}>
                      {INDUSTRIES.map((i) => (
                        <option key={i.value} value={i.value}>{i.label}</option>
                      ))}
                    </select>
                  </div>
                </div>
                <div>
                  <label htmlFor="reg-email" className="label">Email</label>
                  <input id="reg-email" className="field" type="email" placeholder="owner@yourcompany.com"
                         value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required />
                </div>
                <div>
                  <label htmlFor="reg-pw" className="label">Password (8+ characters)</label>
                  <input id="reg-pw" className="field" type="password" minLength={8}
                         value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" required />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label htmlFor="reg-cash" className="label">Bank cash today (₹, optional)</label>
                    <input id="reg-cash" className="field" type="number" min={0} placeholder="500000"
                           value={openingRupees} onChange={(e) => setOpeningRupees(e.target.value)} />
                  </div>
                  <div>
                    <label htmlFor="reg-buf" className="label">Cash floor / buffer (₹, optional)</label>
                    <input id="reg-buf" className="field" type="number" min={0} placeholder="200000"
                           value={bufferRupees} onChange={(e) => setBufferRupees(e.target.value)} />
                  </div>
                </div>
                {error && <p role="alert" className="text-sm font-semibold text-loss">{error}</p>}
                <button type="submit" disabled={busy} className="btn btn-primary h-[50px] w-full">
                  {busy ? <Loader2 className="size-4 animate-spin" /> : <>Create workspace & add data <ArrowRight className="size-4" /></>}
                </button>
              </form>
            </>
          )}
        </motion.div>
      </div>

      {/* right: the promise, on forest */}
      <div className="dots relative hidden flex-col justify-between overflow-hidden bg-forest px-10 py-12 text-white lg:flex xl:px-14">
        <div className="relative"><Logo inverse /></div>

        <div className="relative max-w-lg">
          <p className="text-sm font-semibold text-lime">Financial intelligence · Indian MSMEs</p>
          <h2 className="display mt-6 text-[clamp(2.4rem,4vw,3.6rem)]">
            Know when cash gets tight, <em className="serif-i text-lime">weeks</em> before it does.
          </h2>
          <p className="mt-6 max-w-md text-pretty text-[15px] leading-relaxed text-white/75">
            RUNWAY reconciles your bank, invoices and GST dates into one ledger and
            projects thirteen weeks of cash with an honest uncertainty band — so you
            can see a liquidity problem while there is still time to act.
          </p>
          <ul className="mt-8 space-y-3 text-[14px] text-white/85">
            {[
              "Actual, predicted and simulated kept strictly apart",
              "Every number traceable to an invoice or a transaction",
              "Nothing moves money without your approval",
            ].map((t) => (
              <li key={t} className="flex items-start gap-2.5">
                <ShieldCheck className="mt-0.5 size-4 shrink-0 text-lime" aria-hidden />
                <span>{t}</span>
              </li>
            ))}
          </ul>

          <div className="mt-10 rounded-2xl border border-white/15 bg-white/10 p-5 backdrop-blur-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-wider text-white/60">13-week cash position</p>
                <p className="num mt-1.5 text-2xl font-semibold">₹4.77 L → ₹16.90 L</p>
              </div>
              <span className="grid size-10 place-items-center rounded-xl bg-lime text-forest">
                <TrendingUp className="size-5" aria-hidden />
              </span>
            </div>
            <svg viewBox="0 0 320 74" className="mt-3 w-full" aria-hidden>
              <path d="M0 62 L27 55 L53 48 L80 50 L107 42 L133 36 L160 31 L187 34 L213 25 L240 19 L267 16 L293 18 L320 8"
                    fill="none" stroke="#d3f26b" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
              <path d="M0 62 L27 58 L53 60 L80 64 L107 68 L133 69 L160 67 L187 64 L213 58 L240 48 L267 40 L293 32 L320 22"
                    fill="none" stroke="rgba(255,255,255,.55)" strokeWidth="1.6" strokeDasharray="4 4" strokeLinecap="round" />
            </svg>
            <p className="mt-2 text-[10px] text-white/60">
              solid · predicted P50 &nbsp; / &nbsp; dashed · P10 downside
            </p>
          </div>
        </div>

        <p className="relative text-[11px] text-white/60">
          INNOVASIA 2K26 · PS-04 · Team SignalForge · Vasavi College of Engineering
        </p>
      </div>
    </div>
  );
}
