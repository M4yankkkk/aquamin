"""
Deployment on the real data gap: ~20k river visits report pH, DO and BOD but
not the full panel (all of 2018, 2019, 2021 and part of 2020). Train S3 /
S4-routine models on all 4,861 labelled rows, check covariate shift between
labelled and unlabelled visits (adversarial validation, KS tests), then
reconstruct full-panel WQI where it was never computable.
Writes results/deploy_*.csv and figures/fig_dep_*.
"""

import json

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from xgboost import XGBClassifier

from common import (RESULTS, SEED, SUBSETS, TARGET, category, load_all, make_model, savefig,
                    setup_plotting, compute_wqi)

plt = setup_plotting()


def main():
    df = load_all()
    lab = df[df[TARGET].notna()].copy()
    s3 = SUBSETS["S3"]
    s4 = SUBSETS["S4-routine"]
    unl = df[df[TARGET].isna() & df[s3].notna().all(axis=1)].copy()
    out = {"n_labelled": len(lab), "n_deploy_S3": len(unl),
           "n_deploy_S4": int(unl[s4].notna().all(axis=1).sum()),
           "deploy_by_year": unl["Year"].value_counts().sort_index().to_dict(),
           "deploy_stations": int(unl["Station"].nunique()),
           "deploy_stations_never_labelled": int(len(set(unl["Station"]) - set(lab["Station"]))),
           "deploy_rivers": int(unl["MatchedRiver"].nunique())}

    # ------------------------------------------------------------- covariate shift
    ks = []
    for p in s4:
        a = lab[p].dropna()
        for yr in [2018, 2019, 2020, 2021]:
            b = unl[(unl["Year"] == yr)][p].dropna()
            st = ks_2samp(a, b)
            lo, hi = a.quantile(0.005), a.quantile(0.995)
            ks.append({"param": p, "year": yr, "KS": st.statistic, "p": st.pvalue,
                       "median_lab": a.median(), "median_deploy": b.median(),
                       "pct_outside_train_range": float(((b < lo) | (b > hi)).mean() * 100)})
    ks = pd.DataFrame(ks)
    ks.to_csv(RESULTS / "deploy_ks.csv", index=False)

    # adversarial validation: can a classifier tell labelled from deployment rows using S3?
    both = pd.concat([lab.assign(z=0), unl.assign(z=1)], ignore_index=True)
    auc = []
    adv_oof = None
    for cols, name in [(s3, "S3"), (s3 + ["Month"], "S3+Month")]:
        oof = np.zeros(len(both))
        for tr, te in GroupKFold(5, shuffle=True, random_state=SEED).split(both, groups=both["Station"]):
            c = XGBClassifier(n_estimators=300, max_depth=4, learning_rate=0.05, n_jobs=16,
                              random_state=SEED, eval_metric="logloss")
            c.fit(both[cols].iloc[tr], both["z"].iloc[tr])
            oof[te] = c.predict_proba(both[cols].iloc[te])[:, 1]
        auc.append({"features": name, "AUC": roc_auc_score(both["z"], oof)})
        if name == "S3":
            adv_oof = oof
    out["adversarial_auc"] = auc
    print(ks.round(3).to_string())
    print(auc)

    # ------------------------------------------------------------- reconstruct WQI
    oofp = pd.read_csv(RESULTS / "oof_station.csv")
    q90 = {}
    for s in ["S3", "S4-routine"]:
        r = np.abs(oofp[f"{s}|XGBoost"] - oofp["y"]).to_numpy()
        q90[s] = float(np.sort(r)[int(np.ceil((len(r) + 1) * 0.9)) - 1])
    out["conformal_halfwidth_90"] = q90

    # importance-weighted CV error: re-weight labelled rows by the density ratio
    # p(deploy|x)/p(labelled|x) from the adversarial classifier, so the CV error
    # estimates the error on the deployment distribution (covariate-shift correction)
    pl = np.clip(adv_oof[: len(lab)], 1e-3, 1 - 1e-3)
    w = np.clip(pl / (1 - pl), 0, 50)
    w = w / w.mean()
    yv = oofp["y"].to_numpy()
    shift = {"effective_sample_size": float(w.sum() ** 2 / (w ** 2).sum())}
    for s in ["S3", "S4-routine"]:
        pv = oofp[f"{s}|XGBoost"].to_numpy()
        e = pv - yv
        shift[s] = {
            "RMSE_unweighted": float(np.sqrt(np.mean(e ** 2))),
            "RMSE_weighted": float(np.sqrt(np.average(e ** 2, weights=w))),
            "CatAcc_unweighted": float(np.mean(category(yv) == category(pv))),
            "CatAcc_weighted": float(np.average(category(yv) == category(pv), weights=w)),
            "Coverage90_unweighted": float(np.mean(np.abs(e) <= q90[s])),
            "Coverage90_weighted": float(np.average(np.abs(e) <= q90[s], weights=w)),
        }
    out["shift_corrected_error"] = shift
    print(shift)

    m3 = make_model("XGBoost", s3, n_jobs=16).fit(lab[s3], lab[TARGET])
    unl["WQI_pred_S3"] = m3.predict(unl[s3])
    has4 = unl[s4].notna().all(axis=1)
    m4 = make_model("XGBoost", s4, n_jobs=16).fit(lab[s4], lab[TARGET])
    unl["WQI_pred_S4"] = np.nan
    unl.loc[has4, "WQI_pred_S4"] = m4.predict(unl.loc[has4, s4])
    unl["WQI_formula_S3"] = compute_wqi(unl, s3, cap=100)
    unl["Category_pred_S3"] = category(unl["WQI_pred_S3"])
    unl["Season"] = unl["Season"]
    keep = ["Station", "State", "MatchedRiver", "Latitude", "Longitude", "Date", "Year", "Month",
            "pH", "DO", "BOD", "FecalColiform", "WQI_pred_S3", "WQI_pred_S4", "WQI_formula_S3",
            "Category_pred_S3"]
    unl[keep].to_csv(RESULTS / "deploy_predictions.csv", index=False)
    out["S3_vs_S4_pred_corr"] = float(unl.loc[has4, ["WQI_pred_S3", "WQI_pred_S4"]].corr().iloc[0, 1])
    out["S3_vs_S4_mean_abs_diff"] = float((unl.loc[has4, "WQI_pred_S3"] - unl.loc[has4, "WQI_pred_S4"]).abs().mean())
    out["formula_bias_vs_model"] = float((unl["WQI_formula_S3"] - unl["WQI_pred_S3"]).mean())

    yr = unl.groupby("Year")["WQI_pred_S3"].describe()
    yr.round(2).to_csv(RESULTS / "deploy_by_year.csv")
    catyr = pd.crosstab(unl["Year"], unl["Category_pred_S3"], normalize="index").mul(100).round(1)
    catyr.to_csv(RESULTS / "deploy_category_by_year.csv")
    print(yr.round(2))
    print(catyr)

    # persistence check: station mean predicted WQI in other years vs station mean true WQI in 2020
    t20 = lab.groupby("Station")[TARGET].mean()
    pers = {}
    for y_ in [2018, 2019, 2021]:
        pm = unl[unl["Year"] == y_].groupby("Station")["WQI_pred_S3"].mean()
        j = pd.concat([t20, pm], axis=1, join="inner").dropna()
        pers[y_] = {"n_stations": len(j), "pearson": float(j.corr().iloc[0, 1])}
    # same quantity for true 2020 (labelled) vs predicted 2020 (unlabelled visits, same station)
    pm20 = unl[unl["Year"] == 2020].groupby("Station")["WQI_pred_S3"].mean()
    j = pd.concat([t20, pm20], axis=1, join="inner").dropna()
    pers[2020] = {"n_stations": len(j), "pearson": float(j.corr().iloc[0, 1])}
    out["station_persistence"] = pers
    print(pers)

    # river x year table
    top = unl["MatchedRiver"].value_counts().head(18).index
    rv = unl[unl["MatchedRiver"].isin(top)].pivot_table(index="MatchedRiver", columns="Year",
                                                         values="WQI_pred_S3", aggfunc="mean")
    lab20 = lab[lab["MatchedRiver"].isin(top)].groupby("MatchedRiver")[TARGET].mean()
    rv["2020 (true, labelled)"] = lab20
    rv = rv.sort_values(2019)
    rv.round(2).to_csv(RESULTS / "deploy_river_year.csv")

    with open(RESULTS / "deploy_summary.json", "w") as f:
        json.dump(out, f, indent=2, default=float)
    print(json.dumps(out, indent=2, default=float))

    # ------------------------------------------------------------- figures
    fig, axes = plt.subplots(1, 4, figsize=(11.5, 2.9))
    for ax, p in zip(axes, s4):
        a = lab[p].dropna()
        b = unl[unl["Year"] != 2020][p].dropna()
        logp = p in ("BOD", "FecalColiform")
        f = (lambda v: np.log10(v.clip(lower=0.1))) if logp else (lambda v: v)
        bins = np.linspace(min(f(a).quantile(0.005), f(b).quantile(0.005)),
                           max(f(a).quantile(0.995), f(b).quantile(0.995)), 40)
        ax.hist(f(a), bins=bins, density=True, alpha=0.55, color="#30638e", label="Labelled (2020)")
        ax.hist(f(b), bins=bins, density=True, alpha=0.55, color="#edae49", label="Deploy (2018/19/21)")
        k = ks[(ks["param"] == p) & (ks["year"] == 2019)]["KS"].iloc[0]
        ax.set_title(f"{p}{' (log10)' if logp else ''}  KS={k:.2f}", fontsize=9.5)
        ax.set_yticks([])
    axes[0].legend(fontsize=7.5)
    fig.suptitle("Input distributions: labelled training rows vs. rows to be reconstructed", y=1.03)
    savefig(fig, "fig_dep_shift")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.4), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    yrs = [2018, 2019, 2020, 2021]
    data = [unl[unl["Year"] == y_]["WQI_pred_S3"] for y_ in yrs] + [lab[TARGET]]
    bp = ax.boxplot(data, showfliers=False, patch_artist=True, widths=0.6)
    for patch, c in zip(bp["boxes"], ["#edae49"] * 4 + ["#30638e"]):
        patch.set_facecolor(c)
        patch.set_alpha(0.7)
    ax.set_xticks(range(1, 6), [f"{y_}\n(pred.)\nn={len(d):,}" for y_, d in zip(yrs, data[:4])]
                  + [f"2020\n(true)\nn={len(lab):,}"], fontsize=8)
    for b in [25, 50, 75]:
        ax.axhline(b, color="grey", lw=0.5, ls="--")
    ax.set_ylabel("Capped WQI")
    ax.set_title("Reconstructed full-panel WQI by year (S3 model)")
    ax = axes[1]
    catyr2 = catyr.reindex(columns=["Excellent", "Good", "Poor", "Very Poor"]).fillna(0)
    bottom = np.zeros(len(catyr2))
    for c, col in zip(catyr2.columns, ["#2a9d8f", "#8ab17d", "#e9c46a", "#e76f51"]):
        ax.bar(range(len(catyr2)), catyr2[c], bottom=bottom, color=col, label=c)
        bottom += catyr2[c].to_numpy()
    ax.set_xticks(range(len(catyr2)), catyr2.index)
    ax.set_ylabel("% of visits")
    ax.legend(fontsize=7.5, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.13))
    ax.set_title("Predicted category mix", pad=22)
    savefig(fig, "fig_dep_by_year")

    fig, ax = plt.subplots(figsize=(7.0, 5.2))
    vals = rv.to_numpy()
    im = ax.imshow(vals, cmap="RdYlGn_r", vmin=35, vmax=75, aspect="auto")
    ax.set_xticks(range(rv.shape[1]), [str(c) for c in rv.columns], rotation=20, ha="right")
    ax.set_yticks(range(len(rv)), [r.title() for r in rv.index])
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            if not np.isnan(vals[i, j]):
                ax.text(j, i, f"{vals[i, j]:.0f}", ha="center", va="center", fontsize=7.5)
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="Mean capped WQI")
    ax.set_title("Reconstructed river-level WQI, 2018–2021 (S3 model)\nlast column: true 2020 values")
    savefig(fig, "fig_dep_river_year")

    st = unl.groupby("Station").agg(lat=("Latitude", "mean"), lon=("Longitude", "mean"),
                                    wqi=("WQI_pred_S3", "mean"), n=("WQI_pred_S3", "size"))
    new = ~st.index.isin(lab["Station"])
    fig, ax = plt.subplots(figsize=(6.2, 6.4))
    sc = ax.scatter(st.lon[~new], st.lat[~new], c=st.wqi[~new], cmap="RdYlGn_r", vmin=30, vmax=80, s=12,
                    edgecolor="k", linewidth=0.2, label="Station also in labelled set")
    ax.scatter(st.lon[new], st.lat[new], c=st.wqi[new], cmap="RdYlGn_r", vmin=30, vmax=80, s=26,
               marker="^", edgecolor="k", linewidth=0.4, label=f"Station never labelled ({new.sum()})")
    fig.colorbar(sc, ax=ax, shrink=0.7, label="Mean reconstructed WQI 2018–2021")
    ax.set_aspect("equal")
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.legend(loc="lower left", fontsize=8)
    ax.set_title(f"Reconstructed WQI at {len(st)} stations")
    savefig(fig, "fig_dep_map")


if __name__ == "__main__":
    main()
