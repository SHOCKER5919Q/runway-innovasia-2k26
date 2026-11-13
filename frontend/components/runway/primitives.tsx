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
      className={cn("pill", size === "md" && "px-3 py-1.5 text-xs")}
      style={{ color: meta.color, background: meta.soft, borderColor: meta.soft }}
      title={meta.blurb}
    >
      <span aria-hidden className="inline-block size-1.5 rounded-full" style={{ background: meta.color }} />
      {meta.label}
      {withBlurb && <span className="font-normal text-ink-2"> · {meta.blurb}</span>}
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
    <span className={cn("inline-flex items-center gap-0.5 text-xs font-semibold tnum",
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
        "card group relative p-5 text-left transition-[border-color,background-color,transform]",
        "hover:border-line-2",
        onClick && "cursor-pointer hover:bg-paper-2 focus-visible:bg-paper-2",
        className)}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <p className="truncate text-[13px] font-medium text-ink-3">{label}</p>
            {hint && <Info className="size-3 shrink-0 text-ink-3/70" aria-hidden />}
          </div>
          <p className={cn("num mt-2 text-[28px] font-semibold leading-none tracking-[-0.03em]",
            TONE_CLASS[tone])}>
            {value}
          </p>
          {sub && <div className="mt-2.5 text-[13px] leading-snug text-ink-2">{sub}</div>}
        </div>
        {icon && (
          <span className="grid size-12 shrink-0 place-items-center rounded-2xl bg-sage text-forest">
            {icon}
          </span>
        )}
      </div>
      {(state || footer) && (
        <div className="mt-4 flex items-center justify-between gap-2 border-t border-line pt-3">
          {state ? <StateBadge state={state} /> : <span />}
          {footer}
        </div>
      )}
    </Tag>
  );
}

/* ── page / section header ───────────────────────────────────── */

export function SectionHeader({ title, description, actions, id }:
  { title: string; description?: ReactNode; actions?: ReactNode; id?: string }) {
  return (
    <div id={id} className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h1 className="display text-[28px] leading-tight sm:text-[32px]">{title}</h1>
        {description && (
          <p className="mt-1.5 text-[15px] leading-relaxed text-ink-2 text-pretty">{description}</p>
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
    <section id={id} className={cn("card flex flex-col overflow-hidden", className)}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-4 px-6 pt-5">
          <div className="min-w-0">
            {title && <h2 className="text-[17px] font-semibold tracking-tight">{title}</h2>}
            {description && (
              <p className="mt-0.5 max-w-2xl text-sm text-ink-3 text-pretty">{description}</p>
            )}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className={cn("flex-1 px-6 pb-6 pt-4", bodyClass)}>{children}</div>
    </section>
  );
}

/* ── level pill ──────────────────────────────────────────────── */

const LEVEL_STYLE: Record<string, { cls: string; label: string }> = {
  critical: { cls: "pill-loss", label: "Critical" },
  warning: { cls: "pill-warn", label: "Warning" },
  watch: { cls: "pill-sky", label: "Watch" },
  info: { cls: "", label: "Info" },
};

export function LevelPill({ level }: { level: string }) {
  const s = LEVEL_STYLE[level] ?? LEVEL_STYLE.info;
  return (
    <span className={cn("pill uppercase tracking-wide", s.cls)}>
      {level === "critical" && <AlertTriangle className="size-3" aria-hidden />}
      {s.label}
    </span>
  );
}

export function RiskBand({ band }: { band: string }) {
  const map: Record<string, string> = {
    low: "pill-gain", medium: "pill-warn", high: "pill-loss",
    critical: "pill-loss font-semibold", unknown: "",
  };
  return <span className={cn("pill capitalize", map[band] ?? map.unknown)}>{band}</span>;
}

/* ── evidence list ───────────────────────────────────────────── */

export function Evidence({ items, dense = false }:
  { items: { label: string; value: string }[]; dense?: boolean }) {
  if (!items?.length) return null;
  return (
    <dl className={cn("grid gap-x-4 gap-y-1.5", dense ? "text-xs" : "text-sm")}>
      {items.map((e, i) => (
        <div key={i} className="flex items-start justify-between gap-4 border-b border-line/70 pb-1.5 last:border-0">
          <dt className="shrink-0 text-ink-3">{e.label}</dt>
          <dd className="min-w-0 text-right tnum">{e.value}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ── loading / empty / error ─────────────────────────────────── */

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("rw-shimmer rounded-xl bg-paper-2", className)} />;
}

export function LoadingPanel({ rows = 3, title }: { rows?: number; title?: string }) {
  return (
    <div className="card space-y-3 p-5" role="status" aria-live="polite">
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
    <div className="flex flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-line bg-card px-6 py-14 text-center">
      {icon && <span className="grid size-10 place-items-center rounded-full bg-paper-2 text-ink-3">{icon}</span>}
      <div>
        <p className="font-semibold">{title}</p>
        {description && <p className="mx-auto mt-1 max-w-md text-sm text-ink-3 text-pretty">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="card border-loss/30 p-5" role="alert">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-4 shrink-0 text-loss" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Could not load this section</p>
          <p className="mt-0.5 break-words text-xs text-ink-2">{message}</p>
        </div>
        {onRetry && (
          <button onClick={onRetry} className="btn btn-ghost btn-sm shrink-0">Retry</button>
        )}
      </div>
    </div>
  );
}

/* ── provenance note ─────────────────────────────────────────── */

export function Provenance({ children }: { children: ReactNode }) {
  return (
    <p className="mt-3 flex items-start gap-1.5 text-[11px] leading-relaxed text-ink-3">
      <Info className="mt-0.5 size-3 shrink-0" aria-hidden />
      <span className="text-pretty">{children}</span>
    </p>
  );
}
