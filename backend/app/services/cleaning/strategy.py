from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd
from pydantic import BaseModel, Field


class OperationSpec(BaseModel):
    """One step in a user-approved cleaning pipeline."""

    operation_key: str
    column_name: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)


@dataclass
class OperationOutcome:
    dataframe: pd.DataFrame
    affected_row_count: int
    affected_column_count: int
    message: str


class UnknownStrategyError(Exception):
    """Raised when an OperationSpec references an unregistered operation_key."""


class CleaningStrategy(Protocol):
    """Common interface every cleaning method implements.

    New preprocessing techniques are added by writing one class that
    satisfies this protocol and registering an instance in
    `cleaning/registry.py` — nothing else in the pipeline needs to change.
    """

    key: str
    label: str
    category: str

    def apply(self, dataframe: pd.DataFrame, spec: OperationSpec) -> OperationOutcome: ...


def require_column(dataframe: pd.DataFrame, spec: "OperationSpec") -> str:
    if not spec.column_name or spec.column_name not in dataframe.columns:
        raise ValueError(f"Column '{spec.column_name}' was not found in this dataset.")
    return spec.column_name


def require_numeric_column(dataframe: pd.DataFrame, spec: "OperationSpec") -> str:
    column_name = require_column(dataframe, spec)
    if not pd.api.types.is_numeric_dtype(dataframe[column_name]):
        raise ValueError(f"Column '{column_name}' is not numeric.")
    return column_name


class CleaningStrategyRegistry:
    """Registers cleaning strategies without coupling them to the pipeline executor."""

    def __init__(self) -> None:
        self._strategies: dict[str, CleaningStrategy] = {}

    def register(self, strategy: CleaningStrategy) -> None:
        self._strategies[strategy.key] = strategy

    def get(self, key: str) -> CleaningStrategy:
        strategy = self._strategies.get(key)
        if strategy is None:
            raise UnknownStrategyError(f"Unknown cleaning operation '{key}'.")
        return strategy

    def list_all(self) -> list[CleaningStrategy]:
        return list(self._strategies.values())

    def list_by_category(self, category: str | None = None) -> list[CleaningStrategy]:
        if category is None:
            return self.list_all()
        return [strategy for strategy in self._strategies.values() if strategy.category == category]
