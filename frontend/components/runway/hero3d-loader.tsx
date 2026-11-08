"use client";

/** Client-only wrapper. The 3D bundle must never reach the server renderer,
 *  and it must never block first paint — the hero's text and CTA are
 *  readable before the canvas has downloaded. */

import dynamic from "next/dynamic";
import { prefersReducedMotion } from "./motion";

const Hero3D = dynamic(() => import("./hero3d"), {
  ssr: false,
  loading: () => <HeroFallback />,
});

function HeroFallback() {
  return (
    <div aria-hidden className="relative grid h-full w-full place-items-center">
      <div className="relative h-[70%] w-[55%] max-w-sm">
        {[0, 1, 2].map((i) => (
          <div key={i}
            className="absolute inset-0 rounded-2xl border border-primary/15 bg-gradient-to-br from-primary/[0.07] to-fin-gain/[0.04] backdrop-blur-sm"
            style={{ transform: `translate(${i * 10}px, ${i * -8}px) rotate(${i * 1.2}deg)` }} />
        ))}
      </div>
    </div>
  );
}

export default function HeroCanvas({ className }: { className?: string }) {
  if (typeof window !== "undefined" && prefersReducedMotion()) {
    return <div className={className}><HeroFallback /></div>;
  }
  return <Hero3D className={className} />;
}
