# team_addis_ride — Addis Ride Demand Forecasting

**Team:** _TODO: team name_
**Members:** _TODO: name (role)_, _name (role)_, _name (role)_

## Summary
_TODO: one paragraph — problem, how the three tables were cleaned and joined, final model, validation score._

Forecast hourly trips for 12 Addis Ababa zones for 1–14 Nov 2025 from trip history (1 Jan – 31 Oct 2025),
hourly weather and a city events calendar.

## Setup
```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
```

## Run order
Run from the project root; all paths are relative.

1. `notebooks/01_cleaning_and_integration.ipynb` → `data/processed/master_*.csv`, data dictionary (A)
2. `notebooks/02_analysis_report.ipynb` → B1.1–B4.3 (B)
3. `notebooks/03_visualizations.ipynb` → `figures/fig01–fig12` (C)
4. `notebooks/04_modeling_and_evaluation.ipynb` → `models/final_model.joblib`, `submission/team_addis_ride_submission.csv` (D)
5. Demo: `streamlit run app/app.py` (E)

## Where each deliverable lives
| Deliverable | Location |
|---|---|
| Prediction file | `submission/team_addis_ride_submission.csv` |
| A — Pipeline | `notebooks/01_...`, `reports/A_cleaning_and_integration.md`, `data/processed/` |
| B — Analysis | `notebooks/02_...`, `reports/B_analysis_report.md` |
| C — Visualizations | `notebooks/03_...`, `figures/`, `figures/figure_captions.md` |
| D — Modeling | `notebooks/04_...`, `reports/D_model_evaluation.md`, `models/` |
| E — Demo | `app/` — URL: _TODO (or "runs locally")_ |
| F — Slides | `presentation/team_addis_ride_slides.pdf` |
| G — Structure | this README, `requirements.txt` |

## Results
- Final validation RMSE / MAE: _TODO_ (split: _TODO dates_)
- Demo: _TODO URL_ / local: `streamlit run app/app.py`
