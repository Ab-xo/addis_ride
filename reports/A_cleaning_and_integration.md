# A: Data Cleaning and Integration Report
*Addis Ride Demand Forecasting – Deliverable A*

---

## A0 – Raw Data Inventory

| Table | Rows | Columns |
|---|---|---|
| ride_demand_train.csv | 85,460 | 7 |
| ride_demand_test.csv | 4,032 | 3 |
| weather_hourly.csv | 7,538 | 6 |
| events_calendar.csv | 165 | 9 |

---

## A1 – Cleaning Log

26 issues identified and resolved across the four source tables.

| file | columns | issue | rows_affected | pct_affected | fix |
| --- | --- | --- | --- | --- | --- |
| ride_demand_train.csv | zone | Inconsistent zone spelling (55 raw variants: case, trailing spaces, double spaces, aliases such as C.M.C, Piazza, Mercato, Bole Rd) | 32391 | 37.9 | Normalised whitespace/case and mapped aliases to the 12 canonical labels |
| ride_demand_train.csv | pickup_hour | Timestamps in 3 formats (YYYY-MM-DD HH:MM, day-first DD/MM/YYYY HH:MM, ISO-8601 with +03:00 offset) | 38574 | 45.14 | Parsed each format with an explicit format string; offset rows converted to local time |
| ride_demand_train.csv | trips | Missing target (blank) | 845 | 0.99 | Kept as NaN; zone-hours with no valid trips are excluded from training rows |
| ride_demand_train.csv | trips | Sentinel value -1 (impossible negative count) | 681 | 0.8 | Set to NaN, then treated as missing target |
| ride_demand_train.csv | trips | Spikes recorded x8 (trips/active_drivers > 2.5; clean rows never exceed 2.0; 99% of flagged values are multiples of 8) | 126 | 0.15 | Divided by 8 and rounded |
| ride_demand_train.csv | avg_wait_min | Sentinel value -1 | 1707 | 2.0 | Set to NaN (analysis only; not a model input) |
| ride_demand_train.csv | avg_fare_birr | Missing values (blank) | 1277 | 1.49 | Left as NaN; the demo uses each zone's mean fare over non-missing rows |
| ride_demand_train.csv | zone, pickup_hour | Duplicate zone-hour keys (846 extra rows; 362 keys disagree on trips by 1-3) | 846 | 0.99 | Collapsed to one row per zone-hour; numeric columns averaged (NaN ignored), lowest record_id kept |
| ride_demand_test.csv | zone | Inconsistent zone spelling (55 raw variants: case, trailing spaces, double spaces, aliases such as C.M.C, Piazza, Mercato, Bole Rd) | 1538 | 38.14 | Normalised whitespace/case and mapped aliases to the 12 canonical labels |
| ride_demand_test.csv | pickup_hour | Timestamps in 3 formats (YYYY-MM-DD HH:MM, day-first DD/MM/YYYY HH:MM, ISO-8601 with +03:00 offset) | 1771 | 43.92 | Parsed each format with an explicit format string; offset rows converted to local time |
| ride_demand_train.csv | zone, pickup_hour | Zone-hours with no row at all (outage 504, pre-launch 1752, random 682) | 2938 | 3.36 | Not imputed as targets. Outage and pre-launch hours are excluded from training; lag features that land on any gap fall back to the train-fitted zone x weekday x hour mean |
| weather_hourly.csv | timestamp | Timestamps on UTC, not local time, in 2 formats (732 rows DD/MM/YYYY without a 'Z') | 7538 | 100.0 | Parsed both formats as UTC and converted to Africa/Addis_Ababa (+3 h) |
| weather_hourly.csv | rain_mm | Sentinel value -9999 | 76 | 1.01 | Set to NaN, then imputed with the hour-gap rules below |
| weather_hourly.csv | temp_c | Temperature in Fahrenheit for a contiguous block (2025-07-10 03:00 to 2025-07-25 02:00 local; values 45-77) | 353 | 4.68 | Converted with (F - 32) x 5/9 |
| weather_hourly.csv | temp_c | Missing values (blank) | 42 | 0.56 | Imputed with the hour-gap rules below |
| weather_hourly.csv | humidity_pct | Missing values (blank) | 153 | 2.03 | Imputed with the hour-gap rules below |
| weather_hourly.csv | timestamp | Duplicate hours with conflicting readings | 75 | 0.99 | Averaged the readings for that hour (NaN ignored) |
| weather_hourly.csv | timestamp | Missing hours (192 hours; longest gap 31 h) | 192 | 2.52 | Re-indexed to a full hourly grid; gaps <= 3 h interpolated, longer gaps filled with month x hour climatology; rain gaps set to 0; flagged weather_imputed |
| events_calendar.csv | event_type | Inconsistent spelling (20 variants for 8 types: case, spaces, trailing space) | 94 | 56.97 | Lower-cased, trimmed, spaces -> underscores |
| events_calendar.csv | status | Inconsistent case / trailing spaces (confirmed, Confirmed, CONFIRMED, CANCELLED ) | 28 | 16.97 | Lower-cased and trimmed |
| events_calendar.csv | all | Duplicate events under a second id (EVT-9000, EVT-9001, EVT-9002, EVT-9003, EVT-9004, EVT-9005) | 6 | 3.64 | Dropped the copy, kept the original EVT-0xxx id |
| events_calendar.csv | zone | Zone in mixed spellings, with sub-city suffixes '(Kirkos)', several zones joined by '&', or the whole city ('Citywide', 'ALL', 'All zones', 'city-wide') | 82 | 51.57 | Parsed into a list of canonical zones; citywide -> all 12 zones |
| events_calendar.csv | start_datetime, end_datetime | Timestamps in 3 formats (ISO, day-first DD/MM/YYYY, 'Mon DD, YYYY HH:MM AM/PM') | 161 | 50.63 | Parsed each format with an explicit format string (local time) |
| events_calendar.csv | end_datetime | End missing (4) or earlier than start (1) | 5 | 3.14 | Set end = start + median duration of the same event type |
| events_calendar.csv | expected_attendance | Free text ('approx 34000', '34,756') and blanks (53 blank) | 76 | 47.8 | Stripped 'approx' and thousands separators -> number; blanks filled at feature time with the median attendance of the same event type |
| events_calendar.csv | status | Cancelled events listed in the calendar | 6 | 3.77 | Kept in the clean table but excluded from event features |

---

## A2 – Data Quality Details

### A2a – Zone Canonicalisation

Raw zone column contained **55 variants** for 12 canonical zones.
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
| end_datetime | Missing or before start | 5 | start + median type duration |
| expected_attendance | Free text, commas, "approx" | several | Strip non-numeric → float |
| is_active | Cancelled events | 6 | Flagged; excluded from features |

---

## A3 – Join Design

```
trips (left)
  │
  ├─── many-to-one on pickup_hour ──────────► weather (1 row per local hour)
  │
  └─── many-to-one on (zone, pickup_hour) ──► event_features
           (pre-aggregated from events via interval expansion:
            each event → rows for every hour in [start−2h, end+2h])
```

All joins are LEFT — trips rows without a weather or event match are kept.
No row duplication: validated with `validate="many_to_one"` in pandas merge.

---

## A4 – Join Audit

### Train
| Metric | Value |
|---|---|
| Rows input | 83,104 |
| Rows after weather join | 83,104 |
| Rows after event join | 83,104 |
| Weather match rate | 100.0% |
| Zone-hours in an event window | 1,842 |
| Zone-hours on a public holiday | 3,567 |

### Test
| Metric | Value |
|---|---|
| Rows input | 4,032 |
| Rows after weather join | 4,032 |
| Rows after event join | 4,032 |
| Weather match rate | 100.0% |
| Zone-hours in an event window | 65 |
| Zone-hours on a public holiday | 0 |

### Target rows dropped (NaN or sentinel trips after cleaning)
1,510 rows removed from training set.

---

## A5 – Example Rows After All Joins

| scenario | zone | pickup_hour | trips | rain_mm | rain_class | event_during | event_attendance | is_public_holiday | is_weekend |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rainy hour | Arat Kilo | 2025-01-02 19:00:00 | 77.0 | 5.7 | 3 | 0.0 | 0.0 | 0 | 0 |
| event hour | Arat Kilo | 2025-05-08 08:00:00 | 39.0 | 0.0 | 0 | 1.0 | 0.0 | 0 | 0 |
| public holiday | Arat Kilo | 2025-01-07 00:00:00 | 4.0 | 0.0 | 0 | 0.0 | 0.0 | 1 | 0 |

---

## A6 – Feature Engineering Table

| name | group | formula | source | why | known_at_forecast_time |
| --- | --- | --- | --- | --- | --- |
| zone_id | zone | index of zone in the 12 canonical labels | trips.zone | Zones differ in level and daily shape | yes |
| hour | calendar | pickup_hour.hour (0-23, local) | trips.pickup_hour | Strong daily cycle (commute peaks) | yes |
| day_of_week | calendar | pickup_hour.dayofweek (0=Mon) | trips.pickup_hour | Weekday vs weekend demand shapes differ | yes |
| is_weekend | calendar | day_of_week >= 5 | trips.pickup_hour | Business zones drop, nightlife zones rise at weekends | yes |
| month | calendar | pickup_hour.month | trips.pickup_hour | Seasonality (rainy season Jun-Sep) | yes |
| is_public_holiday | calendar | date of pickup_hour is a listed public holiday | events (public_holiday, confirmed) | Holidays change city-wide demand | yes |
| is_school_break | calendar | date inside a school-break period | events (school_break, confirmed) | Fewer school/commute trips | yes |
| is_payday_window | calendar | day >= days_in_month - 2 or day <= 2 | trips.pickup_hour | Riders may spend more around payday | yes |
| days_since_start | trend | (date - 2025-01-01) in days | trips.pickup_hour | Demand grows through the year; lets the model follow the trend | yes |
| zone_age_days | trend | days since the zone's first record (0 before launch) | trips history (first record per zone) | A newly launched zone (Ayat) ramps up | yes |
| temp_c | weather | cleaned temperature at the local hour (forecast for Nov) | weather.temp_c | Comfort affects walking vs riding | yes |
| rain_mm | weather | rain in the previous hour, mm | weather.rain_mm | Rain pushes people into cars | yes |
| rain_3h_mm | weather | sum of rain_mm over this and the 2 previous hours | weather.rain_mm | Wet streets keep demand up after rain stops | yes |
| rain_class | weather | 0 none, 1 light (<=1 mm), 2 moderate (<=4 mm), 3 heavy (>4 mm) | weather.rain_mm | Non-linear dose-response | yes |
| humidity_pct | weather | cleaned relative humidity | weather.humidity_pct | Proxy for rainy/overcast conditions | yes |
| wind_kmh | weather | cleaned wind speed | weather.wind_kmh | Weather discomfort | yes |
| weather_imputed | weather | 1 if any weather value at this hour was imputed | weather (cleaning) | Lets the model discount filled values | yes |
| event_pre | events | 1 if within 2 h before a confirmed event start in this zone | events (interval join) | Arrivals before an event | yes |
| event_during | events | 1 if the hour overlaps a confirmed event in this zone | events (interval join) | Activity during the event | yes |
| event_post | events | 1 if within 2 h after a confirmed event end in this zone | events (interval join) | Crowds leave at the end - the largest expected spike | yes |
| event_attendance | events | max attendance of events whose window covers the hour (blank -> type median), else 0 | events.expected_attendance | Bigger crowds, bigger spike | yes |
| n_events | events | number of confirmed events whose window covers the hour | events (interval join) | Overlapping events stack | yes |
| hours_to_event_start | events | hours until the next event start in this zone (capped at 24) | events.start | Build-up before an event | yes |
| hours_since_event_end | events | hours since the last event end in this zone (capped at 24) | events.end | Decay after an event | yes |
| football_match_window | events | 1 if inside the pre/during/post window of a confirmed football_match | events (football_match) | Event types have different effects | yes |
| concert_window | events | 1 if inside the pre/during/post window of a confirmed concert | events (concert) | Event types have different effects | yes |
| conference_window | events | 1 if inside the pre/during/post window of a confirmed conference | events (conference) | Event types have different effects | yes |
| exhibition_window | events | 1 if inside the pre/during/post window of a confirmed exhibition | events (exhibition) | Event types have different effects | yes |
| sports_run_window | events | 1 if inside the pre/during/post window of a confirmed sports_run | events (sports_run) | Event types have different effects | yes |
| road_closure_active | events | 1 if a confirmed road closure is in force in this zone | events (road_closure) | Closures can suppress or divert trips | yes |
| trips_lag_14d | lag | trips in the same zone and hour 14 days earlier (missing -> mean of the other lags) | trips history | Recent level of the same zone-hour; >= 14 days so it is known for every forecast hour | yes |
| trips_lag_21d | lag | trips in the same zone and hour 21 days earlier (missing -> mean of the other lags) | trips history | Recent level of the same zone-hour; >= 14 days so it is known for every forecast hour | yes |
| trips_lag_28d | lag | trips in the same zone and hour 28 days earlier (missing -> mean of the other lags) | trips history | Recent level of the same zone-hour; >= 14 days so it is known for every forecast hour | yes |
| trips_lag_35d | lag | trips in the same zone and hour 35 days earlier (missing -> mean of the other lags) | trips history | Recent level of the same zone-hour; >= 14 days so it is known for every forecast hour | yes |
| trips_lag_mean | lag | mean of trips_lag_{14,21,28,35}d | trips history | Smoothed recent same-weekday-same-hour level | yes |

---

## A7 – Integrity Checks

| Check | Result |
|---|---|
| No nulls in master_train target | PASS |
| No negative trips | PASS |
| master_train ≥ 80 000 rows | PASS |
| master_test has all feature columns | PASS |
| All 12 zones in master_train | PASS |
| All 12 zones in master_test | PASS |
| Weather join match rate ≥ 90% | PASS |
| No NaN in train feature columns | PASS |
| No NaN in test feature columns | PASS |
| master_test row count == 4 032 | PASS |

**10/10 checks PASS.**

---

## A8 – Master Table Summary

### master_train.csv
- Rows: **83,104**
- Columns: **44**
- Date range: 2025-01-01 00:00:00 → 2025-10-31 23:00:00
- Trips range: 0 – 321  
  (mean 28.4, median 23.0)

### master_test.csv
- Rows: **4,032**
- Columns: **40**
- Date range: 2025-11-01 00:00:00 → 2025-11-14 23:00:00

### Per-Zone Summary (train)

| zone | mean | median | q95 | count |
| --- | --- | --- | --- | --- |
| Arat Kilo | 20.5 | 15.0 | 58.0 | 7067 |
| Ayat | 17.8 | 16.0 | 41.0 | 5356 |
| Bole | 39.2 | 36.0 | 79.0 | 7075 |
| CMC | 25.7 | 23.0 | 57.0 | 7087 |
| Gerji | 24.2 | 22.0 | 53.0 | 7052 |
| Kazanchis | 31.7 | 23.0 | 86.6 | 7069 |
| Kolfe | 23.0 | 21.0 | 51.0 | 7073 |
| Lideta | 28.0 | 27.0 | 64.2 | 7076 |
| Megenagna | 38.2 | 37.0 | 87.0 | 7063 |
| Merkato | 40.5 | 30.0 | 106.0 | 7050 |
| Piassa | 28.2 | 21.0 | 78.0 | 7074 |
| Sarbet | 21.7 | 20.0 | 49.0 | 7062 |

### Data Dictionary (first 20 columns)

| column | dtype | in_train | in_test | source | description | derivation | known_at_forecast_time | model_feature |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| record_id | object | True | False | train | Original train row id (lowest id kept when duplicates were merged) | raw record_id | n/a | False |
| row_id | object | False | True | test | Test row id; join key for the submission | raw row_id | n/a | False |
| zone | object | True | True | trips | Canonical zone label (12 values) | normalize_zone(raw zone) | yes | False |
| pickup_hour | datetime64[ns] | True | True | trips | Start of the hour, Addis Ababa local time (EAT, naive) | parsed from 3 raw formats | yes | False |
| trips | float64 | True | False | train | TARGET: trips requested in the zone-hour | sentinels -> NaN, x8 spikes / 8, duplicates averaged | no (target) | False |
| avg_fare_birr | float64 | True | False | train | Average fare (analysis/demo only, NOT a model input) | raw, duplicates averaged | no | False |
| avg_wait_min | float64 | True | False | train | Average wait (analysis only, NOT a model input) | -1 -> NaN, duplicates averaged | no | False |
| active_drivers | float64 | True | False | train | Active drivers (analysis only, NOT a model input) | raw, duplicates averaged | no | False |
| weather_source | object | True | True | weather | observed (history) or forecast (1-14 Nov); info only | weather.data_type | yes | False |
| lag_count | int64 | True | True | trips history | How many of the 4 lags were found before filling; info only | count of non-missing lags | yes | False |
| zone_id | int64 | True | True | trips.zone | Zones differ in level and daily shape | index of zone in the 12 canonical labels | yes | True |
| hour | int32 | True | True | trips.pickup_hour | Strong daily cycle (commute peaks) | pickup_hour.hour (0-23, local) | yes | True |
| day_of_week | int32 | True | True | trips.pickup_hour | Weekday vs weekend demand shapes differ | pickup_hour.dayofweek (0=Mon) | yes | True |
| is_weekend | int64 | True | True | trips.pickup_hour | Business zones drop, nightlife zones rise at weekends | day_of_week >= 5 | yes | True |
| month | int32 | True | True | trips.pickup_hour | Seasonality (rainy season Jun-Sep) | pickup_hour.month | yes | True |
| is_public_holiday | int64 | True | True | events (public_holiday, confirmed) | Holidays change city-wide demand | date of pickup_hour is a listed public holiday | yes | True |
| is_school_break | int64 | True | True | events (school_break, confirmed) | Fewer school/commute trips | date inside a school-break period | yes | True |
| is_payday_window | int64 | True | True | trips.pickup_hour | Riders may spend more around payday | day >= days_in_month - 2 or day <= 2 | yes | True |
| days_since_start | int64 | True | True | trips.pickup_hour | Demand grows through the year; lets the model follow the trend | (date - 2025-01-01) in days | yes | True |
| zone_age_days | int64 | True | True | trips history (first record per zone) | A newly launched zone (Ayat) ramps up | days since the zone's first record (0 before launch) | yes | True |

---

## A9 – Gap Analysis

Missing zone-hours in the train grid (pre-launch, outage, or isolated gaps):

| zone | missing_record | outage | pre_launch |
| --- | --- | --- | --- |
| Arat Kilo | 53 | 42 | 0 |
| Ayat | 44 | 42 | 1752 |
| Bole | 58 | 42 | 0 |
| CMC | 58 | 42 | 0 |
| Gerji | 55 | 42 | 0 |
| Kazanchis | 60 | 42 | 0 |
| Kolfe | 58 | 42 | 0 |
| Lideta | 52 | 42 | 0 |
| Megenagna | 58 | 42 | 0 |
| Merkato | 66 | 42 | 0 |
| Piassa | 55 | 42 | 0 |
| Sarbet | 65 | 42 | 0 |

---

*Report generated automatically by `run_pipeline_A.py`.*
