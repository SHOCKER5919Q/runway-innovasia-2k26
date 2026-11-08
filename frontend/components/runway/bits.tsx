"use client";

/**
 * Interaction primitives — the "React Bits" layer.
 *
 * These are the handful of copy-paste motion components that genuinely
 * earn their place on a financial product's marketing surface, written
 * directly rather than pulled in as a dependency. Each is small enough to
 * read, and every one checks `prefers-reduced-motion` in JavaScript so it
 * degrades to a static element rather than a jittery one.
 *
 * Nothing here is used inside the application itself. A magnetic button or
 * a scrambling number is delightful on a landing page and hostile next to
 * someone's bank balance.
 */

import {
  useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState,
  type ReactNode,
} from "react";
import { motion, useInView, useMotionValue, useSpring, useTransform } from "motion/react";
import { cn } from "@/lib/utils";
import { EASE_OUT, prefersReducedMotion } from "./motion";

/* ── useGsap: register plugins once, scope selectors, auto-revert ──── */

export function useGsapContext(
  setup: (ctx: { gsap: any; ScrollTrigger: any; q: (s: string) => any }) => void,
  deps: unknown[] = [],
) {
  const scope = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    let ctx: any;
    let cancelled = false;
    (async () => {
      const { gsap } = await import("gsap");
      const { ScrollTrigger } = await import("gsap/ScrollTrigger");
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);
      ctx = gsap.context(() => {
        setup({
          gsap, ScrollTrigger,
          q: (s: string) => gsap.utils.toArray(s),
        });
      }, scope.current ?? undefined);
    })();
    return () => { cancelled = true; ctx?.revert?.(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return scope;
}

/* ── MagneticButton ────────────────────────────────────────────────
   The pointer pulls the element a few pixels toward it. Subtle enough
   that it reads as responsiveness rather than as a toy. */

export function Magnetic({
  children, strength = 0.35, radius = 110, className,
}: { children: ReactNode; strength?: number; radius?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, { stiffness: 260, damping: 22, mass: 0.6 });
  const sy = useSpring(y, { stiffness: 260, damping: 22, mass: 0.6 });

  useEffect(() => {
    const el = ref.current;
    if (!el || prefersReducedMotion()) return;
    const onMove = (e: PointerEvent) => {
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dx = e.clientX - cx;
      const dy = e.clientY - cy;
      const dist = Math.hypot(dx, dy);
      if (dist < radius + Math.max(r.width, r.height) / 2) {
        x.set(dx * strength);
        y.set(dy * strength);
      } else {
        x.set(0); y.set(0);
      }
    };
    const onLeave = () => { x.set(0); y.set(0); };
    window.addEventListener("pointermove", onMove, { passive: true });
    window.addEventListener("pointerleave", onLeave);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerleave", onLeave);
    };
  }, [x, y, strength, radius]);

  return (
    <motion.span ref={ref} style={{ x: sx, y: sy }} className={cn("inline-block", className)}>
      {children}
    </motion.span>
  );
}

/* ── TiltCard ──────────────────────────────────────────────────────
   3D tilt toward the pointer plus a travelling glare. */

export function TiltCard({
  children, className, max = 8, glare = true,
}: { children: ReactNode; className?: string; max?: number; glare?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const px = useMotionValue(0.5);
  const py = useMotionValue(0.5);
  const srx = useSpring(useTransform(py, [0, 1], [max, -max]), { stiffness: 200, damping: 20 });
  const sry = useSpring(useTransform(px, [0, 1], [-max, max]), { stiffness: 200, damping: 20 });

  const onMove = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (prefersReducedMotion()) return;
    const r = e.currentTarget.getBoundingClientRect();
    px.set((e.clientX - r.left) / r.width);
    py.set((e.clientY - r.top) / r.height);
    e.currentTarget.style.setProperty("--gx", `${((e.clientX - r.left) / r.width) * 100}%`);
    e.currentTarget.style.setProperty("--gy", `${((e.clientY - r.top) / r.height) * 100}%`);
  }, [px, py]);

  return (
    <motion.div
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={() => { px.set(0.5); py.set(0.5); }}
      style={{ rotateX: srx, rotateY: sry, transformPerspective: 900 }}
      className={cn("group relative [transform-style:preserve-3d]", className)}
    >
      {children}
      {glare && (
        <span aria-hidden
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-300 group-hover:opacity-100"
          style={{
            background:
              "radial-gradient(18rem 18rem at var(--gx,50%) var(--gy,50%), oklch(1 0 0 / 0.07), transparent 65%)",
          }} />
      )}
    </motion.div>
  );
}

/* ── SplitText ─────────────────────────────────────────────────────
   Per-character mask reveal, driven by scroll entry. */

export function SplitText({
  text, className, by = "char", delay = 0, stagger,
  as: Tag = "span",
}: {
  text: string; className?: string; by?: "char" | "word"; delay?: number;
  stagger?: number; as?: "span" | "h1" | "h2" | "h3" | "p";
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-12%" });
  const reduce = prefersReducedMotion();
  const step = stagger ?? (by === "char" ? 0.022 : 0.05);

  const words = useMemo(() => text.split(" "), [text]);
  if (reduce) return <Tag className={className}>{text}</Tag>;

  let index = 0;
  return (
    <Tag className={className}>
      <span ref={ref} aria-label={text} className="inline">
        {words.map((w, wi) => (
          <span key={wi} className="inline-block whitespace-nowrap">
            {(by === "char" ? [...w] : [w]).map((unit, ui) => {
              const i = index++;
              return (
                <span key={ui} className="inline-block overflow-hidden align-bottom">
                  <motion.span
                    aria-hidden
                    className="inline-block will-change-transform"
                    initial={{ y: "115%", opacity: 0 }}
                    animate={inView ? { y: "0%", opacity: 1 } : undefined}
                    transition={{ duration: 0.75, ease: EASE_OUT, delay: delay + i * step }}
                  >
                    {unit}
                  </motion.span>
                </span>
              );
            })}
            {wi < words.length - 1 && <span className="inline-block">&nbsp;</span>}
          </span>
        ))}
      </span>
    </Tag>
  );
}

/* ── ScrollFloat ───────────────────────────────────────────────────
   Words lift and settle as the block crosses the viewport. */

export function ScrollFloat({ text, className }: { text: string; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [p, setP] = useState(0);

  useEffect(() => {
    if (prefersReducedMotion()) { setP(1); return; }
    const el = ref.current;
    if (!el) return;
    let raf = 0;
    const update = () => {
      const r = el.getBoundingClientRect();
      const vh = window.innerHeight;
      // 0 when the block is one viewport below, 1 when it reaches the middle
      const t = 1 - (r.top - vh * 0.25) / (vh * 0.75);
      setP(Math.max(0, Math.min(1, t)));
      raf = 0;
    };
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update); };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);

  const words = text.split(" ");
  return (
    <span ref={ref} className={className} aria-label={text}>
      {words.map((w, i) => {
        const local = Math.max(0, Math.min(1, p * words.length - i * 0.65));
        return (
          <span key={i} aria-hidden className="inline-block will-change-transform"
            style={{
              opacity: 0.18 + local * 0.82,
              transform: `translateY(${(1 - local) * 0.35}em)`,
              filter: `blur(${(1 - local) * 5}px)`,
              transition: "none",
            }}>
            {w}{i < words.length - 1 ? " " : ""}
          </span>
        );
      })}
    </span>
  );
}

/* ── Counter ───────────────────────────────────────────────────────
   Eases to a value on entry. Landing page only. */

export function Counter({
  to, duration = 1.6, format, className, prefix = "", suffix = "",
}: {
  to: number; duration?: number; format?: (n: number) => string;
  className?: string; prefix?: string; suffix?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-15%" });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const fmt = format ?? ((n: number) => Math.round(n).toLocaleString("en-IN"));
    if (!inView || prefersReducedMotion()) { el.textContent = prefix + fmt(to) + suffix; return; }
    const t0 = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - t0) / (duration * 1000));
      const eased = 1 - Math.pow(1 - t, 4);
      el.textContent = prefix + fmt(to * eased) + suffix;
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, to, duration, format, prefix, suffix]);
  return <span ref={ref} className={cn("tnum", className)}>{prefix}0{suffix}</span>;
}

/* ── Scramble ──────────────────────────────────────────────────────
   Decodes a string on entry. Used once, on the ledger section. */

const GLYPHS = "0123456789₹#%/\\|<>+-=";

export function Scramble({ text, className, speed = 34 }:
  { text: string; className?: string; speed?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-20%" });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (!inView || prefersReducedMotion()) { el.textContent = text; return; }
    let frame = 0;
    const id = setInterval(() => {
      el.textContent = [...text]
        .map((c, i) => (i < frame / 2 ? c : c === " " ? " "
          : GLYPHS[Math.floor(Math.random() * GLYPHS.length)]))
        .join("");
      frame += 1;
      if (frame / 2 >= text.length) { el.textContent = text; clearInterval(id); }
    }, speed);
    return () => clearInterval(id);
  }, [inView, text, speed]);
  return <span ref={ref} className={cn("font-mono", className)}>{text}</span>;
}

/* ── Marquee ───────────────────────────────────────────────────────
   A continuous ticker. Duplicated content, translated by CSS. */

export function Marquee({
  children, speed = 42, reverse = false, className,
}: { children: ReactNode; speed?: number; reverse?: boolean; className?: string }) {
  return (
    <div className={cn("group relative flex overflow-hidden", className)}
         style={{
           maskImage: "linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent)",
           WebkitMaskImage: "linear-gradient(90deg, transparent, #000 8%, #000 92%, transparent)",
         }}>
      {[0, 1].map((k) => (
        <div key={k} aria-hidden={k === 1}
          className="flex shrink-0 items-center gap-10 pr-10 will-change-transform motion-reduce:animate-none"
          style={{
            animation: `rw-marquee ${speed}s linear infinite`,
            animationDirection: reverse ? "reverse" : "normal",
          }}>
          {children}
        </div>
      ))}
    </div>
  );
}

/* ── GridBeam ──────────────────────────────────────────────────────
   A faint grid with light sweeping along a few lines. Pure CSS. */

export function GridBeam({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}>
      <div className="absolute inset-0 rw-grid-bg" />
      {[18, 42, 67, 86].map((left, i) => (
        <span key={left}
          className="absolute top-0 h-full w-px motion-reduce:hidden"
          style={{
            left: `${left}%`,
            background: "linear-gradient(to bottom, transparent, var(--primary), transparent)",
            opacity: 0.4,
            animation: `rw-beam ${7 + i * 2.3}s ease-in-out ${i * 1.4}s infinite`,
          }} />
      ))}
    </div>
  );
}

/* ── Reveal on scroll with a configurable axis ─────────────────────── */

export function Rise({
  children, delay = 0, y = 28, blur = 8, className,
}: { children: ReactNode; delay?: number; y?: number; blur?: number; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, margin: "-10%" });
  const reduce = prefersReducedMotion();
  return (
    <motion.div
      ref={ref}
      className={className}
      initial={reduce ? false : { opacity: 0, y, filter: `blur(${blur}px)` }}
      animate={inView || reduce ? { opacity: 1, y: 0, filter: "blur(0px)" } : undefined}
      transition={{ duration: 0.85, ease: EASE_OUT, delay }}
    >
      {children}
    </motion.div>
  );
}

/* ── ScrollProgress ────────────────────────────────────────────────── */

export function ScrollProgress() {
  const [p, setP] = useState(0);
  useEffect(() => {
    const onScroll = () => {
      const h = document.documentElement.scrollHeight - window.innerHeight;
      setP(h > 0 ? window.scrollY / h : 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return (
    <div aria-hidden className="fixed inset-x-0 top-0 z-[60] h-px bg-transparent">
      <div className="h-full origin-left bg-primary shadow-[0_0_12px_var(--primary)]"
           style={{ transform: `scaleX(${p})` }} />
    </div>
  );
}
