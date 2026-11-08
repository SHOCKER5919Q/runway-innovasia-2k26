"use client";

import { type ReactNode } from "react";
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Info, Minus } from "lucide-react";
import { STATE_META, type StateKey, TONE_CLASS } from "@/lib/format";
import { cn } from "@/lib/utils";

/* ── state badge ─────────────────────────────────────────────── */

export function StateBadge({ state, size = "sm", withBlurb = false }:
  { state: StateKey | string; size?: "sm" | "md"; withBlurb?: boolean }) {
  const meta = (STATE_META as any)[state];
  if (!meta) return null;
  return (
    <span
      className={cn("rw-chip", size === "md" && "px-3 py-1.5 text-xs")}
      style={{ color: meta.color, background: meta.soft, borderColor: meta.soft }}
      title={meta.blurb}
    >
      <span aria-hidden className="inline-block size-1.5 rounded-full" style={{ background: meta.color }} />
      {meta.label}
      {withBlurb && <span className="text-muted-foreground font-normal"> · {meta.blurb}</span>}
    </span>
  );
}

/* ── delta ───────────────────────────────────────────────────── */

export function Delta({ value, suffix = "", betterWhen = "higher", className }:
  { value: number; suffix?: string; betterWhen?: "higher" | "lower"; className?: string }) {
  const good = value === 0 ? null : betterWhen === "higher" ? value > 0 : value < 0;
  const Icon = value === 0 ? Minus : value > 0 ? ArrowUpRight : ArrowDownRight;
  const tone = good === null ? "neutral" : good ? "gain" : "loss";
  return (
    <span className={cn("inline-flex items-center gap-0.5 text-xs font-medium tnum",
      TONE_CLASS[tone], className)}>
      <Icon className="size-3.5" aria-hidden />
      {Math.abs(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}{suffix}
      <span className="sr-only">{good === null ? "unchanged" : good ? "improved" : "worse"}</span>
    </span>
  );
}

/* ── stat tile ───────────────────────────────────────────────── */

export function Stat({
  label, value, sub, icon, tone = "neutral", state, hint, footer, className, onClick,
}: {
  label: string; value: ReactNode; sub?: ReactNode; icon?: ReactNode;
  tone?: "neutral" | "gain" | "loss" | "warn" | "info";
  state?: StateKey; hint?: string; footer?: ReactNode; className?: string;
  onClick?: () => void;
}) {
  const Tag: any = onClick ? "button" : "div";
  return (
    <Tag
      onClick={onClick}
      title={hint}
      className={cn(
        "rw-card group relative overflow-hidden p-4 text-left duration-300",
        "transition-[border-color,background-color,transform,box-shadow]",
        "hover:border-border-strong",
        onClick && "hover:bg-surface-hover focus-visible:bg-surface-hover cursor-pointer",
        className)}
    >
      {/* A tinted top edge keyed to the tile's tone — the glow line in the
          reference boards. Decorative, and never the only cue. */}
      <span aria-hidden className={cn(
        "pointer-events-none absolute inset-x-0 top-0 h-px opacity-0 transition-opacity duration-300 group-hover:opacity-100",
        tone === "gain" ? "bg-fin-gain" : tone === "loss" ? "bg-fin-loss"
          : tone === "warn" ? "bg-fin-warn" : "bg-primary")} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="truncate text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {label}
            </p>
            {hint && <Info className="size-3 shrink-0 text-muted-foreground/60" aria-hidden />}
          </div>
          <p className={cn("mt-1.5 font-display text-2xl font-semibold tracking-tight tnum",
            TONE_CLASS[tone])}>
            {value}
          </p>
          {sub && <div className="mt-1 text-xs text-muted-foreground">{sub}</div>}
        </div>
        {icon && (
          <span className="grid size-9 shrink-0 place-items-center rounded-lg border border-border bg-surface text-muted-foreground">
            {icon}
          </span>
        )}
      </div>
      {(state || footer) && (
        <div className="mt-3 flex items-center justify-between gap-2 border-t border-border pt-2.5">
          {state ? <StateBadge state={state} /> : <span />}
          {footer}
        </div>
      )}
    </Tag>
  );
}

/* ── section header ──────────────────────────────────────────── */

export function SectionHeader({ title, description, actions, id }:
  { title: string; description?: ReactNode; actions?: ReactNode; id?: string }) {
  return (
    <div id={id} className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <h2 className="font-display text-lg font-semibold tracking-tight">{title}</h2>
        {description && (
          <p className="mt-0.5 max-w-3xl text-sm text-muted-foreground text-pretty">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, description, actions, children, className, bodyClass, id }:
  { title?: string; description?: ReactNode; actions?: ReactNode; children: ReactNode;
    className?: string; bodyClass?: string; id?: string }) {
  return (
    <section id={id} className={cn("rw-card flex flex-col overflow-hidden", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div className="min-w-0">
            {title && <h3 className="font-display text-sm font-semibold tracking-tight">{title}</h3>}
            {description && (
              <p className="mt-0.5 max-w-2xl text-xs text-muted-foreground text-pretty">{description}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("flex-1 p-4", bodyClass)}>{children}</div>
    </section>
  );
}

/* ── level pill ──────────────────────────────────────────────── */

const LEVEL_STYLE: Record<string, { cls: string; label: string }> = {
  critical: { cls: "text-fin-loss bg-fin-loss-soft border-fin-loss/30", label: "Critical" },
  warning: { cls: "text-fin-warn bg-fin-warn-soft border-fin-warn/30", label: "Warning" },
  watch: { cls: "text-fin-info bg-fin-info-soft border-fin-info/30", label: "Watch" },
  info: { cls: "text-muted-foreground bg-surface border-border", label: "Info" },
};

export function LevelPill({ level }: { level: string }) {
  const s = LEVEL_STYLE[level] ?? LEVEL_STYLE.info;
  return (
    <span className={cn("rw-chip uppercase tracking-wide", s.cls)}>
      {level === "critical" && <AlertTriangle className="size-3" aria-hidden />}
      {s.label}
    </span>
  );
}

export function RiskBand({ band }: { band: string }) {
  const map: Record<string, string> = {
    low: "text-fin-gain bg-fin-gain-soft border-fin-gain/30",
    medium: "text-fin-warn bg-fin-warn-soft border-fin-warn/30",
    high: "text-fin-loss bg-fin-loss-soft border-fin-loss/30",
    critical: "text-fin-loss bg-fin-loss-soft border-fin-loss/50 font-semibold",
    unknown: "text-muted-foreground bg-surface border-border",
  };
  return <span className={cn("rw-chip capitalize", map[band] ?? map.unknown)}>{band}</span>;
}

/* ── evidence list ───────────────────────────────────────────── */

export function Evidence({ items, dense = false }:
  { items: { label: string; value: string }[]; dense?: boolean }) {
  if (!items?.length) return null;
  return (
    <dl className={cn("grid gap-x-4 gap-y-1.5", dense ? "text-xs" : "text-sm")}>
      {items.map((e, i) => (
        <div key={i} className="flex items-start justify-between gap-4 border-b border-border/60 pb-1.5 last:border-0">
          <dt className="shrink-0 text-muted-foreground">{e.label}</dt>
          <dd className="min-w-0 text-right tnum">{e.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ── loading / empty / error ─────────────────────────────────── */

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("rw-shimmer rounded-md bg-surface", className)} />;
}

export function LoadingPanel({ rows = 3, title }: { rows?: number; title?: string }) {
  return (
    <div className="rw-card space-y-3 p-4" role="status" aria-live="polite">
      <span className="sr-only">{title ? `Loading ${title}` : "Loading"}</span>
      <Skeleton className="h-4 w-40" />
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({ title, description, action, icon }:
  { title: string; description?: string; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border px-6 py-12 text-center">
      {icon && <span className="grid size-10 place-items-center rounded-full bg-surface text-muted-foreground">{icon}</span>}
      <div>
        <p className="font-medium">{title}</p>
        {description && <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground text-pretty">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="rw-card border-fin-loss/30 p-4" role="alert">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-fin-loss" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium">Could not load this section</p>
          <p className="mt-0.5 break-words text-xs text-muted-foreground">{message}</p>
        </div>
        {onRetry && (
          <button onClick={onRetry}
            className="shrink-0 rounded-md border border-border px-2.5 py-1 text-xs hover:bg-surface-hover">
            Retry
          </button>
        )}
      </div>
    </div>
  );
}

/* ── provenance note ─────────────────────────────────────────── */

export function Provenance({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-relaxed text-muted-foreground">
      <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
      <span className="text-pretty">{children}</span>
    </p>
  );
}
