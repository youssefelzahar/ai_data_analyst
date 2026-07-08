"use client";

import { useEffect, useState } from "react";
import { getDatasetPreview } from "@/services/dataset";
import type { DatasetPreview as DatasetPreviewData } from "@/types/dataset";

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(value);
}

function formatFileSize(fileSizeBytes: number | null): string {
  if (fileSizeBytes === null) return "—";
  if (fileSizeBytes < 1024) return `${fileSizeBytes} B`;
  if (fileSizeBytes < 1024 * 1024) return `${(fileSizeBytes / 1024).toFixed(1)} KB`;
  return `${(fileSizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-4">
      <p className="text-sm text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return String(value);
}

interface DatasetPreviewProps {
  dataSourceId: string;
  fileSizeBytes: number | null;
}

export default function DatasetPreview({ dataSourceId, fileSizeBytes }: DatasetPreviewProps) {
  const [preview, setPreview] = useState<DatasetPreviewData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    setPreview(null);
    setLoadError(null);
    getDatasetPreview(dataSourceId)
      .then(setPreview)
      .catch((error) =>
        setLoadError(error instanceof Error ? error.message : "Failed to load preview"),
      );
  }, [dataSourceId]);

  if (loadError) {
    return (
      <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
        {loadError}
      </p>
    );
  }

  if (!preview) {
    return <p className="text-sm text-slate-500">Loading preview…</p>;
  }

  const totalMissingValues = Object.values(preview.missing_value_counts).reduce(
    (sum, count) => sum + count,
    0,
  );

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Rows" value={formatCompactNumber(preview.row_count)} />
        <StatTile label="Columns" value={formatCompactNumber(preview.column_count)} />
        <StatTile label="Missing values" value={formatCompactNumber(totalMissingValues)} />
        <StatTile label="File size" value={formatFileSize(fileSizeBytes)} />
      </div>

      <section>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Dataset info
        </h3>
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                <th className="px-4 py-2 font-medium">Column</th>
                <th className="px-4 py-2 font-medium">Type</th>
                <th className="px-4 py-2 font-medium">Missing</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {preview.column_names.map((columnName) => (
                <tr key={columnName}>
                  <td className="px-4 py-2 text-slate-200">{columnName}</td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-400">
                    {preview.dtypes[columnName]}
                  </td>
                  <td className="px-4 py-2 text-slate-400">
                    {preview.missing_value_counts[columnName]}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Table preview
        </h3>
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                {preview.column_names.map((columnName) => (
                  <th key={columnName} className="whitespace-nowrap px-4 py-2 font-medium">
                    {columnName}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {preview.preview_rows.map((row, rowIndex) => (
                <tr key={rowIndex}>
                  {preview.column_names.map((columnName) => (
                    <td
                      key={columnName}
                      className="whitespace-nowrap px-4 py-2 text-slate-300"
                    >
                      {formatCellValue(row[columnName])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
