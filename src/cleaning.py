"""Cleaning for the three raw tables (Deliverable A1, A2).

Every function takes a raw table read with ``load_raw`` (all columns as text) and returns a
clean table. Each fix is recorded in a ``CleaningLog`` so the A1 cleaning log is produced by
the same code that does the cleaning.

Clock convention: every cleaned timestamp is a naive ``datetime64`` in Addis Ababa local time
(EAT, UTC+3, no daylight saving). See ``reports/A_cleaning_and_integration.md`` (A2c) for the
evidence behind each table's source clock.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from src import config

# --------------------------------------------------------------------------- loading


def load_raw(path: Path) -> pd.DataFrame:
    """Read a raw CSV with every column as text so nothing is silently coerced or dropped."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


# --------------------------------------------------------------------------- cleaning log


@dataclass
class CleaningLog:
    """Collects one row per cleaning issue (Deliverable A1)."""

    rows: list[dict] = field(default_factory=list)

    def add(self, file: str, columns: str, issue: str, n_affected: int, n_total: int,
            fix: str, reason: str) -> None:
        self.rows.append({
            "file": file,
            "columns": columns,
            "issue": issue,
            "rows_affected": int(n_affected),
            "pct_affected": round(100 * n_affected / n_total, 2) if n_total else 0.0,
            "fix": fix,
            "reason": reason,
        })

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows)


# --------------------------------------------------------------------------- zone labels


def normalize_zone(value: str) -> str | None:
    """Map one raw zone spelling to a canonical label, or None if it is not a known zone.

    Handles case, extra/trailing whitespace, a parenthetical sub-city suffix such as
    "Kazanchis (Kirkos)", and the known alternative spellings in ``config.ZONE_ALIASES``.
    """
    key = re.sub(r"\(.*?\)", "", value)          # drop "(Kirkos)", "(Bole subcity)", ...
    key = re.sub(r"\s+", " ", key).strip().lower()
    key = config.ZONE_ALIASES.get(key, key)
    by_lower = {z.lower(): z for z in config.ZONES}
    return by_lower.get(key.lower())


def parse_event_zones(value: str) -> list[str]:
    """Turn an event-table zone cell into a list of canonical zones.

    The cell may name one zone, several zones joined by "&" or ",", or the whole city.
    Unknown tokens are dropped (the caller logs how many events end up with no zone).
    """
    text = value.strip()
    if text.lower() in config.CITYWIDE_ZONE_TOKENS:
        return list(config.ZONES)
    zones = [normalize_zone(part) for part in re.split(r"[&,/]", text)]
    return sorted({z for z in zones if z is not None})


# --------------------------------------------------------------------------- timestamps


@dataclass(frozen=True)
class TimeFormat:
    """One timestamp layout found in a raw table."""

    name: str
    regex: str          # full-match pattern used to route a row to this format
    strptime: str | None  # explicit format string; None = ISO-8601 with UTC offset
    source_clock: str   # "local" (EAT), "utc", or "offset" (offset written in the string)


TRIP_FORMATS = [
    TimeFormat("YYYY-MM-DD HH:MM", r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", "%Y-%m-%d %H:%M", "local"),
    TimeFormat("DD/MM/YYYY HH:MM", r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", "%d/%m/%Y %H:%M", "local"),
    TimeFormat("ISO-8601 +03:00", r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}", None, "offset"),
]
WEATHER_FORMATS = [
    TimeFormat("YYYY-MM-DDTHH:MM:SSZ", r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", "%Y-%m-%dT%H:%M:%SZ", "utc"),
    # Proven to be UTC as well, not local (see weather_clock_evidence).
    TimeFormat("DD/MM/YYYY HH:MM", r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", "%d/%m/%Y %H:%M", "utc"),
]
EVENT_FORMATS = [
    TimeFormat("YYYY-MM-DD HH:MM", r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", "%Y-%m-%d %H:%M", "local"),
    TimeFormat("DD/MM/YYYY HH:MM", r"\d{2}/\d{2}/\d{4} \d{2}:\d{2}", "%d/%m/%Y %H:%M", "local"),
    TimeFormat("Mon DD, YYYY HH:MM AM", r"[A-Z][a-z]{2} \d{2}, \d{4} \d{2}:\d{2} [AP]M", "%b %d, %Y %I:%M %p", "local"),
]


def parse_mixed_timestamps(values: pd.Series, formats: list[TimeFormat]) -> tuple[pd.Series, pd.Series]:
    """Parse a column written in several layouts into naive local (EAT) timestamps.

    Each row is routed to exactly one format by regex, parsed with an explicit format string
    (so a day-first date can never be read month-first), then converted to local time.

    Returns ``(timestamps, format_name)``. Rows matching no format (e.g. blanks) are NaT / None.
    """
    text = values.str.strip()
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
    fmt_name = pd.Series(None, index=values.index, dtype=object)

    for fmt in formats:
        mask = text.str.fullmatch(fmt.regex) & fmt_name.isna()
        if not mask.any():
            continue
        if fmt.source_clock == "offset":
            ts = pd.to_datetime(text[mask], utc=True).dt.tz_convert(config.LOCAL_TZ).dt.tz_localize(None)
        else:
            ts = pd.to_datetime(text[mask], format=fmt.strptime)
            if fmt.source_clock == "utc":
                ts = ts.dt.tz_localize("UTC").dt.tz_convert(config.LOCAL_TZ).dt.tz_localize(None)
        parsed[mask] = ts
        fmt_name[mask] = fmt.name

    return parsed, fmt_name


def slash_date_check(values: pd.Series) -> dict:
    """Evidence that DD/MM/YYYY strings are day-first: count first/second fields above 12."""
    parts = values[values.str.contains("/", regex=False)].str.strip().str.split("/")
    first = parts.str[0].astype(int)
    second = parts.str[1].astype(int)
    return {
        "n_slash_rows": int(len(parts)),
        "first_field_gt_12": int((first > 12).sum()),
        "second_field_gt_12": int((second > 12).sum()),
        "second_field_max": int(second.max()) if len(second) else None,
    }


# --------------------------------------------------------------------------- trips


def clean_trips(raw: pd.DataFrame, log: CleaningLog, file: str) -> pd.DataFrame:
    """Clean the train or test trip table.

    Train and test share the key steps (zone, timestamp); the value steps only run when the
    operational columns are present (train file).
    """
    df = raw.copy()
    n = len(df)
    is_train = config.TARGET in df.columns

    # 1. Zone spelling -> 12 canonical labels.
    df["zone_raw"] = df["zone"]
    df["zone"] = df["zone_raw"].map(normalize_zone)
    unmapped = df["zone"].isna()
    if unmapped.any():
        raise ValueError(f"{file}: unmapped zone values {sorted(df.loc[unmapped, 'zone_raw'].unique())}")
    changed = (df["zone"] != df["zone_raw"]).sum()
    log.add(file, "zone", f"Inconsistent zone spelling ({df['zone_raw'].nunique()} raw variants: case, "
            "trailing spaces, double spaces, aliases such as C.M.C, Piazza, Mercato, Bole Rd)",
            changed, n, "Normalised whitespace/case and mapped aliases to the 12 canonical labels",
            "Every table must share one zone key for the joins")

    # 2. Timestamps in three layouts -> naive local time.
    df["pickup_hour"], df["ts_format"] = parse_mixed_timestamps(df["pickup_hour"], TRIP_FORMATS)
    if df["pickup_hour"].isna().any():
        raise ValueError(f"{file}: {df['pickup_hour'].isna().sum()} unparsed pickup_hour values")
    non_iso = (df["ts_format"] != TRIP_FORMATS[0].name).sum()
    log.add(file, "pickup_hour", "Timestamps in 3 formats (YYYY-MM-DD HH:MM, day-first DD/MM/YYYY HH:MM, "
            "ISO-8601 with +03:00 offset)", non_iso, n,
            "Parsed each format with an explicit format string; offset rows converted to local time",
            "Avoids day/month swaps and puts every row on the EAT clock")

    if not is_train:
        return df[["row_id", "zone", "pickup_hour"]].reset_index(drop=True)

    for col in ["trips", "avg_fare_birr", "avg_wait_min", "active_drivers"]:
        df[col] = pd.to_numeric(df[col].str.strip().replace("", np.nan), errors="raise")

    # 3. Missing target.
    n_missing = df["trips"].isna().sum()
    log.add(file, "trips", "Missing target (blank)", n_missing, n,
            "Kept as NaN; zone-hours with no valid trips are excluded from training rows",
            "Imputing the target would invent training labels")

    # 4. Sentinel -1 in trips.
    sentinel = df["trips"] == config.TRIPS_SENTINEL
    df.loc[sentinel, "trips"] = np.nan
    log.add(file, "trips", "Sentinel value -1 (impossible negative count)", sentinel.sum(), n,
            "Set to NaN, then treated as missing target", "-1 is a 'no reading' code, not a count")

    # 5. Trips recorded x8: trips per active driver far above the physical maximum.
    ratio = df["trips"] / df["active_drivers"]
    scaled = ratio > config.TRIPS_PER_DRIVER_MAX
    df.loc[scaled, "trips"] = (df.loc[scaled, "trips"] / config.TRIPS_SCALE_ERROR).round()
    log.add(file, "trips", f"Spikes recorded x{config.TRIPS_SCALE_ERROR} (trips/active_drivers > "
            f"{config.TRIPS_PER_DRIVER_MAX}; clean rows never exceed 2.0; 99% of flagged values are "
            "multiples of 8)", scaled.sum(), n,
            f"Divided by {config.TRIPS_SCALE_ERROR} and rounded",
            "A driver cannot serve 10+ trips an hour; genuine event spikes keep a normal ratio "
            "because active_drivers rises with them, so they are untouched")

    # 6. Sentinel -1 in avg_wait_min.
    wait_sentinel = df["avg_wait_min"] == config.WAIT_SENTINEL
    df.loc[wait_sentinel, "avg_wait_min"] = np.nan
    log.add(file, "avg_wait_min", "Sentinel value -1", wait_sentinel.sum(), n,
            "Set to NaN (analysis only; not a model input)", "A wait time cannot be negative")

    # 7. Missing fare.
    log.add(file, "avg_fare_birr", "Missing values (blank)", df["avg_fare_birr"].isna().sum(), n,
            "Left as NaN; the demo uses each zone's mean fare over non-missing rows",
            "Fare is analysis/demo only and must not be invented row by row")

    # 8. Duplicate zone-hours: exact copies and copies whose trips differ by 1-3.
    key = ["zone", "pickup_hour"]
    dup_mask = df.duplicated(key, keep=False)
    value_cols = ["trips", "avg_fare_birr", "avg_wait_min", "active_drivers"]
    n_conflicting = (df[dup_mask].groupby(key)["trips"].nunique(dropna=True) > 1).sum()
    n_extra = df.duplicated(key).sum()
    df = (df.sort_values("record_id")
            .groupby(key, as_index=False)
            .agg(record_id=("record_id", "first"), **{c: (c, "mean") for c in value_cols}))
    log.add(file, "zone, pickup_hour", f"Duplicate zone-hour keys ({n_extra} extra rows; "
            f"{n_conflicting} keys disagree on trips by 1-3)", n_extra, n,
            "Collapsed to one row per zone-hour; numeric columns averaged (NaN ignored), lowest record_id kept",
            "The model needs exactly one target per zone-hour; averaging splits the small disagreement")

    return df[["record_id", "zone", "pickup_hour", *value_cols]].reset_index(drop=True)


def classify_missing_hours(trips: pd.DataFrame, log: CleaningLog, file: str) -> pd.DataFrame:
    """Label every zone-hour absent from the cleaned history (B4.2, A1).

    * ``outage``          - an hour with no rows in any zone (platform down)
    * ``pre_launch``      - before a zone's first ever record (zone not operating yet)
    * ``missing_record``  - any other isolated missing zone-hour
    """
    hours = pd.date_range(config.TRAIN_START, config.TRAIN_END, freq="h")
    grid = pd.MultiIndex.from_product([config.ZONES, hours], names=["zone", "pickup_hour"]).to_frame(index=False)
    present = trips[["zone", "pickup_hour"]].assign(present=True)
    grid = grid.merge(present, on=["zone", "pickup_hour"], how="left")
    missing = grid[grid["present"].isna()].drop(columns="present")

    outage_hours = set(hours.difference(trips["pickup_hour"].unique()))
    launch = trips.groupby("zone")["pickup_hour"].min()

    missing["gap_type"] = "missing_record"
    missing.loc[missing["pickup_hour"] < missing["zone"].map(launch), "gap_type"] = "pre_launch"
    missing.loc[missing["pickup_hour"].isin(outage_hours), "gap_type"] = "outage"

    counts = missing["gap_type"].value_counts()
    log.add(file, "zone, pickup_hour", "Zone-hours with no row at all "
            f"(outage {counts.get('outage', 0)}, pre-launch {counts.get('pre_launch', 0)}, "
            f"random {counts.get('missing_record', 0)})", len(missing), len(grid),
            "Not imputed as targets. Outage and pre-launch hours are excluded from training; "
            "lag features that land on any gap fall back to the train-fitted zone x weekday x hour mean",
            "Outage/pre-launch hours are not zero demand; filling them with 0 would teach the model false drops")
    return missing.reset_index(drop=True)


# --------------------------------------------------------------------------- weather


def _run_lengths(is_missing: pd.Series) -> pd.Series:
    """Length of the consecutive-missing run each row belongs to (0 for present rows)."""
    run_id = (is_missing != is_missing.shift()).cumsum()
    lengths = is_missing.groupby(run_id).transform("sum")
    return lengths.where(is_missing, 0)


def clean_weather(raw: pd.DataFrame, log: CleaningLog, file: str = "weather_hourly.csv") -> pd.DataFrame:
    """Clean the hourly weather table and return one row per local hour, 1 Jan - 14 Nov 2025."""
    df = raw.copy()
    n = len(df)
    num_cols = ["temp_c", "rain_mm", "humidity_pct", "wind_kmh"]

    # 1. Two timestamp layouts, both on UTC -> local time.
    df["timestamp_local"], df["ts_format"] = parse_mixed_timestamps(df["timestamp"], WEATHER_FORMATS)
    if df["timestamp_local"].isna().any():
        raise ValueError(f"{file}: unparsed timestamps")
    log.add(file, "timestamp", "Timestamps on UTC, not local time, in 2 formats "
            f"({(df['ts_format'] == WEATHER_FORMATS[1].name).sum()} rows DD/MM/YYYY without a 'Z')",
            n, n, "Parsed both formats as UTC and converted to Africa/Addis_Ababa (+3 h)",
            "Trip hours are local; joining on raw UTC would attach weather 3 hours off "
            "(evidence: temperature peak, forecast block start, slash-row alignment)")

    for col in num_cols:
        df[col] = pd.to_numeric(df[col].str.strip().replace("", np.nan), errors="raise")
    df["data_type"] = df["data_type"].str.strip().str.lower()

    # 2. Rain sentinel.
    rain_sentinel = df["rain_mm"] == config.RAIN_SENTINEL
    df.loc[rain_sentinel, "rain_mm"] = np.nan
    log.add(file, "rain_mm", f"Sentinel value {config.RAIN_SENTINEL}", rain_sentinel.sum(), n,
            "Set to NaN, then imputed with the hour-gap rules below", "No-reading code, not rainfall")

    # 3. Fahrenheit block.
    fahrenheit = df["temp_c"] > config.TEMP_MAX_PLAUSIBLE_C
    df.loc[fahrenheit, "temp_c"] = ((df.loc[fahrenheit, "temp_c"] - 32) * 5 / 9).round(1)
    span = df.loc[fahrenheit, "timestamp_local"]
    log.add(file, "temp_c", "Temperature in Fahrenheit for a contiguous block "
            f"({span.min():%Y-%m-%d %H:%M} to {span.max():%Y-%m-%d %H:%M} local; values 45-77)",
            fahrenheit.sum(), n, "Converted with (F - 32) x 5/9",
            f"Addis Ababa never exceeds ~{config.TEMP_MAX_PLAUSIBLE_C:.0f} C; converted values match the "
            "neighbouring Celsius hours")

    # 4. Missing values.
    for col in ["temp_c", "humidity_pct"]:
        n_blank = raw[col].str.strip().eq("").sum()
        log.add(file, col, "Missing values (blank)", n_blank, n,
                "Imputed with the hour-gap rules below", "Model needs a value for every hour")

    # 5. Duplicate hours with conflicting readings.
    n_dup = df.duplicated("timestamp_local").sum()
    df = (df.groupby("timestamp_local", as_index=False)
            .agg(**{c: (c, "mean") for c in num_cols}, data_type=("data_type", "first")))
    df[num_cols] = df[num_cols].round(1)
    log.add(file, "timestamp", "Duplicate hours with conflicting readings", n_dup, n,
            "Averaged the readings for that hour (NaN ignored)",
            "Weather must be one row per hour so the join is many-to-one")

    # 6. Missing hours -> full hourly grid.
    grid = pd.DataFrame({"timestamp_local": pd.date_range(config.TRAIN_START, config.TEST_END, freq="h")})
    df = grid.merge(df, on="timestamp_local", how="left")
    hour_missing = df["data_type"].isna()
    run = _run_lengths(hour_missing)
    df["data_type"] = np.where(df["timestamp_local"] >= pd.Timestamp(config.TEST_START), "forecast", "observed")
    log.add(file, "timestamp", f"Missing hours ({hour_missing.sum()} hours; longest gap {int(run.max())} h)",
            hour_missing.sum(), len(grid),
            f"Re-indexed to a full hourly grid; gaps <= {config.WEATHER_INTERP_LIMIT_H} h interpolated, "
            "longer gaps filled with month x hour climatology; rain gaps set to 0; flagged weather_imputed",
            "Every zone-hour needs weather; climatology keeps the daily temperature cycle in long gaps")

    df = _impute_weather(df, num_cols)
    return df


def _impute_weather(df: pd.DataFrame, num_cols: list[str]) -> pd.DataFrame:
    """Fill NaN weather values: short gaps by interpolation, long gaps by climatology, rain by 0.

    Climatology is fitted on observed (history) rows only (Rule 8).
    """
    df = df.copy()
    df["weather_imputed"] = df[num_cols].isna().any(axis=1).astype(int)

    observed = df["data_type"] == "observed"
    month, hour = df["timestamp_local"].dt.month, df["timestamp_local"].dt.hour
    for col in ["temp_c", "humidity_pct", "wind_kmh"]:
        missing = df[col].isna()
        short = missing & (_run_lengths(missing) <= config.WEATHER_INTERP_LIMIT_H)
        interpolated = df[col].interpolate(limit_area="inside")
        df.loc[short, col] = interpolated[short]

        clim = df[observed].groupby([month[observed], hour[observed]])[col].mean()
        hourly = df[observed].groupby(hour[observed])[col].mean()
        fill = pd.Series(list(zip(month, hour)), index=df.index).map(clim).fillna(hour.map(hourly))
        df[col] = df[col].fillna(fill.round(1))

    df["rain_mm"] = df["rain_mm"].fillna(0.0)
    return df


def weather_clock_evidence(raw: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Data evidence for the weather clock (A2c, B2.1).

    * mean temperature by raw hour vs by local hour (Addis peaks mid-afternoon local time)
    * mean absolute difference between slash-format rows and the 'Z' series at hour shifts
    """
    df = raw.copy()
    df["temp"] = pd.to_numeric(df["temp_c"].str.strip().replace("", np.nan))
    df = df[df["temp"] <= config.TEMP_MAX_PLAUSIBLE_C]
    raw_ts, fmt = parse_mixed_timestamps(df["timestamp"], WEATHER_FORMATS)
    raw_utc = raw_ts - pd.Timedelta(hours=3)      # undo the conversion to get the raw clock reading

    by_hour = pd.DataFrame({
        "raw_clock_mean_temp": df.groupby(raw_utc.dt.hour)["temp"].mean(),
        "local_clock_mean_temp": df.groupby(raw_ts.dt.hour)["temp"].mean(),
    }).round(2).rename_axis("hour")

    peak_by_format = pd.DataFrame([
        {"format": f.name, "rows": int((fmt == f.name).sum()),
         "peak_hour_raw_clock": int(df[fmt == f.name].groupby(raw_utc[fmt == f.name].dt.hour)["temp"].mean().idxmax())}
        for f in WEATHER_FORMATS
    ])
    peak_by_format["peak_hour_if_utc_in_local"] = (peak_by_format["peak_hour_raw_clock"] + 3) % 24

    z_series = (df[fmt == WEATHER_FORMATS[0].name].assign(t=raw_utc).drop_duplicates("t").set_index("t")["temp"])
    slash = df[fmt == WEATHER_FORMATS[1].name].assign(t=raw_utc)
    rows = []
    for shift in range(-4, 5):
        ref = z_series.reindex(slash["t"] + pd.Timedelta(hours=shift)).to_numpy()
        diff = np.abs(slash["temp"].to_numpy() - ref)
        rows.append({"shift_h": shift, "mae_temp_c": round(float(np.nanmean(diff)), 2),
                     "n_pairs": int(np.isfinite(diff).sum())})
    return {"temp_by_hour": by_hour, "peak_by_format": peak_by_format, "slash_alignment": pd.DataFrame(rows)}


# --------------------------------------------------------------------------- events


def normalize_event_type(value: str) -> str:
    return re.sub(r"[\s\-]+", "_", value.strip().lower())


def clean_events(raw: pd.DataFrame, log: CleaningLog, file: str = "events_calendar.csv") -> pd.DataFrame:
    """Clean the events calendar. Returns one row per event with a list of affected zones."""
    df = raw.copy()
    n = len(df)
    for col in df.columns:
        df[col] = df[col].str.strip()

    # 1. Event type spelling.
    raw_types = df["event_type"].nunique()
    df["event_type"] = raw["event_type"].map(normalize_event_type)
    unknown = set(df["event_type"]) - set(config.EVENT_TYPES)
    if unknown:
        raise ValueError(f"{file}: unknown event types {unknown}")
    log.add(file, "event_type", f"Inconsistent spelling ({raw_types} variants for 8 types: case, spaces, "
            "trailing space)", (raw["event_type"] != df["event_type"]).sum(), n,
            "Lower-cased, trimmed, spaces -> underscores", "Event type drives which features an event feeds")

    # 2. Status spelling.
    df["status"] = df["status"].str.lower()
    log.add(file, "status", "Inconsistent case / trailing spaces (confirmed, Confirmed, CONFIRMED, CANCELLED )",
            (raw["status"] != df["status"]).sum(), n, "Lower-cased and trimmed",
            "Needed to filter cancelled events reliably")

    # 3. Duplicate events re-entered under a new id (EVT-9xxx).
    content_cols = [c for c in df.columns if c != "event_id"]
    dup = df.sort_values("event_id").duplicated(content_cols)
    dup_ids = sorted(df.sort_values("event_id")[dup]["event_id"])
    df = df.sort_values("event_id")[~dup].reset_index(drop=True)
    log.add(file, "all", f"Duplicate events under a second id ({', '.join(dup_ids)})", len(dup_ids), n,
            "Dropped the copy, kept the original EVT-0xxx id",
            "A duplicate would double-count the event's attendance and window")

    # 4. Zone text -> canonical zone list.
    df["zones"] = df["zone"].map(parse_event_zones)
    no_zone = df["zones"].str.len() == 0
    if no_zone.any():
        raise ValueError(f"{file}: events with no recognised zone: {df.loc[no_zone, 'event_id'].tolist()}")
    df["zone_clean"] = df["zones"].map(";".join)
    log.add(file, "zone", "Zone in mixed spellings, with sub-city suffixes '(Kirkos)', several zones "
            "joined by '&', or the whole city ('Citywide', 'ALL', 'All zones', 'city-wide')",
            (df["zone_clean"] != df["zone"]).sum(), len(df),
            "Parsed into a list of canonical zones; citywide -> all 12 zones",
            "An event must be matched to every zone it affects")

    # 5. Start/end timestamps in 3 layouts.
    df["start"], start_fmt = parse_mixed_timestamps(df["start_datetime"], EVENT_FORMATS)
    df["end"], end_fmt = parse_mixed_timestamps(df["end_datetime"], EVENT_FORMATS)
    if df["start"].isna().any():
        raise ValueError(f"{file}: unparsed start_datetime")
    non_iso = (start_fmt != EVENT_FORMATS[0].name).sum() + ((end_fmt != EVENT_FORMATS[0].name) & end_fmt.notna()).sum()
    log.add(file, "start_datetime, end_datetime", "Timestamps in 3 formats (ISO, day-first DD/MM/YYYY, "
            "'Mon DD, YYYY HH:MM AM/PM')", non_iso, 2 * len(df),
            "Parsed each format with an explicit format string (local time)", "Avoids day/month swaps")

    # 6. Missing or reversed end -> start + median duration of that type.
    duration = df["end"] - df["start"]
    bad_end = df["end"].isna() | (duration <= pd.Timedelta(0))
    median_dur = duration[~bad_end].groupby(df.loc[~bad_end, "event_type"]).median()
    df["end_imputed"] = bad_end.astype(int)
    df.loc[bad_end, "end"] = df.loc[bad_end, "start"] + df.loc[bad_end, "event_type"].map(median_dur)
    log.add(file, "end_datetime", f"End missing ({df['end_datetime'].eq('').sum()}) or earlier than start "
            f"({(bad_end & df['end_datetime'].ne('')).sum()})", bad_end.sum(), len(df),
            "Set end = start + median duration of the same event type", "Every event needs a window to join on")

    # 7. Free-text attendance.
    att = df["expected_attendance"].str.lower().str.replace(r"approx\.?|~|,", "", regex=True).str.strip()
    df["attendance"] = pd.to_numeric(att.replace("", np.nan), errors="raise")
    text_rows = df["expected_attendance"].str.contains(r"[^\d]", regex=True) & df["expected_attendance"].ne("")
    log.add(file, "expected_attendance", f"Free text ('approx 34000', '34,756') and blanks "
            f"({df['attendance'].isna().sum()} blank)", text_rows.sum() + df["attendance"].isna().sum(), len(df),
            "Stripped 'approx' and thousands separators -> number; blanks filled at feature time with the "
            "median attendance of the same event type", "Attendance is used as a numeric feature")

    # 8. Cancelled events.
    df["is_active"] = (df["status"] == "confirmed").astype(int)
    log.add(file, "status", "Cancelled events listed in the calendar", (df["is_active"] == 0).sum(), len(df),
            "Kept in the clean table but excluded from event features",
            "A cancelled event should not leave a demand footprint (checked against trips in A4)")

    return df[["event_id", "event_name", "event_type", "venue", "zone_clean", "zones", "start", "end",
               "end_imputed", "attendance", "status", "is_active"]]
