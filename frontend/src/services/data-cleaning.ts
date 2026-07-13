import { request } from "@/services/api";
import type {
  CleaningMethodsCatalog,
  CleaningRecommendationsResponse,
  DatasetVersionResponse,
  OperationSpec,
  PipelinePreviewResponse,
} from "@/types/data-cleaning";

export function getCleaningRecommendations(
  dataSourceId: string,
  tableName?: string,
): Promise<CleaningRecommendationsResponse> {
  const query = tableName ? `?table_name=${encodeURIComponent(tableName)}` : "";
  return request<CleaningRecommendationsResponse>(
    `/data-sources/${dataSourceId}/cleaning/recommendations${query}`,
  );
}

export function getCleaningMethods(dataSourceId: string): Promise<CleaningMethodsCatalog> {
  return request<CleaningMethodsCatalog>(`/data-sources/${dataSourceId}/cleaning/methods`);
}

export function previewCleaningPipeline(
  dataSourceId: string,
  operations: OperationSpec[],
  tableName?: string,
): Promise<PipelinePreviewResponse> {
  return request<PipelinePreviewResponse>(`/data-sources/${dataSourceId}/cleaning/preview`, {
    method: "POST",
    body: JSON.stringify({ table_name: tableName ?? null, operations }),
  });
}

export function applyCleaningPipeline(
  dataSourceId: string,
  operations: OperationSpec[],
  tableName?: string,
): Promise<DatasetVersionResponse> {
  return request<DatasetVersionResponse>(`/data-sources/${dataSourceId}/cleaning/apply`, {
    method: "POST",
    body: JSON.stringify({ table_name: tableName ?? null, operations }),
  });
}

export function listDatasetVersions(dataSourceId: string): Promise<DatasetVersionResponse[]> {
  return request<DatasetVersionResponse[]>(`/data-sources/${dataSourceId}/cleaning/versions`);
}

export function undoLastDatasetVersion(dataSourceId: string): Promise<void> {
  return request<void>(`/data-sources/${dataSourceId}/cleaning/versions/latest`, {
    method: "DELETE",
  });
}
