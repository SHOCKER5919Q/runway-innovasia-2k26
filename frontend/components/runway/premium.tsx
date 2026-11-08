"use client";

/* ─────────────────────────────────────────────────────────────────────────
   Premium chrome for the marketing pages.

   Two rules this file obeys, both from DESIGN.md:

   - None of this is allowed inside the application. A curtain in front of
     someone checking whether payroll clears on Friday is an insult, not a
     flourish. These are landing-page parts only.
   - Nothing here gates content. The curtain is painted over a page that has
     already rendered and is removed by a timer that cannot fail to a blank
     screen; the rail is decoration layered beside real anchors. Under
     prefers-reduced-motion both reduce to nothing.
   ───────────────────────────────────────────────────────────────────────── */

import { useEffect, useRef, useState } from "react";
import { prefersReducedMotion } from "./motion";

/* ── the intro curtain ───────────────────────────────────────────────────
   One brand beat on first arrival, then gone. Keyed to sessionStorage so
   coming back from /login does not replay it — a flourish that repeats is
   a loading screen. */

export function IntroCurtain({ label = "RUNWAY", sub = "Financial intelligence" }:
  { label?: string; sub?: string }) {
  // Starts false so the server-rendered page is the real page. The curtain
  // only ever exists as a client-side overlay on top of it.
  const [show, setShow] = useState(false);
  const [lifting, setLifting] = useState(false);

  useEffect(() => {
    if (prefersReducedMotion()) return;
    let seen = false;
    try { seen = sessionStorage.getItem("runway.intro") === "1"; } catch { /* private mode */ }
    if (seen) return;

    setShow(true);
    document.documentElement.style.overflow = "hidden";
    try { sessionStorage.setItem("runway.intro", "1"); } catch { /* ignore */ }

    const lift = window.setTimeout(() => setLifting(true), 900);
    const done = window.setTimeout(() => {
      setShow(false);
      document.documentElement.style.overflow = "";
    }, 1700);

    return () => {
      window.clearTimeout(lift);
      window.clearTimeout(done);
      document.documentElement.style.overflow = "";
    };
  }, []);

  if (!show) return null;

  return (
    <div
      aria-hidden
      className="fixed inset-0 z-[100] grid place-items-center bg-background"
      style={lifting
        ? { animation: "rw-curtain-lift 0.8s cubic-bezier(0.76,0,0.24,1) forwards" }
        : undefined}
    >
      <div className="relative text-center" style={{ animation: "rw-curtain-mark 0.6s cubic-bezier(0.16,1,0.3,1) both" }}>
        <p className="font-display text-[clamp(2.2rem,7vw,4.5rem)] font-semibold tracking-[-0.04em]">
          {label}
        </p>
        <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.34em] text-muted-foreground">
          {sub}
        </p>
        {/* the loading rule draws once, left to right */}
        <span className="mt-6 block h-px w-full overflow-hidden bg-border">
          <span className="block h-px w-full bg-primary"
                style={{ animation: "rw-curtain-sweep 1.5s cubic-bezier(0.16,1,0.3,1) both" }} />
        </span>
      </div>
    </div>
  );
}

/* ── the chapter rail ────────────────────────────────────────────────────
   A fixed index of the page's sections that tracks the scroll. It is real
   navigation — every dot is an anchor to a section that exists — so it
   earns its place instead of decorating the gutter. */

export function ChapterRail({ sections }: { sections: readonly { id: string; label: string }[] }) {
  const [active, setActive] = useState(sections[0]?.id ?? "");
  const [visible, setVisible] = useState(false);
  const ratios = useRef(new Map<string, number>());

  useEffect(() => {
    const nodes = sections
      .map((s) => document.getElementById(s.id))
      .filter((n): n is HTMLElement => n !== null);
    if (!nodes.length) return;

    // Track every section's visible share and pick the leader, rather than
    // firing on whichever boundary crossed last. Two short sections next to
    // each other make the naive version flicker between them.
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) ratios.current.set(e.target.id, e.intersectionRatio);
        let bestId = "";
        let best = 0;
        for (const [id, r] of ratios.current) if (r > best) { best = r; bestId = id; }
        if (bestId) setActive(bestId);
      },
      { threshold: [0, 0.1, 0.25, 0.5, 0.75, 1] },
    );
    nodes.forEach((n) => io.observe(n));

    // The rail stays out of the hero — it should arrive once the page has
    // proved it has chapters to index.
    const onScroll = () => setVisible(window.scrollY > window.innerHeight * 0.7);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });

    return () => { io.disconnect(); window.removeEventListener("scroll", onScroll); };
  }, [sections]);

  return (
    <nav
      aria-label="Page sections"
      className={`fixed right-5 top-1/2 z-40 hidden -translate-y-1/2 xl:block
                  transition-opacity duration-500 ${visible ? "opacity-100" : "pointer-events-none opacity-0"}`}
    >
      <ul className="flex flex-col items-end gap-4">
        {sections.map((s) => {
          const on = active === s.id;
          return (
            <li key={s.id}>
              <a href={`#${s.id}`}
                 aria-current={on ? "true" : undefined}
                 className="group flex items-center gap-2.5 py-0.5">
                <span className={`font-mono text-[10px] uppercase tracking-[0.18em] transition-all duration-300
                                  ${on ? "text-primary opacity-100" : "text-muted-foreground opacity-0 group-hover:opacity-100"}`}>
                  {s.label}
                </span>
                <span className="rw-rail-dot" data-on={on} />
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
