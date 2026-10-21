# Reduced-Parameter WQI Prediction for Data-Scarce River Systems

**CV301: Environmental Engineering · NITK Surathkal · Faculty: Saranya P**
Team: Mayank Tiwari (241CV235), Krupa Marol (241CV231), Srushti Dongre (241CV248), Sreenidhi Golamaru (241CV247), Bharath Chowdary (241CV213)
Final course project submission, October 2026.

> **Question:** Can reduced-parameter monitoring provide reliable Water Quality Index (WQI) prediction for data-scarce river systems?

Using 32,968 real river monitoring visits from the CPCB National Water Quality Monitoring Programme (2018–2021), we computed the CPCB weighted-arithmetic WQI from the full 8-parameter panel. We then trained machine-learning models to predict that same WQI from only 3–7 parameters, and evaluated them on monitoring stations the models never saw during training.

## Read the results

| | |
|---|---|
| 📄 Final report, full (42 pp) | [`report/Report_full.pdf`](report/Report_full.pdf) · [Markdown](report/REPORT_full.md) |
| 📄 Final report, condensed (32 pp) | [`report/Report_trimmed.pdf`](report/Report_trimmed.pdf) · [Markdown](report/REPORT_trimmed.md) |
| 📊 Slides (15) | [`report/slides/WQI_Reduced_Parameters.pptx`](report/slides/WQI_Reduced_Parameters.pptx) · [PDF](report/slides/WQI_Reduced_Parameters.pdf) |

## Key results (unseen stations, XGBoost)

| Parameters used | R² | RMSE (WQI pts) | Category accuracy |
|---|---|---|---|
| pH, DO, BOD | 0.957 | 2.93 | 90.6% |
| pH, BOD, Turbidity (best 3) | 0.977 | 2.14 | 94.0% |
| pH, DO, BOD, Turbidity | 0.994 | 1.13 | 96.8% |
| All 8 parameters | 0.997 | 0.76 | 97.8% |
| *Re-computing the formula from pH, DO, BOD (no ML)* | *0.863* | *5.21* | *83.7%* |

- **What drives the index:** pH and BOD explain 87.5% of the CPCB WQI's variance. Fecal coliform, total coliform and EC together explain under 0.3%, because the unit weights are ∝ 1/standard.
- **Holds beyond training stations:** accuracy stays high on held-out rivers (R² 0.942), states (0.943) and seasons (0.949).
- **Training data needed:** models need data from about 25 or more stations to beat the plain formula.
- **Uncertainty:** split-conformal 90% intervals keep their coverage (about ±4.7 points with 3 parameters).
- **Deployment:** we reconstructed the WQI for 20,132 visits that never had one, including 255 stations.

## Where the code is

All code is in [`scripts/`](scripts/). Run the scripts in numeric order.

| File | What it does |
|---|---|
| [`build_dataset.py`](scripts/build_dataset.py) | Loads the 211 raw CPCB CSVs, joins the physical, chemical and biological tables on station + date, filters to rivers and flags implausible values |
| [`compute_wqi.py`](scripts/compute_wqi.py) | Ground-truth WQI (CPCB weighted-arithmetic, sub-indices capped at 100) |
| [`common.py`](scripts/common.py) | **Shared ML code:** parameter subsets, the 8 models (`make_model`), cross-validation splits, metrics |
| [`01_eda.py`](scripts/01_eda.py) | Exploratory analysis and the exact variance decomposition of the index |
| [`02_importance.py`](scripts/02_importance.py) | Parameter importance: correlation, mutual information, RF/XGBoost importance, permutation, SHAP, drop-column, forward selection |
| [`03_combinatorial.py`](scripts/03_combinatorial.py) | Scores all 255 parameter subsets |
| [`04_models.py`](scripts/04_models.py) | **Main training/evaluation:** 8 models × 12 subsets × 5 validation schemes |
| [`05_scarcity.py`](scripts/05_scarcity.py) | Data-scarcity sweep (2–100% of training stations) |
| [`06_uncertainty.py`](scripts/06_uncertainty.py) | Prediction intervals: Gaussian process, split-conformal, conformalised quantile regression |
| [`07_deployment.py`](scripts/07_deployment.py) | Trains final models and predicts WQI for visits without a full panel; covariate-shift checks |
| [`08_sensitivity.py`](scripts/08_sensitivity.py) | Sensitivity to standard values, equal weights and the uncapped index |
| [`09_robustness.py`](scripts/09_robustness.py) | Missing readings, measurement noise, one mask-trained model |
| [`10_tables.py`](scripts/10_tables.py), [`11_make_markdown.py`](scripts/11_make_markdown.py) | Report tables and LaTeX → Markdown conversion |

Models compared: renormalised formula (no ML), linear regression, k-nearest neighbours, SVR, MLP, random forest, XGBoost, Gaussian process regression.

## Repository layout

```
data/processed/   cleaned river data + ground-truth WQI (cpcb_wqi.csv)
data/raw/         links to the 211 raw CPCB files (CSVs not committed, 57 MB)
scripts/          all code (see above)
results/          every experiment output (CSV/JSON), incl. out-of-fold predictions
figures/          all figures (PDF + PNG)
report/           final report (LaTeX sources, PDFs, Markdown) and slides
*.md (root)       project plan, datasets, methodology, data-exploration and WQI notes
```

## How to run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # Python 3.12+ (tested on 3.14)
cd scripts
../.venv/bin/python 01_eda.py
../.venv/bin/python 02_importance.py
# ... through 09_robustness.py (04 and 05 take the longest: ~50 and ~15 min on 16 CPU cores)
```

`data/processed/` is committed, so the analysis runs without downloading the raw data. To rebuild it from scratch, download the files listed in `data/raw/links_*.txt` into `data/raw/{physical,chemical,biological}/`, then run `build_dataset.py` and `compute_wqi.py`. No GPU is needed. The full command list is in Appendix C of the report.

**Data source:** CPCB Surface Water Quality (Manual) datasets, National Water Data Portal ([nwdp.nwic.gov.in](https://nwdp.nwic.gov.in)).
