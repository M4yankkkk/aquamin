"""
Parameter-importance analysis on the full 8-parameter modelling set
(METHODOLOGY.md §3, Pass 1). Seven independent views of importance plus
greedy forward selection; all model-based scores use station-held-out CV.
Writes results/importance_*.csv and figures/fig_imp_*.
"""

import json

import numpy as np
import pandas as pd
import shap
from scipy.stats import spearmanr
from sklearn.feature_selection import mutual_info_regression
from sklearn.inspection import permutation_importance

from common import (LABEL, PARAMS, RESULTS, SEED, TARGET, cross_val_predict_df, load_model_set,
                    make_model, metrics, savefig, setup_plotting, station_folds)

plt = setup_plotting()


def cv_r2(df, cols, folds):
    oof, _ = cross_val_predict_df("XGBoost", cols, df, folds, n_jobs=16)
    return metrics(df[TARGET], oof)


def main():
    df = load_model_set()
    y = df[TARGET].to_numpy()
    X = df[PARAMS]
    folds = station_folds(df)
    res = pd.DataFrame(index=PARAMS)

    # 1. Correlations (Spearman is invariant to the log transform; Pearson on log for skewed params)
    res["spearman"] = [spearmanr(X[p], y)[0] for p in PARAMS]
    res["pearson_log"] = [np.corrcoef(np.log1p(X[p]) if p not in ("pH", "DO") else X[p], y)[0, 1]
                          for p in PARAMS]
    corr = pd.concat([X, df[[TARGET]]], axis=1).corr(method="spearman")
    corr.round(3).to_csv(RESULTS / "importance_spearman_matrix.csv")

    # 2. Mutual information (non-linear relevance)
    res["mutual_info"] = mutual_info_regression(X, y, random_state=SEED, n_neighbors=5)

    # 3. Random-forest impurity importance, 4. XGBoost gain importance (fit on all rows)
    rf = make_model("RandomForest", PARAMS, n_jobs=16).fit(X, y)
    res["rf_impurity"] = rf.feature_importances_
    xgb = make_model("XGBoost", PARAMS, n_jobs=16).fit(X, y)
    gain = xgb.get_booster().get_score(importance_type="gain")
    res["xgb_gain"] = [gain.get(p, 0.0) for p in PARAMS]
    res["xgb_gain"] /= res["xgb_gain"].sum()

    # 5. Permutation importance on held-out stations (mean R² drop across folds)
    perm = np.zeros(len(PARAMS))
    for tr, te in folds:
        m = make_model("XGBoost", PARAMS, n_jobs=16).fit(X.iloc[tr], y[tr])
        pi = permutation_importance(m, X.iloc[te], y[te], n_repeats=10, random_state=SEED,
                                    scoring="r2", n_jobs=1)
        perm += pi.importances_mean / len(folds)
    res["permutation_r2_drop"] = perm

    # 6. SHAP (TreeExplainer on the all-rows XGBoost)
    expl = shap.TreeExplainer(xgb)
    sv = expl.shap_values(X)
    res["mean_abs_shap"] = np.abs(sv).mean(axis=0)

    # 7. Drop-column importance (R² lost when a parameter is removed and the model retrained)
    full = cv_r2(df, PARAMS, folds)
    res["drop_column_r2"] = [full["R2"] - cv_r2(df, [q for q in PARAMS if q != p], folds)["R2"]
                             for p in PARAMS]

    # 8. Analytic variance share from the formula itself (01_eda.py)
    vs = pd.read_csv(RESULTS / "eda_weights_contributions.csv", index_col=0)["variance_share"]
    res["formula_variance_share"] = vs.reindex(PARAMS)

    rank_cols = ["mutual_info", "rf_impurity", "xgb_gain", "permutation_r2_drop", "mean_abs_shap",
                 "drop_column_r2", "formula_variance_share"]
    res["abs_spearman"] = res["spearman"].abs()
    ranks = res[rank_cols + ["abs_spearman"]].rank(ascending=False)
    res["mean_rank"] = ranks.mean(axis=1)
    res = res.sort_values("mean_rank")
    res.round(5).to_csv(RESULTS / "importance_scores.csv")
    ranks.loc[res.index].to_csv(RESULTS / "importance_ranks.csv")
    print(res.round(4).to_string())

    # ------------------------------------------------ greedy forward selection
    chosen, remaining, path = [], list(PARAMS), []
    while remaining:
        scores = {p: cv_r2(df, chosen + [p], folds) for p in remaining}
        best = max(scores, key=lambda p: scores[p]["R2"])
        chosen.append(best)
        remaining.remove(best)
        s = scores[best]
        path.append({"k": len(chosen), "added": best, "R2": s["R2"], "RMSE": s["RMSE"],
                     "CatAcc": s["CatAcc"], "candidates": {p: round(v["R2"], 4) for p, v in scores.items()}})
        print(f"forward k={len(chosen)} +{best}: R2={s['R2']:.4f} RMSE={s['RMSE']:.2f}")
    fwd = pd.DataFrame(path)
    fwd.drop(columns="candidates").to_csv(RESULTS / "importance_forward_selection.csv", index=False)
    with open(RESULTS / "importance_forward_selection.json", "w") as f:
        json.dump(path, f, indent=2)

    # ------------------------------------------------ figures
    # Spearman matrix
    names = [LABEL[p] for p in PARAMS] + ["WQI (target)"]
    fig, ax = plt.subplots(figsize=(6.4, 5.4))
    im = ax.imshow(corr.to_numpy(), cmap="RdBu_r", vmin=-1, vmax=1)
    ax.set_xticks(range(len(names)), names, rotation=40, ha="right")
    ax.set_yticks(range(len(names)), names)
    for i in range(len(names)):
        for j in range(len(names)):
            v = corr.iat[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7.5,
                    color="white" if abs(v) > 0.6 else "black")
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.8, label="Spearman ρ")
    ax.set_title("Rank correlation between parameters and the target")
    savefig(fig, "fig_imp_correlation")

    # normalised importance heatmap across methods
    show = ["abs_spearman", "mutual_info", "rf_impurity", "xgb_gain", "permutation_r2_drop",
            "mean_abs_shap", "drop_column_r2", "formula_variance_share"]
    pretty = ["|Spearman ρ|", "Mutual info.", "RF impurity", "XGB gain", "Permutation",
              "Mean |SHAP|", "Drop-column", "Formula var. share"]
    norm = res[show].clip(lower=0)
    norm = norm / norm.max()
    fig, ax = plt.subplots(figsize=(8.2, 3.9))
    im = ax.imshow(norm.T.to_numpy(), cmap="viridis", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(res)), [LABEL[p] for p in res.index], rotation=25, ha="right")
    ax.set_yticks(range(len(show)), pretty)
    rk = ranks.loc[res.index]
    for i, c in enumerate(show):
        for j, p in enumerate(res.index):
            ax.text(j, i, f"{int(rk.loc[p, c])}", ha="center", va="center", fontsize=8,
                    color="white" if norm.loc[p, c] < 0.55 else "black")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="Score / max (number = rank)")
    ax.set_title("Parameter importance under eight methods (sorted by consensus rank)")
    savefig(fig, "fig_imp_heatmap")

    # SHAP beeswarm
    plt.figure()
    shap.summary_plot(sv, X.rename(columns=LABEL), show=False, plot_size=(7.2, 4.2), max_display=8)
    fig = plt.gcf()
    fig.axes[0].set_title("SHAP values of the full-panel XGBoost model")
    savefig(fig, "fig_imp_shap_beeswarm")

    # SHAP dependence for top drivers
    fig, axes = plt.subplots(1, 4, figsize=(11, 2.9), sharey=True)
    for ax, p in zip(axes, ["pH", "BOD", "Turbidity", "DO"]):
        j = PARAMS.index(p)
        xv = X[p].to_numpy()
        ax.scatter(xv, sv[:, j], s=3, alpha=0.4, c="#30638e")
        if p in ("BOD", "Turbidity"):
            ax.set_xscale("symlog", linthresh=1)
        ax.set_xlabel(LABEL[p])
        ax.axhline(0, color="k", lw=0.6)
    axes[0].set_ylabel("SHAP value (WQI points)")
    fig.suptitle("SHAP dependence: the model recovers the piecewise-linear capped sub-indices", y=1.03)
    savefig(fig, "fig_imp_shap_dependence")

    # forward selection curve
    fig, ax = plt.subplots(figsize=(6.6, 3.3))
    ax.plot(fwd["k"], fwd["R2"], "o-", color="#30638e")
    for k, a, r in zip(fwd["k"], fwd["added"], fwd["R2"]):
        ax.annotate(f"+{LABEL[a]}", (k, r), textcoords="offset points", xytext=(0, -14 if k > 1 else 8),
                    ha="center", fontsize=8)
    ax.set_xlabel("Number of parameters")
    ax.set_ylabel("Station-held-out R²")
    ax.set_ylim(min(0, fwd["R2"].min() - 0.05), 1.02)
    ax2 = ax.twinx()
    ax2.plot(fwd["k"], fwd["RMSE"], "s--", color="#d1495b", alpha=0.7)
    ax2.set_ylabel("RMSE (WQI points)", color="#d1495b")
    ax2.grid(False)
    ax2.spines["right"].set_visible(True)
    ax.set_title("Greedy forward selection (XGBoost)")
    savefig(fig, "fig_imp_forward_selection")

    with open(RESULTS / "importance_summary.json", "w") as f:
        json.dump({"full_model_cv": full, "consensus_order": list(res.index),
                   "forward_order": list(fwd["added"])}, f, indent=2)


if __name__ == "__main__":
    main()
