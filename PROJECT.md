# Reduced-Parameter Water Quality Index (WQI) Prediction for Data-Scarce River Systems

## 1. Problem Statement

> **Can reduced-parameter monitoring provide reliable WQI prediction for data-scarce river systems?**

Water Quality Index (WQI) is traditionally computed from **9–14 physicochemical and biological parameters** (DO, BOD, COD, pH, temperature, turbidity, TDS, conductivity, nitrate, phosphate, fecal/total coliform, etc.). Full-panel monitoring is expensive, lab-dependent (especially BOD, COD, coliform counts which need 3–5 days incubation), and logistically infeasible for:

- Small/rural rivers and tributaries with no permanent monitoring infrastructure
- Developing regions and low-resource river basins
- High-frequency / real-time monitoring (sensors exist cheaply only for a subset of parameters)
- Retrofitting historical sparse records where only a few parameters were ever recorded

**Core hypothesis:** A small, sensor-friendly subset of parameters (3, 5, or 7 out of the full 9–14) — chosen via feature importance / correlation with the true WQI — can be fed into an ML model to predict full WQI with acceptable accuracy (e.g., R² > 0.85–0.90, RMSE within WQI-category tolerance), enabling low-cost, high-frequency, scalable monitoring.

This project treats it as a **feature-reduction + surrogate-modeling problem**: learn a function `f(reduced_params) → WQI` that approximates `g(full_params) → WQI`, and quantify the accuracy/cost trade-off as parameter count drops.

---

## 2. Objectives

1. Compute ground-truth WQI from full-parameter government data using a standard formula (India's CPCB/NSF weighted arithmetic method).
2. Rank parameters by importance/redundancy using statistical + ML feature-selection methods.
3. Build and compare ML models trained on **all parameters**, and on curated **3-, 5-, and 7-parameter subsets**.
4. Quantify accuracy degradation as parameters are reduced, and identify the "knee point" — the minimum parameter count that retains acceptable predictive power.
5. Test robustness under **data scarcity** conditions (few samples, missing values, cross-basin transfer) since that is the real-world deployment scenario for reduced monitoring.
6. Recommend a practical minimal sensor/monitoring kit for low-resource river monitoring stations.

---

## 3. Datasets

### 3.1 Indian Government Sources (Primary — recommended)

| Source | What it has | Access |
|---|---|---|
| **CPCB — Central Pollution Control Board, Water Quality Data** | Real-Time Water Quality Monitoring Stations (RTWQMS) on rivers (Ganga, Yamuna, etc.) + historical manual monitoring (NWMP – National Water Quality Monitoring Programme) data with DO, BOD, pH, conductivity, temperature, nitrate, fecal/total coliform | https://cpcb.nic.in/ , https://cpcb.nic.in/real-time-water-quality-monitoring/ (RTWQMS live dashboard); bulk historical data also mirrored on data.gov.in |
| **data.gov.in — Water Quality datasets** | "Water Quality Data of River [State/Basin]" datasets uploaded per state; NWMP station-wise year-wise CSVs; Ganga Basin water quality data | https://data.gov.in/ (search "water quality river") |
| **India-WRIS (Water Resources Information System)** | Water quality + hydrological data integrated with GIS, river basin-wise | https://indiawris.gov.in/ |
| **CWC — Central Water Commission** | Water quality yearbooks for major rivers, WQI reports | https://cwc.gov.in/ |
| **State Pollution Control Boards (SPCBs)** | State-level river monitoring stations, often finer-grained/local rivers (good for "data-scarce small river" scenario) | e.g., KSPCB (Karnataka), TNPCB, etc. — varies by state |
| **National Water Quality Monitoring Programme (NWMP) Yearbooks (CPCB)** | PDF/Excel yearbooks 2000s–present, ~4000 monitoring stations across India | https://cpcb.nic.in/nwmp-data/ |

**Why this is a good primary choice:** CPCB/NWMP data already reports the classic 9-parameter panel per station per year, across hundreds of rivers and stations of *varying data density* — some rivers/stations have long dense records (good for training/ground truth), others have sparse, irregular records (perfect as a natural "data-scarce" test set) — which maps directly onto the research question.

### 3.2 Global / Supplementary Sources

| Source | What it has | Access |
|---|---|---|
| **USGS National Water Information System (NWIS)** | Long time-series, US rivers, many parameters, good for methodology validation / cross-country generalization test | https://waterdata.usgs.gov/nwis |
| **Water Quality Portal (WQP)** — joint USGS/EPA/NWQMC | Aggregated multi-agency US water quality data | https://www.waterqualitydata.us/ |
| **Kaggle — "Water Quality" / river WQI datasets** | Cleaned, ready-to-use CSVs (often derived from CPCB or Indian river data already) — useful for quick prototyping before wrangling raw govt data | https://www.kaggle.com/datasets (search "water quality index river") |
| **UCI Machine Learning Repository** | A few water-quality-adjacent datasets | https://archive.ics.uci.edu/ |
| **European Environment Agency (EEA) WISE / Waterbase** | EU river water quality monitoring | https://www.eea.europa.eu/data-and-maps/data/waterbase-water-quality-2 |

**Recommendation:** Use **CPCB/NWMP + data.gov.in** as the core dataset (authentic, large, India-relevant, naturally variable in sampling density — ideal for a data-scarcity study), and optionally bring in **one non-Indian dataset (USGS/WQP)** to test whether the reduced-parameter model generalizes across geographies (a strong differentiator for the project).

### 3.3 Data Scarcity Simulation (since real "scarce" datasets are hard to guarantee)

In addition to using naturally sparse stations, **artificially simulate scarcity** on the dense dataset to get controlled experiments:
- Randomly subsample rows to 5%, 10%, 25%, 50% of original size
- Restrict training years (e.g., train on 2 years, test on later years)
- Restrict to a single/few stations then test cross-station transfer
- Randomly mask parameter values (simulate missing sensor readings)

This lets you report a clean **"accuracy vs. sample size" curve** crossed with **"accuracy vs. parameter count" curve** — the two axes of the research question.

---

## 4. WQI Computation (Ground Truth)

Use a standard, well-documented formula so ground truth is defensible:

- **CPCB / NSF Weighted Arithmetic WQI** (most common in Indian literature):
  `WQI = Σ(Wi × Qi) / Σ(Wi)`
  where `Qi` = sub-index (quality rating) of the i-th parameter relative to its standard permissible value, `Wi` = unit weight (inversely proportional to the standard value of that parameter).
- Alternative: **NSF-WQI** (9-parameter, curve-based sub-indices) or **CCME WQI** (scope/frequency/amplitude based) — good for a sensitivity/robustness check (does parameter ranking change with WQI formula choice?).

Standard 9-parameter panel typically used: **DO, BOD, pH, Temperature, Total Coliform/Fecal Coliform, Nitrate, Turbidity, TDS/Conductivity, Total Phosphate.**

---

## 5. Parameter Subset Design (3 / 5 / 7)

Rather than picking subsets arbitrarily, **derive them from feature-importance analysis** on the full model, then sanity-check against sensor cost/practicality. Below is a literature-informed starting hypothesis to validate empirically:

### 5.1 Candidate parameter pool (full set, ~9)
DO, BOD, pH, Temperature, Conductivity/TDS, Turbidity, Nitrate (NO₃⁻), Total/Fecal Coliform, Total Phosphate

### 5.2 Selection criteria to rank them
1. **Correlation with WQI** (Pearson/Spearman) and with each other (drop redundant/collinear pairs)
2. **ML feature importance**: Random Forest / XGBoost `feature_importances_`, permutation importance
3. **SHAP values** for interpretability-driven ranking
4. **Mutual information** with WQI (captures non-linear relevance)
5. **Practicality/cost weighting**: prefer parameters measurable with cheap, real-time, in-situ sensors (pH, DO, temperature, conductivity, turbidity are all low-cost probe-measurable) over lab-only/slow parameters (BOD needs 5-day incubation, coliform needs culturing) — this matters because the *point* of reduced monitoring is field deployability, not just statistical minimality.

### 5.3 Hypothesized subsets to test (validate/adjust via step 5.2 results)

| Set size | Parameters | Rationale |
|---|---|---|
| **3-parameter** | pH, DO, Turbidity (or Conductivity) | Cheapest, fastest, all measurable with a single cheap multi-probe sensor in real time; commonly the top-ranked in prior WQI feature-importance studies |
| **5-parameter** | pH, DO, Temperature, Conductivity/TDS, Turbidity | Adds physical parameters, still all in-situ/sensor-based, no lab incubation needed |
| **7-parameter** | pH, DO, BOD, Temperature, Conductivity, Turbidity, Nitrate | Reintroduces one "slow" lab parameter (BOD) known to be highly weighted in WQI, plus a nutrient indicator (Nitrate) for pollution sensitivity |
| **Full (9)** | + Total/Fecal Coliform, Total Phosphate | Baseline/ceiling for comparison |

Run the actual feature-importance ranking on your dataset and adjust these three sets accordingly — this table is a starting hypothesis, not a fixed answer. Report **all three subset sizes side by side** with accuracy metrics so the notebook/paper can show the actual accuracy-vs-parameter-count trade-off curve, which is the central deliverable.

### 5.4 Also test "combinatorial" subsets, not just one config per size
For a rigorous study, don't just test one hand-picked 3-parameter set — evaluate **multiple candidate combinations** at each size (e.g., top-3 by importance vs. most field-practical 3 vs. most weighted-in-WQI-formula 3) and report the best/worst/average to show sensitivity to *which* parameters are chosen, not just how many.

---

## 6. Machine Learning Methodology

### 6.1 Problem framing
Regression: predict continuous WQI value from parameter subset.
(Optionally also frame as **classification** into WQI categories — Excellent/Good/Poor/Very Poor/Unsuitable — since end-users often care about the category, not the exact number, and classification may be more robust under reduced parameters.)

### 6.2 Models to compare (simple → complex)
1. **Multiple Linear Regression** — interpretable baseline
2. **Random Forest Regressor** — handles non-linearity, gives feature importance for free
3. **XGBoost / LightGBM** — usually best tabular performance, fast, good with small data
4. **Support Vector Regression (SVR)** — good for small/scarce datasets
5. **k-NN Regression** — simple non-parametric baseline
6. **Artificial Neural Network (small MLP)** — for comparison, though likely to overfit on scarce data
7. **Gaussian Process Regression** — gives uncertainty estimates, valuable for a "data-scarce/low-confidence" framing

**Recommendation:** Random Forest / XGBoost as primary models (robust to small-n, give interpretable importances), Linear Regression as baseline, GPR as the "uncertainty-aware" bonus model.

### 6.3 Handling data scarcity specifically (this is the differentiator of the project)
- **Cross-validation with small folds** (Leave-One-Out or 5-fold) instead of a single train/test split when sample size is small
- **Transfer learning across basins**: pretrain on data-rich rivers (e.g., Ganga with dense CPCB records), fine-tune/adapt on data-scarce target river
- **Data augmentation**: SMOTE-for-regression / synthetic minority sampling, or Gaussian noise injection around real samples to expand small training sets
- **Regularization** (Ridge/Lasso, tree depth limits, early stopping) to prevent overfitting on small-n
- **Bayesian/uncertainty-aware models** (Gaussian Process, quantile regression) to report *confidence intervals*, not just point predictions — critical when data is scarce, since "reliable" in the research question implies knowing when NOT to trust the prediction
- **Imputation strategies** for missing parameter values (KNN-imputer, MICE) if using naturally sparse government records with gaps

### 6.4 Evaluation Metrics
- **RMSE, MAE** (absolute error in WQI units)
- **R²** (variance explained)
- **NSE (Nash–Sutcliffe Efficiency)** — standard in hydrology/water-quality ML papers
- **WQI category accuracy** — % of predictions falling in the same quality category (Excellent/Good/Poor/etc.) as ground truth, even if exact value differs — arguably the most decision-relevant metric
- **Uncertainty calibration** (if using GPR/quantile models) — how well predicted confidence intervals capture true error

### 6.5 Experimental Design Matrix
Run every model × every parameter subset (3, 5, 7, full) × every scarcity level (100%, 50%, 25%, 10%, 5% of training data) → produces a rich results grid/heatmap: **(model, #params, %data) → accuracy**. This directly answers the research question quantitatively rather than anecdotally.

---

## 7. Tech Stack

- **Language:** Python 3.10+
- **Data handling:** `pandas`, `numpy`
- **ML:** `scikit-learn`, `xgboost`, `lightgbm`
- **Interpretability:** `shap`
- **Stats/feature selection:** `scipy`, `statsmodels`, `sklearn.feature_selection`
- **Visualization:** `matplotlib`, `seaborn` (or `plotly` for interactive)
- **Notebook environment:** Jupyter / Google Colab (good for reproducibility + sharing)
- **Optional deployment demo:** `streamlit` app where a user enters 3/5/7 sensor readings and gets predicted WQI + category + confidence — great for a project demo/viva

---

## 8. Project Plan / Milestones

1. **Data acquisition** — download CPCB/NWMP data (multiple states/rivers, multiple years), data.gov.in datasets; consolidate into one schema
2. **Data cleaning & EDA** — handle units, missing values, outliers, per-station/per-year aggregation; visualize parameter distributions and correlations
3. **Ground-truth WQI computation** — implement CPCB weighted arithmetic formula, validate against any officially published WQI values as sanity check
4. **Feature importance analysis** — correlation matrix, RF/XGB importances, SHAP, mutual information
5. **Define 3/5/7-parameter subsets** — based on step 4 + practicality
6. **Model training & evaluation** — full experimental matrix (models × subsets × scarcity levels)
7. **Data-scarcity robustness experiments** — subsampling curves, transfer learning across rivers, imputation tests
8. **Results synthesis** — accuracy-vs-parameter-count and accuracy-vs-data-size plots, recommended minimal monitoring kit
9. **(Optional) Streamlit demo app**
10. **Report/paper write-up**

---

## 9. Expected Deliverables

- Cleaned, unified multi-river WQI dataset (CSV) with documented preprocessing pipeline
- Feature importance ranking of all WQI parameters with justification
- Trained models for 3/5/7/full parameter configurations, saved + benchmarked
- Accuracy-vs-parameter-count trade-off curve/table (the key figure answering the research question)
- Accuracy-vs-data-scarcity curve (secondary key figure)
- Recommended **minimal viable sensor kit** for low-resource river monitoring, with expected accuracy/error bounds
- (Optional) Interactive demo app
- Final report/paper documenting methodology and findings

---

## 10. Limitations & Threats to Validity (worth stating explicitly)

- WQI ground truth itself depends on the formula chosen (weighted arithmetic vs NSF vs CCME) — parameter importance rankings can shift somewhat between formulas; report sensitivity to this.
- Government datasets (CPCB/NWMP) can have inconsistent units, station metadata quality, and reporting gaps across years/states — significant cleaning effort should be budgeted.
- "Data-scarce" is being partly *simulated* by subsampling a dense dataset; real scarce stations may have systematically different (not just fewer) characteristics — worth validating on genuinely sparse stations too, not just synthetic subsampling.
- Cross-river/cross-basin generalization is not guaranteed — a model trained on one river's chemistry profile may not transfer to a geologically/climatically different river; this should be tested explicitly, not assumed.
- Excluding coliform/pathogen indicators (common in reduced sets since they're lab-only) means the reduced WQI may miss public-health-relevant contamination even if the aggregate WQI number looks fine — worth a caveat/discussion point.

---

## 11. Possible Extensions (if time permits)

- Time-series forecasting angle: predict *future* WQI from reduced real-time sensor streams (LSTM/Temporal models) rather than just concurrent prediction
- Active learning: identify which additional parameter, if added to a 3-set, would most improve accuracy (guides "what's the next-best sensor to buy")
- Cost-optimization framing: given a sensor budget, formulate parameter selection as a cost-constrained optimization rather than pure accuracy ranking
- Federated/cross-basin model: train one model across multiple states' SPCB data to see if a single reduced-parameter model can serve many rivers at once
- Satellite/remote-sensing proxies (e.g., turbidity/chlorophyll from Sentinel-2) as a "zero in-situ parameter" extreme case, for comparison

---

## 12. Key References / Reading Pointers

- CPCB, *"Guidelines for Water Quality Monitoring"* and NWMP yearbooks (methodology for WQI computation and standard parameter list)
- Horton, R.K. (1965) and Brown et al. (1970) — origin of NSF-WQI method
- CCME (2001) — *Canadian Water Quality Guidelines: CCME Water Quality Index 1.0 Technical Report*
- Search terms for literature review: "machine learning water quality index prediction reduced parameters", "minimum parameters WQI prediction India", "surrogate model water quality index river", "feature selection water quality index random forest"

---

## 13. Quick-Start Checklist

- [ ] Register/download data from data.gov.in and CPCB NWMP portal for 3–5 rivers spanning multiple states
- [ ] Standardize units and column names across sources
- [ ] Implement WQI formula and validate on a few known stations
- [ ] Run correlation + RF/XGB importance + SHAP analysis
- [ ] Lock in 3/5/7-parameter subsets
- [ ] Build experiment loop (models × subsets × data-size levels)
- [ ] Generate the two key trade-off plots
- [ ] Write up findings + recommended minimal monitoring kit
