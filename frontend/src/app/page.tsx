"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { streamAgentMessage } from "@/services/agent";
import { listDataSources } from "@/services/data-sources";
import type { DataSource } from "@/types/data-source";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

type DataSourceState =
  | { kind: "loading" }
  | { kind: "ready"; dataSources: DataSource[] }
  | { kind: "error"; message: string };

export default function HomePage() {
  const [sessionId, setSessionId] = useState("");
  const [dataSourceState, setDataSourceState] = useState<DataSourceState>({
    kind: "loading",
  });
  const [selectedDataSourceId, setSelectedDataSourceId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi, I am ready to route requests through the new agent foundation. Analysis tools will arrive in a later phase.",
    },
  ]);
  const [draftMessage, setDraftMessage] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setSessionId(createSessionId());
  }, []);

  useEffect(() => {
    listDataSources()
      .then((dataSources) => setDataSourceState({ kind: "ready", dataSources }))
      .catch((error: Error) =>
        setDataSourceState({ kind: "error", message: error.message }),
      );
  }, []);

  const selectedDataSource = useMemo(() => {
    if (dataSourceState.kind !== "ready") return null;
    return (
      dataSourceState.dataSources.find(
        (dataSource) => dataSource.id === selectedDataSourceId,
      ) ?? null
    );
  }, [dataSourceState, selectedDataSourceId]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedMessage = draftMessage.trim();
    if (!trimmedMessage || isStreaming || !sessionId) return;

    const assistantMessageId = createSessionId();
    setErrorMessage(null);
    setDraftMessage("");
    setIsStreaming(true);
    setMessages((currentMessages) => [
      ...currentMessages,
      { id: createSessionId(), role: "user", content: trimmedMessage },
      { id: assistantMessageId, role: "assistant", content: "" },
    ]);

    try {
      await streamAgentMessage(
        {
          message: trimmedMessage,
          session_id: sessionId,
          selected_data_source_id: selectedDataSourceId || null,
        },
        (chunk) => {
          setMessages((currentMessages) =>
            currentMessages.map((message) =>
              message.id === assistantMessageId
                ? { ...message, content: message.content + chunk }
                : message,
            ),
          );
        },
      );
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "Unable to reach the agent.";
      setErrorMessage(message);
      setMessages((currentMessages) =>
        currentMessages.map((chatMessage) =>
          chatMessage.id === assistantMessageId
            ? { ...chatMessage, content: `Agent error: ${message}` }
            : chatMessage,
        ),
      );
    } finally {
      setIsStreaming(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-5 py-6 lg:px-8">
        <header className="flex flex-col gap-4 border-b border-slate-800 pb-5 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">
              AI Data Analyst
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Agent foundation chat with intent detection, tool routing, memory,
              and streamed responses.
            </p>
          </div>
          <Link
            href="/data-sources"
            className="w-fit rounded-md border border-slate-700 px-4 py-2 text-sm font-medium text-slate-200 hover:border-sky-500 hover:text-white"
          >
            Manage Data Sources
          </Link>
        </header>

        <section className="grid flex-1 gap-6 lg:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="flex min-h-0 flex-col gap-4 border-r border-slate-800 pr-0 lg:pr-6">
            <div className="rounded-lg border border-slate-800 bg-slate-900/70 p-4">
              <label
                htmlFor="data-source"
                className="text-xs font-semibold uppercase tracking-wide text-slate-400"
              >
                Current DataSource
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
              {dataSourceState.kind === "loading" && (
                <p className="mt-2 text-xs text-slate-500">Loading sources...</p>
              )}
              {dataSourceState.kind === "error" && (
                <p className="mt-2 text-xs text-red-400">
                  {dataSourceState.message}
                </p>
              )}
            </div>

            <div className="min-h-0 flex-1 rounded-lg border border-slate-800 bg-slate-900/70 p-4">
              <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Conversation History
              </h2>
              <div className="mt-3 space-y-3 overflow-y-auto pr-1">
                {messages.map((message) => (
                  <div key={message.id} className="text-sm">
                    <p className="font-medium text-slate-300">
                      {message.role === "user" ? "You" : "AI"}
                    </p>
                    <p className="mt-1 line-clamp-3 text-slate-500">
                      {message.content || "Streaming..."}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </aside>

          <section className="flex min-h-[620px] flex-col rounded-lg border border-slate-800 bg-slate-900">
            <div className="border-b border-slate-800 px-5 py-4">
              <h2 className="text-lg font-semibold">Chat</h2>
              <p className="mt-1 text-sm text-slate-400">
                Session {sessionId ? sessionId.slice(0, 8) : "starting"}
              </p>
            </div>

            <div className="flex-1 space-y-4 overflow-y-auto px-5 py-5">
              {messages.map((message) => (
                <article
                  key={message.id}
                  className={`max-w-[82%] rounded-lg px-4 py-3 text-sm leading-6 ${
                    message.role === "user"
                      ? "ml-auto bg-sky-600 text-white"
                      : "border border-slate-800 bg-slate-950 text-slate-200"
                  }`}
                >
                  {message.content || "Streaming..."}
                </article>
              ))}
            </div>

            {errorMessage && (
              <p className="border-t border-slate-800 px-5 py-3 text-sm text-red-400">
                {errorMessage}
              </p>
            )}

            <form
              onSubmit={handleSubmit}
              className="flex flex-col gap-3 border-t border-slate-800 p-4 sm:flex-row"
            >
              <textarea
                value={draftMessage}
                onChange={(event) => setDraftMessage(event.target.value)}
                placeholder="Ask the agent what it can help route..."
                className="min-h-14 flex-1 resize-none rounded-md border border-slate-700 bg-slate-950 px-3 py-3 text-sm text-slate-100 outline-none placeholder:text-slate-500 focus:border-sky-500"
              />
              <button
                type="submit"
                disabled={!draftMessage.trim() || isStreaming || !sessionId}
                className="rounded-md bg-sky-600 px-5 py-3 text-sm font-semibold text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:bg-slate-700 disabled:text-slate-400"
              >
                {isStreaming ? "Streaming" : "Send"}
              </button>
            </form>
          </section>
        </section>
      </div>
    </main>
  );
}

function createSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}
