"""Project-wide constants and relative paths. Import this instead of hard-coding paths."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
FIGURES = ROOT / "figures"
MODELS = ROOT / "models"
REPORTS = ROOT / "reports"
SUBMISSION = ROOT / "submission"
APP_ASSETS = ROOT / "app" / "assets"

RAW_TRAIN = DATA_RAW / "ride_demand_train.csv"
RAW_TEST = DATA_RAW / "ride_demand_test.csv"
RAW_WEATHER = DATA_RAW / "weather_hourly.csv"
RAW_EVENTS = DATA_RAW / "events_calendar.csv"
RAW_TEMPLATE = DATA_RAW / "submission_template.csv"

MASTER_TRAIN = DATA_PROCESSED / "master_train.csv"
MASTER_TEST = DATA_PROCESSED / "master_test.csv"
DATA_DICTIONARY = DATA_PROCESSED / "data_dictionary_master.csv"
FINAL_MODEL = MODELS / "final_model.joblib"

TEAM_NAME = "addis_ride"
SUBMISSION_FILE = SUBMISSION / f"team_{TEAM_NAME}_submission.csv"

# All tables are converted to this clock before joining (Africa/Addis_Ababa = UTC+3, no DST).
LOCAL_TZ = "Africa/Addis_Ababa"

TRAIN_START = "2025-01-01 00:00"
TRAIN_END = "2025-10-31 23:00"
TEST_START = "2025-11-01 00:00"
TEST_END = "2025-11-14 23:00"

N_ZONES = 12
TRIPS_PER_DRIVER_HOUR = 1.3
RANDOM_STATE = 42

# Columns that exist only in history — never model inputs (Rule 6, D4).
OPERATIONAL_COLS = ["avg_fare_birr", "avg_wait_min", "active_drivers"]
TARGET = "trips"

# Pipeline outputs written for the Deliverable A report.
REPORT_A = REPORTS / "A_cleaning_and_integration.md"
REPORT_A_TABLES = REPORTS / "A_tables"

# --------------------------------------------------------------------------- zones
# The 12 canonical zone labels shared by every table (A2a).
ZONES = [
    "Arat Kilo", "Ayat", "Bole", "CMC", "Gerji", "Kazanchis",
    "Kolfe", "Lideta", "Megenagna", "Merkato", "Piassa", "Sarbet",
]

# Alternative spellings / sub-city names seen in the raw files -> canonical label.
# Keys are lower-case with single spaces and no parenthetical suffix.
ZONE_ALIASES = {
    "c.m.c": "CMC",
    "bole rd": "Bole",
    "kolfe keranio": "Kolfe",
    "mercato": "Merkato",
    "kazanches": "Kazanchis",
    "megenaga": "Megenagna",
    "piazza": "Piassa",
}

# Event-table zone values that mean "every zone".
CITYWIDE_ZONE_TOKENS = {"citywide", "city-wide", "all", "all zones"}

# --------------------------------------------------------------------------- cleaning rules
# Sentinel codes meaning "no reading".
TRIPS_SENTINEL = -1
WAIT_SENTINEL = -1
RAIN_SENTINEL = -9999

# trips / active_drivers never exceeds ~2 in clean rows (99.5th pct = 1.76); rows above
# this ratio are trips recorded x8 (99% of them are exact multiples of 8).
TRIPS_PER_DRIVER_MAX = 2.5
TRIPS_SCALE_ERROR = 8

# Highest plausible Addis Ababa air temperature in Celsius; above this a reading is Fahrenheit.
TEMP_MAX_PLAUSIBLE_C = 40.0

# Weather gaps up to this many hours are linearly interpolated; longer gaps use climatology.
WEATHER_INTERP_LIMIT_H = 3

# --------------------------------------------------------------------------- events
EVENT_TYPES = [
    "public_holiday", "school_break", "football_match", "concert",
    "conference", "exhibition", "road_closure", "sports_run",
]
# Day-level calendar periods (turned into calendar flags, not zone event windows).
CALENDAR_EVENT_TYPES = {"public_holiday", "school_break"}

# Event window: demand can rise before an event and especially after it ends (A3).
EVENT_PRE_HOURS = 2
EVENT_POST_HOURS = 2

# Cap for hours-until / hours-since event features (beyond this the event is irrelevant).
EVENT_HOURS_CAP = 24

# --------------------------------------------------------------------------- features
# Rain classes in mm/h: none (0), light (<=1), moderate (<=4), heavy (>4).
RAIN_CLASS_BINS = [-0.01, 0.0, 1.0, 4.0, float("inf")]
RAIN_CLASS_LABELS = [0, 1, 2, 3]

# Lags must be >= the forecast horizon (14 days) so they are known for every test hour.
LAG_DAYS = [14, 21, 28, 35]
PAYDAY_LAST_DAYS = 3   # last N days of a month
PAYDAY_FIRST_DAYS = 2  # first N days of a month
