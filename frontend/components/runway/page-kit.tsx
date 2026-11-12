"use client";

/**
 * Shared page furniture.
 *
 * Every screen in the workspace uses the same header, the same tab bar and the
 * same disclosure control, so moving between screens costs no re-orientation.
 * The components exist to enforce two rules:
 *
 *   1. A page opens with one sentence, not a paragraph. Anything longer than a
 *      line lives behind <Reveal>.
 *   2. Every action that leaves the page (export, share, add) looks the same
 *      wherever it appears.
 */
import Link from "next/link";
import {
  type ReactNode, useCallback, useEffect, useId, useRef, useState,
} from "react";
import {
  Check, ChevronDown, ChevronRight, Copy, Download, ExternalLink, Info,
  Loader2, Plus, X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { cn } from "@/lib/utils";
import { EASE_OUT, SPRING } from "./motion";
import type { NavItem } from "./nav";

/* ── page header ──────────────────────────────────────────────── */

export function PageHeader({
  title, subtitle, actions, crumb, state, onBack,
}: {
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
  crumb?: ReactNode;
  state?: ReactNode;
  onBack?: () => void;
}) {
  return (
    <header className="mb-5">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="min-w-0">
          {crumb && (
            <div className="mb-1 flex items-center gap-1 text-xs text-muted-foreground">
              {crumb}
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2.5">
            {onBack && (
              <button onClick={onBack} aria-label="Back"
                      className="rounded-md p-1 text-muted-foreground hover:bg-surface-hover">
                <ChevronRight className="size-4 rotate-180" />
              </button>
            )}
            <h1 className="font-display text-[22px] font-semibold tracking-tight sm:text-2xl">
              {title}
            </h1>
            {state}
          </div>
          {subtitle && (
            <p className="mt-1 max-w-3xl text-[13px] leading-relaxed text-muted-foreground text-pretty">
              {subtitle}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
        )}
      </div>
    </header>
  );
}

/* ── tabs ─────────────────────────────────────────────────────── */

export type TabDef = { key: string; label: string; count?: number; icon?: any };

/**
 * Tabs instead of one long scroll. The workspace has more panels than fit on a
 * screen, and a page that is four viewports deep is a page where the second
 * half never gets read.
 *
 * The active tab is kept in the URL hash so a link to a screen lands on the
 * right pane and Back behaves the way a browser user expects.
 */
export function Tabs({
  tabs, active, onChange, className, storageKey,
}: {
  tabs: TabDef[];
  active: string;
  onChange: (k: string) => void;
  className?: string;
  /** Persist the choice per screen, so returning to a page keeps your place. */
  storageKey?: string;
}) {
  return (
    <div className={cn("rw-tabs", className)} role="tablist">
      {tabs.map((t) => {
        const Icon = t.icon;
        const on = t.key === active;
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={on}
            onClick={() => onChange(t.key)}
            className={cn("rw-tab", on && "is-active")}
          >
            {Icon && <Icon className="size-3.5 shrink-0" aria-hidden />}
            {t.label}
            {t.count !== undefined && t.count > 0 && (
              <span className="tnum rounded-full bg-surface px-1.5 py-px text-[10px] text-muted-foreground">
                {t.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Tabs with the selection held in a hash, so the choice is linkable. */
export function useTabs(storageKey: string, initial: string) {
  const [active, setActive] = useState(initial);
  useEffect(() => {
    const fromUrl = window.location.hash.replace("#", "");
    const fromStore = localStorage.getItem(`runway.tab.${storageKey}`);
    const want = fromUrl || fromStore || initial;
    if (want && want !== active) setActive(want);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);
  const set = useCallback((k: string) => {
    setActive(k);
    localStorage.setItem(`runway.tab.${storageKey}`, k);
    history.replaceState(null, "", `#${k}`);
  }, [storageKey]);
  return [active, set] as const;
}

/* ── progressive disclosure ───────────────────────────────────── */

/**
 * Methodology, provenance and long-form explanation live here. The answer is
 * always one line on screen; the reasoning is one click away for the person
 * who needs to audit it. (Named `Details` because `motion.tsx` already owns
 * `Reveal`, which is a scroll animation, not a disclosure.)
 */
export function Details({
  label = "How this is calculated", children, defaultOpen = false, dense = false,
}: {
  label?: string; children: ReactNode; defaultOpen?: boolean; dense?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={cn("rounded-lg border border-border", dense ? "bg-surface/40" : "bg-surface/60")}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={id}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronDown
          className={cn("size-3.5 transition-transform duration-200", !open && "-rotate-90")}
          aria-hidden
        />
        {label}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            id={id}
            initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: EASE_OUT }}
            className="overflow-hidden"
          >
            <div className={cn("border-t border-border px-3 py-2.5 text-xs leading-relaxed text-muted-foreground",
                               dense && "text-[11px]")}>
              {children}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/** One-line note: for the caveat that must never be hidden. */
export function Note({ children, tone = "muted" }:
  { children: ReactNode; tone?: "muted" | "warn" }) {
  return (
    <p className={cn("flex items-start gap-1.5 text-[11px] leading-relaxed",
      tone === "warn" ? "text-fin-warn" : "text-muted-foreground")}>
      <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
      <span className="text-pretty">{children}</span>
    </p>
  );
}

/* ── buttons ──────────────────────────────────────────────────── */

type BtnTone = "default" | "primary" | "ghost";

export function Button({
  children, onClick, href, icon, tone = "default", disabled, busy, size = "md",
  title, type = "button", className,
}: {
  children?: ReactNode; onClick?: () => void; href?: string; icon?: ReactNode;
  tone?: BtnTone; disabled?: boolean; busy?: boolean; size?: "sm" | "md";
  title?: string; type?: "button" | "submit"; className?: string;
}) {
  const cls = cn(
    "inline-flex items-center justify-center gap-1.5 rounded-lg font-medium transition-colors",
    "disabled:pointer-events-none disabled:opacity-50",
    size === "sm" ? "h-8 px-2.5 text-xs" : "h-9 px-3 text-[13px]",
    tone === "primary"
      ? "bg-primary text-primary-foreground hover:bg-primary/90"
      : tone === "ghost"
        ? "text-muted-foreground hover:bg-surface-hover hover:text-foreground"
        : "border border-border bg-surface text-foreground hover:bg-surface-hover",
    className);
  const body = (
    <>
      {busy ? <Loader2 className="size-3.5 animate-spin" aria-hidden /> : icon}
      {children}
    </>
  );
  if (href) {
    return href.startsWith("http")
      ? <a href={href} target="_blank" rel="noreferrer" className={cls} title={title}>{body}</a>
      : <Link href={href} className={cls} title={title}>{body}</Link>;
  }
  return (
    <button type={type} onClick={onClick} disabled={disabled || busy}
            className={cls} title={title}>{body}</button>
  );
}

/**
 * CSV download. The file is served with auth headers, so it is fetched here
 * and handed to the browser as a blob rather than opened as a link.
 */
export function ExportButton({
  path, filename, label = "Export CSV", size = "md", tone = "default",
}: {
  path: string; filename: string; label?: string; size?: "sm" | "md"; tone?: BtnTone;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function go() {
    setBusy(true); setErr(null);
    try {
      const res = await fetch(path, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem("runway.token") ?? ""}`,
          "X-Business-Id": localStorage.getItem("runway.business") ?? "",
        },
      });
      if (!res.ok) throw new Error(`Export failed (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e: any) {
      setErr(e?.message ?? "Export failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end">
      <Button onClick={go} busy={busy} size={size} tone={tone}
              icon={<Download className="size-3.5" />} title={err ?? `Download ${filename}`}>
        {label}
      </Button>
    </span>
  );
}

/** Copy-to-clipboard with a visible confirmation, then a revert. */
export function CopyButton({
  text, label = "Copy", size = "md", className, onCopied,
}: {
  text: string; label?: string; size?: "sm" | "md"; className?: string;
  onCopied?: () => void;
}) {
  const [done, setDone] = useState(false);
  async function go() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard API needs a secure context; fall back to a selectable prompt.
      window.prompt("Copy this message", text);
    }
    setDone(true);
    onCopied?.();
    setTimeout(() => setDone(false), 1600);
  }
  return (
    <Button onClick={go} size={size} className={className}
            icon={done ? <Check className="size-3.5 text-fin-gain" />
                       : <Copy className="size-3.5" />}>
      {done ? "Copied" : label}
    </Button>
  );
}

/* ── modal ────────────────────────────────────────────────────── */

export function Modal({
  open, onClose, title, subtitle, children, width = "max-w-lg",
}: {
  open: boolean; onClose: () => void; title: string; subtitle?: string;
  children: ReactNode; width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[100] flex items-end justify-center p-0 sm:items-center sm:p-6">
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            transition={{ duration: 0.15 }}
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onClose} aria-hidden
          />
          <motion.div
            role="dialog" aria-modal="true" aria-label={title}
            initial={{ opacity: 0, y: 20, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={SPRING}
            className={cn("relative flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-2xl border border-border bg-card shadow-2xl sm:rounded-2xl", width)}
          >
            <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-3.5">
              <div className="min-w-0">
                <h2 className="font-display text-[15px] font-semibold tracking-tight">{title}</h2>
                {subtitle && <p className="mt-0.5 text-xs text-muted-foreground">{subtitle}</p>}
              </div>
              <button onClick={onClose} aria-label="Close"
                      className="rounded-md p-1 text-muted-foreground hover:bg-surface-hover">
                <X className="size-4" />
              </button>
            </header>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
}

/* ── form fields ──────────────────────────────────────────────── */

export function Field({ label, hint, children, required }:
  { label: string; hint?: string; children: ReactNode; required?: boolean }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted-foreground">
        {label}{required && <span className="ml-0.5 text-fin-loss">*</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] text-muted-foreground/80">{hint}</span>}
    </label>
  );
}

export const inputCls =
  "h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm outline-none " +
  "transition-colors placeholder:text-muted-foreground/60 focus:border-primary/60";

export function Select({ value, onChange, options, className }:
  { value: string; onChange: (v: string) => void;
    options: { value: string; label: string }[]; className?: string }) {
  return (
    <select value={value} onChange={(e) => onChange(e.target.value)}
            className={cn(inputCls, "pr-8", className)}>
      {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  );
}

/* ── layout helpers ───────────────────────────────────────────── */

export function Grid({ children, cols = 4, className }:
  { children: ReactNode; cols?: 2 | 3 | 4; className?: string }) {
  return (
    <div className={cn("grid gap-3",
      cols === 2 && "sm:grid-cols-2",
      cols === 3 && "sm:grid-cols-2 xl:grid-cols-3",
      cols === 4 && "grid-cols-2 xl:grid-cols-4",
      className)}>
      {children}
    </div>
  );
}

export function Stack({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("space-y-4", className)}>{children}</div>;
}

/** Compact key/value rows, for the "show me the inputs" panel. */
export function Rows({ items }: { items: { k: string; v: ReactNode }[] }) {
  return (
    <dl className="divide-y divide-border/60 text-xs">
      {items.map((r, i) => (
        <div key={i} className="flex items-baseline justify-between gap-4 py-1.5">
          <dt className="shrink-0 text-muted-foreground">{r.k}</dt>
          <dd className="min-w-0 text-right tnum">{r.v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function PlusIcon() { return <Plus className="size-3.5" />; }
export function ExternalIcon() { return <ExternalLink className="size-3.5" />; }
