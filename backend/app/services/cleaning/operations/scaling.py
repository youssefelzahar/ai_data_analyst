import pandas as pd
from sklearn.preprocessing import MaxAbsScaler, MinMaxScaler, RobustScaler, StandardScaler

from app.services.cleaning.strategy import (
    CleaningStrategyRegistry,
    OperationOutcome,
    OperationSpec,
    require_numeric_column as _require_numeric_column,
)


def _scale(dataframe: pd.DataFrame, spec: OperationSpec, scaler, label: str) -> OperationOutcome:
    column_name = _require_numeric_column(dataframe, spec)
    result = dataframe.copy()
    values = result[[column_name]].astype(float)
    result[column_name] = scaler.fit_transform(values)
    return OperationOutcome(
        dataframe=result,
        affected_row_count=len(result),
        affected_column_count=1,
        message=f"Scaled '{column_name}' using {label}.",
    )


class StandardScalerStrategy:
    key = "scaling.standard"
    label = "StandardScaler"
    category = "scaling"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        return _scale(dataframe, spec, StandardScaler(), self.label)


class MinMaxScalerStrategy:
    key = "scaling.minmax"
    label = "MinMaxScaler"
    category = "scaling"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        return _scale(dataframe, spec, MinMaxScaler(), self.label)


class RobustScalerStrategy:
    key = "scaling.robust"
    label = "RobustScaler"
    category = "scaling"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        return _scale(dataframe, spec, RobustScaler(), self.label)


class MaxAbsScalerStrategy:
    key = "scaling.maxabs"
    label = "MaxAbsScaler"
    category = "scaling"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        return _scale(dataframe, spec, MaxAbsScaler(), self.label)


def register_scaling_strategies(registry: CleaningStrategyRegistry) -> None:
    for strategy in (
        StandardScalerStrategy(),
        MinMaxScalerStrategy(),
        RobustScalerStrategy(),
        MaxAbsScalerStrategy(),
    ):
        registry.register(strategy)
