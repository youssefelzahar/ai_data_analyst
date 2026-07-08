import { request } from "@/services/api";
import type { DataProfile, OutlierRowsResponse } from "@/types/data-profile";

export function listDataSourceTables(dataSourceId: string): Promise<string[]> {
  return request<string[]>(`/data-sources/${dataSourceId}/tables`);
}

export function getDataProfile(dataSourceId: string, tableName?: string): Promise<DataProfile> {
  const query = tableName ? `?table_name=${encodeURIComponent(tableName)}` : "";
  return request<DataProfile>(`/data-sources/${dataSourceId}/profile${query}`);
}

export function getOutlierRows(
  dataSourceId: string,
  columnName: string,
  tableName?: string,
): Promise<OutlierRowsResponse> {
  const params = new URLSearchParams({ column_name: columnName });
  if (tableName) params.set("table_name", tableName);
  return request<OutlierRowsResponse>(`/data-sources/${dataSourceId}/profile/outliers?${params}`);
}
