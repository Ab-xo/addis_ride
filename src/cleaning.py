"""Cleaning for the three raw tables (Deliverable A1/A2).

Every fix should also append a row to the cleaning log: file, columns, issue, rows affected, fix, why.
"""
import pandas as pd


def clean_trips(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise zone labels, parse pickup_hour (multiple formats, local time), drop duplicates, fix bad trips."""
    raise NotImplementedError


def clean_weather(df: pd.DataFrame) -> pd.DataFrame:
    """Parse timestamps, convert to local clock, resolve duplicate hours, sentinels and unit changes."""
    raise NotImplementedError


def clean_events(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise event_type/zone, parse start/end, fix missing or reversed ends, parse attendance."""
    raise NotImplementedError
