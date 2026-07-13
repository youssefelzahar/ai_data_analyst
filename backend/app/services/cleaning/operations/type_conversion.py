import pandas as pd

from app.services.cleaning.strategy import (
    CleaningStrategyRegistry,
    OperationOutcome,
    OperationSpec,
    require_column as _require_column,
)

_TRUE_VALUES = {"true", "1", "yes", "y", "t"}
_FALSE_VALUES = {"false", "0", "no", "n", "f"}


class ToIntegerStrategy:
    key = "type_conversion.to_integer"
    label = "String → Integer"
    category = "type_conversion"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        original = result[column_name]
        converted = pd.to_numeric(original, errors="coerce")
        failed = int((converted.isna() & original.notna()).sum())
        result[column_name] = converted.astype("Int64")
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Converted '{column_name}' to integer ({failed} value(s) could not be parsed and became null).",
        )


class ToFloatStrategy:
    key = "type_conversion.to_float"
    label = "String → Float"
    category = "type_conversion"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        original = result[column_name]
        converted = pd.to_numeric(original, errors="coerce")
        failed = int((converted.isna() & original.notna()).sum())
        result[column_name] = converted.astype(float)
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Converted '{column_name}' to float ({failed} value(s) could not be parsed and became null).",
        )


class ToDatetimeStrategy:
    key = "type_conversion.to_datetime"
    label = "String → DateTime"
    category = "type_conversion"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        original = result[column_name]
        converted = pd.to_datetime(original, errors="coerce")
        failed = int((converted.isna() & original.notna()).sum())
        result[column_name] = converted
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Converted '{column_name}' to datetime ({failed} value(s) could not be parsed and became null).",
        )


class ToBooleanStrategy:
    key = "type_conversion.to_boolean"
    label = "Boolean Conversion"
    category = "type_conversion"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()

        def _coerce(value):
            if pd.isna(value):
                return None
            text = str(value).strip().lower()
            if text in _TRUE_VALUES:
                return True
            if text in _FALSE_VALUES:
                return False
            return None

        original = result[column_name]
        converted = original.map(_coerce)
        failed = int((converted.isna() & original.notna()).sum())
        result[column_name] = converted.astype("boolean")
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Converted '{column_name}' to boolean ({failed} value(s) could not be parsed and became null).",
        )


class ToCategoryStrategy:
    key = "type_conversion.to_category"
    label = "Category Conversion"
    category = "type_conversion"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        column_name = _require_column(dataframe, spec)
        result = dataframe.copy()
        result[column_name] = result[column_name].astype("category")
        return OperationOutcome(
            dataframe=result,
            affected_row_count=len(result),
            affected_column_count=1,
            message=f"Converted '{column_name}' to category dtype "
            f"({result[column_name].nunique()} categories).",
        )


def register_type_conversion_strategies(registry: CleaningStrategyRegistry) -> None:
    for strategy in (
        ToIntegerStrategy(),
        ToFloatStrategy(),
        ToDatetimeStrategy(),
        ToBooleanStrategy(),
        ToCategoryStrategy(),
    ):
        registry.register(strategy)
