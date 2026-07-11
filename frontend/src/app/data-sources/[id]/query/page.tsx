"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import DatabaseExplorer from "@/features/data-sources/database-explorer";
import { getDataSource } from "@/services/data-sources";
import type { DataSource } from "@/types/data-source";

export default function SqlEditorPage({ params }: { params: Promise<{ id: string }> }) {
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

  const isSqlServer = dataSource?.source_type === "sql_server";

  return (
    <main className="mx-auto max-w-6xl p-8">
      <Link href="/data-sources" className="text-sm text-slate-500 hover:text-slate-300">
        ← Data Sources
      </Link>
      <h1 className="mt-2 text-3xl font-bold tracking-tight">
        {dataSource?.name ?? "Database explorer"}
      </h1>
      <p className="mt-1 text-slate-400">
        Browse tables, inspect schema, preview data, and run safe read-only SQL.
      </p>

      {loadError && (
        <p className="mt-4 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          {loadError}
        </p>
      )}

      {dataSource && !isSqlServer && (
        <p className="mt-4 rounded-lg border border-amber-900 bg-amber-950/50 px-4 py-2 text-sm text-amber-400">
          The SQL editor is only available for SQL Server data sources.
        </p>
      )}

      {dataSource && isSqlServer && (
        <div className="mt-6">
          <DatabaseExplorer dataSourceId={dataSourceId} />
        </div>
      )}
    </main>
  );
}
