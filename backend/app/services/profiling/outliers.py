from dataclasses import dataclass
from typing import Callable

import pandas as pd

from app.schemas.data_profile_schema import OutlierReport

_MAX_SAMPLE_OUTLIER_ROWS = 50


class UnknownOutlierMethodError(Exception):
    """Raised when a requested outlier detection method isn't registered."""


@dataclass
class OutlierMethodResult:
    q1: float
    q3: float
    iqr: float
    lower_bound: float
    upper_bound: float
    outlier_row_indices: list[int]


def detect_outliers_iqr(series: pd.Series) -> OutlierMethodResult:
    non_null_values = series.dropna()
    if non_null_values.empty:
        return OutlierMethodResult(
            q1=0.0, q3=0.0, iqr=0.0, lower_bound=0.0, upper_bound=0.0, outlier_row_indices=[]
        )

    q1 = float(non_null_values.quantile(0.25))
    q3 = float(non_null_values.quantile(0.75))
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    is_outlier = (series < lower_bound) | (series > upper_bound)
    outlier_row_indices = [
        position for position, flagged in enumerate(is_outlier.to_numpy()) if flagged
    ]

    return OutlierMethodResult(
        q1=q1, q3=q3, iqr=iqr, lower_bound=lower_bound, upper_bound=upper_bound,
        outlier_row_indices=outlier_row_indices,
    )


# Registering a future method (Z-Score, Isolation Forest, LOF, ...) is one more
# entry here; nothing else in the profiling API needs to change.
OUTLIER_DETECTORS: dict[str, Callable[[pd.Series], OutlierMethodResult]] = {
    "iqr": detect_outliers_iqr,
}


def _run_detector(series: pd.Series, method: str) -> OutlierMethodResult:
    detector = OUTLIER_DETECTORS.get(method)
    if detector is None:
        raise UnknownOutlierMethodError(f"Unknown outlier detection method '{method}'.")
    return detector(series)


def build_outlier_report(series: pd.Series, column_name: str, method: str = "iqr") -> OutlierReport:
    result = _run_detector(series, method)
    row_count = len(series)
    outlier_count = len(result.outlier_row_indices)

    return OutlierReport(
        column_name=column_name,
        detection_method=method,
        q1=result.q1,
        q3=result.q3,
        iqr=result.iqr,
        lower_bound=result.lower_bound,
        upper_bound=result.upper_bound,
        outlier_count=outlier_count,
        outlier_percentage=(outlier_count / row_count * 100) if row_count else 0.0,
        sample_outlier_row_indices=result.outlier_row_indices[:_MAX_SAMPLE_OUTLIER_ROWS],
    )


def get_outlier_row_indices(series: pd.Series, method: str = "iqr") -> list[int]:
    return _run_detector(series, method).outlier_row_indices
