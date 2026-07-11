// Mirrors backend/app/schemas/sql_query_schema.py — keep in sync.

import type { DataProfile } from "@/types/data-profile";
import type { DatasetPreview } from "@/types/dataset";

export interface SqlQueryRequest {
  sql: string;
}

export interface QueryPagination {
  page: number;
  page_size: number;
  total_pages: number;
  total_rows: number;
}

export interface QueryValidationResponse {
  is_valid: boolean;
  normalized_sql: string;
  message: string;
}

export interface QueryResultResponse {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
  pagination: QueryPagination | null;
}

export interface SqlTableColumnMetadata {
  column_name: string;
  data_type: string;
  is_nullable: boolean;
  ordinal_position: number;
  character_maximum_length: number | null;
  numeric_precision: number | null;
  numeric_scale: number | null;
}

export interface SqlTableMetadataResponse {
  table_name: string;
  columns: SqlTableColumnMetadata[];
}

export interface SqlTablePreviewResponse {
  table_name: string;
  columns: string[];
  rows: Record<string, unknown>[];
  pagination: QueryPagination;
}

export interface QueryAnalysisResponse {
  preview: DatasetPreview;
  profile: DataProfile;
}
