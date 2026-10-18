# CPCB Data Acquisition & Exploration — Findings Log

This documents what was actually downloaded from the **real CPCB data on the National Water Data Portal (nwdp.nwic.gov.in)**, what it actually contains, and — critically — how the real numbers change some assumptions made in [METHODOLOGY.md](METHODOLOGY.md) before any real data had been inspected. Data lives in `data/raw/{physical,chemical,biological}/`.

---

## 1. What Was Downloaded

Source: National Water Data Portal (run by the National Water Informatics Centre, under the same government umbrella as CPCB), the three "Surface Water Quality (Manual)" datasets referenced in [DATASETS.md](DATASETS.md).

Each dataset is split per state/UT × time-bucket (`1961_2020`, `2021_2025`, `2026_2030`). The `2026_2030` files were checked and are **empty placeholders** (header row only — that period hasn't happened yet) and were skipped. Everything else was downloaded in full:

| File group | Files | Total rows | Size |
|---|---|---|---|
| **Physical** (EC, Colour, Odour, Turbidity, Temperature, Total Solids) | 70 | 94,159 | 15 MB |
| **Chemical** (pH, DO, TDS, Nitrate, and 20+ others incl. heavy metals) | 71 | 109,683 | 27 MB |
| **Biological** (BOD, COD, Fecal Coliform, Total Coliform) | 70 | 107,537 | 16 MB |

Coverage: **36 states/UTs** (28 states + 8 UTs), **~4,000 unique monitoring stations**. This confirms the scale claimed in DATASETS.md.

**Correction:** the `1961_2020` bucket name is a nominal label on the portal, not the actual data range — the real `Data Acquisition Time` values inside every file only start at **2018-01-01** and run through **2024-07-01** (verified after parsing dates in the cleaning script, Section 6). No pre-2018 records exist in what was downloaded, despite the filename. Treat any "since 1961" framing in earlier notes as wrong.

---

## 2. Finding #1 — The "River" field is essentially unusable for filtering to rivers only

The dataset's structured `River` column is populated for only **92 of 109,683 rows (0.08%)**, covering just 11 named rivers (mostly Meghalaya/Assam basin rivers — Brahmaputra, Kopili, Simsang, etc.). For the other 99.9% of rows, the actual river/lake/tank identity is embedded only in the free-text `Station` name (e.g., `"YAMUNA AT VISHRAMGHAT MATHURA"`), while `River`, `Basin`, `Tributary`, and `Local River` are all `"-"`.

**Implication:** the dataset mixes rivers, lakes, tanks, reservoirs, and canals under one "Surface Water Quality" umbrella (consistent with CPCB's stated 4,484-location network). Restricting the project to *river* systems requires **text-matching station names against a known river-name list** (Yamuna, Ganga, Godavari, Krishna, Kaveri, etc.), not filtering on the `River` field. This is a data-cleaning step to add before anything else.

---

## 3. Finding #2 — Real parameter fill-rates completely reorder which parameters are "cheap and available"

This is the most important finding, because METHODOLOGY.md's hypothesized 3/5/7-parameter sets were built on the *general* assumption that sensor-based physical parameters (pH, DO, Temperature, Conductivity, Turbidity) are the easiest to get. **In this real dataset, that assumption is wrong for Temperature specifically, and only partly true for the others:**

| Parameter | File | Non-empty rows | **Fill rate** |
|---|---|---|---|
| **pH** | Chemical | 107,789 / 109,683 | **98.3%** |
| **Dissolved Oxygen (DO)** | Chemical | 99,204 / 109,683 | **90.4%** |
| **BOD** | Biological | 87,428 / 107,537 | **81.3%** |
| **Fecal Coliform** | Biological | 78,937 / 107,537 | **73.4%** |
| **Electrical Conductivity** | Physical | 49,241 / 94,159 | **52.3%** |
| **Total Coliform** | Biological | 45,440 / 107,537 | **42.3%** |
| **Turbidity** | Physical | 29,358 / 94,159 | **31.2%** |
| **Nitrate N** | Chemical | 30,074 / 109,683 | **27.4%** |
| Total Dissolved Solids | Chemical | 5,224 / 109,683 | 4.8% |
| Total Solids | Physical | 1,801 / 94,159 | 1.9% |
| Colour | Physical | 5,822 / 94,159 | 6.2% |
| **Temperature** | Physical | 0 / 94,159 | **~0%** |
| Odour | Physical | 481 / 94,159 | 0.5% |
| Chemical Oxygen Demand (COD) | Biological | 0 / 107,537 | 0% |

**Temperature — hypothesized as a core member of the 5- and 7-parameter sets in METHODOLOGY.md — is recorded in essentially zero real rows.** COD is likewise never recorded in this feed. TDS and Total Solids, despite being cheap sensor readings in principle, are barely ever logged (under 5%) — Electrical Conductivity is the usable stand-in for dissolved-solids information instead.

This flips the intuition that "sensor-measurable = well-recorded": pH, DO (both chemical-lab-recorded here, but simple/fast tests) and even BOD (a genuinely slow lab test) are far more consistently reported than several of the parameters assumed to be the easy/cheap ones. The takeaway is that **parameter selection must be anchored to actual historical reporting frequency, not just theoretical measurement cost** — a sensor kit is only as useful for training data as what stations have actually been logging.

### Revised parameter subsets (supersedes the hypothesis table in METHODOLOGY.md §3)

| Set | Parameters | Basis |
|---|---|---|
| **3-parameter** | pH, DO, BOD | The three best-covered parameters overall (98%, 90%, 81%); also the three heaviest-weighted terms in most WQI formulas |
| **5-parameter** | pH, DO, BOD, Fecal Coliform, Electrical Conductivity | Adds the pathogen/public-health signal and the best-covered physical parameter |
| **7-parameter** | pH, DO, BOD, Fecal Coliform, Electrical Conductivity, Total Coliform, Turbidity | Adds full coliform coverage and a suspended-solids indicator |
| Dropped from consideration (too sparse to train on reliably) | Temperature, Total Dissolved Solids, Total Solids, Colour, Odour, COD | All under ~6% fill rate; not viable as model inputs without a dedicated imputation strategy that itself would need validating |

This is still a first-pass ranking by raw availability — the correlation/feature-importance analysis in METHODOLOGY.md §3 (Pass 1) still needs to run on the joined, cleaned dataset once WQI ground truth is computed, since a parameter can be well-recorded but weakly predictive, or sparsely recorded but highly predictive when present. Availability sets the *ceiling* on what's practically trainable; importance analysis decides what's used within that ceiling.

---

## 4. Finding #3 — Physical, Chemical, and Biological files are NOT always row-aligned; a join key is required

For the older period (**1961–2020**), the three files match exactly row-for-row per state (e.g., Uttar Pradesh: 3,602 rows in all three) — they represent the same sampling visits.

For the recent period (**2021–2025**), row counts diverge per file within the same state — e.g., Andhra Pradesh: 1,393 physical rows vs. 1,829 chemical vs. 1,811 biological; Uttar Pradesh: 400 physical vs. 1,456 chemical vs. 1,414 biological. **Physical readings are being logged far less often than chemical/biological ones in recent years.**

**Implication:** rows must be joined on `(Station, Data Acquisition Time)`, not concatenated positionally. A spot check also found a small number of duplicate `(Station, Date)` key pairs within a single file (21 duplicates in one 1,829-row chemical file) — likely same-day repeat readings — so the join logic needs a dedup/aggregation rule (e.g., average same-day duplicates) before merging.

---

## 5. Unified Dataset Built (Cleaning + Join Script)

`scripts/build_dataset.py` implements the join described in Section 4: it loads all 211 raw files, parses `Data Acquisition Time` into a real date, deduplicates repeat same-day readings per station (averaging numeric values), and outer-joins Physical + Chemical + Biological on `(Station, State, District, Latitude, Longitude, Date)`. It carries forward only the 8 parameters worth using per the fill-rate findings above (EC, Turbidity, pH, DO, Nitrate N, BOD, Fecal Coliform, Total Coliform) rather than the sparse/unusable ones.

**Outputs** (in `data/processed/`):

| File | Rows | Stations | Notes |
|---|---|---|---|
| `cpcb_unified.csv` | 109,422 | 4,017 | All stations — rivers, lakes, tanks, reservoirs, wells combined |
| `cpcb_river_stations.csv` | 32,971 | 888 | Subset matched to a known river name — **87 distinct rivers** identified |

River matching used the structured `River` column where populated, falling back to a regex word-match of ~95 known Indian river names against the free-text `Station` field (see Finding #1). This lifted usable river coverage from 0.08% of rows to **30.1%** — a large recovery, though the river-name list is a manually compiled working set, not an exhaustive official gazetteer, so some real river stations with obscure/local river names are still being missed and classified as "not a river."

**A real false positive was found and fixed during this step:** a handful of *groundwater* stations (borewells, hand pumps, dug wells) got matched as river stations because their names happened to contain a river name incidentally — e.g. `"BOREWELL KRISHNA MURTHY D.NO. 48-16-43 AUTONAGAR VIJJAYAWADA"` matched "KRISHNA" (a person's name, not the river) purely because the word-boundary regex doesn't understand context. 38 of the initial 33,015 matched rows were like this. A second pass (during the audit in Section 7) found one more: `"GROUND WATER NEAR TAP WATER IN CAMPUS OF KALI ASTHAN BEGUSARAI"` matched "KALI" via a temple/place name, not the river. The script now excludes any station whose name contains a groundwater-source keyword (`BOREWELL`, `HAND PUMP`, `TUBE WELL`, `DUG WELL`, `GROUND WATER`, `OPEN WELL`, `PIEZOMETER`, etc.) from river classification regardless of a name match, dropping the false positives to (as far as spot-checking can confirm) zero. This is a good illustration of why naive keyword matching on free text needs more than one review pass, not just a regex and a good-looking match count.

Fill rates on the **river-only** subset (32,971 rows) turned out close to the unified-table rates, with two parameters slightly *better* covered on rivers specifically — Fecal Coliform 84.3% (vs. 67.3% overall) and BOD 78.1% (vs. 77.0%) — while EC and Total Coliform are somewhat *worse* covered on rivers (25.8% and 24.9% vs. 44.0% and 38.2% overall). This makes sense: EC/Total Coliform readings are more often logged for lakes/tanks/reservoirs in this data than for flowing river stretches. **This is a second reason the revised 3/5/7 parameter sets in METHODOLOGY.md should be re-checked once analysis is restricted to `cpcb_river_stations.csv` only** — fill rates computed on the full unified table (rivers + lakes + wells mixed) are not identical to fill rates on rivers alone, and rivers-only is the actual project scope.

Top rivers by row count: Ganga (5,775), Narmada (2,247), Cauvery (2,035), Satluj (1,928), Godavari (1,809), Yamuna (1,561), Beas (1,558), Krishna (1,399) — a reasonable spread across major Indian river systems, not dominated by just one or two rivers.

**One more data-quality issue found while auditing file listings:** `data/raw/chemical/swq_manual_biological_parameters_cwc_ml_2021_2025.csv` — a 92-row Meghalaya file sourced from **CWC** (Central Water Commission), not CPCB — is filed under the "chemical" dataset category on the portal but actually contains BOD/COD/Coliform (biological-schema) columns, not pH/DO/Nitrate. This explains the 92 structured-`River`-field rows from Finding #1 (Simsang, Kopili, Brahmaputra, etc. — all Meghalaya/Assam rivers): they all come from this one misplaced file. Because `build_dataset.py`'s chemical loader only looks for chemical-schema columns, **these 92 rows' real BOD/Coliform values are currently silently dropped** (the rows survive with metadata only, no parameter values, via `pd.concat`'s automatic column-union behavior — no crash, just quiet data loss). Small in scale (92 of 109,422 rows) but worth a fix: either route CWC-agency files through the biological loader too, or merge this file's values into the biological table directly.

---

## 6. Full Pipeline Audit (2026-09-10)

A systematic audit of `build_dataset.py` and its output, done specifically to catch anything wrong before ground-truth WQI gets computed on top of this table. Checked: exact-duplicate rows, join-key correctness, river-match false positives, numeric plausibility ranges, and coordinate sanity.

**No bugs found in:**
- Exact duplicate rows in the unified table — zero.
- Coordinate sanity — all 109,422 rows fall inside India's real lat/lon bounds (8.3°–34.4°N, 69.7°–96.2°E).
- The join logic itself — verified the `(Station, State, District, Lat, Lon, Date)` key does not silently drop or duplicate rows.

**One non-bug investigated and cleared:** 14 stations (e.g. "DERA BASSI PUNJAB") have two slightly different Lat/Lon pairs under the same display name. Checked whether this was the join key fragmenting a single real visit into two incomplete rows — it isn't. Both coordinate variants independently carry their own complete-or-incomplete parameter readings across physical/chemical/biological, meaning these are genuinely two closely-spaced monitoring points sharing a name (e.g. two sampling points near a bridge), not a pipeline artifact. No data is being lost; the only effect is a very slightly inflated "unique station" count (~0.35%).

**Two real bugs found and fixed:**

1. **A second river-name false positive**, same family as the borewell one: `"GROUND WATER NEAR TAP WATER IN CAMPUS OF KALI ASTHAN BEGUSARAI"` (Bihar) was classified as a "Kali river" station — "Kali Asthan" is a temple/place name, and the station is explicitly groundwater. Fixed by extending `GROUNDWATER_PATTERN` to also catch `GROUND WATER`, `OPEN WELL`, `PIEZOMETER`, and `INFILTRATION GALLERY`. Confirmed clean afterward: 0 remaining groundwater-labeled stations in `cpcb_river_stations.csv`.

2. **Physically implausible readings with no flag.** Numeric range-checking the unified table surfaced real data-entry errors concentrated in a handful of stations — e.g. one Bengaluru lake ("Ramammana Kere") logged **pH 78.2** (scale max is 14), **EC of 25.4 million µS/cm** (seawater is ~50,000), and **Total Coliform of 54 billion MPN/100mL** on the same visit; a Chhattisgarh groundwater station logged EC over 400,000 µS/cm on four separate dates. These would silently corrupt any WQI computed on top of them. **Fix:** `build_dataset.py` now adds a `<Param>_Suspect` boolean column per parameter (flagging values outside a generous physically-plausible range — e.g. pH outside [0,14], EC above 100,000 µS/cm, coliform above 10⁸ MPN/100mL) plus a combined `HasSuspectReading` column. Values are **flagged, not deleted or altered** — a downstream WQI/ML step can decide whether to exclude them. Result: 66 of 109,422 unified rows (0.06%) are flagged, and only **3 of 32,971 river-station rows (0.01%)** — most of the offending stations (lakes, groundwater wells) were already outside river scope anyway.

Full before/after re-run confirms both fixes: river subset is now 32,971 rows / 888 stations (was 32,977 / 889 — one groundwater station correctly dropped), fill rates unchanged to one decimal place.

---

## 7. What This Means for Next Steps

1. ~~Build the cleaning script~~ — **done** (`scripts/build_dataset.py`, Section 5).
2. ~~Audit the pipeline for bugs~~ — **done** (Section 6). Two real fixes applied; one suspected issue (duplicate coordinates) investigated and cleared as harmless.
3. Compute ground-truth WQI only on rows where the required parameters for whichever formula variant is used are actually present, **excluding rows where `HasSuspectReading` is True** — given the fill rates above, the **full 9-parameter WQI can only be computed for a small minority of rows**, which itself is a live illustration of the project's "data-scarce monitoring" premise, not just a simulated one.
4. Re-run the correlation/importance analysis (METHODOLOGY.md §3) on `cpcb_river_stations.csv` specifically (not the full unified table) to confirm or adjust the revised 3/5/7 sets, per the river-vs-overall fill-rate gap noted in Section 5.
5. Treat "sparse/rarely-recorded parameters" (Temperature, TDS, COD, etc.) as a documented limitation of this specific data source rather than assuming they can be added back in later — if they're wanted, they'd have to come from a different source (e.g., the CPCB RTWQMS real-time sensors, which do log temperature every 15 minutes at 36 Ganga stations).
6. Expand the manually-compiled river-name list in `build_dataset.py` as unmatched-but-plausible river stations are spotted during EDA — 30.1% match rate is a floor, not a ceiling.
7. Fix the misplaced CWC Meghalaya file (92 rows currently losing their real BOD/Coliform values, see Section 5) — low priority given its small size, but a quick, correct fix.

---

## 8. Findings from the modelling stage (2026-10-18)

Two more data-quality properties surfaced while deploying the models (full detail in the report, §3.3 and §6.9):

1. **The full 8-parameter panel exists for 2020 only.** For river stations, EC, Total Coliform, Turbidity and Nitrate-N are 80–93% filled in 2020 but 0–4% filled in 2018, 2019 and 2021. Every `WQI_full` row is therefore from 2020; other years carry a routine pH–DO–BOD–Fecal Coliform panel. (The pooled fill rates in §3 hid this.)
2. **BOD reporting floor outside 2020.** In 2018, 2019 and 2021 no river visit has BOD ≤ 1 mg/L, against 22% of visits in 2020, and 26–28% of biological rows have a *blank* BOD (4% in 2020). Low, probably below-detection-limit, BOD values appear to have been left blank in those years. This removes the cleanest visits from those years and biases naive year-to-year WQI comparisons upward. A censored-data treatment would fix it; it is not applied yet.
3. **Colour words in the BOD column.** About 3,000 rows of the 2020 biological files contain colour descriptors ("Clear", "Light Brown", "Turbid Green", …) in the BOD field, which points to a column misalignment in some source files. These rows become NaN on parsing and none of them are in the labelled set, so results are unaffected, but the affected files deserve a closer look.
