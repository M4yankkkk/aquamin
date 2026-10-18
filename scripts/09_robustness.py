"""
Robustness experiments on unseen stations:
  A. one "mask-trained" XGBoost that accepts any subset (missing = NaN)
     versus a dedicated model per subset;
  B. random missing readings at test time: native-NaN model vs. full model
     with mean / iterative (MICE-style) imputation;
  C. measurement noise at realistic field-sensor accuracy, i.e. how precisely
     must each parameter be measured?
Writes results/robust_*.csv and figures/fig_rob_*.
"""

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer, SimpleImputer

from common import (PARAMS, RESULTS, SEED, SUBSET_COLORS, SUBSETS, TARGET, load_model_set,
                    make_model, metrics, savefig, setup_plotting, station_folds)

plt = setup_plotting()
NAMED = ["S3", "S4-routine", "S5", "S7", "I3-importance", "I5-importance", "Sensor-4", "Full-8"]
RATES = [0.0, 0.1, 0.2, 0.3, 0.5]
# 1-sigma field measurement error: absolute for pH/DO, relative for the rest
NOISE = {"pH": ("abs", 0.1), "DO": ("abs", 0.3), "BOD": ("rel", 0.15), "Turbidity": ("rel", 0.10),
         "NitrateN": ("rel", 0.15), "EC": ("rel", 0.05), "FecalColiform": ("rel", 0.5),
         "TotalColiform": ("rel", 0.5)}
NOISE_SCALES = [0, 0.5, 1, 2]


def augment(X, y, copies, p_drop, rng):
    """Replicate rows with random masks; always keep >=1 observed parameter."""
    Xs, ys = [X], [y]
    for _ in range(copies):
        Xm = X.copy()
        mask = rng.random(X.shape) < p_drop
        allm = mask.all(axis=1)
        mask[allm, rng.integers(0, X.shape[1], allm.sum())] = False
        Xm = Xm.mask(mask)
        Xs.append(Xm)
        ys.append(y)
    return pd.concat(Xs, ignore_index=True), np.concatenate(ys)


def add_noise(X, scale, rng):
    Xn = X.copy()
    for p, (kind, s) in NOISE.items():
        if p not in Xn:
            continue
        e = rng.normal(0, s * scale, len(Xn))
        Xn[p] = Xn[p] + e if kind == "abs" else Xn[p] * np.exp(e)
        Xn[p] = Xn[p].clip(lower=0)
    return Xn


def run_fold(df, tr, te, fi):
    y = df[TARGET].to_numpy()
    X = df[PARAMS]
    rng = np.random.default_rng(SEED + fi)
    rows_a, rows_b, rows_c = [], [], []

    # A. mask-trained universal model vs dedicated models
    Xa, ya = augment(X.iloc[tr].reset_index(drop=True), y[tr], copies=6, p_drop=0.5, rng=rng)
    uni = make_model("XGBoost", PARAMS, n_jobs=2)
    uni.set_params(n_estimators=900)
    uni.fit(Xa, ya)
    for n in NAMED:
        cols = SUBSETS[n]
        Xt = X.iloc[te].copy()
        Xt.loc[:, [p for p in PARAMS if p not in cols]] = np.nan
        ded = make_model("XGBoost", cols, n_jobs=2).fit(X.iloc[tr][cols], y[tr])
        rows_a.append({"fold": fi, "subset": n, "model": "Universal (mask-trained)",
                       **metrics(y[te], uni.predict(Xt))})
        rows_a.append({"fold": fi, "subset": n, "model": "Dedicated",
                       **metrics(y[te], ded.predict(X.iloc[te][cols]))})

    # B. random missingness at test time
    full = make_model("XGBoost", PARAMS, n_jobs=2).fit(X.iloc[tr], y[tr])
    mean_imp = SimpleImputer().fit(X.iloc[tr])
    Xlog = np.log1p(X.iloc[tr])
    mice = IterativeImputer(max_iter=15, random_state=SEED).fit(Xlog)
    for r in RATES:
        Xt = X.iloc[te].copy()
        mask = rng.random(Xt.shape) < r
        Xt = Xt.mask(mask)
        rows_b.append({"fold": fi, "rate": r, "method": "Universal (native NaN)", **metrics(y[te], uni.predict(Xt))})
        rows_b.append({"fold": fi, "rate": r, "method": "Full model + mean imputation",
                       **metrics(y[te], full.predict(pd.DataFrame(mean_imp.transform(Xt), columns=PARAMS)))})
        Xi = np.expm1(mice.transform(np.log1p(Xt)))
        rows_b.append({"fold": fi, "rate": r, "method": "Full model + iterative imputation",
                       **metrics(y[te], full.predict(pd.DataFrame(Xi, columns=PARAMS)))})

    # C. measurement noise (test inputs only; models trained on clean data)
    for n in ["S3", "I3-importance", "S7", "Full-8"]:
        cols = SUBSETS[n]
        m = make_model("XGBoost", cols, n_jobs=2).fit(X.iloc[tr][cols], y[tr])
        for sc in NOISE_SCALES:
            for rep in range(3):
                Xn = add_noise(X.iloc[te][cols], sc, rng)
                rows_c.append({"fold": fi, "subset": n, "scale": sc, "rep": rep, "param": "all",
                               **metrics(y[te], m.predict(Xn))})
        # one parameter at a time at scale 1
        for p in cols:
            for rep in range(3):
                Xn = X.iloc[te][cols].copy()
                Xn[[p]] = add_noise(Xn[[p]], 1, rng)
                rows_c.append({"fold": fi, "subset": n, "scale": 1, "rep": rep, "param": p,
                               **metrics(y[te], m.predict(Xn))})
    return rows_a, rows_b, rows_c


def main():
    df = load_model_set()
    folds = station_folds(df)
    outs = Parallel(n_jobs=5)(delayed(run_fold)(df, tr, te, fi) for fi, (tr, te) in enumerate(folds))
    A = pd.DataFrame([r for o in outs for r in o[0]])
    B = pd.DataFrame([r for o in outs for r in o[1]])
    C = pd.DataFrame([r for o in outs for r in o[2]])
    A.to_csv(RESULTS / "robust_universal_raw.csv", index=False)
    B.to_csv(RESULTS / "robust_missing_raw.csv", index=False)
    C.to_csv(RESULTS / "robust_noise_raw.csv", index=False)

    a = A.groupby(["subset", "model"])[["R2", "RMSE", "CatAcc"]].mean().reset_index()
    b = B.groupby(["rate", "method"])[["R2", "RMSE", "CatAcc"]].mean().reset_index()
    c_all = C[C["param"] == "all"].groupby(["subset", "scale"])[["R2", "RMSE", "CatAcc"]].mean().reset_index()
    c_one = C[C["param"] != "all"].groupby(["subset", "param"])[["R2", "RMSE", "CatAcc"]].mean().reset_index()
    a.to_csv(RESULTS / "robust_universal.csv", index=False)
    b.to_csv(RESULTS / "robust_missing.csv", index=False)
    c_all.to_csv(RESULTS / "robust_noise.csv", index=False)
    c_one.to_csv(RESULTS / "robust_noise_by_param.csv", index=False)
    print(a.pivot(index="subset", columns="model", values="RMSE").loc[NAMED].round(3))
    print(b.pivot(index="rate", columns="method", values="RMSE").round(3))
    print(c_all.pivot(index="subset", columns="scale", values="RMSE").round(3))
    print(c_one.round(3).to_string())

    # ------------------------------------------------------------ figures
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.4))
    ax = axes[0]
    pv = a.pivot(index="subset", columns="model", values="RMSE").loc[NAMED]
    x = np.arange(len(NAMED))
    ax.bar(x - 0.2, pv["Dedicated"], 0.4, label="Dedicated model per subset", color="#30638e")
    ax.bar(x + 0.2, pv["Universal (mask-trained)"], 0.4, label="One mask-trained model", color="#edae49")
    ax.set_xticks(x, NAMED, rotation=35, ha="right", fontsize=7.5)
    ax.set_ylabel("RMSE (unseen stations)")
    ax.legend(fontsize=7.5)
    ax.set_title("A. One model for every subset?")
    ax = axes[1]
    for mth, col in zip(b["method"].unique(), ["#edae49", "#7f7f7f", "#2ca02c"]):
        g = b[b["method"] == mth]
        ax.plot(g["rate"] * 100, g["RMSE"], "o-", label=mth, color=col)
    ax.set_xlabel("% of readings missing at random")
    ax.set_ylabel("RMSE")
    ax.legend(fontsize=7.5)
    ax.set_title("B. Missing readings at test time")
    ax = axes[2]
    for n in ["S3", "I3-importance", "S7", "Full-8"]:
        g = c_all[c_all["subset"] == n]
        ax.plot(g["scale"], g["RMSE"], "o-", label=n, color=SUBSET_COLORS[n])
    ax.set_xlabel("Noise level (× typical field-sensor error)")
    ax.set_ylabel("RMSE")
    ax.legend(fontsize=7.5)
    ax.set_title("C. Measurement noise")
    savefig(fig, "fig_rob_all")


if __name__ == "__main__":
    main()
