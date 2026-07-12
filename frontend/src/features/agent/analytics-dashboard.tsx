"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  getConversation,
  listConversations,
  sendAgentMessage,
} from "@/services/agent";
import { listDataSources } from "@/services/data-sources";
import type {
  AgentConversation,
  AgentConversationSummary,
  ChartArtifact,
  ConversationMessage,
  DataTableArtifact,
} from "@/types/agent";
import type { DataSource } from "@/types/data-source";

const Plot = dynamic(() => import("react-plotly.js"), { ssr: false });

type DataSourceState =
  | { kind: "loading" }
  | { kind: "ready"; dataSources: DataSource[] }
  | { kind: "error"; message: string };

function createSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}

function exportRowsToCsv(table: DataTableArtifact) {
  const lines = [
    table.columns.join(","),
    ...table.rows.map((row) =>
      table.columns
        .map((column) => JSON.stringify(row[column] ?? ""))
        .join(","),
    ),
  ];
  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8" });
  const downloadUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = downloadUrl;
  link.download = `${table.title.toLowerCase().replace(/\s+/g, "-")}.csv`;
  link.click();
  URL.revokeObjectURL(downloadUrl);
}

function ArtifactTable({ table }: { table: DataTableArtifact }) {
  const [search, setSearch] = useState("");
  const [sortColumn, setSortColumn] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);
  const pageSize = 10;

  const filteredRows = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();
    const baseRows = !normalizedSearch
      ? table.rows
      : table.rows.filter((row) =>
          table.columns.some((column) =>
            String(row[column] ?? "").toLowerCase().includes(normalizedSearch),
          ),
        );

    if (!sortColumn) return baseRows;
    return [...baseRows].sort((left, right) => {
      const leftValue = String(left[sortColumn] ?? "");
      const rightValue = String(right[sortColumn] ?? "");
      const comparison = leftValue.localeCompare(rightValue, undefined, {
        numeric: true,
        sensitivity: "base",
      });
      return sortDirection === "asc" ? comparison : -comparison;
    });
  }, [pageSize, search, sortColumn, sortDirection, table.columns, table.rows]);

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / pageSize));
  const pagedRows = filteredRows.slice((page - 1) * pageSize, page * pageSize);

  useEffect(() => {
    setPage(1);
  }, [search, sortColumn, sortDirection, table.id]);

  function toggleSort(column: string) {
    if (sortColumn === column) {
      setSortDirection((current) => (current === "asc" ? "desc" : "asc"));
      return;
    }
    setSortColumn(column);
    setSortDirection("asc");
  }

  return (
    <div className="space-y-3 rounded-xl border border-slate-800 bg-slate-950 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h4 className="text-sm font-semibold text-slate-200">{table.title}</h4>
        <button
          onClick={() => exportRowsToCsv(table)}
          className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-300"
        >
          Export CSV
        </button>
      </div>
      <input
        value={search}
        onChange={(event) => setSearch(event.target.value)}
        placeholder="Search table..."
        className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-500"
      />
      <div className="overflow-x-auto rounded-xl border border-slate-800">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-800 text-slate-400">
              {table.columns.map((column) => (
                <th key={column} className="px-3 py-2">
                  <button
                    onClick={() => toggleSort(column)}
                    className="font-medium hover:text-sky-300"
                  >
                    {column}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800">
            {pagedRows.map((row, rowIndex) => (
              <tr key={`${table.id}-${rowIndex}`}>
                {table.columns.map((column) => (
                  <td key={column} className="whitespace-nowrap px-3 py-2 text-slate-300">
                    {String(row[column] ?? "-")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between text-xs text-slate-500">
        <span>
          Showing {pagedRows.length} of {filteredRows.length} rows
        </span>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setPage((current) => Math.max(1, current - 1))}
            disabled={page <= 1}
            className="rounded-lg border border-slate-700 px-3 py-1 disabled:opacity-40"
          >
            Previous
          </button>
          <span>
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
            disabled={page >= totalPages}
            className="rounded-lg border border-slate-700 px-3 py-1 disabled:opacity-40"
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}

function ChartCard({ chart }: { chart: ChartArtifact }) {
  const [isFullscreen, setIsFullscreen] = useState(false);

  const chartBody = (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold text-slate-200">{chart.title}</h4>
          {chart.description && <p className="text-xs text-slate-500">{chart.description}</p>}
        </div>
        <button
          onClick={() => setIsFullscreen(true)}
          className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-300"
        >
          Full Screen
        </button>
      </div>
      <Plot
        data={(chart.figure.data as never[]) ?? []}
        layout={{
          autosize: true,
          paper_bgcolor: "#020617",
          plot_bgcolor: "#020617",
          font: { color: "#cbd5e1" },
          ...(chart.figure.layout as Record<string, unknown>),
        }}
        config={{
          responsive: true,
          displaylogo: false,
          toImageButtonOptions: { format: "png", filename: chart.title },
        }}
        useResizeHandler
        style={{ width: "100%", height: "420px" }}
      />
    </div>
  );

  return (
    <>
      {chartBody}
      {isFullscreen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/90 p-6">
          <div className="w-full max-w-6xl rounded-2xl border border-slate-800 bg-slate-900 p-4">
            <div className="mb-3 flex justify-end">
              <button
                onClick={() => setIsFullscreen(false)}
                className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-sky-700 hover:text-sky-300"
              >
                Close
              </button>
            </div>
            <Plot
              data={(chart.figure.data as never[]) ?? []}
              layout={{
                autosize: true,
                paper_bgcolor: "#0f172a",
                plot_bgcolor: "#0f172a",
                font: { color: "#cbd5e1" },
                ...(chart.figure.layout as Record<string, unknown>),
              }}
              config={{
                responsive: true,
                displaylogo: false,
                toImageButtonOptions: { format: "png", filename: chart.title },
              }}
              useResizeHandler
              style={{ width: "100%", height: "70vh" }}
            />
          </div>
        </div>
      )}
    </>
  );
}

function MessageVisualizations({ message }: { message: ConversationMessage }) {
  const { visualizations } = message;
  if (
    visualizations.kpi_cards.length === 0 &&
    visualizations.tables.length === 0 &&
    visualizations.charts.length === 0
  ) {
    return null;
  }

  return (
    <div className="mt-4 space-y-4">
      {visualizations.kpi_cards.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {visualizations.kpi_cards.map((card) => (
            <div
              key={card.id}
              className="rounded-xl border border-slate-800 bg-slate-950 p-4"
            >
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {card.title}
              </p>
              <p className="mt-2 text-2xl font-semibold text-slate-100">{card.value}</p>
              {card.subtitle && <p className="mt-1 text-xs text-slate-500">{card.subtitle}</p>}
            </div>
          ))}
        </div>
      )}

      {visualizations.tables.map((table) => (
        <ArtifactTable key={table.id} table={table} />
      ))}

      {visualizations.charts.length > 0 && (
        <div className="grid gap-4 xl:grid-cols-2">
          {visualizations.charts.map((chart) => (
            <ChartCard key={chart.id} chart={chart} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function AnalyticsDashboard() {
  const [sessionId, setSessionId] = useState("");
  const [dataSourceState, setDataSourceState] = useState<DataSourceState>({
    kind: "loading",
  });
  const [selectedDataSourceId, setSelectedDataSourceId] = useState("");
  const [conversationSummaries, setConversationSummaries] = useState<AgentConversationSummary[]>([]);
  const [activeConversation, setActiveConversation] = useState<AgentConversation | null>(null);
  const [draftMessage, setDraftMessage] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    const freshSessionId = createSessionId();
    setSessionId(freshSessionId);
    void refreshConversations();
    listDataSources()
      .then((dataSources) => setDataSourceState({ kind: "ready", dataSources }))
      .catch((error: Error) =>
        setDataSourceState({ kind: "error", message: error.message }),
      );
  }, []);

  async function refreshConversations() {
    try {
      const response = await listConversations();
      setConversationSummaries(response.conversations);
    } catch {
      // keep stale list if unavailable
    }
  }

  async function openConversation(targetSessionId: string) {
    try {
      const conversation = await getConversation(targetSessionId);
      setActiveConversation(conversation);
      setSessionId(conversation.session_id);
      setSelectedDataSourceId(conversation.selected_data_source_id ?? "");
      setErrorMessage(null);
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Failed to load conversation.");
    }
  }

  function startNewConversation() {
    setSessionId(createSessionId());
    setActiveConversation(null);
    setDraftMessage("");
    setErrorMessage(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMessage = draftMessage.trim();
    if (!trimmedMessage || isSending || !sessionId) return;

    setIsSending(true);
    setErrorMessage(null);
    try {
      await sendAgentMessage({
        message: trimmedMessage,
        session_id: sessionId,
        selected_data_source_id: selectedDataSourceId || null,
      });
      const conversation = await getConversation(sessionId);
      setActiveConversation(conversation);
      setDraftMessage("");
      await refreshConversations();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : "Unable to reach the agent.");
    } finally {
      setIsSending(false);
    }
  }

  const selectedDataSource = useMemo(() => {
    if (dataSourceState.kind !== "ready") return null;
    return (
      dataSourceState.dataSources.find(
        (dataSource) => dataSource.id === selectedDataSourceId,
      ) ?? null
    );
  }, [dataSourceState, selectedDataSourceId]);

  const messages = activeConversation?.messages ?? [];

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen w-full max-w-[1600px] flex-col gap-6 px-5 py-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-slate-800 pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Analytics Dashboard</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-400">
              Persisted chat, KPI cards, interactive charts, and data tables generated by the AI agent.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              onClick={startNewConversation}
              className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:border-sky-500 hover:text-white"
            >
              New Conversation
            </button>
            <Link
              href="/data-sources"
              className="rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:border-sky-500 hover:text-white"
            >
              Manage Data Sources
            </Link>
          </div>
        </header>

        <section className="grid flex-1 gap-6 lg:grid-cols-[300px_minmax(0,1fr)]">
          <aside className="flex min-h-0 flex-col gap-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4">
              <label
                htmlFor="data-source"
                className="text-xs font-semibold uppercase tracking-wide text-slate-400"
              >
                Current Data Source
              </label>
              <select
                id="data-source"
                value={selectedDataSourceId}
                onChange={(event) => setSelectedDataSourceId(event.target.value)}
                className="mt-3 w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 outline-none focus:border-sky-500"
                disabled={dataSourceState.kind !== "ready"}
              >
                <option value="">No data source selected</option>
                {dataSourceState.kind === "ready" &&
                  dataSourceState.dataSources.map((dataSource) => (
                    <option key={dataSource.id} value={dataSource.id}>
                      {dataSource.name}
                    </option>
                  ))}
              </select>
              <p className="mt-3 text-sm text-slate-300">
                {selectedDataSource
                  ? `${selectedDataSource.name} (${selectedDataSource.source_type})`
                  : "None selected"}
              </p>
            </div>

            <div className="min-h-0 flex-1 rounded-xl border border-slate-800 bg-slate-900/70 p-4">
              <div className="mb-3 flex items-center justify-between gap-3">
                <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Conversations
                </h2>
                <span className="text-xs text-slate-500">{conversationSummaries.length}</span>
              </div>
              <div className="space-y-2 overflow-y-auto pr-1">
                {conversationSummaries.map((conversation) => (
                  <button
                    key={conversation.session_id}
                    onClick={() => void openConversation(conversation.session_id)}
                    className={`w-full rounded-xl border px-3 py-3 text-left transition ${
                      sessionId === conversation.session_id
                        ? "border-sky-500 bg-sky-950/40"
                        : "border-slate-800 bg-slate-950 hover:border-slate-700"
                    }`}
                  >
                    <p className="text-sm font-medium text-slate-200">
                      {conversation.title ?? "Untitled conversation"}
                    </p>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-500">
                      {conversation.last_message_preview ?? "No messages yet."}
                    </p>
                  </button>
                ))}
                {conversationSummaries.length === 0 && (
                  <p className="text-sm text-slate-500">No saved conversations yet.</p>
                )}
              </div>
            </div>
          </aside>

          <section className="flex min-h-[720px] flex-col rounded-xl border border-slate-800 bg-slate-900">
            <div className="border-b border-slate-800 px-5 py-4">
              <h2 className="text-lg font-semibold">
                {activeConversation?.title ?? "New Conversation"}
              </h2>
              <p className="mt-1 text-sm text-slate-400">
                Session {sessionId ? sessionId.slice(0, 8) : "starting"}
              </p>
            </div>

            <div className="flex-1 space-y-6 overflow-y-auto px-5 py-5">
              {messages.length === 0 ? (
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-6 text-sm text-slate-400">
                  Ask for a dashboard, KPI cards, or a chart like a histogram, scatter plot, or heatmap.
                </div>
              ) : (
                messages.map((message) => (
                  <article
                    key={message.id}
                    className={`rounded-xl px-4 py-4 text-sm leading-6 ${
                      message.role === "user"
                        ? "ml-auto max-w-3xl bg-sky-600 text-white"
                        : "border border-slate-800 bg-slate-950 text-slate-200"
                    }`}
                  >
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <p className="font-medium">
                        {message.role === "user" ? "You" : "AI Analyst"}
                      </p>
                      <p className="text-xs text-slate-400">
                        {new Date(message.created_at).toLocaleString()}
                      </p>
                    </div>
                    <p className="whitespace-pre-wrap">{message.content}</p>
                    {message.role === "assistant" && <MessageVisualizations message={message} />}
                  </article>
                ))
              )}
            </div>

            {errorMessage && (
              <p className="border-t border-slate-800 px-5 py-3 text-sm text-red-400">
                {errorMessage}
              </p>
            )}

            <form
              onSubmit={handleSubmit}
              className="flex flex-col gap-3 border-t border-slate-800 p-4"
            >
              <textarea
                value={draftMessage}
                onChange={(event) => setDraftMessage(event.target.value)}
                placeholder="Ask for KPI cards, charts, a dashboard, or a data table..."
                className="min-h-20 resize-none rounded-md border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-500"
              />
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs text-slate-500">
                  The agent saves chat history and generated visualizations for this conversation.
                </p>
                <button
                  type="submit"
                  disabled={!draftMessage.trim() || isSending || !sessionId}
                  className="rounded-md bg-sky-600 px-5 py-3 text-sm font-semibold text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
                >
                  {isSending ? "Generating..." : "Send"}
                </button>
              </div>
            </form>
          </section>
        </section>
      </div>
    </main>
  );
}
