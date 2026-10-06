"""Addis Ride forecast demo (Deliverable E). Run from the project root: streamlit run app/app.py"""
from datetime import date

import streamlit as st

MIN_DATE = date(2025, 11, 1)
MAX_DATE = date(2025, 11, 14)

st.set_page_config(page_title="Addis Ride Forecast", layout="wide")
st.title("Addis Ride — hourly demand forecast")

# TODO: load zone list from app/assets once the cleaning pipeline exports it.
zone = st.selectbox("Zone", ["(zones load after pipeline runs)"])
day = st.date_input("Date", value=MIN_DATE)

if not (MIN_DATE <= day <= MAX_DATE):
    st.warning("Forecasts are available for 1–14 November 2025 only. Please pick a date in that range.")
    st.stop()

st.info("Model not trained yet. TODO: load models/final_model.joblib and bundled weather/events from app/assets/.")
