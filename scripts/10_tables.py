"""
Render the full-results appendix tables of the report directly from
results/*.csv, so the numbers in the report cannot drift from the data.
Writes report/latex/sections/appendix_b.tex.
"""

import pandas as pd

from common import BASE, MODELS, RESULTS

OUT = BASE / "report" / "latex" / "sections" / "appendix_b.tex"
ORDER = ["S3", "S4-routine", "S5", "S7", "Full-8", "I3-importance", "I4-importance", "I5-importance",
         "Sensor-3", "Sensor-4", "S3+context", "S4-routine+context"]
MODEL_HDR = ["Formula", "Linear", "$k$NN", "SVR", "MLP", "RF", "XGB", "GPR"]


def fmt(v, nd):
    return "--" if pd.isna(v) else f"{v:.{nd}f}"


def grid(df, rows, cols, nd, best="min"):
    lines = []
    for r in rows:
        vals = df.loc[r, cols]
        cand = vals.drop("Formula", errors="ignore")
        b = cand.idxmin() if best == "min" else cand.idxmax()
        cells = []
        for c in cols:
            s = fmt(vals[c], nd)
            cells.append(f"\\textbf{{{s}}}" if c == b else s)
        lines.append(f"\\sub{{{r}}} & " + " & ".join(cells) + r" \\")
    return "\n".join(lines)


def table(caption, label, body, colspec, header):
    return (f"\\begin{{table}}[h]\n\\centering\\small\n\\caption{{{caption}}}\n\\label{{{label}}}\n"
            f"\\begin{{tabular}}{{{colspec}}}\n\\toprule\n{header} \\\\\n\\midrule\n{body}\n"
            "\\bottomrule\n\\end{tabular}\n\\end{table}\n")


def main():
    res = pd.read_csv(RESULTS / "models_cv.csv")
    st = res[res["scheme"] == "station"]
    parts = ["\\section{Full result tables}\n\\label{app:tables}\n",
             "All values on unseen stations unless stated; best learned model per row in bold "
             "(the Formula column is excluded from the bold because at \\sub{Full-8} and \\sub{I5} it is "
             "(nearly) the target itself).\n"]
    hdr = "Subset & " + " & ".join(MODEL_HDR)
    for metric, nd, best, cap in [("RMSE", 2, "min", "RMSE (WQI points)"),
                                  ("MAE", 2, "min", "MAE (WQI points)"),
                                  ("CatAcc", 3, "max", "Category accuracy (fraction)")]:
        piv = st.pivot(index="subset", columns="model", values=metric)
        parts.append(table(f"{cap} for every model and subset.", f"tab:app-{metric.lower()}",
                           grid(piv, ORDER, MODELS, nd, best), "l" + "r" * len(MODELS), hdr))

    s3 = res[res["subset"] == "S3"].pivot(index="model", columns="scheme", values="R2")
    s3 = s3.loc[MODELS, ["random", "station", "river", "state", "season"]]
    body = "\n".join(f"{m} & " + " & ".join(f"{v:.3f}" for v in s3.loc[m]) + r" \\" for m in MODELS)
    parts.append(table("\\R{} of every model for \\sub{S3} under the five validation schemes.", "tab:app-s3schemes",
                       body, "lrrrrr", "Model & Random & Stations & Rivers & States & Season"))

    sc = RESULTS / "scarcity.csv"
    if sc.exists():
        a = pd.read_csv(sc)
        fr = sorted(a["frac"].unique())
        for s in ["S3", "S7", "I3-importance"]:
            p = a[a["subset"] == s].pivot(index="model", columns="frac", values="RMSE").loc[MODELS]
            rows = a[(a["subset"] == s) & (a["model"] == "XGBoost")].set_index("frac")["n_train_rows"]
            body = "\n".join(f"{m} & " + " & ".join(f"{p.loc[m, f]:.2f}" for f in fr) + r" \\" for m in MODELS)
            hdr2 = "Model & " + " & ".join(f"{int(f*100)}\\% ({int(rows[f])})" for f in fr)
            parts.append(table(f"Data-scarcity sweep, \\sub{{{s}}}: RMSE by fraction of training stations kept "
                               "(mean training rows in brackets; mean of 5 folds $\\times$ 3 repeats).",
                               f"tab:app-scar-{s.lower()}", body, "l" + "r" * len(fr), hdr2))

    ew = RESULTS / "sens_equalweight_best_per_k.csv"
    if ew.exists():
        b = pd.read_csv(ew)
        body = "\n".join(f"{int(r.k)} & {r.subset.replace('+', ', ').replace('NitrateN', 'Nitrate-N').replace('FecalColiform', 'Fecal coli.').replace('TotalColiform', 'Total coli.')} & "
                         f"{r.R2:.3f} & {r.RMSE:.2f} & {r.CatAcc*100:.1f}\\% \\\\" for r in b.itertuples())
        parts.append(table("Best subset of each size when the target is the \\emph{equal-weight} index.",
                           "tab:app-ew", body, "rp{8cm}rrr", "$k$ & Subset & \\R{} & RMSE & Cat.\\ acc."))

    OUT.write_text("\n".join(parts))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
