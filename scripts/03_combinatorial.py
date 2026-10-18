"""
Exhaustive subset search: every one of the 2^8 - 1 = 255 parameter subsets,
scored with station-held-out CV for XGBoost and for the no-ML renormalised
formula. Shows how much *which* parameters matters versus *how many*
(PROJECT.md §5.4). Writes results/combinatorial.csv and figures/fig_comb_*.
"""

from itertools import combinations

import numpy as np
import pandas as pd
from joblib import Parallel, delayed

from common import (LABEL, PARAMS, RESULTS, SUBSET_COLORS, SUBSETS, TARGET, cross_val_predict_df,
                    load_model_set, metrics, savefig, setup_plotting, station_folds)

plt = setup_plotting()


def score(df, cols, folds):
    y = df[TARGET].to_numpy()
    row = {"k": len(cols), "subset": "+".join(cols)}
    for name in ("XGBoost", "Formula"):
        oof, _ = cross_val_predict_df(name, cols, df, folds, n_jobs=1)
        m = metrics(y, oof)
        for key in ("R2", "RMSE", "MAE", "CatAcc"):
            row[f"{name}_{key}"] = m[key]
    return row


def main():
    df = load_model_set()
    folds = station_folds(df)
    combos = [list(c) for k in range(1, 9) for c in combinations(PARAMS, k)]
    rows = Parallel(n_jobs=16, verbose=0)(delayed(score)(df, c, folds) for c in combos)
    res = pd.DataFrame(rows).sort_values(["k", "XGBoost_R2"], ascending=[True, False])
    res.to_csv(RESULTS / "combinatorial.csv", index=False)

    key = lambda cols: "+".join([p for p in PARAMS if p in cols])
    named = {n: key(c) for n, c in SUBSETS.items()}
    agg = res.groupby("k")["XGBoost_R2"].agg(["max", "median", "min", "count"])
    best = res.loc[res.groupby("k")["XGBoost_R2"].idxmax(), ["k", "subset", "XGBoost_R2", "XGBoost_RMSE",
                                                              "XGBoost_CatAcc"]]
    best.to_csv(RESULTS / "combinatorial_best_per_k.csv", index=False)
    print(agg.round(4).to_string())
    print(best.to_string())
    for n, s in named.items():
        r = res[res["subset"] == s].iloc[0]
        rank = int((res[res["k"] == r["k"]]["XGBoost_R2"] > r["XGBoost_R2"]).sum() + 1)
        print(f"{n:15s} k={r['k']} R2={r['XGBoost_R2']:.4f} rank {rank}/{int(agg.loc[r['k'], 'count'])}"
              f"  formula R2={r['Formula_R2']:.4f}")

    # rank of each named subset within its size
    ranks = []
    for n, s in named.items():
        r = res[res["subset"] == s].iloc[0]
        same = res[res["k"] == r["k"]]
        ranks.append({"name": n, "k": r["k"], "R2": r["XGBoost_R2"], "RMSE": r["XGBoost_RMSE"],
                      "CatAcc": r["XGBoost_CatAcc"], "Formula_R2": r["Formula_R2"],
                      "rank_in_k": int((same["XGBoost_R2"] > r["XGBoost_R2"]).sum() + 1),
                      "n_in_k": len(same)})
    pd.DataFrame(ranks).to_csv(RESULTS / "combinatorial_named_ranks.csv", index=False)

    # ---------------------------------------------------------------- figure 1
    fig, ax = plt.subplots(figsize=(7.4, 4.2))
    rng = np.random.default_rng(0)
    for k in range(1, 9):
        sub = res[res["k"] == k]
        ax.scatter(k + rng.uniform(-0.18, 0.18, len(sub)), sub["XGBoost_R2"].clip(lower=-0.1), s=9,
                   color="#9fb3c8", alpha=0.8, zorder=1)
    ax.plot(agg.index, agg["max"], "-", color="#30638e", lw=1.4, label="Best subset of size k")
    ax.plot(agg.index, agg["median"], "--", color="#30638e", lw=1, label="Median subset")
    for n in ["S3", "S5", "S7", "Full-8", "I3-importance", "S4-routine", "Sensor-3", "Sensor-4"]:
        r = res[res["subset"] == named[n]].iloc[0]
        ax.scatter(r["k"], max(r["XGBoost_R2"], -0.1), s=60, marker="D", color=SUBSET_COLORS[n],
                   edgecolor="k", zorder=3, label=n)
    ax.set_xlabel("Number of parameters (k)")
    ax.set_ylabel("Station-held-out R² (XGBoost)")
    ax.set_ylim(-0.12, 1.03)
    ax.legend(fontsize=7.5, ncol=2, loc="lower right")
    ax.set_title("All 255 subsets: which parameters matter more than how many")
    savefig(fig, "fig_comb_all_subsets")

    # ---------------------------------------------------------------- figure 2: ML vs formula
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    sc = ax.scatter(res["Formula_R2"].clip(lower=-1), res["XGBoost_R2"].clip(lower=-1), c=res["k"],
                    cmap="viridis", s=14)
    ax.plot([-1, 1], [-1, 1], "k--", lw=0.8)
    for n in ["S3", "S5", "S7", "I3-importance"]:
        r = res[res["subset"] == named[n]].iloc[0]
        ax.annotate(n, (max(r["Formula_R2"], -1), r["XGBoost_R2"]), fontsize=8,
                    xytext=(5, -10), textcoords="offset points")
    fig.colorbar(sc, ax=ax, label="k")
    ax.set_xlabel("R², renormalised formula (no ML)")
    ax.set_ylabel("R², XGBoost")
    ax.set_xlim(-1.05, 1.02)
    ax.set_ylim(-1.05, 1.02)
    ax.set_title("ML surrogate vs. computing WQI\nfrom only the available parameters")
    savefig(fig, "fig_comb_ml_vs_formula")

    # ---------------------------------------------------------------- figure 3: presence matrix top-15
    top = res.sort_values("XGBoost_R2", ascending=False)
    top = pd.concat([top[top["k"] == k].head(3) for k in range(1, 8)])
    fig, ax = plt.subplots(figsize=(7.6, 5.4))
    for i, (_, r) in enumerate(top.iterrows()):
        cols = r["subset"].split("+")
        for j, p in enumerate(PARAMS):
            ax.scatter(j, i, s=55, color="#30638e" if p in cols else "#e5e5e5", zorder=2)
        ax.text(len(PARAMS) - 0.3, i, f"R²={r['XGBoost_R2']:.3f}  RMSE={r['XGBoost_RMSE']:.2f}",
                va="center", fontsize=8)
    ax.set_xticks(range(len(PARAMS)), [LABEL[p] for p in PARAMS], rotation=30, ha="right")
    ax.set_yticks(range(len(top)), [f"k={k}" for k in top["k"]], fontsize=8)
    ax.invert_yaxis()
    ax.set_xlim(-0.5, len(PARAMS) + 2.6)
    ax.grid(False)
    ax.set_title("Top-3 subsets at each size k")
    savefig(fig, "fig_comb_top_subsets")


if __name__ == "__main__":
    main()
