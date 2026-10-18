# WQI Ground-Truth Calculation

This documents exactly how the ground-truth Water Quality Index is computed from `data/processed/cpcb_river_stations.csv`, and how much real data supports it. This WQI value is the fixed **target label** every ML model (3/5/7/full-parameter) will be trained to predict — see [METHODOLOGY.md](METHODOLOGY.md) §2 for why the target must stay fixed while only the input parameter count changes.

Implementation: `scripts/compute_wqi.py`. Output: `data/processed/cpcb_wqi.csv`.

---

## 1. Method: CPCB/NSF Weighted Arithmetic Water Quality Index

For each parameter *i*:

1. **Sub-index:** `qᵢ` — a 0–100+ score for how far the observed value is from an ideal value, scaled by the gap between the ideal and the regulatory standard (`Sᵢ`). `qᵢ = 0` means ideal; `qᵢ = 100` means exactly at the regulatory limit; `qᵢ > 100` means the limit is exceeded.
2. **Unit weight:** `Wᵢ = K / Sᵢ`, where `K = 1 / Σ(1/Sᵢ)` is a normalizing constant across all parameters in the panel — parameters with stricter (lower) standards get more relative influence.
3. **Final index:** `WQI = Σ(Wᵢ × qᵢ) / Σ(Wᵢ)`.

This is the same standard method described in PROJECT.md §4 — this file fills in the exact numbers used, since "the CPCB/NSF formula" is a family of closely related formulas that differ in their standard values and edge-case handling, and those choices need to be pinned down and documented, not left implicit.

---

## 2. Standard Values Used (Sᵢ) — and where each one comes from

The CPCB National Water Quality Monitoring Programme (the actual source of this project's data) explicitly designates rivers for assessment against its **"Primary Water Quality Criteria for Outdoor Bathing"** (confirmed from the CPCB NWMP data portal itself). That official criteria set covers exactly **4** of our 8 available parameters. The other 4 aren't part of that specific criteria set, so widely-cited secondary standards (BIS drinking-water limits, or the threshold most commonly used for that parameter in published Indian river-WQI literature) are used instead — flagged clearly below rather than presented as if equally official.

| Parameter | Standard (Sᵢ) | Ideal value | Source | Confidence |
|---|---|---|---|---|
| **DO** | 5 mg/L | 14.6 mg/L (saturation at 0°C — the standard reference ideal used across WQI literature) | **CPCB Primary Bathing Water Criteria** (official) | High |
| **BOD** | 3 mg/L | 0 mg/L | **CPCB Primary Bathing Water Criteria** (official) | High |
| **pH** | 6.5–8.5 (asymmetric band around 7.0) | 7.0 (neutral) | **CPCB Primary Bathing Water Criteria** (official) | High |
| **Fecal Coliform** | 500 MPN/100mL | 0 | **CPCB Primary Bathing Water Criteria** (official, "desirable" tier) | High |
| Total Coliform | 5000 MPN/100mL | 0 | Commonly used secondary threshold in Indian river-WQI literature (not part of the 4-parameter bathing criteria) | Medium |
| Turbidity | 10 NTU | 0 NTU | Commonly used surface-water threshold in river-WQI literature (BIS IS 10500's 1–5 NTU is a *drinking-water* limit, too strict for a river) | Medium |
| Nitrate (as N) | ≈10.2 mg-N/L | 0 | Derived from BIS drinking-water limit of 45 mg/L as NO₃⁻, converted to mg-N/L (×14/62 ≈ 0.226) since the raw CPCB column is `Nitrate N (mgN/L)`, not `Nitrate (mg/L)` | Medium |
| Electrical Conductivity | 1000 µS/cm | 0 µS/cm | Commonly used freshwater threshold in Indian river-WQI literature — **the least standardized of the 8**; no single official CPCB/BIS "safe EC for rivers" figure exists the way it does for DO/BOD/pH | Lower |

**This matters for interpretation:** the ground-truth WQI computed here is *not* a single universally-agreed number — it depends on these standard-value choices, same as every published WQI study. The 4 CPCB-official parameters (DO, BOD, pH, Fecal Coliform) carry high confidence; Total Coliform/Turbidity/Nitrate are medium-confidence commonly-used values; EC is the weakest link. If results are later found sensitive to the EC standard specifically, that's worth flagging rather than treating the WQI as ground truth beyond dispute.

---

## 3. Sub-Index Formulas

Three different shapes are needed depending on which direction "bad" is for that parameter.

**"More is worse" parameters** (BOD, Total Coliform, Fecal Coliform, Turbidity, Nitrate-N, EC) — linear from the ideal (0) to the standard:

```
qᵢ = (observed value / Sᵢ) × 100
```

**DO — "more is better"** (inverted, since low DO is what indicates pollution):

```
qDO = [(14.6 − observed DO) / (14.6 − 5)] × 100
```
Clipped at 0 if observed DO exceeds 14.6 (supersaturation is treated as "as good as ideal," not "better than ideal").

**pH — deviation from neutral, asymmetric tolerance** (CPCB's own band is 6.5–8.5, not symmetric around 7.0):

```
if observed pH ≥ 7.0:  qpH = [(observed pH − 7.0) / (8.5 − 7.0)] × 100
if observed pH <  7.0:  qpH = [(7.0 − observed pH) / (7.0 − 6.5)] × 100
```

All sub-indices are floored at 0 (a value better than ideal is still "0 = ideal," not negative).

---

## 4. Classification Scale

Standard CPCB/Brown WQI category bands, applied to the final score:

| WQI range | Category |
|---|---|
| 0 – 25 | Excellent |
| 26 – 50 | Good |
| 51 – 75 | Poor |
| 76 – 100 | Very Poor |
| > 100 | Unsuitable |

This is the label used for the **WQI-category accuracy** metric in METHODOLOGY.md §6.

---

## 5. What "Ground Truth" Actually Means Here — Two WQI Columns, Not One

Real CPCB monitoring visits rarely report all 8 parameters at once (see DATA_EXPLORATION.md's fill-rate findings). Rather than quietly averaging over whatever happens to be present each time — which would make the target label mean something slightly different from row to row — **two separate columns are computed**, with only one of them usable as the ML target:

- **`WQI_full`** — computed **only** on rows where all 8 parameters are simultaneously present, using the fixed weights above. **This is the ML ground-truth target.** Every 3/5/7-parameter model is trained to predict this same number from a subset of its inputs.
- **`WQI_partial`** — computed on every row that has *at least one* usable parameter, renormalizing the weights over whichever parameters that row actually has. This is descriptive only (useful for overall river/state quality summaries) and must **never** be used as a training target, since two `WQI_partial` values aren't computed the same way and aren't safely comparable to each other.

Rows flagged `HasSuspectReading` (see DATA_EXPLORATION.md §6) are excluded from both.

### Real achieved sample sizes (river stations, suspect rows excluded, 32,968 total)

| Requirement | Rows | % of river data |
|---|---|---|
| Has pH, DO, BOD (3-param) | 24,993 | 75.8% |
| Has pH, DO, BOD, Fecal Coliform, EC (5-param) | 5,961 | 18.1% |
| Has pH, DO, BOD, Fecal Coliform, EC, Total Coliform, Turbidity (7-param) | 5,256 | 15.9% |
| **Has all 8 → `WQI_full` computable** | **4,861** | **14.7%** |

This drop-off — 75.8% of visits report enough for a 3-parameter reading, but only 14.7% report enough for the full picture — **is itself direct, real evidence for the project's premise**, not a simulated stand-in for it: most real river monitoring in this dataset is already operating in a reduced-parameter regime whether by design or by gap, and a model that can predict the full WQI from just those 3 commonly-reported parameters would fill a real, existing gap in ~61% of visits (75.8% − 14.7%) that currently get no full WQI at all.

---

## 6. How This Feeds the ML Pipeline

1. `WQI_full_capped` (see Section 7 — not `WQI_full`) on the 4,861 fully-observed rows becomes the **training/testing target**.
2. For each experiment, only the 3, 5, 7, or 8 input columns for that subset are exposed to the model — **but the target is always the same column from the same 4,861-row set**, never a separately-computed reduced-parameter WQI. This is what makes the comparison across subset sizes fair (METHODOLOGY.md §2).
3. `WQI_partial` (larger row count, ~32,531 rows with at least one usable parameter) can be used later for descriptive analysis (e.g., river/state-level average quality trends) but is explicitly out of scope for model training/evaluation.

---

## 7. A Real Problem Found Running This on Real Data — and the Fix

Running the formula in Sections 1–3 as literally written on the actual 4,861 fully-observed rows produced a **heavily right-skewed, outlier-dominated distribution**: mean 108, median 65, but a max of **3,007** — over 100x a typical value.

This is not a data error (those were already excluded via `HasSuspectReading`). It's a **real methodological gap in the plain linear sub-index formula** (`qᵢ = observed/Sᵢ × 100`) when a parameter's true value can legitimately run to many multiples of its standard:

- **`MAHI AT MUJPUR`, 2020-07-03, WQI = 3,007:** Turbidity = 3,640 NTU (vs. standard 10) during what is almost certainly a monsoon flash-flood silt event. `qTurbidity = 36,400`. Even at Turbidity's modest weight (~0.081), that single parameter contributes ~2,948 points to the index by itself.
- **`GANGA AT U/S MUNGER`, 2020-05-01, WQI = 2,716:** BOD = 294 mg/L (vs. standard 3) — genuine severe organic pollution, likely near a sewage inflow. `qBOD = 9,800`, contributing ~2,646 points at BOD's ~0.27 weight.

Both readings are plausible real events, not entry errors — but a linear, uncapped sub-index treats "300x over the limit" as 3x worse than "100x over the limit," when in practical/decision terms both are simply **"catastrophically polluted, unfit for any use"** and shouldn't be weighted 3x apart. Left uncapped, this also would have been disastrous for model training specifically: a regression loss (MSE) would be dominated by getting these ~100 extreme rows' exact value right, at the expense of learning the actual decision-relevant 0–150 range where 97.6% of the data (4,746 of 4,861 rows) actually lives (only 115 rows exceed WQI=500).

**Fix applied (standard practice in WQI literature for exactly this reason):** each sub-index `qᵢ` is capped at 100 *before* weighting — i.e. `qᵢ = min(qᵢ, 100)`. Beyond the regulatory standard, a parameter is already known to be a violation; the fix stops treating further exceedance as proportionally more informative. This produces a second column:

**`WQI_full_capped`** — same formula, weights, and standards as `WQI_full`, but with every `qᵢ` clipped to [0, 100] first. **This is the recommended ML regression target**, not `WQI_full`.

### Real distribution, before vs. after the fix (n = 4,861)

| | `WQI_full` (uncapped) | `WQI_full_capped` (recommended) |
|---|---|---|
| Mean | 108.4 | 56.1 |
| Median | 64.9 | 55.8 |
| Std dev | 174.6 | 14.1 |
| Max | 3,006.9 | 92.6 |
| Category spread | Excellent 48 / Good 1,153 / Poor 1,741 / Very Poor 676 / **Unsuitable 1,243** | Excellent 61 / Good 1,532 / Poor 2,823 / Very Poor 445 / **Unsuitable 0** |

**One consequence worth flagging explicitly so it isn't later mistaken for a bug:** because `WQI_full_capped` is a weighted average of values each ≤ 100 (and the weights sum to 1), it can **never exceed 100** — so the "Unsuitable" category (defined as >100) is structurally unreachable under the capped version. This is expected, not an error: it means the capped scale's practical ceiling is "Very Poor," and any row that would have been "Unsuitable" under the uncapped formula shows up as a high-end "Very Poor" (75–100) instead. `WQI_full` (uncapped) remains in the output for anyone who specifically wants to compare against literature that reports WQI > 100, or who wants to identify the small number of truly extreme-pollution rows (115 rows > 500) as a separate analysis, e.g. flagging catastrophic-pollution events. It should not be used as the regression target.
