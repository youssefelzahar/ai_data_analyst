"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  deleteDataSource,
  listDataSources,
  uploadDatasetFile,
} from "@/services/data-sources";
import type { DataSource } from "@/types/data-source";

const SUPPORTED_EXTENSIONS = [".csv", ".xlsx", ".xls"];

function formatFileSize(fileSizeBytes: number | null): string {
  if (fileSizeBytes === null) return "—";
  if (fileSizeBytes < 1024) return `${fileSizeBytes} B`;
  if (fileSizeBytes < 1024 * 1024) return `${(fileSizeBytes / 1024).toFixed(1)} KB`;
  return `${(fileSizeBytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatUploadDate(isoDate: string): string {
  return new Date(isoDate).toLocaleString();
}

export default function FileUploadPanel() {
  const [uploadedDatasets, setUploadedDatasets] = useState<DataSource[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const filePickerRef = useRef<HTMLInputElement>(null);

  const refreshUploadedDatasets = useCallback(async () => {
    try {
      setUploadedDatasets(await listDataSources("file"));
    } catch {
      // listing failure is surfaced by the empty state; upload errors are explicit
    }
  }, []);

  useEffect(() => {
    void refreshUploadedDatasets();
  }, [refreshUploadedDatasets]);

  const startUpload = useCallback(
    async (selectedFile: File) => {
      setUploadError(null);
      setUploadSuccess(null);

      const fileExtension = selectedFile.name
        .slice(selectedFile.name.lastIndexOf("."))
        .toLowerCase();
      if (!SUPPORTED_EXTENSIONS.includes(fileExtension)) {
        setUploadError(
          `Unsupported file type "${fileExtension}". Supported: ${SUPPORTED_EXTENSIONS.join(", ")}`,
        );
        return;
      }

      setUploadProgress(0);
      try {
        const savedDataSource = await uploadDatasetFile(selectedFile, setUploadProgress);
        setUploadSuccess(`"${savedDataSource.original_filename}" uploaded successfully.`);
        await refreshUploadedDatasets();
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : "Upload failed");
      } finally {
        setUploadProgress(null);
      }
    },
    [refreshUploadedDatasets],
  );

  const handleDrop = useCallback(
    (dropEvent: React.DragEvent) => {
      dropEvent.preventDefault();
      setIsDragActive(false);
      const droppedFile = dropEvent.dataTransfer.files[0];
      if (droppedFile) void startUpload(droppedFile);
    },
    [startUpload],
  );

  const handleDelete = useCallback(
    async (dataSourceId: string) => {
      try {
        await deleteDataSource(dataSourceId);
        await refreshUploadedDatasets();
      } catch (error) {
        setUploadError(error instanceof Error ? error.message : "Delete failed");
      }
    },
    [refreshUploadedDatasets],
  );

  return (
    <div className="space-y-6">
      <div
        onDragOver={(dragEvent) => {
          dragEvent.preventDefault();
          setIsDragActive(true);
        }}
        onDragLeave={() => setIsDragActive(false)}
        onDrop={handleDrop}
        onClick={() => filePickerRef.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed p-10 text-center transition-colors ${
          isDragActive
            ? "border-sky-400 bg-sky-950/40"
            : "border-slate-700 bg-slate-900 hover:border-slate-500"
        }`}
      >
        <p className="text-lg font-medium">
          Drag &amp; drop your dataset here
        </p>
        <p className="mt-1 text-sm text-slate-400">
          or click to browse — CSV and Excel files are supported
        </p>
        <input
          ref={filePickerRef}
          type="file"
          accept={SUPPORTED_EXTENSIONS.join(",")}
          className="hidden"
          onChange={(changeEvent) => {
            const selectedFile = changeEvent.target.files?.[0];
            if (selectedFile) void startUpload(selectedFile);
            changeEvent.target.value = "";
          }}
        />
      </div>

      {uploadProgress !== null && (
        <div>
          <div className="mb-1 flex justify-between text-sm text-slate-400">
            <span>Uploading…</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-sky-500 transition-all"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {uploadError && (
        <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          {uploadError}
        </p>
      )}
      {uploadSuccess && (
        <p className="rounded-lg border border-emerald-900 bg-emerald-950/50 px-4 py-2 text-sm text-emerald-400">
          {uploadSuccess}
        </p>
      )}

      <section>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Uploaded datasets
        </h3>
        {uploadedDatasets.length === 0 ? (
          <p className="text-sm text-slate-500">No datasets uploaded yet.</p>
        ) : (
          <ul className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900">
            {uploadedDatasets.map((uploadedDataset) => (
              <li
                key={uploadedDataset.id}
                className="flex items-center justify-between gap-4 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">
                    {uploadedDataset.original_filename}
                  </p>
                  <p className="text-xs text-slate-500">
                    {uploadedDataset.file_format?.toUpperCase()} ·{" "}
                    {formatFileSize(uploadedDataset.file_size_bytes)} ·{" "}
                    {formatUploadDate(uploadedDataset.created_at)}
                  </p>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Link
                    href={`/data-sources/${uploadedDataset.id}/preview`}
                    className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-400"
                  >
                    Preview
                  </Link>
                  <Link
                    href={`/data-sources/${uploadedDataset.id}/profile`}
                    className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-400"
                  >
                    Profile
                  </Link>
                  <Link
                    href={`/data-sources/${uploadedDataset.id}/cleaning`}
                    className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-400"
                  >
                    Cleaning
                  </Link>
                  <button
                    onClick={() => void handleDelete(uploadedDataset.id)}
                    className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-red-800 hover:text-red-400"
                  >
                    Delete
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}