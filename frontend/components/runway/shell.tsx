"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowUpRight, Bell, Check, ChevronDown, ChevronsLeft, ChevronsRight,
  Command, LogOut, Menu, MessageCircle, Moon, Search, Sun, X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { GROUPS, NAV, navForRole, type NavItem } from "./nav";
import { Logo } from "./brand";
import { api, session } from "@/lib/api";
import { useApi } from "@/lib/use-api";
import { longDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { SPRING, EASE_OUT } from "./motion";

export { Logo };

type Me = {
  user: { id: string; email: string; full_name: string; is_accountant: boolean };
  businesses: { id: string; name: string; industry: string; role: string;
                is_demo: boolean; demo_scenario: string | null }[];
  active_business_id: string | null;
  pending_memberships?: any[];
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [theme, setTheme] = useState<"dark" | "light">("light");

  const me = useApi<Me>("/api/auth/me");
  const overview = useApi<any>("/api/overview");

  useEffect(() => {
    const saved = (localStorage.getItem("runway.theme") as "dark" | "light") || "light";
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
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    document.documentElement.dataset.theme = next;
    localStorage.setItem("runway.theme", next);
  };

  const toggleCollapse = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("runway.sidebar", next ? "collapsed" : "open");
  };

  // A signed-in user with no approved business is waiting for approval.
  useEffect(() => {
    if (me.data && !me.data.active_business_id) router.replace("/pending");
  }, [me.data, router]);

  const role = useMemo(() => {
    const id = session.businessId ?? me.data?.active_business_id;
    return me.data?.businesses.find((b) => b.id === id)?.role ?? me.data?.businesses[0]?.role;
  }, [me.data]);

  const items = useMemo(
    () => navForRole(role, !!me.data?.user?.is_accountant), [role, me.data]);

  const alerts = overview.data?.alerts_count ?? {};
  const alertCount = (alerts.critical ?? 0) + (alerts.warning ?? 0);
  const recCount = overview.data?.recommendations?.length ?? 0;
  const current = items.find((i) => i.href === pathname);

  const signOut = () => { session.clear(); router.push("/login"); };

  return (
    <div className="flex min-h-dvh bg-paper">
      {/* ── paper rail, forest active state ── */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[264px] flex-col border-r border-line bg-paper duration-300 lg:static lg:sticky lg:top-0 lg:h-screen",
          "transition-[transform,width]",
          collapsed && "lg:w-[72px]",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0")}
        aria-label="Main navigation"
      >
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-line px-5">
          <Link href="/app" className="min-w-0"><Logo compact={collapsed} /></Link>
          <button onClick={() => setMobileOpen(false)}
                  className="rounded-xl p-1 text-ink-3 hover:bg-paper-2 lg:hidden"
                  aria-label="Close navigation">
            <X className="size-4" />
          </button>
          {!collapsed && (
            <span className="hidden text-[11px] font-semibold text-ink-3 lg:inline">Workspace</span>
          )}
        </div>

        <BusinessSwitcher me={me.data} collapsed={collapsed} />

        <nav className="flex-1 overflow-y-auto px-3 pb-6" aria-label="App">
          {GROUPS.map((group) => {
            const groupItems = items.filter((i) => i.group === group);
            if (!groupItems.length) return null;
            return (
              <div key={group} className="mt-6 first:mt-4">
                {!collapsed && (
                  <p className="px-3 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
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

        <div className="border-t border-line p-3">
          <Link href="/"
                className="mb-1 hidden items-center gap-2 rounded-xl px-3 py-2 text-[12px] text-ink-2 hover:bg-white hover:text-ink lg:flex">
            <ArrowUpRight className="size-3.5" />
            {!collapsed && "Product site"}
          </Link>
          <button onClick={toggleCollapse}
                  className="hidden w-full items-center gap-2.5 rounded-xl px-3 py-2 text-[12px] text-ink-2 hover:bg-white hover:text-ink lg:flex">
            {collapsed ? <ChevronsRight className="size-4" /> : <ChevronsLeft className="size-4" />}
            {!collapsed && "Collapse rail"}
          </button>
          <UserCard me={me.data} collapsed={collapsed} onSignOut={signOut} />
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-40 bg-ink/40 lg:hidden"
             onClick={() => setMobileOpen(false)} aria-hidden />
      )}

      {/* ── main ── */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-paper/90 px-4 backdrop-blur sm:px-8">
          <button onClick={() => setMobileOpen(true)}
                  className="grid size-10 place-items-center rounded-xl border border-line bg-card lg:hidden"
                  aria-label="Open navigation">
            <Menu className="size-5" />
          </button>
          <p className="hidden text-sm font-semibold text-ink-2 sm:block">
            {current?.label ?? "Runway"}
          </p>
          <button onClick={() => setPaletteOpen(true)}
                  className="flex h-9 flex-1 items-center gap-2 rounded-full border border-line bg-card px-3 text-[13px] text-ink-3 transition-colors hover:bg-white sm:max-w-xs">
            <Search className="size-4" />
            <span className="flex-1 text-left">Search or jump to…</span>
            <kbd className="rw-kbd hidden sm:inline-flex"><Command className="size-2.5" />K</kbd>
          </button>
          <div className="ml-auto flex items-center gap-2">
            <AsOfPill asOf={overview.data?.as_of} />
            <Link href="/app/risk"
                  className="relative grid size-9 place-items-center rounded-full text-ink-3 hover:bg-white hover:text-ink"
                  aria-label={`${alertCount} open alerts`}>
              <Bell className="size-4" />
              {alertCount > 0 && (
                <span className="absolute right-0.5 top-0.5 grid size-4 place-items-center rounded-full bg-loss text-[9px] font-semibold text-white">
                  {alertCount > 9 ? "9+" : alertCount}
                </span>
              )}
            </Link>
            <button onClick={toggleTheme}
                    className="grid size-9 place-items-center rounded-full text-ink-3 hover:bg-white hover:text-ink"
                    aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}>
              {theme === "light" ? <Moon className="size-4" /> : <Sun className="size-4" />}
            </button>
            <Link href="/app/copilot" className="btn btn-primary btn-sm hidden md:inline-flex">
              <MessageCircle className="size-4" /> Ask a question
            </Link>
          </div>
        </header>

        <span key={`bar-${pathname}`} className="rw-route-bar" aria-hidden />

        <main className="relative min-w-0 flex-1 rw-noise">
          <div key={pathname} className="rw-stage mx-auto w-full max-w-[1180px] px-4 py-8 sm:px-8 sm:py-10">
            {pathname !== "/app" && <RouteContext pathname={pathname} items={items} />}
            {children}
          </div>
        </main>

      </div>

      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} items={items} />
    </div>
  );
}

/* One shared page context line across all twenty-one authenticated screens. */
function RouteContext({ pathname, items }: { pathname: string; items: NavItem[] }) {
  const item = items.find((i) => i.href === pathname);
  if (!item) return null;
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-2.5 text-[12px]">
        <span className="eyebrow">{item.group}</span>
        <span className="text-line-2">/</span>
        <span className="font-semibold text-ink">{item.label}</span>
      </div>
      <p className="hidden text-[13px] text-ink-2 sm:block">{item.blurb}</p>
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
          "group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition",
          active ? "bg-forest text-white" : "text-ink-2 hover:bg-white hover:text-ink")}
      >
        {active && (
          <motion.span layoutId="nav-active" transition={SPRING}
                       className="absolute inset-y-2 left-0 w-1 rounded-full bg-lime" aria-hidden />
        )}
        <Icon className={cn("size-[18px] shrink-0", active ? "text-lime" : "text-ink-3")} aria-hidden />
        {!collapsed && <span className="truncate">{item.label}</span>}
        {!collapsed && badge > 0 && (
          <span className={cn("ml-auto rounded-full px-1.5 py-0.5 text-[10px] font-semibold tnum",
            active ? "bg-white/15 text-white" : "bg-paper-2 text-ink-3")}>
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
    return <div className="mx-3 mb-5 h-12 rw-shimmer rounded-xl bg-paper-2" />;
  }
  const pick = (id: string) => { session.setBusiness(id); window.location.reload(); };
  return (
    <div className="relative mx-3 mb-5">
      <button onClick={() => setOpen((v) => !v)}
              className="flex w-full items-center gap-2.5 rounded-xl border border-line bg-card px-3.5 py-3 text-left hover:border-forest-3"
              aria-expanded={open} aria-haspopup="listbox">
        <span className="grid size-7 shrink-0 place-items-center rounded-lg bg-sage text-[11px] font-bold text-forest">
          {active.name.slice(0, 2).toUpperCase()}
        </span>
        {!collapsed && (
          <>
            <span className="min-w-0 flex-1">
              <span className="block text-[11px] font-semibold text-ink-3">Business</span>
              <span className="block truncate text-sm font-semibold text-ink">{active.name}</span>
            </span>
            <ChevronDown className="size-3.5 shrink-0 text-ink-3" />
          </>
        )}
      </button>
      <AnimatePresence>
        {open && (
          <motion.ul
            initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.16 }} role="listbox"
            className="absolute inset-x-0 top-full z-50 mt-1 overflow-hidden rounded-xl border border-line bg-card p-1 shadow-xl">
            {me.businesses.map((b) => (
              <li key={b.id}>
                <button onClick={() => pick(b.id)} role="option" aria-selected={b.id === active.id}
                        className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[12.5px] text-ink hover:bg-paper-2">
                  <span className="min-w-0 flex-1 truncate">{b.name}</span>
                  {b.id === active.id && <Check className="size-3.5 text-forest-3" />}
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
    <div className="flex items-center gap-3 rounded-xl px-2 py-2">
      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-lime text-[12px] font-bold text-forest">
        {me.user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("")}
      </span>
      {!collapsed && (
        <>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-ink">{me.user.full_name}</span>
            <span className="block truncate text-[11px] capitalize text-ink-3">{me.user.email}</span>
          </span>
          <button onClick={onSignOut} aria-label="Sign out" title="Sign out"
                  className="grid size-9 place-items-center rounded-lg text-ink-3 hover:bg-white hover:text-ink">
            <LogOut className="size-4" />
          </button>
        </>
      )}
    </div>
  );
}

function AsOfPill({ asOf }: { asOf?: string }) {
  if (!asOf) return null;
  return (
    <span className="hidden items-center gap-1.5 rounded-full border border-line bg-card px-3.5 py-1.5 text-[12px] font-medium text-ink-2 sm:inline-flex"
          title="Everything on screen is evaluated as of this date">
      <span className="size-1.5 rounded-full bg-gain" aria-hidden />
      Books as of {longDate(asOf)}
    </span>
  );
}

function DemoRibbon({ scenario }: { scenario: string | null }) {
  return (
    <div className="sticky bottom-0 z-20 border-t border-warn/20 bg-warn/10 px-4 py-1.5 text-center text-[11px] font-medium text-warn backdrop-blur">
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
    <div className="fixed inset-0 z-[100] flex items-start justify-center bg-ink/40 p-4 pt-[12vh] backdrop-blur-sm"
         onClick={onClose} role="dialog" aria-modal="true" aria-label="Command palette">
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: -8 }} animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.18, ease: EASE_OUT }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-xl overflow-hidden rounded-2xl border border-line bg-card shadow-2xl">
        <div className="flex items-center gap-2 border-b border-line px-4">
          <Search className="size-4 text-ink-3" />
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="Jump to a screen…"
                 className="h-12 flex-1 bg-transparent text-sm outline-none placeholder:text-ink-3" />
          <kbd className="rw-kbd">esc</kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto p-1.5">
          {filtered.length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-ink-3">No match</li>
          )}
          {filtered.map((i) => {
            const Icon = i.icon;
            return (
              <li key={i.href}>
                <button onClick={() => { router.push(i.href); onClose(); }}
                        className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left hover:bg-paper-2">
                  <Icon className="size-4 shrink-0 text-ink-3" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">{i.label}</span>
                    <span className="block truncate text-xs text-ink-3">{i.blurb}</span>
                  </span>
                  <span className="shrink-0 text-[10px] uppercase tracking-wide text-ink-3/70">{i.group}</span>
                </button>
              </li>
            );
          })}
        </ul>
      </motion.div>
    </div>
  );
}
