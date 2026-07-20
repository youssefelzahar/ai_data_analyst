import { API_URL, request } from "@/services/api";
import { getAccessToken } from "@/lib/auth-storage";
import type {
  ConnectionTestResult,
  DataSource,
  DataSourceType,
  SqlServerConnectionCreate,
} from "@/types/data-source";

export function listDataSources(sourceType?: DataSourceType): Promise<DataSource[]> {
  const query = sourceType ? `?source_type=${sourceType}` : "";
  return request<DataSource[]>(`/data-sources${query}`);
}

export function getDataSource(dataSourceId: string): Promise<DataSource> {
  return request<DataSource>(`/data-sources/${dataSourceId}`);
}

export function listSqlServerTables(dataSourceId: string): Promise<string[]> {
  return request<string[]>(`/data-sources/${dataSourceId}/tables`);
}

export function deleteDataSource(dataSourceId: string): Promise<void> {
  return request<void>(`/data-sources/${dataSourceId}`, { method: "DELETE" });
}

export function createSqlServerConnection(
  connectionConfig: SqlServerConnectionCreate,
): Promise<DataSource> {
  return request<DataSource>("/data-sources/sql-server", {
    method: "POST",
    body: JSON.stringify(connectionConfig),
  });
}

export function testSqlServerConnection(
  connectionConfig: SqlServerConnectionCreate,
): Promise<ConnectionTestResult> {
  return request<ConnectionTestResult>("/data-sources/sql-server/test", {
    method: "POST",
    body: JSON.stringify(connectionConfig),
  });
}

/**
 * Uploads a dataset file with real progress reporting.
 * Uses XMLHttpRequest because fetch() cannot report upload progress.
 */
export function uploadDatasetFile(
  datasetFile: File,
  onProgress: (percentComplete: number) => void,
): Promise<DataSource> {
  return new Promise((resolve, reject) => {
    const uploadRequest = new XMLHttpRequest();
    uploadRequest.open("POST", `${API_URL}/data-sources/upload`);
    const token = getAccessToken();
    if (token) {
      uploadRequest.setRequestHeader("Authorization", `Bearer ${token}`);
    }

    uploadRequest.upload.onprogress = (progressEvent) => {
      if (progressEvent.lengthComputable) {
        onProgress(Math.round((progressEvent.loaded / progressEvent.total) * 100));
      }
    };

    uploadRequest.onload = () => {
      if (uploadRequest.status >= 200 && uploadRequest.status < 300) {
        resolve(JSON.parse(uploadRequest.responseText) as DataSource);
      } else {
        let errorMessage = `Upload failed (HTTP ${uploadRequest.status})`;
        try {
          const errorBody = JSON.parse(uploadRequest.responseText) as { detail?: string };
          if (errorBody.detail) errorMessage = errorBody.detail;
        } catch {
          // keep the generic message when the body is not JSON
        }
        reject(new Error(errorMessage));
      }
    };
    uploadRequest.onerror = () => reject(new Error("Network error during upload"));

    const uploadFormData = new FormData();
    uploadFormData.append("uploaded_file", datasetFile);
    uploadRequest.send(uploadFormData);
  });
}
