"""
Sensitivity of the conclusions to the ground-truth definition:
  A. each standard value S_i halved / doubled (and an EC sweep, closing
     STATUS.md open issue #4),
  B. an alternative equal-weight WQI (removes the 1/S_i weighting that makes
     coliforms and EC nearly weightless),
  C. the uncapped WQI (log-transformed) as the target.
Writes results/sens_*.csv and figures/fig_sens_*.
"""

import copy
import json
from itertools import combinations

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import spearmanr

import compute_wqi as cw
from common import (CAT_LABELS, LABEL, PARAMS, RESULTS, SUBSET_COLORS, SUBSETS, TARGET, category,
                    cross_val_predict_df, load_model_set, metrics, savefig, setup_plotting,
                    station_folds)

plt = setup_plotting()
BASE_STD = copy.deepcopy(cw.STANDARDS)
NAMED = ["S3", "S4-routine", "S5", "S7", "I3-importance", "I5-importance", "Sensor-4", "Full-8"]


def wqi_with(df, overrides):
    cw.STANDARDS = copy.deepcopy(BASE_STD)
    for p, si in overrides.items():
        cw.STANDARDS[p]["Si"] = si
    try:
        return cw.compute_wqi(df, PARAMS, cap=100).to_numpy()
    finally:
        cw.STANDARDS = copy.deepcopy(BASE_STD)


def equal_weight_wqi(df):
    return np.mean([cw.sub_index(df, p, cap=100).to_numpy() for p in PARAMS], axis=0)


def cv(df, cols, folds, y, model="XGBoost"):
    oof, _ = cross_val_predict_df(model, cols, df, folds, y=y, n_jobs=1)
    return metrics(y, oof), oof


def main():
    df = load_model_set()
    folds = station_folds(df)
    y0 = df[TARGET].to_numpy()
    out = {}

    # ----------------------------------------------------------- A. standard values
    variants = []
    for p in ["BOD", "DO", "Turbidity", "NitrateN", "FecalColiform", "TotalColiform", "EC"]:
        si = BASE_STD[p]["Si"]
        for f in ([0.8, 1.2] if p == "DO" else [0.5, 2.0]):
            variants.append((p, f, {p: si * f}))
    for v in [250, 500, 750, 1500, 2000, 3000, 4000]:
        variants.append(("EC-sweep", v / 1000, {"EC": v}))

    def eval_variant(p, f, ov):
        y = wqi_with(df, ov)
        r = {"param": p, "factor": f, "mean_abs_change": float(np.mean(np.abs(y - y0))),
             "max_abs_change": float(np.max(np.abs(y - y0))),
             "spearman": float(spearmanr(y, y0)[0]),
             "category_agreement": float(np.mean(category(y) == category(y0)))}
        for s in ["S3", "I3-importance", "S7"]:
            r[f"R2_{s}"] = cv(df, SUBSETS[s], folds, y)[0]["R2"]
        return r

    sens = pd.DataFrame(Parallel(n_jobs=16)(delayed(eval_variant)(*v) for v in variants))
    sens.to_csv(RESULTS / "sens_standards.csv", index=False)
    print(sens.round(4).to_string())

    # ----------------------------------------------------------- B. equal-weight WQI
    yew = equal_weight_wqi(df)
    out["equal_weight_describe"] = pd.Series(yew).describe().round(3).to_dict()
    out["equal_weight_spearman_vs_base"] = float(spearmanr(yew, y0)[0])
    qcap = pd.DataFrame({p: cw.sub_index(df, p, cap=100) for p in PARAMS}) / len(PARAMS)
    tot = qcap.sum(axis=1)
    out["equal_weight_variance_share"] = (qcap.apply(lambda c: np.cov(c, tot)[0, 1]) / tot.var()).round(4).to_dict()

    combos = [list(c) for k in range(1, 9) for c in combinations(PARAMS, k)]

    def comb(c):
        m, _ = cv(df, c, folds, yew)
        return {"k": len(c), "subset": "+".join(c), "R2": m["R2"], "RMSE": m["RMSE"], "CatAcc": m["CatAcc"]}

    ew = pd.DataFrame(Parallel(n_jobs=16)(delayed(comb)(c) for c in combos))
    ew.to_csv(RESULTS / "sens_equalweight_combinatorial.csv", index=False)
    best = ew.loc[ew.groupby("k")["R2"].idxmax()]
    best.to_csv(RESULTS / "sens_equalweight_best_per_k.csv", index=False)
    print(best.to_string())

    key = lambda cols: "+".join([p for p in PARAMS if p in cols])
    base_comb = pd.read_csv(RESULTS / "combinatorial.csv")
    named = []
    for n in NAMED:
        s = key(SUBSETS[n])
        rb = base_comb[base_comb["subset"] == s].iloc[0]
        re_ = ew[ew["subset"] == s].iloc[0]
        named.append({"subset": n, "k": len(SUBSETS[n]),
                      "R2_base": rb["XGBoost_R2"], "CatAcc_base": rb["XGBoost_CatAcc"],
                      "R2_equalweight": re_["R2"], "CatAcc_equalweight": re_["CatAcc"],
                      "rank_equalweight": int((ew[ew["k"] == re_["k"]]["R2"] > re_["R2"]).sum() + 1)})
    named = pd.DataFrame(named)
    named.to_csv(RESULTS / "sens_equalweight_named.csv", index=False)
    print(named.round(4).to_string())

    # ----------------------------------------------------------- C. uncapped target (log10)
    yun = np.log10(df["WQI_full"].to_numpy())
    unc = []
    for n in NAMED:
        m, oof = cv(df, SUBSETS[n], folds, yun)
        pred = 10 ** oof
        true = df["WQI_full"].to_numpy()
        bins = [-np.inf, 25, 50, 75, 100, np.inf]
        ct = pd.cut(true, bins, labels=False)
        cp = pd.cut(pred, bins, labels=False)
        unc.append({"subset": n, "R2_log": m["R2"], "RMSE_log": m["RMSE"],
                    "CatAcc_5class": float(np.mean(ct == cp)),
                    "Unsuitable_recall": float(np.mean(cp[ct == 4] == 4)),
                    "median_rel_err": float(np.median(np.abs(pred - true) / true))})
    unc = pd.DataFrame(unc)
    unc.to_csv(RESULTS / "sens_uncapped.csv", index=False)
    print(unc.round(4).to_string())

    with open(RESULTS / "sens_summary.json", "w") as f:
        json.dump(out, f, indent=2, default=float)

    # ----------------------------------------------------------- figures
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.4))
    ax = axes[0]
    sv = sens[sens["param"] != "EC-sweep"]
    lbl = [f"{LABEL[p]} ×{f:g}" for p, f in zip(sv["param"], sv["factor"])]
    ax.barh(range(len(sv))[::-1], sv["mean_abs_change"], color="#30638e")
    ax.set_yticks(range(len(sv))[::-1], lbl, fontsize=8)
    for i, (v, c) in enumerate(zip(sv["mean_abs_change"], sv["category_agreement"])):
        ax.text(v + 0.05, len(sv) - 1 - i, f"{c*100:.1f}% same cat.", va="center", fontsize=7)
    ax.set_xlabel("Mean |Δ WQI| vs. baseline")
    ax.set_xlim(0, sv["mean_abs_change"].max() * 1.6)
    ax.set_title("Changing one standard value $S_i$")
    ax.grid(axis="y", visible=False)
    ax = axes[1]
    ec = sens[sens["param"] == "EC-sweep"].sort_values("factor")
    ecx = list(ec["factor"] * 1000)
    ecy = list(ec["mean_abs_change"])
    ax.plot(ecx + [1000], ecy + [0], "o", color="#d1495b")
    ax.set_xscale("log")
    ax.set_xticks([250, 500, 1000, 2000, 4000], ["250", "500", "1000", "2000", "4000"])
    ax.minorticks_off()
    ax.set_xlabel("EC standard (µS/cm); baseline 1000")
    ax.set_ylabel("Mean |Δ WQI|")
    ax.set_title(f"EC standard sweep: max category change "
                 f"{(1-ec['category_agreement'].min())*100:.2f}%")
    savefig(fig, "fig_sens_standards")

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.5))
    ax = axes[0]
    vs = pd.Series(out["equal_weight_variance_share"]).reindex(PARAMS) * 100
    vb = pd.read_csv(RESULTS / "eda_weights_contributions.csv", index_col=0)["variance_share"].reindex(PARAMS) * 100
    x = np.arange(len(PARAMS))
    ax.bar(x - 0.2, vb, 0.4, label="CPCB weights ($W_i \\propto 1/S_i$)", color="#30638e")
    ax.bar(x + 0.2, vs, 0.4, label="Equal weights", color="#edae49")
    ax.set_xticks(x, [LABEL[p] for p in PARAMS], rotation=30, ha="right")
    ax.set_ylabel("Share of WQI variance (%)")
    ax.legend(fontsize=8)
    ax.set_title("Which parameters drive the index?")
    ax = axes[1]
    xb = np.arange(len(NAMED))
    ax.bar(xb - 0.2, named["R2_base"], 0.4, color="#30638e", label="CPCB-weighted target")
    ax.bar(xb + 0.2, named["R2_equalweight"], 0.4, color="#edae49", label="Equal-weight target")
    ax.set_xticks(xb, NAMED, rotation=30, ha="right", fontsize=8)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("R² (XGBoost, unseen stations)")
    ax.legend(fontsize=8, loc="lower right")
    ax.set_title("Subset performance depends on the formula")
    savefig(fig, "fig_sens_equalweight")


if __name__ == "__main__":
    main()
