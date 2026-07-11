import { request } from "@/services/api";
import type { DataSource } from "@/types/data-source";
import type {
  QueryAnalysisResponse,
  QueryResultResponse,
  QueryValidationResponse,
  SqlTableMetadataResponse,
  SqlTablePreviewResponse,
} from "@/types/sql-query";

export function executeQuery(
  dataSourceId: string,
  sql: string,
  page = 1,
  pageSize = 100,
): Promise<QueryResultResponse> {
  const query = `?page=${page}&page_size=${pageSize}`;
  return request<QueryResultResponse>(`/data-sources/${dataSourceId}/query${query}`, {
    method: "POST",
    body: JSON.stringify({ sql }),
  });
}

export function validateQuery(
  dataSourceId: string,
  sql: string,
): Promise<QueryValidationResponse> {
  return request<QueryValidationResponse>(`/data-sources/${dataSourceId}/query/validate`, {
    method: "POST",
    body: JSON.stringify({ sql }),
  });
}

export function analyzeQuery(dataSourceId: string, sql: string): Promise<QueryAnalysisResponse> {
  return request<QueryAnalysisResponse>(`/data-sources/${dataSourceId}/query/analyze`, {
    method: "POST",
    body: JSON.stringify({ sql }),
  });
}

export function getTableMetadata(
  dataSourceId: string,
  tableName: string,
): Promise<SqlTableMetadataResponse> {
  return request<SqlTableMetadataResponse>(
    `/data-sources/${dataSourceId}/tables/${encodeURIComponent(tableName)}/columns`,
  );
}

export function previewTable(
  dataSourceId: string,
  tableName: string,
  page = 1,
  pageSize = 25,
): Promise<SqlTablePreviewResponse> {
  const query = `?page=${page}&page_size=${pageSize}`;
  return request<SqlTablePreviewResponse>(
    `/data-sources/${dataSourceId}/tables/${encodeURIComponent(tableName)}/preview${query}`,
  );
}

export function convertQueryToDataset(dataSourceId: string, sql: string): Promise<DataSource> {
  return request<DataSource>(`/data-sources/${dataSourceId}/query/convert`, {
    method: "POST",
    body: JSON.stringify({ sql }),
  });
}
