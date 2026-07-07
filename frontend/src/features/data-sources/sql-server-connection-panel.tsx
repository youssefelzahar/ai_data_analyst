"use client";

import { useCallback, useEffect, useState } from "react";
import {
  createSqlServerConnection,
  deleteDataSource,
  listDataSources,
  testSqlServerConnection,
} from "@/services/data-sources";
import type {
  AuthenticationType,
  DataSource,
  SqlServerConnectionCreate,
} from "@/types/data-source";

interface ConnectionFormState {
  connection_name: string;
  server_host: string;
  database_name: string;
  authentication_type: AuthenticationType;
  username: string;
  password: string;
}

const EMPTY_FORM: ConnectionFormState = {
  connection_name: "",
  server_host: "",
  database_name: "",
  authentication_type: "windows",
  username: "",
  password: "",
};

type FeedbackMessage = { kind: "success" | "error"; text: string } | null;

export default function SqlServerConnectionPanel() {
  const [connectionForm, setConnectionForm] = useState<ConnectionFormState>(EMPTY_FORM);
  const [savedConnections, setSavedConnections] = useState<DataSource[]>([]);
  const [feedback, setFeedback] = useState<FeedbackMessage>(null);
  const [isTestingConnection, setIsTestingConnection] = useState(false);
  const [isSavingConnection, setIsSavingConnection] = useState(false);

  const usesSqlAuthentication = connectionForm.authentication_type === "sql_server";

  const refreshSavedConnections = useCallback(async () => {
    try {
      setSavedConnections(await listDataSources("sql_server"));
    } catch {
      // listing failure shows as empty state; action errors are explicit
    }
  }, []);

  useEffect(() => {
    void refreshSavedConnections();
  }, [refreshSavedConnections]);

  const updateFormField = (fieldName: keyof ConnectionFormState, fieldValue: string) => {
    setConnectionForm((currentForm) => ({ ...currentForm, [fieldName]: fieldValue }));
  };

  const validateForm = (): string | null => {
    if (!connectionForm.connection_name.trim()) return "Connection name is required.";
    if (!connectionForm.server_host.trim()) return "Server name is required.";
    if (!connectionForm.database_name.trim()) return "Database name is required.";
    if (usesSqlAuthentication && (!connectionForm.username || !connectionForm.password)) {
      return "Username and password are required for SQL Server Authentication.";
    }
    return null;
  };

  const buildRequestPayload = (): SqlServerConnectionCreate => ({
    connection_name: connectionForm.connection_name.trim(),
    server_host: connectionForm.server_host.trim(),
    database_name: connectionForm.database_name.trim(),
    authentication_type: connectionForm.authentication_type,
    ...(usesSqlAuthentication
      ? { username: connectionForm.username, password: connectionForm.password }
      : {}),
  });

  const handleTestConnection = async () => {
    const validationError = validateForm();
    if (validationError) {
      setFeedback({ kind: "error", text: validationError });
      return;
    }
    setIsTestingConnection(true);
    setFeedback(null);
    try {
      const testResult = await testSqlServerConnection(buildRequestPayload());
      setFeedback({
        kind: testResult.success ? "success" : "error",
        text: testResult.message,
      });
    } catch (error) {
      setFeedback({
        kind: "error",
        text: error instanceof Error ? error.message : "Connection test failed",
      });
    } finally {
      setIsTestingConnection(false);
    }
  };

  const handleSaveConnection = async () => {
    const validationError = validateForm();
    if (validationError) {
      setFeedback({ kind: "error", text: validationError });
      return;
    }
    setIsSavingConnection(true);
    setFeedback(null);
    try {
      const savedConnection = await createSqlServerConnection(buildRequestPayload());
      setFeedback({
        kind: "success",
        text: `Connection "${savedConnection.name}" saved.`,
      });
      setConnectionForm(EMPTY_FORM);
      await refreshSavedConnections();
    } catch (error) {
      setFeedback({
        kind: "error",
        text: error instanceof Error ? error.message : "Saving the connection failed",
      });
    } finally {
      setIsSavingConnection(false);
    }
  };

  const handleDeleteConnection = async (dataSourceId: string) => {
    try {
      await deleteDataSource(dataSourceId);
      await refreshSavedConnections();
    } catch (error) {
      setFeedback({
        kind: "error",
        text: error instanceof Error ? error.message : "Delete failed",
      });
    }
  };

  const inputClassName =
    "w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm " +
    "placeholder:text-slate-600 focus:border-sky-500 focus:outline-none";

  return (
    <div className="space-y-6">
      <div className="space-y-4 rounded-xl border border-slate-800 bg-slate-900 p-6">
        <div>
          <label className="mb-1 block text-sm text-slate-400">Connection Name</label>
          <input
            className={inputClassName}
            placeholder="e.g. warehouse-production"
            value={connectionForm.connection_name}
            onChange={(event) => updateFormField("connection_name", event.target.value)}
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm text-slate-400">Server Name</label>
            <input
              className={inputClassName}
              placeholder="e.g. localhost\SQLEXPRESS"
              value={connectionForm.server_host}
              onChange={(event) => updateFormField("server_host", event.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-400">Database Name</label>
            <input
              className={inputClassName}
              placeholder="e.g. AdventureWorks"
              value={connectionForm.database_name}
              onChange={(event) => updateFormField("database_name", event.target.value)}
            />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm text-slate-400">Authentication Type</label>
          <select
            className={inputClassName}
            value={connectionForm.authentication_type}
            onChange={(event) =>
              updateFormField("authentication_type", event.target.value)
            }
          >
            <option value="windows">Windows Authentication</option>
            <option value="sql_server">SQL Server Authentication</option>
          </select>
        </div>

        {usesSqlAuthentication && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm text-slate-400">Username</label>
              <input
                className={inputClassName}
                autoComplete="off"
                value={connectionForm.username}
                onChange={(event) => updateFormField("username", event.target.value)}
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-slate-400">Password</label>
              <input
                className={inputClassName}
                type="password"
                autoComplete="new-password"
                value={connectionForm.password}
                onChange={(event) => updateFormField("password", event.target.value)}
              />
            </div>
          </div>
        )}

        {feedback && (
          <p
            className={`rounded-lg border px-4 py-2 text-sm ${
              feedback.kind === "success"
                ? "border-emerald-900 bg-emerald-950/50 text-emerald-400"
                : "border-red-900 bg-red-950/50 text-red-400"
            }`}
          >
            {feedback.text}
          </p>
        )}

        <div className="flex gap-3">
          <button
            onClick={() => void handleTestConnection()}
            disabled={isTestingConnection || isSavingConnection}
            className="rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium hover:border-sky-500 disabled:opacity-50"
          >
            {isTestingConnection ? "Testing…" : "Test Connection"}
          </button>
          <button
            onClick={() => void handleSaveConnection()}
            disabled={isTestingConnection || isSavingConnection}
            className="rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
          >
            {isSavingConnection ? "Saving…" : "Save Connection"}
          </button>
        </div>
      </div>

      <section>
        <h3 className="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Saved connections
        </h3>
        {savedConnections.length === 0 ? (
          <p className="text-sm text-slate-500">No saved connections yet.</p>
        ) : (
          <ul className="divide-y divide-slate-800 rounded-xl border border-slate-800 bg-slate-900">
            {savedConnections.map((savedConnection) => (
              <li
                key={savedConnection.id}
                className="flex items-center justify-between gap-4 px-4 py-3"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{savedConnection.name}</p>
                  <p className="text-xs text-slate-500">
                    {savedConnection.server_host} / {savedConnection.database_name} ·{" "}
                    {savedConnection.authentication_type === "windows"
                      ? "Windows Authentication"
                      : `SQL Server Authentication (${savedConnection.username})`}
                  </p>
                </div>
                <button
                  onClick={() => void handleDeleteConnection(savedConnection.id)}
                  className="rounded-lg border border-slate-700 px-3 py-1 text-xs text-slate-400 hover:border-red-800 hover:text-red-400"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}