// Mirrors backend/app/schemas/data_profile_schema.py — keep in sync.

import type { DataSourceType } from "@/types/data-source";

export interface DatasetOverview {
  dataset_name: string;
  source_type: DataSourceType;
  row_count: number;
  column_count: number;
  shape: [number, number];
  memory_usage_bytes: number;
  dataset_size_bytes: number | null;
  total_missing_values: number;
  total_duplicate_rows: number;
  numeric_column_count: number;
  categorical_column_count: number;
}

export interface ColumnProfile {
  column_name: string;
  dtype: string;
  nullable: boolean;
  missing_count: number;
  missing_percentage: number;
  unique_count: number;
  sample_values: unknown[];
}

export interface NumericColumnStatistics {
  column_name: string;
  count: number;
  mean: number;
  median: number;
  mode: number | null;
  minimum: number;
  maximum: number;
  std_deviation: number | null;
  variance: number | null;
  range: number;
  q1: number;
  q3: number;
  iqr: number;
  skewness: number | null;
  kurtosis: number | null;
}

export interface CategoricalColumnStatistics {
  column_name: string;
  unique_count: number;
  most_frequent_value: unknown;
  most_frequent_value_count: number;
  cardinality_ratio: number;
  missing_percentage: number;
}

export interface HighCardinalityColumn {
  column_name: string;
  unique_count: number;
  cardinality_ratio: number;
}

export interface MixedTypeColumn {
  column_name: string;
  observed_types: string[];
}

export interface DataQualityReport {
  constant_columns: string[];
  empty_columns: string[];
  single_unique_value_columns: string[];
  high_cardinality_columns: HighCardinalityColumn[];
  mixed_type_columns: MixedTypeColumn[];
}

export interface OutlierReport {
  column_name: string;
  detection_method: string;
  q1: number;
  q3: number;
  iqr: number;
  lower_bound: number;
  upper_bound: number;
  outlier_count: number;
  outlier_percentage: number;
  sample_outlier_row_indices: number[];
}

export interface DataProfile {
  overview: DatasetOverview;
  columns: ColumnProfile[];
  numeric_statistics: NumericColumnStatistics[];
  categorical_statistics: CategoricalColumnStatistics[];
  data_quality: DataQualityReport;
  outliers: OutlierReport[];
}

export interface OutlierRowsResponse {
  column_name: string;
  detection_method: string;
  row_count: number;
  rows: Record<string, unknown>[];
}
