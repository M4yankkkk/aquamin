"""
Compute ground-truth WQI (CPCB/NSF Weighted Arithmetic method) on the
cleaned, river-filtered CPCB data.

See WQI_CALCULATION.md for the full formula, standard-value sourcing,
and the reasoning behind computing two separate columns (WQI_full vs
WQI_partial) instead of one.

Input:  data/processed/cpcb_river_stations.csv
Output: data/processed/cpcb_wqi.csv
"""

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
PROCESSED = BASE / "data" / "processed"

# (Standard value Si, Ideal value) per WQI_CALCULATION.md §2.
# "MORE_IS_WORSE" params use the plain linear sub-index; DO and pH get
# their own formulas (handled explicitly below).
STANDARDS = {
    "BOD": {"Si": 3, "ideal": 0},
    "TotalColiform": {"Si": 5000, "ideal": 0},
    "FecalColiform": {"Si": 500, "ideal": 0},
    "Turbidity": {"Si": 10, "ideal": 0},
    "NitrateN": {"Si": 45 * 14 / 62, "ideal": 0},  # 45 mg/L as NO3 -> mg-N/L
    "EC": {"Si": 1000, "ideal": 0},
    "DO": {"Si": 5, "ideal": 14.6},
    "pH": {"Si": None, "ideal": 7.0},  # asymmetric, handled specially
}
PH_LOWER, PH_UPPER = 6.5, 8.5

ALL_PARAMS = list(STANDARDS.keys())
MORE_IS_WORSE = ["BOD", "TotalColiform", "FecalColiform", "Turbidity", "NitrateN", "EC"]

CATEGORY_BINS = [-np.inf, 25, 50, 75, 100, np.inf]
CATEGORY_LABELS = ["Excellent", "Good", "Poor", "Very Poor", "Unsuitable"]


def unit_weights(params):
    """Wi = K / Si, K = 1 / sum(1/Si), over the given subset of parameters."""
    si_values = {"pH": (PH_UPPER - PH_LOWER)}  # use the pH tolerance band as its effective Si for weighting
    si_values.update({p: STANDARDS[p]["Si"] for p in params if p != "pH"})
    inv_sum = sum(1 / si_values[p] for p in params)
    k = 1 / inv_sum
    return {p: k / si_values[p] for p in params}


def sub_index(df, param, cap=None):
    if param == "DO":
        lo, hi = STANDARDS["DO"]["Si"], STANDARDS["DO"]["ideal"]  # Si=5, ideal=14.6
        q = (hi - df["DO"]) / (hi - lo) * 100
    elif param == "pH":
        above = df["pH"] >= 7.0
        q = pd.Series(np.nan, index=df.index)
        q[above] = (df.loc[above, "pH"] - 7.0) / (PH_UPPER - 7.0) * 100
        q[~above] = (7.0 - df.loc[~above, "pH"]) / (7.0 - PH_LOWER) * 100
    else:
        si = STANDARDS[param]["Si"]
        q = df[param] / si * 100
    q = q.clip(lower=0)
    if cap is not None:
        q = q.clip(upper=cap)
    return q


def compute_wqi(df, params, cap=None):
    weights = unit_weights(params)
    q_cols = {p: sub_index(df, p, cap=cap) for p in params}
    numerator = sum(q_cols[p] * weights[p] for p in params)
    denom = sum(weights.values())
    return numerator / denom


def main():
    src = PROCESSED / "cpcb_river_stations.csv"
    df = pd.read_csv(src, low_memory=False)
    print(f"Loaded {len(df):,} river-station rows")

    before = len(df)
    df = df[~df["HasSuspectReading"]].reset_index(drop=True)
    print(f"Excluded {before - len(df):,} rows with a suspect reading -> {len(df):,} remain")

    # --- WQI_full: only rows with ALL 8 parameters present ---
    has_all = df[ALL_PARAMS].notna().all(axis=1)
    print(f"\nRows with all {len(ALL_PARAMS)} parameters present (WQI_full computable): "
          f"{has_all.sum():,} ({100*has_all.sum()/len(df):.1f}%)")

    df["WQI_full"] = np.nan
    df.loc[has_all, "WQI_full"] = compute_wqi(df.loc[has_all], ALL_PARAMS)

    # Capped variant (each sub-index qi clipped at 100 before weighting) --
    # the recommended ML regression target. See WQI_CALCULATION.md Section 7:
    # a handful of genuine but extreme readings (e.g. monsoon turbidity
    # spikes of 3000+ NTU, BOD near raw sewage outfalls) blow up the
    # uncapped WQI into the thousands under a linear sub-index formula --
    # mathematically correct but a terrible regression target, since MSE
    # would be dominated by a few thousand-point rows instead of the
    # decision-relevant 0-150 range. Capping each qi at 100 (standard
    # practice: beyond the regulatory limit, more exceedance doesn't add
    # meaningfully different information) keeps WQI_full_capped in [0,100].
    df["WQI_full_capped"] = np.nan
    df.loc[has_all, "WQI_full_capped"] = compute_wqi(df.loc[has_all], ALL_PARAMS, cap=100)

    # --- WQI_partial: renormalized over whichever params are present per row (descriptive only) ---
    has_any = df[ALL_PARAMS].notna().any(axis=1)
    df["WQI_partial"] = np.nan
    df["ParamsUsed_partial"] = np.nan
    if has_any.any():
        weights_full_set = unit_weights(ALL_PARAMS)
        sub = df.loc[has_any]
        q_all = {p: sub_index(sub, p) for p in ALL_PARAMS}
        num = pd.Series(0.0, index=sub.index)
        den = pd.Series(0.0, index=sub.index)
        count = pd.Series(0, index=sub.index)
        for p in ALL_PARAMS:
            present = sub[p].notna()
            num.loc[present] += q_all[p].loc[present] * weights_full_set[p]
            den.loc[present] += weights_full_set[p]
            count.loc[present] += 1
        df.loc[has_any, "WQI_partial"] = num / den
        df.loc[has_any, "ParamsUsed_partial"] = count

    for col in ["WQI_full", "WQI_full_capped", "WQI_partial"]:
        df[col.replace("WQI", "Category")] = pd.cut(
            df[col], bins=CATEGORY_BINS, labels=CATEGORY_LABELS
        )

    out = PROCESSED / "cpcb_wqi.csv"
    df.to_csv(out, index=False)
    print(f"\nSaved -> {out} ({len(df):,} rows)")

    full = df.dropna(subset=["WQI_full"])
    print(f"\n=== WQI_full distribution (n={len(full):,}, uncapped) ===")
    print(full["WQI_full"].describe().to_string())
    print("\nCategory breakdown (WQI_full, uncapped):")
    print(full["Category_full"].value_counts().reindex(CATEGORY_LABELS).to_string())

    print(f"\n=== WQI_full_capped distribution (n={len(full):,}, each qi capped at 100 -- recommended ML target) ===")
    print(full["WQI_full_capped"].describe().to_string())
    print("\nCategory breakdown (WQI_full_capped):")
    print(full["Category_full_capped"].value_counts().reindex(CATEGORY_LABELS).to_string())

    partial = df.dropna(subset=["WQI_partial"])
    print(f"\n=== WQI_partial distribution (n={len(partial):,}, descriptive only) ===")
    print(partial["WQI_partial"].describe().to_string())
    print("\nParams used per WQI_partial row:")
    print(partial["ParamsUsed_partial"].value_counts().sort_index().to_string())

    print("\n=== Top 10 rivers by mean WQI_full (lower = better) ===")
    river_means = full.groupby("MatchedRiver")["WQI_full"].agg(["mean", "count"])
    river_means = river_means[river_means["count"] >= 20].sort_values("mean")
    print(river_means.head(10).to_string())
    print("\n=== Bottom 10 rivers by mean WQI_full (higher = worse, min 20 samples) ===")
    print(river_means.tail(10).to_string())


if __name__ == "__main__":
    main()
