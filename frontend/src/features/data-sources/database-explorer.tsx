"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { listSqlServerTables } from "@/services/data-sources";
import {
  convertQueryToDataset,
  executeQuery,
  getTableMetadata,
  previewTable,
  validateQuery,
} from "@/services/sql-query";
import type { DataSource } from "@/types/data-source";
import type {
  QueryResultResponse,
  QueryValidationResponse,
  SqlTableMetadataResponse,
  SqlTablePreviewResponse,
} from "@/types/sql-query";

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(value);
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  return String(value);
}

function DataGrid({
  columns,
  rows,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
}) {
  if (columns.length === 0) {
    return <p className="text-sm text-slate-500">No columns available.</p>;
  }

  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">No rows to display.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-400">
            {columns.map((column) => (
              <th key={column} className="whitespace-nowrap px-3 py-2 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {columns.map((column) => (
                <td key={`${rowIndex}-${column}`} className="whitespace-nowrap px-3 py-2 text-slate-300">
                  {formatCellValue(row[column])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PaginationControls({
  page,
  totalPages,
  onPrevious,
  onNext,
}: {
  page: number;
  totalPages: number;
  onPrevious: () => void;
  onNext: () => void;
}) {
  return (
    <div className="flex items-center gap-3 text-xs text-slate-500">
      <button
        onClick={onPrevious}
        disabled={page <= 1}
        className="rounded-lg border border-slate-700 px-3 py-1 hover:border-sky-700 hover:text-sky-400 disabled:opacity-40"
      >
        Previous
      </button>
      <span>
        Page {page} of {totalPages}
      </span>
      <button
        onClick={onNext}
        disabled={page >= totalPages}
        className="rounded-lg border border-slate-700 px-3 py-1 hover:border-sky-700 hover:text-sky-400 disabled:opacity-40"
      >
        Next
      </button>
    </div>
  );
}

export default function DatabaseExplorer({ dataSourceId }: { dataSourceId: string }) {
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [tableMetadata, setTableMetadata] = useState<SqlTableMetadataResponse | null>(null);
  const [tablePreview, setTablePreview] = useState<SqlTablePreviewResponse | null>(null);
  const [tablePreviewPage, setTablePreviewPage] = useState(1);
  const [sql, setSql] = useState("");
  const [queryPage, setQueryPage] = useState(1);
  const [queryResult, setQueryResult] = useState<QueryResultResponse | null>(null);
  const [validationResult, setValidationResult] = useState<QueryValidationResponse | null>(null);
  const [savedDataset, setSavedDataset] = useState<DataSource | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoadingTables, setIsLoadingTables] = useState(false);
  const [isLoadingPreview, setIsLoadingPreview] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isConverting, setIsConverting] = useState(false);

  const isBusy = isExecuting || isConverting || isValidating;
  const inputClassName =
    "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm " +
    "placeholder:text-slate-600 focus:border-sky-500 focus:outline-none";

  useEffect(() => {
    setIsLoadingTables(true);
    listSqlServerTables(dataSourceId)
      .then((tableNames) => {
        setTables(tableNames);
        setSelectedTable((current) => current ?? tableNames[0] ?? null);
        setSql((currentSql) => {
          if (currentSql || tableNames.length === 0) {
            return currentSql;
          }
          return `SELECT TOP 100 * FROM [${tableNames[0]}]`;
        });
      })
      .catch((error) =>
        setErrorMessage(error instanceof Error ? error.message : "Failed to load tables"),
      )
      .finally(() => setIsLoadingTables(false));
  }, [dataSourceId]);

  useEffect(() => {
    if (!selectedTable) return;
    setIsLoadingPreview(true);
    setErrorMessage(null);
    Promise.all([
      getTableMetadata(dataSourceId, selectedTable),
      previewTable(dataSourceId, selectedTable, tablePreviewPage, 25),
    ])
      .then(([metadata, preview]) => {
        setTableMetadata(metadata);
        setTablePreview(preview);
      })
      .catch((error) =>
        setErrorMessage(error instanceof Error ? error.message : "Failed to load table details"),
      )
      .finally(() => setIsLoadingPreview(false));
  }, [dataSourceId, selectedTable, tablePreviewPage]);

  const queryPagination = queryResult?.pagination;
  const previewPagination = tablePreview?.pagination;

  const selectedTableSummary = useMemo(() => {
    if (!selectedTable) return "Choose a table to inspect its schema and sample rows.";
    if (!tablePreview?.pagination) return `Inspecting ${selectedTable}.`;
    return `${formatCompactNumber(tablePreview.pagination.total_rows)} rows in ${selectedTable}.`;
  }, [selectedTable, tablePreview]);

  const handleSelectTable = (tableName: string) => {
    setSelectedTable(tableName);
    setTablePreviewPage(1);
    setSql(`SELECT TOP 100 * FROM [${tableName}]`);
    setValidationResult(null);
    setQueryResult(null);
  };

  const handleValidate = async () => {
    if (!sql.trim()) {
      setErrorMessage("Enter a SQL query to validate.");
      return;
    }
    setIsValidating(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const result = await validateQuery(dataSourceId, sql.trim());
      setValidationResult(result);
      setSuccessMessage(result.message);
    } catch (error) {
      setValidationResult(null);
      setErrorMessage(error instanceof Error ? error.message : "Validation failed");
    } finally {
      setIsValidating(false);
    }
  };

  const runQuery = async (page: number) => {
    if (!sql.trim()) {
      setErrorMessage("Enter a SQL query to execute.");
      return;
    }
    setIsExecuting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setSavedDataset(null);
    try {
      const result = await executeQuery(dataSourceId, sql.trim(), page, 100);
      setQueryResult(result);
      setQueryPage(page);
    } catch (error) {
      setQueryResult(null);
      setErrorMessage(error instanceof Error ? error.message : "Query failed");
    } finally {
      setIsExecuting(false);
    }
  };

  const handleConvert = async () => {
    if (!sql.trim()) {
      setErrorMessage("Enter a SQL query to convert.");
      return;
    }
    setIsConverting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const converted = await convertQueryToDataset(dataSourceId, sql.trim());
      setSavedDataset(converted);
      setSuccessMessage(`Saved "${converted.original_filename ?? converted.name}" to Data Sources.`);
    } catch (error) {
      setSavedDataset(null);
      setErrorMessage(error instanceof Error ? error.message : "Conversion failed");
    } finally {
      setIsConverting(false);
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Database Explorer
          </h2>
          <p className="mt-1 text-sm text-slate-500">{selectedTableSummary}</p>
        </div>

        {isLoadingTables ? (
          <p className="text-sm text-slate-500">Loading tables...</p>
        ) : tables.length === 0 ? (
          <p className="text-sm text-slate-500">No tables found in this database.</p>
        ) : (
          <ul className="space-y-2">
            {tables.map((tableName) => {
              const isActive = tableName === selectedTable;
              return (
                <li key={tableName}>
                  <button
                    onClick={() => handleSelectTable(tableName)}
                    className={`w-full rounded-xl border px-3 py-2 text-left text-sm transition ${
                      isActive
                        ? "border-sky-500 bg-sky-950/40 text-sky-200"
                        : "border-slate-800 bg-slate-950 text-slate-300 hover:border-slate-700"
                    }`}
                  >
                    {tableName}
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </aside>

      <section className="space-y-6">
        {errorMessage && (
          <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
            {errorMessage}
          </p>
        )}
        {successMessage && (
          <p className="rounded-lg border border-emerald-900 bg-emerald-950/50 px-4 py-2 text-sm text-emerald-400">
            {successMessage}
          </p>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
          <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <div className="flex items-center justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold">SQL Editor</h2>
                <p className="text-sm text-slate-400">
                  Read-only `SELECT` and `WITH` queries only.
                </p>
              </div>
            </div>

            <textarea
              className={inputClassName}
              rows={10}
              spellCheck={false}
              value={sql}
              onChange={(event) => setSql(event.target.value)}
              placeholder="SELECT TOP 100 * FROM [your_table]"
            />

            {validationResult && (
              <div className="rounded-xl border border-slate-800 bg-slate-950 px-4 py-3 text-sm text-slate-300">
                <p className="font-medium text-emerald-400">Validation passed</p>
                <p className="mt-1 break-all text-slate-400">{validationResult.normalized_sql}</p>
              </div>
            )}

            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => void handleValidate()}
                disabled={isBusy}
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium hover:border-sky-500 disabled:opacity-50"
              >
                {isValidating ? "Validating..." : "Validate"}
              </button>
              <button
                onClick={() => void runQuery(1)}
                disabled={isBusy}
                className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
              >
                {isExecuting ? "Executing..." : "Execute"}
              </button>
              <button
                onClick={() => void handleConvert()}
                disabled={isBusy}
                className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium hover:border-sky-500 disabled:opacity-50"
              >
                {isConverting ? "Converting..." : "Save as Dataset"}
              </button>
            </div>
          </div>

          <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6">
            <div>
              <h2 className="text-lg font-semibold">Table Details</h2>
              <p className="text-sm text-slate-400">
                {selectedTable ? `Schema for ${selectedTable}` : "Select a table to inspect."}
              </p>
            </div>

            {isLoadingPreview ? (
              <p className="text-sm text-slate-500">Loading table details...</p>
            ) : !tableMetadata ? (
              <p className="text-sm text-slate-500">No table selected.</p>
            ) : (
              <div className="space-y-3">
                <div className="max-h-72 overflow-auto rounded-xl border border-slate-800 bg-slate-950">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr className="border-b border-slate-800 text-slate-400">
                        <th className="px-3 py-2">Column</th>
                        <th className="px-3 py-2">Type</th>
                        <th className="px-3 py-2">Nullable</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {tableMetadata.columns.map((column) => (
                        <tr key={column.column_name}>
                          <td className="px-3 py-2 text-slate-200">{column.column_name}</td>
                          <td className="px-3 py-2 text-slate-400">{column.data_type}</td>
                          <td className="px-3 py-2 text-slate-400">
                            {column.is_nullable ? "Yes" : "No"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">Table Preview</h2>
              <p className="text-sm text-slate-400">
                Paginated sample rows from the selected table.
              </p>
            </div>
            {previewPagination && (
              <PaginationControls
                page={previewPagination.page}
                totalPages={previewPagination.total_pages}
                onPrevious={() => setTablePreviewPage((current) => Math.max(1, current - 1))}
                onNext={() =>
                  setTablePreviewPage((current) =>
                    Math.min(previewPagination.total_pages, current + 1),
                  )
                }
              />
            )}
          </div>
          <p className="text-xs text-slate-500">
            {previewPagination
              ? `Showing ${tablePreview?.rows.length ?? 0} rows from ${formatCompactNumber(
                  previewPagination.total_rows,
                )} total.`
              : "Select a table to preview its rows."}
          </p>
          <DataGrid
            columns={tablePreview?.columns ?? []}
            rows={tablePreview?.rows ?? []}
          />
        </div>

        <div className="space-y-4 rounded-2xl border border-slate-800 bg-slate-900 p-6">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold">Query Results</h2>
              <p className="text-sm text-slate-400">
                Paginated results grid for the executed SQL query.
              </p>
            </div>
            {queryPagination && (
              <PaginationControls
                page={queryPagination.page}
                totalPages={queryPagination.total_pages}
                onPrevious={() => void runQuery(Math.max(1, queryPage - 1))}
                onNext={() => void runQuery(Math.min(queryPagination.total_pages, queryPage + 1))}
              />
            )}
          </div>

          {queryResult && (
            <p className="text-xs text-slate-500">
              {formatCompactNumber(queryResult.row_count)} row
              {queryResult.row_count === 1 ? "" : "s"} returned.
            </p>
          )}

          <DataGrid columns={queryResult?.columns ?? []} rows={queryResult?.rows ?? []} />
        </div>

        {savedDataset && (
          <section className="space-y-3 rounded-2xl border border-slate-800 bg-slate-900 p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Saved Dataset
            </h2>
            <p className="text-sm text-slate-300">
              The query output is saved and available in the standard dataset workflow.
            </p>
            <div className="flex flex-wrap gap-2">
              <Link
                href="/data-sources"
                className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-400"
              >
                Data Sources
              </Link>
              <Link
                href={`/data-sources/${savedDataset.id}/preview`}
                className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-400"
              >
                Preview
              </Link>
              <Link
                href={`/data-sources/${savedDataset.id}/profile`}
                className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-400"
              >
                Data Profile
              </Link>
              <Link
                href={`/data-sources/${savedDataset.id}/cleaning`}
                className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-400"
              >
                Cleaning
              </Link>
            </div>
          </section>
        )}
      </section>
    </div>
  );
}
