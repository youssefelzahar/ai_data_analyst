import { API_URL, request } from "@/services/api";
import type { ExportFormatsResponse, ExportReport } from "@/types/export";

interface ExportOptions {
  versionId?: string | null;
  tableName?: string | null;
  /** Extension used for the saved file if the server filename can't be read. */
  fallbackExtension?: string;
}

function buildQuery(options: ExportOptions | undefined): string {
  const params = new URLSearchParams();
  if (options?.versionId) params.set("version_id", options.versionId);
  if (options?.tableName) params.set("table_name", options.tableName);
  const query = params.toString();
  return query ? `?${query}` : "";
}

export function listExportFormats(dataSourceId: string): Promise<ExportFormatsResponse> {
  return request<ExportFormatsResponse>(`/data-sources/${dataSourceId}/export/formats`);
}

export function getExportReport(
  dataSourceId: string,
  options?: ExportOptions,
): Promise<ExportReport> {
  return request<ExportReport>(
    `/data-sources/${dataSourceId}/export/report${buildQuery(options)}`,
  );
}

/**
 * Generate an export on the server and trigger a browser download of the
 * returned file. Resolves once the download has started.
 */
export async function downloadExport(
  dataSourceId: string,
  formatKey: string,
  options?: ExportOptions,
): Promise<void> {
  const response = await fetch(
    `${API_URL}/data-sources/${dataSourceId}/export/${formatKey}${buildQuery(options)}`,
    { method: "GET" },
  );

  if (!response.ok) {
    let message = `Export failed (HTTP ${response.status})`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // keep the generic message when the error body is not JSON
    }
    throw new Error(message);
  }

  const blob = await response.blob();
  const filename = extractFilename(
    response.headers.get("Content-Disposition"),
    formatKey,
    options?.fallbackExtension,
  );
  triggerBrowserDownload(blob, filename);
}

function extractFilename(
  contentDisposition: string | null,
  formatKey: string,
  fallbackExtension?: string,
): string {
  if (contentDisposition) {
    const utf8Match = /filename\*=UTF-8''([^;]+)/i.exec(contentDisposition);
    if (utf8Match) return decodeURIComponent(utf8Match[1]);
    const plainMatch = /filename="?([^";]+)"?/i.exec(contentDisposition);
    if (plainMatch) return plainMatch[1];
  }
  const suffix = fallbackExtension ? `.${fallbackExtension.replace(/^\./, "")}` : "";
  return `export-${formatKey}${suffix}`;
}

function triggerBrowserDownload(blob: Blob, filename: string): void {
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(downloadUrl);
}
