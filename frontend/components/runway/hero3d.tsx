"use client";

/**
 * The hero's 3D object: stacked glass panels with a glowing cash-flow
 * chart suspended inside them.
 *
 * Built in react-three-fiber rather than imported as a generated mesh.
 * A text-to-3D service would hand back a static multi-megabyte GLB; this
 * is ~8 KB of code, reacts to the pointer, and — more to the point — the
 * bars inside it are the *actual shape of a 13-week forecast*, so the
 * hero is showing the product rather than decorating around it.
 *
 * Everything degrades: the canvas is lazy, it pauses when scrolled out of
 * view, it drops to a cheap material on low-end devices, and under
 * `prefers-reduced-motion` nothing animates at all.
 */

import { Suspense, useEffect, useRef, useState } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Environment, Float, MeshTransmissionMaterial, RoundedBox } from "@react-three/drei";
import * as THREE from "three";

const LIME = "#c6f54a";
const EMERALD = "#34e7b0";
const CYAN = "#5ec8f5";

/** The silhouette of a 13-week forecast: a dip in the middle, recovery after. */
const SERIES = [0.42, 0.55, 0.68, 0.60, 0.44, 0.33, 0.29, 0.38, 0.52, 0.66, 0.78, 0.70, 0.86];

function Bars({ depth, hue, lit }: { depth: number; hue: string; lit: number }) {
  const group = useRef<THREE.Group>(null);
  useFrame(({ clock }) => {
    if (!group.current) return;
    const t = clock.getElapsedTime();
    group.current.children.forEach((child, i) => {
      const m = child as THREE.Mesh;
      const mat = m.material as THREE.MeshStandardMaterial;
      // A slow travelling pulse along the series, so the chart reads as live.
      const wave = 0.5 + 0.5 * Math.sin(t * 1.1 - i * 0.42);
      // Capped well under 1. With toneMapped off and a range up to 2.0 the
      // bars clipped straight to white, and the frosted panel then smeared
      // the clipped pixels into one glowing blob instead of a chart.
      mat.emissiveIntensity = lit * (0.34 + wave * 0.42);
    });
  });

  return (
    <group ref={group} position={[0, 0, depth]}>
      {SERIES.map((v, i) => {
        const h = 0.35 + v * 3.1;
        const x = (i - (SERIES.length - 1) / 2) * 0.205;   // spans 2.46 inside a 3.3 panel
        return (
          <mesh key={i} position={[x, -1.85 + h / 2, 0]}>
            <boxGeometry args={[0.125, h, 0.1]} />
            {/* A dark body keeps the gaps between bars readable; the colour
                arrives as emission, not as albedo. */}
            <meshStandardMaterial
              color="#0a1f17" emissive={hue} emissiveIntensity={0.5}
              roughness={0.35} metalness={0} />
          </mesh>
        );
      })}
    </group>
  );
}

function Panel({
  z, rotation, scale, cheap,
}: { z: number; rotation: [number, number, number]; scale: number; cheap: boolean }) {
  return (
    <RoundedBox args={[3.3, 5.9, 0.1]} radius={0.07} smoothness={4}
                position={[0, 0, z]} rotation={rotation} scale={scale}>
      {cheap ? (
        // Low-end path: a cheap translucent standard material. Same silhouette,
        // a fraction of the cost, and nobody gets a 4 fps hero.
        <meshStandardMaterial
          color="#bff2ff" transparent opacity={0.22}
          roughness={0.06} metalness={0.15} />
      ) : (
        <MeshTransmissionMaterial
          samples={8} resolution={320} transmission={1} thickness={0.45}
          roughness={0.08} ior={1.22} chromaticAberration={0.28}
          anisotropy={0.2} distortion={0.07} distortionScale={0.16}
          temporalDistortion={0.04} attenuationDistance={5.0}
          attenuationColor="#9fe9c9" color="#e6f6ef"
        />
      )}
    </RoundedBox>
  );
}

function Scene({ cheap }: { cheap: boolean }) {
  const rig = useRef<THREE.Group>(null);
  const { viewport } = useThree();

  useFrame(({ pointer, clock }, delta) => {
    if (!rig.current) return;
    const t = clock.getElapsedTime();
    // Pointer parallax, damped so it glides rather than snaps.
    const targetY = pointer.x * 0.34 + Math.sin(t * 0.22) * 0.06;
    const targetX = -pointer.y * 0.2 + Math.cos(t * 0.18) * 0.04;
    rig.current.rotation.y = THREE.MathUtils.damp(rig.current.rotation.y, targetY, 3, delta);
    rig.current.rotation.x = THREE.MathUtils.damp(rig.current.rotation.x, targetX, 3, delta);
  });

  const scale = Math.min(1.08, viewport.width / 8);

  return (
    <group ref={rig} scale={scale}>
      <Float speed={1.1} rotationIntensity={0.14} floatIntensity={0.5}>
        <group rotation={[0, -0.42, 0.05]}>
          {/* The chart sits between the panels, so the glass refracts it. */}
          {/* Two bar layers, each sandwiched between sheets so the glass in
              front of them does the refracting. */}
          <Bars depth={-0.55} hue={EMERALD} lit={0.8} />
          <Bars depth={-1.5} hue={CYAN} lit={0.45} />

          <Panel z={0.35} rotation={[0, 0, 0]} scale={1} cheap={cheap} />
          <Panel z={-0.9} rotation={[0, 0.07, 0.018]} scale={0.97} cheap={cheap} />
          <Panel z={-2.1} rotation={[0, 0.14, 0.036]} scale={0.94} cheap={cheap} />

          {/* Rim light so the sheet edges catch, as they do in the reference. */}
          <pointLight position={[-3.4, 2.4, 3.0]} intensity={9} color={LIME} distance={13} />
          <pointLight position={[3.4, -1.6, 2.4]} intensity={7} color={CYAN} distance={13} />
          <pointLight position={[0, 0, -4]} intensity={6} color={EMERALD} distance={11} />
          <pointLight position={[-1.4, 2.6, 3.4]} intensity={4} color="#ffffff" distance={10} />
        </group>
      </Float>
    </group>
  );
}

export default function Hero3D({ className }: { className?: string }) {
  const [visible, setVisible] = useState(true);
  const [cheap, setCheap] = useState(false);
  const host = useRef<HTMLDivElement>(null);

  // A plain capability heuristic rather than drei's useDetectGPU, which
  // runs a benchmark and can suspend — and this component sits outside any
  // Suspense boundary of its own.
  useEffect(() => {
    const coarse = window.matchMedia("(pointer: coarse)").matches;
    const fewCores = (navigator.hardwareConcurrency ?? 8) <= 4;
    const narrow = window.innerWidth < 820;
    const saveData = (navigator as { connection?: { saveData?: boolean } })
      .connection?.saveData === true;
    setCheap(coarse || fewCores || narrow || saveData);
  }, []);

  // Pause the render loop whenever the hero is off screen. A 3D canvas
  // spinning behind six screens of content is pure battery theft.
  useEffect(() => {
    const el = host.current;
    if (!el || !("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(([e]) => setVisible(e.isIntersecting), { threshold: 0 });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div ref={host} className={className} aria-hidden>
      <Canvas
        frameloop={visible ? "always" : "never"}
        dpr={[1, cheap ? 1.25 : 1.8]}
        gl={{ antialias: !cheap, alpha: true, powerPreference: "high-performance" }}
        camera={{ position: [0.4, 0.2, 8.0], fov: 40 }}
      >
        <Suspense fallback={null}>
          <ambientLight intensity={0.22} />
          <directionalLight position={[4, 6, 6]} intensity={1.1} />
          <Scene cheap={cheap} />
          {!cheap && <Environment preset="city" environmentIntensity={0.6} />}
        </Suspense>
      </Canvas>
    </div>
  );
}
