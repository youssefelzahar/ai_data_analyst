import { request } from "@/services/api";
import type { DatasetPreview } from "@/types/dataset";

export function getDatasetPreview(
  dataSourceId: string,
  previewRowCount = 10,
): Promise<DatasetPreview> {
  return request<DatasetPreview>(
    `/data-sources/${dataSourceId}/preview?preview_row_count=${previewRowCount}`,
  );
}
