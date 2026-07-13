// Mirrors backend/app/schemas/data_cleaning_schema.py — keep in sync.

import type { DatasetOverview } from "@/types/data-profile";

export type CleaningCategory =
  | "missing_values"
  | "duplicates"
  | "type_conversion"
  | "outliers"
  | "encoding"
  | "scaling"
  | "skew"
  | "text";

export interface OperationSpec {
  operation_key: string;
  column_name: string | null;
  params: Record<string, unknown>;
}

export interface RecommendationItem {
  category: CleaningCategory;
  column_name: string | null;
  recommended_operation_key: string;
  recommended_label: string;
  reason: string;
  alternative_operation_keys: string[];
}

export interface CleaningRecommendationsResponse {
  missing_values: RecommendationItem[];
  duplicates: RecommendationItem[];
  type_conversion: RecommendationItem[];
  outliers: RecommendationItem[];
  encoding: RecommendationItem[];
  scaling: RecommendationItem[];
  skew: RecommendationItem[];
  text: RecommendationItem[];
}

export interface CleaningMethodDescriptor {
  key: string;
  label: string;
  category: CleaningCategory;
}

export interface CleaningMethodsCatalog {
  methods: CleaningMethodDescriptor[];
}

export interface PipelineStepResult {
  operation_key: string;
  column_name: string | null;
  affected_row_count: number;
  affected_column_count: number;
  message: string;
}

export interface PipelinePreviewResponse {
  steps: PipelineStepResult[];
  before_overview: DatasetOverview;
  after_overview: DatasetOverview;
  sample_before_rows: Record<string, unknown>[];
  sample_after_rows: Record<string, unknown>[];
}

export interface DatasetVersionResponse {
  id: string;
  data_source_id: string;
  version_number: number;
  row_count: number;
  column_count: number;
  file_size_bytes: number;
  operations_summary: Record<string, unknown>[];
  label: string | null;
  created_at: string;
}
