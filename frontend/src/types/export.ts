// Mirrors backend/app/schemas/export_schema.py — keep in sync.

import type { ChartArtifact, DataTableArtifact, KpiCardArtifact } from "@/types/agent";

export interface DatasetSummarySection {
  dataset_name: string;
  source_type: string;
  version_id: string | null;
  version_label: string | null;
  row_count: number;
  column_count: number;
  numeric_column_count: number;
  categorical_column_count: number;
  total_missing_values: number;
  missing_percentage: number;
  total_duplicate_rows: number;
  memory_usage_bytes: number;
  dataset_size_bytes: number | null;
}

export interface CleaningOperationSummary {
  operation_key: string;
  column_name: string | null;
  message: string | null;
  params: Record<string, unknown>;
}

export interface CleaningVersionSummary {
  version_id: string;
  version_number: number;
  label: string | null;
  row_count: number;
  column_count: number;
  created_at: string;
  operations: CleaningOperationSummary[];
}

export interface CleaningSummarySection {
  applied: boolean;
  total_versions: number;
  selected_version_number: number | null;
  versions: CleaningVersionSummary[];
}

export type InsightSeverity = "info" | "warning" | "critical";
export type RecommendationPriority = "low" | "medium" | "high";

export interface Insight {
  title: string;
  detail: string;
  severity: InsightSeverity;
}

export interface Recommendation {
  title: string;
  detail: string;
  priority: RecommendationPriority;
}

export interface ModelMetric {
  name: string;
  value: string;
}

export interface ModelPerformanceSection {
  model_name: string;
  task_type: string;
  metrics: ModelMetric[];
}

export interface VisualizationSection {
  kpi_cards: KpiCardArtifact[];
  charts: ChartArtifact[];
  tables: DataTableArtifact[];
}

export interface ExportReport {
  generated_at: string;
  dataset_summary: DatasetSummarySection;
  cleaning_summary: CleaningSummarySection | null;
  visualizations: VisualizationSection;
  kpi_summary: KpiCardArtifact[];
  insights: Insight[];
  recommendations: Recommendation[];
  model_performance: ModelPerformanceSection | null;
}

export interface ExportFormatDescriptor {
  key: string;
  label: string;
  file_extension: string;
  media_type: string;
  description: string;
}

export interface ExportFormatsResponse {
  formats: ExportFormatDescriptor[];
}
