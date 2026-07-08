from typing import Any

import pandas as pd


def to_json_safe(value: Any) -> Any:
    """Convert a pandas/numpy scalar into a native, JSON-serializable Python value."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value
