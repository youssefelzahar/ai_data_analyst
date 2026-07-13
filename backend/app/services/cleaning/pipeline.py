import pandas as pd

from app.services.cleaning.strategy import CleaningStrategyRegistry, OperationOutcome, OperationSpec


class CleaningPipelineExecutor:
    """Threads a DataFrame through an ordered list of approved operations."""

    def __init__(self, registry: CleaningStrategyRegistry) -> None:
        self._registry = registry

    def run(
        self, dataframe: pd.DataFrame, operations: list[OperationSpec]
    ) -> tuple[pd.DataFrame, list[OperationOutcome]]:
        current_dataframe = dataframe
        outcomes: list[OperationOutcome] = []
        for operation_spec in operations:
            strategy = self._registry.get(operation_spec.operation_key)
            outcome = strategy.apply(current_dataframe, operation_spec)
            outcomes.append(outcome)
            current_dataframe = outcome.dataframe
        return current_dataframe, outcomes
