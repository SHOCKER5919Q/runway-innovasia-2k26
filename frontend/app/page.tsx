import GroveLanding from "@/components/runway/atelier";

/* Never serve a statically cached copy of the marketing page. The v1 WebGL
   hero used to be prerendered into a long-lived HTML document, which is why a
   stale browser tab could keep showing dark glass panels after a redesign. */
export const dynamic = "force-dynamic";
export const revalidate = 0;

export default function Landing() {
  return <GroveLanding />;
}
