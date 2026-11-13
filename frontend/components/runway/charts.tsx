"use client";

/**
 * Chart layer.
 *
 * Conventions, applied everywhere:
 *  - ACTUAL is a solid line, PREDICTED is a line with a P10-P90 band,
 *    SIMULATED is dashed. Colour is never the only difference between them.
 *  - The safety buffer is always drawn as a labelled reference line, so a
 *    cash curve is read against the threshold that matters rather than
 *    against zero.
 *  - Axis ticks use compact Indian units (L / Cr), tooltips use full
 *    grouped rupees. A chart is for shape; a tooltip is for the number.
 */

import { useMemo } from "react";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, ComposedChart, Legend, Line,
  LineChart, Pie, PieChart, PolarAngleAxis, RadialBar, RadialBarChart, ReferenceLine,
  ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis,
} from "recharts";
import { inr, shortDate } from "@/lib/format";

export const C = {
  primary: "var(--chart-1)", azure: "var(--chart-2)", teal: "var(--chart-3)",
  amber: "var(--chart-4)", rose: "var(--chart-5)", slate: "var(--chart-6)",
  grid: "var(--chart-grid)", tick: "var(--chart-tick)",
  actual: "var(--state-actual)", predicted: "var(--state-predicted)",
  simulated: "var(--state-simulated)",
  gain: "var(--fin-gain)", loss: "var(--fin-loss)", warn: "var(--fin-warn)",
};

const AXIS = { stroke: C.tick, fontSize: 11, tickLine: false, axisLine: false } as const;

/** Axis-tick money. Deliberately NOT `inr(v, {compact:true})`: that always
 *  carries two decimals and a space ("₹34.00 L"), which overflows a 64px
 *  axis gutter and wraps onto a second line. An axis needs the magnitude,
 *  not the paise — the tooltip carries the exact figure. */
export function compactAxis(v: number) {
  if (v === null || v === undefined || Number.isNaN(v)) return "";
  const neg = v < 0;
  const rupees = Math.abs(v) / 100;
  const unit = (n: number, d: number, suffix: string) => {
    const q = n / d;
    // One decimal only while it still adds information: 8.5L keeps it,
    // 12L and 1Cr do not.
    if (q >= 10) return `${Math.round(q)}${suffix}`;
    const one = q.toFixed(1);
    return `${one.endsWith(".0") ? one.slice(0, -2) : one}${suffix}`;
  };
  let body: string;
  if (rupees >= 1_00_00_000) body = unit(rupees, 1_00_00_000, "Cr");
  else if (rupees >= 1_00_000) body = unit(rupees, 1_00_000, "L");
  else if (rupees >= 1_000) body = unit(rupees, 1_000, "K");
  else body = String(Math.round(rupees));
  return `${neg ? "−" : ""}₹${body}`;
}

export function ChartTip({ active, payload, label, labelFormat, valueFormat }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-border bg-popover/95 px-3 py-2 shadow-lg backdrop-blur">
      {label !== undefined && (
        <p className="mb-1.5 text-[11px] font-medium text-muted-foreground">
          {labelFormat ? labelFormat(label) : label}
        </p>
      )}
      <div className="space-y-1">
        {payload.filter((p: any) => p.value !== null && p.value !== undefined).map((p: any, i: number) => (
          <div key={i} className="flex items-center justify-between gap-5 text-xs">
            <span className="flex items-center gap-1.5">
              <span className="size-2 rounded-[2px]" style={{ background: p.color || p.fill }} aria-hidden />
              <span className="text-muted-foreground">{p.name}</span>
            </span>
            <span className="font-medium tnum">
              {/* A band (e.g. P10-P90) arrives as [low, high]; formatting the
                  pair as one number printed "₹NaN". */}
              {Array.isArray(p.value)
                ? p.value.map((v: number) => (valueFormat ? valueFormat(v, p) : inr(v))).join(" – ")
                : valueFormat ? valueFormat(p.value, p) : inr(p.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── the three-state cash chart ──────────────────────────────── */

export type CashSeries = {
  week_starts: string[];
  p10: number[]; p50: number[]; p90: number[];
  safety_buffer_paise?: number;
};

export function CashBandChart({
  series, scenario, scenarioLabel = "Scenario", actualTo, height = 300, showBuffer = true,
}: {
  series: CashSeries;
  scenario?: { p50: number[]; p10?: number[] } | null;
  scenarioLabel?: string;
  actualTo?: number;
  height?: number;
  showBuffer?: boolean;
}) {
  const data = useMemo(() => series.week_starts.map((w, i) => ({
    week: w,
    idx: i,
    actual: actualTo !== undefined && i <= actualTo ? series.p50[i] : null,
    p50: series.p50[i],
    // Recharts stacks an area by [base, range]; the band is p10 plus the
    // distance to p90 so the fill sits exactly between the quantiles.
    band: [series.p10[i], series.p90[i]] as [number, number],
    p10: series.p10[i],
    p90: series.p90[i],
    scenario: scenario?.p50?.[i] ?? null,
    scenarioP10: scenario?.p10?.[i] ?? null,
  })), [series, scenario, actualTo]);

  const buffer = series.safety_buffer_paise ?? 0;

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
        <defs>
          <linearGradient id="bandFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={C.predicted} stopOpacity={0.22} />
            <stop offset="100%" stopColor={C.predicted} stopOpacity={0.04} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="week" {...AXIS} tickFormatter={shortDate} minTickGap={18} />
        <YAxis {...AXIS} tickFormatter={compactAxis} width={56} />
        <Tooltip
          content={<ChartTip labelFormat={(l: string) => `Week of ${shortDate(l)}`} />}
          cursor={{ stroke: C.grid, strokeWidth: 1 }}
        />
        {showBuffer && buffer > 0 && (
          <ReferenceLine
            y={buffer} stroke={C.warn} strokeDasharray="5 4" strokeWidth={1.5}
            label={{ value: `Safety buffer ${inr(buffer, { compact: true })}`,
                     position: "insideTopLeft", fill: C.warn, fontSize: 10 }}
          />
        )}
        <ReferenceLine y={0} stroke={C.loss} strokeOpacity={0.5} strokeWidth={1} />
        <Area type="monotone" dataKey="band" name="P10–P90 range" stroke="none"
              fill="url(#bandFill)" isAnimationActive={false} activeDot={false}
              legendType="none" />
        <Line type="monotone" dataKey="p10" name="P10 (downside)" stroke={C.predicted}
              strokeOpacity={0.55} strokeWidth={1} dot={false} strokeDasharray="2 3" />
        <Line type="monotone" dataKey="p90" name="P90 (upside)" stroke={C.predicted}
              strokeOpacity={0.55} strokeWidth={1} dot={false} strokeDasharray="2 3" />
        <Line type="monotone" dataKey="p50" name="Predicted (P50)" stroke={C.predicted}
              strokeWidth={2.25} dot={false} activeDot={{ r: 4 }} />
        {actualTo !== undefined && (
          <Line type="monotone" dataKey="actual" name="Actual" stroke={C.actual}
                strokeWidth={2.5} dot={false} connectNulls={false} />
        )}
        {scenario && (
          <Line type="monotone" dataKey="scenario" name={scenarioLabel} stroke={C.simulated}
                strokeWidth={2.25} strokeDasharray="6 4" dot={false} activeDot={{ r: 4 }} />
        )}
        <Legend verticalAlign="bottom" height={28} iconType="plainline"
                wrapperStyle={{ fontSize: 11, color: C.tick }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/* ── inflow / outflow ────────────────────────────────────────── */

export function FlowBars({ weeks, inflow, outflow, height = 220 }:
  { weeks: string[]; inflow: number[]; outflow: number[]; height?: number }) {
  const data = weeks.map((w, i) => ({
    week: w, inflow: inflow[i] ?? 0, outflow: -(outflow[i] ?? 0),
    net: (inflow[i] ?? 0) - (outflow[i] ?? 0),
  }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }} stackOffset="sign">
        <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="week" {...AXIS} tickFormatter={shortDate} minTickGap={18} />
        <YAxis {...AXIS} tickFormatter={compactAxis} width={60} />
        <Tooltip content={<ChartTip labelFormat={(l: string) => `Week of ${shortDate(l)}`}
                                    valueFormat={(v: number) => inr(Math.abs(v))} />} />
        <ReferenceLine y={0} stroke={C.grid} />
        <Bar dataKey="inflow" name="Expected in" fill={C.gain} radius={[3, 3, 0, 0]} stackId="s" />
        <Bar dataKey="outflow" name="Expected out" fill={C.loss} radius={[0, 0, 3, 3]} stackId="s" />
        <Line type="monotone" dataKey="net" name="Net" stroke={C.primary} strokeWidth={2} dot={false} />
        <Legend verticalAlign="bottom" height={24} wrapperStyle={{ fontSize: 11, color: C.tick }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

/* ── receivables ageing ──────────────────────────────────────── */

const AGE_COLORS = [C.teal, C.amber, "var(--chart-4)", C.rose, C.loss];

export function AgeingBars({ buckets, height = 200 }:
  { buckets: { label: string; amount_paise: number; count: number; share: number }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={buckets} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
        <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="label" {...AXIS} />
        <YAxis {...AXIS} tickFormatter={compactAxis} width={60} />
        <Tooltip content={<ChartTip valueFormat={(v: number) => inr(v)} />}
                 cursor={{ fill: "var(--surface-hover)" }} />
        <Bar dataKey="amount_paise" name="Outstanding" radius={[4, 4, 0, 0]}>
          {buckets.map((_, i) => <Cell key={i} fill={AGE_COLORS[Math.min(i, AGE_COLORS.length - 1)]} />)}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── concentration ───────────────────────────────────────────── */

export function ConcentrationPie({ items, height = 220 }:
  { items: { name: string; volume_paise: number; share: number }[]; height?: number }) {
  const palette = [C.primary, C.azure, C.teal, C.amber, C.rose, C.slate];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={items} dataKey="volume_paise" nameKey="name" innerRadius="56%" outerRadius="86%"
             paddingAngle={2} strokeWidth={0}>
          {items.map((_, i) => <Cell key={i} fill={palette[i % palette.length]} />)}
        </Pie>
        <Tooltip content={<ChartTip valueFormat={(v: number) => inr(v)} />} />
        <Legend verticalAlign="bottom" height={34} iconType="circle"
                wrapperStyle={{ fontSize: 11, color: C.tick }} />
      </PieChart>
    </ResponsiveContainer>
  );
}

/* ── health gauge ────────────────────────────────────────────── */

export function HealthGauge({ score, size = 148 }: { score: number; size?: number }) {
  const tone = score >= 80 ? C.gain : score >= 65 ? C.teal : score >= 50 ? C.warn : C.loss;
  return (
    <div className="relative" style={{ width: size, height: size }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadialBarChart innerRadius="74%" outerRadius="100%" data={[{ value: score, fill: tone }]}
                        startAngle={220} endAngle={-40}>
          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
          <RadialBar dataKey="value" cornerRadius={8} background={{ fill: "var(--surface)" }} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div className="pointer-events-none absolute inset-0 grid place-items-center">
        <div className="text-center">
          <p className="font-display text-3xl font-semibold tnum" style={{ color: tone }}>
            {score.toFixed(0)}
          </p>
          <p className="text-[10px] uppercase tracking-wider text-muted-foreground">out of 100</p>
        </div>
      </div>
    </div>
  );
}

/* ── sparkline ───────────────────────────────────────────────── */

export function Spark({ data, color = C.primary, height = 36 }:
  { data: number[]; color?: string; height?: number }) {
  const rows = data.map((v, i) => ({ i, v }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows} margin={{ top: 2, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id={`sp-${color.replace(/\W/g, "")}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area type="monotone" dataKey="v" stroke={color} strokeWidth={1.75}
              fill={`url(#sp-${color.replace(/\W/g, "")})`} isAnimationActive={false} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* ── breach probability by week ──────────────────────────────── */

export function BreachBars({ weeks, probs, height = 150 }:
  { weeks: string[]; probs: number[]; height?: number }) {
  const data = probs.map((p, i) => ({ week: weeks[i + 1] ?? weeks[i], p }));
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 4, left: 4 }}>
        <CartesianGrid stroke={C.grid} strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="week" {...AXIS} tickFormatter={shortDate} minTickGap={16} />
        <YAxis {...AXIS} width={42} tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
               domain={[0, "dataMax"]} />
        <Tooltip content={<ChartTip labelFormat={(l: string) => `Week of ${shortDate(l)}`}
                                    valueFormat={(v: number) => `${(v * 100).toFixed(1)}%`} />}
                 cursor={{ fill: "var(--surface-hover)" }} />
        <Bar dataKey="p" name="Chance of breaching the buffer" radius={[3, 3, 0, 0]}>
          {data.map((d, i) => (
            <Cell key={i} fill={d.p > 0.3 ? C.loss : d.p > 0.12 ? C.warn : C.teal} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ── customer delay vs exposure ──────────────────────────────── */

export function RiskScatter({ points, height = 260 }: {
  points: { name: string; delay: number; exposure: number; reliability: number }[];
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <ScatterChart margin={{ top: 12, right: 16, bottom: 16, left: 4 }}>
        <CartesianGrid stroke={C.grid} strokeDasharray="3 3" />
        <XAxis type="number" dataKey="delay" name="Mean delay" unit="d" {...AXIS}
               label={{ value: "Mean delay vs terms (days)", position: "insideBottom",
                        offset: -8, fill: C.tick, fontSize: 10 }} />
        <YAxis type="number" dataKey="exposure" name="Open exposure" {...AXIS}
               tickFormatter={compactAxis} width={64} />
        <ZAxis type="number" dataKey="reliability" range={[60, 320]} name="Reliability" />
        <Tooltip cursor={{ strokeDasharray: "3 3" }}
                 content={({ active, payload }: any) => {
                   if (!active || !payload?.length) return null;
                   const d = payload[0].payload;
                   return (
                     <div className="rounded-lg border border-border bg-popover/95 px-3 py-2 text-xs shadow-lg backdrop-blur">
                       <p className="font-medium">{d.name}</p>
                       <p className="mt-1 text-muted-foreground">
                         {d.delay > 0 ? "+" : ""}{d.delay.toFixed(1)} days · {inr(d.exposure)} open
                       </p>
                       <p className="text-muted-foreground">Reliability {d.reliability.toFixed(0)}/100</p>
                     </div>
                   );
                 }} />
        <ReferenceLine x={0} stroke={C.gain} strokeDasharray="4 4"
                       label={{ value: "On terms", fill: C.gain, fontSize: 10, position: "top" }} />
        <Scatter data={points} name="Customers">
          {points.map((p, i) => (
            <Cell key={i} fill={p.delay > 20 ? C.loss : p.delay > 8 ? C.warn : C.teal} fillOpacity={0.78} />
          ))}
        </Scatter>
      </ScatterChart>
    </ResponsiveContainer>
  );
}

/* ── risk surface heatmap (plain CSS grid, no chart library) ─── */

export function RiskHeatmap({ weeks, levels }: {
  weeks: string[];
  levels: { label: string; threshold_paise: number; by_week: number[] }[];
}) {
  const cell = (p: number) => {
    const a = Math.min(1, Math.max(0, p));
    const color = a > 0.5 ? "var(--fin-loss)" : a > 0.2 ? "var(--fin-warn)" : "var(--fin-gain)";
    return { background: color, opacity: 0.12 + a * 0.78 };
  };
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-separate border-spacing-[2px] text-[11px]">
        <thead>
          <tr>
            <th className="w-44 px-2 py-1 text-left font-medium text-muted-foreground">Cash falls…</th>
            {weeks.map((w, i) => (
              <th key={w} className="px-1 py-1 text-center font-normal text-muted-foreground">
                W{i + 1}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {levels.map((lv) => (
            <tr key={lv.label}>
              <th scope="row" className="px-2 py-1 text-left font-normal text-muted-foreground">
                {lv.label}
              </th>
              {lv.by_week.map((p, i) => (
                <td key={i} className="rounded-[3px] px-1 py-1.5 text-center tnum"
                    style={cell(p)}
                    title={`${lv.label}, week of ${shortDate(weeks[i])}: ${(p * 100).toFixed(0)}%`}>
                  {p >= 0.01 ? Math.round(p * 100) : "·"}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-[11px] text-muted-foreground">
        Each cell is the chance cash sits below that level in that week, as a percentage.
        Values are interpolated from the simulated quantile paths.
      </p>
    </div>
  );
}
