"use client";

import { useState } from "react";
import Link from "next/link";
import FileUploadPanel from "@/features/data-sources/file-upload-panel";
import SqlServerConnectionPanel from "@/features/data-sources/sql-server-connection-panel";
import { AuthGuard } from "@/components/auth-guard";

type DataSourceTab = "upload" | "sql_server";

export default function DataSourcesPage() {
  return (
    <AuthGuard requireAdmin>
      <DataSourcesContent />
    </AuthGuard>
  );
}

function DataSourcesContent() {
  const [activeTab, setActiveTab] = useState<DataSourceTab>("upload");

  const tabClassName = (tab: DataSourceTab) =>
    `rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
      activeTab === tab
        ? "bg-sky-600 text-white"
        : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
    }`;

  return (
    <main className="mx-auto max-w-3xl p-8">
      <div className="mb-8">
        <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">
          ← Home
        </Link>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">Data Sources</h1>
        <p className="mt-1 text-slate-400">
          Upload a dataset or connect to a database. Everything you register
          here becomes available for analysis.
        </p>
      </div>

      <div className="mb-6 flex gap-2 rounded-xl border border-slate-800 bg-slate-900 p-2">
        <button className={tabClassName("upload")} onClick={() => setActiveTab("upload")}>
          Upload Dataset
        </button>
        <button
          className={tabClassName("sql_server")}
          onClick={() => setActiveTab("sql_server")}
        >
          SQL Server Connection
        </button>
      </div>

      {activeTab === "upload" ? <FileUploadPanel /> : <SqlServerConnectionPanel />}
    </main>
  );
}
