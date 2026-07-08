// Mirrors backend/app/schemas/data_source_schema.py::DatasetPreviewResponse — keep in sync.

export interface DatasetPreview {
  row_count: number;
  column_count: number;
  column_names: string[];
  dtypes: Record<string, string>;
  missing_value_counts: Record<string, number>;
  preview_rows: Record<string, unknown>[];
}
