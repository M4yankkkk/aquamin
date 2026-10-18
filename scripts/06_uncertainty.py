"""
Uncertainty quantification: can a reduced-parameter model say how much to
trust each prediction? Three interval methods at a nominal 90% level, all
evaluated on unseen stations:
  1. GPR predictive standard deviation (Gaussian interval),
  2. split-conformal (CV+ style) around XGBoost, using inner station-CV residuals,
  3. conformalised quantile regression (CQR) with gradient-boosting quantile models.
Writes results/uncertainty*.csv and figures/fig_unc_*.
"""

import sys

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import norm
from sklearn.model_selection import GroupKFold
from sklearn.ensemble import HistGradientBoostingRegressor

from common import (SEED, SUBSET_COLORS, SUBSETS, TARGET, RESULTS, category, load_model_set,
                    make_model, savefig, setup_plotting, station_folds)

plt = setup_plotting()
ALPHA = 0.10
SETS = ["S3", "S4-routine", "S5", "S7", "I3-importance", "Full-8"]
LEVELS = [0.5, 0.6, 0.7, 0.8, 0.9, 0.95]


class QuantilePair:
    """Lower/upper quantile gradient-boosting models. sklearn's histogram GBM
    re-fits leaf values to the exact quantile at each step; XGBoost's quantile
    objective (constant-magnitude gradients) under-fits at this learning rate
    and gave near-constant ~15-point intervals regardless of inputs."""

    def __init__(self, lo, hi):
        self.lo, self.hi = lo, hi

    def fit(self, X, y):
        kw = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=20,
                  random_state=SEED)
        self.m_lo = HistGradientBoostingRegressor(loss="quantile", quantile=self.lo, **kw).fit(X, y)
        self.m_hi = HistGradientBoostingRegressor(loss="quantile", quantile=self.hi, **kw).fit(X, y)
        return self

    def predict(self, X):
        return np.column_stack([self.m_lo.predict(X), self.m_hi.predict(X)])


def xgb_quantile(lo, hi):
    return QuantilePair(lo, hi)


def conformal_q(scores, level):
    n = len(scores)
    k = min(n, int(np.ceil((n + 1) * level)))
    return np.sort(scores)[k - 1]


def run_fold(df, cols, tr, te):
    """Returns per-test-row: y, xgb point, conformal residual-quantiles at each
    level, CQR bounds (90%), GPR mean/std."""
    y = df[TARGET].to_numpy()
    X = df[cols]
    dtr = df.iloc[tr]
    inner = list(GroupKFold(5, shuffle=True, random_state=SEED).split(dtr, groups=dtr["Station"]))

    # inner OOF residuals (point model) and CQR scores
    res_abs = np.empty(len(tr))
    cqr_scores = np.empty(len(tr))
    for itr, ite in inner:
        a, b = tr[itr], tr[ite]
        m = make_model("XGBoost", cols).fit(X.iloc[a], y[a])
        res_abs[ite] = np.abs(y[b] - m.predict(X.iloc[b]))
        qm = xgb_quantile(ALPHA / 2, 1 - ALPHA / 2).fit(X.iloc[a], y[a])
        qp = qm.predict(X.iloc[b])
        cqr_scores[ite] = np.maximum(qp[:, 0] - y[b], y[b] - qp[:, 1])

    m = make_model("XGBoost", cols).fit(X.iloc[tr], y[tr])
    point = m.predict(X.iloc[te])
    qm = xgb_quantile(ALPHA / 2, 1 - ALPHA / 2).fit(X.iloc[tr], y[tr])
    qp = qm.predict(X.iloc[te])
    qc = conformal_q(cqr_scores, 1 - ALPHA)
    gpr = make_model("GPR", cols).fit(X.iloc[tr], y[tr])
    gm, gs = gpr.predict(X.iloc[te], return_std=True)

    out = pd.DataFrame({"idx": te, "y": y[te], "xgb": point,
                        "cqr_lo": qp[:, 0] - qc, "cqr_hi": qp[:, 1] + qc,
                        "qr_lo": qp[:, 0], "qr_hi": qp[:, 1],
                        "gpr": gm, "gpr_sd": gs})
    for lv in LEVELS:
        out[f"conf_q{int(lv*100)}"] = conformal_q(res_abs, lv)
    return out


def main():
    df = load_model_set()
    if "--plot-only" in sys.argv:
        res = pd.read_csv(RESULTS / "uncertainty.csv")
        cal = pd.read_csv(RESULTS / "uncertainty_calibration.csv")
        pred = {s: pd.read_csv(RESULTS / f"uncertainty_pred_{s}.csv") for s in SETS}
        return plots(df, res, cal, pred)
    folds = station_folds(df)
    jobs = [(s, fi) for s in SETS for fi in range(len(folds))]
    outs = Parallel(n_jobs=16, verbose=2)(
        delayed(run_fold)(df, SUBSETS[s], *folds[fi]) for s, fi in jobs)
    pred = {}
    for (s, fi), o in zip(jobs, outs):
        pred.setdefault(s, []).append(o)
    pred = {s: pd.concat(v).sort_values("idx").reset_index(drop=True) for s, v in pred.items()}

    rows, calib = [], []
    turb_hi = (df["Turbidity"] > 10).to_numpy()  # turbidity above its standard (unseen by S3)
    for s, p in pred.items():
        z = norm.ppf(1 - ALPHA / 2)
        methods = {
            "GPR": (p["gpr"] - z * p["gpr_sd"], p["gpr"] + z * p["gpr_sd"]),
            "Conformal": (p["xgb"] - p["conf_q90"], p["xgb"] + p["conf_q90"]),
            "Quantile GBM (raw)": (p["qr_lo"], p["qr_hi"]),
            "CQR": (p["cqr_lo"], p["cqr_hi"]),
        }
        for mname, (lo, hi) in methods.items():
            cov = (p["y"] >= lo) & (p["y"] <= hi)
            cat = category(p["y"])
            row = {"subset": s, "method": mname, "coverage": cov.mean(), "mean_width": (hi - lo).mean(),
                   "median_width": (hi - lo).median(),
                   "cov_turbidity_high": cov[turb_hi].mean(), "cov_turbidity_low": cov[~turb_hi].mean()}
            for c in ["Good", "Poor", "Very Poor"]:
                row[f"cov_{c}"] = cov[cat == c].mean()
            # fraction of rows whose whole interval sits inside one category => confidently labelled
            row["single_category_frac"] = float(np.mean(category(lo) == category(hi)))
            rows.append(row)
        for lv in LEVELS:
            zz = norm.ppf(0.5 + lv / 2)
            calib.append({"subset": s, "level": lv,
                          "GPR": np.mean(np.abs(p["y"] - p["gpr"]) <= zz * p["gpr_sd"]),
                          "Conformal": np.mean(np.abs(p["y"] - p["xgb"]) <= p[f"conf_q{int(lv*100)}"])})
    res = pd.DataFrame(rows)
    res.to_csv(RESULTS / "uncertainty.csv", index=False)
    cal = pd.DataFrame(calib)
    cal.to_csv(RESULTS / "uncertainty_calibration.csv", index=False)
    for s, p in pred.items():
        p.to_csv(RESULTS / f"uncertainty_pred_{s}.csv", index=False)
    print(res.round(3).to_string())
    plots(df, res, cal, pred)


def plots(df, res, cal, pred):
    # --------------------------------------------------------- coverage/width bars
    meth = ["GPR", "Conformal", "Quantile GBM (raw)", "CQR"]
    mcol = {"GPR": "#1f77b4", "Conformal": "#d62728", "Quantile GBM (raw)": "#bbbbbb", "CQR": "#2ca02c"}
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.4))
    w = 0.2
    for i, mname in enumerate(meth):
        sub = res[res["method"] == mname].set_index("subset").loc[SETS]
        axes[0].bar(np.arange(len(SETS)) + (i - 1.5) * w, sub["coverage"] * 100, w, color=mcol[mname],
                    label=mname)
        axes[1].bar(np.arange(len(SETS)) + (i - 1.5) * w, sub["mean_width"], w, color=mcol[mname])
    axes[0].axhline(90, color="k", ls="--", lw=0.8)
    axes[0].set_ylim(50, 100)
    axes[0].set_ylabel("Empirical coverage (%)")
    axes[0].set_title("Coverage of nominal 90% intervals")
    axes[1].set_ylabel("Mean interval width (WQI points)")
    axes[1].set_title("Interval width (narrower = more useful)")
    for a in axes:
        a.set_xticks(range(len(SETS)), SETS, rotation=20, fontsize=8)
    axes[0].legend(fontsize=7.5, ncol=4, loc="upper center", bbox_to_anchor=(1.1, 1.22))
    savefig(fig, "fig_unc_coverage_width")

    # --------------------------------------------------------- calibration curves
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4), sharey=True)
    for ax, mname in zip(axes, ["GPR", "Conformal"]):
        for s in SETS:
            g = cal[cal["subset"] == s]
            ax.plot(g["level"] * 100, g[mname] * 100, "o-", ms=3.5, color=SUBSET_COLORS[s], label=s)
        ax.plot([50, 95], [50, 95], "k--", lw=0.8)
        ax.set_xlabel("Nominal coverage (%)")
        ax.set_title(f"{mname} calibration")
    axes[0].set_ylabel("Empirical coverage (%)")
    axes[0].legend(fontsize=7.5)
    savefig(fig, "fig_unc_calibration")

    # --------------------------------------------------------- example station time series
    p = pred["S3"].copy()
    p["Station"] = df["Station"].to_numpy()[p["idx"]]
    p["Date"] = df["Date"].to_numpy()[p["idx"]]
    counts = p["Station"].value_counts()
    cands = [st for st in counts.index if counts[st] >= 11]
    var = {st: p[p["Station"] == st]["y"].std() for st in cands}
    picks = sorted(var, key=var.get, reverse=True)[:2]
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.2), sharey=True)
    for ax, st in zip(axes, picks):
        g = p[p["Station"] == st].sort_values("Date")
        ax.fill_between(g["Date"], g["cqr_lo"], g["cqr_hi"], color="#2ca02c", alpha=0.2, label="90% CQR interval")
        ax.plot(g["Date"], g["xgb"], "o-", color="#d1495b", ms=3.5, label="S3 prediction (pH, DO, BOD)")
        ax.plot(g["Date"], g["y"], "ks", ms=3.5, label="True full-panel WQI")
        for b in [25, 50, 75]:
            ax.axhline(b, color="grey", lw=0.4, ls="--")
        name = st.title()
        ax.set_title(name if len(name) <= 45 else name[:42].rsplit(" ", 1)[0] + " …", fontsize=9)
        ax.tick_params(axis="x", labelrotation=30, labelsize=7.5)
    axes[0].set_ylabel("Capped WQI")
    axes[0].legend(fontsize=7.5, loc="upper left")
    fig.suptitle("Unseen-station predictions with uncertainty (station never in training)", y=1.02)
    savefig(fig, "fig_unc_station_examples")


if __name__ == "__main__":
    main()
