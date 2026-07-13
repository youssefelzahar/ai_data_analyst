import pandas as pd
from sklearn.experimental import enable_iterative_imputer  # noqa: F401  (registers IterativeImputer)
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import IterativeImputer, KNNImputer

from app.services.cleaning.strategy import (
    CleaningStrategyRegistry,
    OperationOutcome,
    OperationSpec,
    require_column as _require_column,
)


class DropRowsStrategy:
    key = "missing_values.drop_rows"
    label = "Drop Rows"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        missing_mask = dataframe[column_name].isna()
        result = dataframe.loc[~missing_mask].reset_index(drop=True)
        affected_rows = int(missing_mask.sum())
        return OperationOutcome(
            dataframe=result,
            affected_row_count=affected_rows,
            affected_column_count=1,
            message=f"Dropped {affected_rows} row(s) missing '{column_name}'.",
        )


class DropColumnsStrategy:
    key = "missing_values.drop_columns"
    label = "Drop Columns"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.drop(columns=[column_name])
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(dataframe),
            affected_column_count=1,
            message=f"Dropped column '{column_name}' (too sparse to impute reliably).",
        )


class MeanImputeStrategy:
    key = "missing_values.mean"
    label = "Mean"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        mean_value = result[column_name].mean()
        result[column_name] = result[column_name].fillna(mean_value)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Filled {missing_count} missing value(s) in '{column_name}' with the mean ({mean_value:.4g}).",
        )


class MedianImputeStrategy:
    key = "missing_values.median"
    label = "Median"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        median_value = result[column_name].median()
        result[column_name] = result[column_name].fillna(median_value)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Filled {missing_count} missing value(s) in '{column_name}' with the median ({median_value:.4g}).",
        )


class ModeImputeStrategy:
    key = "missing_values.mode"
    label = "Mode"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        mode_values = result[column_name].mode()
        if mode_values.empty:
            return OperationOutcome(
                dataframe=result, affected_row_count=0, affected_column_count=1,
                message=f"Column '{column_name}' has no mode; nothing was imputed.",
            )
        mode_value = mode_values.iloc[0]
        result[column_name] = result[column_name].fillna(mode_value)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Filled {missing_count} missing value(s) in '{column_name}' with the mode ({mode_value!r}).",
        )


class ForwardFillStrategy:
    key = "missing_values.forward_fill"
    label = "Forward Fill"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        result[column_name] = result[column_name].ffill()
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Forward-filled {missing_count} missing value(s) in '{column_name}'.",
        )


class BackwardFillStrategy:
    key = "missing_values.backward_fill"
    label = "Backward Fill"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        result[column_name] = result[column_name].bfill()
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Backward-filled {missing_count} missing value(s) in '{column_name}'.",
        )


class ConstantValueStrategy:
    key = "missing_values.constant"
    label = "Constant Value"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        constant_value = spec.params.get("value", "Unknown")
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        result[column_name] = result[column_name].fillna(constant_value)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Filled {missing_count} missing value(s) in '{column_name}' with '{constant_value}'.",
        )


class KnnImputeStrategy:
    key = "missing_values.knn"
    label = "KNN Imputer"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        numeric_columns = dataframe.select_dtypes(include="number").columns.tolist()
        if column_name not in numeric_columns:
            raise ValueError("KNN imputation is only supported for numeric columns.")
        neighbors = int(spec.params.get("n_neighbors", 5))
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        imputer = KNNImputer(n_neighbors=neighbors)
        imputed = imputer.fit_transform(result[numeric_columns])
        result[numeric_columns] = imputed
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Imputed {missing_count} missing value(s) in '{column_name}' using KNN (k={neighbors}).",
        )


class MissForestImputeStrategy:
    key = "missing_values.missforest"
    label = "MissForest"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        numeric_columns = dataframe.select_dtypes(include="number").columns.tolist()
        if column_name not in numeric_columns:
            raise ValueError("MissForest imputation is only supported for numeric columns.")
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        imputer = IterativeImputer(
            estimator=RandomForestRegressor(n_estimators=50, random_state=0),
            random_state=0,
        )
        imputed = imputer.fit_transform(result[numeric_columns])
        result[numeric_columns] = imputed
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Imputed {missing_count} missing value(s) in '{column_name}' using MissForest "
            "(iterative random-forest imputation).",
        )


class InterpolateStrategy:
    key = "missing_values.interpolate"
    label = "Interpolation"
    category = "missing_values"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        if not pd.api.types.is_numeric_dtype(dataframe[column_name]):
            raise ValueError("Interpolation is only supported for numeric columns.")
        result = dataframe.copy()
        missing_count = int(result[column_name].isna().sum())
        result[column_name] = result[column_name].interpolate(method="linear", limit_direction="both")
        return OperationOutcome(
            dataframe=result,
            affected_row_count=missing_count,
            affected_column_count=1,
            message=f"Interpolated {missing_count} missing value(s) in '{column_name}'.",
        )


def register_missing_value_strategies(registry: CleaningStrategyRegistry) -> None:
    for strategy in (
        DropRowsStrategy(),
        DropColumnsStrategy(),
        MeanImputeStrategy(),
        MedianImputeStrategy(),
        ModeImputeStrategy(),
        ForwardFillStrategy(),
        BackwardFillStrategy(),
        ConstantValueStrategy(),
        KnnImputeStrategy(),
        MissForestImputeStrategy(),
        InterpolateStrategy(),
    ):
        registry.register(strategy)
