"""Joins and feature engineering (Deliverable A3–A6). Same code path for train and test."""
import pandas as pd


def join_weather(trips: pd.DataFrame, weather: pd.DataFrame) -> pd.DataFrame:
    """Many-to-one join on local hour. Row count must not change."""
    raise NotImplementedError


def join_events(trips: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Interval join: flag hours before / during / after each event in its zone(s)."""
    raise NotImplementedError


def add_calendar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Hour, day of week, weekend, holiday, payday, trend index."""
    raise NotImplementedError
