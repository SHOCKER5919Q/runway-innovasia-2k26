"use client";

/**
 * Shared chrome for the public site.
 *
 * A marketing site should behave like every other site on the internet: a
 * sticky bar with a handful of links, a footer with the legal bits, and pages
 * that scroll normally. No entrance curtain, no scroll-jacking, no pinned
 * chapters — the visitor is here to find out what the product does, not to be
 * given a show.
 */
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode } from "react";
import { ArrowRight, Menu, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Logo } from "@/components/runway/shell";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/features", label: "Features" },
  { href: "/how-it-works", label: "How it works" },
  { href: "/#pricing", label: "Pricing" },
];

export function MarketingShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col bg-background">
      <MarketingNav />
      <main id="main" className="flex-1">{children}</main>
      <MarketingFooter />
    </div>
  );
}

function MarketingNav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={cn(
      "sticky top-0 z-50 border-b bg-background/80 backdrop-blur-md transition-colors",
      scrolled ? "border-border" : "border-transparent")}>
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-5 sm:px-8">
        <Link href="/" aria-label="RUNWAY home"><Logo /></Link>

        <nav className="hidden items-center gap-7 text-[13.5px] md:flex" aria-label="Main">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href}
                  className={cn("transition-colors hover:text-foreground",
                    pathname === l.href ? "text-foreground" : "text-muted-foreground")}>
              {l.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <Link href="/login"
                className="hidden rounded-lg px-3 py-2 text-[13.5px] text-muted-foreground transition-colors hover:text-foreground sm:block">
            Sign in
          </Link>
          <Link href="/login"
                className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3.5 py-2 text-[13.5px] font-semibold text-primary-foreground transition-opacity hover:opacity-90">
            Open demo <ArrowRight className="size-3.5" />
          </Link>
          <button onClick={() => setOpen((v) => !v)} aria-label="Menu"
                  className="rounded-md p-2 text-muted-foreground hover:bg-surface-hover md:hidden">
            {open ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-border px-5 py-3 md:hidden" aria-label="Mobile">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} onClick={() => setOpen(false)}
                  className="block py-2 text-sm text-muted-foreground hover:text-foreground">
              {l.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}

const FOOTER_COLUMNS = [
  {
    title: "Product",
    links: [
      { href: "/features", label: "Features" },
      { href: "/how-it-works", label: "How it works" },
      { href: "/#pricing", label: "Pricing" },
    ],
  },
  {
    title: "Workspace",
    links: [
      { href: "/login", label: "Sign in" },
      { href: "/app", label: "Dashboard" },
      { href: "/app/reports", label: "Cash Health Passport" },
    ],
  },
];

function MarketingFooter() {
  return (
    <footer className="border-t border-border bg-surface/30">
      <div className="mx-auto max-w-6xl px-5 py-12 sm:px-8">
        <div className="flex flex-col gap-10 sm:flex-row sm:justify-between">
          <div className="max-w-xs">
            <Logo />
            <p className="mt-3 text-[13px] leading-relaxed text-muted-foreground">
              A financial intelligence layer for Indian MSMEs — reconciled ledger,
              13-week cash forecast, and a scenario lab.
            </p>
          </div>
          <div className="flex gap-14">
            {FOOTER_COLUMNS.map((col) => (
              <div key={col.title}>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  {col.title}
                </p>
                <ul className="mt-3 space-y-2">
                  {col.links.map((l) => (
                    <li key={l.href}>
                      <Link href={l.href}
                            className="text-[13px] text-muted-foreground transition-colors hover:text-foreground">
                        {l.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-10 flex flex-col gap-3 border-t border-border pt-6 text-[11.5px] leading-relaxed text-muted-foreground sm:flex-row sm:items-center sm:justify-between">
          <p>
            © {new Date().getFullYear()} RUNWAY. Built for INNOVASIA 2K26 · PS-04.
          </p>
          <p className="max-w-2xl sm:text-right">
            The workspace runs on synthetic data generated for demonstration.
            RUNWAY is not a credit rating and does not move money.
          </p>
        </div>
      </div>
    </footer>
  );
}

/* ── small shared section parts ───────────────────────────────── */

export function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-primary">
      {children}
    </p>
  );
}

export function SectionTitle({ children, sub, id }:
  { children: ReactNode; sub?: ReactNode; id?: string }) {
  return (
    <div id={id} className="max-w-2xl">
      <h2 className="font-display text-[26px] font-semibold leading-tight tracking-tight text-balance sm:text-3xl">
        {children}
      </h2>
      {sub && (
        <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground text-pretty">
          {sub}
        </p>
      )}
    </div>
  );
}

export function Section({ children, className, id }:
  { children: ReactNode; className?: string; id?: string }) {
  return (
    <section id={id} className={cn("mx-auto max-w-6xl px-5 py-16 sm:px-8 sm:py-20", className)}>
      {children}
    </section>
  );
}

export function FeatureCard({ icon, title, body }:
  { icon: ReactNode; title: string; body: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-5 transition-colors hover:border-border-strong">
      <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
        {icon}
      </span>
      <h3 className="mt-3.5 font-display text-[15px] font-semibold tracking-tight">{title}</h3>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-muted-foreground text-pretty">
        {body}
      </p>
    </div>
  );
}
