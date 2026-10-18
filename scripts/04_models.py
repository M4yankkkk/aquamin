"""
Main experiment: every model x every parameter subset, under five
validation schemes of increasing difficulty (random rows -> unseen stations
-> unseen rivers -> unseen states -> unseen season). Writes
results/models_cv.csv, results/oof_station.csv and figures/fig_models_*.
"""

import sys

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import confusion_matrix
from sklearn.model_selection import KFold

from common import (CAT_LABELS, MAIN_SUBSETS, MODEL_COLORS, MODELS, PARAMS, RESULTS, SEED,
                    SUBSET_COLORS, SUBSETS, TARGET, category, cross_val_predict_df, group_folds,
                    leave_one_group, load_model_set, metrics, savefig, setup_plotting,
                    station_folds, sub_index, summarise, unit_weights)

plt = setup_plotting()

CTX = ["Latitude", "Longitude", "MonthSin", "MonthCos"]
EXTRA = {
    "S3+context": SUBSETS["S3"] + CTX,
    "S4-routine+context": SUBSETS["S4-routine"] + CTX,
}
ALL_SETS = {**SUBSETS, **EXTRA}
SCHEME_SUBSETS = MAIN_SUBSETS + ["I3-importance", "I5-importance"]
SCHEME_LABEL = {"random": "Random rows", "station": "Unseen stations", "river": "Unseen rivers",
                "state": "Unseen states", "season": "Unseen season"}


def run(scheme, sname, model, df, folds):
    cols = ALL_SETS[sname]
    oof, pf = cross_val_predict_df(model, cols, df, folds, n_jobs=1)
    row = {"scheme": scheme, "subset": sname, "model": model, "k": len(cols)}
    row.update(summarise(df[TARGET].to_numpy(), oof, pf))
    return row, (scheme, sname, model, oof)


def main():
    df = load_model_set()
    df["MonthSin"] = np.sin(2 * np.pi * df["Month"] / 12)
    df["MonthCos"] = np.cos(2 * np.pi * df["Month"] / 12)
    y = df[TARGET].to_numpy()

    schemes = {
        "random": list(KFold(5, shuffle=True, random_state=SEED).split(df)),
        "station": station_folds(df),
        "river": group_folds(df, "MatchedRiver"),
        "state": group_folds(df, "State"),
        "season": leave_one_group(df, "Season"),
    }
    tasks = []
    for sname in ALL_SETS:
        for m in MODELS:
            if m == "Formula" and sname in EXTRA:
                continue
            tasks.append(("station", sname, m))
    for sc in ["random", "river", "state", "season"]:
        for sname in SCHEME_SUBSETS:
            for m in MODELS:
                tasks.append((sc, sname, m))
    if "--plot-only" in sys.argv:
        res = pd.read_csv(RESULTS / "models_cv.csv")
        oof = pd.read_csv(RESULTS / "oof_station.csv")
    else:
        # GPR tasks are the slowest: dispatch them first
        tasks.sort(key=lambda t: t[2] != "GPR")
        out = Parallel(n_jobs=16, verbose=5)(delayed(run)(sc, s, m, df, schemes[sc]) for sc, s, m in tasks)
        rows = [o[0] for o in out]
        res = pd.DataFrame(rows)
        res.to_csv(RESULTS / "models_cv.csv", index=False)

        oof = pd.DataFrame({f"{s}|{m}": p for sc, s, m, p in (o[1] for o in out) if sc == "station"})
        oof.insert(0, "y", y)
        oof.insert(0, "Station", df["Station"])
        oof.to_csv(RESULTS / "oof_station.csv", index=False)

    st = res[res["scheme"] == "station"]
    piv = st.pivot(index="subset", columns="model", values="R2")
    order = MAIN_SUBSETS + ["I3-importance", "I4-importance", "I5-importance", "Sensor-3", "Sensor-4",
                            "S3+context", "S4-routine+context"]
    piv = piv.loc[order, MODELS]
    print(piv.round(4).to_string())
    print(st.pivot(index="subset", columns="model", values="RMSE").loc[order, MODELS].round(2).to_string())
    print(res[res["model"] == "XGBoost"].pivot(index="subset", columns="scheme", values="R2")
          .loc[SCHEME_SUBSETS].round(4).to_string())

    # ------------------------------------------------------------ figure: R² heatmap
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    vals = piv.to_numpy()
    im = ax.imshow(np.clip(vals, 0, 1), cmap="RdYlGn", vmin=0.5, vmax=1, aspect="auto")
    ax.set_xticks(range(len(MODELS)), MODELS, rotation=25, ha="right")
    ax.set_yticks(range(len(order)), order)
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            v = vals[i, j]
            ax.text(j, i, "—" if np.isnan(v) else f"{v:.3f}", ha="center", va="center", fontsize=7.5)
    ax.grid(False)
    ax.axhline(4.5, color="k", lw=1)
    ax.axhline(9.5, color="k", lw=1)
    fig.colorbar(im, ax=ax, label="R² (unseen stations)")
    ax.set_title("Held-out-station R² for every model and parameter set")
    savefig(fig, "fig_models_r2_heatmap")

    # ------------------------------------------------------------ figure: accuracy vs param set
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))
    x = np.arange(len(MAIN_SUBSETS))
    for m in MODELS:
        sub = st[st["model"] == m].set_index("subset").loc[MAIN_SUBSETS]
        axes[0].plot(x, sub["RMSE"], "o-", color=MODEL_COLORS[m], label=m, lw=1.3, ms=4)
        axes[1].plot(x, sub["CatAcc"] * 100, "o-", color=MODEL_COLORS[m], label=m, lw=1.3, ms=4)
    for a in axes:
        a.set_xticks(x, ["S3\n(3)", "S4-routine\n(4)", "S5\n(5)", "S7\n(7)", "Full\n(8)"])
    axes[0].set_ylabel("RMSE (WQI points)")
    axes[1].set_ylabel("Category accuracy (%)")
    axes[1].axhline(100 * np.mean(category(y) == "Poor"), color="k", ls=":", lw=0.8)
    axes[1].text(0, 100 * np.mean(category(y) == "Poor") + 0.8, "majority-class baseline", fontsize=7.5)
    axes[0].legend(fontsize=7.5, ncol=2)
    axes[0].set_title("Error vs. parameter set (unseen stations)")
    axes[1].set_title("Category accuracy vs. parameter set")
    savefig(fig, "fig_models_vs_subset")

    # ------------------------------------------------------------ figure: pred vs actual
    best = "XGBoost"
    fig, axes = plt.subplots(1, 4, figsize=(11.5, 3.1), sharey=True)
    for ax, s in zip(axes, ["S3", "S5", "S7", "Full-8"]):
        p = oof[f"{s}|{best}"]
        ax.scatter(y, p, s=3, alpha=0.35, color=SUBSET_COLORS[s])
        ax.plot([10, 95], [10, 95], "k-", lw=0.7)
        for b in [25, 50, 75]:
            ax.axvline(b, color="grey", lw=0.4, ls="--")
            ax.axhline(b, color="grey", lw=0.4, ls="--")
        mm = metrics(y, p)
        ax.set_title(f"{s}: R²={mm['R2']:.3f}, RMSE={mm['RMSE']:.2f}", fontsize=9.5)
        ax.set_xlabel("True capped WQI")
        ax.set_xlim(10, 95)
        ax.set_ylim(10, 95)
    axes[0].set_ylabel("Predicted (XGBoost, unseen stations)")
    savefig(fig, "fig_models_pred_vs_true")

    # ------------------------------------------------------------ figure: confusion matrices
    fig, axes = plt.subplots(1, 4, figsize=(11.5, 3.0))
    for ax, s in zip(axes, ["S3", "S5", "S7", "Full-8"]):
        cm = confusion_matrix(category(y), category(oof[f"{s}|{best}"]), labels=CAT_LABELS)
        cmn = cm / cm.sum(axis=1, keepdims=True)
        ax.imshow(cmn, cmap="Blues", vmin=0, vmax=1)
        for i in range(4):
            for j in range(4):
                ax.text(j, i, f"{cm[i, j]}", ha="center", va="center", fontsize=8,
                        color="white" if cmn[i, j] > 0.6 else "black")
        ax.set_xticks(range(4), ["Exc", "Good", "Poor", "V.Poor"], fontsize=8)
        ax.set_yticks(range(4), ["Exc", "Good", "Poor", "V.Poor"], fontsize=8)
        ax.grid(False)
        ax.set_title(f"{s} (acc. {np.trace(cm)/cm.sum()*100:.1f}%)", fontsize=9.5)
        ax.set_xlabel("Predicted")
    axes[0].set_ylabel("True")
    fig.subplots_adjust(wspace=0.45)
    savefig(fig, "fig_models_confusion")

    # ------------------------------------------------------------ figure: generalisation schemes
    xs = res[res["model"] == "XGBoost"].pivot(index="subset", columns="scheme", values="RMSE")
    xs = xs.loc[SCHEME_SUBSETS, list(SCHEME_LABEL)]
    fig, ax = plt.subplots(figsize=(8.8, 3.4))
    w = 0.16
    for i, sc in enumerate(SCHEME_LABEL):
        ax.bar(np.arange(len(xs)) + (i - 2) * w, xs[sc], w, label=SCHEME_LABEL[sc])
    ax.set_xticks(range(len(xs)), xs.index, fontsize=8.5)
    ax.set_ylabel("RMSE (WQI points)")
    ax.set_ylim(0, xs.to_numpy().max() * 1.22)
    ax.legend(fontsize=8, ncol=5, loc="upper center", bbox_to_anchor=(0.5, 1.0))
    ax.set_title("XGBoost error under increasingly strict validation schemes")
    savefig(fig, "fig_models_generalisation")

    # ------------------------------------------------------------ figure: what the S3 model misses
    w8 = unit_weights(PARAMS)
    missing = sum(sub_index(df, p, cap=100) * w8[p] for p in ["Turbidity", "NitrateN", "FecalColiform",
                                                              "EC", "TotalColiform"])
    resid = oof["S3|XGBoost"] - y
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.3))
    ax = axes[0]
    ax.scatter(missing, resid, s=3, alpha=0.35, color="#d1495b")
    ax.axhline(0, color="k", lw=0.6)
    ax.set_xlabel("Contribution of the 5 unseen parameters to true WQI")
    ax.set_ylabel("S3 residual (pred − true)")
    r = np.corrcoef(missing, resid)[0, 1]
    ax.set_title(f"S3 residuals mirror the unseen term (r = {r:.2f})")
    ax = axes[1]
    turb_q = sub_index(df, "Turbidity", cap=100)
    bins = pd.cut(turb_q, [-1, 20, 40, 60, 80, 99.99, 100], labels=["0–20", "20–40", "40–60", "60–80",
                                                                      "80–99", "100\n(capped)"])
    g = pd.DataFrame({"b": bins, "e": np.abs(resid)}).groupby("b", observed=True)["e"]
    ax.bar(range(len(g.mean())), g.mean(), color="#d1495b", alpha=0.8)
    ax.set_xticks(range(len(g.mean())), g.mean().index, fontsize=8)
    ax.set_xlabel("Turbidity sub-index $q_{Turb}$ (unseen by S3)")
    ax.set_ylabel("Mean |error|")
    ax.set_title("S3 error is largest when turbidity is atypical")
    savefig(fig, "fig_models_s3_residuals")

    # ------------------------------------------------------------ error vs station density
    nvis = df.groupby("Station")[TARGET].transform("size")
    dens = pd.cut(nvis, [0, 3, 6, 9, 12, 100], labels=["1–3", "4–6", "7–9", "10–12", "13+"])
    tab = []
    for s in ["S3", "S5", "S7", "Full-8", "I3-importance"]:
        e = np.abs(oof[f"{s}|XGBoost"] - y)
        t = pd.DataFrame({"d": dens, "e": e}).groupby("d", observed=True)["e"].mean()
        t.name = s
        tab.append(t)
    tab = pd.concat(tab, axis=1)
    tab["n_rows"] = pd.Series(dens).value_counts().reindex(tab.index)
    tab.round(3).to_csv(RESULTS / "models_error_by_station_density.csv")
    print(tab.round(3).to_string())


if __name__ == "__main__":
    main()
