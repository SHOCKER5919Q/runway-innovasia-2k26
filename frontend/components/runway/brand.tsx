"use client";

import { cn } from "@/lib/utils";

/** The Drive-reference mark: a rising line on a forest tile with a lime arrow.
 *  `inverse` swaps tile and text for the forest story panels. */
export function Logo({ compact = false, inverse = false, className }:
  { compact?: boolean; inverse?: boolean; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <span className={cn(
        "grid size-8 shrink-0 place-items-center rounded-[10px]",
        inverse ? "bg-lime text-forest" : "bg-forest text-lime",
      )}>
        <svg viewBox="0 0 24 24" className="size-[18px]" fill="none" stroke="currentColor"
             strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M3 17l6-6 4 4 8-9" />
          <path d="M15 6h6v6" />
        </svg>
      </span>
      {!compact && (
        <span className={cn("text-[19px] font-semibold tracking-tight",
          inverse ? "text-white" : "text-ink")}>
          Runway
        </span>
      )}
    </span>
  );
}

export function BrandLine({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-2", className)}>
      <span className="h-px w-6 bg-lime" aria-hidden />
      <span className="eyebrow">Financial intelligence</span>
    </span>
  );
}
