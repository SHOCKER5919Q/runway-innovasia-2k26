"use client";

/* ─────────────────────────────────────────────────────────────────────────
   Renders one Cash Health Passport section.

   The shared report is the only RUNWAY page an outsider sees — a banker, a
   buyer's accountant, an investor doing diligence. It was dumping
   JSON.stringify into a <pre>, which is the single least credible thing a
   financial product can show the person deciding whether to lend.

   The passport's section values are a small, closed set of shapes, so this
   renders them structurally rather than guessing:

     Money       {paise, rupees, display, compact}  → formatted rupees
     ratio       0..1 under a share/probability key  → a percentage
     score       0..100 under a score key            → "72.8 / 100"
     row list    array of flat objects               → a table
     group       nested object                       → a labelled list

   An unrecognised shape falls through to monospace JSON rather than
   throwing: a passport that cannot render one new field should still show
   the other eight.
   ───────────────────────────────────────────────────────────────────────── */

import { days, inr, pct, titleCase, weeks } from "@/lib/format";

type Money = { paise: number; display?: string; compact?: string };

const isMoney = (v: unknown): v is Money =>
  !!v && typeof v === "object" && !Array.isArray(v) && "paise" in (v as object);

const isRowList = (v: unknown): v is Record<string, unknown>[] =>
  Array.isArray(v) && v.length > 0 && v.every(
    (r) => !!r && typeof r === "object" && !Array.isArray(r));

/** Humanises a payload key: "runway_weeks_p10" → "Runway weeks P10". */
function humanise(key: string) {
  const t = key.replace(/_/g, " ").replace(/\bp(\d{2})\b/gi, (_, d) => `P${d}`);
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/** Formats a leaf by what its key says it means. Money is detected by shape. */
function leaf(key: string, v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (isMoney(v)) return inr(v.paise);
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "string") return /^[a-z_]+$/.test(v) ? titleCase(v) : v;

  if (typeof v === "number") {
    const k = key.toLowerCase();
    // A ratio is stored as a fraction; a score is stored out of a hundred.
    if (/(_share|probability|ratio|share)$/.test(k) || k === "top1_share" || k === "top3_share") {
      return pct(v, 1);
    }
    if (k.includes("score")) return `${v.toFixed(1)} / 100`;
    if (k.endsWith("_days") || k === "mean_delay_days") return days(v, 1);
    if (k.includes("week")) return Number.isInteger(v) ? String(v) : weeks(v);
    if (k === "weight") return pct(v, 0);
    return v.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  }
  return JSON.stringify(v);
}

/* ── a table for an array of flat records ───────────────────────── */

function RowTable({ rows }: { rows: Record<string, unknown>[] }) {
  // Union of keys in first-seen order, so a row missing a field still lines up.
  const cols: string[] = [];
  for (const r of rows) for (const k of Object.keys(r)) if (!cols.includes(k)) cols.push(k);

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-[12px]">
        <thead>
          <tr className="border-b border-border">
            {cols.map((c) => (
              <th key={c} scope="col"
                  className="whitespace-nowrap px-2.5 py-1.5 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {humanise(c)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-border/50 last:border-0">
              {cols.map((c, j) => (
                <td key={c}
                    className={`whitespace-nowrap px-2.5 py-1.5 ${j === 0 ? "font-medium" : "tnum text-muted-foreground"}`}>
                  {leaf(c, r[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── a definition list for an object ───────────────────────────── */

function Group({ obj }: { obj: Record<string, unknown> }) {
  const entries = Object.entries(obj);
  // Nested structures get their own sub-block below the flat rows, so the
  // headline numbers are never pushed under a table.
  const flat = entries.filter(([, v]) => !isRowList(v) && !(v && typeof v === "object" && !isMoney(v)));
  const deep = entries.filter(([, v]) => isRowList(v) || (v && typeof v === "object" && !isMoney(v)));

  return (
    <div className="space-y-4">
      {flat.length > 0 && (
        <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
          {flat.map(([k, v]) => (
            <div key={k} className="flex items-baseline justify-between gap-4 border-b border-border/50 pb-1.5">
              <dt className="text-[12px] text-muted-foreground">{humanise(k)}</dt>
              <dd className="shrink-0 text-[13px] font-medium tnum">{leaf(k, v)}</dd>
            </div>
          ))}
        </dl>
      )}
      {deep.map(([k, v]) => (
        <div key={k}>
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            {humanise(k)}
          </p>
          <ReportValue value={v} />
        </div>
      ))}
    </div>
  );
}

/* ── the entry point ───────────────────────────────────────────── */

export function ReportValue({ value }: { value: unknown }) {
  if (value === null || value === undefined) {
    return <p className="text-[12px] text-muted-foreground">Not available for this period.</p>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      return (
        <p className="text-[12px] text-muted-foreground">
          Nothing to report yet — this becomes available once the first measurement lands.
        </p>
      );
    }
    if (isRowList(value)) return <RowTable rows={value} />;
    return (
      <ul className="space-y-1 text-[12px]">
        {value.map((v, i) => <li key={i} className="tnum">{leaf("", v)}</li>)}
      </ul>
    );
  }
  if (isMoney(value)) {
    return <p className="font-display text-xl font-semibold tnum">{inr(value.paise)}</p>;
  }
  if (typeof value === "object") return <Group obj={value as Record<string, unknown>} />;
  return <p className="text-[13px] tnum">{leaf("", value)}</p>;
}

/* ── how a figure was arrived at ───────────────────────────────── */

const VERIFICATION: Record<string, { label: string; cls: string }> = {
  verified_actual: { label: "Verified actual", cls: "border-state-actual/40 bg-state-actual-soft text-state-actual" },
  derived_from_verified_ledger: { label: "Derived from ledger", cls: "border-state-actual/30 bg-surface text-muted-foreground" },
  measured: { label: "Measured", cls: "border-fin-gain/35 bg-fin-gain-soft text-fin-gain" },
  model_prediction: { label: "Model prediction", cls: "border-state-predicted/40 bg-state-predicted-soft text-state-predicted" },
  derived_indicator: { label: "Derived indicator", cls: "border-border bg-surface text-muted-foreground" },
  mixed_verified_and_estimated: { label: "Partly estimated", cls: "border-fin-warn/35 bg-fin-warn-soft text-fin-warn" },
};

export function VerificationChip({ kind }: { kind: string }) {
  const v = VERIFICATION[kind] ?? { label: titleCase(kind), cls: "border-border bg-surface text-muted-foreground" };
  return (
    <span className={`rw-chip ${v.cls}`} title="How this figure was arrived at">
      {v.label}
    </span>
  );
}
