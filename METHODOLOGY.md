# Parameters & ML Methodology — How We Get From Raw Readings to a Reliable WQI

This file explains, in full, **which water-quality parameters the project uses, why, how they feed into the WQI calculation, and exactly how machine learning turns a reduced set of them into a reliable WQI prediction.** It complements [PROJECT.md](PROJECT.md) (problem framing) and [DATASETS.md](DATASETS.md) (data sources).

---

## 1. The Full Parameter Set (the "ceiling" — 9 parameters)

WQI is conventionally computed from 9 physicochemical/biological parameters. Every one of these exists in the CPCB/NWMP records described in DATASETS.md. This is the **starting pool** from which the 3/5/7-parameter subsets are carved.

| # | Parameter | What it actually measures | Unit | Why it matters for water quality | How it's measured — cost & time |
|---|---|---|---|---|---|
| 1 | **pH** | Acidity/alkalinity of water | pH scale | Extreme pH harms aquatic life and indicates industrial/chemical contamination | Cheap handheld/in-situ probe, instant reading |
| 2 | **Dissolved Oxygen (DO)** | Oxygen available for aquatic organisms | mg/L | Low DO = poor aeration, high organic pollution, fish kills | Cheap in-situ probe, instant reading |
| 3 | **Biochemical Oxygen Demand (BOD)** | Oxygen consumed by microbes decomposing organic matter | mg/L | Direct proxy for organic pollution load (sewage, effluents) | **Lab-only**, 5-day incubation test — slow, expensive, needs trained staff |
| 4 | **Temperature** | Water temperature | °C | Affects DO solubility, biological activity, and is a proxy for thermal pollution | Cheap in-situ probe, instant |
| 5 | **Conductivity / Total Dissolved Solids (TDS)** | Dissolved ion/salt concentration | µS/cm or mg/L | Indicates dissolved salts, industrial discharge, mineral content | Cheap in-situ probe, instant |
| 6 | **Turbidity** | Water clarity / suspended particles | NTU | Indicates silt, erosion, organic/inorganic suspended pollution | Cheap in-situ probe, instant |
| 7 | **Nitrate (NO₃⁻)** | Nutrient/fertilizer runoff indicator | mg/L | Excess nitrate causes eutrophication, algal blooms; health risk in drinking water | Field test kit (~minutes) or lab (more precise) |
| 8 | **Total/Fecal Coliform** | Bacterial (fecal) contamination | MPN/100 mL | Direct indicator of sewage contamination and pathogen risk | **Lab-only**, culturing takes 24–48+ hours |
| 9 | **Total Phosphate** | Nutrient (phosphorus) load | mg/L | Along with nitrate, drives eutrophication and algal blooms | Lab test, a few hours |

**Key pattern to notice (this drives the whole reduction strategy):** parameters 1, 2, 4, 5, 6 are **cheap, instant, field-sensor-measurable**. Parameters 3, 7, 8, 9 are **slow and/or lab-dependent**. Reduced-parameter monitoring is fundamentally about pushing the working set toward the first group while keeping as much WQI-relevant signal as possible from the second.

---

## 2. How the Full Set Becomes Ground-Truth WQI

Before any ML happens, every historical record (all 9 parameters, one row per station/date) is converted into a single **ground-truth WQI value** using the standard **CPCB/NSF Weighted Arithmetic Water Quality Index** method:

- Each parameter's raw value is converted into a **sub-index (Qᵢ)** — a 0–100 quality rating relative to a standard permissible value for that parameter (e.g., BIS/CPCB limits for drinking or bathing water class, depending on the designated use of the river stretch).
- Each parameter is assigned a **unit weight (Wᵢ)**, inversely proportional to its own standard permissible value — parameters with stricter (lower) standards get proportionally more influence.
- The final index is the weighted average: **WQI = Σ(Wᵢ × Qᵢ) / Σ(Wᵢ)**.

This WQI value — computed once from the **full 9-parameter row** — becomes the **target label ("ground truth")** that every ML model is trained to predict, whether it's given 3, 5, 7, or all 9 input parameters. In other words: **the target never changes; only the number of inputs the model is allowed to see changes.** That's what makes the 3-vs-5-vs-7-vs-9 comparison fair and meaningful.

*(Note: since permissible standards differ slightly by designated water use — drinking vs. bathing vs. irrigation class — the exact standard values adopted must be fixed and documented once, and applied consistently across the whole dataset so all WQI ground-truth labels are computed on the same basis.)*

---

## 3. From 9 Down to 7, 5, and 3 — How Parameters Are Actually Chosen

Parameters are **not** hand-picked by guesswork. Selection happens in two combined passes:

**Pass 1 — Statistical/ML relevance ranking**, using the full dataset (9 parameters → WQI):
- **Correlation analysis**: how strongly each parameter individually correlates with the computed WQI, and how much parameters correlate with *each other* (to eliminate redundant pairs — e.g., conductivity and TDS often carry near-identical information).
- **ML feature importance**: train a Random Forest / XGBoost model on all 9 parameters and read off which ones it actually relies on to predict WQI.
- **SHAP values**: a more rigorous, per-prediction breakdown of how much each parameter pushes the predicted WQI up or down — used to double-check the raw importance ranking isn't an artifact of one algorithm.
- **Mutual information**: catches non-linear relevance that plain correlation can miss.

**Pass 2 — Practicality/cost weighting**, applied on top of the statistical ranking:
- Among similarly-ranked parameters, prefer the one that's **cheap, instant, and field-sensor-measurable** (pH, DO, temperature, conductivity, turbidity) over one that needs lab incubation or culturing (BOD, coliform) — because the entire point of "reduced-parameter monitoring" is that it must be deployable in the field, not just statistically minimal on paper.

The two passes are combined, and the resulting subsets are then validated empirically (Section 5) rather than assumed correct — if the data says a hypothesized subset underperforms, the subset is revised.

### Revised subsets — based on actual CPCB data, not just the original hypothesis

The original working hypothesis (below, kept for record) assumed sensor-cheap parameters like Temperature and Conductivity/TDS would also be the most consistently *recorded* ones. Pulling and inspecting the real CPCB dataset (see [DATA_EXPLORATION.md](DATA_EXPLORATION.md)) showed this is wrong in one important case: **Temperature is recorded in essentially 0% of ~94,000 real physical-parameter rows**, and TDS/Total Solids are recorded in under 5%. Meanwhile pH (98.3%), DO (90.4%), and even the lab-only BOD (81.3%) are the best-covered parameters by far. Parameter selection therefore has to be anchored to **actual historical reporting frequency**, not just theoretical measurement cost — a subset is only trainable if stations have actually been logging it.

| Set | Parameters | Why these | What's sacrificed |
|---|---|---|---|
| **3-parameter** | pH, DO, BOD | The three best-covered parameters in the real data (98%, 90%, 81% fill rate) and the three most heavily-weighted terms in most WQI formulas | Loses all pathogen and dissolved-solids/turbidity signal — expect the biggest accuracy drop here for sewage- or silt-affected stretches |
| **5-parameter** | pH, DO, BOD, Fecal Coliform, Electrical Conductivity | Adds the pathogen/public-health signal (73% fill rate) and the best-covered physical/dissolved-solids proxy (52% fill rate) | Still missing Total Coliform and turbidity — some public-health and sediment-pollution cases may be under-flagged |
| **7-parameter** | pH, DO, BOD, Fecal Coliform, Electrical Conductivity, Total Coliform, Turbidity | Adds full coliform coverage (42%) and a suspended-solids indicator (31%) | Nitrate/nutrient signal still excluded (only 27% fill rate — kept for the full/ceiling set instead) |
| **Full (9, ceiling)** | + Nitrate, Total Phosphate | Baseline/ceiling for comparison — not a "reduced" set, used only to measure how much is lost at each reduction. Note: even this "full" set excludes Temperature, TDS, Colour, Odour, and COD, which are too sparsely recorded in this data source to use as model inputs at all | — |

Multiple candidate combinations per size are still tested (e.g., a 3-set chosen purely by statistical importance vs. one chosen purely for fill-rate/practicality) so the final report shows sensitivity to *which* parameters are picked, not just *how many* — but availability now sets the realistic ceiling on what's tested at all.

<details>
<summary>Original hypothesis (superseded — kept for record)</summary>

| Set | Parameters | Why these (original reasoning, before real data was inspected) |
|---|---|---|
| 3-parameter | pH, DO, Turbidity (or Conductivity) | Assumed cheap, instant, single-probe-measurable |
| 5-parameter | pH, DO, Temperature, Conductivity/TDS, Turbidity | Assumed full physical-parameter, 100% sensor-based coverage |
| 7-parameter | pH, DO, BOD, Temperature, Conductivity, Turbidity, Nitrate | Assumed BOD/Nitrate reintroduction gave the best accuracy-for-one-extra-parameter trade |

This assumed sensor-cheap parameters (especially Temperature) would also be the best-recorded ones historically — the real data shows the opposite for Temperature specifically.
</details>

---

## 4. How Parameters Are Used as ML Inputs (feature engineering)

Once a subset is fixed, each parameter becomes one **input feature** to the model, prepared as follows:

- **Scaling/normalization**: parameters are on wildly different scales (pH ~0–14, conductivity ~10–2000+ µS/cm, coliform counts in the thousands) — all inputs are rescaled to comparable ranges so no single parameter dominates purely due to its raw magnitude.
- **Missing value handling**: real government records have gaps; missing readings are filled using neighborhood-aware imputation (e.g., nearest similar station/season) rather than dropped, to preserve as much data as possible — critical for the data-scarce scenario.
- **Temporal context**: month/season is included as an auxiliary feature where relevant, since parameters like temperature and DO are naturally seasonal — this helps the model distinguish "seasonal DO dip" from "pollution-driven DO dip."
- **Station/location identity**: used carefully — either as a categorical feature (for a "same-basin" model) or deliberately excluded (for a cross-basin generalization test), depending on which experiment is being run.
- **No parameter is ever hand-weighted by the analyst** — the whole point of using ML instead of just re-deriving a smaller weighted-arithmetic formula is that the model learns the actual (possibly non-linear, interacting) relationship between the reduced inputs and the full-panel WQI, rather than assuming the same linear weights CPCB uses for the full set still apply when parameters are removed.

---

## 5. The End-to-End ML Pipeline

1. **Assemble ground truth**: combine full-parameter records from CPCB/NWMP + supplementary sources (per DATASETS.md) into one table; compute WQI for every row using the fixed standard (Section 2).
2. **Clean & split**: handle units/inconsistencies across sources; create train/test splits three different ways — random split, temporal split (train on older years, test on newer), and station-holdout split (train on some rivers, test on unseen ones) — because "reliable for data-scarce systems" specifically means reliable on data the model hasn't effectively seen before.
3. **Run parameter selection** (Section 3) once on the full-parameter training data to lock in the 3/5/7 subsets.
4. **Construct reduced-input training tables**: for each subset size, build a version of the training data containing *only* those input columns, still paired with the same full-panel-derived WQI label.
5. **Train multiple model types on each subset**, so the comparison isn't tied to one algorithm's quirks:
   - **Linear Regression** — interpretable baseline; shows how much of the relationship is simply linear.
   - **Random Forest / XGBoost** — the primary candidates; handle non-linear parameter interactions well and remain robust with modest amounts of data.
   - **Support Vector Regression (SVR)** — often competitive specifically when training data is small.
   - **Gaussian Process Regression (GPR)** — in addition to a point prediction, this gives a **confidence interval**, which is essential for the "reliable" part of the research question: a data-scarce station should get a prediction *plus* an honest statement of how uncertain that prediction is.
   - **A small neural network** — included mainly as a comparison point; expected to need more data than the scarce-data scenario provides, which is itself an informative negative result.
6. **Evaluate every (model × parameter-subset × data-availability-level) combination** using:
   - **RMSE / MAE** — average numeric error in WQI units.
   - **R²** — how much of the WQI's variation the reduced inputs actually explain.
   - **NSE (Nash–Sutcliffe Efficiency)** — the standard water-quality-modeling benchmark, allows direct comparison with published studies.
   - **WQI-category accuracy** — how often the reduced-parameter model puts a sample in the correct quality bucket (Excellent/Good/Poor/Very Poor/Unsuitable) even if the exact numeric value is slightly off — arguably the metric that matters most to an actual decision-maker.
7. **Repeat step 6 across shrinking training-data sizes** (100%, 50%, 25%, 10%, 5%, plus real naturally-sparse stations) — this produces the second key curve: how much training data a given parameter subset actually needs to stay reliable.
8. **Cross-basin / cross-country transfer test**: pretrain the best-performing model+subset combination on a data-rich source (e.g., Water Quality Portal or a dense CPCB river), then fine-tune on a small target river's data, to test whether knowledge transfer can compensate for genuine scarcity rather than relying on more subsampled-but-still-similar data.

---

## 6. How This Actually Answers the Research Question

Putting it together, the pipeline produces two central results that directly answer *"Can reduced-parameter monitoring provide reliable WQI prediction for data-scarce river systems?"*:

1. **An accuracy-vs-parameter-count curve** — showing exactly how much WQI prediction accuracy is retained (or lost) going from 9 → 7 → 5 → 3 parameters, per model type. If the 5- or 7-parameter curve stays close to the 9-parameter ceiling, that's a direct "yes" for that subset size; if the 3-parameter curve drops sharply, that defines the practical floor.
2. **An accuracy-vs-training-data-size curve**, crossed with the above — showing whether a given reduced parameter subset *remains* reliable even when very little training data is available (the actual "data-scarce" condition), not just when reduced parameters are tested against a full, data-rich training set.
3. **Uncertainty estimates (via GPR/quantile methods)** attached to every prediction, so "reliable" is answered not just with an average accuracy number but with a statement like *"a 5-parameter model trained on this little data predicts WQI within ±X with Y% confidence"* — which is what a real low-resource monitoring station operator would actually need to trust the output.
4. A final, evidence-based recommendation: **the minimum parameter set (3, 5, or 7) and minimum data volume** at which reduced monitoring stays within an acceptable error/category-accuracy threshold — i.e., a concrete, defensible answer to the problem statement, plus the practical "minimal sensor kit" recommendation for deployment.

---

## 7. Summary Table — Parameters, Role, and Method

Reflects the revised, real-data-driven subsets from Section 3 (real CPCB fill rate shown per parameter — see [DATA_EXPLORATION.md](DATA_EXPLORATION.md)).

| Parameter | Real fill rate | In 3-set? | In 5-set? | In 7-set? | Measurement type | Role in ML pipeline |
|---|---|---|---|---|---|---|
| pH | 98.3% | ✓ | ✓ | ✓ | Lab/probe, fast | Core input, all subsets |
| DO | 90.4% | ✓ | ✓ | ✓ | Sensor, instant | Core input, all subsets |
| BOD | 81.3% | ✓ | ✓ | ✓ | Lab, 5-day | Core input despite being lab-only — best-covered organic-pollution signal in the real data |
| Fecal Coliform | 73.4% | — | ✓ | ✓ | Lab, 24–48h | Pathogen/public-health signal |
| Electrical Conductivity | 52.3% | — | ✓ | ✓ | Sensor, instant | Dissolved-solids proxy (TDS itself too sparse to use directly) |
| Total Coliform | 42.3% | — | — | ✓ | Lab, 24–48h | Broader bacterial contamination signal |
| Turbidity | 31.2% | — | — | ✓ | Sensor, instant | Suspended-sediment/pollution signal |
| Nitrate | 27.4% | — | — | — (full only) | Field kit / lab | Ceiling-only; nutrient-pollution signal |
| Total Phosphate | not in this source | — | — | — (full only) | Lab | Ceiling-only; nutrient signal — must come from a different CPCB feed if used |
| Temperature | ~0% | — | — | — | Sensor, instant | **Excluded** — essentially never recorded in this data source despite being cheap to measure |
| TDS / Total Solids | <5% | — | — | — | Sensor, instant | **Excluded** — too sparse; Conductivity used as proxy instead |
