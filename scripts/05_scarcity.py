"""
Data-scarcity sweep (METHODOLOGY.md §5 step 7): shrink the training set by
keeping only a random fraction of the *training stations* in each
station-held-out fold, and measure how accuracy decays per model and
parameter subset. Test folds are untouched, so every point is evaluated on
the same unseen stations. Writes results/scarcity*.csv, figures/fig_scar_*.
"""

import sys

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from common import (MODEL_COLORS, MODELS, RESULTS, SEED, SUBSET_COLORS, SUBSETS, TARGET,
                    load_model_set, make_model, metrics, savefig, setup_plotting, station_folds)

plt = setup_plotting()

FRACS = [0.02, 0.05, 0.10, 0.25, 0.50, 1.00]
REPEATS = 3
SETS = ["S3", "S4-routine", "S5", "S7", "Full-8", "I3-importance"]


def run(df, folds, sname, model, frac, rep, fi):
    cols = SUBSETS[sname]
    tr, te = folds[fi]
    y = df[TARGET].to_numpy()
    stations = df["Station"].iloc[tr].unique()
    rng = np.random.default_rng(SEED + 1000 * rep + fi)
    n_keep = max(2, int(round(frac * len(stations))))
    keep = set(rng.choice(stations, n_keep, replace=False))
    tr_sub = tr[df["Station"].iloc[tr].isin(keep).to_numpy()]
    m = make_model(model, cols, n_jobs=1)
    if model == "GPR":
        m.set_params(n_restarts=0)  # 480 GPR fits in this sweep; one optimiser start each
    m.fit(df[cols].iloc[tr_sub], y[tr_sub])
    p = m.predict(df[cols].iloc[te])
    row = {"subset": sname, "model": model, "frac": frac, "rep": rep, "fold": fi,
           "n_train_rows": len(tr_sub), "n_train_stations": n_keep}
    row.update(metrics(y[te], p))
    return row


def main():
    df = load_model_set()
    folds = station_folds(df)
    tasks = []
    for s in SETS:
        for m in MODELS:
            for f in FRACS:
                reps = 1 if (f == 1.0 or m == "Formula") else REPEATS
                for r in range(reps):
                    for fi in range(len(folds)):
                        tasks.append((s, m, f, r, fi))
    if "--plot-only" in sys.argv:
        raw = pd.read_csv(RESULTS / "scarcity_raw.csv")
    else:
        tasks.sort(key=lambda t: (t[1] != "GPR", -t[2]))
        rows = Parallel(n_jobs=16, verbose=2)(delayed(run)(df, folds, *t) for t in tasks)
        raw = pd.DataFrame(rows)
        raw.to_csv(RESULTS / "scarcity_raw.csv", index=False)

    agg = raw.groupby(["subset", "model", "frac"]).agg(
        R2=("R2", "mean"), R2_sd=("R2", "std"), RMSE=("RMSE", "mean"), RMSE_sd=("RMSE", "std"),
        CatAcc=("CatAcc", "mean"), CatAcc_sd=("CatAcc", "std"), MAE=("MAE", "mean"),
        n_train_rows=("n_train_rows", "mean"), n_train_stations=("n_train_stations", "mean"),
    ).reset_index()
    agg.to_csv(RESULTS / "scarcity.csv", index=False)

    # data needed: smallest fraction whose RMSE is within 10% of the full-data RMSE
    need = []
    for (s, m), g in agg[agg["model"] != "Formula"].groupby(["subset", "model"]):
        g = g.sort_values("frac")
        full = g[g["frac"] == 1.0]["RMSE"].iloc[0]
        ok = g[g["RMSE"] <= 1.10 * full]
        f = ok["frac"].min()
        need.append({"subset": s, "model": m, "RMSE_full": full,
                     "min_frac_within10pct": f,
                     "rows_needed": float(g[g["frac"] == f]["n_train_rows"].iloc[0]),
                     "stations_needed": float(g[g["frac"] == f]["n_train_stations"].iloc[0]),
                     "RMSE_at_2pct": g[g["frac"] == 0.02]["RMSE"].iloc[0],
                     "CatAcc_at_2pct": g[g["frac"] == 0.02]["CatAcc"].iloc[0]})
    need = pd.DataFrame(need)
    need.to_csv(RESULTS / "scarcity_data_needed.csv", index=False)
    print(agg[agg["model"] == "XGBoost"].pivot(index="subset", columns="frac", values="RMSE").round(2))
    print(agg[agg["subset"] == "S3"].pivot(index="model", columns="frac", values="RMSE").round(2))
    print(need.round(3).to_string())

    rows_at = agg[(agg["subset"] == "S3") & (agg["model"] == "XGBoost")].set_index("frac")
    xt = [f"{int(f*100)}%\n~{int(rows_at.loc[f, 'n_train_rows'])} rows" for f in FRACS]

    # ------------------------------------------------------- figure: per subset (XGBoost + SVR)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6), sharey=True)
    for ax, m in zip(axes, ["XGBoost", "SVR"]):
        for s in SETS:
            g = agg[(agg["subset"] == s) & (agg["model"] == m)].sort_values("frac")
            ax.errorbar(range(len(FRACS)), g["RMSE"], yerr=g["RMSE_sd"], fmt="o-", ms=4, lw=1.3,
                        capsize=2, color=SUBSET_COLORS[s], label=s)
        ax.set_xticks(range(len(FRACS)), xt, fontsize=7.5)
        ax.set_yscale("log")
        ax.set_yticks([0.5, 1, 2, 4, 8], ["0.5", "1", "2", "4", "8"])
        ax.set_title(f"{m}: error vs. training data")
        ax.set_xlabel("Fraction of training stations kept")
    axes[0].set_ylabel("RMSE on unseen stations (log scale)")
    axes[0].legend(fontsize=7.5, ncol=2)
    savefig(fig, "fig_scar_by_subset")

    # ------------------------------------------------------- figure: S3 and S7, all models
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6), sharey=True)
    for ax, s in zip(axes, ["S3", "S7"]):
        for m in MODELS:
            g = agg[(agg["subset"] == s) & (agg["model"] == m)].sort_values("frac")
            ax.plot(range(len(FRACS)), g["RMSE"], "o-", ms=3.5, lw=1.3, color=MODEL_COLORS[m], label=m,
                    ls="--" if m == "Formula" else "-")
        ax.set_xticks(range(len(FRACS)), xt, fontsize=7.5)
        ax.set_yscale("log")
        ax.set_yticks([1, 2, 4, 8], ["1", "2", "4", "8"])
        ax.set_title(f"{s}: which model copes best with little data?")
        ax.set_xlabel("Fraction of training stations kept")
    axes[0].set_ylabel("RMSE on unseen stations (log scale)")
    axes[1].legend(fontsize=7.5, ncol=2)
    savefig(fig, "fig_scar_by_model")

    # ------------------------------------------------------- figure: heatmap model x frac (S3)
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.4), sharey=True)
    for ax, s in zip(axes, ["S3", "Full-8"]):
        h = agg[agg["subset"] == s].pivot(index="model", columns="frac", values="CatAcc").loc[MODELS] * 100
        im = ax.imshow(h.to_numpy(), cmap="RdYlGn", vmin=70, vmax=100, aspect="auto")
        ax.set_xticks(range(len(FRACS)), [f"{int(f*100)}%" for f in FRACS])
        ax.set_yticks(range(len(MODELS)), MODELS)
        ax.tick_params(axis="y", labelleft=(s == "S3"))
        for i in range(h.shape[0]):
            for j in range(h.shape[1]):
                ax.text(j, i, f"{h.iat[i, j]:.1f}", ha="center", va="center", fontsize=7.5)
        ax.grid(False)
        ax.set_title(f"{s}: category accuracy (%)")
        ax.set_xlabel("Training stations kept")
    fig.colorbar(im, ax=axes, shrink=0.85)
    savefig(fig, "fig_scar_catacc_heatmap")


if __name__ == "__main__":
    main()
