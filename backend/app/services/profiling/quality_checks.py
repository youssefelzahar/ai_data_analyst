import pandas as pd

from app.schemas.data_profile_schema import DataQualityReport, HighCardinalityColumn, MixedTypeColumn
from app.services.profiling.column_analysis import is_numeric_column

_HIGH_CARDINALITY_RATIO = 0.5


def build_data_quality_report(dataframe: pd.DataFrame) -> DataQualityReport:
    row_count = len(dataframe)

    empty_columns: list[str] = []
    constant_columns: list[str] = []
    single_unique_value_columns: list[str] = []
    high_cardinality_columns: list[HighCardinalityColumn] = []
    mixed_type_columns: list[MixedTypeColumn] = []

    for column_name in dataframe.columns:
        series = dataframe[column_name]
        non_null_values = series.dropna()

        if series.isna().all():
            empty_columns.append(column_name)
        if series.nunique(dropna=False) <= 1:
            constant_columns.append(column_name)
        if non_null_values.nunique() == 1:
            single_unique_value_columns.append(column_name)

        if not is_numeric_column(series) and row_count:
            unique_count = int(non_null_values.nunique())
            cardinality_ratio = unique_count / row_count
            if cardinality_ratio >= _HIGH_CARDINALITY_RATIO:
                high_cardinality_columns.append(
                    HighCardinalityColumn(
                        column_name=column_name,
                        unique_count=unique_count,
                        cardinality_ratio=cardinality_ratio,
                    )
                )

        if series.dtype == object and not non_null_values.empty:
            observed_types = sorted({type(value).__name__ for value in non_null_values})
            if len(observed_types) > 1:
                mixed_type_columns.append(
                    MixedTypeColumn(column_name=column_name, observed_types=observed_types)
                )

    return DataQualityReport(
        constant_columns=constant_columns,
        empty_columns=empty_columns,
        single_unique_value_columns=single_unique_value_columns,
        high_cardinality_columns=high_cardinality_columns,
        mixed_type_columns=mixed_type_columns,
    )
