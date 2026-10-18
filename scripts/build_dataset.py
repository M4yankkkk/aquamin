"""
Clean, join, and river-filter the raw CPCB Surface Water Quality data
(Physical + Chemical + Biological) downloaded from the National Water
Data Portal into one unified table for WQI ground-truth computation.

Input:  data/raw/{physical,chemical,biological}/*.csv
Output: data/processed/cpcb_unified.csv        (all stations, all params)
        data/processed/cpcb_river_stations.csv (subset matched to a known river)

See DATA_EXPLORATION.md for the findings that shaped the decisions here
(unreliable "River" column, need for a station/date join key, dedup need,
and which parameters are even worth carrying through).
"""

import glob
import re
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

# Columns present identically in every raw file, used as join/identity keys.
META_COLS = ["Station", "Agency", "State", "District", "River", "Latitude", "Longitude"]
DATE_COL = "Data Acquisition Time"
JOIN_KEYS = ["Station", "State", "District", "Latitude", "Longitude", "Date"]

# Renaming only the parameters actually worth carrying forward (see
# DATA_EXPLORATION.md fill-rate table). Sparse/unusable columns
# (Temperature, TDS, Total Solids, Colour, Odour, COD) are intentionally
# dropped rather than carried through as all-NaN columns.
PHYSICAL_PARAMS = {
    "Electric Conductivity (μS/cm)": "EC",
    "Turbidity (NTU)": "Turbidity",
}
CHEMICAL_PARAMS = {
    "Potential of Hydrogen (pH)": "pH",
    "Dissolved oxygen (mg/L)": "DO",
    "Nitrate N (mgN/L)": "NitrateN",
}
BIOLOGICAL_PARAMS = {
    "Biochemical Oxygen Demand (mg/L)": "BOD",
    "Fecal Coliform (MPN/100mL)": "FecalColiform",
    "Total Coliform (MPN/100mL)": "TotalColiform",
}

# A working list of Indian river names for matching against free-text
# station names, since the raw "River" column is populated for <0.1% of
# rows (see DATA_EXPLORATION.md Finding #1). Not exhaustive — extend as
# unmatched-but-plausible stations are found during EDA.
INDIAN_RIVERS = [
    "GANGA", "GANGES", "YAMUNA", "BRAHMAPUTRA", "GODAVARI", "KRISHNA",
    "KAVERI", "CAUVERY", "NARMADA", "NARBADA", "TAPI", "TAPTI", "MAHANADI",
    "INDUS", "SUTLEJ", "SATLUJ", "BEAS", "RAVI", "CHENAB", "JHELUM",
    "GOMTI", "GHAGHARA", "GANDAK", "KOSI", "SON", "BETWA", "CHAMBAL",
    "SABARMATI", "MAHI", "TUNGABHADRA", "BHIMA", "PERIYAR", "VAIGAI",
    "TAMIRAPARNI", "PENNAR", "PENNER", "DAMODAR", "SUBARNAREKHA",
    "BRAHMANI", "BAITARANI", "LUNI", "KALI", "SHARAVATHI", "NETRAVATI",
    "HOOGHLY", "HUGLI", "TEESTA", "TISTA", "TORSA", "BARAK", "KOPILI",
    "MANAS", "DIBANG", "LOHIT", "SUBANSIRI", "RAMGANGA", "SHARDA",
    "RAPTI", "BURHI GANDAK", "AJAY", "MAYURAKSHI", "RUPNARAYAN",
    "BHAGIRATHI", "ALAKNANDA", "MANDAKINI", "PINDAR", "DHAULIGANGA",
    "ZUARI", "MANDOVI", "SHARAVATI", "KUNDALIKA", "ULHAS", "VAITARNA",
    "PANCHGANGA", "GHATAPRABHA", "MALAPRABHA", "HEMAVATI", "KABINI",
    "MOYAR", "BHAVANI", "NOYYAL", "PALAR", "PONNAIYAR", "VELLAR",
    "MUSI", "MANJIRA", "WAINGANGA", "WARDHA", "PURNA", "PENGANGA",
    "INDRAVATI", "SABARI", "SILERU", "SARDA", "BANAS", "MAHANANDA",
    "KAMENG", "SIANG", "DIHANG",
]
# Physically plausible ranges per parameter, used only to FLAG (never
# silently drop or alter) implausible readings before any WQI/ML step
# consumes this table. Bounds are deliberately generous — e.g. pH's max
# of 14 is a hard chemical limit, but EC/coliform ceilings are set well
# above genuine extreme-pollution readings so real (if shocking) values
# aren't flagged as errors. Found by auditing real output: e.g. a
# Bengaluru lake reading pH 78.2 and EC of 25 million uS/cm (seawater is
# ~50,000) on the same visit — a data-entry error, not real water.
PLAUSIBLE_RANGE = {
    "pH": (0, 14),
    "DO": (0, 25),
    "BOD": (0, 1000),
    "EC": (0, 100_000),
    "Turbidity": (0, 5000),
    "NitrateN": (0, 500),
    "FecalColiform": (0, 100_000_000),
    "TotalColiform": (0, 100_000_000),
}

RIVER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(r) for r in INDIAN_RIVERS) + r")\b",
    flags=re.IGNORECASE,
)

# Station names that are actually groundwater sources (borewells, hand
# pumps, dug wells, etc.) sometimes contain a river name incidentally
# (a person's name, a district named after the river, or genuinely being
# "near" the river) and must NOT be classified as river surface-water
# stations regardless of a name match. Found by inspecting real matches,
# e.g. "BOREWELL KRISHNA MURTHY ... VIJJAYAWADA" matching "KRISHNA".
GROUNDWATER_PATTERN = re.compile(
    r"BOREWELL|BORE\s*WELL|BOREHOLE|HAND\s*PUMP|HANDPUMP|TUBE\s*WELL|TUBEWELL"
    r"|DUG\s*WELL|GROUND\s*WATER|OPEN\s*WELL|PIEZOMETER|INFILTRATION\s*GALLERY",
    flags=re.IGNORECASE,
)


def load_and_clean(folder: str, param_map: dict) -> pd.DataFrame:
    files = sorted(glob.glob(str(RAW / folder / "*.csv")))
    frames = []
    for fp in files:
        df = pd.read_csv(fp, dtype=str, keep_default_na=False, na_values=["", "-", '""'])
        frames.append(df)
    raw = pd.concat(frames, ignore_index=True)

    keep_cols = META_COLS + [DATE_COL] + list(param_map.keys())
    raw = raw[[c for c in keep_cols if c in raw.columns]].copy()
    raw = raw.rename(columns=param_map)

    raw["Date"] = pd.to_datetime(raw[DATE_COL], format="%d-%m-%Y %H:%M", errors="coerce").dt.date
    raw = raw.drop(columns=[DATE_COL])

    for col in param_map.values():
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    raw["Latitude"] = pd.to_numeric(raw["Latitude"], errors="coerce")
    raw["Longitude"] = pd.to_numeric(raw["Longitude"], errors="coerce")

    raw = raw.dropna(subset=["Station", "Date"])

    # Dedup same (station, date) repeat readings by averaging numeric params;
    # metadata + free-text River field just take the first value.
    agg = {c: "mean" for c in param_map.values()}
    agg.update({c: "first" for c in ["Agency", "River"] if c in raw.columns})
    grouped = raw.groupby(JOIN_KEYS, as_index=False, dropna=False).agg(agg)
    return grouped


def main():
    print("Loading and cleaning PHYSICAL...")
    physical = load_and_clean("physical", PHYSICAL_PARAMS)
    print(f"  -> {len(physical):,} deduped (station,date) rows")

    print("Loading and cleaning CHEMICAL...")
    chemical = load_and_clean("chemical", CHEMICAL_PARAMS)
    print(f"  -> {len(chemical):,} deduped (station,date) rows")

    print("Loading and cleaning BIOLOGICAL...")
    biological = load_and_clean("biological", BIOLOGICAL_PARAMS)
    print(f"  -> {len(biological):,} deduped (station,date) rows")

    print("Joining on (Station, State, District, Latitude, Longitude, Date)...")
    merged = pd.merge(
        physical, chemical, on=JOIN_KEYS, how="outer", suffixes=("_phys", "_chem")
    )
    # Resolve River/Agency duplicated by the merge (keep whichever side has it)
    for col in ["River", "Agency"]:
        left, right = f"{col}_phys", f"{col}_chem"
        if left in merged.columns and right in merged.columns:
            merged[col] = merged[left].combine_first(merged[right])
            merged = merged.drop(columns=[left, right])

    merged = pd.merge(
        merged, biological, on=JOIN_KEYS, how="outer", suffixes=("", "_bio")
    )
    for col in ["River", "Agency"]:
        alt = f"{col}_bio"
        if alt in merged.columns:
            merged[col] = merged[col].combine_first(merged[alt]) if col in merged.columns else merged[alt]
            merged = merged.drop(columns=[alt])

    print(f"Unified table: {len(merged):,} rows, {merged['Station'].nunique():,} unique stations")

    merged["Year"] = pd.to_datetime(merged["Date"]).dt.year
    merged["Month"] = pd.to_datetime(merged["Date"]).dt.month

    # River matching: trust the structured "River" column when populated,
    # otherwise fall back to regex matching the station name.
    has_structured_river = merged["River"].notna() & (merged["River"].astype(str).str.strip() != "")
    name_match = merged["Station"].astype(str).str.extract(RIVER_PATTERN, expand=False)
    merged["MatchedRiver"] = np.where(
        has_structured_river, merged["River"], name_match.str.upper()
    )
    is_groundwater = merged["Station"].astype(str).str.contains(GROUNDWATER_PATTERN, na=False)
    merged.loc[is_groundwater, "MatchedRiver"] = np.nan
    merged["IsRiverStation"] = merged["MatchedRiver"].notna()

    param_cols = list(PHYSICAL_PARAMS.values()) + list(CHEMICAL_PARAMS.values()) + list(BIOLOGICAL_PARAMS.values())

    # Flag (do not drop/alter) physically implausible readings so a later
    # WQI/ML step can decide to exclude them rather than silently trusting
    # a value like pH 78.2.
    suspect_any = pd.Series(False, index=merged.index)
    for col, (lo, hi) in PLAUSIBLE_RANGE.items():
        if col in merged.columns:
            out_of_range = (merged[col] < lo) | (merged[col] > hi)
            merged[f"{col}_Suspect"] = out_of_range.fillna(False)
            suspect_any |= merged[f"{col}_Suspect"]
    merged["HasSuspectReading"] = suspect_any

    suspect_cols = [f"{c}_Suspect" for c in PLAUSIBLE_RANGE if f"{c}_Suspect" in merged.columns]
    ordered_cols = [
        "Station", "Agency", "State", "District", "Latitude", "Longitude",
        "Date", "Year", "Month", "River", "MatchedRiver", "IsRiverStation",
    ] + param_cols + suspect_cols + ["HasSuspectReading"]
    merged = merged[[c for c in ordered_cols if c in merged.columns]]
    merged = merged.sort_values(["State", "Station", "Date"]).reset_index(drop=True)

    out_all = PROCESSED / "cpcb_unified.csv"
    merged.to_csv(out_all, index=False)
    print(f"\nSaved unified table -> {out_all} ({len(merged):,} rows)")

    river_df = merged[merged["IsRiverStation"]].reset_index(drop=True)
    out_river = PROCESSED / "cpcb_river_stations.csv"
    river_df.to_csv(out_river, index=False)
    print(f"Saved river-only subset -> {out_river} ({len(river_df):,} rows, "
          f"{river_df['Station'].nunique():,} unique stations, "
          f"{river_df['MatchedRiver'].nunique():,} distinct rivers)")

    print("\n=== Fill rate on UNIFIED table ===")
    for col in param_cols:
        n = merged[col].notna().sum()
        print(f"  {col}: {n:,} / {len(merged):,} ({100*n/len(merged):.1f}%)")

    print("\n=== Fill rate on RIVER-ONLY subset ===")
    for col in param_cols:
        n = river_df[col].notna().sum()
        pct = 100 * n / len(river_df) if len(river_df) else 0
        print(f"  {col}: {n:,} / {len(river_df):,} ({pct:.1f}%)")

    print(f"\nDate range: {merged['Date'].min()} to {merged['Date'].max()}")
    print(f"River match rate overall: {merged['IsRiverStation'].mean()*100:.1f}% of rows")
    print("\nTop 20 matched rivers by row count:")
    print(river_df["MatchedRiver"].value_counts().head(20).to_string())

    print("\n=== Suspect (physically implausible) readings, flagged not dropped ===")
    for col in PLAUSIBLE_RANGE:
        flag_col = f"{col}_Suspect"
        if flag_col in merged.columns:
            n = merged[flag_col].sum()
            if n:
                print(f"  {col}: {n} rows outside {PLAUSIBLE_RANGE[col]}")
    print(f"  TOTAL rows with >=1 suspect reading: {merged['HasSuspectReading'].sum():,} "
          f"({100*merged['HasSuspectReading'].mean():.2f}% of unified table)")
    print(f"  Of which on river stations: {river_df['HasSuspectReading'].sum():,} "
          f"({100*river_df['HasSuspectReading'].mean():.2f}% of river subset)")


if __name__ == "__main__":
    main()
