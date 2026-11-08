"""Invoice-level payment-delay prediction.

Model stack, in the order they are tried and compared:

* **B0 - global median delay.** The number you get for free.
* **B1 - per-customer expanding median.** The strongest cheap baseline, and
  the one a spreadsheet could produce. Anything more complex has to beat it.
* **M - gradient-boosted quantile regression** at alpha = 0.1 / 0.5 / 0.9.
  Chosen over a neural model because the dataset is small (hundreds to a few
  thousand invoices), the relationships are monotone-ish, and the per-feature
  contributions can be read off directly.

Intervals from quantile regression are *not* calibrated out of the box, so a
**split-conformal** step rescales them on a held-out calibration slice until
the empirical coverage matches the nominal 80%. This is what lets RUNWAY say
"P10-P90" and mean it.

Everything is evaluated on a chronological split. There is no shuffling
anywhere in this module.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np

from app.forecast.features import FEATURE_NAMES, FeatureRow, build_features, settled_rows

MODEL_VERSION = "pdm-gbq-conformal-1.2.0"
MIN_TRAIN = 60
TEST_FRACTION = 0.2
CALIB_FRACTION = 0.2


@dataclass
class DelayModel:
    version: str = MODEL_VERSION
    trained: bool = False
    fallback_reason: str = ""
    global_median: float = 0.0
    customer_median: dict[str, float] = field(default_factory=dict)
    customer_sd: dict[str, float] = field(default_factory=dict)
    models: dict = field(default_factory=dict)        # alpha -> estimator
    median_estimator_key: object = 0.5                # 0.5 or "abs"
    blend_weight: float = 1.0                         # 1 = pure model, 0 = pure baseline
    train_customer_median: dict[str, float] = field(default_factory=dict)
    conformal_scale: float = 1.0
    residual_sd: float = 7.0
    feature_means: np.ndarray | None = None
    metrics: dict = field(default_factory=dict)
    selection_note: str = ""
    n_train: int = 0
    n_test: int = 0

    # ── prediction ────────────────────────────────────────────────

    def predict_row(self, r: FeatureRow) -> dict:
        cust_fallback = self.customer_median.get(r.counterparty_id, self.global_median)
        if not self.trained:
            sd = self.customer_sd.get(r.counterparty_id, self.residual_sd) or self.residual_sd
            p50 = cust_fallback
            return self._assemble(r, p50 - 1.2816 * sd, p50, p50 + 1.2816 * sd,
                                  source="per-customer median (model not trained)",
                                  drivers=[{"feature": "customer history",
                                            "contribution_days": round(p50 - self.global_median, 2),
                                            "value": round(cust_fallback, 2)}])
        X = r.x.reshape(1, -1)
        p50 = self._median(X, r.counterparty_id)
        raw50 = float(self.models[self.median_estimator_key].predict(X)[0])
        p10 = p50 + (float(self.models[0.1].predict(X)[0]) - raw50)
        p90 = p50 + (float(self.models[0.9].predict(X)[0]) - raw50)
        # Conformal widening around the median, then re-sort so quantiles
        # can never cross (a quantile forest can produce p10 > p90 locally).
        p10 = p50 - (p50 - p10) * self.conformal_scale
        p90 = p50 + (p90 - p50) * self.conformal_scale
        p10, p50, p90 = sorted((p10, p50, p90))
        return self._assemble(r, p10, p50, p90, source=f"{self.version} quantile GBM + conformal",
                              drivers=self.explain(r))

    def _median(self, X, counterparty_id: str) -> float:
        """Stacked prediction: the GBM blended with the per-customer median.

        The blend weight is fitted on a held-out calibration slice, so the
        stack is guaranteed on that slice to be no worse than whichever of
        the two components is better. This is the mechanism that stops a
        fashionable model from shipping when a median would do.
        """
        model_p = float(self.models[self.median_estimator_key].predict(X)[0])
        base_p = self.train_customer_median.get(counterparty_id, self.global_median)
        w = self.blend_weight
        return w * model_p + (1.0 - w) * base_p

    def _assemble(self, r: FeatureRow, p10: float, p50: float, p90: float,
                  *, source: str, drivers: list) -> dict:
        p10, p50, p90 = (max(-10.0, v) for v in (p10, p50, p90))
        spread = max(1.0, (p90 - p10) / 2.5631)   # implied sigma from an 80% band
        pay = r.due_date + timedelta(days=int(round(p50)))
        today_ref = r.due_date
        return {
            "invoice_id": r.invoice_id,
            "predicted_delay_days_p10": round(p10, 2),
            "predicted_delay_days_p50": round(p50, 2),
            "predicted_delay_days_p90": round(p90, 2),
            "predicted_pay_date": pay.isoformat(),
            "sigma_days": round(spread, 2),
            "prob_within_7": round(_norm_cdf((7 - p50) / spread), 4),
            "prob_within_15": round(_norm_cdf((15 - p50) / spread), 4),
            "prob_within_30": round(_norm_cdf((30 - p50) / spread), 4),
            "prob_default": round(max(0.0, 1 - _norm_cdf((120 - p50) / spread)), 4),
            "confidence": round(min(1.0, 1.0 / (1.0 + spread / 12.0)), 3),
            "model_version": self.version, "source": source, "drivers": drivers,
            "_ref_date": today_ref.isoformat(),
        }

    def explain(self, r: FeatureRow, top_k: int = 5) -> list[dict]:
        """Per-feature contribution by single-feature ablation against the
        training mean. Model-agnostic, deterministic and cheap - the same
        shape of answer SHAP gives, without the extra dependency.

        A positive contribution means that feature pushes the predicted
        payment *later*.
        """
        if not self.trained or self.feature_means is None:
            return []
        base = float(self.models[0.5].predict(self.feature_means.reshape(1, -1))[0])
        full = float(self.models[0.5].predict(r.x.reshape(1, -1))[0])
        contribs = []
        for i, name in enumerate(FEATURE_NAMES):
            x = self.feature_means.copy()
            x[i] = r.x[i]
            v = float(self.models[0.5].predict(x.reshape(1, -1))[0])
            contribs.append({"feature": name, "contribution_days": round(v - base, 2),
                             "value": round(float(r.x[i]), 3)})
        contribs.sort(key=lambda c: -abs(c["contribution_days"]))
        out = contribs[:top_k]
        out.append({"feature": "_baseline_prediction_days", "contribution_days": round(base, 2),
                    "value": None})
        out.append({"feature": "_model_prediction_days", "contribution_days": round(full, 2),
                    "value": None})
        return out


def _norm_cdf(z: float) -> float:
    from math import erf, sqrt
    return 0.5 * (1.0 + erf(z / sqrt(2.0)))


# ──────────────────────────── training ─────────────────────────────

def train(invoices: list, as_of: date, *, verbose: bool = False) -> DelayModel:
    rows = build_features(invoices, as_of)
    done = settled_rows(rows)
    m = DelayModel()

    # Per-customer expanding baselines are always available.
    by_cp: dict[str, list[float]] = {}
    for r in done:
        by_cp.setdefault(r.counterparty_id, []).append(r.y)
    allv = np.array([r.y for r in done], dtype=float) if done else np.array([0.0])
    m.global_median = float(np.median(allv))
    m.residual_sd = float(allv.std()) or 7.0
    for cp, v in by_cp.items():
        a = np.array(v, dtype=float)
        m.customer_median[cp] = float(np.median(a))
        m.customer_sd[cp] = float(a.std()) if a.size > 1 else m.residual_sd

    if len(done) < MIN_TRAIN:
        m.fallback_reason = (f"only {len(done)} settled invoices available, "
                             f"{MIN_TRAIN} required to fit the model")
        m.metrics = {"status": "untrained", "reason": m.fallback_reason}
        return m

    done.sort(key=lambda r: r.issue_date)   # chronological, never shuffled
    n = len(done)
    n_test = max(20, int(n * TEST_FRACTION))
    n_calib = max(20, int(n * CALIB_FRACTION))
    train_rows = done[: n - n_test - n_calib]
    calib_rows = done[n - n_test - n_calib: n - n_test]
    test_rows = done[n - n_test:]
    if len(train_rows) < MIN_TRAIN:
        m.fallback_reason = "not enough history left after the chronological split"
        m.metrics = {"status": "untrained", "reason": m.fallback_reason}
        return m

    Xtr = np.vstack([r.x for r in train_rows]); ytr = np.array([r.y for r in train_rows])
    Xca = np.vstack([r.x for r in calib_rows]); yca = np.array([r.y for r in calib_rows])
    Xte = np.vstack([r.x for r in test_rows]);  yte = np.array([r.y for r in test_rows])

    from sklearn.ensemble import GradientBoostingRegressor
    params = dict(n_estimators=300, max_depth=3, learning_rate=0.05,
                  subsample=0.9, min_samples_leaf=12, random_state=42)
    for alpha in (0.1, 0.5, 0.9):
        est = GradientBoostingRegressor(loss="quantile", alpha=alpha, **params)
        est.fit(Xtr, ytr)
        m.models[alpha] = est
    # An L1 regressor usually beats the alpha=0.5 pinball fit on MAE; keep
    # whichever actually wins on the calibration slice.
    abs_est = GradientBoostingRegressor(loss="absolute_error", **params).fit(Xtr, ytr)
    m.models["abs"] = abs_est
    m.feature_means = Xtr.mean(axis=0)
    m.trained = True
    m.n_train, m.n_test = len(train_rows), len(test_rows)

    for r in train_rows:
        m.train_customer_median.setdefault(r.counterparty_id, [])
    tr_hist: dict[str, list[float]] = {}
    for r in train_rows:
        tr_hist.setdefault(r.counterparty_id, []).append(r.y)
    m.train_customer_median = {cp: float(np.median(v)) for cp, v in tr_hist.items()}

    mae_q = float(np.mean(np.abs(m.models[0.5].predict(Xca) - yca)))
    mae_a = float(np.mean(np.abs(abs_est.predict(Xca) - yca)))
    m.median_estimator_key = "abs" if mae_a <= mae_q else 0.5

    # Fit the stacking weight on the calibration slice only.
    base_ca = np.array([m.train_customer_median.get(r.counterparty_id, m.global_median)
                        for r in calib_rows])
    model_ca = m.models[m.median_estimator_key].predict(Xca)
    grid = np.linspace(0.0, 1.0, 21)
    maes = [float(np.mean(np.abs(w * model_ca + (1 - w) * base_ca - yca))) for w in grid]
    best_w = float(grid[int(np.argmin(maes))])
    base_mae, best_mae = maes[0], min(maes)
    # Paired comparison on the calibration slice: the two predictors score the
    # same invoices, so the right test is on the per-invoice difference in
    # absolute error, not on the two error distributions separately.
    stacked_ca = best_w * model_ca + (1 - best_w) * base_ca
    diff = np.abs(base_ca - yca) - np.abs(stacked_ca - yca)   # >0 means the stack wins
    se = float(np.std(diff, ddof=1)) / np.sqrt(len(diff)) if len(diff) > 2 else float("inf")
    t_stat = float(np.mean(diff) / se) if se > 0 else 0.0
    rel_gain = (base_mae - best_mae) / max(1e-9, base_mae)
    ship = bool(t_stat >= 1.96 and rel_gain >= 0.02)
    m.blend_weight = best_w if ship else 0.0
    m.selection_note = (
        f"paired calibration test over {len(diff)} invoices: baseline MAE {base_mae:.2f}d, "
        f"stacked {best_mae:.2f}d at w={best_w:.2f} ({rel_gain:+.1%}, t={t_stat:+.2f}). "
        + ("Learned model shipped." if ship else
           "Learned model NOT shipped - the improvement is not distinguishable from noise "
           "(needs t>=1.96 and >=2% gain), so RUNWAY uses the per-customer median."))

    # Split conformal: scale the band until held-out coverage reaches 80%.
    raw_ca = m.models[m.median_estimator_key].predict(Xca)
    c50 = m.blend_weight * raw_ca + (1 - m.blend_weight) * base_ca
    c10 = c50 + (m.models[0.1].predict(Xca) - raw_ca)
    c90 = c50 + (m.models[0.9].predict(Xca) - raw_ca)
    lo_gap = np.maximum(1e-6, c50 - c10)
    hi_gap = np.maximum(1e-6, c90 - c50)
    nonconf = np.maximum((c50 - yca) / lo_gap, (yca - c50) / hi_gap)
    k = int(np.ceil((len(yca) + 1) * 0.80)) - 1
    m.conformal_scale = float(np.sort(nonconf)[min(k, len(nonconf) - 1)])
    m.conformal_scale = float(np.clip(m.conformal_scale, 0.5, 4.0))

    m.metrics = _evaluate(m, train_rows, test_rows, Xte, yte)
    if verbose:
        print(json.dumps(m.metrics, indent=2))
    return m


# ─────────────────────────── evaluation ────────────────────────────

def _pinball(y: np.ndarray, q: np.ndarray, alpha: float) -> float:
    d = y - q
    return float(np.mean(np.maximum(alpha * d, (alpha - 1) * d)))


def _evaluate(m: DelayModel, train_rows, test_rows, Xte, yte) -> dict:
    raw = m.models[m.median_estimator_key].predict(Xte)
    base_te = np.array([m.train_customer_median.get(r.counterparty_id, m.global_median)
                        for r in test_rows])
    p50 = m.blend_weight * raw + (1 - m.blend_weight) * base_te
    p10 = p50 + (m.models[0.1].predict(Xte) - raw)
    p90 = p50 + (m.models[0.9].predict(Xte) - raw)
    p10c = p50 - (p50 - p10) * m.conformal_scale
    p90c = p50 + (p90 - p50) * m.conformal_scale

    # Baselines measured on exactly the same test rows.
    b0 = np.full_like(yte, m.global_median, dtype=float)
    tr_by_cp: dict[str, list[float]] = {}
    for r in train_rows:
        tr_by_cp.setdefault(r.counterparty_id, []).append(r.y)
    b1 = np.array([float(np.median(tr_by_cp.get(r.counterparty_id, [m.global_median])))
                   for r in test_rows])

    def stats(pred):
        err = pred - yte
        mae = float(np.mean(np.abs(err)))
        rmse = float(np.sqrt(np.mean(err ** 2)))
        denom = float(np.sum(np.abs(yte))) or 1.0
        return {"mae_days": round(mae, 3), "rmse_days": round(rmse, 3),
                "wape": round(float(np.sum(np.abs(err))) / denom, 4),
                "bias_days": round(float(np.mean(err)), 3)}

    cov_raw = float(np.mean((yte >= p10) & (yte <= p90)))
    cov_cal = float(np.mean((yte >= p10c) & (yte <= p90c)))
    model_mae = float(np.mean(np.abs(p50 - yte)))
    b1_mae = float(np.mean(np.abs(b1 - yte)))

    # Does it actually help us decide? Treat "will be more than 15 days late"
    # as the operational alert and measure precision/recall of that call.
    late_true = yte > 15
    late_pred = p50 > 15
    tp = int(np.sum(late_true & late_pred)); fp = int(np.sum(~late_true & late_pred))
    fn = int(np.sum(late_true & ~late_pred))
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None

    return {
        "status": "trained", "model_version": m.version,
        "split": "chronological (no shuffling)",
        "median_estimator": str(m.median_estimator_key),
        "stacking_weight_on_gbm": round(m.blend_weight, 3),
        "model_selection": m.selection_note,
        "n_train": m.n_train, "n_test": int(len(yte)),
        "model": stats(p50),
        "baseline_global_median": stats(b0),
        "baseline_customer_median": stats(b1),
        "improvement_vs_customer_median_pct": round(100 * (b1_mae - model_mae) / b1_mae, 2)
            if b1_mae else None,
        "beats_customer_median_baseline": bool(model_mae < b1_mae),
        "pinball_p10": round(_pinball(yte, p10c, 0.1), 4),
        "pinball_p50": round(_pinball(yte, p50, 0.5), 4),
        "pinball_p90": round(_pinball(yte, p90c, 0.9), 4),
        "coverage_p10_p90_raw": round(cov_raw, 4),
        "coverage_p10_p90_conformal": round(cov_cal, 4),
        "coverage_target": 0.80,
        "conformal_scale": round(m.conformal_scale, 3),
        "late_alert_precision_gt15d": round(precision, 3) if precision is not None else None,
        "late_alert_recall_gt15d": round(recall, 3) if recall is not None else None,
        "note": ("All figures are produced by app.forecast.payment_delay on the held-out "
                 "chronological tail of this business's own invoices. Re-run "
                 "scripts/evaluate_models.py to reproduce."),
    }


def predict_open(model: DelayModel, invoices: list, as_of: date) -> list[dict]:
    rows = build_features(invoices, as_of)
    out = []
    for r in rows:
        if r.outstanding_paise <= 0:
            continue
        p = model.predict_row(r)
        pay = date.fromisoformat(p["predicted_pay_date"])
        # A prediction may not land in the past: an unpaid invoice whose
        # predicted date has already gone is re-anchored to today plus the
        # remaining tail of the distribution.
        if pay < as_of:
            # Shift the whole distribution, not just the median, or the
            # quantiles cross and every downstream interval becomes nonsense.
            overdue = (as_of - r.due_date).days
            extra = max(3.0, p["sigma_days"] * 0.6)
            shift = (overdue + extra) - p["predicted_delay_days_p50"]
            for k in ("predicted_delay_days_p10", "predicted_delay_days_p50",
                      "predicted_delay_days_p90"):
                p[k] = round(p[k] + shift, 2)
            p["predicted_pay_date"] = (as_of + timedelta(days=int(round(extra)))).isoformat()
            sig = p["sigma_days"]
            p50n = p["predicted_delay_days_p50"]
            p["prob_within_7"] = round(_norm_cdf((overdue + 7 - p50n) / sig), 4)
            p["prob_within_15"] = round(_norm_cdf((overdue + 15 - p50n) / sig), 4)
            p["prob_within_30"] = round(_norm_cdf((overdue + 30 - p50n) / sig), 4)
            p["source"] += " (re-anchored: already past the predicted date)"
        p["outstanding_paise"] = r.outstanding_paise
        p["counterparty_id"] = r.counterparty_id
        p["due_date"] = r.due_date.isoformat()
        out.append(p)
    return out
