import pandas as pd

from app.schemas.data_profile_schema import CategoricalColumnStatistics, ColumnProfile, NumericColumnStatistics
from app.services.json_safe import to_json_safe

_MAX_SAMPLE_VALUES = 5


def _none_if_nan(value: float) -> float | None:
    return None if pd.isna(value) else float(value)


def is_numeric_column(series: pd.Series) -> bool:
    """True for real numeric measures — excludes bool, which pandas otherwise
    classifies as numeric but which has no meaningful mean/quantile/etc."""
    return pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series)


def build_column_profile(series: pd.Series, column_name: str) -> ColumnProfile:
    row_count = len(series)
    missing_count = int(series.isna().sum())
    non_null_values = series.dropna()
    sample_values = [to_json_safe(value) for value in non_null_values.unique()[:_MAX_SAMPLE_VALUES]]

    return ColumnProfile(
        column_name=column_name,
        dtype=str(series.dtype),
        nullable=missing_count > 0,
        missing_count=missing_count,
        missing_percentage=(missing_count / row_count * 100) if row_count else 0.0,
        unique_count=int(non_null_values.nunique()),
        sample_values=sample_values,
    )


def build_numeric_statistics(series: pd.Series, column_name: str) -> NumericColumnStatistics | None:
    if not is_numeric_column(series):
        return None

    non_null_values = series.dropna()
    if non_null_values.empty:
        return None

    minimum = float(non_null_values.min())
    maximum = float(non_null_values.max())
    q1 = float(non_null_values.quantile(0.25))
    q3 = float(non_null_values.quantile(0.75))
    mode_values = non_null_values.mode()

    return NumericColumnStatistics(
        column_name=column_name,
        count=int(non_null_values.count()),
        mean=float(non_null_values.mean()),
        median=float(non_null_values.median()),
        mode=float(mode_values.iloc[0]) if not mode_values.empty else None,
        minimum=minimum,
        maximum=maximum,
        std_deviation=_none_if_nan(non_null_values.std()),
        variance=_none_if_nan(non_null_values.var()),
        range=maximum - minimum,
        q1=q1,
        q3=q3,
        iqr=q3 - q1,
        skewness=_none_if_nan(non_null_values.skew()),
        kurtosis=_none_if_nan(non_null_values.kurt()),
    )


def build_categorical_statistics(
    series: pd.Series, column_name: str
) -> CategoricalColumnStatistics | None:
    if is_numeric_column(series):
        return None

    row_count = len(series)
    non_null_values = series.dropna()
    unique_count = int(non_null_values.nunique())
    missing_count = row_count - len(non_null_values)

    most_frequent_value = None
    most_frequent_value_count = 0
    if not non_null_values.empty:
        value_counts = non_null_values.value_counts()
        most_frequent_value = to_json_safe(value_counts.index[0])
        most_frequent_value_count = int(value_counts.iloc[0])

    return CategoricalColumnStatistics(
        column_name=column_name,
        unique_count=unique_count,
        most_frequent_value=most_frequent_value,
        most_frequent_value_count=most_frequent_value_count,
        cardinality_ratio=(unique_count / row_count) if row_count else 0.0,
        missing_percentage=(missing_count / row_count * 100) if row_count else 0.0,
    )
