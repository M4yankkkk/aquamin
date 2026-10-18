"""
Shared definitions for the analysis/modelling scripts (02_* onwards).

Everything that has to be identical across experiments lives here: the
target column, the parameter subsets, feature transforms, model
definitions, CV splitters and metrics. See METHODOLOGY.md for the design
and REPORT.md for the results.
"""

from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, RegressorMixin
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.linear_model import LinearRegression
from sklearn.metrics import f1_score, mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from sklearn.svm import SVR
from xgboost import XGBRegressor

BASE = Path(__file__).resolve().parent.parent
PROCESSED = BASE / "data" / "processed"
RESULTS = BASE / "results"
FIGURES = BASE / "figures"
RESULTS.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compute_wqi import ALL_PARAMS, compute_wqi, sub_index, unit_weights  # noqa: E402

SEED = 42
TARGET = "WQI_full_capped"

# Canonical display order (descending formula weight) and labels.
PARAMS = ["pH", "BOD", "DO", "Turbidity", "NitrateN", "FecalColiform", "EC", "TotalColiform"]
LABEL = {
    "pH": "pH", "DO": "DO", "BOD": "BOD", "FecalColiform": "Fecal Coli.",
    "EC": "EC", "TotalColiform": "Total Coli.", "Turbidity": "Turbidity",
    "NitrateN": "Nitrate-N",
}
# Heavy-tailed parameters get a log10(1+x) transform for distance/linear models.
LOG_PARAMS = ["BOD", "FecalColiform", "TotalColiform", "Turbidity", "NitrateN", "EC"]

# Parameter subsets evaluated throughout. "Designated" = the availability-
# driven sets fixed in METHODOLOGY.md §3 before any modelling; the others are
# added by this analysis (routine panel, importance-driven, sensor-only).
SUBSETS = {
    "S3": ["pH", "DO", "BOD"],
    "S4-routine": ["pH", "DO", "BOD", "FecalColiform"],
    "S5": ["pH", "DO", "BOD", "FecalColiform", "EC"],
    "S7": ["pH", "DO", "BOD", "FecalColiform", "EC", "TotalColiform", "Turbidity"],
    "Full-8": PARAMS,
    "I3-importance": ["pH", "BOD", "Turbidity"],
    "I4-importance": ["pH", "DO", "BOD", "Turbidity"],
    "I5-importance": ["pH", "DO", "BOD", "Turbidity", "NitrateN"],
    "Sensor-3": ["pH", "DO", "EC"],
    "Sensor-4": ["pH", "DO", "EC", "Turbidity"],
}
DESIGNATED = ["S3", "S5", "S7", "Full-8"]
MAIN_SUBSETS = ["S3", "S4-routine", "S5", "S7", "Full-8"]

CAT_BINS = [-np.inf, 25, 50, 75, np.inf]  # capped WQI cannot exceed 100
CAT_LABELS = ["Excellent", "Good", "Poor", "Very Poor"]

SEASON = {12: "Post-monsoon", 1: "Winter", 2: "Winter", 3: "Pre-monsoon", 4: "Pre-monsoon",
          5: "Pre-monsoon", 6: "Monsoon", 7: "Monsoon", 8: "Monsoon", 9: "Monsoon",
          10: "Post-monsoon", 11: "Post-monsoon"}

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)


# --------------------------------------------------------------------------- data
def load_all():
    df = pd.read_csv(PROCESSED / "cpcb_wqi.csv", low_memory=False)
    df["Date"] = pd.to_datetime(df["Date"])
    df["Season"] = df["Month"].map(SEASON)
    return df


def load_model_set():
    """The 4,861 fully-observed river rows that carry the ground-truth target."""
    df = load_all()
    df = df.dropna(subset=[TARGET]).reset_index(drop=True)
    return df


def category(wqi):
    return pd.cut(np.asarray(wqi, dtype=float), bins=CAT_BINS, labels=CAT_LABELS).astype(str)


# ------------------------------------------------------------------------ features
def _log_cols(cols):
    return [c for c in cols if c in LOG_PARAMS]


def preprocessor(cols):
    """log10(1+x) on heavy-tailed params, then standardise everything."""
    logc = _log_cols(cols)
    other = [c for c in cols if c not in logc]
    steps = []
    if logc:
        steps.append(("log", FunctionTransformer(np.log1p, feature_names_out="one-to-one"), logc))
    if other:
        steps.append(("pass", "passthrough", other))
    return Pipeline([("ct", ColumnTransformer(steps)), ("sc", StandardScaler())])


class FormulaBaseline(BaseEstimator, RegressorMixin):
    """No-ML baseline: the same capped weighted-arithmetic WQI, computed from
    only the available parameters with weights renormalised over them. This is
    what a practitioner would do without a model (cf. WQI_partial)."""

    def __init__(self, cols=None):
        self.cols = cols

    def fit(self, X, y=None):
        return self

    def predict(self, X):
        X = pd.DataFrame(X, columns=self.cols)
        return compute_wqi(X, list(self.cols), cap=100).to_numpy()


class SubsampledGPR(BaseEstimator, RegressorMixin):
    """Exact GPR is O(n^3); fit on at most `max_n` random training rows
    (a standard subset-of-data approximation). ARD RBF + white noise."""

    def __init__(self, cols=None, max_n=1500, n_restarts=1, random_state=SEED):
        self.cols = cols
        self.max_n = max_n
        self.n_restarts = n_restarts
        self.random_state = random_state

    def fit(self, X, y):
        X = pd.DataFrame(X, columns=self.cols)
        y = np.asarray(y, dtype=float)
        if len(X) > self.max_n:
            idx = np.random.default_rng(self.random_state).choice(len(X), self.max_n, replace=False)
            X, y = X.iloc[idx], y[idx]
        self.pre_ = preprocessor(self.cols).fit(X)
        k = (ConstantKernel(1.0, (1e-2, 1e2))
             * RBF(length_scale=np.ones(len(self.cols)), length_scale_bounds=(1e-2, 1e3))
             + WhiteKernel(0.1, (1e-5, 1e1)))
        self.gp_ = GaussianProcessRegressor(k, normalize_y=True, n_restarts_optimizer=self.n_restarts,
                                            random_state=self.random_state)
        self.gp_.fit(self.pre_.transform(X), y)
        return self

    def predict(self, X, return_std=False):
        X = pd.DataFrame(X, columns=self.cols)
        return self.gp_.predict(self.pre_.transform(X), return_std=return_std)


def make_model(name, cols, n_jobs=1):
    """Model zoo. Hyper-parameters are fixed a priori (Appendix B of the report)
    rather than tuned per fold, so every subset/size gets an identical recipe."""
    cols = list(cols)
    if name == "Formula":
        return FormulaBaseline(cols)
    if name == "Linear":
        return Pipeline([("pre", preprocessor(cols)), ("m", LinearRegression())])
    if name == "kNN":
        return Pipeline([("pre", preprocessor(cols)),
                         ("m", KNeighborsRegressor(n_neighbors=10, weights="distance"))])
    if name == "SVR":
        return Pipeline([("pre", preprocessor(cols)), ("m", SVR(C=30, epsilon=0.5, gamma="scale"))])
    if name == "MLP":
        return Pipeline([("pre", preprocessor(cols)),
                         ("m", MLPRegressor(hidden_layer_sizes=(64, 32), alpha=1e-3,
                                            learning_rate_init=3e-3, max_iter=3000,
                                            early_stopping=True, n_iter_no_change=30,
                                            random_state=SEED))])
    if name == "RandomForest":
        return RandomForestRegressor(n_estimators=400, min_samples_leaf=2, max_features=1.0,
                                     random_state=SEED, n_jobs=n_jobs)
    if name == "XGBoost":
        return XGBRegressor(n_estimators=600, learning_rate=0.03, max_depth=5, subsample=0.8,
                            colsample_bytree=0.9, min_child_weight=3, reg_lambda=1.0,
                            random_state=SEED, n_jobs=n_jobs, tree_method="hist")
    if name == "GPR":
        return SubsampledGPR(cols)
    raise ValueError(name)


MODELS = ["Formula", "Linear", "kNN", "SVR", "MLP", "RandomForest", "XGBoost", "GPR"]


# ---------------------------------------------------------------------- splitting
def station_folds(df, k=5, seed=SEED):
    """Primary scheme: whole stations are held out, so a test station is never
    seen in training (the honest analogue of deploying at a new site)."""
    gkf = GroupKFold(n_splits=k, shuffle=True, random_state=seed)
    return list(gkf.split(df, groups=df["Station"]))


def group_folds(df, col, k=5, seed=SEED):
    gkf = GroupKFold(n_splits=k, shuffle=True, random_state=seed)
    return list(gkf.split(df, groups=df[col]))


def leave_one_group(df, col):
    return [(np.where(df[col] != g)[0], np.where(df[col] == g)[0]) for g in sorted(df[col].unique())]


# ------------------------------------------------------------------------ metrics
def kge(y, p):
    r = np.corrcoef(y, p)[0, 1]
    alpha = np.std(p) / np.std(y)
    beta = np.mean(p) / np.mean(y)
    return 1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)


def metrics(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    sse = np.sum((y - p) ** 2)
    sst = np.sum((y - y.mean()) ** 2)
    cy, cp = category(y), category(p)
    yi = np.searchsorted([25, 50, 75], y, side="left")
    pi = np.searchsorted([25, 50, 75], p, side="left")
    return {
        "R2": 1 - sse / sst,  # identical to Nash-Sutcliffe efficiency on held-out data
        "RMSE": float(np.sqrt(mean_squared_error(y, p))),
        "MAE": float(mean_absolute_error(y, p)),
        "KGE": float(kge(y, p)),
        "CatAcc": float(np.mean(cy == cp)),
        "CatF1": float(f1_score(cy, cp, average="macro", labels=CAT_LABELS, zero_division=0)),
        "Within5": float(np.mean(np.abs(y - p) <= 5)),
        "OffBy2Plus": float(np.mean(np.abs(yi - pi) >= 2)),
    }


def cross_val_predict_df(model_name, cols, df, folds, y=None, n_jobs=1):
    """Out-of-fold predictions (each row predicted by the model whose training
    fold excluded it). Returns array aligned with df and per-fold metrics."""
    y = df[TARGET].to_numpy() if y is None else np.asarray(y)
    X = df[list(cols)]
    oof = np.full(len(df), np.nan)
    per_fold = []
    for tr, te in folds:
        m = make_model(model_name, cols, n_jobs=n_jobs)
        m.fit(X.iloc[tr], y[tr])
        oof[te] = m.predict(X.iloc[te])
        per_fold.append(metrics(y[te], oof[te]))
    return oof, per_fold


def summarise(y, oof, per_fold):
    out = metrics(y, oof)
    pf = pd.DataFrame(per_fold)
    for k in ["R2", "RMSE", "MAE", "CatAcc"]:
        out[k + "_sd"] = float(pf[k].std(ddof=1)) if len(pf) > 1 else np.nan
    return out


# --------------------------------------------------------------------- plotting
def setup_plotting():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
        "font.size": 10, "axes.titlesize": 11, "axes.labelsize": 10,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.25, "legend.frameon": False,
        "font.family": "DejaVu Sans",
    })
    return plt


SUBSET_COLORS = {
    "S3": "#d1495b", "S4-routine": "#edae49", "S5": "#66a182", "S7": "#00798c",
    "Full-8": "#30638e", "I3-importance": "#b07aa1", "I4-importance": "#8e6c8a", "I5-importance": "#5b3758",
    "Sensor-3": "#9a9a9a", "Sensor-4": "#5f5f5f",
}
MODEL_COLORS = {
    "Formula": "#7f7f7f", "Linear": "#bcbd22", "kNN": "#17becf", "SVR": "#9467bd",
    "MLP": "#8c564b", "RandomForest": "#2ca02c", "XGBoost": "#d62728", "GPR": "#1f77b4",
}


def savefig(fig, name):
    fig.savefig(FIGURES / f"{name}.pdf")
    fig.savefig(FIGURES / f"{name}.png")
    import matplotlib.pyplot as plt
    plt.close(fig)
