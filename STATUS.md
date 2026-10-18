# Project Status

Living summary of where this project actually stands. Check the date below before trusting anything as current.

**Last updated:** 2026-10-18

---

## Where things stand right now

**Phase:** Complete. All analysis has been run and the final report is written: LaTeX (full and condensed PDFs), Markdown, and a 15-slide deck.

| Stage | Status |
|---|---|
| Problem framing & plan | ✅ Done |
| Dataset survey | ✅ Done |
| Real CPCB data downloaded, cleaned, joined, audited | ✅ Done |
| Ground-truth WQI computed | ✅ Done (4,861 labelled visits) |
| Parameter importance analysis | ✅ Done: 8 methods + forward selection (`02_importance.py`) |
| Exhaustive subset search | ✅ Done: all 255 subsets (`03_combinatorial.py`) |
| Model training (3/4/5/7/8-parameter and other sets) | ✅ Done: 8 models × 12 subsets × 5 CV schemes (`04_models.py`) |
| Data-scarcity sweep | ✅ Done (`05_scarcity.py`) |
| Uncertainty, robustness, sensitivity, deployment | ✅ Done (`06`–`09`) |
| Final report | ✅ Done: `report/` (see below) |

---

## Headline results (unseen stations, XGBoost)

- **pH, DO, BOD (S3):** R² 0.957, RMSE 2.9, 90.6% category accuracy. No visit is ever off by two or more categories. The renormalised formula over the same three parameters gets R² 0.863.
- **Best 3 parameters:** pH, BOD, Turbidity (R² 0.977). Adding DO gives 0.994; adding Nitrate gives 0.998, the ceiling.
- **The CPCB weights (∝ 1/Sᵢ) drive everything:** pH and BOD explain 87.5% of WQI variance; Fecal Coliform, EC and Total Coliform together explain under 0.3%. As a result the planned S5 barely beats S3.
- **Generalisation:** unseen rivers 0.942, unseen states 0.943, unseen season 0.949 (S3).
- **Data scarcity:** models need training data from about 25 or more stations to beat the formula. GPR is best when data are scarce, XGBoost with more data.
- **Uncertainty:** split-conformal 90% intervals hold coverage (±4.7 points for S3).
- **Robustness:** field-level pH noise (σ = 0.1) costs more accuracy than dropping five parameters.
- **Sensitivity:** under equal weights, S3 falls to R² 0.62; only S7 is robust to every index definition. The EC standard is irrelevant, which closes the old open issue #4.
- **Deployment:** WQI reconstructed for 20,132 visits, including 255 stations that never had one. Shift-corrected RMSE is 3.0.

---

## Document map

| File | What it's for |
|---|---|
| [PROJECT.md](PROJECT.md) | Problem statement, objectives, original plan |
| [DATASETS.md](DATASETS.md) | Candidate datasets; CPCB marked acquired |
| [METHODOLOGY.md](METHODOLOGY.md) | Parameter definitions and the pre-registered 3/5/7 subsets |
| [DATA_EXPLORATION.md](DATA_EXPLORATION.md) | Findings log, incl. §8: 2020-only panel, BOD reporting floor, BOD column misalignment |
| [WQI_CALCULATION.md](WQI_CALCULATION.md) | WQI formula, standards, capping |
| `report/Report_full.pdf` | **Final report, full version (42 pp)** |
| `report/Report_trimmed.pdf` | Final report, condensed version (32 pp) |
| `report/REPORT_full.md`, `report/REPORT_trimmed.md` | The same two reports in Markdown, generated from the LaTeX |
| `report/slides/WQI_Reduced_Parameters.pptx` | 15-slide presentation with speaker notes |
| `report/latex/` | LaTeX sources: `body.tex` + `sections/`; `main_full.tex` / `main_trimmed.tex` set the `\iffull` flag |
| `scripts/01_eda.py` … `09_robustness.py` | Analysis pipeline (shared code in `scripts/common.py`) |
| `scripts/10_tables.py`, `scripts/11_make_markdown.py` | Appendix tables from CSVs; LaTeX → Markdown converter |
| `results/`, `figures/` | All experiment outputs (CSV/JSON) and figures (PDF + PNG) |

---

## Environment

- `.venv/` was rebuilt on **Python 3.14** on 2026-10-18; the old 3.12 venv broke when the system Python was upgraded. `ensurepip` is missing on this machine, so the venv is created with `--without-pip` and bootstrapped with `get-pip.py`.
- Install with `.venv/bin/pip install -r requirements.txt`.
- Re-running the data pipeline under the new environment reproduced all three `data/processed/` files byte-for-byte.
- The slide deck is built with `pptxgenjs` (Node), which is not a project dependency. Install it anywhere and point `NODE_PATH` at it (see the header of `report/slides/build_deck.js`).
- The LaTeX is compiled with `tectonic`.
- Full run order: report Appendix C.

## Data in git

`data/raw/**/*.csv` is gitignored (57 MB; re-fetchable via `data/raw/links_*.txt`). `data/processed/` is tracked (34 MB), so the analysis runs without re-downloading.

---

## Known open issues

1. River-name matching uses a manual list of about 95 rivers. Small and local rivers, the most data-scarce ones, are under-covered.
2. BOD values ≤ 1 mg/L are blank outside 2020. A censored-data (e.g. Tobit) treatment would let those visits count properly in year-to-year comparisons.
3. About 3,000 rows in 2020 biological files have colour words in the BOD column (misalignment). These rows are not in the labelled set, but the source files are worth a look.
4. The misplaced 92-row CWC Meghalaya file still loses its BOD/coliform values (low priority, no effect on results).
5. Ground truth exists for 2020 only, so inter-annual transfer is untested. Re-run when more full-panel years appear.

## Possible extensions

NSF/CCME or pathogen-weighted indices; CPCB real-time sensor data; satellite turbidity proxies; cost-constrained parameter selection; a small web tool serving the model bank with conformal intervals.
