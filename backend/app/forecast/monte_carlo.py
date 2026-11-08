"""Monte Carlo simulation of the 13-week cash path.

Uncertain inputs, each with a stated distribution:

===========================  ==========================================
Variable                      Distribution
===========================  ==========================================
Receivable payment date       Normal(predicted delay, conformal sigma),
                              truncated at >= 0 days from today, with a
                              shared latent factor across customers.
Sales not yet invoiced        Lognormal around the weekly run-rate, CV
                              taken from the business's own history.
Collection lag on those       Normal(median realised lag, realised sd)
Operating costs               Lognormal, CV 12% (ledger-estimated)
Unplanned expense             Poisson arrivals, Exponential severity
Supplier / statutory dates    Near-deterministic (sigma 0.5-2 days)
===========================  ==========================================

**Correlation.** Treating customer payment delays as independent is the
classic understatement of liquidity risk: when the market is tight,
everybody pays late at once. Each path draws one standard-normal common
factor ``Z`` and each customer's delay uses
``sqrt(rho)*Z + sqrt(1-rho)*e_i`` - a single-factor copula, the same device
used for correlated defaults in credit portfolios. ``rho`` is estimated from
the business's own data by ``analytics.concentration.correlated_exposure``
and defaults to 0.25 when there is too little history.

**Common random numbers.** A scenario comparison re-uses the *same* seed and
therefore the same random draws as the baseline, so the difference between
the two paths is the decision and not the noise. This is standard variance
reduction and it is what makes a 0.3-week runway difference meaningful.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from app.forecast.cashflow import ForecastInputs

DEFAULT_PATHS = 4000


@dataclass
class SimulationResult:
    as_of: str
    horizon_weeks: int
    week_starts: list[str]
    opening_cash_paise: int
    safety_buffer_paise: int
    paths: int
    seed: int
    # weekly closing-cash quantiles, index 0 = today
    p10: list[int]
    p25: list[int]
    p50: list[int]
    p75: list[int]
    p90: list[int]
    mean: list[int]
    inflow_p50: list[int]
    outflow_p50: list[int]
    net_p50: list[int]
    min_cash_p10_paise: int
    min_cash_p50_paise: int
    min_cash_p90_paise: int
    runway_weeks_p10: float
    runway_weeks_p50: float
    runway_weeks_p90: float
    first_breach_week_p50: int | None
    breach_probability: float
    breach_prob_by_week: list[float]
    negative_cash_probability: float
    liquidity_var_paise: int
    liquidity_cvar_paise: int
    expected_shortfall_paise: int
    drivers: list[dict]
    assumptions: dict

    def dict(self) -> dict:
        return self.__dict__.copy()


def _week_index(day_offsets: np.ndarray, as_of: date, n_weeks: int) -> np.ndarray:
    """Map a day offset from ``as_of`` onto a forecast bucket.

    Bucket 0 is **now**: it holds the opening balance and no cash flows.
    Bucket ``w`` (1..n_weeks) covers days ``[(w-1)*7, w*7)`` from today and
    is labelled by the date ``as_of + w*7``, i.e. the balance *at the end of*
    that week.

    Anchoring on ``as_of`` rather than on the calendar Monday matters: with a
    Monday anchor, every payment arriving in the remainder of the current
    week lands in bucket 0 and is silently discarded, which makes "customers
    pay earlier" look like it *destroys* cash.

    Indices past ``n_weeks`` are returned as-is and must be masked out by the
    caller, never clipped - clipping would dump every flow beyond the horizon
    into the final week and invent a jump there.
    """
    return np.floor(np.asarray(day_offsets, dtype=float) / 7.0).astype(int) + 1


def _scatter(target: np.ndarray, idx: np.ndarray, values: np.ndarray, n_weeks: int) -> int:
    """Accumulate ``values`` into ``target[path, week]``, dropping anything
    outside the horizon. Returns the paise dropped (reported as 'beyond
    horizon' so nothing silently disappears)."""
    paths = target.shape[0]
    rows = np.repeat(np.arange(paths), idx.shape[1]) if idx.ndim == 2 else np.arange(paths)
    flat_idx = idx.reshape(-1) if idx.ndim == 2 else idx
    flat_val = values.reshape(-1) if np.ndim(values) == 2 else np.broadcast_to(
        values, flat_idx.shape).astype(float)
    mask = (flat_idx >= 0) & (flat_idx <= n_weeks)
    np.add.at(target, (rows[mask], flat_idx[mask]), flat_val[mask])
    return int(flat_val[~mask].sum() / paths) if (~mask).any() else 0


def simulate(fi: ForecastInputs, *, paths: int = DEFAULT_PATHS, seed: int = 20260101,
             confidence: float = 0.95) -> SimulationResult:
    rng = np.random.default_rng(seed)
    W = fi.horizon_weeks
    week_starts = [fi.as_of + timedelta(days=7 * i) for i in range(W + 1)]

    inflow = np.zeros((paths, W + 1))
    outflow = np.zeros((paths, W + 1))
    beyond_receivables = beyond_payables = beyond_new_sales = 0

    # ── receivables with a single common latent factor ─────────────
    if fi.inflows:
        amt = np.array([i.amount_paise for i in fi.inflows], dtype=float)
        mu = np.array([i.day_offset for i in fi.inflows], dtype=float)
        sg = np.array([i.sigma_days for i in fi.inflows], dtype=float)
        cps = sorted({i.counterparty_id for i in fi.inflows})
        cp_ix = np.array([cps.index(i.counterparty_id) for i in fi.inflows])

        rho = float(np.clip(fi.delay_correlation, 0.0, 0.95))
        Z = rng.standard_normal((paths, 1))                       # market-wide factor
        E = rng.standard_normal((paths, len(cps)))                # customer-specific
        cust = np.sqrt(rho) * Z + np.sqrt(1 - rho) * E            # (paths, n_customers)
        idio = rng.standard_normal((paths, len(fi.inflows)))      # invoice-specific
        shock = 0.75 * cust[:, cp_ix] + 0.25 * idio
        days = np.maximum(0.0, mu[None, :] + sg[None, :] * shock)
        wi = _week_index(days, fi.as_of, W)
        vals = np.broadcast_to(amt[None, :], wi.shape).astype(float)
        beyond_receivables = _scatter(inflow, wi, vals, W)

    # ── scheduled outflows ─────────────────────────────────────────
    if fi.outflows:
        oamt = np.array([o.amount_paise for o in fi.outflows], dtype=float)
        omu = np.array([o.day_offset for o in fi.outflows], dtype=float)
        osg = np.array([o.sigma_days for o in fi.outflows], dtype=float)
        od = np.maximum(0.0, omu[None, :] + osg[None, :] * rng.standard_normal((paths, len(oamt))))
        owi = _week_index(od, fi.as_of, W)
        beyond_payables = _scatter(outflow, owi,
                                   np.broadcast_to(oamt[None, :], owi.shape).astype(float), W)

    # ── sales not yet invoiced, and the purchases they trigger ──────
    cv = float(np.clip(fi.revenue_cv, 0.05, 0.6))
    sigma_ln = np.sqrt(np.log(1 + cv ** 2))
    new_sales = np.array(fi.weekly_new_sales_paise, dtype=float)
    if new_sales.size:
        mult = rng.lognormal(mean=-0.5 * sigma_ln ** 2, sigma=sigma_ln, size=(paths, new_sales.size))
        realised = new_sales[None, :] * mult
        lag = np.maximum(
            1.0, rng.normal(fi.new_sales_collection_lag_days, fi.new_sales_lag_sigma,
                            size=(paths, new_sales.size)))
        committed = fi.baseline_weekly_sales_paise or list(new_sales)
        for k in range(new_sales.size):
            # sale is booked mid-week k+1, collected lag days later
            day = (k + 0.5) * 7 + lag[:, k]
            wi = _week_index(day, fi.as_of, W)
            beyond_new_sales += _scatter(inflow, wi, realised[:, k], W)
            # Purchase to support it: raised ahead of the sale, paid on terms.
            # Inside the committed window the order is already placed, so the
            # cash goes out whatever happens to the sale.
            # Full commitment inside the lead-plus-terms window, then a linear
            # taper: a buyer can renegotiate or cancel later orders, but not
            # instantly and not all of them.
            C = max(1, fi.committed_purchase_weeks)
            if k < len(committed):
                frac = 1.0 if k < C else max(0.0, 1.0 - (k - C + 1) / C)
                buy = np.maximum(realised[:, k], float(committed[k]) * frac)
            else:
                buy = realised[:, k]
            pday = (k + 0.5) * 7 - fi.cogs_lead_days + fi.cogs_payment_days
            pwi = _week_index(np.full(paths, max(0.0, pday)), fi.as_of, W)
            _scatter(outflow, pwi, buy * fi.cogs_ratio, W)

    # ── recurring opex ──────────────────────────────────────────────
    if fi.weekly_opex_paise > 0:
        s = np.sqrt(np.log(1 + fi.opex_cv ** 2))
        outflow[:, 1:] += fi.weekly_opex_paise * rng.lognormal(
            mean=-0.5 * s ** 2, sigma=s, size=(paths, W))

    # ── unplanned expense shocks ────────────────────────────────────
    if fi.shock_weekly_rate > 0:
        n = rng.poisson(fi.shock_weekly_rate, size=(paths, W))
        sev = rng.exponential(fi.shock_mean_paise, size=(paths, W))
        outflow[:, 1:] += n * sev

    # ── assemble paths ──────────────────────────────────────────────
    # Bucket 0 carries no flows by construction (see _week_index).
    net = inflow - outflow
    assert not net[:, 0].any(), "bucket 0 must stay empty - it is today's balance"
    closing = fi.opening_cash_paise + np.cumsum(net, axis=1)

    q = lambda a, p: np.percentile(a, p, axis=0).round().astype(np.int64).tolist()
    buffer = fi.safety_buffer_paise
    below = closing[:, 1:] < buffer
    breach_any = below.any(axis=1)
    first = np.where(breach_any, below.argmax(axis=1) + 1, 0)

    mins = closing[:, 1:].min(axis=1)
    # Liquidity VaR / CVaR, adapted from market risk: the loss variable is the
    # shortfall of the worst weekly cash position against the safety buffer.
    loss = np.maximum(0.0, buffer - mins)
    alpha = confidence
    var = float(np.quantile(loss, alpha))
    tail = loss[loss >= var]
    cvar = float(tail.mean()) if tail.size else var

    runway = _runway_weeks(closing, buffer)

    return SimulationResult(
        as_of=fi.as_of.isoformat(), horizon_weeks=W,
        week_starts=[w.isoformat() for w in week_starts],
        opening_cash_paise=int(fi.opening_cash_paise), safety_buffer_paise=int(buffer),
        paths=paths, seed=seed,
        p10=q(closing, 10), p25=q(closing, 25), p50=q(closing, 50),
        p75=q(closing, 75), p90=q(closing, 90),
        mean=closing.mean(axis=0).round().astype(np.int64).tolist(),
        inflow_p50=q(inflow, 50), outflow_p50=q(outflow, 50), net_p50=q(net, 50),
        min_cash_p10_paise=int(np.percentile(mins, 10)),
        min_cash_p50_paise=int(np.percentile(mins, 50)),
        min_cash_p90_paise=int(np.percentile(mins, 90)),
        runway_weeks_p10=round(float(np.percentile(runway, 10)), 2),
        runway_weeks_p50=round(float(np.percentile(runway, 50)), 2),
        runway_weeks_p90=round(float(np.percentile(runway, 90)), 2),
        first_breach_week_p50=(int(np.median(first[breach_any])) if breach_any.any() else None),
        breach_probability=round(float(breach_any.mean()), 4),
        breach_prob_by_week=[round(float(x), 4) for x in below.mean(axis=0)],
        negative_cash_probability=round(float((closing[:, 1:] < 0).any(axis=1).mean()), 4),
        liquidity_var_paise=int(var), liquidity_cvar_paise=int(cvar),
        expected_shortfall_paise=int(loss.mean()),
        drivers=_drivers(fi),
        assumptions={
            **fi.assumptions,
            "paths": paths, "seed": seed,
            "delay_correlation_rho": fi.delay_correlation,
            "revenue_cv": round(cv, 3), "opex_cv": fi.opex_cv,
            "shock_weekly_rate": fi.shock_weekly_rate,
            "shock_mean_paise": fi.shock_mean_paise,
            "var_confidence": confidence,
            "var_definition": ("Liquidity VaR: the shortfall of the worst weekly cash "
                               "position against the safety buffer, at the stated "
                               "confidence. This is an operational liquidity measure "
                               "adapted from market-risk VaR. It is NOT a regulated "
                               "investment VaR and carries no regulatory meaning."),
            "cvar_definition": ("Mean shortfall in the tail beyond the VaR point - how "
                                "bad it gets when it goes bad."),
            "quantile_convention": ("P10 is a pessimistic cash path and P90 an optimistic "
                                    "one. These are simulation quantiles, not guarantees."),
            "horizon_truncation_note": (
                "A 13-week window sees the cash cost of a revenue change sooner "
                "than its collection effect, because purchases are paid in "
                f"roughly {fi.cogs_lead_days + fi.cogs_payment_days} days while "
                f"collections arrive after about "
                f"{fi.new_sales_collection_lag_days:.0f} days. Read a revenue "
                "shock's full impact over two quarters, not one."),
            "beyond_horizon_paise": {
                "receivables": beyond_receivables,
                "sales_not_yet_invoiced": beyond_new_sales,
                "payables": beyond_payables,
                "note": ("Mean paise per path that falls after week "
                         f"{W} and is therefore excluded. Money arriving after the "
                         "horizon cannot pay a bill inside it."),
            },
        })


def _runway_weeks(closing: np.ndarray, buffer: int) -> np.ndarray:
    """Weeks until the path first falls below the buffer.

    Reported as the horizon when it never does, so the statistic is censored
    and ``runway >= horizon`` must be read as "beyond the forecast window",
    not as a precise number.
    """
    paths, n = closing.shape
    W = n - 1
    below = closing[:, 1:] < buffer
    out = np.full(paths, float(W))
    any_b = below.any(axis=1)
    idx = below.argmax(axis=1)
    prev = np.where(idx == 0, closing[:, 0], closing[np.arange(paths), idx])
    cur = closing[np.arange(paths), idx + 1]
    denom = np.where(prev - cur != 0, prev - cur, 1.0)
    frac = np.clip((prev - buffer) / denom, 0.0, 1.0)
    out[any_b] = (idx[any_b] + frac[any_b])
    return out


def _drivers(fi: ForecastInputs) -> list[dict]:
    """What is actually moving the forecast, largest first."""
    rows = []
    tot_in = sum(i.amount_paise for i in fi.inflows)
    if tot_in:
        rows.append({"driver": "Open receivables", "direction": "inflow",
                     "amount_paise": tot_in, "count": len(fi.inflows),
                     "evidence": "invoice-level, from the ledger"})
    new_total = int(sum(fi.weekly_new_sales_paise))
    if new_total:
        rows.append({"driver": "Sales not yet invoiced (run-rate)", "direction": "inflow",
                     "amount_paise": new_total, "count": len(fi.weekly_new_sales_paise),
                     "evidence": "estimated - de-seasonalised trailing median"})
    by_kind: dict[str, dict] = {}
    for o in fi.outflows:
        e = by_kind.setdefault(o.kind, {"driver": o.kind.replace("_", " ").title(),
                                        "direction": "outflow", "amount_paise": 0, "count": 0,
                                        "evidence": "scheduled, from the ledger"})
        e["amount_paise"] += o.amount_paise
        e["count"] += 1
    rows.extend(by_kind.values())
    if fi.weekly_opex_paise:
        rows.append({"driver": "Recurring operating costs", "direction": "outflow",
                     "amount_paise": fi.weekly_opex_paise * fi.horizon_weeks,
                     "count": fi.horizon_weeks, "evidence": "estimated - trailing run-rate"})
    cogs = int(sum(fi.weekly_new_sales_paise) * fi.cogs_ratio)
    if cogs:
        rows.append({"driver": "Purchases for forecast sales", "direction": "outflow",
                     "amount_paise": cogs, "count": len(fi.weekly_new_sales_paise),
                     "evidence": f"estimated - {fi.cogs_ratio:.0%} of forecast sales"})
    rows.sort(key=lambda r: -r["amount_paise"])
    return rows


def sensitivity(fi: ForecastInputs, *, paths: int = 1200, seed: int = 20260101) -> list[dict]:
    """One-at-a-time elasticity of minimum cash to each major assumption.

    Common random numbers throughout, so each row isolates the assumption
    rather than the sampling noise.
    """
    base = simulate(fi, paths=paths, seed=seed)
    out = []
    knobs = [
        ("All customers pay 7 days later", lambda f: [setattr(i, "day_offset", i.day_offset + 7)
                                                      for i in f.inflows]),
        ("All customers pay 7 days earlier", lambda f: [setattr(i, "day_offset", max(0.0, i.day_offset - 7))
                                                        for i in f.inflows]),
        ("Sales run-rate 10% lower", lambda f: setattr(
            f, "weekly_new_sales_paise", [int(v * 0.9) for v in f.weekly_new_sales_paise])),
        ("Sales run-rate 10% higher", lambda f: setattr(
            f, "weekly_new_sales_paise", [int(v * 1.1) for v in f.weekly_new_sales_paise])),
        ("Purchase cost 5% higher", lambda f: setattr(f, "cogs_ratio", f.cogs_ratio * 1.05)),
        ("Operating costs 10% higher", lambda f: setattr(
            f, "weekly_opex_paise", int(f.weekly_opex_paise * 1.1))),
        ("Delay correlation 0.6 instead of estimated",
         lambda f: setattr(f, "delay_correlation", 0.6)),
    ]
    for label, mutate in knobs:
        f = fi.copy()
        mutate(f)
        r = simulate(f, paths=paths, seed=seed)
        out.append({
            "assumption": label,
            "min_cash_p50_delta_paise": r.min_cash_p50_paise - base.min_cash_p50_paise,
            "min_cash_p10_delta_paise": r.min_cash_p10_paise - base.min_cash_p10_paise,
            "runway_p50_delta_weeks": round(r.runway_weeks_p50 - base.runway_weeks_p50, 2),
            "breach_probability_delta": round(r.breach_probability - base.breach_probability, 4),
        })
    out.sort(key=lambda r: r["min_cash_p50_delta_paise"])
    return out
