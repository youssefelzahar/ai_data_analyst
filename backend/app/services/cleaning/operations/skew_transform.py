import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import PowerTransformer

from app.services.cleaning.strategy import (
    CleaningStrategyRegistry,
    OperationOutcome,
    OperationSpec,
    require_numeric_column as _require_numeric_column,
)


def _skewness_message(column_name: str, before: pd.Series, after: pd.Series, method: str) -> str:
    before_skew = float(before.skew())
    after_skew = float(after.skew())
    return (
        f"Applied {method} to '{column_name}': skewness {before_skew:.3f} -> {after_skew:.3f}."
    )


class LogTransformSkewStrategy:
    key = "skew.log_transform"
    label = "Log Transform"
    category = "skew"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        result = dataframe.copy()
        before = result[column_name].dropna()
        if (before <= -1).any():
            raise ValueError(f"Log transform requires values > -1 in '{column_name}'.")
        result[column_name] = np.log1p(result[column_name])
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=_skewness_message(column_name, before, result[column_name].dropna(), "log transform"),
        )


class SquareRootTransformStrategy:
    key = "skew.sqrt_transform"
    label = "Square Root Transform"
    category = "skew"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        result = dataframe.copy()
        before = result[column_name].dropna()
        if (before < 0).any():
            raise ValueError(f"Square root transform requires non-negative values in '{column_name}'.")
        result[column_name] = np.sqrt(result[column_name])
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=_skewness_message(column_name, before, result[column_name].dropna(), "square root transform"),
        )


class BoxCoxTransformStrategy:
    key = "skew.boxcox"
    label = "Box-Cox"
    category = "skew"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        result = dataframe.copy()
        before = result[column_name].dropna()
        if (before <= 0).any():
            raise ValueError(f"Box-Cox requires strictly positive values in '{column_name}'.")
        non_null_mask = result[column_name].notna()
        transformed, _lambda = stats.boxcox(result.loc[non_null_mask, column_name])
        result.loc[non_null_mask, column_name] = transformed
        return OperationOutcome(
            dataframe=result,
            affected_row_count=int(non_null_mask.sum()),
            affected_column_count=1,
            message=_skewness_message(column_name, before, result[column_name].dropna(), "Box-Cox transform")
            + f" (lambda={_lambda:.3f})",
        )


class YeoJohnsonTransformStrategy:
    key = "skew.yeojohnson"
    label = "Yeo-Johnson"
    category = "skew"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_numeric_column(dataframe, spec)
        result = dataframe.copy()
        before = result[column_name].dropna()
        non_null_mask = result[column_name].notna()
        transformer = PowerTransformer(method="yeo-johnson")
        transformed = transformer.fit_transform(result.loc[non_null_mask, [column_name]])
        result.loc[non_null_mask, column_name] = transformed.ravel()
        return OperationOutcome(
            dataframe=result,
            affected_row_count=int(non_null_mask.sum()),
            affected_column_count=1,
            message=_skewness_message(column_name, before, result[column_name].dropna(), "Yeo-Johnson transform"),
        )


def register_skew_transform_strategies(registry: CleaningStrategyRegistry) -> None:
    for strategy in (
        LogTransformSkewStrategy(),
        SquareRootTransformStrategy(),
        BoxCoxTransformStrategy(),
        YeoJohnsonTransformStrategy(),
    ):
        registry.register(strategy)
