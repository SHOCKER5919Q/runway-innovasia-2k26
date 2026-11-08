"use client";

/**
 * Motion layer.
 *
 * Lenis gives the marketing surface its inertial scroll; GSAP ScrollTrigger
 * drives the scroll-linked reveals; Motion (Framer) handles component-level
 * state transitions inside the app.
 *
 * Two rules this file enforces:
 *  1. Lenis runs on marketing pages only. Hijacking scroll inside a
 *     financial table is actively hostile - people scan, they do not glide.
 *  2. Every animation is disabled under `prefers-reduced-motion`, including
 *     Lenis and the GSAP ticker, not just the CSS.
 */

import { useEffect, useRef, type ReactNode } from "react";
import { motion, useInView, type Variants } from "motion/react";

export const EASE_OUT = [0.16, 1, 0.3, 1] as const;
export const SPRING = { type: "spring" as const, stiffness: 420, damping: 34, mass: 0.8 };
export const SPRING_SOFT = { type: "spring" as const, stiffness: 240, damping: 30 };

export function prefersReducedMotion() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: (i = 0) => ({
    opacity: 1, y: 0,
    transition: { duration: 0.55, ease: EASE_OUT, delay: Math.min(i * 0.05, 0.4) },
  }),
};

export const stagger: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.055, delayChildren: 0.05 } },
};

/** Reveal on first entry into the viewport; never re-animates on scroll-back. */
export function Reveal({
  children, delay = 0, y = 14, className, as = "div",
}: { children: ReactNode; delay?: number; y?: number; className?: string; as?: "div" | "section" | "li" }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-60px" });
  const reduce = prefersReducedMotion();
  const Tag = motion[as] as typeof motion.div;
  return (
    <Tag
      ref={ref as never}
      className={className}
      initial={reduce ? false : { opacity: 0, y }}
      animate={inView || reduce ? { opacity: 1, y: 0 } : undefined}
      transition={{ duration: 0.6, ease: EASE_OUT, delay }}
    >
      {children}
    </Tag>
  );
}

/** Smooth scroll for the marketing surface only. */
export function SmoothScroll({ children }: { children: ReactNode }) {
  useEffect(() => {
    if (prefersReducedMotion()) return;

    let lenis: any;
    let raf = 0;
    let tick: ((t: number) => void) | null = null;
    let gsapRef: any = null;
    let cancelled = false;
    let onFontsReady: (() => void) | null = null;

    (async () => {
      const Lenis = (await import("lenis")).default;
      if (cancelled) return;
      lenis = new Lenis({
        duration: 1.05, smoothWheel: true, wheelMultiplier: 0.9, touchMultiplier: 1.6,
      });

      try {
        const { gsap } = await import("gsap");
        const { ScrollTrigger } = await import("gsap/ScrollTrigger");
        if (cancelled) return;
        gsap.registerPlugin(ScrollTrigger);
        gsapRef = gsap;

        // One clock, not two. Driving Lenis from GSAP's ticker is what keeps
        // a pinned section from juddering: with a separate requestAnimationFrame
        // loop, Lenis can move the scroll position in a frame where
        // ScrollTrigger has already measured, so the pinned element lags the
        // page by a frame and visibly shivers.
        tick = (time: number) => lenis.raf(time * 1000); // GSAP ticks in seconds
        gsap.ticker.add(tick);
        gsap.ticker.lagSmoothing(0);
        lenis.on("scroll", ScrollTrigger.update);

        // Pinned sections compute their end from laid-out height. A late web
        // font changes that height after the triggers were measured, which
        // leaves every pin ending in the wrong place.
        if (document.fonts?.status === "loaded") {
          ScrollTrigger.refresh();
        } else {
          onFontsReady = () => ScrollTrigger.refresh();
          document.fonts?.addEventListener?.("loadingdone", onFontsReady);
        }
      } catch {
        // GSAP is optional. Without it Lenis needs its own loop again.
        const loop = (t: number) => { lenis.raf(t); raf = requestAnimationFrame(loop); };
        raf = requestAnimationFrame(loop);
      }
    })();

    return () => {
      cancelled = true;
      if (raf) cancelAnimationFrame(raf);
      if (tick && gsapRef) gsapRef.ticker.remove(tick);
      if (onFontsReady) document.fonts?.removeEventListener?.("loadingdone", onFontsReady);
      // Deliberately NOT killing ScrollTriggers here. Each section creates
      // its own inside a gsap.context that reverts itself, and under dev's
      // double-mount a blanket kill from this parent can take out triggers
      // the children have just rebuilt.
      lenis?.destroy?.();
    };
  }, []);
  return <>{children}</>;
}

/** Counts a number up when it scrolls into view. Used sparingly - on the
 *  landing page only, never on a live financial figure, because an
 *  animating balance is unreadable at exactly the moment it matters. */
export function CountUp({
  to, duration = 1.4, format, className,
}: { to: number; duration?: number; format?: (n: number) => string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fmt = format ?? ((n: number) => Math.round(n).toLocaleString("en-IN"));
    if (!inView || prefersReducedMotion()) { el.textContent = fmt(to); return; }
    const t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / (duration * 1000));
      const eased = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(to * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, duration, format]);
  return <span ref={ref} className={className}>0</span>;
}

/** Character-by-character text reveal (GSAP-style, implemented with Motion
 *  so there is one animation runtime inside the app bundle). */
export function TextReveal({ text, className, delay = 0 }: { text: string; className?: string; delay?: number }) {
  const reduce = prefersReducedMotion();
  if (reduce) return <span className={className}>{text}</span>;
  const words = text.split(" ");
  return (
    <span className={className} aria-label={text}>
      {words.map((w, i) => (
        <span key={i} className="inline-block overflow-hidden align-bottom">
          <motion.span
            className="inline-block"
            initial={{ y: "110%", opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.7, ease: EASE_OUT, delay: delay + i * 0.045 }}
            aria-hidden
          >
            {w}&nbsp;
          </motion.span>
        </span>
      ))}
    </span>
  );
}

/** Pointer-tracking highlight. One decorative effect, used on hero cards
 *  only, so it reads as craft rather than noise. */
export function Spotlight({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${e.clientX - r.left}px`);
      el.style.setProperty("--my", `${e.clientY - r.top}px`);
    };
    el.addEventListener("pointermove", onMove);
    return () => el.removeEventListener("pointermove", onMove);
  }, []);
  return (
    <div ref={ref} className={`group relative ${className}`}>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={{
          background:
            "radial-gradient(22rem 22rem at var(--mx,50%) var(--my,50%), rgba(198, 245, 74, 0.10), transparent 70%)",
        }}
      />
      {children}
    </div>
  );
}

export { motion };
