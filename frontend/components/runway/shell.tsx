"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  Bell, Check, ChevronDown, ChevronsLeft, ChevronsRight, CircleHelp, Command,
  LogOut, Menu, Moon, Search, Sun, X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { ACCOUNTANT_NAV, GROUPS, NAV, type NavItem } from "./nav";
import { LevelPill, StateBadge } from "./primitives";
import { api, session } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { longDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { SPRING, EASE_OUT } from "./motion";

type Me = {
  user: { id: string; email: string; full_name: string; is_accountant: boolean };
  businesses: { id: string; name: string; industry: string; role: string;
                is_demo: boolean; demo_scenario: string | null }[];
  active_business_id: string | null;
};

export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="relative grid size-8 shrink-0 place-items-center rounded-lg bg-primary/15 ring-1 ring-primary/30">
        <svg viewBox="0 0 24 24" className="size-4.5" aria-hidden>
          <path d="M3 18 L9 12 L13 15 L21 6" fill="none" stroke="var(--primary)"
                strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="21" cy="6" r="2.2" fill="var(--primary)" />
        </svg>
      </span>
      {!compact && (
        <span className="font-display text-[15px] font-semibold tracking-tight">RUNWAY</span>
      )}
    </span>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("dark");

  const me = useApi<Me>("/api/auth/me");
  const overview = useApi<any>("/api/overview");

  useEffect(() => {
    const saved = (localStorage.getItem("runway.theme") as "dark" | "light") || "dark";
    setTheme(saved);
    document.documentElement.dataset.theme = saved;
    setCollapsed(localStorage.getItem("runway.sidebar") === "collapsed");
  }, []);

  useEffect(() => { setMobileOpen(false); }, [pathname]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault(); setPaletteOpen((v) => !v);
      }
      if (e.key === "Escape") setPaletteOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    localStorage.setItem("runway.theme", next);
  };

  const toggleCollapse = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("runway.sidebar", next ? "collapsed" : "open");
  };

  const items = useMemo(() => {
    const base = [...NAV];
    if (me.data?.user?.is_accountant) base.push(ACCOUNTANT_NAV);
    return base;
  }, [me.data]);

  const alerts = overview.data?.alerts_count ?? {};
  const alertCount = (alerts.critical ?? 0) + (alerts.warning ?? 0);
  const recCount = overview.data?.recommendations?.length ?? 0;

  const signOut = () => { session.clear(); router.push("/login"); };

  return (
    <div className="flex min-h-dvh bg-background">
      {/* ── sidebar ── */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[264px] flex-col border-r border-sidebar-border bg-sidebar duration-300 lg:static",
          "transition-[transform,opacity]",
          collapsed && "lg:w-[72px]",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0")}
        aria-label="Main navigation"
      >
        <div className="flex h-14 items-center justify-between px-4">
          <Link href="/app" className="min-w-0"><Logo compact={collapsed} /></Link>
          <button onClick={() => setMobileOpen(false)}
                  className="rounded-md p-1 text-muted-foreground hover:bg-sidebar-accent lg:hidden"
                  aria-label="Close navigation">
            <X className="size-4" />
          </button>
        </div>

        <BusinessSwitcher me={me.data} collapsed={collapsed} />

        <nav className="flex-1 overflow-y-auto px-2 pb-3">
          {GROUPS.map((group) => {
            const groupItems = items.filter((i) => i.group === group);
            if (!groupItems.length) return null;
            return (
              <div key={group} className="mt-4 first:mt-1">
                {!collapsed && (
                  <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground/70">
                    {group}
                  </p>
                )}
                <ul className="space-y-0.5">
                  {groupItems.map((item) => (
                    <NavLink key={item.href} item={item} collapsed={collapsed}
                             active={pathname === item.href}
                             badge={item.badge === "alerts" ? alertCount
                                    : item.badge === "recs" ? recCount : 0} />
                  ))}
                </ul>
              </div>
            );
          })}
        </nav>

        <div className="border-t border-sidebar-border p-2">
          <button onClick={toggleCollapse}
                  className="hidden w-full items-center gap-2.5 rounded-md px-3 py-2 text-xs text-muted-foreground hover:bg-sidebar-accent lg:flex">
            {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
            {!collapsed && "Collapse"}
          </button>
          <UserCard me={me.data} collapsed={collapsed} onSignOut={signOut} />
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
             onClick={() => setMobileOpen(false)} aria-hidden />
      )}

      {/* ── main ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border bg-background/85 px-4 backdrop-blur-md">
          <button onClick={() => setMobileOpen(true)}
                  className="rounded-md p-1.5 text-muted-foreground hover:bg-surface-hover lg:hidden"
                  aria-label="Open navigation">
            <Menu className="size-5" />
          </button>
          <button onClick={() => setPaletteOpen(true)}
                  className="flex h-9 flex-1 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-sm text-muted-foreground transition-colors hover:bg-surface-hover sm:max-w-sm">
            <Search className="size-4" />
            <span className="flex-1 text-left">Search or jump to…</span>
            <kbd className="rw-kbd hidden sm:inline-flex"><Command className="size-2.5" />K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-1.5">
            <AsOfPill asOf={overview.data?.as_of} />
            <Link href="/app/risk"
                  className="relative rounded-md p-2 text-muted-foreground hover:bg-surface-hover"
                  aria-label={`${alertCount} open alerts`}>
              <Bell className="size-4" />
              {alertCount > 0 && (
                <span className="absolute right-1 top-1 grid size-4 place-items-center rounded-full bg-fin-loss text-[9px] font-semibold text-white">
                  {alertCount > 9 ? "9+" : alertCount}
                </span>
              )}
            </Link>
            <button onClick={toggleTheme}
                    className="rounded-md p-2 text-muted-foreground hover:bg-surface-hover"
                    aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
              {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
          </div>
        </header>

        {/* Remounted on every navigation, so the bar runs its one sweep
            and then removes itself. No timers, no state to get stuck. */}
        <span key={`bar-${pathname}`} className="rw-route-bar" aria-hidden />

        <main className="min-w-0 flex-1">
          <div
            key={pathname}
            /* rw-stage cascades this screen's sections in. The wrapper no
               longer fades as one block — the children do it themselves,
               which is what makes a screen assemble rather than appear. */
            className="rw-stage mx-auto w-full max-w-[1600px] px-4 py-5 sm:px-6 lg:px-8"
          >
            {children}
          </div>
        </main>

        {overview.data?.business?.is_demo && <DemoRibbon scenario={overview.data.business.demo_scenario} />}
      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} items={items} />
    </div>
  );
}

function NavLink({ item, collapsed, active, badge }:
  { item: NavItem; collapsed: boolean; active: boolean; badge: number }) {
  const Icon = item.icon;
  return (
    <li>
      <Link
        href={item.href}
        title={collapsed ? `${item.label} — ${item.blurb}` : item.blurb}
        aria-current={active ? "page" : undefined}
        className={cn(
          "group relative flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
          active
            ? "bg-sidebar-accent font-medium text-sidebar-accent-foreground"
            : "text-muted-foreground hover:bg-sidebar-accent/60 hover:text-sidebar-foreground")}
      >
        {active && (
          <motion.span layoutId="nav-active" transition={SPRING}
                       className="absolute inset-y-1 left-0 w-0.5 rounded-full bg-primary" aria-hidden />
        )}
        <Icon className={cn("size-4 shrink-0", active && "text-primary")} aria-hidden />
        {!collapsed && <span className="truncate">{item.label}</span>}
        {!collapsed && badge > 0 && (
          <span className="ml-auto rounded-full bg-surface px-1.5 py-0.5 text-[10px] font-medium tnum text-muted-foreground">
            {badge}
          </span>
        )}
      </Link>
    </li>
  );
}

function BusinessSwitcher({ me, collapsed }: { me: Me | null; collapsed: boolean }) {
  const [open, setOpen] = useState(false);
  const active = me?.businesses.find((b) => b.id === session.businessId) ?? me?.businesses[0];
  if (!me || !active) {
    return <div className="mx-2 mb-1 h-12 rw-shimmer rounded-lg bg-sidebar-accent/40" />;
  }
  const pick = (id: string) => { session.setBusiness(id); window.location.reload(); };
  return (
    <div className="relative mx-2 mb-1">
      <button onClick={() => setOpen((v) => !v)}
              className="flex w-full items-center gap-2.5 rounded-lg border border-sidebar-border bg-sidebar-accent/40 px-2.5 py-2 text-left hover:bg-sidebar-accent"
              aria-expanded={open} aria-haspopup="listbox">
        <span className="grid size-7 shrink-0 place-items-center rounded-md bg-primary/15 text-[11px] font-semibold text-primary">
          {active.name.slice(0, 2).toUpperCase()}
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px] font-medium">{active.name}</span>
              <span className="block truncate text-[11px] capitalize text-muted-foreground">
                {active.industry.replace(/_/g, " ")} · {active.role}
              </span>
            </span>
            <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
          </>
        )}
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul
            initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.16 }} role="listbox"
            className="absolute inset-x-0 top-full z-50 mt-1 overflow-hidden rounded-lg border border-border bg-popover p-1 shadow-xl">
            {me.businesses.map((b) => (
              <li key={b.id}>
                <button onClick={() => pick(b.id)} role="option" aria-selected={b.id === active.id}
                        className="flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-[13px] hover:bg-surface-hover">
                  <span className="min-w-0 flex-1 truncate">{b.name}</span>
                  {b.id === active.id && <Check className="size-3.5 text-primary" />}
                </button>
              </li>
            ))}
          </motion.ul>
        )}
      </AnimatePresence>
    </div>
  );
}

function UserCard({ me, collapsed, onSignOut }:
  { me: Me | null; collapsed: boolean; onSignOut: () => void }) {
  if (!me) return null;
  return (
    <div className="flex items-center gap-2.5 rounded-md px-2 py-2">
      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface text-[11px] font-semibold">
        {me.user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
      </span>
      {!collapsed && (
        <>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-[12px] font-medium">{me.user.full_name}</span>
            <span className="block truncate text-[10px] text-muted-foreground">{me.user.email}</span>
          </span>
          <button onClick={onSignOut} aria-label="Sign out"
                  className="rounded p-1 text-muted-foreground hover:bg-sidebar-accent hover:text-foreground">
            <LogOut className="size-3.5" />
          </button>
        </>
      )}
    </div>
  );
}

function AsOfPill({ asOf }: { asOf?: string }) {
  if (!asOf) return null;
  return (
    <span className="hidden items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1.5 text-[11px] text-muted-foreground sm:inline-flex"
          title="Everything on screen is evaluated as of this date">
      <span className="size-1.5 rounded-full bg-fin-gain" aria-hidden />
      As of {longDate(asOf)}
    </span>
  );
}

function DemoRibbon({ scenario }: { scenario: string | null }) {
  return (
    <div className="sticky bottom-0 z-20 border-t border-fin-warn/25 bg-fin-warn-soft px-4 py-1.5 text-center text-[11px] text-fin-warn backdrop-blur">
      Demonstration workspace — every figure is computed from <strong>synthetic</strong> data
      {scenario ? ` (scenario ${scenario})` : ""}. No real business is described here.
    </div>
  );
}

function CommandPalette({ open, onClose, items }:
  { open: boolean; onClose: () => void; items: NavItem[] }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const filtered = items.filter((i) =>
    `${i.label} ${i.blurb} ${i.group}`.toLowerCase().includes(q.toLowerCase()));
  useEffect(() => { if (!open) setQ(""); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-start justify-center bg-black/60 p-4 pt-[12vh] backdrop-blur-sm"
         onClick={onClose} role="dialog" aria-modal="true" aria-label="Command palette">
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: -8 }} animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.18, ease: EASE_OUT }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl overflow-hidden rounded-xl border border-border bg-popover shadow-2xl">
        <div className="flex items-center gap-2 border-b border-border px-4">
          <Search className="size-4 text-muted-foreground" />
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="Jump to a screen…"
                 className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
          <kbd className="rw-kbd">esc</kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto p-1.5">
          {filtered.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">No match</li>
          )}
          {filtered.map((i) => {
            const Icon = i.icon;
            return (
              <li key={i.href}>
                <button onClick={() => { router.push(i.href); onClose(); }}
                        className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left hover:bg-surface-hover">
                  <Icon className="size-4 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm">{i.label}</span>
                    <span className="block truncate text-xs text-muted-foreground">{i.blurb}</span>
                  </span>
                  <span className="shrink-0 text-[10px] uppercase tracking-wide text-muted-foreground/70">
                    {i.group}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </motion.div>
    </div>
  );
}
