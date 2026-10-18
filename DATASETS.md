# Usable Datasets for Reduced-Parameter WQI Prediction

This file lists every dataset identified as usable for the project, with source, size/coverage, and its intended role. Figures marked **(confirmed)** were verified via the source page itself; figures marked **(unconfirmed — verify on download)** were not exposed on a static page (common with Kaggle, which renders dataset stats via JavaScript) and must be checked once the file is actually downloaded, before it's relied on for planning.

---

## 1. Primary Government Sources (India) — ground truth / core corpus

| Dataset | Source & Link | Size / Coverage | How We'll Use It |
|---|---|---|---|
| **CPCB National Water Quality Monitoring Programme (NWMP)** | https://cpcb.gov.in/nwmp-data/ | **(confirmed)** Network spans **4,484 monitoring locations** across 28 states + 7 UTs, of which **2,108 stations are on 189 rivers**. Yearly reports from **2012–2025**, mostly PDF/Excel. | Primary source of the full 9-parameter panel across many rivers. Because station density varies hugely (some rivers monitored monthly for 20+ years, others sporadically) this single source naturally contains both **data-rich** and **data-scarce** stations — used as both training corpus and real (not simulated) scarcity test set. |
| **CPCB Surface Water Quality (Manual) — via National Water Data Portal** ✅ **ACQUIRED** | https://nwdp.nwic.gov.in/dataset/?organization=cpcb | **(confirmed by download)** 3 CSV datasets — Physical (94,159 rows / 70 files / 15 MB), Chemical (109,683 rows / 71 files / 27 MB), Biological (107,537 rows / 70 files / 16 MB). Covers 36 states/UTs, ~4,000 stations, 1961–2024. Saved locally at `data/raw/{physical,chemical,biological}/`. | **This is now the project's primary working dataset.** Physical + Chemical + Biological tables are joined on `(Station, Data Acquisition Time)` to reconstruct the full parameter row needed for WQI ground truth — see [DATA_EXPLORATION.md](DATA_EXPLORATION.md) for real fill-rate analysis and join caveats found after inspection. |
| **CPCB Real-Time Water Quality Monitoring Stations (RTWQMS)** | https://cpcb.nic.in/real-time-water-quality-monitoring/ | **(confirmed)** 36 real-time stations commissioned on the Ganga (Phase 1, since 2017). Each logs **pH, DO, conductivity, BOD, turbidity, temperature every 15 minutes**. | These 6 logged parameters are exactly sensor-measurable (no lab incubation) — used as a live/near-live testbed for the 5-and-6-parameter reduced subsets, and as a check on whether high-frequency sensor data alone can substitute periodic lab sampling. |
| **data.gov.in — "Water Quality" dataset group** | https://www.data.gov.in/dataset-group-name/water-quality | State/SPCB-wise CSV/XLS uploads. Per-file size varies (typically hundreds to a few thousand rows per state per year) — **(unconfirmed per-file — verify on download)**. | Supplementary state-level sources, especially valuable for small/local rivers monitored only by individual State Pollution Control Boards — these are the most naturally "data-scarce" stations in the whole project. |
| **India-WRIS (Water Resources Information System)** | https://indiawris.gov.in/ | GIS-integrated hydrological + water-quality data, station-wise. Requires free registration; size varies by query. | Optional auxiliary source — pull river discharge/flow data per station to test as an extra low-cost proxy feature alongside the reduced chemical parameter sets. |

---

## 2. Ready-to-Use Processed Datasets (Kaggle) — for fast prototyping

| Dataset | Source & Link | Size / Coverage | How We'll Use It |
|---|---|---|---|
| **"Indian water quality data"** (anbarivan) | https://www.kaggle.com/datasets/anbarivan/indian-water-quality-data | **(confirmed via literature citing it)** **1,679 records**, **7 parameters** — DO, pH, conductivity, BOD, nitrate, fecal coliform, total coliform — multiple Indian states, **2005–2014** (CPCB-derived). | Fastest path to a clean, ready-to-train baseline. Already used in published WQI-ML papers, so it doubles as a benchmark to reproduce/compare against. Since it already ships with 7 parameters, it's the natural first dataset to prototype the **7-parameter model** before scaling to the full CPCB corpus. |
| **"India Water Quality Data"** (venkatramakrishnan) | https://www.kaggle.com/datasets/venkatramakrishnan/india-water-quality-data | Government-sourced. **(unconfirmed — verify on download)**. | Secondary/cross-check dataset — potentially extends station or year coverage beyond the anbarivan set; used to sanity-check consistency of parameter values across sources. |
| **"Indian Water Quality Data (2021–2023)"** (rishabchitloor) | https://www.kaggle.com/datasets/rishabchitloor/indian-water-quality-data-2021-2023 | Multi-year, recent. **(unconfirmed — verify on download)**. | Covers years *after* the anbarivan set (2005–2014) — used for a **temporal train/test split** (train on old data, test on recent data) to check whether a reduced-parameter model trained on one era generalizes to another. |
| **"Dataset of River Ganga and Sangam (India)"** — IoT sensor data (dal4206) | https://www.kaggle.com/datasets/dal4206/dataset-of-river-ganga-and-sangam-india | Daily IoT sensor readings: **Electrical Conductivity, DO, ORP, pH, Temperature** (5 parameters). Row count **(unconfirmed — verify on download)**. | This is a real-world 5-sensor-parameter deployment that already excludes lab-only parameters (BOD, coliform) — directly usable as a live test case for the project's **3- and 5-parameter sensor-only subsets**. |
| **"Water bodies quality data – India"** (balabaskar) | https://www.kaggle.com/datasets/balabaskar/water-quality-data-india | Lakes, ponds, tanks, wetlands (not rivers). Size **(unconfirmed)**. | Out of core scope (not rivers) — kept only as an optional extension experiment ("does the reduced-parameter approach generalize beyond rivers to other water bodies?"). |
| **"NWMP Water Quality Data for Indian Lakes"** (akkshaysr) | https://www.kaggle.com/datasets/akkshaysr/nwmp-water-quality-data-for-indian-lakes | **(confirmed)** CSV, **712 KB**. Lakes, not rivers. | Same caveat as above — reserved for an optional non-river generalization extension, not the core river-focused study. |

---

## 3. Academic / Open Multi-Sensor Dataset

| Dataset | Source & Link | Size / Coverage | How We'll Use It |
|---|---|---|---|
| **"An Open, Multi-Sensor Dataset of Water Pollution of the Ganga Basin"** (Chaudhary et al.) | https://arxiv.org/abs/1612.05626 | **(confirmed)** **60+ locations** across the Ganga Basin; combines real-time sensor readings, laboratory results, **and citizen mobile-app estimates**; documented case study spans the Ardh Kumbh 2016 event (months of data). Exact record count not stated in the abstract — **(unconfirmed — verify on download)**. | Directly relevant to the "reduced/low-cost monitoring" framing: lets us test whether **citizen-reported / app-estimated readings** can stand in for one or more lab parameters, an even cheaper alternative to sensor hardware. Also a good multi-modal robustness check for the scarcity experiments. |

---

## 4. Global / Cross-Geography Supplementary Sources

| Dataset | Source & Link | Size / Coverage | How We'll Use It |
|---|---|---|---|
| **USGS National Water Information System (NWIS)** | https://waterdata.usgs.gov/nwis | Decades of US river monitoring data; millions of records across thousands of stations. | Cross-geography generalization test — check whether a reduced-parameter model trained on Indian river chemistry transfers to US rivers (or vice versa), a strong differentiator for the study. |
| **Water Quality Portal (WQP)** — joint USGS / EPA / 400+ agencies | https://www.waterqualitydata.us/ | **(confirmed)** **430+ million records** contributed by 1,000+ programs/agencies. | Large-scale supplementary source for the **transfer-learning** experiments in the methodology: pretrain a model on data-rich WQP stations, then fine-tune on a simulated data-scarce Indian river to test knowledge transfer across basins/countries. |

---

## 5. Simulated Data-Scarcity Sets (derived, not separately downloaded)

These aren't new downloads — they're controlled subsets carved out of Section 1/2 datasets, needed because *guaranteed* naturally-scarce data is hard to source in bulk:

| Simulation | Derived From | How We'll Use It |
|---|---|---|
| Random row subsampling (5%, 10%, 25%, 50% of rows) | anbarivan Kaggle set + combined CPCB corpus | Produces the "accuracy vs. training-data-size" curve, crossed against the "accuracy vs. parameter-count" curve — the central result of the study. |
| Temporal holdout (train on early years, test on later years) | rishabchitloor (2021–2023) vs. anbarivan (2005–2014) | Tests generalization across time without needing extra downloads. |
| Single-station / few-station training, cross-station testing | CPCB NWMP multi-station corpus | Tests spatial/cross-basin transfer at small scale before attempting the full WQP transfer-learning experiment. |
| Random parameter masking (simulate sensor dropout) | Any of the above | Tests robustness to missing readings, relevant for real low-cost sensor deployments that occasionally fail. |

---

## 6. Recommended Primary Combination

For the core study (not the extensions), the recommended combination is:

1. **CPCB NWMP / National Water Data Portal data** (Section 1) — the authoritative, large-scale, naturally variable-density corpus; this is the dataset the final results should be reported on.
2. **anbarivan Kaggle set** (Section 2) — fast prototyping and a literature benchmark to validate the pipeline before scaling to the full CPCB corpus.
3. **Dataset of River Ganga and Sangam IoT set** (Section 2) — a genuine low-parameter, sensor-only deployment to validate the 3-/5-parameter subsets against a real (not simulated) reduced-monitoring station.
4. **Water Quality Portal** (Section 4) — used only for the transfer-learning/generalization side-experiment, not the primary Indian-river result.

Everything else (lakes/ponds datasets, India-WRIS, the Ganga Basin multi-sensor academic set) is optional supporting or extension material, called out explicitly in each row above so it doesn't get mistaken for core scope.
