/** Indian number formatting and shared display helpers. */

export type Money = { paise: number; rupees: number; display: string; compact: string };

const INR = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

/** Format paise with Indian digit grouping (lakh / crore). */
export function inr(paise: number | null | undefined, opts: { compact?: boolean; sign?: boolean } = {}) {
  if (paise === null || paise === undefined || Number.isNaN(paise)) return "—";
  const neg = paise < 0;
  const rupees = Math.round(Math.abs(paise) / 100);
  let body: string;
  if (opts.compact) {
    if (rupees >= 1_00_00_000) body = `${(rupees / 1_00_00_000).toFixed(2)} Cr`;
    else if (rupees >= 1_00_000) body = `${(rupees / 1_00_000).toFixed(2)} L`;
    else if (rupees >= 1_000) body = `${(rupees / 1_000).toFixed(1)} K`;
    else body = INR.format(rupees);
  } else {
    body = INR.format(rupees);
  }
  const prefix = neg ? "−" : opts.sign ? "+" : "";
  return `${prefix}₹${body}`;
}

export function money(m: Money | null | undefined, compact = false) {
  if (!m) return "—";
  return compact ? m.compact : m.display;
}

export function paiseOf(m: Money | number | null | undefined): number {
  if (m === null || m === undefined) return 0;
  return typeof m === "number" ? m : m.paise;
}

export function pct(v: number | null | undefined, digits = 0) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function signedPct(v: number | null | undefined, digits = 1) {
  if (v === null || v === undefined) return "—";
  return `${v >= 0 ? "+" : "−"}${Math.abs(v * 100).toFixed(digits)}%`;
}

export function days(n: number | null | undefined, digits = 0) {
  if (n === null || n === undefined) return "—";
  const s = Math.abs(n).toFixed(digits);
  return `${n >= 0 ? "+" : "−"}${s} day${Math.abs(n) === 1 ? "" : "s"}`;
}

export function weeks(n: number | null | undefined, digits = 1) {
  if (n === null || n === undefined) return "—";
  return `${n.toFixed(digits)} wk`;
}

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export function shortDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
}

export function longDate(iso: string | null | undefined) {
  if (!iso) return "—";
  const d = new Date(iso + (iso.length === 10 ? "T00:00:00" : ""));
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function relDays(iso: string | null | undefined, from?: string) {
  if (!iso) return "—";
  const a = new Date(iso + "T00:00:00").getTime();
  const b = from ? new Date(from + "T00:00:00").getTime() : Date.now();
  const n = Math.round((a - b) / 86_400_000);
  if (n === 0) return "today";
  if (n === 1) return "tomorrow";
  if (n === -1) return "yesterday";
  return n > 0 ? `in ${n} days` : `${-n} days ago`;
}

export function titleCase(s: string) {
  return (s || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Direction of a financial delta, for colour + glyph. Never colour alone. */
export function direction(delta: number, betterWhen: "higher" | "lower" = "higher") {
  if (delta === 0) return { tone: "neutral" as const, glyph: "→", label: "unchanged" };
  const good = betterWhen === "higher" ? delta > 0 : delta < 0;
  return good
    ? { tone: "gain" as const, glyph: "▲", label: "improved" }
    : { tone: "loss" as const, glyph: "▼", label: "worse" };
}

export const TONE_CLASS: Record<string, string> = {
  gain: "text-fin-gain",
  loss: "text-fin-loss",
  warn: "text-fin-warn",
  info: "text-fin-info",
  neutral: "text-muted-foreground",
};

export const LEVEL_TONE: Record<string, "loss" | "warn" | "info" | "neutral"> = {
  critical: "loss", warning: "warn", watch: "info", info: "neutral",
};

export const STATE_META = {
  actual: {
    label: "Actual", short: "A", color: "var(--state-actual)",
    soft: "var(--state-actual-soft)",
    blurb: "Recorded in your ledger and reconciled",
    question: "What is happening?",
  },
  predicted: {
    label: "Predicted", short: "P", color: "var(--state-predicted)",
    soft: "var(--state-predicted-soft)",
    blurb: "A model estimate with an uncertainty range",
    question: "What is likely to happen?",
  },
  simulated: {
    label: "Simulated", short: "S", color: "var(--state-simulated)",
    soft: "var(--state-simulated-soft)",
    blurb: "A what-if. Nothing is written to your ledger",
    question: "What could happen?",
  },
} as const;

export type StateKey = keyof typeof STATE_META;
