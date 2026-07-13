import numpy as np
import pandas as pd

from app.services.cleaning.strategy import (
    CleaningStrategyRegistry,
    OperationOutcome,
    OperationSpec,
    require_numeric_column as _require_numeric_column,
)
from app.services.profiling.outliers import detect_outliers_iqr


class KeepOutliersStrategy:
    key = "outliers.keep"
    label = "Keep Outliers"
    category = "outliers"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        return OperationOutcome(
            dataframe=dataframe,
            affected_row_count=0,
            affected_column_count=0,
            message=f"Kept all values in '{column_name}' unchanged.",
        )


class RemoveOutliersStrategy:
    key = "outliers.remove"
    label = "Remove Outliers"
    category = "outliers"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        bounds = detect_outliers_iqr(dataframe[column_name])
        outlier_mask = (dataframe[column_name] < bounds.lower_bound) | (
            dataframe[column_name] > bounds.upper_bound
        )
        result = dataframe.loc[~outlier_mask].reset_index(drop=True)
        affected_rows = int(outlier_mask.sum())
        return OperationOutcome(
            dataframe=result,
            affected_row_count=affected_rows,
            affected_column_count=1,
            message=f"Removed {affected_rows} outlier row(s) from '{column_name}' (IQR method).",
        )


class IqrCappingStrategy:
    key = "outliers.iqr_capping"
    label = "IQR Capping"
    category = "outliers"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        bounds = detect_outliers_iqr(dataframe[column_name])
        result = dataframe.copy()
        outlier_mask = (result[column_name] < bounds.lower_bound) | (
            result[column_name] > bounds.upper_bound
        )
        result[column_name] = result[column_name].clip(lower=bounds.lower_bound, upper=bounds.upper_bound)
        affected_rows = int(outlier_mask.sum())
        return OperationOutcome(
            dataframe=result,
            affected_row_count=affected_rows,
            affected_column_count=1,
            message=f"Capped {affected_rows} value(s) in '{column_name}' to "
            f"[{bounds.lower_bound:.4g}, {bounds.upper_bound:.4g}] (IQR bounds).",
        )


class WinsorizationStrategy:
    key = "outliers.winsorization"
    label = "Winsorization"
    category = "outliers"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        lower_percentile = float(spec.params.get("lower_percentile", 1))
        upper_percentile = float(spec.params.get("upper_percentile", 99))
        result = dataframe.copy()
        lower_bound = result[column_name].quantile(lower_percentile / 100)
        upper_bound = result[column_name].quantile(upper_percentile / 100)
        affected_mask = (result[column_name] < lower_bound) | (result[column_name] > upper_bound)
        result[column_name] = result[column_name].clip(lower=lower_bound, upper=upper_bound)
        affected_rows = int(affected_mask.sum())
        return OperationOutcome(
            dataframe=result,
            affected_row_count=affected_rows,
            affected_column_count=1,
            message=f"Winsorized '{column_name}' at the {lower_percentile}th/{upper_percentile}th "
            f"percentiles, affecting {affected_rows} row(s).",
        )


class ZScoreFilterStrategy:
    key = "outliers.zscore_filter"
    label = "Z-Score Filtering"
    category = "outliers"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        threshold = float(spec.params.get("threshold", 3.0))
        series = dataframe[column_name]
        mean = series.mean()
        std = series.std()
        if not std or pd.isna(std):
            return OperationOutcome(
                dataframe=dataframe, affected_row_count=0, affected_column_count=0,
                message=f"'{column_name}' has zero variance; z-score filtering skipped.",
            )
        z_scores = (series - mean).abs() / std
        outlier_mask = z_scores > threshold
        result = dataframe.loc[~outlier_mask].reset_index(drop=True)
        affected_rows = int(outlier_mask.sum())
        return OperationOutcome(
            dataframe=result,
            affected_row_count=affected_rows,
            affected_column_count=1,
            message=f"Removed {affected_rows} row(s) from '{column_name}' with |z-score| > {threshold}.",
        )


class LogTransformStrategy:
    key = "outliers.log_transform"
    label = "Log Transformation"
    category = "outliers"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        result = dataframe.copy()
        if (result[column_name].dropna() <= -1).any():
            raise ValueError(
                f"Log transformation requires values > -1 in '{column_name}'."
            )
        result[column_name] = np.log1p(result[column_name])
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Applied log1p transformation to '{column_name}' to compress extreme values.",
        )


def register_outlier_strategies(registry: CleaningStrategyRegistry) -> None:
    for strategy in (
        KeepOutliersStrategy(),
        RemoveOutliersStrategy(),
        IqrCappingStrategy(),
        WinsorizationStrategy(),
        ZScoreFilterStrategy(),
        LogTransformStrategy(),
    ):
        registry.register(strategy)
