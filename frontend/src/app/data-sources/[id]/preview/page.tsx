"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import DatasetPreview from "@/features/dataset/dataset-preview";
import { getDataSource } from "@/services/data-sources";
import type { DataSource } from "@/types/data-source";

export default function DatasetPreviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: dataSourceId } = use(params);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    getDataSource(dataSourceId)
      .then(setDataSource)
      .catch((error) =>
        setLoadError(error instanceof Error ? error.message : "Failed to load data source"),
      );
  }, [dataSourceId]);

  return (
    <main className="mx-auto max-w-4xl p-8">
      <Link href="/data-sources" className="text-sm text-slate-500 hover:text-slate-300">
        ← Data Sources
      </Link>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">
        {dataSource?.original_filename ?? "Dataset preview"}
      </h1>
      <p className="mt-1 text-slate-400">
        A snapshot of this dataset&apos;s shape, columns, and sample rows.
      </p>

      {loadError && (
        <p className="mt-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          {loadError}
        </p>
      )}

      <div className="mt-6">
        <DatasetPreview
          dataSourceId={dataSourceId}
          fileSizeBytes={dataSource?.file_size_bytes ?? null}
        />
      </div>
    </main>
  );
}
