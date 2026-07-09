"use client";

import Link from "next/link";
import { useState } from "react";
import { convertQueryToDataset, executeQuery } from "@/services/sql-query";
import type { DataSource } from "@/types/data-source";
import type { QueryResultResponse } from "@/types/sql-query";

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(value);
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  return String(value);
}

function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-slate-500">The query returned no rows.</p>;
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-slate-400">
            {Object.keys(rows[0]).map((key) => (
              <th key={key} className="whitespace-nowrap px-3 py-2 font-medium">
                {key}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {Object.values(row).map((value, valueIndex) => (
                <td key={valueIndex} className="whitespace-nowrap px-3 py-2 text-slate-300">
                  {formatCellValue(value)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SqlEditorPanel({ dataSourceId }: { dataSourceId: string }) {
  const [sql, setSql] = useState("SELECT TOP 100 * FROM ");
  const [isExecuting, setIsExecuting] = useState(false);
  const [isConverting, setIsConverting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [result, setResult] = useState<QueryResultResponse | null>(null);
  const [savedDataset, setSavedDataset] = useState<DataSource | null>(null);

  const trimmedSql = sql.trim();
  const isBusy = isExecuting || isConverting;

  const handleExecute = async () => {
    if (!trimmedSql) {
      setErrorMessage("Enter a SQL query to execute.");
      return;
    }
    setIsExecuting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setSavedDataset(null);
    try {
      setResult(await executeQuery(dataSourceId, trimmedSql));
    } catch (error) {
      setResult(null);
      setErrorMessage(error instanceof Error ? error.message : "Query failed");
    } finally {
      setIsExecuting(false);
    }
  };

  const handleConvert = async () => {
    if (!trimmedSql) {
      setErrorMessage("Enter a SQL query to convert.");
      return;
    }
    setIsConverting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const converted = await convertQueryToDataset(dataSourceId, trimmedSql);
      setSavedDataset(converted);
      setSuccessMessage(`Saved \"${converted.original_filename ?? converted.name}\" to Data Sources.`);
    } catch (error) {
      setSavedDataset(null);
      setErrorMessage(error instanceof Error ? error.message : "Conversion failed");
    } finally {
      setIsConverting(false);
    }
  };

  const inputClassName =
    "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-sm " +
    "placeholder:text-slate-600 focus:border-sky-500 focus:outline-none";

  return (
    <div className="space-y-6">
      <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-6">
        <div>
          <label className="mb-1 block text-sm text-slate-400">SQL query (read-only SELECT)</label>
          <textarea
            className={inputClassName}
            rows={8}
            spellCheck={false}
            value={sql}
            onChange={(event) => setSql(event.target.value)}
            placeholder="SELECT TOP 100 * FROM your_table"
          />
        </div>

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

        <div className="flex gap-3">
          <button
            onClick={() => void handleExecute()}
            disabled={isBusy}
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
          >
            {isExecuting ? "Executing..." : "Execute"}
          </button>
          <button
            onClick={() => void handleConvert()}
            disabled={isBusy}
            title="Runs the query and saves the result as a dataset with preview/profile pages"
            className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium hover:border-sky-500 disabled:opacity-50"
          >
            {isConverting ? "Converting..." : "Convert to pandas"}
          </button>
        </div>
      </div>

      {savedDataset && (
        <section className="space-y-3 rounded-xl border border-slate-800 bg-slate-900 p-4">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Saved dataset</h2>
          <p className="text-sm text-slate-300">
            The query output is now saved and available outside this editor.
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
          </div>
        </section>
      )}

      {result && (
        <section className="space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">Results</h2>
          <p className="text-xs text-slate-500">
            {result.truncated
              ? `Showing first ${result.rows.length} of ${formatCompactNumber(result.row_count)} rows (truncated).`
              : `${formatCompactNumber(result.row_count)} row${result.row_count === 1 ? "" : "s"}.`}
          </p>
          <ResultTable rows={result.rows} />
        </section>
      )}
    </div>
  );
}
