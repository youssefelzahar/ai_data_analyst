"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getDataProfile, getOutlierRows, listDataSourceTables } from "@/services/data-profile";
import type {
  ColumnProfile,
  DataProfile as DataProfileData,
  OutlierRowsResponse,
} from "@/types/data-profile";
import type { DataSourceType } from "@/types/data-source";

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(value);
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) return "—";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`;
}

function formatNumber(value: number | null): string {
  if (value === null) return "—";
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}

function formatCellValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  return String(value);
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 px-4 py-3">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-1 text-xl font-semibold text-slate-100">{value}</p>
    </div>
  );
}

type WarningSeverity = "warning" | "serious";

function WarningCard({
  severity,
  title,
  detail,
}: {
  severity: WarningSeverity;
  title: string;
  detail: string;
}) {
  const toneClassName =
    severity === "serious"
      ? "border-red-900 bg-red-950/50 text-red-400"
      : "border-amber-900 bg-amber-950/50 text-amber-400";
  return (
    <div className={`rounded-xl border px-4 py-3 ${toneClassName}`}>
      <div className="flex items-center gap-2 text-sm font-semibold">
        <span aria-hidden className="inline-block h-2 w-2 shrink-0 rounded-full bg-current" />
        {title}
      </div>
      <p className="mt-1 text-xs text-slate-300">{detail}</p>
    </div>
  );
}

type ColumnSortKey = "column_name" | "dtype" | "missing_count" | "unique_count";

function sortColumns(
  columns: ColumnProfile[],
  sortKey: ColumnSortKey,
  sortDirection: "asc" | "desc",
): ColumnProfile[] {
  const sorted = [...columns].sort((a, b) => {
    const left = a[sortKey];
    const right = b[sortKey];
    if (typeof left === "number" && typeof right === "number") return left - right;
    return String(left).localeCompare(String(right));
  });
  return sortDirection === "asc" ? sorted : sorted.reverse();
}

interface DataProfileProps {
  dataSourceId: string;
  sourceType: DataSourceType;
}

export default function DataProfile({ dataSourceId, sourceType }: DataProfileProps) {
  const [availableTables, setAvailableTables] = useState<string[] | null>(null);
  const [selectedTable, setSelectedTable] = useState<string>("");
  const [profile, setProfile] = useState<DataProfileData | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [columnSearch, setColumnSearch] = useState("");
  const [sortKey, setSortKey] = useState<ColumnSortKey>("column_name");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");

  const [expandedOutlierColumns, setExpandedOutlierColumns] = useState<Set<string>>(new Set());
  const [outlierRowsByColumn, setOutlierRowsByColumn] = useState<
    Record<string, OutlierRowsResponse | "loading" | "error">
  >({});

  useEffect(() => {
    if (sourceType !== "sql_server") return;
    listDataSourceTables(dataSourceId)
      .then(setAvailableTables)
      .catch((error) =>
        setLoadError(error instanceof Error ? error.message : "Failed to load tables"),
      );
  }, [dataSourceId, sourceType]);

  useEffect(() => {
    if (sourceType === "sql_server" && !selectedTable) return;
    setProfile(null);
    setLoadError(null);
    getDataProfile(dataSourceId, sourceType === "sql_server" ? selectedTable : undefined)
      .then(setProfile)
      .catch((error) =>
        setLoadError(error instanceof Error ? error.message : "Failed to load profile"),
      );
  }, [dataSourceId, sourceType, selectedTable]);

  const toggleSort = useCallback(
    (key: ColumnSortKey) => {
      if (key === sortKey) {
        setSortDirection((direction) => (direction === "asc" ? "desc" : "asc"));
      } else {
        setSortKey(key);
        setSortDirection("asc");
      }
    },
    [sortKey],
  );

  const filteredSortedColumns = useMemo(() => {
    if (!profile) return [];
    const matching = profile.columns.filter((column) =>
      column.column_name.toLowerCase().includes(columnSearch.toLowerCase()),
    );
    return sortColumns(matching, sortKey, sortDirection);
  }, [profile, columnSearch, sortKey, sortDirection]);

  const toggleOutlierRows = useCallback(
    (columnName: string) => {
      setExpandedOutlierColumns((current) => {
        const next = new Set(current);
        if (next.has(columnName)) {
          next.delete(columnName);
        } else {
          next.add(columnName);
          if (!outlierRowsByColumn[columnName]) {
            setOutlierRowsByColumn((rows) => ({ ...rows, [columnName]: "loading" }));
            getOutlierRows(dataSourceId, columnName, sourceType === "sql_server" ? selectedTable : undefined)
              .then((result) =>
                setOutlierRowsByColumn((rows) => ({ ...rows, [columnName]: result })),
              )
              .catch(() =>
                setOutlierRowsByColumn((rows) => ({ ...rows, [columnName]: "error" })),
              );
          }
        }
        return next;
      });
    },
    [dataSourceId, sourceType, selectedTable, outlierRowsByColumn],
  );

  if (sourceType === "sql_server" && !selectedTable) {
    return (
      <div className="space-y-4">
        <div>
          <label className="mb-1 block text-sm text-slate-400">Table</label>
          <select
            className="w-full max-w-sm rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm focus:border-sky-500 focus:outline-none"
            value={selectedTable}
            onChange={(event) => setSelectedTable(event.target.value)}
          >
            <option value="">
              {availableTables === null ? "Loading tables…" : "Select a table"}
            </option>
            {availableTables?.map((tableName) => (
              <option key={tableName} value={tableName}>
                {tableName}
              </option>
            ))}
          </select>
        </div>
        {loadError && (
          <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
            {loadError}
          </p>
        )}
      </div>
    );
  }

  if (loadError) {
    return (
      <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
        {loadError}
      </p>
    );
  }

  if (!profile) {
    return <p className="text-sm text-slate-500">Building profile…</p>;
  }

  const { overview, data_quality: dataQuality } = profile;

  const warningCards: { severity: WarningSeverity; title: string; detail: string }[] = [];
  if (overview.total_missing_values > 0) {
    warningCards.push({
      severity: "warning",
      title: "Missing values",
      detail: `${formatCompactNumber(overview.total_missing_values)} missing cells across this dataset.`,
    });
  }
  if (overview.total_duplicate_rows > 0) {
    warningCards.push({
      severity: "warning",
      title: "Duplicate rows",
      detail: `${formatCompactNumber(overview.total_duplicate_rows)} duplicate row(s) detected.`,
    });
  }
  if (dataQuality.constant_columns.length > 0) {
    warningCards.push({
      severity: "warning",
      title: "Constant columns",
      detail: dataQuality.constant_columns.join(", "),
    });
  }
  if (dataQuality.high_cardinality_columns.length > 0) {
    warningCards.push({
      severity: "warning",
      title: "High-cardinality columns",
      detail: dataQuality.high_cardinality_columns.map((column) => column.column_name).join(", "),
    });
  }
  if (dataQuality.mixed_type_columns.length > 0) {
    warningCards.push({
      severity: "serious",
      title: "Mixed data types",
      detail: dataQuality.mixed_type_columns.map((column) => column.column_name).join(", "),
    });
  }

  const sortIndicator = (key: ColumnSortKey) =>
    sortKey === key ? (sortDirection === "asc" ? " ▲" : " ▼") : "";

  return (
    <div className="space-y-8">
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatTile label="Rows" value={formatCompactNumber(overview.row_count)} />
        <StatTile label="Columns" value={formatCompactNumber(overview.column_count)} />
        <StatTile label="Dataset size" value={formatBytes(overview.dataset_size_bytes)} />
        <StatTile label="Memory usage" value={formatBytes(overview.memory_usage_bytes)} />
        <StatTile label="Missing values" value={formatCompactNumber(overview.total_missing_values)} />
        <StatTile label="Duplicate rows" value={formatCompactNumber(overview.total_duplicate_rows)} />
        <StatTile label="Numeric columns" value={formatCompactNumber(overview.numeric_column_count)} />
        <StatTile
          label="Categorical columns"
          value={formatCompactNumber(overview.categorical_column_count)}
        />
      </div>

      {warningCards.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Data quality
          </h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {warningCards.map((card) => (
              <WarningCard key={card.title} {...card} />
            ))}
          </div>
        </section>
      )}

      <section>
        <div className="mb-3 flex items-center justify-between gap-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
            Column summary
          </h3>
          <input
            className="w-48 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm placeholder:text-slate-600 focus:border-sky-500 focus:outline-none"
            placeholder="Search columns…"
            value={columnSearch}
            onChange={(event) => setColumnSearch(event.target.value)}
          />
        </div>
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400">
                {(
                  [
                    ["column_name", "Column"],
                    ["dtype", "Type"],
                    ["missing_count", "Missing"],
                    ["unique_count", "Unique"],
                  ] as [ColumnSortKey, string][]
                ).map(([key, label]) => (
                  <th
                    key={key}
                    className="cursor-pointer select-none px-4 py-2 font-medium hover:text-slate-200"
                    onClick={() => toggleSort(key)}
                  >
                    {label}
                    {sortIndicator(key)}
                  </th>
                ))}
                <th className="px-4 py-2 font-medium">Sample values</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {filteredSortedColumns.map((column) => (
                <tr key={column.column_name}>
                  <td className="px-4 py-2 text-slate-200">{column.column_name}</td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-400">{column.dtype}</td>
                  <td className="px-4 py-2 text-slate-400">
                    {column.missing_count} ({formatPercentage(column.missing_percentage)})
                  </td>
                  <td className="px-4 py-2 text-slate-400">{column.unique_count}</td>
                  <td className="max-w-xs truncate px-4 py-2 text-slate-400">
                    {column.sample_values.map(formatCellValue).join(", ")}
                  </td>
                </tr>
              ))}
              {filteredSortedColumns.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-3 text-center text-slate-500">
                    No columns match “{columnSearch}”.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {profile.numeric_statistics.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Numeric statistics
          </h3>
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  {["Column", "Mean", "Median", "Std dev", "Variance", "Min", "Max", "Skew", "Kurtosis"].map(
                    (label) => (
                      <th key={label} className="whitespace-nowrap px-4 py-2 font-medium">
                        {label}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {profile.numeric_statistics.map((stats) => (
                  <tr key={stats.column_name}>
                    <td className="px-4 py-2 text-slate-200">{stats.column_name}</td>
                    <td className="px-4 py-2 text-slate-400">{formatNumber(stats.mean)}</td>
                    <td className="px-4 py-2 text-slate-400">{formatNumber(stats.median)}</td>
                    <td className="px-4 py-2 text-slate-400">{formatNumber(stats.std_deviation)}</td>
                    <td className="px-4 py-2 text-slate-400">{formatNumber(stats.variance)}</td>
                    <td className="px-4 py-2 text-slate-400">{formatNumber(stats.minimum)}</td>
                    <td className="px-4 py-2 text-slate-400">{formatNumber(stats.maximum)}</td>
                    <td className="px-4 py-2 text-slate-400">{formatNumber(stats.skewness)}</td>
                    <td className="px-4 py-2 text-slate-400">{formatNumber(stats.kurtosis)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {profile.categorical_statistics.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Categorical statistics
          </h3>
          <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  {["Column", "Unique values", "Most frequent", "Frequency", "Cardinality"].map(
                    (label) => (
                      <th key={label} className="whitespace-nowrap px-4 py-2 font-medium">
                        {label}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {profile.categorical_statistics.map((stats) => (
                  <tr key={stats.column_name}>
                    <td className="px-4 py-2 text-slate-200">{stats.column_name}</td>
                    <td className="px-4 py-2 text-slate-400">{stats.unique_count}</td>
                    <td className="px-4 py-2 text-slate-400">
                      {formatCellValue(stats.most_frequent_value)}
                    </td>
                    <td className="px-4 py-2 text-slate-400">{stats.most_frequent_value_count}</td>
                    <td className="px-4 py-2 text-slate-400">
                      {formatPercentage(stats.cardinality_ratio * 100)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {profile.outliers.length > 0 && (
        <section>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Outlier analysis
          </h3>
          <div className="space-y-3">
            {profile.outliers.map((outlier) => {
              const isExpanded = expandedOutlierColumns.has(outlier.column_name);
              const rowsState = outlierRowsByColumn[outlier.column_name];
              return (
                <div
                  key={outlier.column_name}
                  className="rounded-xl border border-slate-800 bg-slate-900 p-4"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <p className="font-medium text-slate-200">{outlier.column_name}</p>
                      <p className="text-xs text-slate-500">
                        {outlier.outlier_count} outliers ({formatPercentage(outlier.outlier_percentage)}) ·
                        method: {outlier.detection_method} · bounds [{formatNumber(outlier.lower_bound)},{" "}
                        {formatNumber(outlier.upper_bound)}]
                      </p>
                    </div>
                    <button
                      onClick={() => toggleOutlierRows(outlier.column_name)}
                      disabled={outlier.outlier_count === 0}
                      className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-400 disabled:opacity-40"
                    >
                      {isExpanded ? "Hide outlier rows" : "View outlier rows"}
                    </button>
                  </div>

                  {isExpanded && (
                    <div className="mt-3 overflow-x-auto rounded-lg border border-slate-800">
                      {rowsState === "loading" && (
                        <p className="p-3 text-sm text-slate-500">Loading outlier rows…</p>
                      )}
                      {rowsState === "error" && (
                        <p className="p-3 text-sm text-red-400">Failed to load outlier rows.</p>
                      )}
                      {rowsState && rowsState !== "loading" && rowsState !== "error" && (
                        <table className="w-full text-left text-sm">
                          <thead>
                            <tr className="border-b border-slate-800 text-slate-400">
                              {rowsState.rows[0] &&
                                Object.keys(rowsState.rows[0]).map((key) => (
                                  <th key={key} className="whitespace-nowrap px-3 py-2 font-medium">
                                    {key}
                                  </th>
                                ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-800">
                            {rowsState.rows.map((row, rowIndex) => (
                              <tr key={rowIndex}>
                                {Object.values(row).map((value, valueIndex) => (
                                  <td
                                    key={valueIndex}
                                    className="whitespace-nowrap px-3 py-2 text-slate-300"
                                  >
                                    {formatCellValue(value)}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}
    </div>
  );
}
