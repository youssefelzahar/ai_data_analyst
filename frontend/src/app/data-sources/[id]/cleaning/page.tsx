"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import DataCleaning from "@/features/dataset/data-cleaning";
import { getDataSource } from "@/services/data-sources";
import type { DataSource } from "@/types/data-source";
import { AuthGuard } from "@/components/auth-guard";

export default function DataCleaningPage({ params }: { params: Promise<{ id: string }> }) {
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
    <AuthGuard requireAdmin>
      <main className="mx-auto max-w-6xl p-8">
        <Link href="/data-sources" className="text-sm text-slate-500 hover:text-slate-300">
          ← Data Sources
        </Link>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">
          {dataSource?.name ?? "Data cleaning"}
        </h1>
        <p className="mt-1 text-slate-400">
          Review recommendations, build a pipeline, and approve every change before it's applied.
        </p>

        {loadError && (
          <p className="mt-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
            {loadError}
          </p>
        )}

        {dataSource && (
          <div className="mt-6">
            <DataCleaning dataSourceId={dataSourceId} sourceType={dataSource.source_type} />
          </div>
        )}
      </main>
    </AuthGuard>
  );
}
