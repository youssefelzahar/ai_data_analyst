// Mirrors backend/app/schemas/sql_query_schema.py — keep in sync.

import type { DataProfile } from "@/types/data-profile";
import type { DatasetPreview } from "@/types/dataset";

export interface SqlQueryRequest {
  sql: string;
}

export interface QueryResultResponse {
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  truncated: boolean;
}

export interface QueryAnalysisResponse {
  preview: DatasetPreview;
  profile: DataProfile;
}
