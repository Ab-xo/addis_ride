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
