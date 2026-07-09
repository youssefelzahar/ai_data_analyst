import { request } from "@/services/api";
import type { DataSource } from "@/types/data-source";
import type { QueryAnalysisResponse, QueryResultResponse } from "@/types/sql-query";

export function executeQuery(dataSourceId: string, sql: string): Promise<QueryResultResponse> {
  return request<QueryResultResponse>(`/data-sources/${dataSourceId}/query`, {
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

export function convertQueryToDataset(dataSourceId: string, sql: string): Promise<DataSource> {
  return request<DataSource>(`/data-sources/${dataSourceId}/query/convert`, {
    method: "POST",
    body: JSON.stringify({ sql }),
  });
}
