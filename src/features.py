"""Joins and feature engineering (Deliverable A3-A6, A8).

Train and test rows go through exactly the same functions. Anything estimated from data
(attendance medians, zone launch dates, lag fall-backs) is fitted on train history only and
then applied to both tables (Rule 8).

Join design (A3):
    trips (left) --many-to-one on local hour-->            weather (one row per hour)
    trips (left) --many-to-one on (zone, local hour)-->    event features (one row per zone-hour,
                                                           built by an interval expansion of events)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src import config

KEY = ["zone", "pickup_hour"]

# --------------------------------------------------------------------------- feature catalogue
# Single source of truth for the A6 feature table and the A8 data dictionary.
# known = known at forecast time (Rule 6). Only known features are model inputs.
FEATURE_SPECS: list[dict] = [
    # calendar ---------------------------------------------------------------
    dict(name="zone_id", group="zone", source="trips.zone",
         formula="index of zone in the 12 canonical labels", why="Zones differ in level and daily shape"),
    dict(name="hour", group="calendar", source="trips.pickup_hour",
         formula="pickup_hour.hour (0-23, local)", why="Strong daily cycle (commute peaks)"),
    dict(name="day_of_week", group="calendar", source="trips.pickup_hour",
         formula="pickup_hour.dayofweek (0=Mon)", why="Weekday vs weekend demand shapes differ"),
    dict(name="is_weekend", group="calendar", source="trips.pickup_hour",
         formula="day_of_week >= 5", why="Business zones drop, nightlife zones rise at weekends"),
    dict(name="month", group="calendar", source="trips.pickup_hour",
         formula="pickup_hour.month", why="Seasonality (rainy season Jun-Sep)"),
    dict(name="is_public_holiday", group="calendar", source="events (public_holiday, confirmed)",
         formula="date of pickup_hour is a listed public holiday", why="Holidays change city-wide demand"),
    dict(name="is_school_break", group="calendar", source="events (school_break, confirmed)",
         formula="date inside a school-break period", why="Fewer school/commute trips"),
    dict(name="is_payday_window", group="calendar", source="trips.pickup_hour",
         formula=f"day >= days_in_month - {config.PAYDAY_LAST_DAYS - 1} or day <= {config.PAYDAY_FIRST_DAYS}",
         why="Riders may spend more around payday"),
    dict(name="days_since_start", group="trend", source="trips.pickup_hour",
         formula="(date - 2025-01-01) in days", why="Demand grows through the year; lets the model follow the trend"),
    dict(name="zone_age_days", group="trend", source="trips history (first record per zone)",
         formula="days since the zone's first record (0 before launch)", why="A newly launched zone (Ayat) ramps up"),
    # weather ----------------------------------------------------------------
    dict(name="temp_c", group="weather", source="weather.temp_c",
         formula="cleaned temperature at the local hour (forecast for Nov)", why="Comfort affects walking vs riding"),
    dict(name="rain_mm", group="weather", source="weather.rain_mm",
         formula="rain in the previous hour, mm", why="Rain pushes people into cars"),
    dict(name="rain_3h_mm", group="weather", source="weather.rain_mm",
         formula="sum of rain_mm over this and the 2 previous hours", why="Wet streets keep demand up after rain stops"),
    dict(name="rain_class", group="weather", source="weather.rain_mm",
         formula="0 none, 1 light (<=1 mm), 2 moderate (<=4 mm), 3 heavy (>4 mm)", why="Non-linear dose-response"),
    dict(name="humidity_pct", group="weather", source="weather.humidity_pct",
         formula="cleaned relative humidity", why="Proxy for rainy/overcast conditions"),
    dict(name="wind_kmh", group="weather", source="weather.wind_kmh",
         formula="cleaned wind speed", why="Weather discomfort"),
    dict(name="weather_imputed", group="weather", source="weather (cleaning)",
         formula="1 if any weather value at this hour was imputed", why="Lets the model discount filled values"),
    # events -----------------------------------------------------------------
    dict(name="event_pre", group="events", source="events (interval join)",
         formula=f"1 if within {config.EVENT_PRE_HOURS} h before a confirmed event start in this zone",
         why="Arrivals before an event"),
    dict(name="event_during", group="events", source="events (interval join)",
         formula="1 if the hour overlaps a confirmed event in this zone", why="Activity during the event"),
    dict(name="event_post", group="events", source="events (interval join)",
         formula=f"1 if within {config.EVENT_POST_HOURS} h after a confirmed event end in this zone",
         why="Crowds leave at the end - the largest expected spike"),
    dict(name="event_attendance", group="events", source="events.expected_attendance",
         formula="max attendance of events whose window covers the hour (blank -> type median), else 0",
         why="Bigger crowds, bigger spike"),
    dict(name="n_events", group="events", source="events (interval join)",
         formula="number of confirmed events whose window covers the hour", why="Overlapping events stack"),
    dict(name="hours_to_event_start", group="events", source="events.start",
         formula=f"hours until the next event start in this zone (capped at {config.EVENT_HOURS_CAP})",
         why="Build-up before an event"),
    dict(name="hours_since_event_end", group="events", source="events.end",
         formula=f"hours since the last event end in this zone (capped at {config.EVENT_HOURS_CAP})",
         why="Decay after an event"),
    *[dict(name=f"{t}_window", group="events", source=f"events ({t})",
           formula=f"1 if inside the pre/during/post window of a confirmed {t}",
           why="Event types have different effects")
      for t in ["football_match", "concert", "conference", "exhibition", "sports_run"]],
    dict(name="road_closure_active", group="events", source="events (road_closure)",
         formula="1 if a confirmed road closure is in force in this zone", why="Closures can suppress or divert trips"),
    # lags -------------------------------------------------------------------
    *[dict(name=f"trips_lag_{d}d", group="lag", source="trips history",
           formula=f"trips in the same zone and hour {d} days earlier (missing -> mean of the other lags)",
           why="Recent level of the same zone-hour; >= 14 days so it is known for every forecast hour")
      for d in config.LAG_DAYS],
    dict(name="trips_lag_mean", group="lag", source="trips history",
         formula=f"mean of trips_lag_{{{','.join(map(str, config.LAG_DAYS))}}}d",
         why="Smoothed recent same-weekday-same-hour level"),
]
for spec in FEATURE_SPECS:
    spec.setdefault("known_at_forecast_time", "yes")

FEATURES = [s["name"] for s in FEATURE_SPECS]
EVENT_FEATURES = [s["name"] for s in FEATURE_SPECS if s["group"] == "events"]
WEATHER_FEATURES = [s["name"] for s in FEATURE_SPECS if s["group"] == "weather"]


# --------------------------------------------------------------------------- weather join


def add_weather_features(weather: pd.DataFrame) -> pd.DataFrame:
    """Derive hour-level weather features on the continuous hourly weather grid."""
    w = weather.sort_values("timestamp_local").copy()
    w["rain_3h_mm"] = w["rain_mm"].rolling(3, min_periods=1).sum().round(1)
    w["rain_class"] = pd.cut(w["rain_mm"], bins=config.RAIN_CLASS_BINS,
                             labels=config.RAIN_CLASS_LABELS).astype(int)
    return w.rename(columns={"data_type": "weather_source"})


def join_weather(trips: pd.DataFrame, weather: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Many-to-one left join of trips onto weather by local hour. Row count must not change."""
    cols = ["timestamp_local", "temp_c", "rain_mm", "rain_3h_mm", "rain_class", "humidity_pct",
            "wind_kmh", "weather_imputed", "weather_source"]
    out = trips.merge(weather[cols], left_on="pickup_hour", right_on="timestamp_local",
                      how="left", validate="many_to_one", indicator=True)
    audit = {
        "rows_before": len(trips),
        "rows_after": len(out),
        "matched": int((out["_merge"] == "both").sum()),
        "match_rate_pct": round(100 * (out["_merge"] == "both").mean(), 2),
        "zone_hours_on_imputed_weather": int(out["weather_imputed"].sum()),
        "zone_hours_on_forecast_weather": int((out["weather_source"] == "forecast").sum()),
    }
    return out.drop(columns=["timestamp_local", "_merge"]), audit


# --------------------------------------------------------------------------- event join


def fill_attendance(events: pd.DataFrame) -> pd.DataFrame:
    """Fill blank attendance with the median of the same event type (fitted on history events)."""
    ev = events.copy()
    history = ev["start"] < pd.Timestamp(config.TEST_START)
    medians = ev[history].groupby("event_type")["attendance"].median()
    ev["attendance_filled"] = ev["attendance"].fillna(ev["event_type"].map(medians)).fillna(0)
    return ev


def expand_event_windows(events: pd.DataFrame) -> pd.DataFrame:
    """Interval join step 1: one row per (event, zone, hour) for hours near a zone event.

    An hour h covers [h, h+1). Window rule (A3):
        pre    = the EVENT_PRE_HOURS hours before floor(start)
        during = hours from floor(start) up to (not including) ceil(end)
        post   = the EVENT_POST_HOURS hours from ceil(end)
    Hours out to EVENT_HOURS_CAP on either side are kept for hours_to/since features.
    Only confirmed, zone-level events are expanded; holidays/school breaks become calendar flags.
    """
    zone_events = events[(events["is_active"] == 1) & ~events["event_type"].isin(config.CALENDAR_EVENT_TYPES)]
    cap = pd.Timedelta(hours=config.EVENT_HOURS_CAP)
    frames = []
    for ev in zone_events.itertuples(index=False):
        start, end = ev.start.floor("h"), ev.end.ceil("h")
        hours = pd.date_range(start - cap, end + cap - pd.Timedelta(hours=1), freq="h")
        to_start = (start - hours) / pd.Timedelta(hours=1)        # >0 before the event
        since_end = (hours - end) / pd.Timedelta(hours=1)         # >=0 after the event
        phase = np.select(
            [(to_start > 0) & (to_start <= config.EVENT_PRE_HOURS),
             (to_start <= 0) & (since_end < 0),
             (since_end >= 0) & (since_end < config.EVENT_POST_HOURS)],
            ["pre", "during", "post"], default="outside")
        for zone in ev.zones:
            frames.append(pd.DataFrame({
                "event_id": ev.event_id, "event_type": ev.event_type, "zone": zone,
                "pickup_hour": hours, "phase": phase, "attendance": ev.attendance_filled,
                "to_start": to_start, "since_end": since_end,
            }))
    return pd.concat(frames, ignore_index=True)


def aggregate_event_features(windows: pd.DataFrame) -> pd.DataFrame:
    """Interval join step 2: collapse the long event table to one row per zone-hour."""
    w = windows.copy()
    w["in_window"] = w["phase"] != "outside"
    for phase in ["pre", "during", "post"]:
        w[f"event_{phase}"] = (w["phase"] == phase).astype(int)
    w["att_in_window"] = w["attendance"].where(w["in_window"], 0)
    w["to_start_pos"] = w["to_start"].where(w["to_start"] > 0)
    w["since_end_pos"] = w["since_end"].where(w["since_end"] >= 0) + 1   # 1 = first hour after end
    for t in ["football_match", "concert", "conference", "exhibition", "sports_run"]:
        w[f"{t}_window"] = ((w["event_type"] == t) & w["in_window"]).astype(int)
    w["road_closure_active"] = ((w["event_type"] == "road_closure") & (w["phase"] == "during")).astype(int)

    agg = w.groupby(KEY).agg(
        event_pre=("event_pre", "max"), event_during=("event_during", "max"), event_post=("event_post", "max"),
        event_attendance=("att_in_window", "max"), n_events=("in_window", "sum"),
        hours_to_event_start=("to_start_pos", "min"), hours_since_event_end=("since_end_pos", "min"),
        **{c: (c, "max") for c in [f"{t}_window" for t in
                                   ["football_match", "concert", "conference", "exhibition", "sports_run"]]},
        road_closure_active=("road_closure_active", "max"),
    ).reset_index()
    return agg


def join_events(trips: pd.DataFrame, event_feats: pd.DataFrame) -> pd.DataFrame:
    """Many-to-one left join of trips onto zone-hour event features; no event -> 0 / cap."""
    out = trips.merge(event_feats, on=KEY, how="left", validate="many_to_one")
    cap = config.EVENT_HOURS_CAP
    for col in ["hours_to_event_start", "hours_since_event_end"]:
        out[col] = out[col].fillna(cap).clip(upper=cap)
    flag_cols = [c for c in event_feats.columns if c not in KEY + ["hours_to_event_start", "hours_since_event_end"]]
    out[flag_cols] = out[flag_cols].fillna(0)
    out["n_events"] = out["n_events"].astype(int)
    return out


def event_join_audit(events: pd.DataFrame, windows: pd.DataFrame, train_keys: pd.DataFrame,
                     test_keys: pd.DataFrame) -> pd.DataFrame:
    """Per-event outcome of the interval join (A4): matched to train/test zone-hours or excluded, and why."""
    in_window = windows[windows["phase"] != "outside"]
    matched_train = set(in_window.merge(train_keys, on=KEY)["event_id"])
    matched_test = set(in_window.merge(test_keys, on=KEY)["event_id"])

    rows = []
    for ev in events.itertuples(index=False):
        if ev.is_active == 0:
            outcome = "excluded: cancelled"
        elif ev.event_type in config.CALENDAR_EVENT_TYPES:
            outcome = "used as calendar flag (city-wide day)"
        elif ev.event_id in matched_train or ev.event_id in matched_test:
            outcome = "matched"
        else:
            outcome = "excluded: no trip rows in window (outage / missing hours)"
        rows.append({"event_id": ev.event_id, "event_type": ev.event_type, "zones": ev.zone_clean,
                     "start": ev.start, "end": ev.end, "status": ev.status, "outcome": outcome,
                     "matched_train": ev.event_id in matched_train, "matched_test": ev.event_id in matched_test})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- calendar & trend


def add_calendar_features(df: pd.DataFrame, events: pd.DataFrame, launch: pd.Series) -> pd.DataFrame:
    """Calendar, holiday, payday and trend features. ``launch`` = first record per zone (from train)."""
    out = df.copy()
    ts = out["pickup_hour"]
    date = ts.dt.normalize()

    out["zone_id"] = out["zone"].map({z: i for i, z in enumerate(config.ZONES)}).astype(int)
    out["hour"] = ts.dt.hour
    out["day_of_week"] = ts.dt.dayofweek
    out["is_weekend"] = (out["day_of_week"] >= 5).astype(int)
    out["month"] = ts.dt.month

    active = events[events["is_active"] == 1]
    holidays = set(active.loc[active["event_type"] == "public_holiday", "start"].dt.normalize())
    out["is_public_holiday"] = date.isin(holidays).astype(int)

    breaks = active[active["event_type"] == "school_break"]
    in_break = pd.Series(False, index=out.index)
    for b in breaks.itertuples(index=False):
        in_break |= (ts >= b.start.floor("D")) & (ts < b.end.ceil("D"))
    out["is_school_break"] = in_break.astype(int)

    dim = ts.dt.days_in_month
    out["is_payday_window"] = ((ts.dt.day > dim - config.PAYDAY_LAST_DAYS) |
                               (ts.dt.day <= config.PAYDAY_FIRST_DAYS)).astype(int)

    out["days_since_start"] = (date - pd.Timestamp(config.TRAIN_START).normalize()).dt.days
    out["zone_age_days"] = ((date - out["zone"].map(launch).dt.normalize()).dt.days).clip(lower=0)
    return out


# --------------------------------------------------------------------------- lags


def add_lag_features(df: pd.DataFrame, history: pd.DataFrame) -> pd.DataFrame:
    """Same-zone, same-hour trips 14/21/28/35 days earlier, looked up in the cleaned train history.

    Every lag is >= the 14-day forecast horizon, so it is known for all test hours.
    A lag that lands on a gap is replaced by the mean of the row's other lags; rows with no lag
    at all (a zone's first 14 days) use that zone's hour-of-day mean over its first 28 days.
    """
    hist = history.dropna(subset=[config.TARGET]).set_index(KEY)[config.TARGET]
    out = df.copy()
    lag_cols = []
    for d in config.LAG_DAYS:
        col = f"trips_lag_{d}d"
        lookup = pd.MultiIndex.from_arrays([out["zone"], out["pickup_hour"] - pd.Timedelta(days=d)])
        out[col] = hist.reindex(lookup).to_numpy()
        lag_cols.append(col)

    out["lag_count"] = out[lag_cols].notna().sum(axis=1)
    out["trips_lag_mean"] = out[lag_cols].mean(axis=1)

    h = history.dropna(subset=[config.TARGET])
    first = h.groupby("zone")["pickup_hour"].transform("min")
    early = h[h["pickup_hour"] < first + pd.Timedelta(days=28)]
    start_profile = early.groupby(["zone", early["pickup_hour"].dt.hour])[config.TARGET].mean()
    no_lag = out["trips_lag_mean"].isna()
    out.loc[no_lag, "trips_lag_mean"] = start_profile.reindex(
        pd.MultiIndex.from_arrays([out.loc[no_lag, "zone"], out.loc[no_lag, "pickup_hour"].dt.hour])).to_numpy()

    for col in lag_cols:
        out[col] = out[col].fillna(out["trips_lag_mean"])
    return out


# --------------------------------------------------------------------------- master tables


def build_master(trips_train: pd.DataFrame, trips_test: pd.DataFrame, weather: pd.DataFrame,
                 events: pd.DataFrame, gaps: pd.DataFrame) -> dict:
    """Join and engineer features for train and test with the same code path.

    Returns master tables plus every audit table needed for the A4 report.
    """
    launch = trips_train.groupby("zone")["pickup_hour"].min()     # fitted on train
    events = fill_attendance(events)                               # medians fitted on history events
    weather_f = add_weather_features(weather)
    windows = expand_event_windows(events)
    event_feats = aggregate_event_features(windows)

    # Training rows = zone-hours with a valid target.
    n_before_target_drop = len(trips_train)
    train = trips_train.dropna(subset=[config.TARGET]).reset_index(drop=True)
    target_dropped = n_before_target_drop - len(train)

    tables, audits = {}, {}
    for name, df in [("train", train), ("test", trips_test)]:
        n0 = len(df)
        out, w_audit = join_weather(df, weather_f)
        n1 = len(out)
        out = join_events(out, event_feats)
        n2 = len(out)
        out = add_calendar_features(out, events, launch)
        out = add_lag_features(out, trips_train)
        audits[name] = {"rows_input": n0, "rows_after_weather_join": n1, "rows_after_event_join": n2,
                        "weather": w_audit,
                        "zone_hours_in_event_window": int((out["n_events"] > 0).sum()),
                        "zone_hours_on_holiday": int(out["is_public_holiday"].sum())}
        tables[name] = out

    id_train = ["record_id", *KEY]
    id_test = ["row_id", *KEY]
    info_cols = ["weather_source", "lag_count"]
    master_train = tables["train"][id_train + [config.TARGET] + config.OPERATIONAL_COLS + FEATURES + info_cols]
    master_test = tables["test"][id_test + FEATURES + info_cols]

    event_audit = event_join_audit(events, windows, master_train[KEY], master_test[KEY])
    gap_summary = gaps.groupby(["gap_type", "zone"]).size().unstack("gap_type", fill_value=0)

    return {
        "master_train": master_train.reset_index(drop=True),
        "master_test": master_test.reset_index(drop=True),
        "events_clean": events,
        "weather_features": weather_f,
        "event_windows": windows,
        "event_audit": event_audit,
        "join_audit": audits,
        "target_rows_dropped": target_dropped,
        "gap_summary": gap_summary,
        "launch": launch,
    }


# --------------------------------------------------------------------------- documentation tables


def feature_table() -> pd.DataFrame:
    """A6: name, formula, source columns, why it helps, known at forecast time."""
    return pd.DataFrame(FEATURE_SPECS)[["name", "group", "formula", "source", "why", "known_at_forecast_time"]]


_BASE_COLUMNS = [
    ("record_id", "train", "Original train row id (lowest id kept when duplicates were merged)", "raw record_id", "n/a"),
    ("row_id", "test", "Test row id; join key for the submission", "raw row_id", "n/a"),
    ("zone", "trips", "Canonical zone label (12 values)", "normalize_zone(raw zone)", "yes"),
    ("pickup_hour", "trips", "Start of the hour, Addis Ababa local time (EAT, naive)", "parsed from 3 raw formats", "yes"),
    ("trips", "train", "TARGET: trips requested in the zone-hour", "sentinels -> NaN, x8 spikes / 8, duplicates averaged", "no (target)"),
    ("avg_fare_birr", "train", "Average fare (analysis/demo only, NOT a model input)", "raw, duplicates averaged", "no"),
    ("avg_wait_min", "train", "Average wait (analysis only, NOT a model input)", "-1 -> NaN, duplicates averaged", "no"),
    ("active_drivers", "train", "Active drivers (analysis only, NOT a model input)", "raw, duplicates averaged", "no"),
    ("weather_source", "weather", "observed (history) or forecast (1-14 Nov); info only", "weather.data_type", "yes"),
    ("lag_count", "trips history", "How many of the 4 lags were found before filling; info only", "count of non-missing lags", "yes"),
]


def data_dictionary(master_train: pd.DataFrame, master_test: pd.DataFrame) -> pd.DataFrame:
    """A8: every master column with type, source, description, derivation and role."""
    rows = []
    for name, source, desc, derivation, known in _BASE_COLUMNS:
        table = master_train if name in master_train else master_test
        rows.append({"column": name, "dtype": str(table[name].dtype), "in_train": name in master_train,
                     "in_test": name in master_test, "source": source, "description": desc,
                     "derivation": derivation, "known_at_forecast_time": known, "model_feature": False})
    for spec in FEATURE_SPECS:
        rows.append({"column": spec["name"], "dtype": str(master_train[spec["name"]].dtype), "in_train": True,
                     "in_test": True, "source": spec["source"], "description": spec["why"],
                     "derivation": spec["formula"], "known_at_forecast_time": spec["known_at_forecast_time"],
                     "model_feature": True})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- evidence helpers


def baseline_profile(master_train: pd.DataFrame) -> pd.Series:
    """Mean trips per zone x weekday x hour over hours with no event and no holiday."""
    quiet = master_train[(master_train["n_events"] == 0) & (master_train["is_public_holiday"] == 0)]
    return quiet.groupby(["zone", "day_of_week", "hour"])[config.TARGET].mean()


def event_offset_profile(master_train: pd.DataFrame, events: pd.DataFrame, event_type: str,
                         offsets: range = range(-4, 7), active: int = 1) -> pd.DataFrame:
    """Mean trips / baseline by hour offset from event start, in the event's zones.

    Used as clock evidence for the events table (A2c) and for the cancelled-event check (A4).
    """
    base = baseline_profile(master_train)
    trips = master_train.set_index(KEY)[config.TARGET]
    sel = events[(events["event_type"] == event_type) & (events["is_active"] == active)]
    rows = []
    for ev in sel.itertuples(index=False):
        for zone in ev.zones:
            for k in offsets:
                h = ev.start.floor("h") + pd.Timedelta(hours=k)
                if (zone, h) in trips.index:
                    b = base.get((zone, h.dayofweek, h.hour))
                    if b and b > 0:
                        rows.append({"offset_h": k, "ratio": trips[(zone, h)] / b})
    if not rows:
        return pd.DataFrame(columns=["offset_h", "mean_ratio", "n"])
    return (pd.DataFrame(rows).groupby("offset_h")["ratio"].agg(mean_ratio="mean", n="size")
            .round(3).reset_index())
