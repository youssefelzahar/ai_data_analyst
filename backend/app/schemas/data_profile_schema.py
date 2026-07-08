from typing import Any

from pydantic import BaseModel

from app.schemas.data_source_schema import DataSourceType


class DatasetOverview(BaseModel):
    dataset_name: str
    source_type: DataSourceType
    row_count: int
    column_count: int
    shape: tuple[int, int]
    memory_usage_bytes: int
    dataset_size_bytes: int | None
    total_missing_values: int
    total_duplicate_rows: int
    numeric_column_count: int
    categorical_column_count: int


class ColumnProfile(BaseModel):
    column_name: str
    dtype: str
    nullable: bool
    missing_count: int
    missing_percentage: float
    unique_count: int
    sample_values: list[Any]


class NumericColumnStatistics(BaseModel):
    column_name: str
    count: int
    mean: float
    median: float
    mode: float | None
    minimum: float
    maximum: float
    std_deviation: float | None
    variance: float | None
    range: float
    q1: float
    q3: float
    iqr: float
    skewness: float | None
    kurtosis: float | None


class CategoricalColumnStatistics(BaseModel):
    column_name: str
    unique_count: int
    most_frequent_value: Any
    most_frequent_value_count: int
    cardinality_ratio: float
    missing_percentage: float


class HighCardinalityColumn(BaseModel):
    column_name: str
    unique_count: int
    cardinality_ratio: float


class MixedTypeColumn(BaseModel):
    column_name: str
    observed_types: list[str]


class DataQualityReport(BaseModel):
    constant_columns: list[str]
    empty_columns: list[str]
    single_unique_value_columns: list[str]
    high_cardinality_columns: list[HighCardinalityColumn]
    mixed_type_columns: list[MixedTypeColumn]


class OutlierReport(BaseModel):
    column_name: str
    detection_method: str
    q1: float
    q3: float
    iqr: float
    lower_bound: float
    upper_bound: float
    outlier_count: int
    outlier_percentage: float
    sample_outlier_row_indices: list[int]


class DataProfileResponse(BaseModel):
    overview: DatasetOverview
    columns: list[ColumnProfile]
    numeric_statistics: list[NumericColumnStatistics]
    categorical_statistics: list[CategoricalColumnStatistics]
    data_quality: DataQualityReport
    outliers: list[OutlierReport]


class OutlierRowsResponse(BaseModel):
    column_name: str
    detection_method: str
    row_count: int
    rows: list[dict[str, Any]]
