"""Prediction and submission writing/validation (Deliverable G4)."""
import pandas as pd

from src.config import RAW_TEMPLATE


def validate_submission(sub: pd.DataFrame) -> None:
    """Assert the submission matches the template exactly: columns, row_ids, order, valid predictions."""
    template = pd.read_csv(RAW_TEMPLATE)
    assert list(sub.columns) == ["row_id", "predicted_trips"], f"bad columns: {list(sub.columns)}"
    assert len(sub) == len(template), f"expected {len(template)} rows, got {len(sub)}"
    assert sub["row_id"].is_unique, "duplicate row_ids"
    assert (sub["row_id"].values == template["row_id"].values).all(), "row_ids differ from template order"
    preds = pd.to_numeric(sub["predicted_trips"], errors="coerce")
    assert preds.notna().all(), "blank or non-numeric predictions"
    assert (preds >= 0).all(), "negative predictions"
