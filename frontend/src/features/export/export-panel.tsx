"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { listDatasetVersions } from "@/services/data-cleaning";
import { downloadExport, getExportReport, listExportFormats } from "@/services/export";
import { listDataSources } from "@/services/data-sources";
import type { DatasetVersionResponse } from "@/types/data-cleaning";
import type { DataSource } from "@/types/data-source";
import type {
  CleaningVersionSummary,
  ExportFormatDescriptor,
  ExportReport,
} from "@/types/export";

type ReportState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ready"; report: ExportReport }
  | { kind: "error"; message: string };

type Toast = { id: number; type: "success" | "error"; message: string };

const FORMAT_ICON: Record<string, string> = {
  pdf: "📄",
  excel: "📊",
  powerbi: "📈",
};

export default function ExportPanel({
  dataSourceId: fixedDataSourceId,
}: {
  dataSourceId?: string;
}) {
  const allowDataSourceSelection = !fixedDataSourceId;

  const [dataSources, setDataSources] = useState<DataSource[]>([]);
  const [selectedDataSourceId, setSelectedDataSourceId] = useState(fixedDataSourceId ?? "");
  const [versions, setVersions] = useState<DatasetVersionResponse[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState("");
  const [formats, setFormats] = useState<ExportFormatDescriptor[]>([]);
  const [reportState, setReportState] = useState<ReportState>({ kind: "idle" });
  const [busyFormat, setBusyFormat] = useState<string | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const pushToast = useCallback((type: Toast["type"], message: string) => {
    const id = Date.now() + Math.random();
    setToasts((current) => [...current, { id, type, message }]);
    setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 6000);
  }, []);

  // Load selectable data sources (only when no fixed id was provided).
  useEffect(() => {
    if (!allowDataSourceSelection) return;
    listDataSources()
      .then(setDataSources)
      .catch((error: Error) => pushToast("error", error.message));
  }, [allowDataSourceSelection, pushToast]);

  // Load versions + formats whenever the selected data source changes.
  useEffect(() => {
    if (!selectedDataSourceId) {
      setVersions([]);
      setFormats([]);
      return;
    }
    setSelectedVersionId("");
    listDatasetVersions(selectedDataSourceId)
      .then(setVersions)
      .catch(() => setVersions([]));
    listExportFormats(selectedDataSourceId)
      .then((response) => setFormats(response.formats))
      .catch((error: Error) => pushToast("error", error.message));
  }, [selectedDataSourceId, pushToast]);

  const loadReport = useCallback(() => {
    if (!selectedDataSourceId) return;
    setReportState({ kind: "loading" });
    getExportReport(selectedDataSourceId, { versionId: selectedVersionId || null })
      .then((report) => setReportState({ kind: "ready", report }))
      .catch((error: Error) => setReportState({ kind: "error", message: error.message }));
  }, [selectedDataSourceId, selectedVersionId]);

  // Refresh the report preview when the data source or version selection changes.
  useEffect(() => {
    loadReport();
  }, [loadReport]);

  async function handleExport(formatKey: string) {
    if (!selectedDataSourceId || busyFormat) return;
    setBusyFormat(formatKey);
    try {
      const descriptor = formats.find((format) => format.key === formatKey);
      await downloadExport(selectedDataSourceId, formatKey, {
        versionId: selectedVersionId || null,
        fallbackExtension: descriptor?.file_extension,
      });
      const label = descriptor?.label ?? formatKey;
      pushToast("success", `${label} generated and downloaded.`);
    } catch (error) {
      pushToast("error", error instanceof Error ? error.message : "Export failed.");
    } finally {
      setBusyFormat(null);
    }
  }

  const report = reportState.kind === "ready" ? reportState.report : null;
  const cleaningSummary = report?.cleaning_summary ?? null;

  const selectedCleaningVersion = useMemo<CleaningVersionSummary | null>(() => {
    if (!cleaningSummary) return null;
    if (selectedVersionId) {
      return (
        cleaningSummary.versions.find((version) => version.version_id === selectedVersionId) ?? null
      );
    }
    if (cleaningSummary.selected_version_number != null) {
      return (
        cleaningSummary.versions.find(
          (version) => version.version_number === cleaningSummary.selected_version_number,
        ) ?? null
      );
    }
    return null;
  }, [cleaningSummary, selectedVersionId]);

  return (
    <div className="space-y-6">
      {/* Configuration */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Report configuration
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {allowDataSourceSelection && (
            <div>
              <label className="text-xs font-medium text-slate-400" htmlFor="export-data-source">
                Data source
              </label>
              <select
                id="export-data-source"
                value={selectedDataSourceId}
                onChange={(event) => setSelectedDataSourceId(event.target.value)}
                className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
              >
                <option value="">Select a data source…</option>
                {dataSources.map((dataSource) => (
                  <option key={dataSource.id} value={dataSource.id}>
                    {dataSource.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div>
            <label className="text-xs font-medium text-slate-400" htmlFor="export-version">
              Dataset version <span className="text-slate-600">(optional)</span>
            </label>
            <select
              id="export-version"
              value={selectedVersionId}
              onChange={(event) => setSelectedVersionId(event.target.value)}
              disabled={!selectedDataSourceId}
              className="mt-2 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500 disabled:opacity-50"
            >
              <option value="">
                {versions.length > 0
                  ? "Latest cleaned version (default)"
                  : "Original dataset (default)"}
              </option>
              {versions
                .slice()
                .reverse()
                .map((version) => (
                  <option key={version.id} value={version.id}>
                    {version.label ?? `Version ${version.version_number}`} ·{" "}
                    {version.row_count.toLocaleString()} rows
                  </option>
                ))}
            </select>
            <p className="mt-2 text-xs text-slate-500">
              Leave unset to export the current dataset. Choosing a version exports that exact
              cleaned snapshot.
            </p>
          </div>
        </div>
      </section>

      {/* Export actions */}
      <section className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-400">
          Export
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {formats.length === 0 && (
            <p className="text-sm text-slate-500">
              {selectedDataSourceId
                ? "Loading available formats…"
                : "Select a data source to enable exports."}
            </p>
          )}
          {formats.map((format) => {
            const isBusy = busyFormat === format.key;
            const isDisabled = !selectedDataSourceId || (busyFormat !== null && !isBusy);
            return (
              <div
                key={format.key}
                className="flex flex-col rounded-xl border border-slate-800 bg-slate-950 p-4"
              >
                <div className="flex items-center gap-2">
                  <span className="text-lg">{FORMAT_ICON[format.key] ?? "📁"}</span>
                  <h3 className="text-sm font-semibold text-slate-200">{format.label}</h3>
                </div>
                <p className="mt-1 flex-1 text-xs text-slate-500">{format.description}</p>
                <button
                  onClick={() => handleExport(format.key)}
                  disabled={isDisabled}
                  className="mt-3 rounded-md bg-sky-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                >
                  {isBusy ? "Generating…" : `Export ${format.file_extension.toUpperCase()}`}
                </button>
                {isBusy && (
                  <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                    <div className="h-full w-1/2 animate-[progress_1.1s_ease-in-out_infinite] rounded-full bg-sky-500" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <p className="mt-4 text-xs text-slate-500">
          PDF contains the full analysis. Excel contains the processed dataset and analysis
          tables. Power BI produces a dashboard-ready workbook (KPI + chart tables) — open Power BI
          Desktop and use <span className="text-slate-300">Get Data → Excel</span> to build the
          visuals from it.
        </p>
      </section>

      {/* Report preview */}
      {reportState.kind === "loading" && (
        <p className="text-sm text-slate-500">Assembling report preview…</p>
      )}
      {reportState.kind === "error" && (
        <p className="rounded-lg border border-red-900 bg-red-950/50 px-4 py-2 text-sm text-red-400">
          {reportState.message}
        </p>
      )}

      {report && (
        <section className="space-y-6">
          <ReportPreview report={report} />
          {cleaningSummary?.applied && (
            <CleaningVersionViewer
              summary={cleaningSummary}
              highlighted={selectedCleaningVersion}
            />
          )}
        </section>
      )}

      {/* Toast notifications */}
      <div className="pointer-events-none fixed bottom-6 right-6 z-50 flex w-80 flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto rounded-lg border px-4 py-3 text-sm shadow-lg ${
              toast.type === "success"
                ? "border-emerald-800 bg-emerald-950/90 text-emerald-200"
                : "border-red-800 bg-red-950/90 text-red-200"
            }`}
          >
            {toast.message}
          </div>
        ))}
      </div>

      <style jsx global>{`
        @keyframes progress {
          0% {
            transform: translateX(-100%);
          }
          100% {
            transform: translateX(300%);
          }
        }
      `}</style>
    </div>
  );
}

function ReportPreview({ report }: { report: ExportReport }) {
  const summary = report.dataset_summary;
  const severityColor: Record<string, string> = {
    info: "border-sky-800 bg-sky-950/40 text-sky-200",
    warning: "border-amber-800 bg-amber-950/40 text-amber-200",
    critical: "border-red-800 bg-red-950/40 text-red-200",
  };
  const priorityColor: Record<string, string> = {
    low: "text-emerald-300",
    medium: "text-amber-300",
    high: "text-red-300",
  };

  return (
    <div className="space-y-6 rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold text-slate-100">Report preview</h2>
        <span className="text-xs text-slate-500">
          Generated {new Date(report.generated_at).toLocaleString()}
          {summary.version_label ? ` · ${summary.version_label}` : ""}
        </span>
      </div>

      {/* Dataset summary */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryTile label="Rows" value={summary.row_count.toLocaleString()} />
        <SummaryTile label="Columns" value={summary.column_count.toLocaleString()} />
        <SummaryTile
          label="Missing values"
          value={`${summary.total_missing_values.toLocaleString()} (${summary.missing_percentage.toFixed(1)}%)`}
        />
        <SummaryTile label="Duplicate rows" value={summary.total_duplicate_rows.toLocaleString()} />
      </div>

      {/* KPI summary */}
      {report.kpi_summary.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            KPI summary
          </h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {report.kpi_summary.map((card) => (
              <div key={card.id} className="rounded-xl border border-slate-800 bg-slate-950 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {card.title}
                </p>
                <p className="mt-1 text-xl font-semibold text-slate-100">{card.value}</p>
                {card.subtitle && <p className="mt-1 text-xs text-slate-500">{card.subtitle}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Visualizations included */}
      {report.visualizations.charts.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Visualizations included ({report.visualizations.charts.length})
          </h3>
          <div className="flex flex-wrap gap-2">
            {report.visualizations.charts.map((chart) => (
              <span
                key={chart.id}
                className="rounded-full border border-slate-700 bg-slate-950 px-3 py-1 text-xs text-slate-300"
              >
                {chart.title} · {chart.chart_type}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Insights */}
      {report.insights.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            AI insights
          </h3>
          <div className="space-y-2">
            {report.insights.map((insight, index) => (
              <div
                key={index}
                className={`rounded-lg border px-4 py-2 text-sm ${
                  severityColor[insight.severity] ?? severityColor.info
                }`}
              >
                <p className="font-semibold">{insight.title}</p>
                <p className="mt-0.5 text-xs opacity-90">{insight.detail}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommendations */}
      {report.recommendations.length > 0 && (
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Business recommendations
          </h3>
          <ul className="space-y-2">
            {report.recommendations.map((recommendation, index) => (
              <li
                key={index}
                className="rounded-lg border border-slate-800 bg-slate-950 px-4 py-2 text-sm text-slate-300"
              >
                <span className="font-semibold text-slate-100">{recommendation.title}</span>
                <span
                  className={`ml-2 text-xs font-semibold uppercase ${
                    priorityColor[recommendation.priority] ?? "text-slate-400"
                  }`}
                >
                  {recommendation.priority}
                </span>
                <p className="mt-0.5 text-xs text-slate-500">{recommendation.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-slate-100">{value}</p>
    </div>
  );
}

function CleaningVersionViewer({
  summary,
  highlighted,
}: {
  summary: NonNullable<ExportReport["cleaning_summary"]>;
  highlighted: CleaningVersionSummary | null;
}) {
  const [openVersionId, setOpenVersionId] = useState<string | null>(
    highlighted?.version_id ?? summary.versions[summary.versions.length - 1]?.version_id ?? null,
  );

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-100">Cleaning versions</h2>
        <span className="text-xs text-slate-500">{summary.total_versions} version(s)</span>
      </div>
      <p className="mt-1 text-xs text-slate-500">
        Inspect the operations applied in each cleaned snapshot. The version being exported is
        marked.
      </p>
      <div className="mt-4 space-y-2">
        {summary.versions
          .slice()
          .reverse()
          .map((version) => {
            const isOpen = openVersionId === version.version_id;
            const isExported = version.version_number === summary.selected_version_number;
            return (
              <div
                key={version.version_id}
                className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950"
              >
                <button
                  onClick={() =>
                    setOpenVersionId(isOpen ? null : version.version_id)
                  }
                  className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
                >
                  <span className="flex items-center gap-2">
                    <span className="text-sm font-medium text-slate-200">
                      {version.label ?? `Version ${version.version_number}`}
                    </span>
                    {isExported && (
                      <span className="rounded-full border border-sky-700 bg-sky-950/60 px-2 py-0.5 text-[10px] font-semibold uppercase text-sky-300">
                        Exported
                      </span>
                    )}
                  </span>
                  <span className="text-xs text-slate-500">
                    {version.row_count.toLocaleString()} × {version.column_count} ·{" "}
                    {version.operations.length} op(s) {isOpen ? "▲" : "▼"}
                  </span>
                </button>
                {isOpen && (
                  <div className="border-t border-slate-800 px-4 py-3">
                    {version.operations.length === 0 ? (
                      <p className="text-xs text-slate-500">No operations recorded.</p>
                    ) : (
                      <ul className="space-y-1.5">
                        {version.operations.map((operation, index) => (
                          <li key={index} className="text-xs text-slate-300">
                            <span className="font-semibold text-slate-100">
                              {operation.operation_key}
                            </span>
                            {operation.column_name && (
                              <span className="text-slate-400"> · {operation.column_name}</span>
                            )}
                            {operation.message && (
                              <span className="text-slate-500"> — {operation.message}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </div>
            );
          })}
      </div>
    </div>
  );
}
