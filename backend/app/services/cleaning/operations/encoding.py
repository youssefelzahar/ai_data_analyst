import pandas as pd

from app.services.cleaning.strategy import (
    CleaningStrategyRegistry,
    OperationOutcome,
    OperationSpec,
    require_column as _require_column,
)


class LabelEncodingStrategy:
    key = "encoding.label"
    label = "Label Encoding"
    category = "encoding"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        categories = sorted(result[column_name].dropna().unique(), key=str)
        mapping = {category: index for index, category in enumerate(categories)}
        result[column_name] = result[column_name].map(mapping)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Label-encoded '{column_name}' into {len(categories)} integer code(s).",
        )


class OneHotEncodingStrategy:
    key = "encoding.one_hot"
    label = "One-Hot Encoding"
    category = "encoding"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        dummies = pd.get_dummies(dataframe[column_name], prefix=column_name)
        result = pd.concat([dataframe.drop(columns=[column_name]), dummies], axis=1)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=len(dummies.columns),
            message=f"One-hot encoded '{column_name}' into {len(dummies.columns)} new column(s).",
        )


class OrdinalEncodingStrategy:
    key = "encoding.ordinal"
    label = "Ordinal Encoding"
    category = "encoding"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        order = spec.params.get("order")
        if not order:
            raise ValueError("Ordinal encoding requires params.order (a list defining category rank).")
        mapping = {category: rank for rank, category in enumerate(order)}
        result = dataframe.copy()
        result[column_name] = result[column_name].map(mapping)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Ordinal-encoded '{column_name}' using the provided rank order.",
        )


class TargetEncodingStrategy:
    key = "encoding.target"
    label = "Target Encoding"
    category = "encoding"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        target_column = spec.params.get("target_column")
        if not target_column or target_column not in dataframe.columns:
            raise ValueError("Target encoding requires params.target_column referencing a numeric column.")
        result = dataframe.copy()
        target_means = result.groupby(column_name)[target_column].mean()
        result[column_name] = result[column_name].map(target_means)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Target-encoded '{column_name}' using the mean of '{target_column}' per category.",
        )


class FrequencyEncodingStrategy:
    key = "encoding.frequency"
    label = "Frequency Encoding"
    category = "encoding"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        frequencies = result[column_name].value_counts(normalize=True)
        result[column_name] = result[column_name].map(frequencies)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Frequency-encoded '{column_name}' using each category's relative frequency.",
        )


def register_encoding_strategies(registry: CleaningStrategyRegistry) -> None:
    for strategy in (
        LabelEncodingStrategy(),
        OneHotEncodingStrategy(),
        OrdinalEncodingStrategy(),
        TargetEncodingStrategy(),
        FrequencyEncodingStrategy(),
    ):
        registry.register(strategy)
