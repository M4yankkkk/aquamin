"""
Exploratory data analysis on the river subset and the 4,861-row modelling set.
Writes figures/ (fig_eda_*) and results/eda_*.{csv,json}.
"""

import json

import numpy as np
import pandas as pd

from common import (CAT_LABELS, FIGURES, LABEL, PARAMS, RESULTS, SEASON, TARGET, category,
                    load_all, savefig, setup_plotting, sub_index, unit_weights)

plt = setup_plotting()
ORDER7 = ["pH", "DO", "BOD", "FecalColiform", "EC", "TotalColiform", "Turbidity", "NitrateN"]


def main():
    df = load_all()
    model = df.dropna(subset=[TARGET]).copy()
    out = {}

    # ---------------------------------------------------------- fill rates by year
    fill_year = df.groupby("Year")[ORDER7].apply(lambda g: g.notna().mean() * 100)
    fill_year = fill_year.loc[[y for y in fill_year.index if y <= 2021]]
    fill_all = df[ORDER7].notna().mean() * 100
    fill_year.round(1).to_csv(RESULTS / "eda_fill_by_year.csv")
    out["fill_overall"] = fill_all.round(1).to_dict()
    out["rows_by_year"] = df["Year"].value_counts().sort_index().to_dict()

    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    im = ax.imshow(fill_year.to_numpy(), cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(ORDER7)), [LABEL[p] for p in ORDER7], rotation=30, ha="right")
    ax.set_yticks(range(len(fill_year)), fill_year.index)
    for i in range(fill_year.shape[0]):
        for j in range(fill_year.shape[1]):
            v = fill_year.iat[i, j]
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=8,
                    color="white" if v > 60 else "black")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="% of river visits")
    ax.set_title("Parameter fill rate on river stations, by year")
    savefig(fig, "fig_eda_fill_by_year")

    # ---------------------------------------------------------- availability funnel
    steps = [
        ("All river visits\n(suspect rows removed)", len(df)),
        ("pH, DO, BOD\n(S3)", df[["pH", "DO", "BOD"]].notna().all(axis=1).sum()),
        ("+ Fecal Coliform\n(S4-routine)", df[["pH", "DO", "BOD", "FecalColiform"]].notna().all(axis=1).sum()),
        ("+ EC\n(S5)", df[["pH", "DO", "BOD", "FecalColiform", "EC"]].notna().all(axis=1).sum()),
        ("+ Total Coli., Turbidity\n(S7)", df[ORDER7[:7]].notna().all(axis=1).sum()),
        ("+ Nitrate-N\n(all 8: target defined)", df[ORDER7].notna().all(axis=1).sum()),
    ]
    out["funnel"] = {s.replace("\n", " "): int(n) for s, n in steps}
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    names, vals = zip(*steps)
    colors = ["#bbbbbb", "#d1495b", "#edae49", "#66a182", "#00798c", "#30638e"]
    ax.barh(range(len(vals))[::-1], vals, color=colors)
    for i, v in enumerate(vals):
        ax.text(v + 300, len(vals) - 1 - i, f"{v:,}  ({100*v/vals[0]:.1f}%)", va="center", fontsize=9)
    ax.set_yticks(range(len(vals))[::-1], names, fontsize=8.5)
    ax.set_xlim(0, vals[0] * 1.3)
    ax.set_xlabel("River monitoring visits (2018–2024)")
    ax.set_title("How many visits report each parameter set")
    ax.grid(axis="y", visible=False)
    savefig(fig, "fig_eda_funnel")

    # ---------------------------------------------------------- WQI distributions
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.0))
    ax = axes[0]
    ax.hist(model["WQI_full"].clip(upper=600), bins=80, color="#888888")
    ax.set_xlabel("Uncapped WQI (clipped at 600 for display)")
    ax.set_ylabel("Visits")
    ax.set_title(f"Uncapped: mean {model['WQI_full'].mean():.0f}, max {model['WQI_full'].max():.0f}")
    ax = axes[1]
    ax.hist(model[TARGET], bins=60, color="#30638e")
    for b in [25, 50, 75]:
        ax.axvline(b, color="k", lw=0.8, ls="--")
    ax.set_xlabel("Capped WQI (target)")
    ax.set_title(f"Capped: mean {model[TARGET].mean():.1f}, sd {model[TARGET].std():.1f}")
    ax = axes[2]
    cats = category(model[TARGET])
    cc = pd.Series(cats).value_counts().reindex(CAT_LABELS).fillna(0)
    ax.bar(range(4), cc.values, color=["#2a9d8f", "#8ab17d", "#e9c46a", "#e76f51"])
    ax.set_xticks(range(4), CAT_LABELS)
    for i, v in enumerate(cc.values):
        ax.text(i, v + 30, f"{int(v)}\n({100*v/len(model):.1f}%)", ha="center", fontsize=8)
    ax.set_ylim(0, cc.max() * 1.25)
    ax.set_title("Category of capped WQI")
    savefig(fig, "fig_eda_wqi_distribution")
    out["category_counts"] = cc.astype(int).to_dict()
    out["target_describe"] = model[TARGET].describe().round(3).to_dict()

    # ---------------------------------------------------------- parameter distributions
    desc = model[PARAMS].describe(percentiles=[0.05, 0.25, 0.5, 0.75, 0.95]).T
    desc["skew"] = model[PARAMS].skew()
    desc.round(3).to_csv(RESULTS / "eda_param_describe.csv")

    std_line = {"BOD": 3, "FecalColiform": 500, "TotalColiform": 5000, "Turbidity": 10,
                "NitrateN": 45 * 14 / 62, "EC": 1000, "DO": 5}
    fig, axes = plt.subplots(2, 4, figsize=(10.5, 4.6))
    for ax, p in zip(axes.ravel(), PARAMS):
        v = model[p]
        logscale = p not in ("pH", "DO")
        data = np.log10(v.clip(lower=1e-2)) if logscale else v
        ax.hist(data, bins=50, color="#5b8bb5")
        if p in std_line:
            s = np.log10(std_line[p]) if logscale else std_line[p]
            ax.axvline(s, color="#d1495b", lw=1.3, ls="--")
        if p == "pH":
            for s in (6.5, 8.5):
                ax.axvline(s, color="#d1495b", lw=1.3, ls="--")
        ax.set_title(LABEL[p] + (" (log10)" if logscale else ""))
        ax.set_yticks([])
    fig.suptitle("Parameter distributions in the modelling set (red = standard limit Sᵢ)", y=1.01)
    fig.tight_layout()
    savefig(fig, "fig_eda_param_distributions")

    # share of visits exceeding the standard, per parameter
    exceed = {}
    for p in PARAMS:
        q = sub_index(model, p)
        exceed[p] = float((q > 100).mean() * 100)
    out["pct_exceeding_standard"] = {k: round(v, 1) for k, v in exceed.items()}

    # ---------------------------------------------------------- weights vs sub-index spread
    w = unit_weights(PARAMS)
    qcap = pd.DataFrame({p: sub_index(model, p, cap=100) for p in PARAMS})
    contrib = qcap.mul(pd.Series(w))
    # exact variance decomposition: Var(WQI) = sum_i Cov(w_i q_i, WQI)
    wqi = contrib.sum(axis=1)
    share = contrib.apply(lambda c: np.cov(c, wqi)[0, 1]) / wqi.var()
    tab = pd.DataFrame({
        "weight": pd.Series(w), "mean_q_capped": qcap.mean(), "sd_q_capped": qcap.std(),
        "mean_contribution": contrib.mean(), "variance_share": share,
        "pct_exceed": pd.Series(exceed),
    }).loc[PARAMS]
    tab.round(5).to_csv(RESULTS / "eda_weights_contributions.csv")
    out["check_wqi_recomputed_maxabs"] = float(np.abs(wqi - model[TARGET]).max())

    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.1), sharey=True)
    y = np.arange(len(PARAMS))[::-1]
    axes[0].barh(y, tab["weight"], color="#30638e")
    axes[0].set_title("Unit weight $W_i = K/S_i$")
    axes[0].set_yticks(y, [LABEL[p] for p in PARAMS])
    for yy, v in zip(y, tab["weight"]):
        axes[0].text(v + 0.005, yy, f"{v:.4f}", va="center", fontsize=7.5)
    axes[0].set_xlim(0, 0.52)
    axes[1].barh(y, tab["mean_q_capped"], xerr=tab["sd_q_capped"], color="#66a182",
                 error_kw={"elinewidth": 0.8})
    axes[1].set_title("Capped sub-index $q_i$ (mean ± sd)")
    axes[2].barh(y, tab["variance_share"] * 100, color="#d1495b")
    axes[2].set_title("Share of WQI variance (%)")
    for yy, v in zip(y, tab["variance_share"] * 100):
        axes[2].text(max(v, 0) + 1, yy, f"{v:.1f}", va="center", fontsize=7.5)
    axes[2].set_xlim(0, max(tab["variance_share"] * 100) * 1.25)
    for a in axes:
        a.grid(axis="y", visible=False)
    savefig(fig, "fig_eda_weights")

    # ---------------------------------------------------------- station map
    st = model.groupby("Station").agg(lat=("Latitude", "mean"), lon=("Longitude", "mean"),
                                      wqi=(TARGET, "mean"), n=(TARGET, "size"))
    allst = df.groupby("Station").agg(lat=("Latitude", "mean"), lon=("Longitude", "mean"))
    fig, ax = plt.subplots(figsize=(6.2, 6.4))
    ax.scatter(allst.lon, allst.lat, s=5, c="#dddddd", label="River station, no full panel")
    sc = ax.scatter(st.lon, st.lat, c=st.wqi, s=10 + st.n * 1.5, cmap="RdYlGn_r", vmin=30, vmax=80,
                    edgecolor="k", linewidth=0.2, label="Station with full panel (2020)")
    fig.colorbar(sc, ax=ax, shrink=0.7, label="Mean capped WQI (higher = worse)")
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    ax.set_aspect("equal")
    ax.legend(loc="lower left", fontsize=8, markerscale=1.5)
    ax.set_title(f"{len(st)} stations with ground truth, {len(allst)} river stations total")
    savefig(fig, "fig_eda_station_map")
    out["n_stations_model"] = int(len(st))
    out["n_stations_river"] = int(len(allst))
    out["n_rivers_model"] = int(model["MatchedRiver"].nunique())
    out["n_states_model"] = int(model["State"].nunique())
    out["visits_per_station"] = st["n"].describe().round(2).to_dict()

    # ---------------------------------------------------------- seasonality
    mon = model.groupby("Month")[TARGET].describe()
    fig, axes = plt.subplots(1, 2, figsize=(10, 3))
    ax = axes[0]
    ax.fill_between(mon.index, mon["25%"], mon["75%"], color="#30638e", alpha=0.2, label="IQR")
    ax.plot(mon.index, mon["mean"], "o-", color="#30638e", label="Mean")
    ax.set_xticks(range(1, 13), list("JFMAMJJASOND"))
    ax.set_xlabel("Month (2020)")
    ax.set_ylabel("Capped WQI")
    ax.axvspan(5.5, 9.5, color="#edae49", alpha=0.15, label="Monsoon")
    ax.legend(fontsize=8)
    ax.set_title("Seasonal cycle of the target")
    ax = axes[1]
    pm = model.groupby("Month")[["Turbidity", "BOD", "DO"]].median()
    ax.plot(pm.index, pm["Turbidity"] / pm["Turbidity"].mean(), "o-", label="Turbidity")
    ax.plot(pm.index, pm["BOD"] / pm["BOD"].mean(), "s-", label="BOD")
    ax.plot(pm.index, pm["DO"] / pm["DO"].mean(), "^-", label="DO")
    ax.axvspan(5.5, 9.5, color="#edae49", alpha=0.15)
    ax.set_xticks(range(1, 13), list("JFMAMJJASOND"))
    ax.set_ylabel("Monthly median / annual mean")
    ax.legend(fontsize=8)
    ax.set_title("Seasonal cycle of key drivers")
    savefig(fig, "fig_eda_seasonality")
    out["season_counts"] = model["Season"].value_counts().to_dict()

    # ---------------------------------------------------------- river league table
    rv = model.groupby("MatchedRiver")[TARGET].agg(["mean", "std", "count"])
    rv = rv[rv["count"] >= 40].sort_values("mean")
    rv.round(2).to_csv(RESULTS / "eda_river_wqi.csv")
    fig, ax = plt.subplots(figsize=(7.2, 5.2))
    cols = [plt.cm.RdYlGn_r((m - 35) / 45) for m in rv["mean"]]
    ax.barh(range(len(rv)), rv["mean"], xerr=rv["std"], color=cols, error_kw={"elinewidth": 0.6})
    ax.set_yticks(range(len(rv)), [f"{r.title()} (n={int(c)})" for r, c in zip(rv.index, rv["count"])],
                  fontsize=8)
    for b in [25, 50, 75]:
        ax.axvline(b, color="k", lw=0.6, ls="--")
    ax.set_xlabel("Mean capped WQI ± sd (2020)")
    ax.set_title("Rivers with ≥40 fully-observed visits")
    ax.grid(axis="y", visible=False)
    savefig(fig, "fig_eda_rivers")

    with open(RESULTS / "eda_summary.json", "w") as f:
        json.dump(out, f, indent=2, default=float)
    print(json.dumps(out, indent=2, default=float))
    print(tab.round(4).to_string())


if __name__ == "__main__":
    main()
