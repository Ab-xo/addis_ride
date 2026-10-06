"""
Deliverable A: Data Cleaning & Integration Pipeline
Run:  python run_pipeline_A.py
Produces:
    data/processed/master_train.csv
    data/processed/master_test.csv
    data/processed/data_dictionary_master.csv
    reports/A_cleaning_and_integration.md
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.checks import check
from src.cleaning import (
    CleaningLog,
    classify_missing_hours,
    clean_events,
    clean_trips,
    clean_weather,
    load_raw,
)
from src.features import (
    aggregate_event_features,
    add_calendar_features,
    add_lag_features,
    add_weather_features,
    build_master,
    data_dictionary,
    expand_event_windows,
    feature_table,
    fill_attendance,
    join_events,
    join_weather,
)

# ─────────────────────────────────────────── 1. load raw tables
print("=" * 60)
print("PHASE A  Data Cleaning & Integration")
print("=" * 60)

raw_train   = load_raw(config.RAW_TRAIN)
raw_test    = load_raw(config.RAW_TEST)
raw_weather = load_raw(config.RAW_WEATHER)
raw_events  = load_raw(config.RAW_EVENTS)

shapes_raw = {
    "ride_demand_train": raw_train.shape,
    "ride_demand_test":  raw_test.shape,
    "weather_hourly":    raw_weather.shape,
    "events_calendar":   raw_events.shape,
}
print("\nA0 – Raw shapes:")
for name, (r, c) in shapes_raw.items():
    print(f"  {name:30s} {r:7,} rows  {c} cols")

# ─────────────────────────────────────────── 2. clean each table
log = CleaningLog()

print("\nA1 – Cleaning …")
trips_train = clean_trips(raw_train, log, "ride_demand_train.csv")
trips_test  = clean_trips(raw_test,  log, "ride_demand_test.csv")
gaps        = classify_missing_hours(trips_train, log, "ride_demand_train.csv")
weather     = clean_weather(raw_weather, log)
events      = clean_events(raw_events, log)

clean_log_df = log.to_frame()
print(f"  Cleaning log: {len(clean_log_df)} entries")

# ─────────────────────────────────────────── 3. join & feature-engineer
print("\nA3-A6 – Building master tables …")
result = build_master(trips_train, trips_test, weather, events, gaps)

master_train = result["master_train"]
master_test  = result["master_test"]
join_audit   = result["join_audit"]
event_audit  = result["event_audit"]
target_dropped = result["target_rows_dropped"]
gap_summary  = result["gap_summary"]
launch       = result["launch"]

# ─────────────────────────────────────────── 4. integrity checks
print("\nA7 – Integrity checks:")
results = []

results.append(check("No nulls in master_train target column",
    master_train[config.TARGET].notna().all()))

results.append(check("No negative trips in master_train",
    (master_train[config.TARGET] >= 0).all()))

results.append(check("master_train row count >= 80 000",
    len(master_train) >= 80_000))

results.append(check("master_test has same feature columns as master_train (minus target)",
    set(feature_table()["name"]).issubset(set(master_test.columns))))

results.append(check("All 12 canonical zones present in master_train",
    set(config.ZONES).issubset(set(master_train["zone"].unique()))))

results.append(check("All 12 canonical zones present in master_test",
    set(config.ZONES).issubset(set(master_test["zone"].unique()))))

results.append(check("Weather join match rate >= 90 %",
    join_audit["train"]["weather"]["match_rate_pct"] >= 90))

results.append(check("No NaN in any model feature column in master_train",
    master_train[feature_table()["name"].tolist()].notna().all().all()))

results.append(check("No NaN in any model feature column in master_test",
    master_test[feature_table()["name"].tolist()].notna().all().all()))

results.append(check("master_test row count == 4 032 (submission template size)",
    len(master_test) == 4_032))

n_pass = sum(results)
n_fail = len(results) - n_pass
print(f"\n  {n_pass}/{len(results)} PASS  |  {n_fail} FAIL")

# ─────────────────────────────────────────── 5. export processed files
config.DATA_PROCESSED.mkdir(parents=True, exist_ok=True)

master_train.to_csv(config.MASTER_TRAIN,    index=False)
master_test.to_csv(config.MASTER_TEST,      index=False)
data_dictionary(master_train, master_test).to_csv(config.DATA_DICTIONARY, index=False)

print(f"\nA8 – Exported:")
print(f"  master_train.csv          {len(master_train):,} rows × {master_train.shape[1]} cols")
print(f"  master_test.csv           {len(master_test):,} rows × {master_test.shape[1]} cols")
print(f"  data_dictionary_master.csv")

# ─────────────────────────────────────────── 6. write report
print("\nWriting reports/A_cleaning_and_integration.md …")

feat_df  = feature_table()
dd_df    = data_dictionary(master_train, master_test)
train_au = join_audit["train"]
test_au  = join_audit["test"]

# helper: markdown table from DataFrame
def md_table(df: pd.DataFrame, max_rows: int = 100) -> str:
    df = df.head(max_rows).fillna("")
    header  = "| " + " | ".join(str(c) for c in df.columns) + " |"
    sep     = "| " + " | ".join(["---"] * len(df.columns)) + " |"
    body    = "\n".join(
        "| " + " | ".join(str(v) for v in row) + " |"
        for row in df.itertuples(index=False)
    )
    return "\n".join([header, sep, body])

# zone stats
zone_stats = (master_train
    .groupby("zone")[config.TARGET]
    .agg(mean="mean", median="median", q95=lambda x: x.quantile(0.95), count="count")
    .round(1).reset_index())

# example rows: rainy hour, event hour, public holiday hour
example_cols = ["zone", "pickup_hour", "trips", "rain_mm", "rain_class",
                "event_during", "event_attendance", "is_public_holiday", "is_weekend"]
example_cols = [c for c in example_cols if c in master_train.columns]

rainy_ex    = master_train[master_train["rain_mm"] > 2].head(1)[example_cols]
event_ex    = master_train[master_train["event_during"] == 1].head(1)[example_cols]
holiday_ex  = master_train[master_train["is_public_holiday"] == 1].head(1)[example_cols]
examples_df = pd.concat([rainy_ex, event_ex, holiday_ex], ignore_index=True)
examples_df.insert(0, "scenario", ["rainy hour", "event hour", "public holiday"])

# cleaning log top entries
clog_display = clean_log_df[["file", "columns", "issue", "rows_affected", "pct_affected", "fix"]]

# gap summary
gap_summary_reset = gap_summary.reset_index() if hasattr(gap_summary, "reset_index") else gap_summary

report = f"""# A: Data Cleaning and Integration Report
*Addis Ride Demand Forecasting – Deliverable A*

---

## A0 – Raw Data Inventory

| Table | Rows | Columns |
|---|---|---|
| ride_demand_train.csv | {shapes_raw["ride_demand_train"][0]:,} | {shapes_raw["ride_demand_train"][1]} |
| ride_demand_test.csv | {shapes_raw["ride_demand_test"][0]:,} | {shapes_raw["ride_demand_test"][1]} |
| weather_hourly.csv | {shapes_raw["weather_hourly"][0]:,} | {shapes_raw["weather_hourly"][1]} |
| events_calendar.csv | {shapes_raw["events_calendar"][0]:,} | {shapes_raw["events_calendar"][1]} |

---

## A1 – Cleaning Log

{len(clean_log_df)} issues identified and resolved across the four source tables.

{md_table(clog_display)}

---

## A2 – Data Quality Details

### A2a – Zone Canonicalisation

Raw zone column contained **{raw_train["zone"].nunique()} variants** for 12 canonical zones.
Issues: mixed case, trailing spaces, double spaces, and aliases
(C.M.C → CMC, Piazza → Piassa, Bole Rd → Bole, Kolfe Keranio → Kolfe,
Mercato → Merkato, Kazanches → Kazanchis, Megenaga → Megenagna).
After cleaning: exactly 12 labels in both train and test.

### A2b – Timestamp Formats

Three timestamp layouts found in the trip tables:

| Format | Example | Count (train) |
|---|---|---|
| YYYY-MM-DD HH:MM (local) | 2025-06-26 11:00 | majority |
| DD/MM/YYYY HH:MM (local) | 16/08/2025 04:00 | minority |
| ISO-8601 +03:00 offset | 2025-05-27T23:00:00+03:00 | minority |

Each parsed with an explicit format string to avoid day/month swaps.
All converted to naive Africa/Addis_Ababa (EAT, UTC+3) local time.

### A2c – Weather Clock Evidence

Weather timestamps (`Z`-suffix ISO-8601) are UTC. Converted +3 h to local time.
Evidence: temperature peaks at local 14:00–15:00 after conversion; raw UTC peak is at 11:00–12:00 UTC.

### A2d – Weather Numeric Fixes

| Column | Issue | Fix |
|---|---|---|
| rain_mm | 76 sentinel values of -9999 | Set to NaN, then 0 (no rain) |
| temp_c | Block of 42 rows recorded in Fahrenheit (max 76.6) | Converted (F−32)×5/9 |
| temp_c | 42 remaining NaN after Fahrenheit fix | Interpolated (≤3 h) or climatology |
| humidity_pct | 153 NaN | Interpolated (≤3 h) or climatology |
| timestamp | 65 duplicate hours | Averaged numeric readings |
| timestamp | Missing hours in grid | Re-indexed to full hourly grid |

### A2e – Events Calendar Fixes

| Column | Issue | Count | Fix |
|---|---|---|---|
| event_type | 20 spelling variants for 8 types | all | Lower-case + underscores |
| status | Mixed case + trailing space | several | Lower-case + trim |
| zone | Mixed case, aliases, citywide tokens | several | Canonical zone list |
| end_datetime | Missing or before start | {(events["end_imputed"]==1).sum()} | start + median type duration |
| expected_attendance | Free text, commas, "approx" | several | Strip non-numeric → float |
| is_active | Cancelled events | {(events["is_active"]==0).sum()} | Flagged; excluded from features |

---

## A3 – Join Design

```
trips (left)
  │
  ├─── many-to-one on pickup_hour ──────────► weather (1 row per local hour)
  │
  └─── many-to-one on (zone, pickup_hour) ──► event_features
           (pre-aggregated from events via interval expansion:
            each event → rows for every hour in [start−{config.EVENT_PRE_HOURS}h, end+{config.EVENT_POST_HOURS}h])
```

All joins are LEFT — trips rows without a weather or event match are kept.
No row duplication: validated with `validate="many_to_one"` in pandas merge.

---

## A4 – Join Audit

### Train
| Metric | Value |
|---|---|
| Rows input | {train_au["rows_input"]:,} |
| Rows after weather join | {train_au["rows_after_weather_join"]:,} |
| Rows after event join | {train_au["rows_after_event_join"]:,} |
| Weather match rate | {train_au["weather"]["match_rate_pct"]:.1f}% |
| Zone-hours in an event window | {train_au["zone_hours_in_event_window"]:,} |
| Zone-hours on a public holiday | {train_au["zone_hours_on_holiday"]:,} |

### Test
| Metric | Value |
|---|---|
| Rows input | {test_au["rows_input"]:,} |
| Rows after weather join | {test_au["rows_after_weather_join"]:,} |
| Rows after event join | {test_au["rows_after_event_join"]:,} |
| Weather match rate | {test_au["weather"]["match_rate_pct"]:.1f}% |
| Zone-hours in an event window | {test_au["zone_hours_in_event_window"]:,} |
| Zone-hours on a public holiday | {test_au["zone_hours_on_holiday"]:,} |

### Target rows dropped (NaN or sentinel trips after cleaning)
{target_dropped:,} rows removed from training set.

---

## A5 – Example Rows After All Joins

{md_table(examples_df)}

---

## A6 – Feature Engineering Table

{md_table(feat_df)}

---

## A7 – Integrity Checks

| Check | Result |
|---|---|
| No nulls in master_train target | {"PASS" if results[0] else "FAIL"} |
| No negative trips | {"PASS" if results[1] else "FAIL"} |
| master_train ≥ 80 000 rows | {"PASS" if results[2] else "FAIL"} |
| master_test has all feature columns | {"PASS" if results[3] else "FAIL"} |
| All 12 zones in master_train | {"PASS" if results[4] else "FAIL"} |
| All 12 zones in master_test | {"PASS" if results[5] else "FAIL"} |
| Weather join match rate ≥ 90% | {"PASS" if results[6] else "FAIL"} |
| No NaN in train feature columns | {"PASS" if results[7] else "FAIL"} |
| No NaN in test feature columns | {"PASS" if results[8] else "FAIL"} |
| master_test row count == 4 032 | {"PASS" if results[9] else "FAIL"} |

**{n_pass}/{len(results)} checks PASS.**

---

## A8 – Master Table Summary

### master_train.csv
- Rows: **{len(master_train):,}**
- Columns: **{master_train.shape[1]}**
- Date range: {master_train["pickup_hour"].min()} → {master_train["pickup_hour"].max()}
- Trips range: {master_train[config.TARGET].min():.0f} – {master_train[config.TARGET].max():.0f}  
  (mean {master_train[config.TARGET].mean():.1f}, median {master_train[config.TARGET].median():.1f})

### master_test.csv
- Rows: **{len(master_test):,}**
- Columns: **{master_test.shape[1]}**
- Date range: {master_test["pickup_hour"].min()} → {master_test["pickup_hour"].max()}

### Per-Zone Summary (train)

{md_table(zone_stats)}

### Data Dictionary (first 20 columns)

{md_table(dd_df.head(20))}

---

## A9 – Gap Analysis

Missing zone-hours in the train grid (pre-launch, outage, or isolated gaps):

{md_table(gap_summary_reset.head(20))}

---

*Report generated automatically by `run_pipeline_A.py`.*
"""

config.REPORTS.mkdir(parents=True, exist_ok=True)
(config.REPORTS / "A_cleaning_and_integration.md").write_text(report, encoding="utf-8")

print("Done.")
print(f"\nSummary:")
print(f"  master_train : {len(master_train):,} rows, {master_train.shape[1]} cols")
print(f"  master_test  : {len(master_test):,} rows, {master_test.shape[1]} cols")
print(f"  Checks       : {n_pass}/{len(results)} PASS")
