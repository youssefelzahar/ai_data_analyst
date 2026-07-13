"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  applyCleaningPipeline,
  getCleaningMethods,
  getCleaningRecommendations,
  listDatasetVersions,
  previewCleaningPipeline,
  undoLastDatasetVersion,
} from "@/services/data-cleaning";
import { listDataSourceTables } from "@/services/data-profile";
import type {
  CleaningCategory,
  CleaningMethodsCatalog,
  CleaningRecommendationsResponse,
  DatasetVersionResponse,
  PipelinePreviewResponse,
  RecommendationItem,
} from "@/types/data-cleaning";
import type { DataSourceType } from "@/types/data-source";

const CATEGORY_LABELS: Record<CleaningCategory, string> = {
  missing_values: "Missing Values",
  duplicates: "Duplicates",
  type_conversion: "Data Type Conversion",
  outliers: "Outlier Handling",
  encoding: "Categorical Encoding",
  scaling: "Numerical Scaling",
  skew: "Skewed Features",
  text: "Text Preprocessing",
};

const CATEGORY_ORDER: CleaningCategory[] = [
  "missing_values",
  "duplicates",
  "type_conversion",
  "outliers",
  "encoding",
  "scaling",
  "skew",
  "text",
];

interface PipelineItem {
  id: string;
  category: CleaningCategory;
  operationKey: string;
  columnName: string | null;
  reason: string;
}

let pipelineItemCounter = 0;
function nextPipelineItemId(): string {
  pipelineItemCounter += 1;
  return `pipeline-item-${pipelineItemCounter}`;
}

function formatCompactNumber(value: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact" }).format(value);
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

function SampleRowsTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (rows.length === 0) {
    return <p className="p-3 text-sm text-slate-500">No rows.</p>;
  }
  const columns = Object.keys(rows[0]);
  return (
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
              <td key={column} className="whitespace-nowrap px-3 py-2 text-slate-300">
                {formatCellValue(row[column])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function RecommendationCard({
  item,
  methodsCatalog,
  onAdd,
}: {
  item: RecommendationItem;
  methodsCatalog: CleaningMethodsCatalog | null;
  onAdd: (operationKey: string, label: string) => void;
}) {
  const alternatives = methodsCatalog?.methods.filter((method) => method.category === item.category) ?? [];
  const [selectedKey, setSelectedKey] = useState(item.recommended_operation_key);

  const selectedLabel =
    alternatives.find((method) => method.key === selectedKey)?.label ?? item.recommended_label;

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="font-medium text-slate-200">{item.column_name ?? "Whole dataset"}</p>
          <p className="mt-1 text-xs text-slate-500">{item.reason}</p>
        </div>
        <div className="flex items-center gap-2">
          {alternatives.length > 0 && (
            <select
              className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs focus:border-sky-500 focus:outline-none"
              value={selectedKey}
              onChange={(event) => setSelectedKey(event.target.value)}
            >
              {alternatives.map((method) => (
                <option key={method.key} value={method.key}>
                  {method.label}
                  {method.key === item.recommended_operation_key ? " (recommended)" : ""}
                </option>
              ))}
            </select>
          )}
          <button
            onClick={() => onAdd(selectedKey, selectedLabel)}
            className="rounded-lg border border-sky-700 px-3 py-1.5 text-xs text-sky-400 hover:bg-sky-950/50"
          >
            Add to pipeline
          </button>
        </div>
      </div>
    </div>
  );
}

interface DataCleaningProps {
  dataSourceId: string;
  sourceType: DataSourceType;
}

export default function DataCleaning({ dataSourceId, sourceType }: DataCleaningProps) {
  const [availableTables, setAvailableTables] = useState<string[] | null>(null);
  const [selectedTable, setSelectedTable] = useState<string>("");

  const [recommendations, setRecommendations] = useState<CleaningRecommendationsResponse | null>(null);
  const [methodsCatalog, setMethodsCatalog] = useState<CleaningMethodsCatalog | null>(null);
  const [versions, setVersions] = useState<DatasetVersionResponse[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [pipeline, setPipeline] = useState<PipelineItem[]>([]);
  const [preview, setPreview] = useState<PipelinePreviewResponse | null>(null);
  const [isPreviewing, setIsPreviewing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [isUndoing, setIsUndoing] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const tableName = sourceType === "sql_server" ? selectedTable : undefined;

  useEffect(() => {
    if (sourceType !== "sql_server") return;
    listDataSourceTables(dataSourceId)
      .then(setAvailableTables)
      .catch((error) => setLoadError(error instanceof Error ? error.message : "Failed to load tables"));
  }, [dataSourceId, sourceType]);

  const refresh = useCallback(() => {
    if (sourceType === "sql_server" && !selectedTable) return;
    setLoadError(null);
    Promise.all([
      getCleaningRecommendations(dataSourceId, tableName),
      getCleaningMethods(dataSourceId),
      listDatasetVersions(dataSourceId),
    ])
      .then(([recommendationsResult, methodsResult, versionsResult]) => {
        setRecommendations(recommendationsResult);
        setMethodsCatalog(methodsResult);
        setVersions(versionsResult);
      })
      .catch((error) => setLoadError(error instanceof Error ? error.message : "Failed to load recommendations"));
  }, [dataSourceId, sourceType, selectedTable, tableName]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const addToPipeline = useCallback(
    (item: RecommendationItem, operationKey: string) => {
      setPipeline((current) => [
        ...current,
        {
          id: nextPipelineItemId(),
          category: item.category,
          operationKey,
          columnName: item.column_name,
          reason: item.reason,
        },
      ]);
      setPreview(null);
    },
    [],
  );

  const removeFromPipeline = useCallback((id: string) => {
    setPipeline((current) => current.filter((step) => step.id !== id));
    setPreview(null);
  }, []);

  const moveStep = useCallback((id: string, direction: -1 | 1) => {
    setPipeline((current) => {
      const index = current.findIndex((step) => step.id === id);
      const targetIndex = index + direction;
      if (index === -1 || targetIndex < 0 || targetIndex >= current.length) return current;
      const next = [...current];
      [next[index], next[targetIndex]] = [next[targetIndex], next[index]];
      return next;
    });
    setPreview(null);
  }, []);

  const operationSpecs = useMemo(
    () =>
      pipeline.map((step) => ({
        operation_key: step.operationKey,
        column_name: step.columnName,
        params: {},
      })),
    [pipeline],
  );

  const handlePreview = useCallback(() => {
    if (pipeline.length === 0) return;
    setIsPreviewing(true);
    setActionError(null);
    setSuccessMessage(null);
    previewCleaningPipeline(dataSourceId, operationSpecs, tableName)
      .then(setPreview)
      .catch((error) => setActionError(error instanceof Error ? error.message : "Preview failed"))
      .finally(() => setIsPreviewing(false));
  }, [dataSourceId, operationSpecs, pipeline.length, tableName]);

  const handleApply = useCallback(() => {
    if (pipeline.length === 0) return;
    setIsApplying(true);
    setActionError(null);
    applyCleaningPipeline(dataSourceId, operationSpecs, tableName)
      .then((version) => {
        setSuccessMessage(`Applied as version ${version.version_number}.`);
        setPipeline([]);
        setPreview(null);
        refresh();
      })
      .catch((error) => setActionError(error instanceof Error ? error.message : "Apply failed"))
      .finally(() => setIsApplying(false));
  }, [dataSourceId, operationSpecs, pipeline.length, tableName, refresh]);

  const handleCancel = useCallback(() => {
    setPipeline([]);
    setPreview(null);
    setActionError(null);
  }, []);

  const handleUndo = useCallback(() => {
    setIsUndoing(true);
    setActionError(null);
    undoLastDatasetVersion(dataSourceId)
      .then(() => {
        setSuccessMessage("Reverted the most recent version.");
        refresh();
      })
      .catch((error) => setActionError(error instanceof Error ? error.message : "Undo failed"))
      .finally(() => setIsUndoing(false));
  }, [dataSourceId, refresh]);

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
            <option value="">{availableTables === null ? "Loading tables…" : "Select a table"}</option>
            {availableTables?.map((tableOption) => (
              <option key={tableOption} value={tableOption}>
                {tableOption}
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

  if (!recommendations || !methodsCatalog) {
    return <p className="text-sm text-slate-500">Analyzing dataset…</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
      <div className="space-y-8">
        {CATEGORY_ORDER.map((category) => {
          const items = recommendations[category];
          if (items.length === 0) return null;
          return (
            <section key={category}>
              <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
                {CATEGORY_LABELS[category]}
              </h3>
              <div className="space-y-3">
                {items.map((item, index) => (
                  <RecommendationCard
                    key={`${category}-${item.column_name ?? "dataset"}-${index}`}
                    item={item}
                    methodsCatalog={methodsCatalog}
                    onAdd={(operationKey) => addToPipeline(item, operationKey)}
                  />
                ))}
              </div>
            </section>
          );
        })}

        {CATEGORY_ORDER.every((category) => recommendations[category].length === 0) && (
          <p className="rounded-xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-400">
            No cleaning issues detected — this dataset looks clean.
          </p>
        )}
      </div>

      <div className="space-y-6">
        <section>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
            Cleaning pipeline
          </h3>
          {pipeline.length === 0 ? (
            <p className="rounded-xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-500">
              Add recommendations from the left to build a pipeline.
            </p>
          ) : (
            <div className="space-y-2">
              {pipeline.map((step, index) => (
                <div key={step.id}>
                  <div className="rounded-xl border border-slate-800 bg-slate-900 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium text-slate-200">
                          {CATEGORY_LABELS[step.category]}
                          {step.columnName ? ` · ${step.columnName}` : ""}
                        </p>
                        <p className="text-xs text-slate-500">
                          {methodsCatalog.methods.find((m) => m.key === step.operationKey)?.label ??
                            step.operationKey}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => moveStep(step.id, -1)}
                          disabled={index === 0}
                          className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:text-slate-200 disabled:opacity-30"
                        >
                          ↑
                        </button>
                        <button
                          onClick={() => moveStep(step.id, 1)}
                          disabled={index === pipeline.length - 1}
                          className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:text-slate-200 disabled:opacity-30"
                        >
                          ↓
                        </button>
                        <button
                          onClick={() => removeFromPipeline(step.id)}
                          className="rounded border border-red-900 px-2 py-1 text-xs text-red-400 hover:bg-red-950/50"
                        >
                          Remove
                        </button>
                      </div>
                    </div>
                  </div>
                  {index < pipeline.length - 1 && (
                    <p className="py-1 text-center text-slate-600" aria-hidden>
                      ↓
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            <button
              onClick={handlePreview}
              disabled={pipeline.length === 0 || isPreviewing}
              className="rounded-lg border border-sky-700 px-3 py-1.5 text-sm text-sky-400 hover:bg-sky-950/50 disabled:opacity-40"
            >
              {isPreviewing ? "Previewing…" : "Preview"}
            </button>
            <button
              onClick={handleApply}
              disabled={pipeline.length === 0 || isApplying}
              className="rounded-lg border border-emerald-700 px-3 py-1.5 text-sm text-emerald-400 hover:bg-emerald-950/50 disabled:opacity-40"
            >
              {isApplying ? "Applying…" : "Apply"}
            </button>
            <button
              onClick={handleCancel}
              disabled={pipeline.length === 0}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-400 hover:text-slate-200 disabled:opacity-40"
            >
              Cancel
            </button>
          </div>

          {actionError && (
            <p className="mt-3 rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
              {actionError}
            </p>
          )}
          {successMessage && !actionError && (
            <p className="mt-3 rounded-lg border border-emerald-900 bg-emerald-950/50 px-4 py-2 text-sm text-emerald-400">
              {successMessage}
            </p>
          )}
        </section>

        <section>
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
              Applied versions
            </h3>
            <button
              onClick={handleUndo}
              disabled={versions.length === 0 || isUndoing}
              className="rounded-lg border border-amber-700 px-3 py-1 text-xs text-amber-400 hover:bg-amber-950/50 disabled:opacity-40"
            >
              {isUndoing ? "Undoing…" : "Undo last"}
            </button>
          </div>
          {versions.length === 0 ? (
            <p className="rounded-xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-500">
              No cleaning has been applied yet — the dataset is unchanged.
            </p>
          ) : (
            <div className="space-y-2">
              {versions.map((version) => (
                <div key={version.id} className="rounded-xl border border-slate-800 bg-slate-900 p-3">
                  <p className="text-sm font-medium text-slate-200">
                    Version {version.version_number}
                  </p>
                  <p className="text-xs text-slate-500">
                    {formatCompactNumber(version.row_count)} rows · {version.column_count} columns ·{" "}
                    {version.operations_summary.length} operation(s)
                  </p>
                </div>
              ))}
            </div>
          )}
        </section>

        {preview && (
          <section>
            <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
              Preview
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <StatTile label="Rows before" value={formatCompactNumber(preview.before_overview.row_count)} />
              <StatTile label="Rows after" value={formatCompactNumber(preview.after_overview.row_count)} />
              <StatTile
                label="Columns before"
                value={formatCompactNumber(preview.before_overview.column_count)}
              />
              <StatTile
                label="Columns after"
                value={formatCompactNumber(preview.after_overview.column_count)}
              />
              <StatTile
                label="Missing before"
                value={formatCompactNumber(preview.before_overview.total_missing_values)}
              />
              <StatTile
                label="Missing after"
                value={formatCompactNumber(preview.after_overview.total_missing_values)}
              />
            </div>

            <div className="mt-4 space-y-2">
              {preview.steps.map((step, index) => (
                <div key={index} className="rounded-lg border border-slate-800 bg-slate-900 p-3 text-sm">
                  <p className="text-slate-200">{step.message}</p>
                  <p className="text-xs text-slate-500">
                    Affected: {step.affected_row_count} row(s), {step.affected_column_count} column(s)
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-4 space-y-3">
              <div>
                <p className="mb-1 text-xs font-medium text-slate-500">Before (sample)</p>
                <div className="overflow-x-auto rounded-lg border border-slate-800">
                  <SampleRowsTable rows={preview.sample_before_rows} />
                </div>
              </div>
              <div>
                <p className="mb-1 text-xs font-medium text-slate-500">After (sample)</p>
                <div className="overflow-x-auto rounded-lg border border-slate-800">
                  <SampleRowsTable rows={preview.sample_after_rows} />
                </div>
              </div>
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
