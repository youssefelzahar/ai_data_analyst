import pandas as pd

from app.services.cleaning.strategy import CleaningStrategyRegistry, OperationOutcome, OperationSpec


def _drop_and_report(dataframe: pd.DataFrame, keep) -> OperationOutcome:
    duplicate_mask = dataframe.duplicated(keep=keep)
    result = dataframe.loc[~duplicate_mask].reset_index(drop=True)
    affected_rows = int(duplicate_mask.sum())
    return OperationOutcome(
        dataframe=result,
        affected_row_count=affected_rows,
        affected_column_count=len(dataframe.columns),
        message=f"Removed {affected_rows} duplicate row(s).",
    )


class RemoveDuplicatesStrategy:
    key = "duplicates.remove"
    label = "Remove Duplicate Rows"
    category = "duplicates"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        return _drop_and_report(dataframe, keep="first")


class KeepFirstStrategy:
    key = "duplicates.keep_first"
    label = "Keep First"
    category = "duplicates"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        return _drop_and_report(dataframe, keep="first")


class KeepLastStrategy:
    key = "duplicates.keep_last"
    label = "Keep Last"
    category = "duplicates"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        return _drop_and_report(dataframe, keep="last")


class KeepUniqueStrategy:
    key = "duplicates.keep_unique"
    label = "Keep Unique"
    category = "duplicates"

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome:
        return _drop_and_report(dataframe, keep=False)


def register_duplicate_strategies(registry: CleaningStrategyRegistry) -> None:
    for strategy in (
        RemoveDuplicatesStrategy(),
        KeepFirstStrategy(),
        KeepLastStrategy(),
        KeepUniqueStrategy(),
    ):
        registry.register(strategy)
